# scorers/substrate_compat/logic.py
import base64
import re
from typing import Any

import requests

from engine.models import EvaluationUnit

_GITHUB_API = "https://api.github.com"
_BLOCK_SCALAR_PATTERN = re.compile(
    r"^(?P<indent>[ \t]*)(?:-\s+)?[^:#]+:\s*[>|][-+0-9]*\s*(?:#.*)?$"
)
_HEREDOC_START_PATTERN = re.compile(r"<<-?\s*(['\"]?)(?P<tag>[A-Za-z_][A-Za-z0-9_-]*)\1")


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


def _iter_key_section_lines(content: str, key: str):
    lines = content.splitlines()
    pattern = re.compile(rf"^(?P<indent>[ \t]*)(?:-\s+)?{re.escape(key)}:\s*(?P<value>.*)$")
    index = 0
    block_scalar_indent: int | None = None

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        line_indent = len(line) - len(line.lstrip(" \t"))
        if block_scalar_indent is not None:
            if not stripped or line_indent > block_scalar_indent:
                index += 1
                continue
            block_scalar_indent = None

        match = pattern.match(line)
        if not match:
            scalar_match = _BLOCK_SCALAR_PATTERN.match(line)
            if scalar_match:
                block_scalar_indent = len(scalar_match.group("indent"))
            index += 1
            continue

        indent = len(match.group("indent"))
        inline_value = match.group("value").strip()
        if inline_value and not _is_block_scalar_indicator(inline_value):
            yield inline_value
        if _is_block_scalar_indicator(inline_value):
            block_scalar_indent = indent
            index += 1
            continue

        cursor = index + 1
        while cursor < len(lines):
            nested_line = lines[cursor]
            stripped = nested_line.strip()
            if not stripped:
                cursor += 1
                continue

            nested_indent = len(nested_line) - len(nested_line.lstrip(" \t"))
            if nested_indent <= indent:
                break

            scalar_match = _BLOCK_SCALAR_PATTERN.match(nested_line)
            if scalar_match:
                scalar_indent = len(scalar_match.group("indent"))
                cursor += 1
                while cursor < len(lines):
                    scalar_line = lines[cursor]
                    scalar_stripped = scalar_line.strip()
                    if not scalar_stripped:
                        cursor += 1
                        continue
                    scalar_line_indent = len(scalar_line) - len(scalar_line.lstrip(" \t"))
                    if scalar_line_indent <= scalar_indent:
                        break
                    cursor += 1
                continue

            yield stripped
            cursor += 1

        index += 1


def _is_block_scalar_indicator(value: str) -> bool:
    return bool(re.fullmatch(r"[>|][-+0-9]*", value.strip()))


def _strip_yaml_inline_comment(value: str) -> str:
    in_single_quote = False
    in_double_quote = False
    escaping = False

    for index, char in enumerate(value):
        if in_double_quote:
            if escaping:
                escaping = False
                continue
            if char == "\\":
                escaping = True
                continue
            if char == '"':
                in_double_quote = False
            continue

        if in_single_quote:
            if char == "'":
                in_single_quote = False
            continue

        if char == '"':
            in_double_quote = True
            continue
        if char == "'":
            in_single_quote = True
            continue
        if char == "#":
            return value[:index].rstrip()

    return value.rstrip()


