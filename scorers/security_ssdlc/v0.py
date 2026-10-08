"""V0's evidence-based security measurement, separate from immutable V1 rules."""

from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import quote

from engine.metric_outcomes import MetricOutcome, insufficient_data, measured, not_applicable
from engine.models import EvaluationUnit
from scorers.shared.github_signals import (
    GitHubPermissionError,
    github_get,
    raise_for_required_github_evidence,
)

_API = "https://api.github.com"
_CONFIG_PATHS = (
    "renovate.json",
    "renovate.json5",
    ".github/renovate.json",
    ".github/renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".renovaterc.json5",
)
_KEYS = ("renovate_enabled", "branch_protection_required_checks", "signed_commits_required")
_PRESET_REPOS = {"canonical/renovate-apps", "canonical/renovate-websites"}
# Renovate's bundled preset namespaces; only `:disableRenovate` among them turns Renovate off.
_BUILTIN_NAMESPACES = {
    "",
    "abandonments",
    "config",
    "customManagers",
    "default",
    "docker",
    "group",
    "helpers",
    "mergeConfidence",
    "monorepo",
    "npm",
    "packages",
    "preview",
    "regexManagers",
    "replacements",
    "schedule",
    "security",
    "workarounds",
}


def _is_builtin_preset(preset: str) -> bool:
    namespace, separator, name = preset.partition(":")
    return bool(separator and name) and ">" not in preset and namespace in _BUILTIN_NAMESPACES


class _UnknownEvidence(ValueError):
    pass


def _get(url: str, token: str, *, absent_ok: bool = False) -> Any:
    response = github_get(url, token)
    if absent_ok and response.status_code == 404:
        return None
    raise_for_required_github_evidence(response, url)
    return response.json()


def _file(repo: str, path: str, token: str, *, absent_ok: bool = True) -> str | None:
    payload = _get(f"{_API}/repos/{repo}/contents/{path}", token, absent_ok=absent_ok)
    if payload is None:
        return None
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise _UnknownEvidence("Configuration file content is unavailable.")
    try:
        return base64.b64decode(payload["content"]).decode("utf-8")
    except (KeyError, ValueError, UnicodeError) as exc:
        raise _UnknownEvidence("Configuration file content cannot be decoded.") from exc


def _configuration(text: str) -> dict[str, Any]:
    """Parse the literal JSON/JSON5 subset used by Canonical onboarding files."""
    # Tokenization preserves comments inside quoted strings, including https URLs.
    tokens = [
        token
        for token in re.findall(
            r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|'
            r"[A-Za-z_$][A-Za-z0-9_$-]*|\s+|.",
            text,
        )
        if not token.startswith(("//", "/*"))
    ]
    cleaned: list[str] = []
    for index, token in enumerate(tokens):
        if token.startswith("'"):
            value = token[1:-1].replace("\\'", "'").replace('\\"', '"')
            cleaned.append(json.dumps(value))
        elif re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$-]*", token):
            following = next((part for part in tokens[index + 1 :] if part.strip()), "")
            cleaned.append(json.dumps(token) if following == ":" else token)
        else:
            cleaned.append(token)
    literal = "".join(cleaned)
    # Only remove trailing commas outside strings.
    literal = re.sub(r'("(?:\\.|[^"\\])*")|,\s*([}\]])', lambda m: m[1] or m[2], literal)
    try:
        result = json.loads(literal)
    except ValueError as exc:
        raise _UnknownEvidence("Renovate configuration is not a supported literal object.") from exc
    if not isinstance(result, dict):
        raise _UnknownEvidence("Renovate configuration must be an object.")
    return result


