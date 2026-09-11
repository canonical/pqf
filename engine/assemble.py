import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from engine.framework import FrameworkVersion, contract_digest, discover_frameworks, get_framework
from engine.graph import build_graph
from engine.medal_engine import compute_leaf_product, compute_root_product
from engine.models import ApplicabilityOutcome, ProductType


def _build_dimensions_meta(dimensions_config: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        medals_meta: dict[str, Any] = {}
        for tier, conditions in dim_config.get("medals", {}).items():
            medals_meta[tier] = {"criteria": conditions}
        outputs_meta = {}
        for metric_name, metric_cfg in dim_config.get("outputs", {}).items():
            if not isinstance(metric_cfg, dict):
                continue
            outputs_meta[metric_name] = {
                "label": metric_cfg.get("label", metric_name),
                "description": metric_cfg.get("description", ""),
                "type": metric_cfg.get("type", "unknown"),
                "range": metric_cfg.get("range", ""),
                "ai_assisted": metric_cfg.get("ai_assisted", False),
                "informational": metric_cfg.get("informational", False),
            }
        meta[dim_name] = {
            "label": dim_config.get("label", dim_name.replace("_", " ").title()),
            "description": dim_config.get("description", ""),
            "applies_to": dim_config.get("applies_to", {}).get("product_types", []),
            "aggregation": dim_config.get("aggregation", "worst_in_scope"),
            "outputs": outputs_meta,
            "medals": medals_meta,
        }
    return meta


def _dim_to_dict(dim_result) -> dict[str, Any]:
    composition = None
    if dim_result.composition is not None:
        composition = [
            {
                "product_id": leaf_result.product_id,
                "repo": leaf_result.repo,
                "medal": leaf_result.medal.value,
                "result": leaf_result.result.value,
                "applicability": leaf_result.applicability.value,
                "metrics": leaf_result.metrics,
                "excluded_from_parent_medal": leaf_result.excluded_from_parent_medal,
            }
            for leaf_result in dim_result.composition
        ]
    return {
        "medal": dim_result.medal.value,
        "target": dim_result.target.value,
        "applicability": dim_result.applicability.value,
        "meets_target": dim_result.meets_target,
        "result": dim_result.result.value,
        "metrics": dim_result.metrics,
        "composition": composition,
    }


def _result_to_dict(result, node) -> dict[str, Any]:
    return {
        "id": result.product_id,
        "product_type": node.product_type.value,
        "name": node.name,
        "description": node.description,
        "lifecycle": node.lifecycle,
        "current_medal": result.current_medal.value,
        "target_medal": result.target_medal.value,
        "current_result": result.current_result.value,
        "target_result": result.target_result.value,
        "meets_target": result.meets_target,
        "squad": node.ownership_squad,
        "is_portfolio_entry": node.is_portfolio_entry,
        "documentation_url": node.documentation_url,
        "source": (
            {"repo": node.source_repo, "subpath": node.source_subpath} if node.source_repo else None
        ),
        "composed_of": [
            {
                "product_id": edge.product_id,
                "excluded_from_parent_medal": edge.excluded_from_parent_medal,
            }
            for edge in node.composed_of
        ]
        if node.product_type == ProductType.ROOT
        else None,
        "context_refs": [
            {"label": context_ref.label, "repo": context_ref.repo}
            for context_ref in node.context_refs
        ],
        "parent_product_ids": node.parent_ids,
        "dimensions": {name: _dim_to_dict(dim) for name, dim in result.dimensions.items()},
    }


def _framework_to_dict(framework: FrameworkVersion) -> dict[str, Any]:
    return {
        "id": framework.id,
        "sequence": framework.sequence,
        "label": framework.label,
        "status": framework.status.value,
        "description": framework.description,
    }


def _versioned_computed_dir(computed_dir: Path, selected_framework: FrameworkVersion) -> Path:
    version_dir = computed_dir / "versions" / selected_framework.id
    if not version_dir.exists():
        raise ValueError(f"Missing computed version directory {version_dir}")
    return version_dir


def _validate_envelope(
    path: Path,
    payload: dict[str, Any],
    *,
    selected_framework: FrameworkVersion,
    expected_contract_digest: str,
) -> dict[str, str]:
    if payload.get("framework_version") != selected_framework.id:
        raise ValueError(
            f"{path} targets framework version {payload.get('framework_version')!r}, "
            f"expected {selected_framework.id!r}"
        )

    actual_digest = payload.get("contract_digest")
    if actual_digest != expected_contract_digest:
        raise ValueError(
            f"{path} has contract digest {actual_digest!r}; expected contract digest "
            f"{expected_contract_digest!r}"
        )

    implementation_fingerprints = payload.get("implementation_fingerprints")
    if not isinstance(implementation_fingerprints, dict):
        raise ValueError(f"{path} is missing implementation_fingerprints")

    return implementation_fingerprints


def _load_leaf_metrics(
    computed_dir: Path,
    *,
    selected_framework: FrameworkVersion,
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, str]]:
    expected_digest = contract_digest(selected_framework)
    implementation_fingerprints: dict[str, str] | None = None
    leaf_computed: dict[str, dict[str, dict[str, Any]]] = {}
    version_dir = _versioned_computed_dir(computed_dir, selected_framework)
    computed_paths = sorted(version_dir.glob("*.json"))
    if not computed_paths:
        raise ValueError(f"No computed envelopes found in {version_dir}")

    for path in computed_paths:
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid computed JSON in {path}: {exc}") from exc

        envelope_fingerprints = _validate_envelope(
            path,
            payload,
            selected_framework=selected_framework,
            expected_contract_digest=expected_digest,
        )
        if implementation_fingerprints is None:
            implementation_fingerprints = envelope_fingerprints
        elif envelope_fingerprints != implementation_fingerprints:
            raise ValueError(f"{path} has mismatched implementation fingerprints")

        for leaf_id, leaf_data in payload.get("leaf_metrics", {}).items():
            if leaf_id not in leaf_computed:
                leaf_computed[leaf_id] = {}
            for dimension_name, metrics in leaf_data.items():
                if isinstance(metrics, dict):
                    leaf_computed[leaf_id][dimension_name] = metrics

    return leaf_computed, implementation_fingerprints or {}


