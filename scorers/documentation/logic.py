from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from engine.models import EvaluationUnit
from scorers.shared.github_signals import (
    default_branch_check_runs,
    repo_file_exists,
    repo_file_text,
    repo_releases,
    workflow_files,
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _scoped_path(unit: EvaluationUnit, path: str) -> str:
    if unit.subpath:
        return f"{unit.subpath.rstrip('/')}/{path}"
    return path


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


def _readme_present(unit: EvaluationUnit, github_token: str | None) -> bool:
    return bool(_file_text(unit, "README.md", github_token).strip())


def _contributing_present(unit: EvaluationUnit, github_token: str | None) -> bool:
    return bool(_file_text(unit, "CONTRIBUTING.md", github_token).strip())


def _documentation_workflows_passing(check_runs: list[dict[str, Any]]) -> bool:
    # Require core documentation checks (lint, links, build) to be present
    # and passing. Use explicit needles to avoid accidental matches with unrelated jobs.
    lint_present = _check_run_exists(
        check_runs,
        "docs lint",
        "markdownlint",
        "vale",
        "docs-checks / vale",
    )
    lint_passed = _check_run_passed(
        check_runs,
        "docs lint",
        "markdownlint",
        "vale",
        "docs-checks / vale",
    )

    links_present = _check_run_exists(
        check_runs,
        "link check",
        "linkcheck",
        "docs links",
        "docs-checks / linkcheck",
    )
    links_passed = _check_run_passed(
        check_runs,
        "link check",
        "linkcheck",
        "docs links",
        "docs-checks / linkcheck",
    )

    # Require docs build to be present AND passing
    build_present = _check_run_exists(
        check_runs,
        "docs build",
        "documentation build",
        "build docs",
        "docs-checks / docs build",
    )
    build_passed = _check_run_passed(
        check_runs,
        "docs build",
        "documentation build",
        "build docs",
        "docs-checks / docs build",
    )

    return (
        lint_present
        and lint_passed
        and links_present
        and links_passed
        and build_present
        and build_passed
    )


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
    if 'alt="read the docs"' in readme or "alt='read the docs'" in readme:
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


def _release_notes_process_implemented(unit: EvaluationUnit, github_token: str | None) -> bool:
    """
    Determine whether a canonical release-notes workflow is implemented.

    Requires all of:
    - Release-notes structure files (common.yaml, releases/, template/)
    - A workflow file that uses canonical/release-notes-automation
    - At least two non-draft releases with non-empty body
    """
    required_structure = (
        "docs/release-notes/common.yaml",
        "docs/release-notes/releases",
        "docs/release-notes/template",
    )
    has_structure = (
        _file_exists(unit, required_structure[0], github_token)
        and _file_exists(unit, required_structure[1], github_token)
        and _file_exists(unit, required_structure[2], github_token)
    )
    if not has_structure:
        return False

    workflow_texts = [content.lower() for _, content in workflow_files(unit.repo, github_token)]
    has_generation_workflow = any(
        "canonical/release-notes-automation/.github/workflows/action.yml" in text
        for text in workflow_texts
    )
    if not has_generation_workflow:
        return False

    non_draft = [r for r in repo_releases(unit.repo, github_token) if not r.get("draft", False)]
    if len(non_draft) < 2:
        return False
    latest_two = sorted(
        non_draft,
        key=lambda r: str(r.get("published_at") or r.get("created_at") or r.get("tag_name") or ""),
        reverse=True,
    )[:2]
    return all(str(rel.get("body", "")).strip() for rel in latest_two)


def _diataxis_coverage_ai(
    unit: EvaluationUnit,
    github_token: str | None,
    openrouter_api_key: str,
    model: str,
) -> int:
    """AI-assisted diataxis coverage assessment via OpenRouter.

    Returns 0-4 score indicating Diataxis coverage (tutorials, how-tos, reference, explanation).
    Falls back to 0 if API key is missing or request fails.
    """
    if not openrouter_api_key:
        return 0

    prompt = (_PROMPTS_DIR / "diataxis_check.md").read_text()
    readme = _file_text(unit, "README.md", github_token)
    docs_index = _file_text(unit, "docs/index.md", github_token)
    payload = f"{prompt}\n\nRepository context:\nREADME:\n{readme}\n\ndocs/index.md:\n{docs_index}"

    try:
        client = OpenAI(api_key=openrouter_api_key, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": payload}],
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        value = int(parsed.get("diataxis_coverage", 0))
        return max(0, min(4, value))
    except Exception:
        return 0


def compute_metrics(
    unit: EvaluationUnit,
    github_token: str,
    openrouter_api_key: str,
    model: str = "anthropic/claude-sonnet-4.5",
) -> dict[str, Any]:
    check_runs = default_branch_check_runs(unit.repo, github_token)
    return {
        "readme_present": _readme_present(unit, github_token),
        "contributing_present": _contributing_present(unit, github_token),
        "has_security": _file_exists(unit, "SECURITY.md", github_token),
        "documentation_workflows_passing": _documentation_workflows_passing(check_runs),
        "diataxis_coverage_ai": _diataxis_coverage_ai(
            unit, github_token, openrouter_api_key, model=model
        ),
        "uses_rtd_hosting": _uses_rtd_hosting(unit, github_token),
        "release_notes_process_implemented": _release_notes_process_implemented(unit, github_token),
    }
