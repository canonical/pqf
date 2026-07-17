from typing import Any

import requests

from engine.models import EvaluationUnit

_GITHUB_API = "https://api.github.com"


def _make_github_session(github_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return session


def _search_code(query: str, github_token: str) -> int:
    """Return total_count from GitHub code search."""
    session = _make_github_session(github_token)
    resp = session.get(
        f"{_GITHUB_API}/search/code",
        params={"q": query, "per_page": 1},
        timeout=15,
    )
    if not resp.ok:
        return 0
    return resp.json().get("total_count", 0)


def _uses_ops_testing(repos: list[str], github_token: str) -> bool:
    """True if NO repo uses the deprecated Harness class."""
    for repo in repos:
        count = _search_code(f"from ops.testing import Harness repo:{repo}", github_token)
        if count > 0:
            return False
    return True


def _uses_jubilant(repos: list[str], github_token: str) -> bool:
    """True if at least one repo imports jubilant in its integration tests."""
    for repo in repos:
        count = _search_code(f"import jubilant repo:{repo}", github_token)
        if count > 0:
            return True
    return False


def compute_metrics(unit: EvaluationUnit, github_token: str | None = None) -> dict[str, Any]:
    """
    Fetch test metrics from the evaluation unit's Allure report URL.
    Checks uses_ops_testing and uses_jubilant against unit.repo.
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
    if github_token and unit.repo:
        uses_ops = _uses_ops_testing([unit.repo], github_token)
        uses_jub = _uses_jubilant([unit.repo], github_token)

    return {
        "coverage_pct": coverage_pct,
        "stability_pct": stability_pct,
        "latest_build_passing": latest_build_passing,
        "uses_ops_testing": uses_ops,
        "uses_jubilant": uses_jub,
    }
