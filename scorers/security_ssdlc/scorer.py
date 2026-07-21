#!/usr/bin/env python3
"""security_ssdlc scorer — iterates leaf products and outputs per-leaf metrics."""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from engine.graph import build_graph, resolve_leaf_units_for
from scorers.security_ssdlc.logic import compute_metrics


def _load_all_products(products_dir: Path) -> list[dict]:
    return [yaml.safe_load(f.read_text()) for f in sorted(products_dir.glob("*.yaml"))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-yaml", required=True)
    parser.add_argument("--products-dir", default=None,
                        help="Directory containing all product YAMLs "
                             "(needed to resolve ref: entries).")
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
