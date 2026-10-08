from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from pathlib import Path
from typing import Any

from openai import APIError, OpenAI
from packaging.version import InvalidVersion, Version

from engine.metric_outcomes import MetricOutcome, insufficient_data, measured, not_applicable
from engine.models import EvaluationUnit, ProductType
from scorers.shared.github_signals import (
    default_branch_check_runs,
    github_get,
    raise_for_required_github_evidence,
    repo_file_exists,
    repo_file_text,
    repo_releases,
    workflow_files,
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_LOG = logging.getLogger(__name__)
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
TEMPLATE_REPO = "canonical/platform-engineering-charm-template"
TEMPLATE_REF = "8299de3ec4a264c853d48c6bb09903677e38cbd7"


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


def _has_changelog(unit: EvaluationUnit, github_token: str | None) -> bool:
    """Return True if CHANGELOG.md exists and is non-empty in the repository root."""
    return _file_exists(unit, "CHANGELOG.md", github_token)


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
) -> MetricOutcome:
    if not openrouter_api_key or not model:
        return insufficient_data("AI assessment is not configured.")

    readme = _file_text(unit, "README.md", github_token)
    docs_index = _file_text(unit, "docs/index.md", github_token)
    return _assess_diataxis(
        f"README:\n{readme}\n\ndocs/index.md:\n{docs_index}",
        openrouter_api_key,
        model,
        legacy_clamp=True,
    )


def _assess_diataxis(
    documentation: str, api_key: str, model: str, *, legacy_clamp: bool = False
) -> MetricOutcome:
    prompt_file = "diataxis_check.md" if legacy_clamp else "diataxis_v0_check.md"
    prompt = (_PROMPTS_DIR / prompt_file).read_text()
    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": f"{prompt}\n\nDocumentation:\n{documentation}"}],
        )
    except APIError as exc:
        _LOG.warning(
            "AI documentation assessment failed: %s (status %s)",
            type(exc).__name__,
            getattr(exc, "status_code", "n/a"),
        )
        return insufficient_data("AI documentation assessment is unavailable.")
    try:
        content = (response.choices[0].message.content or "").strip()
        fenced = _FENCE.fullmatch(content)
        parsed = json.loads(fenced.group(1) if fenced else content)
        value = parsed["diataxis_coverage"]
        reason = parsed.get("reasoning", "")
        if type(value) is not int or (not legacy_clamp and not 0 <= value <= 4):
            raise ValueError
        if not isinstance(reason, str) or (not legacy_clamp and not reason.strip()):
            raise ValueError
    except (ValueError, KeyError, IndexError, TypeError):
        return insufficient_data("AI documentation assessment returned invalid evidence.")
    outcome = measured(max(0, min(4, value)))
    return MetricOutcome(outcome.state, outcome.value, reason.strip() or None)


def compute_metrics(
    unit: EvaluationUnit,
    github_token: str,
    openrouter_api_key: str,
    model: str = "anthropic/claude-sonnet-4.5",
) -> dict[str, MetricOutcome]:
    check_runs = default_branch_check_runs(unit.repo, github_token)
    return {
        "readme_present": measured(_readme_present(unit, github_token)),
        "contributing_present": measured(_contributing_present(unit, github_token)),
        "has_security": measured(_file_exists(unit, "SECURITY.md", github_token)),
        "documentation_workflows_passing": measured(_documentation_workflows_passing(check_runs)),
        "diataxis_coverage_ai": _diataxis_coverage_ai(
            unit, github_token, openrouter_api_key, model=model
        ),
        "uses_rtd_hosting": measured(_uses_rtd_hosting(unit, github_token)),
        "release_notes_process_implemented": measured(
            _release_notes_process_implemented(unit, github_token)
        ),
        "has_changelog": measured(_has_changelog(unit, github_token)),
    }


def _required_file_text(repo: str, path: str, token: str | None, *, ref: str | None = None) -> str:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    if ref is not None:
        url += f"?ref={ref}"
    response = github_get(url, token)
    if response.status_code == 404 and ref is None:
        return ""
    raise_for_required_github_evidence(response, url)
    try:
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise ValueError
        content = payload["content"]
        if not isinstance(content, str):
            raise ValueError
        return base64.b64decode("".join(content.split()), validate=True).decode("utf-8")
    except (ValueError, KeyError, UnicodeError, binascii.Error):
        raise RuntimeError("GitHub documentation file evidence is invalid.") from None


def _normalized_text(text: str) -> str:
    return " ".join(re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).split())


