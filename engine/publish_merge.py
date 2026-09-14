"""Merge freshly computed versions with the latest published Pages snapshot."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_portfolio(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read portfolio {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Portfolio {path} must contain a JSON object")
    return payload


def _generated_at(payload: dict[str, Any], path: Path) -> datetime:
    value = payload.get("generated_at")
    if not isinstance(value, str):
        raise ValueError(f"Portfolio {path} is missing generated_at")
    try:
        generated_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Portfolio {path} has invalid generated_at: {value!r}") from exc
    if generated_at.tzinfo is None:
        raise ValueError(f"Portfolio {path} has timezone-naive generated_at")
    return generated_at.astimezone(UTC)


def _same_scoring_identity(
    candidate: dict[str, Any],
    latest: dict[str, Any],
) -> bool:
    candidate_framework = candidate.get("framework")
    latest_framework = latest.get("framework")
    return (
        isinstance(candidate_framework, dict)
        and isinstance(latest_framework, dict)
        and candidate_framework.get("id") == latest_framework.get("id")
        and candidate.get("source_revision") == latest.get("source_revision")
        and candidate.get("contract_digest") == latest.get("contract_digest")
    )


def _replace_directory(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def merge_latest_versions(
    public_dir: Path,
    latest_dir: Path,
    *,
    selected_versions: set[str],
) -> None:
    """Preserve concurrent publications without overriding this run's new inputs."""
    latest_versions = latest_dir / "versions"
    if not latest_versions.is_dir():
        return

    candidate_versions = public_dir / "versions"
    candidate_versions.mkdir(parents=True, exist_ok=True)

    for latest_version in sorted(path for path in latest_versions.iterdir() if path.is_dir()):
        destination = candidate_versions / latest_version.name
        if latest_version.name not in selected_versions:
            _replace_directory(latest_version, destination)
            continue

        candidate_path = destination / "portfolio.json"
        latest_path = latest_version / "portfolio.json"
        candidate = _load_portfolio(candidate_path)
        candidate_generated_at = _generated_at(candidate, candidate_path)
        try:
            latest = _load_portfolio(latest_path)
            latest_generated_at = _generated_at(latest, latest_path)
        except ValueError:
            continue
        if (
            _same_scoring_identity(candidate, latest)
            and latest_generated_at > candidate_generated_at
        ):
            _replace_directory(latest_version, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge latest Pages versions into a candidate public directory."
    )
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--latest-dir", type=Path, required=True)
    parser.add_argument("--selected-versions-json", required=True)
    args = parser.parse_args(argv)

    try:
        selected = json.loads(args.selected_versions_json)
        if not isinstance(selected, list) or not all(
            isinstance(version, str) for version in selected
        ):
            raise ValueError("selected versions must be a JSON array of strings")
        merge_latest_versions(
            args.public_dir,
            args.latest_dir,
            selected_versions=set(selected),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
