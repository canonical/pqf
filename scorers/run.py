#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.framework import FrameworkStatus, discover_frameworks, get_framework  # noqa: E402
from engine.graph import build_graph, resolve_leaf_units_for  # noqa: E402
from scorers.registry import DEFAULT_OPENROUTER_MODEL, ScorerContext, run_dimension  # noqa: E402


def _load_all_products(products_dir: Path) -> list[dict[str, Any]]:
    return [yaml.safe_load(path.read_text()) for path in sorted(products_dir.glob("*.yaml"))]


def _resolve_dimension_name(
    parser: argparse.ArgumentParser,
    parsed_dimension: str | None,
    fixed_dimension: str | None,
) -> str:
    if fixed_dimension is None:
        assert parsed_dimension is not None
        return parsed_dimension
    if parsed_dimension is not None and parsed_dimension != fixed_dimension:
        parser.error(
            f"--dimension {parsed_dimension!r} does not match fixed dimension {fixed_dimension!r}"
        )
    return fixed_dimension


def main(argv: list[str] | None = None, *, fixed_dimension: str | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a version-aware PQF scorer.")
    parser.add_argument("--framework-root", required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--dimension", required=fixed_dimension is None)
    parser.add_argument("--product-yaml", required=True)
    parser.add_argument(
        "--products-dir",
        default=None,
        help="Directory containing all product YAMLs (needed to resolve ref: entries).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenRouter model ID (overrides OPENROUTER_MODEL env var).",
    )
    args = parser.parse_args(argv)
    dimension_name = _resolve_dimension_name(parser, args.dimension, fixed_dimension)

    frameworks = discover_frameworks(Path(args.framework_root))
    selected_framework = get_framework(frameworks, args.framework_version)
    if selected_framework.status == FrameworkStatus.ARCHIVED:
        print(
            f"Framework version {selected_framework.id} is archived and cannot be used for "
            "scorer execution.",
            file=sys.stderr,
        )
        return 1

    try:
        dimension_config = selected_framework.dimensions["dimensions"][dimension_name]
    except KeyError:
        available = ", ".join(sorted(selected_framework.dimensions["dimensions"]))
        print(
            f"Unknown dimension {dimension_name!r} for framework {selected_framework.id}. "
            f"Available dimensions: {available}",
            file=sys.stderr,
        )
        return 1

    product_path = Path(args.product_yaml)
    product = yaml.safe_load(product_path.read_text())
    product_id = product["id"]

    products_dir = Path(args.products_dir) if args.products_dir else product_path.parent
    all_products = _load_all_products(products_dir)
    graph = build_graph(all_products, frameworks, selected_framework)
    units = resolve_leaf_units_for(graph, product_id)
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("GITHUB_TOKEN is required for scorer execution.", file=sys.stderr)
        return 1
    context = ScorerContext(
        github_token=github_token,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        openrouter_model=args.model or os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
    )

    results = {
        unit.product_id: run_dimension(unit, dimension_name, dimension_config, context)
        for unit in units
    }
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