def _renovate_config_enabled(
    config: dict[str, Any], token: str, seen: frozenset[str] = frozenset()
) -> bool | None:
    enabled = config.get("enabled")
    if "enabled" in config and not isinstance(enabled, bool):
        raise _UnknownEvidence("Renovate enabled setting is not a boolean.")
    extends = config.get("extends", [])
    if not isinstance(extends, list) or not all(isinstance(item, str) for item in extends):
        raise _UnknownEvidence("Renovate presets are not a literal list.")
    if enabled is False:
        return False
    result = None
    for preset in extends:
        if preset == ":disableRenovate":
            result = False
        elif _is_builtin_preset(preset):
            continue
        elif preset.startswith("github>") and preset[7:] in _PRESET_REPOS:
            if preset in seen or len(seen) >= 4:
                raise _UnknownEvidence("Renovate preset inheritance is cyclic or too deep.")
            text = _file(preset[7:], "default.json", token, absent_ok=False)
            inherited = _renovate_config_enabled(_configuration(text or ""), token, seen | {preset})
            if inherited is not None:
                result = inherited
        else:
            raise _UnknownEvidence(
                "Renovate preset is outside the approved configuration conventions."
            )
    rules = config.get("packageRules", [])
    if not isinstance(rules, list) or any(not isinstance(rule, dict) for rule in rules):
        raise _UnknownEvidence("Renovate package rules are not a literal list of objects.")
    all_disabled = False
    for rule in rules:
        if "enabled" not in rule:
            continue
        if not isinstance(rule["enabled"], bool):
            raise _UnknownEvidence("Renovate package-rule enablement is not a boolean.")
        selectors = {key: value for key, value in rule.items() if key.startswith("match")}
        matches_all = selectors == {"matchPackageNames": ["*"]}
        if rule["enabled"]:
            all_disabled = False
        elif matches_all:
            all_disabled = True
    if all_disabled:
        return False
    return True if enabled is True else result


def _renovate(repo: str, token: str) -> MetricOutcome:
    try:
        for path in _CONFIG_PATHS:
            text = _file(repo, path, token)
            if text is not None:
                enabled = _renovate_config_enabled(_configuration(text), token)
                if enabled is False:
                    return measured(False)
                return measured(_has_open_renovate_dashboard(repo, token))
        return measured(False)
    except _UnknownEvidence as exc:
        return insufficient_data(str(exc))


def _has_open_renovate_dashboard(repo: str, token: str) -> bool:
    for page in range(1, 101):
        listing = _get(f"{_API}/repos/{repo}/issues?state=open&per_page=100&page={page}", token)
        if not isinstance(listing, list):
            raise _UnknownEvidence("Open issue listing cannot be interpreted.")
        for issue in listing:
            if not isinstance(issue, dict):
                raise _UnknownEvidence("Open issue evidence cannot be interpreted.")
            if "pull_request" in issue or issue.get("state") != "open":
                continue
            if issue.get("title") != "Dependency Dashboard":
                continue
            author = issue.get("user")
            if not isinstance(author, dict):
                raise _UnknownEvidence("Dependency Dashboard author is unavailable.")
            if (
                author.get("login") == "renovate[bot]"
                and author.get("type") == "Bot"
                and author.get("id") == 29139614
            ):
                return True
        if len(listing) < 100:
            return False
    raise _UnknownEvidence("Open issue acquisition exceeds the bounded pagination limit.")


def _pattern_matches(pattern: str, value: str, default: str | None = None) -> bool:
    if pattern == "~ALL":
        return True
    if pattern == "~DEFAULT_BRANCH":
        return default is not None and value == default
    if (
        not isinstance(pattern, str)
        or re.search(r"[\[\]{}\\]|[$]", pattern)
        or pattern.startswith("~")
    ):
        raise _UnknownEvidence("Ruleset pattern is outside the supported literal conventions.")
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if pattern[index : index + 2] == "**":
                if pattern[index + 2 : index + 3] == "/":
                    parts.append("(?:.*/)?")
                    index += 3
                else:
                    parts.append(".*")
                    index += 2
            else:
                parts.append("[^/]*")
                index += 1
        else:
            parts.append("[^/]" if char == "?" else re.escape(char))
            index += 1
    return re.fullmatch("".join(parts), value) is not None


def _matches(condition: Any, value: str, default: str | None = None) -> bool:
    if not isinstance(condition, dict) or set(condition) - {"include", "exclude", "protected"}:
        raise _UnknownEvidence("Ruleset condition is not a supported include/exclude object.")
    if condition.get("protected"):
        raise _UnknownEvidence("Ruleset protected-repository selection cannot be resolved.")
    include, exclude = condition.get("include"), condition.get("exclude", [])
    if not isinstance(include, list) or not isinstance(exclude, list):
        raise _UnknownEvidence("Ruleset selectors are not literal lists.")
    excluded = [_pattern_matches(pattern, value, default) for pattern in exclude]
    included = [_pattern_matches(pattern, value, default) for pattern in include]
    return any(included) and not any(excluded)


