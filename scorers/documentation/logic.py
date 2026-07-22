from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from engine.models import EvaluationUnit
from scorers.shared.github_signals import (
    default_branch_check_runs,
    repo_file_exists,
    repo_file_text,
    repo_releases,
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _scoped_path(unit: EvaluationUnit, path: str) -> str:
    if unit.subpath:
        return f"{unit.subpath.rstrip('/')}/{path}"
    return path


def _section_present(text: str, *candidates: str) -> bool:
    wanted = tuple(candidate.lower() for candidate in candidates)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        heading = re.sub(r"\s+", " ", stripped.lstrip("#").strip().lower())
        if any(candidate in heading for candidate in wanted):
            return True
    return False


def _file_exists(unit: EvaluationUnit, path: str, github_token: str | None) -> bool:
    return repo_file_exists(unit.repo, _scoped_path(unit, path), github_token)


def _file_text(unit: EvaluationUnit, path: str, github_token: str | None) -> str:
    return repo_file_text(unit.repo, _scoped_path(unit, path), github_token)


def _any_file_exists(
    unit: EvaluationUnit, paths: tuple[str, ...], github_token: str | None
) -> bool:
    return any(_file_exists(unit, path, github_token) for path in paths)


def _name_matches(name: str, needle: str) -> bool:
    """Return True when the needle appears as a discrete token or phrase in the check-run name.

    Uses a conservative regex that requires non-alphanumeric boundaries around the needle
    to avoid accidental partial matches (e.g. "lint" matching "super-linter-job").
    """
    name = name.lower()
    needle = needle.lower()
    pattern = rf"(^|[^a-z0-9]){re.escape(needle)}([^a-z0-9]|$)"
    return re.search(pattern, name) is not None


def _check_run_passed(check_runs: list[dict[str, Any]], *needles: str) -> bool:
    for check in check_runs:
        name = str(check.get("name", "")).lower()
        conclusion = str(check.get("conclusion", "")).lower()
        for needle in needles:
            if _name_matches(name, needle):
                return conclusion == "success"
    return False


def _check_run_exists(check_runs: list[dict[str, Any]], *needles: str) -> bool:
    for check in check_runs:
        name = str(check.get("name", "")).lower()
        for needle in needles:
            if _name_matches(name, needle):
                return True
    return False


def _readme_meets_structure(unit: EvaluationUnit, github_token: str | None) -> bool:
    readme = _file_text(unit, "README.md", github_token)
    if not readme.strip():
        return False
    required_groups = (
        ("overview", "about", "summary"),
        ("getting started", "quick start", "installation", "install"),
        ("support", "troubleshooting", "help"),
    )
    return all(_section_present(readme, *group) for group in required_groups)


def _contributing_meets_structure(unit: EvaluationUnit, github_token: str | None) -> bool:
    contributing = _file_text(unit, "CONTRIBUTING.md", github_token)
    if not contributing.strip():
        return False
    required_groups = (
        ("contributing",),
        ("development", "local development", "setup"),
        ("testing", "validation"),
        ("governance", "review", "code of conduct"),
    )
    return all(_section_present(contributing, *group) for group in required_groups)


def _documentation_workflows_passing(check_runs: list[dict[str, Any]]) -> bool:
    # Require that the core documentation checks (lint, style, links, build) are present and passing.
    # Use explicit needles to avoid accidental matches with unrelated jobs.
    lint_present = _check_run_exists(check_runs, "docs lint", "markdownlint")
    lint_passed = _check_run_passed(check_runs, "docs lint", "markdownlint")

    style_present = _check_run_exists(check_runs, "vale", "style guide")
    style_passed = _check_run_passed(check_runs, "vale", "style guide")

    links_present = _check_run_exists(check_runs, "link check", "linkcheck", "docs links")
    links_passed = _check_run_passed(check_runs, "link check", "linkcheck", "docs links")

    # Require docs build to be present AND passing
    build_present = _check_run_exists(check_runs, "docs build", "documentation build", "build docs")
    build_passed = _check_run_passed(
        check_runs,
        "docs build",
        "documentation build",
        "build docs",
    )

    return (
        lint_present
        and lint_passed
        and style_present
        and style_passed
        and links_present
        and links_passed
        and build_present
        and build_passed
    )


def _diataxis_coverage(unit: EvaluationUnit, github_token: str | None) -> int:
    categories = (
        ("docs/tutorial.md", "docs/tutorial/README.md", "tutorial.md", "docs/getting-started.md"),
        ("docs/how-to.md", "docs/howto.md", "docs/how-to/README.md", "how-to.md"),
        ("docs/reference.md", "docs/reference/README.md", "reference.md"),
        (
            "docs/explanation.md",
            "docs/explanation/README.md",
            "docs/architecture.md",
            "explanation.md",
        ),
    )
    return sum(1 for paths in categories if _any_file_exists(unit, paths, github_token))


def _tutorial_tested(
    unit: EvaluationUnit, github_token: str | None, check_runs: list[dict[str, Any]]
) -> bool:
    tutorial_present = _any_file_exists(
        unit,
        ("docs/tutorial.md", "docs/tutorial/README.md", "tutorial.md", "docs/getting-started.md"),
        github_token,
    )
    # Support CI-based tutorial verification beyond Playwright/e2e naming by matching
    # a broader but deterministic set of substrings commonly used for tutorial tests.
    tutorial_tested = _check_run_passed(
        check_runs,
        "tutorial",
        "playwright",
        "e2e",
        "docs test",
        "docs-test",
        "documentation test",
        "tutorial-test",
        "integration test",
        "integration-test",
    )
    return tutorial_present and tutorial_tested


def _uses_rtd_hosting(unit: EvaluationUnit, github_token: str | None) -> bool:
    doc_url = unit.documentation_url.lower()
    readme = _file_text(unit, "README.md", github_token).lower()
    return (
        "readthedocs" in doc_url
        or "readthedocs-hosted.com" in doc_url
        or "readthedocs" in readme
    )


def _recent_release_notes_present(unit: EvaluationUnit, github_token: str | None) -> bool:
    """
    Determine whether recent releases have release notes.

    Deterministic approach:
    - Query repository releases via the GitHub API (repo_releases)
    - Inspect the last two non-draft releases
    - Return True if both have a non-empty 'body' field (release notes)
    - Return False if fewer than two non-draft releases exist or their bodies are empty
    """
    releases = repo_releases(unit.repo, github_token)
    if not releases:
        return False
    # Filter out draft releases and take the first two
    non_draft = [r for r in releases if not r.get("draft", False)]
    if len(non_draft) < 2:
        return False
    recent_two = non_draft[:2]
    for rel in recent_two:
        body = str(rel.get("body", "") or "").strip()
        if not body:
            return False
    return True


def compute_metrics(
    unit: EvaluationUnit,
    github_token: str,
    openrouter_api_key: str,
    model: str = "anthropic/claude-sonnet-4.5",
) -> dict[str, Any]:
    del openrouter_api_key, model
    check_runs = default_branch_check_runs(unit.repo, github_token)
    return {
        "readme_meets_structure": _readme_meets_structure(unit, github_token),
        "contributing_meets_structure": _contributing_meets_structure(unit, github_token),
        "has_security": _file_exists(unit, "SECURITY.md", github_token),
        "documentation_workflows_passing": _documentation_workflows_passing(check_runs),
        "diataxis_coverage": _diataxis_coverage(unit, github_token),
        "tutorial_tested": _tutorial_tested(unit, github_token, check_runs),
        "uses_rtd_hosting": _uses_rtd_hosting(unit, github_token),
        "recent_release_notes_present": _recent_release_notes_present(unit, github_token),
    }
