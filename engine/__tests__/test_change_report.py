from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from engine.change_report import (
    _read_worktree_snapshot,
    classify_repository_changes,
    render_change_report,
)


def _base_snapshot() -> dict:
    return {
        "frameworks": {
            "v0": {
                "framework": {
                    "id": "v0",
                    "sequence": 0,
                    "label": "PQF V0",
                    "status": "active",
                    "description": "Base contract",
                },
                "dimensions": {
                    "dimensions": {
                        "test_verification": {
                            "label": "Test verification",
                            "description": "Automated test health.",
                            "scorer": "scorers/test_verification/scorer.py",
                            "applies_to": {"product_types": ["charm"]},
                            "aggregation": "worst_in_scope",
                            "required_metrics_for_scoring": ["latest_build_passing"],
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
                },
            }
        },
        "products": {
            "test-charm": {
                "id": "test-charm",
                "product_type": "charm",
                "name": "Test Charm",
                "lifecycle": "stable",
                "introduced_in": "v0",
                "targets": {"v0": "bronze"},
                "ownership": {"squad": "team-a"},
                "source": {"repo": "canonical/test-charm"},
            }
        },
    }


def _write_framework_metadata(
    version_dir: Path,
    *,
    version_id: str = "v0",
    status: str = "active",
) -> None:
    version_dir.mkdir(parents=True)
    (version_dir / "framework.yaml").write_text(
        yaml.safe_dump(
            {
                "id": version_id,
                "sequence": 0,
                "label": f"PQF {version_id.upper()}",
                "status": status,
                "description": "Base contract",
            },
            sort_keys=False,
        )
    )


def _write_dimensions_snapshot(version_dir: Path) -> None:
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "dimensions.yaml").write_text(
        yaml.safe_dump(
            {
                "dimensions": {
                    "test_verification": {
                        "label": "Test verification",
                        "description": "Automated test health.",
                        "scorer": "scorers/test_verification/scorer.py",
                        "applies_to": {"product_types": ["charm"]},
                        "aggregation": "worst_in_scope",
                        "required_metrics_for_scoring": ["latest_build_passing"],
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
            },
            sort_keys=False,
        )
    )


def test_classify_repository_changes_reports_framework_metadata_only_changes():
    base = _base_snapshot()
    head = deepcopy(base)
    head["frameworks"]["v0"]["framework"]["description"] = "Updated contract description"

    changes = classify_repository_changes(base, head)

    assert changes["metadata_only"] == ["framework v0 metadata changed: description"]
    assert changes["additive_informational"] == []
    assert changes["scoring_semantic"] == []
    assert changes["catalog_membership_or_target"] == []


def test_classify_repository_changes_reports_added_informational_metric():
    base = _base_snapshot()
    head = deepcopy(base)
    head["frameworks"]["v0"]["dimensions"]["dimensions"]["test_verification"]["outputs"][
        "coverage_pct"
    ] = {
        "implementation": "coverage-pct/v1",
        "type": "number",
        "range": "0-100",
        "label": "Coverage",
        "description": "Latest Allure coverage percentage.",
        "informational": True,
    }

    changes = classify_repository_changes(base, head)

    assert changes["metadata_only"] == []
    assert changes["additive_informational"] == [
        "framework v0 dimension test_verification added informational output coverage_pct"
    ]
    assert changes["scoring_semantic"] == []
    assert changes["catalog_membership_or_target"] == []


def test_classify_repository_changes_reports_metric_implementation_revision_changes():
    base = _base_snapshot()
    head = deepcopy(base)
    output = head["frameworks"]["v0"]["dimensions"]["dimensions"]["test_verification"]["outputs"][
        "latest_build_passing"
    ]
    output["implementation"] = "latest-build-passing/v2"

    changes = classify_repository_changes(base, head)

    assert changes["metadata_only"] == []
    assert changes["additive_informational"] == []
    assert changes["scoring_semantic"] == [
        "framework v0 dimension test_verification output "
        "latest_build_passing changed implementation"
    ]
    assert changes["catalog_membership_or_target"] == []


def test_classify_repository_changes_reports_rubric_changes():
    base = _base_snapshot()
    head = deepcopy(base)
    head["frameworks"]["v0"]["dimensions"]["dimensions"]["test_verification"]["medals"] = {
        "bronze": ["latest_build_passing == true"],
        "gold": ["latest_build_passing == true"],
    }

    changes = classify_repository_changes(base, head)

    assert changes["metadata_only"] == []
    assert changes["additive_informational"] == []
    assert changes["scoring_semantic"] == [
        "framework v0 dimension test_verification changed medal criteria"
    ]
    assert changes["catalog_membership_or_target"] == []


def test_classify_repository_changes_reports_target_changes():
    base = _base_snapshot()
    head = deepcopy(base)
    head["products"]["test-charm"]["targets"]["v0"] = "silver"

    changes = classify_repository_changes(base, head)

    assert changes["metadata_only"] == []
    assert changes["additive_informational"] == []
    assert changes["scoring_semantic"] == []
    assert changes["catalog_membership_or_target"] == ["product test-charm changed targets"]


def test_read_worktree_snapshot_rejects_missing_dimensions_snapshot(tmp_path, monkeypatch):
    framework_root = tmp_path / "framework" / "versions" / "v0"
    _write_framework_metadata(framework_root)
    (tmp_path / "products").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="framework/versions/v0/dimensions.yaml"):
        _read_worktree_snapshot()


def test_read_worktree_snapshot_rejects_orphan_dimensions_snapshot(tmp_path, monkeypatch):
    framework_root = tmp_path / "framework" / "versions" / "v0"
    _write_dimensions_snapshot(framework_root)
    (tmp_path / "products").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="framework/versions/v0/framework.yaml"):
        _read_worktree_snapshot()


def test_read_worktree_snapshot_wraps_yaml_parse_errors(tmp_path, monkeypatch):
    framework_root = tmp_path / "framework" / "versions" / "v0"
    _write_framework_metadata(framework_root)
    (framework_root / "dimensions.yaml").write_text("dimensions: [broken\n")
    (tmp_path / "products").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="framework/versions/v0/dimensions.yaml"):
        _read_worktree_snapshot()


def test_render_change_report_outputs_all_markdown_sections():
    report = render_change_report(
        {
            "metadata_only": ["framework v0 metadata changed: description"],
            "additive_informational": [
                "framework v0 dimension test_verification added informational output coverage_pct"
            ],
            "scoring_semantic": ["framework v0 dimension test_verification changed medal criteria"],
            "catalog_membership_or_target": ["product test-charm changed targets"],
        }
    )

    assert "## Metadata-only changes" in report
    assert "## Additive informational measurements" in report
    assert "## Scoring-semantic changes" in report
    assert "## Catalog membership or target changes" in report
    assert "- product test-charm changed targets" in report
