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
    """Return True if the latest check-run matching any of the needles has a 'success' conclusion.

    Uses completed_at or started_at timestamps when present to pick the latest run within a
    check-family. If timestamps are missing, falls back to the last occurrence in the
    provided list for deterministic behavior.
    """
    latest_key = None
    latest_conclusion: str | None = None
    for idx, check in enumerate(check_runs):
        name = str(check.get("name", "")).lower()
        conclusion = str(check.get("conclusion", "")).lower()
        for needle in needles:
            if _name_matches(name, needle):
                # Prefer completed_at, then started_at; these are ISO timestamps and
                # compare lexicographically. Fall back to index to be deterministic.
                ts = check.get("completed_at") or check.get("started_at") or ""
                key = (str(ts), idx)
                if latest_key is None or key > latest_key:
                    latest_key = key
                    latest_conclusion = conclusion
    return (latest_conclusion or "") == "success"


def _check_run_exists(check_runs: list[dict[str, Any]], *needles: str) -> bool:
    for check in check_runs:
        name = str(check.get("name", "")).lower()
        for needle in needles:
            if _name_matches(name, needle):
                return True
    return False


def _contains_template_markers(text: str) -> bool:
    """Detect common template placeholders or unresolved instruction comments.

    Conservative deterministic checks for cookiecutter/templating markers and
    obvious "replace me"/TODO comments used by repository templates.
    """
    if not text:
        return False
    lower = text.lower()
    # Common templating placeholders
    if "{{" in text and "}}" in text:
        return True
    if "cookiecutter" in lower:
        return True
    # Explicit replace/todo markers frequently left from templates
    templates = [
        "replace_me",
        "project_name",
        "todo",
        "fixme",
        "<!-- todo",
        "<!-- replace",
        "[//]: #",
        "this project was generated",
    ]
    for t in templates:
        if t in lower:
            return True
    return False


def _readme_meets_structure(unit: EvaluationUnit, github_token: str | None) -> bool:
    readme = _file_text(unit, "README.md", github_token)
    if not readme.strip():
        return False
    # Fail if the README looks like an unrendered template or contains placeholders
    if _contains_template_markers(readme):
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
    # Fail if the contributing file looks like an unrendered template or contains placeholders
    if _contains_template_markers(contributing):
        return False
    required_groups = (
        ("contributing",),
        ("development", "local development", "setup"),
        ("testing", "validation"),
        ("governance", "review", "code of conduct"),
    )
    return all(_section_present(contributing, *group) for group in required_groups)


def _documentation_workflows_passing(check_runs: list[dict[str, Any]]) -> bool:
    # Require core documentation checks (lint, links, build) to be present
    # and passing. Use explicit needles to avoid accidental matches with unrelated jobs.
    lint_present = _check_run_exists(check_runs, "docs lint", "markdownlint")
    lint_passed = _check_run_passed(check_runs, "docs lint", "markdownlint")

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
    # Require that a check-run name indicates BOTH tutorial context AND a test/verification intent.
    # Evaluate the latest matching check-run conclusion (by completed_at/started_at, fallback to
    # list order) rather than accepting the first success we encounter. If the latest matching
    # tutorial-test run failed, the metric should be False.
    tutorial_needles = (
        "tutorial",
        "tutorials",
        "docs tutorial",
    )
    intent_needles = ("test", "tests", "e2e", "verification", "verify", "validation", "validate")

    latest_key = None
    latest_conclusion: str | None = None
    for idx, check in enumerate(check_runs):
        name = str(check.get("name", "")).lower()
        conclusion = str(check.get("conclusion", "")).lower()
        has_tutorial = any(_name_matches(name, t) for t in tutorial_needles)
        has_intent = any(_name_matches(name, i) for i in intent_needles)
        if not (has_tutorial and has_intent):
            continue
        # Prefer completed_at, then started_at. These are ISO timestamps
        # and compare lexicographically. Fall back to the list index for
        # deterministic ordering when timestamps are missing.
        ts = check.get("completed_at") or check.get("started_at") or ""
        key = (str(ts), idx)
        if latest_key is None or key > latest_key:
            latest_key = key
            latest_conclusion = conclusion
    if latest_conclusion is None:
        return False
    # Only count as tested if the latest matching run concluded successfully
    # and a tutorial file exists in the repository.
    return (latest_conclusion == "success") and tutorial_present


def _uses_rtd_hosting(unit: EvaluationUnit, github_token: str | None) -> bool:
    """Tightly detect ReadTheDocs hosting.

    Require an explicit ReadTheDocs signal only: either the documentation_url points at
    a readthedocs domain, the README contains an explicit RTD URL, or the README includes
    a Read the Docs badge/image with an alt or src referencing readthedocs domains. Avoid
    generic textual mentions that could be false positives.
    """
    doc_url = (unit.documentation_url or "").lower()
    if any(token in doc_url for token in ("readthedocs", "readthedocs-hosted.com")):
        return True
    readme = _file_text(unit, "README.md", github_token).lower()
    if not readme:
        return False
    # Explicit RTD URLs (readthedocs.io/.org/.hosted.com/hosted)
    rtd_url_regex = (
        r'https?://[^")\s]*'
        r"(?:readthedocs\.io|readthedocs\.org|readthedocs-hosted\.com)"
    )
    if re.search(rtd_url_regex, readme):
        return True
    # Explicit badge alt text referencing 'read the docs'
    if "alt=\"read the docs\"" in readme or "alt='read the docs'" in readme:
        return True
    # Markdown images with a src that includes readthedocs domains
    md_badge_regex = (
        r"!\[[^\]]*\]\([^\)]*"
        r"(?:readthedocs\.io|readthedocs\.org|readthedocs-hosted\.com)"
        r"[^\)]*\)"
    )
    if re.search(md_badge_regex, readme):
        return True
    img_regex = (
        r'<img[^>]+src=["\']\S*'
        r"(?:readthedocs\.io|readthedocs\.org|readthedocs-hosted\.com)"
        r'\S*["\']'
    )
    if re.search(img_regex, readme):
        return True
    return False


def _recent_release_notes_present(unit: EvaluationUnit, github_token: str | None) -> bool:
    """
    Determine whether recent releases have release notes and a documented process.

    Deterministic approach:
    - Require a deterministic process evidence marker file (one of a known set)
    - Query repository releases via the GitHub API (repo_releases)
    - Inspect the last two non-draft releases
    - Return True if process marker exists and both releases have a non-empty 'body'
    """
    # Known deterministic marker files that indicate a release-notes process exists
    marker_paths = (
        "docs/release-notes.md",
        "docs/release-notes/README.md",
        ".github/release-notes.md",
        "RELEASE_NOTES.md",
        "docs/releasing.md",
        ".github/release-process.md",
    )
    # Require process evidence marker
    if not _any_file_exists(unit, marker_paths, github_token):
        return False

    releases = repo_releases(unit.repo, github_token)
    if not releases:
        return False
    # Filter out draft releases and sort explicitly so "latest two" is deterministic.
    non_draft = [r for r in releases if not r.get("draft", False)]
    non_draft.sort(
        key=lambda r: str(
            r.get("published_at")
            or r.get("created_at")
            or r.get("released_at")
            or r.get("tag_name")
            or ""
        ),
        reverse=True,
    )
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