def _applicable(ruleset: dict[str, Any], repo: str, metadata: dict[str, Any], branch: str) -> bool:
    conditions = ruleset.get("conditions")
    if not isinstance(conditions, dict) or set(conditions) - {
        "ref_name",
        "repository_name",
        "repository_id",
    }:
        raise _UnknownEvidence("Ruleset uses unknown or dynamic conditions.")
    if not _matches(conditions.get("ref_name"), f"refs/heads/{branch}", f"refs/heads/{branch}"):
        return False
    if "repository_name" in conditions and not _matches(
        conditions["repository_name"], repo.split("/", 1)[1]
    ):
        return False
    if "repository_id" in conditions:
        selector = conditions["repository_id"]
        if (
            not isinstance(selector, dict)
            or set(selector) != {"repository_ids"}
            or not isinstance(selector["repository_ids"], list)
            or metadata.get("id") is None
        ):
            raise _UnknownEvidence("Ruleset repository selection cannot be resolved.")
        if metadata["id"] not in selector["repository_ids"]:
            return False
    return True


def _has_checks(value: Any, *, ruleset: bool = False) -> bool:
    if value is None:
        return False
    if not isinstance(value, dict):
        raise _UnknownEvidence("Required status checks are not a supported object.")
    checks = value.get("required_status_checks", []) if ruleset else value.get("checks", [])
    contexts = [] if ruleset else value.get("contexts", [])
    if not isinstance(checks, list) or not isinstance(contexts, list):
        raise _UnknownEvidence("Required status checks are not literal lists.")
    if any(not isinstance(item, str) for item in contexts) or any(
        not isinstance(item, dict) or not isinstance(item.get("context"), str) for item in checks
    ):
        raise _UnknownEvidence("Required status check context cannot be interpreted.")
    return any(item.strip() for item in contexts) or any(item["context"].strip() for item in checks)


def _rulesets(repo: str, token: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for page in range(1, 101):
        url = f"{_API}/repos/{repo}/rulesets?includes_parents=true&per_page=100&page={page}"
        listing = _get(url, token)
        if not isinstance(listing, list):
            raise _UnknownEvidence("Ruleset listing is not a list.")
        for entry in listing:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), int):
                raise _UnknownEvidence("Ruleset identity is unavailable.")
            source_type = entry.get("source_type", "Repository")
            if source_type == "Organization":
                source = entry.get("source", repo.split("/", 1)[0])
                if source != repo.split("/", 1)[0]:
                    raise _UnknownEvidence("Inherited ruleset source cannot be interpreted.")
                detail_url = f"{_API}/orgs/{source}/rulesets/{entry['id']}"
            elif source_type == "Repository":
                detail_url = f"{_API}/repos/{repo}/rulesets/{entry['id']}"
            else:
                raise _UnknownEvidence("Inherited ruleset source type cannot be interpreted.")
            detail = _get(detail_url, token)
            if not isinstance(detail, dict):
                raise _UnknownEvidence("Ruleset details are not an object.")
            result.append(detail)
        if len(listing) < 100:
            return result
    raise _UnknownEvidence("Ruleset acquisition exceeds the bounded pagination limit.")


