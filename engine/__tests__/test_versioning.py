from pathlib import Path

import pytest

from engine.framework import FrameworkStatus, FrameworkVersion
from engine.versioning import is_in_version, resolve_target


def _framework(version_id: str, sequence: int, status: FrameworkStatus) -> FrameworkVersion:
    return FrameworkVersion(
        id=version_id,
        sequence=sequence,
        label=f"PQF {version_id.upper()}",
        status=status,
        description=f"{version_id} contract",
        directory=Path("."),
        dimensions={"dimensions": {}},
    )


FRAMEWORKS = [
    _framework("v0", 0, FrameworkStatus.ARCHIVED),
    _framework("v1", 1, FrameworkStatus.ACTIVE),
    _framework("v2", 2, FrameworkStatus.UPCOMING),
]
FRAMEWORK_BY_ID = {framework.id: framework for framework in FRAMEWORKS}


def test_is_in_version_uses_start_inclusive_end_exclusive_boundaries():
    assert is_in_version({"introduced_in": "v1"}, FRAMEWORKS, FRAMEWORK_BY_ID["v1"])
    assert not is_in_version({"introduced_in": "v1"}, FRAMEWORKS, FRAMEWORK_BY_ID["v0"])
    assert not is_in_version(
        {"introduced_in": "v0", "retired_in": "v1"},
        FRAMEWORKS,
        FRAMEWORK_BY_ID["v1"],
    )


def test_is_in_version_rejects_unknown_boundaries():
    with pytest.raises(ValueError, match="v9"):
        is_in_version({"introduced_in": "v9"}, FRAMEWORKS, FRAMEWORK_BY_ID["v1"])


def test_is_in_version_rejects_invalid_ranges():
    with pytest.raises(ValueError, match="introduced_in.*retired_in"):
        is_in_version(
            {"introduced_in": "v1", "retired_in": "v1"},
            FRAMEWORKS,
            FRAMEWORK_BY_ID["v1"],
        )


def test_resolve_target_returns_latest_declared_target_not_after_selected_version():
    data = {
        "introduced_in": "v0",
        "targets": {
            "v0": "bronze",
            "v1": "silver",
        },
    }

    assert resolve_target(data, FRAMEWORKS, FRAMEWORK_BY_ID["v1"]) == "silver"
    assert resolve_target(data, FRAMEWORKS, FRAMEWORK_BY_ID["v2"]) == "silver"


def test_resolve_target_rejects_missing_target_at_introduction():
    with pytest.raises(ValueError, match="introduced_in"):
        resolve_target(
            {
                "introduced_in": "v0",
                "targets": {"v1": "silver"},
            },
            FRAMEWORKS,
            FRAMEWORK_BY_ID["v1"],
        )


def test_resolve_target_rejects_unknown_target_version():
    with pytest.raises(ValueError, match="v9"):
        resolve_target(
            {
                "introduced_in": "v0",
                "targets": {"v0": "bronze", "v9": "gold"},
            },
            FRAMEWORKS,
            FRAMEWORK_BY_ID["v1"],
        )
