#!/usr/bin/env python3
"""support_engagement scorer — iterates leaf products and outputs per-leaf metrics."""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from engine.graph import build_graph, resolve_leaf_units
from scorers.support_engagement.logic import compute_metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-yaml", required=True)
    args = parser.parse_args()

    product = yaml.safe_load(Path(args.product_yaml).read_text())
    graph = build_graph([product])
    units = resolve_leaf_units(graph)
    github_token = os.environ["GITHUB_TOKEN"]

    results = {}
    for unit in units:
        results[unit.product_id] = compute_metrics(unit, github_token)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
