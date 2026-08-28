# engine/__tests__/test_integration.py
"""
End-to-end test: run the CLI against sample product YAML and a fixture computed
JSON. Uses a temp file for computed data so the test is independent of whatever
CI may have committed to computed/matrix.json.

Fixture metric values and expected medals:
  test_verification: silver  (coverage 87 >= 80, stability 94 >= 85, integration evidence present)
  documentation:     bronze  (baseline docs presence passes; diataxis 3 < 4 → not silver)
  substrate_compat:  silver  (
      supports_juju_3=true and substrate test evidence present; juju_4 false
  )
  security_ssdlc:    silver  (automation + protection + renovate + sast true; cve tracking false)
  engagement:        silver (triage 3 <= 3; pr_review 4 <= 5; coverage >= 80; ownership true)

Overall current_medal: bronze (documentation pulls it down)
Target: gold (restored from the existing PQF product definition)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent.parent

_FIXTURE_COMPUTED = {
    "product_id": "matrix",
    "computed_at": "2026-06-29T20:00:00+00:00",
    "metrics": {
        "test_verification": {
            "coverage_pct": 87,
            "stability_pct": 94,
            "latest_build_passing": True,
            "integration_test_evidence_present": True,
            "uses_ops_testing": True,
            "uses_jubilant": False,
        },
        "documentation": {
            "readme_present": True,
            "contributing_present": True,
            "has_security": True,
            "documentation_workflows_passing": True,
            "diataxis_coverage_ai": 3,
            "uses_rtd_hosting": False,
            "release_notes_process_implemented": True,
        },
        "substrate_compat": {
            "supports_juju_3": True,
            "supports_juju_4": False,
            "substrate_test_evidence_present": True,
            "uses_canonical_k8s": False,
        },
        "security_ssdlc": {
            "renovate_enabled": True,
            "canonical_repo_automation_registered": True,
            "branch_protection_required_checks": True,
            "signed_commits_required": True,
            "sast_workflow_present": True,
            "cve_tracking_process_present": False,
        },
        "engagement": {
            "avg_triage_days": 3.0,
            "avg_pr_review_days": 4.0,
            "response_coverage_rate": 85,
            "ownership_signal": True,
            "has_jira_sync": False,
        },
    },
}


def test_cli_computes_expected_medals_for_matrix():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(_FIXTURE_COMPUTED, tmp)
        tmp_path = tmp.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as drift_tmp:
        json.dump({}, drift_tmp)
        drift_path = drift_tmp.name

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "engine",
            "--product",
            str(REPO_ROOT / "products/matrix.yaml"),
            "--computed",
            tmp_path,
            "--dimensions",
            str(REPO_ROOT / "config/dimensions.yaml"),
            "--drift-history",
            drift_path,
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed:\n{result.stderr}"

    output = json.loads(result.stdout)

    assert output["id"] == "matrix"
    assert output["current_medal"] == "silver"
    assert output["target_medal"] == "gold"

    dims = output["dimensions"]
    assert dims["engagement"]["medal"] == "silver"

    # No drift history entries yet → drift is null for all
    for dim in dims.values():
        assert dim["drift"] is None


def test_dimensions_config_declares_required_metrics_for_scoring_for_each_dimension():
    dimensions = yaml.safe_load((REPO_ROOT / "config/dimensions.yaml").read_text())

    assert dimensions["dimensions"]["test_verification"]["required_metrics_for_scoring"] == [
        "latest_build_passing"
    ]
    assert dimensions["dimensions"]["documentation"]["required_metrics_for_scoring"] == [
        "readme_present",
        "contributing_present",
        "has_security",
    ]
    assert dimensions["dimensions"]["substrate_compat"]["required_metrics_for_scoring"] == [
        "supports_juju_3",
        "substrate_test_evidence_present",
    ]
    assert dimensions["dimensions"]["security_ssdlc"]["required_metrics_for_scoring"] == [
        "branch_protection_required_checks",
        "renovate_enabled",
    ]
    assert dimensions["dimensions"]["engagement"]["required_metrics_for_scoring"] == [
        "avg_triage_days",
        "avg_pr_review_days",
        "response_coverage_rate",
    ]
    assert (
        dimensions["dimensions"]["documentation"]["outputs"]["diataxis_coverage_ai"]["ai_assisted"]
        is True
    )


def test_required_metrics_for_scoring_are_declared_outputs():
    dimensions = yaml.safe_load((REPO_ROOT / "config/dimensions.yaml").read_text())["dimensions"]

    for dim_name, dim_cfg in dimensions.items():
        outputs = set(dim_cfg.get("outputs", {}).keys())
        required = dim_cfg.get("required_metrics_for_scoring", [])
        assert set(required).issubset(outputs), (
            f"{dim_name} has required_metrics_for_scoring not present in outputs: "
            f"{sorted(set(required) - outputs)}"
        )
