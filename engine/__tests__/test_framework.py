import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

from engine.framework import FrameworkStatus, contract_digest, discover_frameworks, get_framework

REPO_ROOT = Path(__file__).parent.parent.parent


def _minimal_dimensions(
    *,
    dimensions: dict | None = None,
) -> dict:
    if dimensions is not None:
        return {"dimensions": dimensions}

    return {
        "dimensions": {
            "test_verification": {
                "label": "Test verification",
                "description": "Automated test health.",
                "scorer": "scorers/test_verification/scorer.py",
                "applies_to": {"product_types": ["charm"]},
                "aggregation": "worst_in_scope",
                "outputs": {
                    "latest_build_passing": {
                        "implementation": "latest-build-passing/v1",
                        "type": "boolean",
                        "label": "Latest build passing",
                        "description": "Latest CI summary has no failures.",
                    }
                },
                "medals": {"bronze": ["latest_build_passing == true"]},
            }
        }
    }


def _write_framework_version(
    root: Path,
    *,
    version_id: str,
    sequence: int,
    status: str,
    dimensions: dict | None = None,
    label: str | None = None,
    description: str | None = None,
) -> None:
    version_dir = root / version_id
    version_dir.mkdir(parents=True)

    (version_dir / "framework.yaml").write_text(
        yaml.safe_dump(
            {
                "id": version_id,
                "sequence": sequence,
                "label": label or f"PQF {version_id.upper()}",
                "status": status,
                "description": description or f"{version_id} contract",
            },
            sort_keys=False,
        )
    )
    (version_dir / "dimensions.yaml").write_text(
        yaml.safe_dump(_minimal_dimensions(dimensions=dimensions), sort_keys=False)
    )


def test_discover_frameworks_sorts_by_sequence_and_resolves_versions(tmp_path):
    _write_framework_version(tmp_path, version_id="v1", sequence=1, status="upcoming")
    _write_framework_version(tmp_path, version_id="v0", sequence=0, status="active")

    frameworks = discover_frameworks(tmp_path)

    assert [(f.id, f.status) for f in frameworks] == [
        ("v0", FrameworkStatus.ACTIVE),
        ("v1", FrameworkStatus.UPCOMING),
    ]
    assert get_framework(frameworks, "v1").sequence == 1


def test_discover_frameworks_rejects_multiple_active_versions(tmp_path):
    _write_framework_version(tmp_path, version_id="v0", sequence=0, status="active")
    _write_framework_version(tmp_path, version_id="v1", sequence=1, status="active")

    with pytest.raises(ValueError, match="v0.*v1|v1.*v0"):
        discover_frameworks(tmp_path)


def test_discover_frameworks_rejects_multiple_upcoming_versions(tmp_path):
    _write_framework_version(tmp_path, version_id="v0", sequence=0, status="active")
    _write_framework_version(tmp_path, version_id="v1", sequence=1, status="upcoming")
    _write_framework_version(tmp_path, version_id="v2", sequence=2, status="upcoming")

    with pytest.raises(ValueError, match="v1.*v2|v2.*v1"):
        discover_frameworks(tmp_path)


def test_discover_frameworks_rejects_duplicate_sequences(tmp_path):
    _write_framework_version(tmp_path, version_id="v0", sequence=0, status="active")
    _write_framework_version(tmp_path, version_id="v1", sequence=0, status="upcoming")

    with pytest.raises(ValueError, match="v0.*v1|v1.*v0"):
        discover_frameworks(tmp_path)


def test_discover_frameworks_rejects_archived_version_after_active(tmp_path):
    _write_framework_version(tmp_path, version_id="v0", sequence=0, status="active")
    _write_framework_version(tmp_path, version_id="v1", sequence=1, status="archived")

    with pytest.raises(ValueError, match="v0.*v1|v1.*v0"):
        discover_frameworks(tmp_path)


def test_get_framework_rejects_unknown_version(tmp_path):
    _write_framework_version(tmp_path, version_id="v0", sequence=0, status="active")
    frameworks = discover_frameworks(tmp_path)

    with pytest.raises(ValueError, match="v9"):
        get_framework(frameworks, "v9")


