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


def _compute_avg_triage_days(
    issues: list[dict], session: requests.Session, owner_repo: str
) -> float:
    """
    Average time (days) from issue creation to first comment by a non-author.
    Issues that are PRs (have pull_request key with a truthy value) are excluded.
    Issues with no external comments are excluded from the average.
    Returns 0.0 if no triageable issues found.
    """
    triage_times: list[float] = []
    for issue in issues:
        # Skip PRs
        if issue.get("pull_request"):
            continue
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
                break
    if not triage_times:
        return 0.0
    return round(sum(triage_times) / len(triage_times), 1)


def _compute_avg_pr_review_days(
    pulls: list[dict], session: requests.Session, owner_repo: str
) -> float:
    """
    Average time (days) from PR creation to first review submission.
    PRs with no reviews are excluded from the average.
    Returns 0.0 if no reviewed PRs found.
    """
    review_times: list[float] = []
    for pr in pulls:
        created = _parse_dt(pr["created_at"])
        number = pr["number"]
        reviews_url = f"{_GITHUB_API}/repos/{owner_repo}/pulls/{number}/reviews"
        resp = session.get(reviews_url, timeout=15)
        if not resp.ok:
            continue
        reviews = resp.json()
        if reviews:
            first_review = _parse_dt(reviews[0]["submitted_at"])
            review_times.append((first_review - created).total_seconds() / 86400)
    if not review_times:
        return 0.0
    return round(sum(review_times) / len(review_times), 1)


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
            "has_squad_topic": False,
            "has_jira_sync": False,
        }

    session = _make_github_session(github_token)
    since = (datetime.now(UTC) - timedelta(days=_LOOKBACK_DAYS)).isoformat()

    all_issue_times: list[float] = []
    all_pr_times: list[float] = []

    issues_url = f"{_GITHUB_API}/repos/{repo}/issues"
    issues_resp = session.get(
        issues_url,
        params={"state": "all", "since": since, "per_page": 100},
        timeout=30,
    )
    if issues_resp.ok:
        triage_avg = _compute_avg_triage_days(issues_resp.json(), session, repo)
        if triage_avg > 0:
            all_issue_times.append(triage_avg)

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
        pr_avg = _compute_avg_pr_review_days(filtered_pulls, session, repo)
        if pr_avg > 0:
            all_pr_times.append(pr_avg)

    avg_triage = round(sum(all_issue_times) / len(all_issue_times), 1) if all_issue_times else 0.0
    avg_pr = round(sum(all_pr_times) / len(all_pr_times), 1) if all_pr_times else 0.0
    squad_topic = _has_squad_topic(repo, session)
    jira_sync = _has_jira_sync(repo, session)

    return {
        "avg_triage_days": avg_triage,
        "avg_pr_review_days": avg_pr,
        "has_squad_topic": squad_topic,
        "has_jira_sync": jira_sync,
    }
