# engine/assemble.py
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from engine.drift_tracker import update_drift_history
from engine.graph import build_graph
from engine.medal_engine import compute_leaf_product, compute_root_product
from engine.models import ProductType


def _build_dimensions_meta(dimensions_config: dict) -> dict:
    meta = {}
    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        medals_meta: dict = {}
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


def _dim_to_dict(dim_result) -> dict:
    composition = None
    if dim_result.composition is not None:
        composition = [
            {
                "product_id": lr.product_id,
                "repo": lr.repo,
                "medal": lr.medal.value,
                "applicability": lr.applicability.value,
                "metrics": lr.metrics,
                "excluded_from_parent_medal": lr.excluded_from_parent_medal,
            }
            for lr in dim_result.composition
        ]
    return {
        "medal": dim_result.medal.value,
        "target": dim_result.target.value,
        "applicability": dim_result.applicability.value,
        "metrics": dim_result.metrics,
        "drift": {
            "status": dim_result.drift.status,
            "first_seen_at": dim_result.drift.first_seen_at,
            "deadline": dim_result.drift.deadline,
        } if dim_result.drift else None,
        "composition": composition,
    }


def _result_to_dict(result, node) -> dict:
    return {
        "id": result.product_id,
        "product_type": node.product_type.value,
        "name": node.name,
        "description": node.description,
        "lifecycle": node.lifecycle,
        "target_medal": result.target_medal.value,
        "current_medal": result.current_medal.value,
        "squad": node.ownership_squad,
        "is_portfolio_entry": node.is_portfolio_entry,
        "documentation_url": node.documentation_url,
        "source": (
            {"repo": node.source_repo, "subpath": node.source_subpath}
            if node.source_repo
            else None
        ),
        "composed_of": [
            {"product_id": e.product_id, "excluded_from_parent_medal": e.excluded_from_parent_medal}
            for e in node.composed_of
        ] if node.product_type == ProductType.ROOT else None,
        "context_refs": [
            {"label": cr.label, "repo": cr.repo} for cr in node.context_refs
        ],
        "parent_product_ids": node.parent_ids,
        "dimensions": {
            name: _dim_to_dict(dim) for name, dim in result.dimensions.items()
        },
    }


def assemble_portfolio(
    products_dir,
    computed_dir,
    dimensions_config,
    drift_history,
    update_drift,
) -> dict:
    products_dir = Path(products_dir)
    computed_dir = Path(computed_dir)
    now = datetime.now(UTC)

    product_dicts = [
        yaml.safe_load(p.read_text())
        for p in sorted(products_dir.glob("*.yaml"))
        if not p.name.startswith(".")
    ]
    graph = build_graph(product_dicts)

    # Load leaf metrics from computed files:
    # computed/{root-id}.json → {"leaf_metrics": {"leaf-id": {"dim": {metrics}}}}
    leaf_computed: dict[str, dict[str, dict]] = {}  # leaf_id -> dim_name -> metrics
    for path in sorted(computed_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for leaf_id, leaf_data in data.get("leaf_metrics", {}).items():
            if leaf_id not in leaf_computed:
                leaf_computed[leaf_id] = {}
            for key, value in leaf_data.items():
                if isinstance(value, dict):  # only dimension metric dicts
                    leaf_computed[leaf_id][key] = value

    # Compute leaf product results
    leaf_results = {}
    for node in graph.nodes.values():
        if node.product_type in (ProductType.CHARM, ProductType.SNAP):
            leaf_results[node.id] = compute_leaf_product(
                node.id,
                node.product_type.value,
                leaf_computed.get(node.id, {}),
                dimensions_config,
                drift_history,
                node.target_medal,
            )

    # Compute root product results
    root_results = {}
    for node in graph.nodes.values():
        if node.product_type == ProductType.ROOT:
            root_results[node.id] = compute_root_product(
                node.id, graph, leaf_results,
                dimensions_config, drift_history, node.target_medal, now,
            )

    if update_drift:
        for pid, result in {**root_results, **leaf_results}.items():
            for dim_name, dim_result in result.dimensions.items():
                update_drift_history(
                    pid, dim_name, dim_result.medal, result.target_medal, drift_history, now
                )

    # Emit all computed products: portfolio entries (root/standalone) AND inline leaves.
    # The UI overview filters by is_portfolio_entry; leaf detail pages need inline products too.
    all_results = {**root_results, **leaf_results}
    products_out = [
        _result_to_dict(all_results[node.id], node)
        for node in graph.nodes.values()
        if node.id in all_results
    ]

    return {
        "generated_at": now.isoformat(),
        "products": products_out,
        "dimensions_meta": _build_dimensions_meta(dimensions_config),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PQF portfolio assembler")
    parser.add_argument("--products-dir", required=True)
    parser.add_argument("--computed-dir", required=True)
    parser.add_argument("--dimensions", required=True)
    parser.add_argument("--drift-history", required=True, dest="drift_history")
    parser.add_argument("--output", required=True)
    parser.add_argument("--update-drift", action="store_true", dest="update_drift")
    args = parser.parse_args()

    dimensions_config = yaml.safe_load(Path(args.dimensions).read_text())
    drift_history_path = Path(args.drift_history)
    drift_history = json.loads(drift_history_path.read_text())

    portfolio = assemble_portfolio(
        products_dir=Path(args.products_dir),
        computed_dir=Path(args.computed_dir),
        dimensions_config=dimensions_config,
        drift_history=drift_history,
        update_drift=args.update_drift,
    )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(portfolio, indent=2) + "\n")

    if args.update_drift:
        drift_history_path.write_text(json.dumps(drift_history, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