def test_contract_digest_is_stable_for_equivalent_contracts(tmp_path):
    dims_one = {
        "documentation": {
            "label": "Documentation",
            "description": "Docs baseline.",
            "scorer": "scorers/documentation/scorer.py",
            "applies_to": {"product_types": ["charm", "snap"]},
            "aggregation": "worst_in_scope",
            "outputs": {
                "readme_present": {
                    "implementation": "readme-present/v1",
                    "type": "boolean",
                    "label": "README present",
                    "description": "README.md exists.",
                }
            },
            "medals": {"bronze": ["readme_present == true"]},
        },
        "test_verification": {
            "label": "Test verification",
            "description": "Automated test health.",
            "scorer": "scorers/test_verification/scorer.py",
            "applies_to": {"product_types": ["charm"]},
            "aggregation": "worst_in_scope",
            "outputs": {
                "latest_build_passing": {
                    "implementation": "latest-build-passing/v1",
                    "type": "boolean",
                    "label": "Latest build passing",
                    "description": "Latest CI summary has no failures.",
                }
            },
            "medals": {"bronze": ["latest_build_passing == true"]},
        },
    }
    dims_two = {
        "test_verification": dims_one["test_verification"],
        "documentation": dims_one["documentation"],
    }

    _write_framework_version(
        tmp_path / "first",
        version_id="v0",
        sequence=0,
        status="active",
        dimensions=dims_one,
    )
    _write_framework_version(
        tmp_path / "second",
        version_id="v0",
        sequence=0,
        status="active",
        dimensions=dims_two,
    )

    digest_one = contract_digest(discover_frameworks(tmp_path / "first")[0])
    digest_two = contract_digest(discover_frameworks(tmp_path / "second")[0])

    assert digest_one == digest_two
    assert len(digest_one) == 64


def _digest_for(root: Path, *, target: str, versions: list[dict]) -> str:
    """Digest of `target` in a catalog built from `versions` (a valid lifecycle set)."""
    for version in versions:
        _write_framework_version(root, **version)
    return contract_digest(get_framework(discover_frameworks(root), target))


def test_contract_digest_survives_activation_to_archived(tmp_path):
    """Archiving a version freezes its measurements; it must not restate the contract."""
    before = _digest_for(
        tmp_path / "before",
        target="v0",
        versions=[
            {"version_id": "v0", "sequence": 0, "status": "active"},
            {"version_id": "v1", "sequence": 1, "status": "upcoming"},
        ],
    )
    after = _digest_for(
        tmp_path / "after",
        target="v0",
        versions=[
            {"version_id": "v0", "sequence": 0, "status": "archived"},
            {"version_id": "v1", "sequence": 1, "status": "active"},
        ],
    )

    assert before == after


def test_contract_digest_ignores_upcoming_to_active_activation(tmp_path):
    before = _digest_for(
        tmp_path / "before",
        target="v1",
        versions=[
            {"version_id": "v0", "sequence": 0, "status": "active"},
            {"version_id": "v1", "sequence": 1, "status": "upcoming"},
        ],
    )
    after = _digest_for(
        tmp_path / "after",
        target="v1",
        versions=[
            {"version_id": "v0", "sequence": 0, "status": "archived"},
            {"version_id": "v1", "sequence": 1, "status": "active"},
        ],
    )

    assert before == after


def test_contract_digest_ignores_label_and_description_edits(tmp_path):
    original = _digest_for(
        tmp_path / "original",
        target="v0",
        versions=[
            {
                "version_id": "v0",
                "sequence": 0,
                "status": "active",
                "label": "PQF V0",
                "description": "First contract",
            }
        ],
    )
    relabelled = _digest_for(
        tmp_path / "relabelled",
        target="v0",
        versions=[
            {
                "version_id": "v0",
                "sequence": 0,
                "status": "active",
                "label": "PQF V0 (2026 edition)",
                "description": "First contract, clarified wording.",
            }
        ],
    )

    assert original == relabelled


def test_contract_digest_ignores_dimension_and_output_display_metadata(tmp_path):
    baseline_dimensions = _minimal_dimensions()
    relabelled_dimensions = _minimal_dimensions()
    dimension = relabelled_dimensions["dimensions"]["test_verification"]
    dimension["label"] = "CI verification"
    dimension["description"] = "Clarified dimension copy."
    output = dimension["outputs"]["latest_build_passing"]
    output["label"] = "Main branch passing"
    output["description"] = "Clarified metric copy."
    output["range"] = "boolean"
    output["ai_assisted"] = False

    baseline = _digest_for(
        tmp_path / "baseline",
        target="v0",
        versions=[
            {
                "version_id": "v0",
                "sequence": 0,
                "status": "active",
                "dimensions": baseline_dimensions["dimensions"],
            }
        ],
    )
    relabelled = _digest_for(
        tmp_path / "relabelled",
        target="v0",
        versions=[
            {
                "version_id": "v0",
                "sequence": 0,
                "status": "active",
                "dimensions": relabelled_dimensions["dimensions"],
            }
        ],
    )

    assert baseline == relabelled