def _has_body(text: str) -> bool:
    lines = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).splitlines()
    for index, line in enumerate(lines):
        if not line.strip() or re.match(r"^\s{0,3}#{1,6}(?:\s|$)", line):
            continue
        if re.fullmatch(r"\s*[=-]+\s*", line):
            continue
        if index + 1 < len(lines) and re.fullmatch(r"\s*[=-]+\s*", lines[index + 1]):
            continue
        return True
    return False


def _root_file_adopted(unit: EvaluationUnit, path: str, token: str | None) -> MetricOutcome:
    content = _required_file_text(unit.repo, path, token)
    template = _required_file_text(TEMPLATE_REPO, path, token, ref=TEMPLATE_REF)
    if not template.strip():
        raise RuntimeError("Pinned documentation template evidence is empty.")
    return measured(_has_body(content) and _normalized_text(content) != _normalized_text(template))


def _sphinx_stack_version(
    unit: EvaluationUnit,
    token: str | None,
    docs_path: str,
    has_user_facing_docs: bool,
) -> MetricOutcome:
    if unit.product_type == ProductType.SNAP:
        return not_applicable("Snap-only repositories are exempt from Sphinx Stack adoption.")
    if unit.documentation_exemption.strip():
        return not_applicable(unit.documentation_exemption.strip())
    if not has_user_facing_docs:
        return not_applicable("Product has no user-facing documentation.")
    text = _required_file_text(unit.repo, f"{docs_path}/_dev/version", token).strip()
    try:
        Version(text)
    except InvalidVersion:
        return measured("")
    return measured(text)


def _authoritative_docs(repo: str, path: str, token: str | None) -> str | None:
    pending = [path]
    documents: list[str] = []
    size = 0
    visited = 0
    while pending:
        current = pending.pop()
        url = f"https://api.github.com/repos/{repo}/contents/{current}"
        response = github_get(url, token)
        if response.status_code == 404:
            return None
        raise_for_required_github_evidence(response, url)
        entries = response.json()
        if not isinstance(entries, list):
            raise RuntimeError("GitHub documentation directory evidence is invalid.")
        for entry in sorted(entries, key=lambda item: item["path"]):
            child = entry["path"]
            if entry["type"] == "dir" and not entry["name"].startswith(("_", ".")):
                pending.append(child)
            elif entry["type"] == "file" and child.endswith((".md", ".rst")):
                content = _required_file_text(repo, child, token)
                if _has_body(content):
                    documents.append(f"{child}:\n{content}")
                    size += len(content)
            visited += 1
            if visited > 500 or size > 200_000:
                return None
    return "\n\n".join(documents) if size >= 200 else None


def compute_v0_metrics(
    unit: EvaluationUnit,
    github_token: str,
    openrouter_api_key: str,
    model: str = "anthropic/claude-sonnet-4.5",
    *,
    docs_repo: str | None = None,
    docs_path: str = "docs",
    has_user_facing_docs: bool = True,
) -> dict[str, MetricOutcome]:
    """Measure V0 with deterministic root file adoption and informational AI coverage.

    docs_path is repository-relative, defaulting to root docs/ even in monorepos.
    Set it explicitly for an agreed component documentation scope. docs_repo selects
    an authoritative linked documentation repository for the informational assessment;
    Sphinx adoption is checked in unit.repo. unit.documentation_exemption supplies
    the reviewed product-metadata exemption reason, never inferred from a name.
    Without 200 characters of authoritative documentation, coverage is unavailable.
    """
    docs_path = docs_path.strip("/")
    result = {
        "readme_present": _root_file_adopted(unit, "README.md", github_token),
        "contributing_present": _root_file_adopted(unit, "CONTRIBUTING.md", github_token),
        # The template SECURITY.md is a complete policy, so verbatim adoption qualifies.
        "has_security": measured(
            _has_body(_required_file_text(unit.repo, "SECURITY.md", github_token))
        ),
        "uses_sphinx_stack": _sphinx_stack_version(
            unit, github_token, docs_path, has_user_facing_docs
        ),
    }
    if not has_user_facing_docs:
        coverage = not_applicable("Product has no user-facing documentation.")
    elif not openrouter_api_key or not model:
        coverage = insufficient_data("AI assessment is not configured.")
    else:
        documentation = _authoritative_docs(docs_repo or unit.repo, docs_path, github_token)
        coverage = (
            _assess_diataxis(documentation, openrouter_api_key, model)
            if documentation
            else insufficient_data("Authoritative documentation is absent or insufficient.")
        )
    result["diataxis_coverage_ai"] = coverage
    return result