def _ruleset_requirement(
    ruleset: dict[str, Any], kind: str, repo: str, metadata: dict[str, Any], branch: str
) -> bool:
    enforcement = ruleset.get("enforcement")
    if enforcement in {"disabled", "evaluate"}:
        return False
    if enforcement != "active":
        raise _UnknownEvidence("Ruleset enforcement cannot be interpreted.")
    target = ruleset.get("target")
    if target == "tag":
        return False
    if target != "branch":
        raise _UnknownEvidence("Ruleset target cannot be interpreted.")
    if not _applicable(ruleset, repo, metadata, branch):
        return False
    bypass = ruleset.get("bypass_actors")
    if not isinstance(bypass, list):
        raise _UnknownEvidence("Ruleset bypass policy cannot be interpreted.")
    for actor in bypass:
        if not isinstance(actor, dict) or actor.get("bypass_mode") not in {
            "always",
            "pull_request",
            "exempt",
        }:
            raise _UnknownEvidence("Ruleset bypass mode cannot be interpreted.")
    if bypass:
        return False
    rules = ruleset.get("rules")
    if not isinstance(rules, list) or any(not isinstance(item, dict) for item in rules):
        raise _UnknownEvidence("Ruleset rules cannot be interpreted.")
    supported_rules = {
        "creation",
        "update",
        "deletion",
        "required_linear_history",
        "required_signatures",
        "required_deployments",
        "pull_request",
        "required_status_checks",
        "non_fast_forward",
        "commit_message_pattern",
        "commit_author_email_pattern",
        "committer_email_pattern",
        "branch_name_pattern",
        "tag_name_pattern",
        "file_path_restriction",
        "max_file_path_length",
        "file_extension_restriction",
        "max_file_size",
        "required_code_scanning",
        "workflows",
        "code_scanning",
        "copilot_code_review",
        "merge_queue",
    }
    if any(item.get("type") not in supported_rules for item in rules):
        raise _UnknownEvidence("Ruleset contains an unknown or dynamic rule type.")
    for item in rules:
        if item.get("type") == kind:
            if kind == "required_signatures":
                return True
            if not isinstance(item.get("parameters"), dict):
                raise _UnknownEvidence("Required check rule parameters are unavailable.")
            if _has_checks(item["parameters"], ruleset=True):
                return True
    return False


def _protection(repo: str, token: str, metadata: dict[str, Any]) -> dict[str, MetricOutcome]:
    keys = _KEYS[1:]
    branch = metadata.get("default_branch")
    if not isinstance(branch, str) or not branch:
        return dict.fromkeys(keys, insufficient_data("Repository default branch is unavailable."))
    url = f"{_API}/repos/{repo}/branches/{quote(branch, safe='')}/protection"
    values = dict.fromkeys(keys, False)
    unknown: dict[str, str] = {}
    try:
        classic = _get(url, token, absent_ok=True)
    except GitHubPermissionError as exc:
        classic = None
        unknown.update(dict.fromkeys(keys, str(exc)))
    if classic is not None:
        try:
            if not isinstance(classic, dict):
                raise _UnknownEvidence("Classic branch protection is not an object.")
            try:
                values[keys[0]] = _has_checks(classic.get("required_status_checks"))
            except _UnknownEvidence as exc:
                unknown[keys[0]] = str(exc)
            signatures = classic.get("required_signatures")
            if signatures is None:
                try:
                    signatures = _get(f"{url}/required_signatures", token, absent_ok=True)
                except GitHubPermissionError as exc:
                    unknown[keys[1]] = str(exc)
            if signatures is not None:
                if not isinstance(signatures, dict) or not isinstance(
                    signatures.get("enabled"), bool
                ):
                    unknown[keys[1]] = "Required signatures setting cannot be interpreted."
                else:
                    values[keys[1]] = signatures["enabled"]
        except _UnknownEvidence as exc:
            unknown.update(dict.fromkeys(keys, str(exc)))
    try:
        rulesets = _rulesets(repo, token)
    except (_UnknownEvidence, GitHubPermissionError) as exc:
        rulesets = []
        unknown.update(dict.fromkeys(keys, str(exc)))
    for key, kind in zip(keys, ("required_status_checks", "required_signatures"), strict=True):
        for ruleset in rulesets:
            try:
                values[key] |= _ruleset_requirement(ruleset, kind, repo, metadata, branch)
            except _UnknownEvidence as exc:
                unknown[key] = str(exc)
    return {
        key: measured(True)
        if values[key]
        else insufficient_data(unknown[key])
        if key in unknown
        else measured(False)
        for key in keys
    }


def compute_v0_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, MetricOutcome]:
    """Measure Renovate onboarding with bot dashboard evidence and branch requirements."""
    if not unit.repo:
        return dict.fromkeys(_KEYS, not_applicable("Evaluation unit has no repository."))
    metadata = _get(f"{_API}/repos/{unit.repo}", github_token)
    if not isinstance(metadata, dict):
        return dict.fromkeys(_KEYS, insufficient_data("Repository metadata cannot be interpreted."))
    return {
        "renovate_enabled": _renovate(unit.repo, github_token),
        **_protection(unit.repo, github_token, metadata),
    }
