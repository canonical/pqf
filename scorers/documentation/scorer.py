#!/usr/bin/env python3
"""documentation scorer — iterates leaf products and outputs per-leaf metrics."""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from engine.graph import build_graph, resolve_leaf_units
from scorers.documentation.logic import compute_metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-yaml", required=True)
    parser.add_argument(
        "--model",
        default=None,
        help="OpenRouter model ID (overrides OPENROUTER_MODEL env var)",
    )
    args = parser.parse_args()

    github_token = os.environ["GITHUB_TOKEN"]
    openrouter_api_key = os.environ["OPENROUTER_API_KEY"]
    model = args.model or os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")

    product = yaml.safe_load(Path(args.product_yaml).read_text())
    graph = build_graph([product])
    units = resolve_leaf_units(graph)

    results = {}
    for unit in units:
        results[unit.product_id] = compute_metrics(
            unit, github_token, openrouter_api_key, model=model
        )

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
