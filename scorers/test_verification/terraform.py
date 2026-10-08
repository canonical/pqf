"""Parse the supported Terraform provider declarations without executing HCL."""

import json
import re
from collections import defaultdict

from engine.metric_outcomes import MetricOutcome, insufficient_data, measured, not_applicable

_TOKENS = re.compile(
    r"<<-?(?P<label>[A-Za-z_]\w*)\r?\n[\s\S]*?\n[ \t]*(?P=label)\b|"
    r'\s+|#[^\n]*|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'
    r"[A-Za-z_][A-Za-z_0-9-]*|[0-9]+(?:\.[0-9]+)*|[^\s]"
)
_CONSTRAINT = re.compile(r"^(~>|>=|<=|!=|>|<|=)?\s*(\d+(?:\.\d+){0,2})$")


def major_one(constraint: object) -> bool | None:
    """True only when the nonempty version range stays within provider major 1."""
    if not isinstance(constraint, str) or "${" in constraint:
        return None
    lower = (0, 0, 0)
    upper = None
    lower_closed = True
    upper_closed = False
    excluded = set()
    for clause in constraint.split(","):
        match = _CONSTRAINT.fullmatch(clause.strip())
        if not match:
            return None
        operator, version = match.groups()
        parts = tuple(int(part) for part in version.split("."))
        value = (*parts, *(0 for _ in range(3 - len(parts))))
        if operator == "!=":
            excluded.add(value)
            continue
        if operator == "~>":
            bound = (value[0] + 1, 0, 0) if len(parts) < 3 else (value[0], value[1] + 1, 0)
            if value > lower:
                lower, lower_closed = value, True
            if upper is None or bound < upper:
                upper, upper_closed = bound, False
        elif operator in {">", ">="}:
            if value > lower or (value == lower and operator == ">"):
                lower, lower_closed = value, operator == ">="
        elif operator in {"<", "<="}:
            if upper is None or value < upper or (value == upper and operator == "<"):
                upper, upper_closed = value, operator == "<="
        else:
            if value > lower:
                lower, lower_closed = value, True
            if upper is None or value < upper:
                upper, upper_closed = value, True
    if upper is not None and (
        lower > upper
        or (lower == upper and (not lower_closed or not upper_closed or lower in excluded))
    ):
        return None
    return (
        lower >= (1, 0, 0)
        and upper is not None
        and (upper < (2, 0, 0) or (upper == (2, 0, 0) and not upper_closed))
    )


def _tokens(text: str) -> list[str]:
    result = []
    position = 0
    for match in _TOKENS.finditer(text):
        if text[position : match.start()].strip():
            raise ValueError("Unsupported HCL expression")
        token = match.group()
        if not token.isspace() and not token.startswith(("#", "//", "/*")):
            result.append(token)
        position = match.end()
    if text[position:].strip():
        raise ValueError("Unsupported HCL expression")
    return result


def _end(tokens: list[str], start: int) -> int:
    depth = 0
    for index in range(start, len(tokens)):
        if tokens[index] == "{":
            depth += 1
        elif tokens[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("Unclosed HCL block")


def _attributes(tokens: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    index = 0
    while index < len(tokens):
        if tokens[index] == ",":
            index += 1
            continue
        if index + 2 >= len(tokens) or tokens[index + 1] != "=":
            raise ValueError("Unsupported provider declaration")
        name, value = tokens[index], tokens[index + 2]
        if name.startswith('"'):
            name = json.loads(name)
        if value == "{":
            end = _end(tokens, index + 2)
            result[name] = _attributes(tokens[index + 3 : end])
            index = end + 1
        elif value.startswith('"'):
            result[name] = json.loads(value)
            index += 3
        elif value == "[":
            finish = index + 3
            depth = 1
            while finish < len(tokens) and depth:
                if tokens[finish] == "[":
                    depth += 1
                elif tokens[finish] == "]":
                    depth -= 1
                finish += 1
            if depth:
                raise ValueError("Unclosed provider attribute list")
            result[name] = tokens[index + 3 : finish - 1]
            index = finish
        else:
            raise ValueError("Provider requirement is not a literal")
    return result


def _requirements(text: str) -> list[dict[str, object]]:
    tokens = _tokens(text)
    result = []
    index = 0
    while index < len(tokens):
        if tokens[index] == "terraform" and tokens[index + 1 : index + 2] == ["{"]:
            end = _end(tokens, index + 1)
            child = index + 2
            while child < end:
                if tokens[child] == "required_providers":
                    start = child + 1
                    if tokens[start : start + 1] == ["="]:
                        start += 1
                    if tokens[start : start + 1] != ["{"]:
                        raise ValueError("Invalid required_providers block")
                    finish = _end(tokens, start)
                    result.append(_attributes(tokens[start + 1 : finish]))
                    child = finish + 1
                elif tokens[child] == "{":
                    child = _end(tokens, child) + 1
                else:
                    child += 1
            index = end + 1
        elif tokens[index] == "{":
            index = _end(tokens, index) + 1
        else:
            index += 1
    return result


def terraform_outcome(files: dict[str, str]) -> MetricOutcome:
    modules: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path, text in files.items():
        if path.endswith((".tf", ".tf.json")):
            modules[path.rsplit("/", 1)[0] if "/" in path else ""].append((path, text))
    if not modules:
        return not_applicable("No Terraform modules in the component.")
    outcomes: list[bool | None] = []
    for entries in modules.values():
        declarations: list[dict[str, object]] = []
        unreadable = False
        for path, text in entries:
            try:
                if path.endswith(".json"):
                    terraform = json.loads(text).get("terraform", {})
                    blocks = terraform if isinstance(terraform, list) else [terraform]
                    for block in blocks:
                        providers = block.get("required_providers", {})
                        declarations.extend(
                            providers if isinstance(providers, list) else [providers]
                        )
                else:
                    declarations.extend(_requirements(text))
            except (ValueError, TypeError, AttributeError, IndexError):
                outcomes.append(None)
                unreadable = True
        found = False
        for declaration in declarations:
            if not isinstance(declaration, dict):
                outcomes.append(None)
                continue
            for name, requirement in declaration.items():
                source = requirement.get("source", "") if isinstance(requirement, dict) else ""
                if name != "juju" and source not in {
                    "juju/juju",
                    "registry.terraform.io/juju/juju",
                }:
                    continue
                found = True
                if source not in {
                    "juju/juju",
                    "registry.terraform.io/juju/juju",
                }:
                    outcomes.append(False)
                    continue
                version = (
                    requirement.get("version") if isinstance(requirement, dict) else requirement
                )
                outcomes.append(False if version is None else major_one(version))
        if not found and not unreadable:
            outcomes.append(False)
    if False in outcomes:
        return measured(False)
    if None in outcomes:
        return insufficient_data("Cannot interpret all Terraform Juju provider requirements.")
    return measured(True)
