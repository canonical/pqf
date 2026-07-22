from __future__ import annotations

import base64
from typing import Any

import requests

_GITHUB_API = "https://api.github.com"


def build_github_session(github_token: str | None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    if github_token:
        session.headers["Authorization"] = f"token {github_token}"
    return session


def github_get(url: str, github_token: str | None, *, accept: str | None = None) -> requests.Response:
    session = build_github_session(github_token)
    headers = {"Accept": accept} if accept else None
    response = session.get(url, headers=headers, timeout=15)
    if github_token and response.status_code in {401, 403, 404}:
        response = build_github_session(None).get(url, headers=headers, timeout=15)
    return response


def repo_file_exists(owner_repo: str, path: str, github_token: str | None) -> bool:
    response = github_get(f"{_GITHUB_API}/repos/{owner_repo}/contents/{path}", github_token)
    return response.status_code == 200


def repo_file_text(owner_repo: str, path: str, github_token: str | None) -> str:
    response = github_get(f"{_GITHUB_API}/repos/{owner_repo}/contents/{path}", github_token)
    if not response.ok:
        return ""
    payload = response.json()
    content = payload.get("content", "")
    if payload.get("encoding") == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return content


def repo_topics(owner_repo: str, github_token: str | None) -> list[str]:
    response = github_get(
        f"{_GITHUB_API}/repos/{owner_repo}/topics",
        github_token,
        accept="application/vnd.github.mercy-preview+json",
    )
    if not response.ok:
        return []
    return response.json().get("names", [])


def workflow_files(owner_repo: str, github_token: str | None) -> list[tuple[str, str]]:
    listing = github_get(f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/workflows", github_token)
    if not listing.ok:
        return []
    results: list[tuple[str, str]] = []
    for entry in listing.json():
        if entry.get("type") != "file":
            continue
        name = entry.get("name", "")
        if not name.endswith((".yml", ".yaml")):
            continue
        results.append((name, repo_file_text(owner_repo, f".github/workflows/{name}", github_token)))
    return results


def search_code_count(query: str, github_token: str | None) -> int:
    response = build_github_session(github_token).get(
        f"{_GITHUB_API}/search/code",
        params={"q": query, "per_page": 1},
        timeout=15,
    )
    if not response.ok:
        return 0
    return int(response.json().get("total_count", 0))


def default_branch_check_runs(owner_repo: str, github_token: str | None) -> list[dict[str, Any]]:
    repo_response = github_get(f"{_GITHUB_API}/repos/{owner_repo}", github_token)
    if not repo_response.ok:
        return []
    branch = repo_response.json().get("default_branch", "main")
    branch_response = github_get(f"{_GITHUB_API}/repos/{owner_repo}/branches/{branch}", github_token)
    if not branch_response.ok:
        return []
    head_sha = branch_response.json().get("commit", {}).get("sha", "")
    if not head_sha:
        return []
    checks_response = github_get(
        f"{_GITHUB_API}/repos/{owner_repo}/commits/{head_sha}/check-runs",
        github_token,
        accept="application/vnd.github+json",
    )
    if not checks_response.ok:
        return []
    return checks_response.json().get("check_runs", [])
