# engine/__tests__/test_integration.py
"""
End-to-end test: run the CLI against sample product YAML and a fixture computed
JSON. Uses a temp file for computed data so the test is independent of whatever
CI may have committed to computed/matrix.json.

Fixture metric values and expected medals:
  test_verification: silver  (coverage 87 >= 80, stability 94 >= 85; 87 < 90 → not gold)
  documentation:     bronze  (has all files + links_passing, but diataxis 3 < 4 → not silver)
  substrate_compat:  silver  (supports_juju_3=true; juju_4+ck8s false → not gold)
  security_ssdlc:    silver  (dependabot_enabled=true; codeql_enabled=false → not gold)
  support_engagement: silver (triage 3 <= 5; pr_review 6 <= 7; both > gold threshold)

Overall current_medal: bronze (documentation pulls it down)
Target: bronze (aligned with imported docs catalog)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

_FIXTURE_COMPUTED = {
    "product_id": "matrix",
    "computed_at": "2026-06-29T20:00:00+00:00",
    "metrics": {
        "test_verification": {
            "coverage_pct": 87,
            "stability_pct": 94,
            "latest_build_passing": True,
        },
        "documentation": {
            "has_readme": True,
            "has_contributing": True,
            "has_security": True,
            "diataxis_coverage": 3,
            "style_linter_passing": True,
            "links_passing": True,
        },
        "substrate_compat": {
            "supports_juju_3": True,
            "supports_juju_4": False,
            "supports_ck8s": False,
        },
        "security_ssdlc": {
            "dependabot_enabled": True,
            "codeql_enabled": False,
        },
        "support_engagement": {
            "avg_triage_days": 3.0,
            "avg_pr_review_days": 6.0,
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
    assert output["current_medal"] == "bronze"
    assert output["target_medal"] == "bronze"

    dims = output["dimensions"]
    assert dims["test_verification"]["medal"] == "silver"
    assert dims["documentation"]["medal"] == "bronze"
    assert dims["substrate_compat"]["medal"] == "silver"
    assert dims["security_ssdlc"]["medal"] == "silver"
    assert dims["support_engagement"]["medal"] == "silver"

    # No drift history entries yet → drift is null for all
    for dim in dims.values():
        assert dim["drift"] is None
