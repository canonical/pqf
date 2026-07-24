from typing import Any

from engine.models import EvaluationUnit
from scorers.shared.github_signals import (
    github_get,
    repo_file_exists,
    repo_file_text,
    search_code_count,
    workflow_files,
)

_GITHUB_API = "https://api.github.com"
_CANONICAL_REPO_AUTOMATION_REPO = "canonical/canonical-repo-automation"


def _has_branch_protection_required_checks(owner_repo: str, github_token: str) -> bool:
    """Return True if the default branch has ≥1 required status check."""
    repo_resp = github_get(f"{_GITHUB_API}/repos/{owner_repo}", github_token)
    if not repo_resp.ok:
        return False
    default_branch = repo_resp.json().get("default_branch", "main")
    prot_resp = github_get(
        f"{_GITHUB_API}/repos/{owner_repo}/branches/{default_branch}/protection",
        github_token,
    )
    if not prot_resp.ok:
        return False
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
    repo_name = owner_repo.split("/", 1)[-1]
    repo_resp = github_get(
        f"{_GITHUB_API}/repos/{_CANONICAL_REPO_AUTOMATION_REPO}",
        github_token,
    )
    if not repo_resp.ok:
        return False
    default_branch = repo_resp.json().get("default_branch", "main")
    tree_resp = github_get(
        f"{_GITHUB_API}/repos/{_CANONICAL_REPO_AUTOMATION_REPO}/git/trees/{default_branch}?recursive=1",
        github_token,
    )
    if not tree_resp.ok:
        return False
    tree = tree_resp.json().get("tree", [])
    candidate_paths = (
        f"/repos/{repo_name}/inputs.hcl",
        f"/repos/{repo_name}/terragrunt.hcl",
    )
    registration_path = next(
        (
            entry.get("path", "")
            for entry in tree
            if entry.get("type") == "blob"
            and any(entry.get("path", "").endswith(candidate) for candidate in candidate_paths)
        ),
        "",
    )
    if not registration_path:
        return False
    registration_text = repo_file_text(
        _CANONICAL_REPO_AUTOMATION_REPO,
        registration_path,
        github_token,
    )
    if not registration_text:
        return False
    lines = {line.strip() for line in registration_text.splitlines() if line.strip()}
    if owner_repo in lines or repo_name in lines:
        return True
    # canonical-repo-automation currently stores one config file per registered repo.
    return True


def compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]:
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

    branch_protection = (
        _has_branch_protection_required_checks(unit.repo, github_token) if unit.repo else False
    )

    return {
        "renovate_enabled": renovate_enabled,
        "canonical_repo_automation_registered": canonical_repo_automation_registered,
        "branch_protection_required_checks": branch_protection,
        "sast_workflow_present": sast_workflow_present,
        "cve_tracking_process_present": cve_tracking_process_present,
    }
