# engine/__main__.py
"""
CLI entry point for the PQF medal engine.

Usage:
    python -m engine \
        --product products/matrix.yaml \
        --computed computed/matrix.json \
        --dimensions config/dimensions.yaml \
        --drift-history drift-history.json

    # With drift-history update (call after all per-dimension results are in):
    python -m engine ... --update-drift
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from engine.drift_tracker import update_drift_history
from engine.medal_engine import compute_product
from engine.models import DimensionResult, DriftState, Medal, ProductResult


def _drift_to_dict(drift: DriftState | None) -> dict | None:
    if drift is None:
        return None
    return {
        "status": drift.status,
        "first_seen_at": drift.first_seen_at,
        "deadline": drift.deadline,
    }


def _dimension_to_dict(dim: DimensionResult) -> dict:
    return {
        "medal": dim.medal.value,
        "target": dim.target.value,
        "status": dim.status.value,
        "metrics": dim.metrics,
        "drift": _drift_to_dict(dim.drift),
    }


def _result_to_portfolio_entry(result: ProductResult, product: dict) -> dict:
    """Produce the product entry as it appears in public/portfolio.json."""
    return {
        "id": result.product_id,
        "name": product.get("name", result.product_id),
        "description": product.get("description", ""),
        "lifecycle": product.get("lifecycle", ""),
        "target_medal": result.target_medal.value,
        "current_medal": result.current_medal.value,
        "current_status": result.current_status.value,
        "squad": product.get("ownership", {}).get("squad", ""),
        "documentation_url": product.get("documentation_url", ""),
        "components": product.get("components", {}),
        "dimensions": {name: _dimension_to_dict(dim) for name, dim in result.dimensions.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PQF Medal Engine")
    parser.add_argument("--product", required=True, help="Path to products/<id>.yaml")
    parser.add_argument("--computed", required=True, help="Path to computed/<id>.json")
    parser.add_argument("--dimensions", required=True, help="Path to config/dimensions.yaml")
    parser.add_argument(
        "--drift-history", required=True, dest="drift_history", help="Path to drift-history.json"
    )
    parser.add_argument(
        "--update-drift",
        action="store_true",
        dest="update_drift",
        help="Mutate drift-history.json with current run's results",
    )
    args = parser.parse_args()

    product = yaml.safe_load(Path(args.product).read_text())

    computed_path = Path(args.computed)
    computed = json.loads(computed_path.read_text()) if computed_path.exists() else {}

    dimensions = yaml.safe_load(Path(args.dimensions).read_text())
    drift_history_path = Path(args.drift_history)
    drift_history = json.loads(drift_history_path.read_text())

    result = compute_product(product, computed, dimensions, drift_history)

    if args.update_drift:
        now = datetime.now(UTC)
        for dim_name, dim_result in result.dimensions.items():
            update_drift_history(
                product["id"],
                dim_name,
                dim_result.medal,
                Medal(product["target_medal"]),
                drift_history,
                now,
            )
        drift_history_path.write_text(json.dumps(drift_history, indent=2) + "\n")

    entry = _result_to_portfolio_entry(result, product)
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
