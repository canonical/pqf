from __future__ import annotations

import base64
import binascii
from typing import Any

import requests

_GITHUB_API = "https://api.github.com"


class GitHubAcquisitionError(RuntimeError):
    """Raised when required GitHub evidence could not be acquired."""

    def __init__(self, status_code: int, url: str):
        self.status_code = status_code
        self.url = url
        super().__init__(f"GitHub evidence acquisition failed: status={status_code} url={url}")


def raise_for_required_github_evidence(response: requests.Response, url: str) -> None:
    if not response.ok:
        raise GitHubAcquisitionError(response.status_code, url)


def required_github_json(response: requests.Response, url: str, expected_type: type) -> Any:
    try:
        payload = response.json()
    except (requests.exceptions.JSONDecodeError, ValueError):
        raise GitHubAcquisitionError(response.status_code, url) from None
    if not isinstance(payload, expected_type):
        raise GitHubAcquisitionError(response.status_code, url)
    return payload


def decode_github_file_content(response: requests.Response, url: str) -> str:
    payload = required_github_json(response, url, dict)
    content = payload.get("content")
    if not isinstance(content, str):
        raise GitHubAcquisitionError(response.status_code, url)
    if payload.get("encoding") == "base64":
        try:
            compact_content = "".join(content.split())
            return base64.b64decode(compact_content, validate=True).decode(
                "utf-8", errors="replace"
            )
        except (binascii.Error, ValueError):
            raise GitHubAcquisitionError(response.status_code, url) from None
    return content


def _session_get(session: requests.Session, url: str, **kwargs: Any) -> requests.Response:
    try:
        return session.get(url, **kwargs)
    except requests.RequestException:
        raise GitHubAcquisitionError(0, url) from None


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


