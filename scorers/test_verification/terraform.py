"""Every Terraform module must bound juju/juju with >= A, < B, where A >= 1.0.

Newer major versions are allowed. Missing/noncanonical requirements fail; unreadable
declarations are unknown. HCL syntax is parsed by python-hcl2, never by regex.
"""

import json
import re
from collections import defaultdict
from typing import Any

import hcl2
from lark.exceptions import LarkError
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


def requires_explicit_provider_range(constraint: str) -> bool:
    """Require one >= lower and one < upper bound, with lower >= 1.0.

    Unreadable numeric constraints and empty intervals raise ValueError.
    """
    bounds = {}
    for clause in constraint.split(","):
        match = _CLAUSE.fullmatch(clause.strip())
        if not match:
            raise ValueError("Expected a literal numeric Terraform version constraint.")
        operator, number = match.groups()
        if operator not in {">=", "<"} or operator in bounds:
            return False
        bounds[operator] = Version(number)
    if set(bounds) != {">=", "<"}:
        return False
    lower, upper = bounds[">="], bounds["<"]
    if lower >= upper:
        raise ValueError("The provider version range is empty.")
    return lower >= Version("1.0")


def _blocks(value: Any) -> list[dict[str, Any]]:
    """Normalize block lists from HCL and single-block mappings from Terraform JSON."""
    blocks = value if isinstance(value, list) else [value]
    if not all(isinstance(block, dict) for block in blocks):
        raise ValueError("Expected Terraform blocks to be mappings.")
    return blocks


def _requirements(path: str, text: str) -> list[dict[str, Any]]:
    """Parse one Terraform file and extract its required_providers mappings.

    Each mapping associates local provider names with their source and version requirements.
    """
    document = json.loads(text) if path.endswith(".json") else hcl2.loads(text)
    if not isinstance(document, dict):
        raise ValueError("Expected a Terraform document mapping.")
    return [
        providers
        for terraform in _blocks(document.get("terraform", []))
        for providers in _blocks(terraform.get("required_providers", []))
    ]


def _provider_outcome(path: str, name: str, requirement: Any) -> MetricOutcome | None:
    """Check a Juju provider's source and version, including the path in failure reasons.

    Return None for declarations identified as unrelated providers.
    """
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
            f"{path}: juju/juju has no version constraint; expected >= A, < B with A >= 1.0.",
        )
    try:
        if not isinstance(constraint, str):
            raise ValueError("Expected a literal version constraint string.")
        if requires_explicit_provider_range(constraint):
            return measured(True)
    except ValueError as exc:
        return insufficient_data(f"{path}: juju/juju constraint {constraint!r}: {exc}")
    return MetricOutcome(
        MetricState.MEASURED,
        False,
        f"{path}: juju/juju constraint {constraint!r} must use >= A, < B with A >= 1.0.",
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
                    "expected >= A, < B with A >= 1.0.",
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
