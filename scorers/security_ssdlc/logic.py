import base64
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


def _fetch_workflow_contents(owner_repo: str, github_token: str) -> list[str]:
    """Fetch text contents of all workflow YAML files in .github/workflows/."""
    session = _make_github_session(github_token)
    list_resp = session.get(
        f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/workflows",
        timeout=15,
    )
    if not list_resp.ok:
        return []
    contents = []
    for entry in list_resp.json():
        if entry.get("type") != "file":
            continue
        name = entry.get("name", "")
        if not (name.endswith(".yml") or name.endswith(".yaml")):
            continue
        file_resp = session.get(entry["url"], timeout=15)
        if file_resp.ok:
            data = file_resp.json()
            raw = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
            contents.append(raw)
    return contents


def _has_branch_protection_required_checks(owner_repo: str, github_token: str) -> bool:
    """Return True if the default branch has ≥1 required status check."""
    session = _make_github_session(github_token)
    repo_resp = session.get(f"{_GITHUB_API}/repos/{owner_repo}", timeout=15)
    if not repo_resp.ok:
        return False
    default_branch = repo_resp.json().get("default_branch", "main")
    prot_resp = session.get(
        f"{_GITHUB_API}/repos/{owner_repo}/branches/{default_branch}/protection",
        timeout=15,
    )
    if not prot_resp.ok:
        return False
    data = prot_resp.json()
    checks = data.get("required_status_checks", {})
    contexts = checks.get("contexts", [])
    strict_checks = checks.get("checks", [])
    return len(contexts) > 0 or len(strict_checks) > 0


def compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]:
    """
    Check GitHub Security features for the evaluation unit's repo.

    dependabot_enabled: .github/dependabot.yml exists in the repo
    codeql_enabled:     any workflow references github/codeql-action
    """
    dependabot_enabled = False
    codeql_enabled = False

    if unit.repo:
        session = _make_github_session(github_token)
        dependabot_resp = session.get(
            f"{_GITHUB_API}/repos/{unit.repo}/contents/.github/dependabot.yml",
            timeout=15,
        )
        if dependabot_resp.status_code == 200:
            dependabot_enabled = True
        for content in _fetch_workflow_contents(unit.repo, github_token):
            if "github/codeql-action" in content:
                codeql_enabled = True

    branch_protection = (
        _has_branch_protection_required_checks(unit.repo, github_token) if unit.repo else False
    )

    return {
        "dependabot_enabled": dependabot_enabled,
        "codeql_enabled": codeql_enabled,
        "branch_protection_required_checks": branch_protection,
    }