def github_session_get(
    session: requests.Session,
    url: str,
    **kwargs: Any,
) -> requests.Response:
    response = _session_get(session, url, **kwargs)
    retry_anonymously = (
        response.status_code == 401
        or response.status_code == 429
        or (response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0")
    )
    if retry_anonymously and session.headers.get("Authorization"):
        return _session_get(build_github_session(None), url, **kwargs)
    return response


def github_get(
    url: str,
    github_token: str | None,
    *,
    accept: str | None = None,
) -> requests.Response:
    session = build_github_session(github_token)
    headers = {"Accept": accept} if accept else None
    response = _session_get(session, url, headers=headers, timeout=15)
    # If we tried with a token but got an auth/visibility-related error,
    # retry anonymously (some repos being scored are public)
    if github_token and response.status_code in {401, 403, 404}:
        response = _session_get(
            build_github_session(None),
            url,
            headers=headers,
            timeout=15,
        )
    return response


def repo_file_exists(owner_repo: str, path: str, github_token: str | None) -> bool:
    url = f"{_GITHUB_API}/repos/{owner_repo}/contents/{path}"
    response = github_get(url, github_token)
    if response.status_code == 404:
        return False
    raise_for_required_github_evidence(response, url)
    return True


def repo_file_text(
    owner_repo: str,
    path: str,
    github_token: str | None,
    *,
    allow_not_found: bool = True,
) -> str:
    url = f"{_GITHUB_API}/repos/{owner_repo}/contents/{path}"
    response = github_get(url, github_token)
    if response.status_code == 404 and allow_not_found:
        return ""
    raise_for_required_github_evidence(response, url)
    return decode_github_file_content(response, url)


def repo_topics(owner_repo: str, github_token: str | None) -> list[str]:
    url = f"{_GITHUB_API}/repos/{owner_repo}/topics"
    response = github_get(
        url,
        github_token,
        accept="application/vnd.github.mercy-preview+json",
    )
    raise_for_required_github_evidence(response, url)
    payload = required_github_json(response, url, dict)
    names = payload.get("names")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise GitHubAcquisitionError(response.status_code, url)
    return names


def workflow_files(owner_repo: str, github_token: str | None) -> list[tuple[str, str]]:
    url = f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/workflows"
    listing = github_get(url, github_token)
    if listing.status_code == 404:
        return []
    raise_for_required_github_evidence(listing, url)
    entries = required_github_json(listing, url, list)
    results: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise GitHubAcquisitionError(listing.status_code, url)
        if entry.get("type") != "file":
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            raise GitHubAcquisitionError(listing.status_code, url)
        if not name.endswith((".yml", ".yaml")):
            continue
        if not isinstance(entry.get("url"), str):
            raise GitHubAcquisitionError(listing.status_code, url)
        file_text = repo_file_text(
            owner_repo,
            f".github/workflows/{name}",
            github_token,
            allow_not_found=False,
        )
        results.append((name, file_text))
    # Sort by filename for deterministic output
    results.sort(key=lambda t: t[0])
    return results


def search_code_count(query: str, github_token: str | None) -> int:
    # Use same authenticated -> anonymous retry behavior as github_get for public repos.
    session = build_github_session(github_token)
    response = _session_get(
        session,
        f"{_GITHUB_API}/search/code",
        params={"q": query, "per_page": 1},
        timeout=15,
    )
    if github_token and response.status_code in {401, 403, 404}:
        # Retry anonymously
        response = _session_get(
            build_github_session(None),
            f"{_GITHUB_API}/search/code",
            params={"q": query, "per_page": 1},
            timeout=15,
        )
    url = f"{_GITHUB_API}/search/code"
    raise_for_required_github_evidence(response, url)
    payload = required_github_json(response, url, dict)
    count = payload.get("total_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise GitHubAcquisitionError(response.status_code, url)
    return count


def default_branch_check_runs(
    owner_repo: str,
    github_token: str | None,
) -> list[dict[str, Any]]:
    repo_response = github_get(f"{_GITHUB_API}/repos/{owner_repo}", github_token)
    repo_url = f"{_GITHUB_API}/repos/{owner_repo}"
    raise_for_required_github_evidence(repo_response, repo_url)
    repo_payload = required_github_json(repo_response, repo_url, dict)
    branch = repo_payload.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise GitHubAcquisitionError(repo_response.status_code, repo_url)
    url = f"{_GITHUB_API}/repos/{owner_repo}/branches/{branch}"
    branch_response = github_get(url, github_token)
    raise_for_required_github_evidence(branch_response, url)
    branch_payload = required_github_json(branch_response, url, dict)
    commit = branch_payload.get("commit")
    if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str) or not commit["sha"]:
        raise GitHubAcquisitionError(branch_response.status_code, url)
    head_sha = commit["sha"]
    url = f"{_GITHUB_API}/repos/{owner_repo}/commits/{head_sha}/check-runs"
    headers = {"Accept": "application/vnd.github+json"}
    runs: list[dict[str, Any]] = []
    page = 1
    while True:
        session = build_github_session(github_token)
        checks_response = _session_get(
            session,
            url,
            headers=headers,
            params={"per_page": 100, "page": page},
            timeout=15,
        )
        if github_token and checks_response.status_code in {401, 403}:
            checks_response = _session_get(
                build_github_session(None),
                url,
                headers=headers,
                params={"per_page": 100, "page": page},
                timeout=15,
            )
        raise_for_required_github_evidence(checks_response, url)
        checks_payload = required_github_json(checks_response, url, dict)
        page_runs = checks_payload.get("check_runs")
        if not isinstance(page_runs, list) or not all(isinstance(run, dict) for run in page_runs):
            raise GitHubAcquisitionError(checks_response.status_code, url)
        runs.extend(page_runs)
        if len(page_runs) < 100:
            break
        page += 1
    return runs


def repo_releases(owner_repo: str, github_token: str | None) -> list[dict[str, Any]]:
    """Return releases for a repository using the GitHub Releases API.

    Falls back to anonymous request if an authenticated request fails due to visibility.
    """
    url = f"{_GITHUB_API}/repos/{owner_repo}/releases"
    response = github_get(url, github_token)
    raise_for_required_github_evidence(response, url)
    releases = required_github_json(response, url, list)
    if not all(isinstance(release, dict) for release in releases):
        raise GitHubAcquisitionError(response.status_code, url)
    return releases
