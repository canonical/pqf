"""Build the GitHub Actions matrix of framework/product/dimension rows to score.

Selection rules:
    - nightly: every active framework version.
    - weekly: every upcoming framework version.
    - manual: exactly the requested framework version, which must be active or
      upcoming (never archived).

Each selected framework version contributes one matrix row per (product, dimension)
pair, for every product whose introduced_in/retired_in boundaries include that
framework version. The output is printed as compact JSON shaped for consumption
via `fromJson(...)` in a workflow `strategy.matrix`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from engine.framework import FrameworkStatus, FrameworkVersion, discover_frameworks, get_framework
from engine.versioning import is_in_version

CADENCES = ("nightly", "weekly", "manual")

_CADENCE_STATUS = {
    "nightly": FrameworkStatus.ACTIVE,
    "weekly": FrameworkStatus.UPCOMING,
}


def select_frameworks(
    frameworks: list[FrameworkVersion],
    *,
    cadence: str,
    framework_version: str | None = None,
) -> list[FrameworkVersion]:
    """Select the framework versions in scope for a given cadence.

    Raises ValueError for an unknown cadence, a missing/archived manual
    selection, or a framework-version argument supplied for a scheduled cadence.
    """
    if cadence not in CADENCES:
        raise ValueError(f"Unknown cadence: {cadence!r}. Expected one of {CADENCES}.")

    if cadence == "manual":
        if not framework_version:
            raise ValueError("--framework-version is required for manual cadence")
        selected = get_framework(frameworks, framework_version)
        if selected.status == FrameworkStatus.ARCHIVED:
            raise ValueError(
                f"Framework version {selected.id} is archived and cannot be scheduled for scoring."
            )
        return [selected]

    if framework_version:
        raise ValueError(f"--framework-version is not supported for {cadence} cadence")

    status = _CADENCE_STATUS[cadence]
    return [framework for framework in frameworks if framework.status == status]


def _load_products(products_dir: Path) -> list[dict[str, Any]]:
    return [
        yaml.safe_load(path.read_text())
        for path in sorted(products_dir.glob("*.yaml"))
        if not path.name.startswith(".")
    ]


def build_matrix_rows(
    frameworks: list[FrameworkVersion],
    selected: list[FrameworkVersion],
    products_dir: Path,
) -> list[dict[str, str]]:
    """Build {"framework_version", "product", "dimension"} rows for the selected versions.

    Products whose introduced_in/retired_in boundaries exclude a selected framework
    version are skipped for that version.
    """
    products = _load_products(products_dir)
    rows: list[dict[str, str]] = []
    for framework in selected:
        dimension_names = sorted(framework.dimensions.get("dimensions", {}))
        for product in products:
            if not is_in_version(product, frameworks, framework):
                continue
            for dimension_name in dimension_names:
                rows.append(
                    {
                        "framework_version": framework.id,
                        "product": product["id"],
                        "dimension": dimension_name,
                    }
                )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the framework/product/dimension matrix for a workflow run."
    )
    parser.add_argument("--framework-root", default="framework/versions")
    parser.add_argument("--products-dir", default="products")
    parser.add_argument("--cadence", required=True, choices=CADENCES)
    parser.add_argument(
        "--framework-version",
        default=None,
        help="Required for --cadence manual; must be an active or upcoming version.",
    )
    args = parser.parse_args(argv)

    try:
        frameworks = discover_frameworks(Path(args.framework_root))
        selected = select_frameworks(
            frameworks,
            cadence=args.cadence,
            framework_version=args.framework_version,
        )
        rows = build_matrix_rows(frameworks, selected, Path(args.products_dir))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps({"include": rows}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
