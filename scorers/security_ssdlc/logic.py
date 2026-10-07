import base64
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from engine.metric_outcomes import MetricOutcome, insufficient_data, measured, not_applicable
from engine.models import EvaluationUnit
from scorers.security_ssdlc.v0 import compute_v0_metrics as compute_v0_metrics
from scorers.shared.github_signals import (
    GitHubPermissionError,
    github_get,
    raise_for_required_github_evidence,
)

_GITHUB_API = "https://api.github.com"
_CANONICAL_REPO_AUTOMATION_REPO = "canonical/canonical-repo-automation"


def _required_get(url: str, token: str, *, absent_ok: bool = False) -> Any:
    response = github_get(url, token)
    if absent_ok and response.status_code == 404:
        return None
    raise_for_required_github_evidence(response, url)
    return response.json()


def repo_file_exists(owner_repo: str, path: str, github_token: str) -> bool:
    return (
        _required_get(
            f"{_GITHUB_API}/repos/{owner_repo}/contents/{path}", github_token, absent_ok=True
        )
        is not None
    )


def repo_file_text(owner_repo: str, path: str, github_token: str) -> str:
    payload = _required_get(
        f"{_GITHUB_API}/repos/{owner_repo}/contents/{path}", github_token, absent_ok=True
    )
    if payload is None:
        return ""
    content = payload.get("content", "")
    if payload.get("encoding") == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return content


def workflow_files(owner_repo: str, github_token: str) -> list[tuple[str, str]]:
    listing = _required_get(
        f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/workflows",
        github_token,
        absent_ok=True,
    )
    if listing is None:
        return []
    return sorted(
        (
            entry["name"],
            repo_file_text(owner_repo, f".github/workflows/{entry['name']}", github_token),
        )
        for entry in listing
        if entry.get("type") == "file" and entry.get("name", "").endswith((".yml", ".yaml"))
    )


def search_code_count(query: str, github_token: str) -> int:
    params = urlencode({"q": query, "per_page": 1})
    payload = _required_get(f"{_GITHUB_API}/search/code?{params}", github_token)
    return int(payload.get("total_count", 0))


def _has_signed_commits_required(owner_repo: str, github_token: str) -> bool:
    """Return True if default branch requires signed commits in protection rules."""
    repo_resp = github_get(f"{_GITHUB_API}/repos/{owner_repo}", github_token)
    raise_for_required_github_evidence(repo_resp, f"{_GITHUB_API}/repos/{owner_repo}")
    default_branch = repo_resp.json().get("default_branch", "main")
    prot_resp = github_get(
        f"{_GITHUB_API}/repos/{owner_repo}/branches/{default_branch}/protection",
        github_token,
    )
    if prot_resp.status_code == 404:
        return False
    raise_for_required_github_evidence(
        prot_resp, f"{_GITHUB_API}/repos/{owner_repo}/branches/{default_branch}/protection"
    )
    signatures = prot_resp.json().get("required_signatures", {})
    return bool(signatures.get("enabled", False))


def _has_branch_protection_required_checks(owner_repo: str, github_token: str) -> bool:
    """Return True if the default branch has ≥1 required status check."""
    repo_resp = github_get(f"{_GITHUB_API}/repos/{owner_repo}", github_token)
    raise_for_required_github_evidence(repo_resp, f"{_GITHUB_API}/repos/{owner_repo}")
    default_branch = repo_resp.json().get("default_branch", "main")
    prot_resp = github_get(
        f"{_GITHUB_API}/repos/{owner_repo}/branches/{default_branch}/protection",
        github_token,
    )
    if prot_resp.status_code == 404:
        return False
    raise_for_required_github_evidence(
        prot_resp, f"{_GITHUB_API}/repos/{owner_repo}/branches/{default_branch}/protection"
    )
    data = prot_resp.json()
    checks = data.get("required_status_checks", {})
    contexts = checks.get("contexts", [])
    strict_checks = checks.get("checks", [])
    return len(contexts) > 0 or len(strict_checks) > 0


def _has_sast_workflow(owner_repo: str, github_token: str) -> bool:
    for _, content in workflow_files(owner_repo, github_token):
        lowered = content.lower()
        if any(
            token in lowered
            for token in (
                "github/codeql-action",
                "semgrep",
                "bandit",
                "trivy",
                "grype",
                "snyk",
                "osv-scanner",
            )
        ):
            return True
    return False


