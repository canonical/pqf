# scorers/support_engagement/logic.py
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from engine.models import EvaluationUnit

_GITHUB_API = "https://api.github.com"
_LOOKBACK_DAYS = 90


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


def _parse_dt(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


def _has_squad_topic(owner_repo: str, session: requests.Session) -> bool:
    """True if the repo has a GitHub topic matching 'squad-*'."""
    resp = session.get(
        f"{_GITHUB_API}/repos/{owner_repo}/topics",
        headers={"Accept": "application/vnd.github.mercy-preview+json"},
        timeout=15,
    )
    if not resp.ok:
        return False
    topics = resp.json().get("names", [])
    return any(topic.startswith("squad-") for topic in topics)


def _has_jira_sync(owner_repo: str, session: requests.Session) -> bool:
    """True if .github/.jira_sync_config.yaml exists in the repo."""
    resp = session.get(
        f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/.jira_sync_config.yaml",
        timeout=15,
    )
    return resp.status_code == 200


def _compute_issue_triage_stats(
    issues: list[dict], session: requests.Session, owner_repo: str
) -> tuple[float, int, int]:
    """
    Average time (days) from issue creation to first comment by a non-author.
    Issues that are PRs (have pull_request key with a truthy value) are excluded.
    Issues with no external comments are excluded from the average.
    Returns 0.0 if no triageable issues found.
    """
    triage_times: list[float] = []
    eligible_issues = 0
    responded_issues = 0
    for issue in issues:
        # Skip PRs
        if issue.get("pull_request"):
            continue
        eligible_issues += 1
        created = _parse_dt(issue["created_at"])
        author = issue["user"]["login"]
        number = issue["number"]
        comments_url = f"{_GITHUB_API}/repos/{owner_repo}/issues/{number}/comments"
        resp = session.get(comments_url, timeout=15)
        if not resp.ok:
            continue
        for comment in resp.json():
            if comment["user"]["login"] != author:
                first_comment = _parse_dt(comment["created_at"])
                triage_times.append((first_comment - created).total_seconds() / 86400)
                responded_issues += 1
                break
    avg = round(sum(triage_times) / len(triage_times), 1) if triage_times else 0.0
    return avg, responded_issues, eligible_issues


def _compute_pr_review_stats(
    pulls: list[dict], session: requests.Session, owner_repo: str
) -> tuple[float, int, int]:
    """
    Average time (days) from PR creation to first review submission.
    PRs with no reviews are excluded from the average.
    Returns 0.0 if no reviewed PRs found.
    """
    review_times: list[float] = []
    eligible_prs = 0
    responded_prs = 0
    for pr in pulls:
        eligible_prs += 1
        created = _parse_dt(pr["created_at"])
        number = pr["number"]
        reviews_url = f"{_GITHUB_API}/repos/{owner_repo}/pulls/{number}/reviews"
        resp = session.get(reviews_url, timeout=15)
        if not resp.ok:
            continue
        reviews = resp.json()
        if reviews:
            first_review = min(_parse_dt(review["submitted_at"]) for review in reviews)
            review_times.append((first_review - created).total_seconds() / 86400)
            responded_prs += 1
    avg = round(sum(review_times) / len(review_times), 1) if review_times else 0.0
    return avg, responded_prs, eligible_prs


def compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]:
    """
    Compute support engagement metrics from GitHub issues and PRs
    for the evaluation unit's repo, looking back 90 days.
    """
    repo = unit.repo
    if not repo:
        return {
            "avg_triage_days": 0.0,
            "avg_pr_review_days": 0.0,
            "response_coverage_rate": 0,
            "ownership_signal": False,
            "has_jira_sync": False,
        }

    session = _make_github_session(github_token)
    since = (datetime.now(UTC) - timedelta(days=_LOOKBACK_DAYS)).isoformat()

    triage_avg = 0.0
    pr_avg = 0.0
    issue_responded = 0
    issue_total = 0
    pr_responded = 0
    pr_total = 0

    issues_url = f"{_GITHUB_API}/repos/{repo}/issues"
    issues_resp = session.get(
        issues_url,
        params={"state": "all", "since": since, "per_page": 100},
        timeout=30,
    )
    if issues_resp.ok:
        triage_avg, issue_responded, issue_total = _compute_issue_triage_stats(
            issues_resp.json(), session, repo
        )

    pulls_url = f"{_GITHUB_API}/repos/{repo}/pulls"
    pulls_resp = session.get(
        pulls_url,
        params={"state": "all", "per_page": 100},
        timeout=30,
    )
    if pulls_resp.ok:
        # Filter PRs by 90-day window (since param not supported on /pulls endpoint)
        since_dt = _parse_dt(since)
        filtered_pulls = [p for p in pulls_resp.json() if _parse_dt(p["created_at"]) >= since_dt]
        pr_avg, pr_responded, pr_total = _compute_pr_review_stats(filtered_pulls, session, repo)

    avg_triage = triage_avg
    avg_pr = pr_avg
    total_items = issue_total + pr_total
    total_responded = issue_responded + pr_responded
    response_coverage_rate = round((100 * total_responded / total_items), 1) if total_items else 0.0
    squad_topic = _has_squad_topic(repo, session)
    jira_sync = _has_jira_sync(repo, session)

    return {
        "avg_triage_days": avg_triage,
        "avg_pr_review_days": avg_pr,
        "response_coverage_rate": response_coverage_rate,
        "ownership_signal": squad_topic,
        "has_jira_sync": jira_sync,
    }
