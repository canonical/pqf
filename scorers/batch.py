#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from engine.framework import FrameworkStatus, discover_frameworks, get_framework
from engine.graph import build_graph, resolve_leaf_units_for
from scorers import registry


def _load_all_products(products_dir: Path) -> list[dict[str, Any]]:
    return [yaml.safe_load(path.read_text()) for path in sorted(products_dir.glob("*.yaml"))]


def _parse_version_ids(value: str) -> list[str]:
    try:
        version_ids = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("--framework-versions-json must be valid JSON") from exc
    if (
        not isinstance(version_ids, list)
        or not version_ids
        or not all(isinstance(version_id, str) and version_id for version_id in version_ids)
    ):
        raise ValueError("--framework-versions-json must be a non-empty JSON array of strings")
    if len(version_ids) != len(set(version_ids)):
        raise ValueError("--framework-versions-json must not contain duplicate versions")
    return version_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score one product across framework versions.")
    parser.add_argument("--framework-root", required=True)
    parser.add_argument("--framework-versions-json", required=True)
    parser.add_argument("--product-yaml", required=True)
    parser.add_argument("--products-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)

    try:
        version_ids = _parse_version_ids(args.framework_versions_json)
        frameworks = discover_frameworks(Path(args.framework_root))
        selected = [get_framework(frameworks, version_id) for version_id in version_ids]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    archived = [
        framework.id for framework in selected if framework.status == FrameworkStatus.ARCHIVED
    ]
    if archived:
        print(
            "Archived framework versions cannot be used for scorer execution: "
            + ", ".join(archived),
            file=sys.stderr,
        )
        return 1

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("GITHUB_TOKEN is required for scorer execution.", file=sys.stderr)
        return 1

    context = registry.ScorerContext(
        github_token=github_token,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        openrouter_model=args.model
        or os.environ.get("OPENROUTER_MODEL", registry.DEFAULT_OPENROUTER_MODEL),
    )
    product_path = Path(args.product_yaml)
    product = yaml.safe_load(product_path.read_text())
    product_id = product["id"]
    all_products = _load_all_products(Path(args.products_dir))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runner_cache = registry.RunnerCache()

    for framework in selected:
        graph = build_graph(all_products, frameworks, framework)
        units = resolve_leaf_units_for(graph, product_id)
        for dimension_name, dimension_config in framework.dimensions["dimensions"].items():
            results = {
                unit.product_id: registry.run_dimension(
                    unit,
                    dimension_name,
                    dimension_config,
                    context,
                    runner_cache=runner_cache,
                )
                for unit in units
            }
            output_path = output_dir / f"{framework.id}__{product_id}__{dimension_name}.json"
            output_path.write_text(json.dumps(results, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