def _has_cve_tracking_process(owner_repo: str, github_token: str) -> bool:
    marker_files = (
        "docs/cve.md",
        "docs/cve/README.md",
        "docs/security-updates.md",
        ".github/security-advisory.md",
        "SECURITY.md",
    )
    existing_markers = [
        path for path in marker_files if repo_file_exists(owner_repo, path, github_token)
    ]
    if not existing_markers:
        return False
    for marker in existing_markers:
        marker_text = repo_file_text(owner_repo, marker, github_token).lower()
        if any(token in marker_text for token in ("cve", "vulnerability", "security update")):
            return True
        # Marker presence outside SECURITY.md is itself meaningful process evidence.
        if marker != "SECURITY.md":
            return True
    return False


def _is_registered_in_repo_automation(owner_repo: str, github_token: str) -> bool:
    """Return True if canonical-repo-automation manages a config file for owner_repo.

    canonical-repo-automation only manages canonical/* repos. The presence of a
    per-repo config file (repos/<name>/inputs.hcl or terragrunt.hcl) is the
    authoritative registration signal.
    """
    owner, repo_name = owner_repo.split("/", 1) if "/" in owner_repo else ("", owner_repo)
    if owner.lower() != "canonical":
        return False
    repo_resp = github_get(
        f"{_GITHUB_API}/repos/{_CANONICAL_REPO_AUTOMATION_REPO}",
        github_token,
    )
    raise_for_required_github_evidence(
        repo_resp, f"{_GITHUB_API}/repos/{_CANONICAL_REPO_AUTOMATION_REPO}"
    )
    default_branch = repo_resp.json().get("default_branch", "main")
    tree_resp = github_get(
        f"{_GITHUB_API}/repos/{_CANONICAL_REPO_AUTOMATION_REPO}/git/trees/{default_branch}?recursive=1",
        github_token,
    )
    raise_for_required_github_evidence(
        tree_resp,
        f"{_GITHUB_API}/repos/{_CANONICAL_REPO_AUTOMATION_REPO}/git/trees/{default_branch}?recursive=1",
    )
    tree = tree_resp.json().get("tree", [])
    candidate_suffixes = (
        f"repos/{repo_name}/inputs.hcl",
        f"repos/{repo_name}/terragrunt.hcl",
    )
    return any(
        entry.get("type") == "blob"
        and any(entry.get("path", "").endswith(suffix) for suffix in candidate_suffixes)
        for entry in tree
    )


def _protection_outcome(
    measure: Callable[[str, str], bool], repo: str, token: str
) -> MetricOutcome:
    try:
        return measured(measure(repo, token))
    except GitHubPermissionError as exc:
        return insufficient_data(str(exc))


def compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, MetricOutcome]:
    """
    Check SSDLC signals for the evaluation unit's repo.
    """
    renovate_enabled = False
    canonical_repo_automation_registered = False
    sast_workflow_present = False
    cve_tracking_process_present = False

    if unit.repo:
        renovate_enabled = any(
            repo_file_exists(unit.repo, path, github_token)
            for path in (
                ".github/renovate.json",
                ".github/renovate.json5",
                "renovate.json",
                "renovate.json5",
            )
        )
        if not renovate_enabled:
            renovate_enabled = search_code_count(f"repo:{unit.repo} renovate", github_token) > 0

        canonical_repo_automation_registered = _is_registered_in_repo_automation(
            unit.repo,
            github_token,
        )
        sast_workflow_present = _has_sast_workflow(unit.repo, github_token)
        cve_tracking_process_present = _has_cve_tracking_process(unit.repo, github_token)

    values = {
        "renovate_enabled": renovate_enabled,
        "canonical_repo_automation_registered": canonical_repo_automation_registered,
        "sast_workflow_present": sast_workflow_present,
        "cve_tracking_process_present": cve_tracking_process_present,
    }
    outcomes = {
        key: measured(value) if unit.repo else not_applicable("Evaluation unit has no repository.")
        for key, value in values.items()
    }
    for key, measure in (
        ("signed_commits_required", _has_signed_commits_required),
        ("branch_protection_required_checks", _has_branch_protection_required_checks),
    ):
        outcomes[key] = (
            _protection_outcome(measure, unit.repo, github_token)
            if unit.repo
            else not_applicable("Evaluation unit has no repository.")
        )
    return outcomes
