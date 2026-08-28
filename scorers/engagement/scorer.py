#!/usr/bin/env python3
"""engagement scorer — iterates leaf products and outputs per-leaf metrics."""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

# Ensure local repo modules are imported when running this file directly.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_all_products(products_dir: Path) -> list[dict]:
    return [yaml.safe_load(f.read_text()) for f in sorted(products_dir.glob("*.yaml"))]


def main() -> int:
    from engine.graph import build_graph, resolve_leaf_units_for
    from scorers.engagement.logic import compute_metrics

    parser = argparse.ArgumentParser()
    parser.add_argument("--product-yaml", required=True)
    parser.add_argument(
        "--products-dir",
        default=None,
        help="Directory containing all product YAMLs (needed to resolve ref: entries).",
    )
    args = parser.parse_args()

    product_path = Path(args.product_yaml)
    product = yaml.safe_load(product_path.read_text())
    product_id = product["id"]

    products_dir = Path(args.products_dir) if args.products_dir else product_path.parent
    all_products = _load_all_products(products_dir)
    graph = build_graph(all_products)
    units = resolve_leaf_units_for(graph, product_id)
    github_token = os.environ["GITHUB_TOKEN"]

    results = {}
    for unit in units:
        results[unit.product_id] = compute_metrics(unit, github_token)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
