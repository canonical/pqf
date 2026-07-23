from typing import Any

import requests

from engine.models import EvaluationUnit

# Reuse shared helpers for GitHub interactions
from scorers.shared.github_signals import search_code_count, workflow_files


def _uses_ops_testing(repos: list[str], github_token: str | None) -> bool:
    """True if NO repo uses the deprecated Harness class."""
    for repo in repos:
        count = search_code_count(f"from ops.testing import Harness repo:{repo}", github_token)
        if count > 0:
            return False
    return True


def _uses_jubilant(repos: list[str], github_token: str | None) -> bool:
    """True if at least one repo imports jubilant in its integration tests."""
    for repo in repos:
        count = search_code_count(f"import jubilant repo:{repo}", github_token)
        if count > 0:
            return True
    return False


def _integration_test_evidence_present(owner_repo: str, github_token: str | None) -> bool:
    for _, content in workflow_files(owner_repo, github_token):
        lowered = content.lower()
        if "integration" in lowered and (
            "pytest -m integration" in lowered
            or "pytest tests/integration" in lowered
            or "jubilant" in lowered
            or "integration-tests" in lowered
        ):
            return True
    return False


def compute_metrics(unit: EvaluationUnit, github_token: str | None = None) -> dict[str, Any]:
    """
    Fetch test metrics from the evaluation unit's Allure report URL.
    Checks uses_ops_testing and uses_jubilant against unit.repo.
    Also detects integration test evidence from workflows and code search.
    """
    coverage_pct = 0
    stability_pct = 0
    latest_build_passing = False

    url = unit.allure_report_url.strip()
    if url:
        summary_url = url.rstrip("/") + "/widgets/summary.json"
        resp = requests.get(summary_url, timeout=30)
        resp.raise_for_status()
        stat = resp.json().get("statistic", {})
        total = stat.get("total", 0)
        if total > 0:
            passed = stat.get("passed", 0)
            failed = stat.get("failed", 0)
            broken = stat.get("broken", 0)
            coverage_pct = round(passed / total * 100)
            stability_pct = round((total - failed - broken) / total * 100)
            latest_build_passing = failed == 0 and broken == 0

    uses_ops = False
    uses_jub = False
    integration_evidence = False
    if github_token and unit.repo:
        uses_ops = _uses_ops_testing([unit.repo], github_token)
        uses_jub = _uses_jubilant([unit.repo], github_token)
        # Integration evidence combines workflow markers and code-search signals.
        integration_evidence = _integration_test_evidence_present(unit.repo, github_token)

    return {
        "coverage_pct": coverage_pct,
        "stability_pct": stability_pct,
        "latest_build_passing": latest_build_passing,
        "integration_test_evidence_present": integration_evidence,
        "uses_ops_testing": uses_ops,
        "uses_jubilant": uses_jub,
    }
