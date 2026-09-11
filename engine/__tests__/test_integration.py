# engine/__tests__/test_integration.py
"""Integration coverage for the live repo dimensions contract."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent.parent


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