def _compliance_summary(products: list[dict[str, Any]]) -> dict[str, int]:
    portfolio_entries = [product for product in products if product["is_portfolio_entry"]]
    total = len(portfolio_entries)
    meeting_target = sum(1 for product in portfolio_entries if product["meets_target"])
    insufficient_data = sum(
        1
        for product in portfolio_entries
        if not product["meets_target"]
        and any(
            dimension["applicability"] == ApplicabilityOutcome.INSUFFICIENT_DATA.value
            for dimension in product["dimensions"].values()
        )
    )
    return {
        "total": total,
        "meeting_target": meeting_target,
        "below_target": total - meeting_target - insufficient_data,
        "insufficient_data": insufficient_data,
    }


def assemble_portfolio(
    products_dir,
    computed_dir,
    frameworks,
    selected_framework,
    source_revision: str,
) -> dict:
    products_dir = Path(products_dir)
    computed_dir = Path(computed_dir)
    now = datetime.now(UTC)

    product_dicts = [
        yaml.safe_load(path.read_text())
        for path in sorted(products_dir.glob("*.yaml"))
        if not path.name.startswith(".")
    ]
    dimensions_config = selected_framework.dimensions
    graph = build_graph(product_dicts, frameworks, selected_framework)
    leaf_computed, implementation_fingerprints = _load_leaf_metrics(
        computed_dir,
        selected_framework=selected_framework,
    )

    leaf_results = {}
    for node in graph.nodes.values():
        if node.product_type in (ProductType.CHARM, ProductType.SNAP):
            leaf_results[node.id] = compute_leaf_product(
                node.id,
                node.product_type.value,
                leaf_computed.get(node.id, {}),
                dimensions_config,
                node.target_medal,
            )

    root_results = {}
    for node in graph.nodes.values():
        if node.product_type == ProductType.ROOT:
            root_results[node.id] = compute_root_product(
                node.id,
                graph,
                leaf_results,
                dimensions_config,
                node.target_medal,
            )

    all_results = {**root_results, **leaf_results}
    products_out = [
        _result_to_dict(all_results[node.id], node)
        for node in graph.nodes.values()
        if node.id in all_results
    ]

    return {
        "generated_at": now.isoformat(),
        "framework": _framework_to_dict(selected_framework),
        "contract_digest": contract_digest(selected_framework),
        "source_revision": source_revision,
        "implementation_fingerprints": implementation_fingerprints,
        "compliance_summary": _compliance_summary(products_out),
        "products": products_out,
        "dimensions_meta": _build_dimensions_meta(dimensions_config),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PQF portfolio assembler")
    parser.add_argument("--products-dir", required=True)
    parser.add_argument("--computed-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--framework-root", required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()

    frameworks = discover_frameworks(Path(args.framework_root))
    selected_framework = get_framework(frameworks, args.framework_version)

    try:
        portfolio = assemble_portfolio(
            products_dir=Path(args.products_dir),
            computed_dir=Path(args.computed_dir),
            frameworks=frameworks,
            selected_framework=selected_framework,
            source_revision=args.source_revision,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(portfolio, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
