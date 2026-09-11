import json
import sys
from pathlib import Path

import pytest
import yaml

from engine import assemble
from engine.framework import contract_digest, discover_frameworks, get_framework

DIMS_CONFIG = {
    "dimensions": {
        "test_verification": {
            "label": "Test Verification",
            "description": "Automated test health.",
            "scorer": "scorers/test_verification/scorer.py",
            "applies_to": {"product_types": ["charm", "snap"]},
            "aggregation": "worst_in_scope",
            "outputs": {
                "coverage_pct": {
                    "implementation": "coverage-pct/v1",
                    "type": "number",
                    "label": "Coverage",
                    "description": "Coverage percentage.",
                    "range": "0-100",
                }
            },
            "medals": {
                "silver": ["coverage_pct >= 80"],
                "bronze": ["coverage_pct >= 70"],
            },
        },
        "documentation": {
            "label": "Documentation",
            "description": "Documentation baseline.",
            "scorer": "scorers/documentation/scorer.py",
            "applies_to": {"product_types": ["charm", "snap"]},
            "aggregation": "worst_in_scope",
            "outputs": {
                "has_readme": {
                    "implementation": "readme-present/v1",
                    "type": "boolean",
                    "label": "README present",
                    "description": "README.md exists.",
                }
            },
            "medals": {
                "gold": ["has_readme == true"],
                "bronze": ["has_readme == true"],
            },
        },
    }
}

ROOT_YAML = """\
id: matrix
product_type: root
name: Matrix
lifecycle: stable
introduced_in: v0
targets:
  v0: gold
  v1: gold
ownership:
  squad: americas
composed_of:
  - id: synapse
    product_type: charm
    introduced_in: v0
    source:
      repo: canonical/synapse-operator
context_refs:
  - label: PostgreSQL
    repo: canonical/postgresql-k8s-operator
"""

IMPLEMENTATION_FINGERPRINTS = {
    "coverage-pct/v1": "coverage-sha",
    "readme-present/v1": "readme-sha",
}


def _write_framework_version(root: Path, *, version_id: str, sequence: int, status: str) -> None:
    version_dir = root / version_id
    version_dir.mkdir(parents=True)
    (version_dir / "framework.yaml").write_text(
        yaml.safe_dump(
            {
                "id": version_id,
                "sequence": sequence,
                "label": f"PQF {version_id.upper()}",
                "status": status,
                "description": f"{version_id} contract",
            },
            sort_keys=False,
        )
    )
    (version_dir / "dimensions.yaml").write_text(yaml.safe_dump(DIMS_CONFIG, sort_keys=False))


def _write_computed_file(
    root: Path,
    *,
    framework_version: str,
    selected_framework,
    product_id: str = "matrix",
    test_coverage: int = 75,
    has_readme: bool = True,
    contract_digest_override: str | None = None,
) -> None:
    version_dir = root / "versions" / framework_version
    version_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "framework_version": framework_version,
        "contract_digest": contract_digest_override or contract_digest(selected_framework),
        "implementation_fingerprints": IMPLEMENTATION_FINGERPRINTS,
        "product_id": product_id,
        "computed_at": "2026-01-01T00:00:00+00:00",
        "leaf_metrics": {
            "synapse": {
                "test_verification": {"coverage_pct": test_coverage},
                "documentation": {"has_readme": has_readme},
            }
        },
    }
    (version_dir / f"{product_id}.json").write_text(json.dumps(payload))


@pytest.fixture
def repo_fixture(tmp_path):
    products_dir = tmp_path / "products"
    products_dir.mkdir()
    (products_dir / "matrix.yaml").write_text(ROOT_YAML)

    framework_root = tmp_path / "framework" / "versions"
    _write_framework_version(framework_root, version_id="v0", sequence=0, status="active")
    _write_framework_version(framework_root, version_id="v1", sequence=1, status="upcoming")

    frameworks = discover_frameworks(framework_root)
    return {
        "products_dir": products_dir,
        "computed_dir": tmp_path / "computed",
        "framework_root": framework_root,
        "frameworks": frameworks,
        "v0": get_framework(frameworks, "v0"),
        "v1": get_framework(frameworks, "v1"),
    }


@pytest.fixture
def portfolio(repo_fixture):
    _write_computed_file(
        repo_fixture["computed_dir"],
        framework_version="v0",
        selected_framework=repo_fixture["v0"],
    )
    return assemble.assemble_portfolio(
        products_dir=repo_fixture["products_dir"],
        computed_dir=repo_fixture["computed_dir"],
        frameworks=repo_fixture["frameworks"],
        selected_framework=repo_fixture["v0"],
        source_revision="deadbeef",
    )


