import requests
import responses

from engine.models import EvaluationUnit, ProductType
from scorers.support_engagement.logic import (
    _has_jira_sync,
    _has_squad_topic,
    compute_metrics,
)

_GITHUB_API = "https://api.github.com"

UNIT = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
)

UNIT_EMPTY = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="",
)

_ISSUES = [
    {
        "number": 1,
        "user": {"login": "reporter"},
        "created_at": "2026-06-01T00:00:00Z",
        "pull_request": None,  # not a PR
    },
    {
        "number": 2,
        "user": {"login": "reporter"},
        "created_at": "2026-06-01T00:00:00Z",
        "pull_request": None,
    },
]

_COMMENTS_ISSUE_1 = [
    {"user": {"login": "maintainer"}, "created_at": "2026-06-03T00:00:00Z"}
]  # 2 days to triage

_COMMENTS_ISSUE_2 = [
    {"user": {"login": "reporter"}, "created_at": "2026-06-01T12:00:00Z"},  # skip — same author
    {"user": {"login": "maintainer"}, "created_at": "2026-06-05T00:00:00Z"},  # 4 days
]

_PULLS = [
    {"number": 10, "created_at": "2026-06-01T00:00:00Z"},
]

_REVIEWS_PR_10 = [
    {"submitted_at": "2026-06-02T00:00:00Z", "state": "COMMENTED"},  # 1 day
]


def _mock_repo_metadata(
    owner_repo: str,
    topics: list[str] | None = None,
    jira_sync: bool = False,
):
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/{owner_repo}/topics",
        json={"names": topics or []},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/.jira_sync_config.yaml",
        json={} if jira_sync else {"message": "Not Found"},
        status=200 if jira_sync else 404,
    )


@responses.activate
def test_avg_triage_days_computed_correctly():
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=_ISSUES,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues/1/comments",
        json=_COMMENTS_ISSUE_1,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues/2/comments",
        json=_COMMENTS_ISSUE_2,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=_PULLS,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/10/reviews",
        json=_REVIEWS_PR_10,
        status=200,
    )
    _mock_repo_metadata(
        "canonical/synapse-operator",
        topics=["squad-americas", "product-matrix"],
        jira_sync=True,
    )
    result = compute_metrics(UNIT, "token")
    assert result["avg_triage_days"] == 3.0  # (2 + 4) / 2
    assert result["avg_pr_review_days"] == 1.0
    assert result["response_coverage_rate"] == 100.0
    assert result["ownership_signal"] is True
    assert result["has_jira_sync"] is True


@responses.activate
def test_returns_zero_when_no_issues():
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=[],
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=[],
        status=200,
        match_querystring=False,
    )
    _mock_repo_metadata("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["avg_triage_days"] == 0.0
    assert result["avg_pr_review_days"] == 0.0
    assert result["response_coverage_rate"] == 0.0
    assert result["ownership_signal"] is False
    assert result["has_jira_sync"] is False


@responses.activate
def test_skips_pr_issues_in_issue_list():
    """Issues that are actually PRs (have pull_request key) are excluded."""
    issues = [
        {
            "number": 5,
            "user": {"login": "a"},
            "created_at": "2026-06-01T00:00:00Z",
            "pull_request": {"url": "https://..."},
        }
    ]
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=issues,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=[],
        status=200,
        match_querystring=False,
    )
    _mock_repo_metadata("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["avg_triage_days"] == 0.0
    assert result["response_coverage_rate"] == 0.0
    assert result["ownership_signal"] is False
    assert result["has_jira_sync"] is False


@responses.activate
def test_zero_when_issue_has_no_comments():
    issues = [
        {
            "number": 3,
            "user": {"login": "reporter"},
            "created_at": "2026-06-01T00:00:00Z",
            "pull_request": None,
        }
    ]
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=issues,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues/3/comments",
        json=[],
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=[],
        status=200,
        match_querystring=False,
    )
    _mock_repo_metadata("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["avg_triage_days"] == 0.0
    assert result["response_coverage_rate"] == 0.0
    assert result["ownership_signal"] is False
    assert result["has_jira_sync"] is False


@responses.activate
def test_has_squad_topic_true():
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/test-repo/topics",
        json={"names": ["squad-americas", "product-matrix"]},
        status=200,
    )
    session = requests.Session()
    session.headers.update({"Authorization": "Bearer test"})
    result = _has_squad_topic("canonical/test-repo", session)
    assert result is True


@responses.activate
def test_has_jira_sync_true():
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/test-repo/contents/.github/.jira_sync_config.yaml",
        json={},
        status=200,
    )
    session = requests.Session()
    session.headers.update({"Authorization": "Bearer test"})
    result = _has_jira_sync("canonical/test-repo", session)
    assert result is True


def test_returns_zeros_when_no_repo():
    result = compute_metrics(UNIT_EMPTY, "token")
    assert result == {
        "avg_triage_days": 0.0,
        "avg_pr_review_days": 0.0,
        "response_coverage_rate": 0,
        "ownership_signal": False,
        "has_jira_sync": False,
    }


@responses.activate
def test_pr_review_zero_when_no_reviews():
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=[],
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=[{"number": 20, "created_at": "2026-06-01T00:00:00Z"}],
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/20/reviews",
        json=[],
        status=200,
    )
    _mock_repo_metadata("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["avg_pr_review_days"] == 0.0
    assert result["response_coverage_rate"] == 0.0
    assert result["ownership_signal"] is False
    assert result["has_jira_sync"] is False


@responses.activate
def test_single_repo_triage_days():
    """Single unit repo contributes to triage average."""
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=[
            {
                "number": 1,
                "user": {"login": "a"},
                "created_at": "2026-06-01T00:00:00Z",
                "pull_request": None,
            }
        ],
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues/1/comments",
        json=[{"user": {"login": "b"}, "created_at": "2026-06-03T00:00:00Z"}],
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=[],
        status=200,
        match_querystring=False,
    )
    _mock_repo_metadata("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["avg_triage_days"] == 2.0
    assert result["response_coverage_rate"] == 100.0
    assert result["ownership_signal"] is False
    assert result["has_jira_sync"] is False


@responses.activate
def test_excludes_prs_outside_90day_window():
    """PRs created more than 90 days ago are excluded from the metric."""
    # One old PR (created ~180 days ago), one recent PR (created recently)
    pulls = [
        {"number": 1, "created_at": "2025-12-01T00:00:00Z"},  # ~180 days ago
        {"number": 2, "created_at": "2026-06-01T00:00:00Z"},  # recent
    ]
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=[],
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=pulls,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/2/reviews",
        json=[{"submitted_at": "2026-06-02T00:00:00Z"}],
        status=200,
    )
    _mock_repo_metadata("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    # Only PR #2 should be considered (PR #1 is outside 90-day window)
    assert result["avg_pr_review_days"] == 1.0
    assert result["response_coverage_rate"] == 100.0
    assert result["ownership_signal"] is False
    assert result["has_jira_sync"] is False
