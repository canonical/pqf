import json
from pathlib import Path

import pytest
import yaml

from engine.assemble import assemble_portfolio
from engine.framework import contract_digest, discover_frameworks, get_framework
from engine.graph import build_graph, resolve_leaf_units_for
from engine.merge_computed import merge_scorer_outputs
from engine.metric_outcomes import insufficient_data, measured, not_applicable, serialize_metrics
from engine.models import ProductType
from scorers import registry


@pytest.mark.parametrize("unknown_required", [False, True])
def test_v0_outcomes_survive_complete_generation_pipeline(tmp_path, monkeypatch, unknown_required):
    framework_root = Path(__file__).resolve().parents[2] / "framework/versions"
    frameworks = discover_frameworks(framework_root)
    framework = get_framework(frameworks, "v0")
    dimensions = framework.dimensions["dimensions"]
    product = {
        "id": "demo",
        "product_type": "root",
        "name": "Demo",
        "introduced_in": "v0",
        "targets": {"v0": "gold"},
        "composed_of": [
            {
                "id": kind,
                "product_type": "snap" if kind == "snap" else "charm",
                "introduced_in": "v0",
                "source": {"repo": f"canonical/{kind}"},
            }
            for kind in ("k8s", "machine", "snap")
        ],
    }
    products_dir = tmp_path / "products"
    products_dir.mkdir()
    (products_dir / "demo.yaml").write_text(yaml.safe_dump(product))
    units = resolve_leaf_units_for(build_graph([product], frameworks, framework), "demo")

    def testing(unit, context):
        outputs = {key: measured(True) for key in dimensions["test_verification"]["outputs"]}
        outputs["ci_passing"] = insufficient_data("No attributable run.")
        outputs["uses_tf_v1_provider"] = not_applicable("No Terraform modules.")
        if unit.product_id == "machine":
            outputs["supports_canonical_k8s"] = not_applicable("Machine charm.")
        if unit.product_type == ProductType.SNAP:
            outputs = {
                key: not_applicable("Not a charm.") for key in outputs if key != "ci_passing"
            } | {"ci_passing": measured(False)}
        if unknown_required and unit.product_id == "k8s":
            outputs["uses_jubilant"] = insufficient_data("Tests could not be interpreted.")
        return outputs

    def documentation(unit, context):
        return {
            "readme_present": measured(True),
            "contributing_present": measured(True),
            "has_security": measured(True),
            "diataxis_coverage_ai": insufficient_data("AI disabled."),
            "uses_sphinx_stack": not_applicable("Snap.")
            if unit.product_type == ProductType.SNAP
            else measured("1.2.3"),
        }

    def security(unit, context):
        return {key: measured(True) for key in dimensions["security_ssdlc"]["outputs"]}

    monkeypatch.setattr(
        registry,
        "RUNNERS",
        {
            **registry.RUNNERS,
            "v0_testing": testing,
            "v0_documentation": documentation,
            "v0_security": security,
        },
    )
    scorer_dir = tmp_path / "scorers"
    scorer_dir.mkdir()
    fingerprints = {}
    for name, config in dimensions.items():
        outcomes = {
            unit.product_id: serialize_metrics(
                registry.run_dimension(
                    unit,
                    name,
                    config,
                    registry.ScorerContext("token"),
                )
            )
            for unit in units
        }
        (scorer_dir / f"{name}.json").write_text(json.dumps(outcomes))
        fingerprints.update(registry.implementation_fingerprints(config))
    merged = merge_scorer_outputs(
        product_id="demo",
        scorer_dir=scorer_dir,
        dimensions_config=framework.dimensions,
        framework_version="v0",
        contract_digest=contract_digest(framework),
        implementation_fingerprints=fingerprints,
    )
    computed_dir = tmp_path / "computed/versions/v0"
    computed_dir.mkdir(parents=True)
    (computed_dir / "demo.json").write_text(json.dumps(merged))
    published = assemble_portfolio(
        products_dir,
        tmp_path / "computed",
        frameworks,
        framework,
        "revision",
    )
    products = {item["id"]: item for item in published["products"]}
    assert products["demo"]["current_result"] == (
        "insufficient_data" if unknown_required else "gold"
    )
    assert products["snap"]["dimensions"]["test_verification"]["result"] == "not_applicable"
    assert products["machine"]["dimensions"]["test_verification"]["metrics"][
        "supports_canonical_k8s"
    ] == {
        "state": "not_applicable",
        "value": None,
        "reason": "Machine charm.",
    }
    assert products["snap"]["dimensions"]["test_verification"]["metrics"]["ci_passing"] == {
        "state": "measured",
        "value": False,
    }
    assert published["metric_schema_version"] == 1
