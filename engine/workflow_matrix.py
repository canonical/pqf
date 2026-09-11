"""Build the GitHub Actions matrix of framework/product rows to score.

Selection rules:
    - nightly: every active framework version.
    - weekly: every upcoming framework version.
    - manual: exactly the requested framework version, which must be active or
      upcoming (never archived).
    - changed: every live framework version whose framework, scorer, engine, or
      catalog inputs changed (used for push/pull_request events).

Whatever the cadence selects is then unioned with the *bootstrap* set: every live
(active or upcoming) framework version whose published portfolio is missing or was
built from a different scoring contract. That guarantees the publish job can always
rebuild a complete version index, because each live version is either computed in
this run or carried forward unchanged from the previously published site. Archived
versions are never selected: their measurements are frozen and their scorers must
never run again.

Each selected framework version contributes one matrix row per product, for every
product whose introduced_in/retired_in boundaries include that framework version.
Each job is expected to loop over that framework version's dimensions itself, which
keeps the matrix small and amortizes checkout/install across all dimensions. The
output is printed as compact JSON shaped for consumption via `fromJson(...)` in a
workflow `strategy.matrix`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from engine.framework import (
    FrameworkStatus,
    FrameworkVersion,
    contract_digest,
    discover_frameworks,
    get_framework,
)
from engine.versioning import is_in_version

CADENCES = ("nightly", "weekly", "manual", "changed")

#: Exact mapping from the cron literals declared in
#: `.github/workflows/compute-metrics.yml` to the cadence they trigger.
#: `test_workflows.py` asserts the workflow's declared cron entries match this
#: mapping exactly, so the two can never drift apart silently.
SCHEDULE_CADENCES = {
    "0 2 * * *": "nightly",
    "0 3 * * 1": "weekly",
}

#: Changes under these paths can affect the scoring of every live framework version.
BROAD_CHANGE_PREFIXES = (
    "scorers/",
    "engine/",
    "config/",
    "products/",
    ".github/workflows/compute-metrics.yml",
)

_LIVE_STATUSES = (FrameworkStatus.ACTIVE, FrameworkStatus.UPCOMING)

_CADENCE_STATUS = {
    "nightly": FrameworkStatus.ACTIVE,
    "weekly": FrameworkStatus.UPCOMING,
}


def cadence_for_schedule(schedule: str) -> str:
    """Map a cron literal from `github.event.schedule` to its cadence.

    Raises ValueError for any cron that is not declared in SCHEDULE_CADENCES, so a
    workflow/schedule mismatch fails loudly instead of silently scoring the wrong
    framework versions.
    """
    try:
        return SCHEDULE_CADENCES[schedule.strip()]
    except KeyError:
        known = ", ".join(sorted(SCHEDULE_CADENCES))
        raise ValueError(f"Unknown schedule cron: {schedule!r}. Declared crons: {known}") from None


def _is_live(framework: FrameworkVersion) -> bool:
    return framework.status in _LIVE_STATUSES


def _relevant_changed_paths(changed_paths: list[str]) -> list[str]:
    return [path.strip() for path in changed_paths if path.strip() and "__tests__/" not in path]


def select_changed_frameworks(
    frameworks: list[FrameworkVersion],
    changed_paths: list[str],
) -> list[FrameworkVersion]:
    """Select the live framework versions affected by a set of changed paths.

    A change under `framework/versions/<id>/` affects only that version. A change to
    shared scoring inputs (scorers, engine, config, catalog, the workflow itself) or
    to a `framework/` file outside a known version directory affects every live
    version.
    """
    paths = _relevant_changed_paths(changed_paths)
    known_version_prefixes = tuple(f"framework/versions/{f.id}/" for f in frameworks)

    broad_change = any(
        path.startswith(BROAD_CHANGE_PREFIXES)
        or (path.startswith("framework/") and not path.startswith(known_version_prefixes))
        for path in paths
    )

    selected: list[FrameworkVersion] = []
    for framework in frameworks:
        if not _is_live(framework):
            continue
        version_prefix = f"framework/versions/{framework.id}/"
        if broad_change or any(path.startswith(version_prefix) for path in paths):
            selected.append(framework)
    return selected


def select_frameworks(
    frameworks: list[FrameworkVersion],
    *,
    cadence: str,
    framework_version: str | None = None,
    changed_paths: list[str] | None = None,
) -> list[FrameworkVersion]:
    """Select the framework versions in scope for a given cadence.

    Raises ValueError for an unknown cadence, a missing/archived manual
    selection, or a framework-version argument supplied for a non-manual cadence.
    """
    if cadence not in CADENCES:
        raise ValueError(f"Unknown cadence: {cadence!r}. Expected one of {CADENCES}.")

    if cadence == "manual":
        if not framework_version:
            raise ValueError("--framework-version is required for manual cadence")
        requested = get_framework(frameworks, framework_version)
        if requested.status == FrameworkStatus.ARCHIVED:
            raise ValueError(
                f"Framework version {requested.id} is archived and cannot be scheduled for scoring."
            )
        selected = [requested]
        if changed_paths is not None:
            selected_ids = {requested.id}
            for changed in select_changed_frameworks(frameworks, changed_paths):
                if changed.id not in selected_ids:
                    selected.append(changed)
        return sorted(selected, key=lambda framework: framework.sequence)

    if framework_version:
        raise ValueError(f"--framework-version is not supported for {cadence} cadence")

    if cadence == "changed":
        if changed_paths is None:
            raise ValueError("--changed-paths-file is required for changed cadence")
        return select_changed_frameworks(frameworks, changed_paths)

    status = _CADENCE_STATUS[cadence]
    return [framework for framework in frameworks if framework.status == status]


def missing_live_versions(
    frameworks: list[FrameworkVersion],
    published_dir: Path,
) -> list[FrameworkVersion]:
    """Return live framework versions with no published portfolio under published_dir.

    `published_dir` is a checkout of the deployed site, so a version's portfolio lives
    at `<published_dir>/versions/<id>/portfolio.json`. A missing directory (nothing
    published yet) means every live version is missing.
    """
    published_dir = Path(published_dir)
    return [
        framework
        for framework in frameworks
        if _is_live(framework)
        and not (published_dir / "versions" / framework.id / "portfolio.json").is_file()
    ]


def _published_contract_digest(published_dir: Path, version_id: str) -> str | None:
    """Read the scoring-contract digest recorded in a published portfolio.

    Returns None when the portfolio is absent, unreadable, not an object, or does not
    record a digest — all of which mean the published artifact cannot be shown to
    match the current contract and must be recomputed.
    """
    path = Path(published_dir) / "versions" / version_id / "portfolio.json"
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    digest = payload.get("contract_digest")
    return digest if isinstance(digest, str) and digest else None


def stale_live_versions(
    frameworks: list[FrameworkVersion],
    published_dir: Path,
) -> list[FrameworkVersion]:
    """Return live versions whose published portfolio is missing or built from another contract.

    A portfolio that exists but records a different `contract_digest` was produced by
    a superseded scoring contract, so serving it alongside the current contract would
    misrepresent the framework version. Such versions are recomputed like missing ones.

    Archived versions are never returned: their measurements are frozen and their
    scorers must never run again.
    """
    published_dir = Path(published_dir)
    return [
        framework
        for framework in frameworks
        if _is_live(framework)
        and _published_contract_digest(published_dir, framework.id) != contract_digest(framework)
    ]


def bootstrap_selection(
    frameworks: list[FrameworkVersion],
    selected: list[FrameworkVersion],
    published_dir: Path | None,
) -> list[FrameworkVersion]:
    """Union the cadence selection with live versions the published site cannot serve.

    Without this, a run that only recomputes some versions would leave the version
    index generator with no portfolio for a live version it must describe, failing
    late in the publish job instead of simply scoring the missing version. The same
    applies to a published portfolio whose contract digest is stale: the index
    generator rejects it, so the version is recomputed instead.
    """
    if published_dir is None:
        return sorted(selected, key=lambda framework: framework.sequence)

    selected_ids = {framework.id for framework in selected}
    combined = list(selected)
    for framework in stale_live_versions(frameworks, published_dir):
        if framework.id not in selected_ids:
            combined.append(framework)
    return sorted(combined, key=lambda framework: framework.sequence)


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
    """Build {"framework_version", "product"} rows for the selected versions.

    Dimensions are deliberately *not* part of the matrix: each job discovers and runs
    every dimension declared by its framework version. Products whose
    introduced_in/retired_in boundaries exclude a selected framework version are
    skipped for that version.
    """
    products = _load_products(products_dir)
    rows: list[dict[str, str]] = []
    for framework in selected:
        for product in products:
            if not is_in_version(product, frameworks, framework):
                continue
            rows.append({"framework_version": framework.id, "product": product["id"]})
    return rows


def _read_changed_paths(path: str | None) -> list[str] | None:
    if path is None:
        return None
    changed_file = Path(path)
    if not changed_file.exists():
        return []
    return changed_file.read_text().splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the framework/product matrix for a workflow run."
    )
    parser.add_argument("--framework-root", default="framework/versions")
    parser.add_argument("--products-dir", default="products")
    parser.add_argument("--cadence", choices=CADENCES)
    parser.add_argument(
        "--schedule",
        default=None,
        help="Cron literal from github.event.schedule; resolved to a cadence.",
    )
    parser.add_argument(
        "--framework-version",
        default=None,
        help="Required for --cadence manual; must be an active or upcoming version.",
    )
    parser.add_argument(
        "--changed-paths-file",
        default=None,
        help="Required for --cadence changed; file of changed paths, one per line.",
    )
    parser.add_argument(
        "--published-dir",
        default=None,
        help=(
            "Checkout of the currently published site. Live framework versions whose "
            "portfolio there is missing or built from a different contract digest are "
            "added to the matrix so the version index can be rebuilt."
        ),
    )
    args = parser.parse_args(argv)

    if bool(args.cadence) == bool(args.schedule):
        parser.error("exactly one of --cadence or --schedule is required")

    try:
        cadence = args.cadence or cadence_for_schedule(args.schedule)
        frameworks = discover_frameworks(Path(args.framework_root))
        selected = select_frameworks(
            frameworks,
            cadence=cadence,
            framework_version=args.framework_version,
            changed_paths=_read_changed_paths(args.changed_paths_file),
        )
        selected = bootstrap_selection(
            frameworks,
            selected,
            Path(args.published_dir) if args.published_dir else None,
        )
        rows = build_matrix_rows(frameworks, selected, Path(args.products_dir))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps({"include": rows}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
