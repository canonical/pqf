"""Repository-wide Juju provider bounds, independent of charm source subpaths."""

import json
import re
from collections import defaultdict

import hcl2
from lark.exceptions import LarkError

from engine.metric_outcomes import (
    MetricOutcome,
    MetricState,
    insufficient_data,
    measured,
    not_applicable,
)
from engine.models import EvaluationUnit, ProductType
from scorers.test_verification import evidence
from scorers.test_verification.terraform import _JUJU_SOURCES, _blocks, terraform_outcome

_PROVIDER_SOURCE = re.compile(r"(?:[A-Za-z0-9.-]+(?::[0-9]+)?/)?[A-Za-z0-9_-]+/[A-Za-z0-9_-]+")


def _explicitly_non_juju(documents: list[dict]) -> bool:
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


def repository_terraform_outcome(files: dict[str, str]) -> MetricOutcome:
    """Exclude only demonstrably non-Juju modules; validate everything else."""
    modules = defaultdict(dict)
    for path, text in files.items():
        if path.endswith((".tf", ".tf.json")):
            directory = path.rsplit("/", 1)[0] if "/" in path else "."
            modules[directory][path] = text
    outcomes = []
    for directory, module in sorted(modules.items()):
        try:
            documents = [
                json.loads(text) if path.endswith(".json") else hcl2.loads(text)
                for path, text in module.items()
            ]
            if not all(isinstance(document, dict) for document in documents):
                raise ValueError("Expected Terraform document mappings.")
            if _explicitly_non_juju(documents):
                continue
        except (ValueError, LarkError) as exc:
            outcome = terraform_outcome(module)
            if outcome.value is True:
                outcome = insufficient_data(f"{directory}: cannot classify Terraform: {exc}")
            outcomes.append(outcome)
        else:
            outcomes.append(terraform_outcome(module))
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


def compute_metrics(
    unit: EvaluationUnit, github_token: str | None = None
) -> dict[str, MetricOutcome]:
    if unit.product_type != ProductType.CHARM:
        outcome = not_applicable("This is not a charm.")
    else:
        try:
            files = evidence.acquire(unit, github_token, terraform_only=True)
        except evidence.UninterpretableRepository as exc:
            outcome = insufficient_data(str(exc))
        else:
            outcome = repository_terraform_outcome(files)
    return {"uses_tf_v1_provider": outcome}
