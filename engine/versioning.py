from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.framework import FrameworkVersion


@dataclass(frozen=True)
class VersionBoundary:
    introduced_in: FrameworkVersion
    retired_in: FrameworkVersion | None = None


def _version_index(versions: list[FrameworkVersion]) -> dict[str, FrameworkVersion]:
    return {version.id: version for version in versions}


def _resolve_boundary(
    data: dict[str, Any],
    versions: list[FrameworkVersion],
) -> VersionBoundary:
    version_index = _version_index(versions)

    introduced_id = data.get("introduced_in")
    if not introduced_id:
        raise ValueError("Missing required version boundary: introduced_in")
    if introduced_id not in version_index:
        raise ValueError(f"Unknown framework version boundary: {introduced_id}")

    retired_id = data.get("retired_in")
    if retired_id is not None and retired_id not in version_index:
        raise ValueError(f"Unknown framework version boundary: {retired_id}")

    introduced_in = version_index[introduced_id]
    retired_in = version_index.get(retired_id) if retired_id is not None else None
    if retired_in is not None and retired_in.sequence <= introduced_in.sequence:
        raise ValueError(
            "Invalid version range: introduced_in must be before retired_in "
            f"({introduced_id} -> {retired_id})"
        )

    return VersionBoundary(introduced_in=introduced_in, retired_in=retired_in)


def is_in_version(
    data: dict[str, Any],
    versions: list[FrameworkVersion],
    selected: FrameworkVersion,
) -> bool:
    boundary = _resolve_boundary(data, versions)
    if selected.sequence < boundary.introduced_in.sequence:
        return False
    if boundary.retired_in is not None and selected.sequence >= boundary.retired_in.sequence:
        return False
    return True


def resolve_target(
    data: dict[str, Any],
    versions: list[FrameworkVersion],
    selected: FrameworkVersion,
) -> str:
    boundary = _resolve_boundary(data, versions)
    raw_targets = data.get("targets")
    if not isinstance(raw_targets, dict) or not raw_targets:
        product_id = data.get("id", "<unnamed product>")
        raise ValueError(f"Missing required targets mapping for {product_id}")

    version_index = _version_index(versions)
    if boundary.introduced_in.id not in raw_targets:
        raise ValueError(
            f"Missing target declaration at introduced_in boundary {boundary.introduced_in.id}"
        )

    latest_target: tuple[int, str] | None = None
    for version_id, target in raw_targets.items():
        version = version_index.get(version_id)
        if version is None:
            raise ValueError(f"Unknown framework version in targets: {version_id}")
        if version.sequence > selected.sequence:
            continue
        if latest_target is None or version.sequence > latest_target[0]:
            latest_target = (version.sequence, target)

    if latest_target is None:
        raise ValueError(
            f"No target declaration is available on or before selected framework {selected.id}"
        )

    return latest_target[1]
