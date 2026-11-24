"""Repository-wide Juju provider bounds, excluding explicit non-Juju utilities.

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
_PROVIDER_SOURCE = re.compile(r"(?:[A-Za-z0-9.-]+(?::[0-9]+)?/)?[A-Za-z0-9_-]+/[A-Za-z0-9_-]+")


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


def _document(path: str, text: str) -> dict[str, Any]:
    document = json.loads(text) if path.endswith(".json") else hcl2.loads(text)
    if not isinstance(document, dict):
        raise ValueError("Expected a Terraform document mapping.")
    return document


def _explicitly_non_juju(documents: list[dict[str, Any]]) -> bool:
    providers = set()
    resource_types = set()
    for document in documents:
        if document.get("module"):
            return False
        for block in _blocks(document.get("provider", [])):
            if "juju" in block:
                return False
            resource_types.update(f"{name}_" for name in block)
        for kind in ("resource", "data"):
            for block in _blocks(document.get(kind, [])):
                if any(name.startswith("juju_") for name in block):
                    return False
                resource_types.update(block)
        for terraform in _blocks(document.get("terraform", [])):
            for requirements in _blocks(terraform.get("required_providers", [])):
                for name, requirement in requirements.items():
                    source = requirement.get("source") if isinstance(requirement, dict) else None
                    if (
                        name == "juju"
                        or not isinstance(source, str)
                        or source in _JUJU_SOURCES
                        or not _PROVIDER_SOURCE.fullmatch(source)
                    ):
                        return False
                    providers.add(name)
    return bool(providers) and all(
        any(kind.startswith(f"{name}_") for name in providers) for kind in resource_types
    )


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
    """Require every Juju or unclassified module in the source repository to comply."""
    modules: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path, text in files.items():
        if path.endswith((".tf", ".tf.json")):
            directory = path.rsplit("/", 1)[0] if "/" in path else "."
            modules[directory].append((path, text))
    if not modules:
        return not_applicable("No Terraform modules in the source repository.")

    outcomes = []
    for directory, entries in sorted(modules.items()):
        module_outcomes = []
        documents = []
        for path, text in sorted(entries):
            try:
                document = _document(path, text)
                declarations = [
                    providers
                    for terraform in _blocks(document.get("terraform", []))
                    for providers in _blocks(terraform.get("required_providers", []))
                ]
            except (ValueError, LarkError) as exc:
                module_outcomes.append(insufficient_data(f"{path}: cannot parse Terraform: {exc}"))
                continue
            documents.append(document)
            for declaration in declarations:
                for name, requirement in declaration.items():
                    outcome = _provider_outcome(path, name, requirement)
                    if outcome is not None:
                        module_outcomes.append(outcome)
        if len(documents) == len(entries):
            try:
                if _explicitly_non_juju(documents):
                    continue
            except ValueError as exc:
                module_outcomes.append(
                    insufficient_data(f"{directory}: cannot classify Terraform: {exc}")
                )
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
    if not outcomes:
        return not_applicable("No Juju or unclassified Terraform modules in the source repository.")
    return measured(True)