def test_contract_digest_changes_when_medal_criteria_change(tmp_path):
    stricter = _minimal_dimensions()
    stricter["dimensions"]["test_verification"]["medals"] = {
        "bronze": ["latest_build_passing == true"],
        "silver": ["latest_build_passing == true"],
    }

    baseline = _digest_for(
        tmp_path / "baseline",
        target="v0",
        versions=[{"version_id": "v0", "sequence": 0, "status": "active"}],
    )
    changed = _digest_for(
        tmp_path / "changed",
        target="v0",
        versions=[
            {
                "version_id": "v0",
                "sequence": 0,
                "status": "active",
                "dimensions": stricter["dimensions"],
            }
        ],
    )

    assert baseline != changed


def test_contract_digest_changes_when_metric_implementation_changes(tmp_path):
    revised = _minimal_dimensions()
    revised["dimensions"]["test_verification"]["outputs"]["latest_build_passing"][
        "implementation"
    ] = "latest-build-passing/v2"

    baseline = _digest_for(
        tmp_path / "baseline",
        target="v0",
        versions=[{"version_id": "v0", "sequence": 0, "status": "active"}],
    )
    changed = _digest_for(
        tmp_path / "changed",
        target="v0",
        versions=[
            {
                "version_id": "v0",
                "sequence": 0,
                "status": "active",
                "dimensions": revised["dimensions"],
            }
        ],
    )

    assert baseline != changed


def test_framework_cli_lists_selected_dimension_ids(tmp_path):
    _write_framework_version(
        tmp_path,
        version_id="v0",
        sequence=0,
        status="active",
        dimensions={
            "documentation": {
                "label": "Documentation",
                "description": "Docs baseline.",
                "scorer": "scorers/documentation/scorer.py",
                "applies_to": {"product_types": ["snap"]},
                "aggregation": "worst_in_scope",
                "outputs": {
                    "readme_present": {
                        "implementation": "readme-present/v1",
                        "type": "boolean",
                        "label": "README present",
                        "description": "README.md exists.",
                    }
                },
                "medals": {"bronze": ["readme_present == true"]},
            },
            "test_verification": {
                "label": "Test verification",
                "description": "Automated test health.",
                "scorer": "scorers/test_verification/scorer.py",
                "applies_to": {"product_types": ["charm"]},
                "aggregation": "worst_in_scope",
                "outputs": {
                    "latest_build_passing": {
                        "implementation": "latest-build-passing/v1",
                        "type": "boolean",
                        "label": "Latest build passing",
                        "description": "Latest CI summary has no failures.",
                    }
                },
                "medals": {"bronze": ["latest_build_passing == true"]},
            },
        },
    )
    _write_framework_version(tmp_path, version_id="v1", sequence=1, status="upcoming")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.framework",
            "--root",
            str(tmp_path),
            "--version",
            "v0",
            "--list-dimensions",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "documentation test_verification"


def test_repo_framework_snapshots_match_expected_lifecycle_and_shape():
    frameworks_dir = REPO_ROOT / "framework" / "versions"
    framework_schema = json.loads(
        (REPO_ROOT / "config" / "schemas" / "framework.schema.json").read_text()
    )
    dimensions_schema = json.loads(
        (REPO_ROOT / "config" / "schemas" / "dimensions.schema.json").read_text()
    )

    frameworks = discover_frameworks(frameworks_dir)

    assert [(f.id, f.status) for f in frameworks] == [
        ("v0", FrameworkStatus.ACTIVE),
        ("v1", FrameworkStatus.UPCOMING),
    ]
    assert "substrate_compat" not in get_framework(frameworks, "v0").dimensions["dimensions"]
    assert "substrate_compat" in get_framework(frameworks, "v1").dimensions["dimensions"]

    for framework in frameworks:
        metadata = yaml.safe_load((framework.directory / "framework.yaml").read_text())
        dimensions = yaml.safe_load((framework.directory / "dimensions.yaml").read_text())
        assert jsonschema.Draft7Validator(framework_schema).is_valid(metadata)
        assert jsonschema.Draft7Validator(dimensions_schema).is_valid(dimensions)
