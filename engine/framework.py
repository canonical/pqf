"""Discover and inspect versioned PQF framework contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml


class FrameworkStatus(StrEnum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class FrameworkVersion:
    id: str
    sequence: int
    label: str
    status: FrameworkStatus
    description: str
    directory: Path
    dimensions: dict[str, Any]


_STATUS_ORDER = {
    FrameworkStatus.ARCHIVED: 0,
    FrameworkStatus.ACTIVE: 1,
    FrameworkStatus.UPCOMING: 2,
}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def _duplicate_members(values: list[tuple[str, str | int]]) -> list[str]:
    grouped: dict[str | int, list[str]] = {}
    for framework_id, value in values:
        grouped.setdefault(value, []).append(framework_id)

    duplicates: list[str] = []
    for ids in grouped.values():
        if len(ids) > 1:
            duplicates.extend(sorted(ids))
    return duplicates


def _validate_frameworks(frameworks: list[FrameworkVersion]) -> None:
    errors: list[str] = []

    active_ids = sorted(
        framework.id for framework in frameworks if framework.status == FrameworkStatus.ACTIVE
    )
    if len(active_ids) != 1:
        errors.append(
            "expected exactly one active framework"
            + (f": {', '.join(active_ids)}" if active_ids else "")
        )

    upcoming_ids = sorted(
        framework.id for framework in frameworks if framework.status == FrameworkStatus.UPCOMING
    )
    if len(upcoming_ids) > 1:
        errors.append(f"expected at most one upcoming framework: {', '.join(upcoming_ids)}")

    duplicate_ids = _duplicate_members([(framework.id, framework.id) for framework in frameworks])
    if duplicate_ids:
        errors.append(f"duplicate framework ids: {', '.join(duplicate_ids)}")

    duplicate_sequences = _duplicate_members(
        [(framework.id, framework.sequence) for framework in frameworks]
    )
    if duplicate_sequences:
        errors.append(f"duplicate framework sequences: {', '.join(duplicate_sequences)}")

    ordered = sorted(frameworks, key=lambda framework: framework.sequence)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if _STATUS_ORDER[current.status] < _STATUS_ORDER[previous.status]:
            errors.append(
                "framework lifecycle order conflicts with sequence order: "
                f"{previous.id}, {current.id}"
            )

    if errors:
        raise ValueError("; ".join(errors))


def discover_frameworks(root: Path) -> list[FrameworkVersion]:
    frameworks: list[FrameworkVersion] = []
    for metadata_path in sorted(root.glob("*/framework.yaml")):
        directory = metadata_path.parent
        metadata = _load_yaml(metadata_path)
        dimensions = _load_yaml(directory / "dimensions.yaml")

        frameworks.append(
            FrameworkVersion(
                id=metadata["id"],
                sequence=metadata["sequence"],
                label=metadata["label"],
                status=FrameworkStatus(metadata["status"]),
                description=metadata["description"],
                directory=directory,
                dimensions=dimensions,
            )
        )

    frameworks.sort(key=lambda framework: framework.sequence)
    _validate_frameworks(frameworks)
    return frameworks


def get_framework(frameworks: list[FrameworkVersion], version_id: str) -> FrameworkVersion:
    for framework in frameworks:
        if framework.id == version_id:
            return framework

    available = ", ".join(framework.id for framework in frameworks)
    raise ValueError(f"Unknown framework version: {version_id}. Available versions: {available}")


def contract_digest(framework: FrameworkVersion) -> str:
    payload = {
        "id": framework.id,
        "sequence": framework.sequence,
        "label": framework.label,
        "status": framework.status.value,
        "description": framework.description,
        "dimensions": framework.dimensions,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover and inspect PQF framework contracts.")
    parser.add_argument(
        "--root",
        default="framework/versions",
        metavar="DIR",
        help="Framework versions directory (default: framework/versions)",
    )
    parser.add_argument("--version", help="Framework version ID to inspect, e.g. v1")
    parser.add_argument(
        "--list-dimensions",
        action="store_true",
        help="Print selected dimension IDs separated by spaces.",
    )
    args = parser.parse_args()

    frameworks = discover_frameworks(Path(args.root))
    if args.list_dimensions:
        if not args.version:
            parser.error("--version is required with --list-dimensions")
        framework = get_framework(frameworks, args.version)
        print(" ".join(sorted(framework.dimensions["dimensions"].keys())))
        return 0

    parser.error("no action requested")
    return 2


if __name__ == "__main__":
    sys.exit(main())