def _normalize_yaml_scalar(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("- "):
        normalized = normalized[2:].strip()
    normalized = _strip_yaml_inline_comment(normalized).strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()
    return normalized


def _has_juju_channel(content: str, track: str) -> bool:
    return any(
        _normalize_yaml_scalar(line) == track
        for line in _iter_key_section_lines(content, "juju-channel")
    )


def _iter_run_commands(content: str):
    lines = content.splitlines()
    pattern = re.compile(r"^(?P<indent>[ \t]*)(?:-\s+)?run:\s*(?P<value>.*)$")

    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue

        indent = len(match.group("indent"))
        inline_value = match.group("value").strip()
        if inline_value and not _is_block_scalar_indicator(inline_value):
            yield from _iter_shell_commands(_normalize_yaml_scalar(inline_value))
            continue

        block_lines, _ = _extract_block_scalar_lines(lines, index + 1, indent)
        scalar = _normalize_run_block_scalar(inline_value, block_lines)
        yield from _iter_shell_commands(scalar)


def _extract_block_scalar_lines(
    lines: list[str], start: int, parent_indent: int
) -> tuple[list[str], int]:
    block_lines: list[str] = []
    cursor = start
    content_indent: int | None = None

    while cursor < len(lines):
        nested_line = lines[cursor]
        stripped = nested_line.strip()
        nested_indent = len(nested_line) - len(nested_line.lstrip(" \t"))
        if stripped and nested_indent <= parent_indent:
            break

        if stripped:
            if content_indent is None or nested_indent < content_indent:
                content_indent = nested_indent
            block_lines.append(nested_line)
        else:
            block_lines.append("")
        cursor += 1

    if content_indent is None:
        return [], cursor

    dedented_lines = [line[content_indent:] if line else "" for line in block_lines]
    return dedented_lines, cursor


def _normalize_run_block_scalar(indicator: str, lines: list[str]) -> str:
    if not lines:
        return ""

    style = indicator.strip()[0]
    if style == "|":
        return "\n".join(lines)

    folded_parts: list[str] = []
    previous_blank = True
    for line in lines:
        if not line:
            folded_parts.append("\n")
            previous_blank = True
            continue
        if folded_parts and not previous_blank and not folded_parts[-1].endswith("\n"):
            folded_parts.append(" ")
        folded_parts.append(line)
        previous_blank = False
    return "".join(folded_parts)


def _find_unquoted_heredoc_start(command: str) -> str | None:
    in_single_quote = False
    in_double_quote = False
    escaping = False

    for index, char in enumerate(command):
        if in_double_quote:
            if escaping:
                escaping = False
                continue
            if char == "\\":
                escaping = True
                continue
            if char == '"':
                in_double_quote = False
            continue

        if in_single_quote:
            if char == "'":
                in_single_quote = False
            continue

        if char == '"':
            in_double_quote = True
            continue
        if char == "'":
            in_single_quote = True
            continue
        if char == "<" and command[index : index + 2] == "<<":
            heredoc_match = _HEREDOC_START_PATTERN.match(command, index)
            if heredoc_match:
                return heredoc_match.group("tag")
    return None


def _iter_shell_commands(script: str):
    heredoc_tag: str | None = None

    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if heredoc_tag is not None:
            if stripped == heredoc_tag:
                heredoc_tag = None
            continue

        if not stripped.startswith("#"):
            heredoc_tag = _find_unquoted_heredoc_start(stripped)
        yield stripped


def _uses_canonical_k8s(content: str) -> bool:
    if any(
        _normalize_yaml_scalar(line).lower() == "true"
        for line in _iter_key_section_lines(content, "use-canonical-k8s")
    ):
        return True
    return any(
        re.match(
            r"^juju\s+bootstrap\s+(?:microk8s|canonical-kubernetes|ck8s)\b",
            command.strip().lower(),
        )
        for command in _iter_run_commands(content)
    )


def _has_integration_signal(content: str) -> bool:
    if any(
        "integration_test" in _normalize_yaml_scalar(line).lower()
        for line in _iter_key_section_lines(content, "uses")
    ):
        return True

    command_patterns = (
        r"(^|&&|\|\||;)\s*pytest\s+-m\s+integration\b",
        r"(^|&&|\|\||;)\s*tox\s+-e\s+integration\b",
    )
    return any(
        re.search(pattern, command.strip().lower())
        for command in _iter_run_commands(content)
        for pattern in command_patterns
    )


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


def compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]:
    """
    Determine substrate compatibility by scanning GitHub workflow files.

    supports_juju_3: any workflow matches juju-channel:.*3/stable
    supports_juju_4: any workflow matches juju-channel:.*4/stable
    uses_canonical_k8s: any workflow contains use-canonical-k8s: true
    """
    supports_juju_3 = False
    supports_juju_4 = False
    uses_canonical_k8s = False
    substrate_test_evidence_present = False

    if unit.repo:
        for content in _fetch_workflow_contents(unit.repo, github_token):
            has_integration_signal = _has_integration_signal(content)
            has_substrate_target_signal = False
            if _has_juju_channel(content, "3/stable"):
                supports_juju_3 = True
                has_substrate_target_signal = True
            if _has_juju_channel(content, "4/stable"):
                supports_juju_4 = True
                has_substrate_target_signal = True
            if _uses_canonical_k8s(content):
                uses_canonical_k8s = True
                has_substrate_target_signal = True
            if has_integration_signal and has_substrate_target_signal:
                substrate_test_evidence_present = True

    return {
        "supports_juju_3": supports_juju_3,
        "supports_juju_4": supports_juju_4,
        "substrate_test_evidence_present": substrate_test_evidence_present,
        "uses_canonical_k8s": uses_canonical_k8s,
    }