def test_portfolio_embeds_framework_and_compliance_metadata(portfolio, repo_fixture):
    assert portfolio["framework"] == {
        "id": "v0",
        "sequence": 0,
        "label": "PQF V0",
        "status": "active",
        "description": "v0 contract",
    }
    assert portfolio["contract_digest"] == contract_digest(repo_fixture["v0"])
    assert portfolio["source_revision"] == "deadbeef"
    assert portfolio["implementation_fingerprints"] == IMPLEMENTATION_FINGERPRINTS
    assert portfolio["compliance_summary"] == {
        "total": 1,
        "meeting_target": 0,
        "below_target": 1,
        "insufficient_data": 0,
    }


def test_portfolio_contains_root_product(portfolio):
    ids = [p["id"] for p in portfolio["products"]]
    assert "matrix" in ids


def test_root_product_has_correct_type(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    assert matrix["product_type"] == "root"
    assert matrix["is_portfolio_entry"] is True
    assert matrix["meets_target"] is False


def test_inline_leaf_included_in_products_but_not_portfolio_entry(portfolio):
    ids = [p["id"] for p in portfolio["products"]]
    assert "synapse" in ids
    synapse = next(p for p in portfolio["products"] if p["id"] == "synapse")
    assert synapse["is_portfolio_entry"] is False


def test_root_dimension_has_composition(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    dim = matrix["dimensions"]["test_verification"]
    assert dim["result"] == "bronze"
    assert dim["meets_target"] is False
    assert dim["composition"] is not None
    assert len(dim["composition"]) == 1
    assert dim["composition"][0]["product_id"] == "synapse"
    assert dim["composition"][0]["result"] == "bronze"


def test_root_product_has_current_status(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    assert matrix["current_result"] == "bronze"
    assert matrix["target_result"] == "gold"


def test_context_refs_in_portfolio(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    assert len(matrix["context_refs"]) == 1
    assert matrix["context_refs"][0]["label"] == "PostgreSQL"


def test_dimensions_meta_has_applies_to(portfolio):
    meta = portfolio["dimensions_meta"]["test_verification"]
    assert "charm" in meta["applies_to"]
    assert meta["aggregation"] == "worst_in_scope"


def test_assemble_portfolio_rejects_mismatched_contract_digest(repo_fixture):
    _write_computed_file(
        repo_fixture["computed_dir"],
        framework_version="v0",
        selected_framework=repo_fixture["v0"],
        contract_digest_override="not-the-real-digest",
    )

    with pytest.raises(ValueError, match="contract digest"):
        assemble.assemble_portfolio(
            products_dir=repo_fixture["products_dir"],
            computed_dir=repo_fixture["computed_dir"],
            frameworks=repo_fixture["frameworks"],
            selected_framework=repo_fixture["v0"],
            source_revision="deadbeef",
        )


def test_assemble_portfolio_requires_selected_version_directory(repo_fixture):
    with pytest.raises(ValueError, match="Missing computed version directory"):
        assemble.assemble_portfolio(
            products_dir=repo_fixture["products_dir"],
            computed_dir=repo_fixture["computed_dir"],
            frameworks=repo_fixture["frameworks"],
            selected_framework=repo_fixture["v0"],
            source_revision="deadbeef",
        )


def test_assemble_cli_writes_selected_version_without_touching_existing_portfolio(
    tmp_path, monkeypatch, repo_fixture
):
    _write_computed_file(
        repo_fixture["computed_dir"],
        framework_version="v1",
        selected_framework=repo_fixture["v1"],
        test_coverage=85,
    )
    existing_v0 = tmp_path / "public" / "versions" / "v0" / "portfolio.json"
    existing_v0.parent.mkdir(parents=True)
    existing_v0.write_text('{"sentinel": "keep-me"}\n')

    output = tmp_path / "public" / "versions" / "v1" / "portfolio.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assemble.py",
            "--products-dir",
            str(repo_fixture["products_dir"]),
            "--computed-dir",
            str(repo_fixture["computed_dir"]),
            "--framework-root",
            str(repo_fixture["framework_root"]),
            "--framework-version",
            "v1",
            "--source-revision",
            "cafebabe",
            "--output",
            str(output),
        ],
    )

    assert assemble.main() == 0
    assert existing_v0.read_text() == '{"sentinel": "keep-me"}\n'
    written = json.loads(output.read_text())
    assert written["framework"]["id"] == "v1"
    assert written["source_revision"] == "cafebabe"
