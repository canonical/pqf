"""Every Terraform module must explicitly require juju/juju >= 1.0.

Newer major versions are allowed. Missing/older requirements fail; unreadable
declarations are unknown. HCL syntax is parsed by python-hcl2, never by regex.
"""

import json
import re
from collections import defaultdict
from typing import Any

import hcl2
from lark.exceptions import LarkError
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from engine.metric_outcomes import (
    MetricOutcome,
    MetricState,
    insufficient_data,
    measured,
    not_applicable,
)

_JUJU_SOURCES = {"juju/juju", "registry.terraform.io/juju/juju"}
_CLAUSE = re.compile(r"(~>|>=|<=|!=|>|<|=)?\s*(\d+(?:\.\d+){0,2})")


def requires_provider_one_or_newer(constraint: str) -> bool:
    """Check the minimum of a nonempty numeric Terraform version range.

    packaging handles comparisons and exclusions. Translate Terraform's `=`
    and pessimistic `~>` operators into standard comparison specifiers first.
    Dynamic/unsupported constraints and empty ranges raise ValueError.
    """
    comparisons = []
    for clause in constraint.split(","):
        match = _CLAUSE.fullmatch(clause.strip())
        if not match:
            raise ValueError("Expected a literal numeric Terraform version constraint.")
        operator, number = match.groups()
        if operator == "~>":
            release = Version(number).release
            ceiling = (
                f"{release[0] + 1}.0" if len(release) < 3 else f"{release[0]}.{release[1] + 1}.0"
            )
            comparisons.extend((f">={number}", f"<{ceiling}"))
        else:
            comparisons.append(f"{'==' if operator in (None, '=') else operator}{number}")
    specifiers = SpecifierSet(",".join(comparisons))
    minimum = max(
        (Version(s.version) for s in specifiers if s.operator in {">", ">=", "=="}),
        default=Version("0"),
    )
    maximum = min(
        (Version(s.version) for s in specifiers if s.operator in {"<", "<=", "=="}),
        default=None,
    )
    if maximum is not None and (
        minimum > maximum or (minimum == maximum and minimum not in specifiers)
    ):
        raise ValueError("The provider version range is empty.")
    return minimum >= Version("1.0")


def _blocks(value: Any) -> list[dict[str, Any]]:
    blocks = value if isinstance(value, list) else [value]
    if not all(isinstance(block, dict) for block in blocks):
        raise ValueError("Expected Terraform blocks to be mappings.")
    return blocks


def _requirements(path: str, text: str) -> list[dict[str, Any]]:
    document = json.loads(text) if path.endswith(".json") else hcl2.loads(text)
    if not isinstance(document, dict):
        raise ValueError("Expected a Terraform document mapping.")
    return [
        providers
        for terraform in _blocks(document.get("terraform", []))
        for providers in _blocks(terraform.get("required_providers", []))
    ]


def _provider_outcome(path: str, name: str, requirement: Any) -> MetricOutcome | None:
    source = requirement.get("source") if isinstance(requirement, dict) else None
    if source is not None and (not isinstance(source, str) or "${" in source):
        return insufficient_data(f"{path}: provider {name!r} has a nonliteral source {source!r}.")
    if name != "juju" and source not in _JUJU_SOURCES:
        return None
    if source not in _JUJU_SOURCES:
        return MetricOutcome(
            MetricState.MEASURED,
            False,
            f"{path}: provider {name!r} has source {source!r}; expected juju/juju.",
        )
    constraint = requirement.get("version")
    if constraint is None:
        return MetricOutcome(
            MetricState.MEASURED,
            False,
            f"{path}: juju/juju has no version constraint; it must require at least 1.0.",
        )
    try:
        if not isinstance(constraint, str):
            raise ValueError("Expected a literal version constraint string.")
        if requires_provider_one_or_newer(constraint):
            return measured(True)
    except ValueError as exc:
        return insufficient_data(f"{path}: juju/juju constraint {constraint!r}: {exc}")
    return MetricOutcome(
        MetricState.MEASURED,
        False,
        f"{path}: juju/juju constraint {constraint!r} permits versions below 1.0.",
    )


def terraform_outcome(files: dict[str, str]) -> MetricOutcome:
    """Require every in-scope module, including test setup modules, to comply."""
    modules: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path, text in files.items():
        if path.endswith((".tf", ".tf.json")):
            directory = path.rsplit("/", 1)[0] if "/" in path else "."
            modules[directory].append((path, text))
    if not modules:
        return not_applicable("No Terraform modules in the component.")

    outcomes = []
    for directory, entries in sorted(modules.items()):
        module_outcomes = []
        for path, text in sorted(entries):
            try:
                declarations = _requirements(path, text)
            except (ValueError, LarkError) as exc:
                module_outcomes.append(insufficient_data(f"{path}: cannot parse Terraform: {exc}"))
                continue
            for declaration in declarations:
                for name, requirement in declaration.items():
                    outcome = _provider_outcome(path, name, requirement)
                    if outcome is not None:
                        module_outcomes.append(outcome)
        if not module_outcomes:
            module_outcomes.append(
                MetricOutcome(
                    MetricState.MEASURED,
                    False,
                    f"{directory}: no explicit juju/juju provider requirement; "
                    "expected at least 1.0.",
                )
            )
        outcomes.extend(module_outcomes)
    failures = [outcome.reason for outcome in outcomes if outcome.value is False]
    if failures:
        return MetricOutcome(MetricState.MEASURED, False, "\n".join(failures))
    unknowns = [
        outcome.reason for outcome in outcomes if outcome.state == MetricState.INSUFFICIENT_DATA
    ]
    if unknowns:
        return insufficient_data("\n".join(unknowns))
    return measured(True)
