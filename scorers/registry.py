from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from engine.models import EvaluationUnit
from scorers.documentation import logic as documentation_logic
from scorers.engagement import logic as engagement_logic
from scorers.security_ssdlc import logic as security_ssdlc_logic
from scorers.shared import github_signals
from scorers.substrate_compat import logic as substrate_compat_logic
from scorers.test_verification import logic as test_verification_logic

DEFAULT_OPENROUTER_MODEL = "anthropic/claude-sonnet-4.5"


@dataclass(frozen=True)
class ScorerContext:
    github_token: str
    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL


@dataclass(frozen=True)
class MetricBinding:
    dimension: str
    output_key: str
    runner_key: str


def _run_test_verification(unit: EvaluationUnit, context: ScorerContext) -> dict[str, Any]:
    return test_verification_logic.compute_metrics(unit, github_token=context.github_token or None)


def _run_documentation(unit: EvaluationUnit, context: ScorerContext) -> dict[str, Any]:
    return documentation_logic.compute_metrics(
        unit,
        context.github_token,
        context.openrouter_api_key,
        model=context.openrouter_model,
    )


def _run_substrate_compat(unit: EvaluationUnit, context: ScorerContext) -> dict[str, Any]:
    return substrate_compat_logic.compute_metrics(unit, context.github_token)


def _run_security_ssdlc(unit: EvaluationUnit, context: ScorerContext) -> dict[str, Any]:
    return security_ssdlc_logic.compute_metrics(unit, context.github_token)


def _run_engagement(unit: EvaluationUnit, context: ScorerContext) -> dict[str, Any]:
    return engagement_logic.compute_metrics(unit, context.github_token)


RUNNERS = MappingProxyType(
    {
        "test_verification": _run_test_verification,
        "documentation": _run_documentation,
        "substrate_compat": _run_substrate_compat,
        "security_ssdlc": _run_security_ssdlc,
        "engagement": _run_engagement,
    }
)

RUNNER_SOURCE_FILES = MappingProxyType(
    {
        "test_verification": (
            Path(test_verification_logic.__file__).resolve(),
            Path(github_signals.__file__).resolve(),
        ),
        "documentation": (
            Path(documentation_logic.__file__).resolve(),
            Path(github_signals.__file__).resolve(),
            Path(documentation_logic.__file__).resolve().parent / "prompts" / "diataxis_check.md",
        ),
        "substrate_compat": (
            Path(substrate_compat_logic.__file__).resolve(),
            Path(github_signals.__file__).resolve(),
        ),
        "security_ssdlc": (
            Path(security_ssdlc_logic.__file__).resolve(),
            Path(github_signals.__file__).resolve(),
        ),
        "engagement": (
            Path(engagement_logic.__file__).resolve(),
            Path(github_signals.__file__).resolve(),
        ),
    }
)

METRIC_BINDINGS = MappingProxyType(
    {
        "latest-build-passing/v1": MetricBinding(
            dimension="test_verification",
            output_key="latest_build_passing",
            runner_key="test_verification",
        ),
        "integration-test-evidence-present/v1": MetricBinding(
            dimension="test_verification",
            output_key="integration_test_evidence_present",
            runner_key="test_verification",
        ),
        "uses-jubilant/v1": MetricBinding(
            dimension="test_verification",
            output_key="uses_jubilant",
            runner_key="test_verification",
        ),
        "coverage-pct/v1": MetricBinding(
            dimension="test_verification",
            output_key="coverage_pct",
            runner_key="test_verification",
        ),
        "stability-pct/v1": MetricBinding(
            dimension="test_verification",
            output_key="stability_pct",
            runner_key="test_verification",
        ),
        "readme-present/v1": MetricBinding(
            dimension="documentation",
            output_key="readme_present",
            runner_key="documentation",
        ),
        "contributing-present/v1": MetricBinding(
            dimension="documentation",
            output_key="contributing_present",
            runner_key="documentation",
        ),
        "security-file-present/v1": MetricBinding(
            dimension="documentation",
            output_key="has_security",
            runner_key="documentation",
        ),
        "release-notes-process-implemented/v1": MetricBinding(
            dimension="documentation",
            output_key="release_notes_process_implemented",
            runner_key="documentation",
        ),
        "documentation-workflow-status/v1": MetricBinding(
            dimension="documentation",
            output_key="documentation_workflows_passing",
            runner_key="documentation",
        ),
        "diataxis-coverage-ai/v1": MetricBinding(
            dimension="documentation",
            output_key="diataxis_coverage_ai",
            runner_key="documentation",
        ),
        "uses-rtd-hosting/v1": MetricBinding(
            dimension="documentation",
            output_key="uses_rtd_hosting",
            runner_key="documentation",
        ),
        "changelog-present/v1": MetricBinding(
            dimension="documentation",
            output_key="has_changelog",
            runner_key="documentation",
        ),
        "supports-juju-3/v1": MetricBinding(
            dimension="substrate_compat",
            output_key="supports_juju_3",
            runner_key="substrate_compat",
        ),
        "substrate-test-evidence-present/v1": MetricBinding(
            dimension="substrate_compat",
            output_key="substrate_test_evidence_present",
            runner_key="substrate_compat",
        ),
        "supports-juju-4/v1": MetricBinding(
            dimension="substrate_compat",
            output_key="supports_juju_4",
            runner_key="substrate_compat",
        ),
        "uses-canonical-k8s/v1": MetricBinding(
            dimension="substrate_compat",
            output_key="uses_canonical_k8s",
            runner_key="substrate_compat",
        ),
        "renovate-enabled/v1": MetricBinding(
            dimension="security_ssdlc",
            output_key="renovate_enabled",
            runner_key="security_ssdlc",
        ),
        "branch-protection-required-checks/v1": MetricBinding(
            dimension="security_ssdlc",
            output_key="branch_protection_required_checks",
            runner_key="security_ssdlc",
        ),
        "signed-commits-required/v1": MetricBinding(
            dimension="security_ssdlc",
            output_key="signed_commits_required",
            runner_key="security_ssdlc",
        ),
        "sast-workflow-present/v1": MetricBinding(
            dimension="security_ssdlc",
            output_key="sast_workflow_present",
            runner_key="security_ssdlc",
        ),
        "cve-process-evidence/v1": MetricBinding(
            dimension="security_ssdlc",
            output_key="cve_tracking_process_present",
            runner_key="security_ssdlc",
        ),
        "ownership-signal/v1": MetricBinding(
            dimension="engagement",
            output_key="ownership_signal",
            runner_key="engagement",
        ),
        "response-coverage-rate/v1": MetricBinding(
            dimension="engagement",
            output_key="response_coverage_rate",
            runner_key="engagement",
        ),
        "avg-triage-days/v1": MetricBinding(
            dimension="engagement",
            output_key="avg_triage_days",
            runner_key="engagement",
        ),
        "avg-pr-review-days/v1": MetricBinding(
            dimension="engagement",
            output_key="avg_pr_review_days",
            runner_key="engagement",
        ),
        "jira-sync-configured/v1": MetricBinding(
            dimension="engagement",
            output_key="has_jira_sync",
            runner_key="engagement",
        ),
        "repo-views-14d/v1": MetricBinding(
            dimension="engagement",
            output_key="repo_views_14d",
            runner_key="engagement",
        ),
    }
)


def _selected_bindings(
    dimension_config: dict[str, Any],
    *,
    dimension_name: str | None = None,
) -> list[tuple[str, MetricBinding]]:
    outputs = dimension_config.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Dimension config is missing an outputs mapping")

    selected: list[tuple[str, MetricBinding]] = []
    for output_key, output_config in outputs.items():
        implementation_id = output_config.get("implementation")
        binding = METRIC_BINDINGS.get(implementation_id)
        if binding is None:
            raise ValueError(
                f"unknown metric implementation {implementation_id!r} referenced by "
                f"output {output_key!r}"
            )
        if dimension_name is not None and binding.dimension != dimension_name:
            raise ValueError(
                f"metric implementation {implementation_id!r} belongs to dimension "
                f"{binding.dimension!r}, not {dimension_name!r}"
            )
        if binding.output_key != output_key:
            raise ValueError(
                f"metric implementation {implementation_id!r} resolves to output "
                f"{binding.output_key!r}, not {output_key!r}"
            )
        if binding.runner_key not in RUNNERS:
            raise ValueError(
                f"metric implementation {implementation_id!r} references unknown runner "
                f"{binding.runner_key!r}"
            )
        selected.append((implementation_id, binding))
    return selected


def run_dimension(
    unit: EvaluationUnit,
    dimension_name: str,
    dimension_config: dict[str, Any],
    context: ScorerContext,
) -> dict[str, Any]:
    selected = _selected_bindings(dimension_config, dimension_name=dimension_name)
    runner_results: dict[str, dict[str, Any]] = {}

    for _, binding in selected:
        if binding.runner_key in runner_results:
            continue
        runner_results[binding.runner_key] = RUNNERS[binding.runner_key](unit, context)

    metrics: dict[str, Any] = {}
    for implementation_id, binding in selected:
        outputs = runner_results[binding.runner_key]
        if binding.output_key not in outputs:
            raise ValueError(
                f"metric implementation {implementation_id!r} did not return expected output "
                f"{binding.output_key!r}"
            )
        metrics[binding.output_key] = outputs[binding.output_key]

    return metrics


def implementation_fingerprints(dimension_config: dict[str, Any]) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for implementation_id, binding in _selected_bindings(dimension_config):
        digest = hashlib.sha256()
        for source_path in RUNNER_SOURCE_FILES[binding.runner_key]:
            content = source_path.read_bytes()
            digest.update(len(content).to_bytes(8, byteorder="big"))
            digest.update(content)
        fingerprints[implementation_id] = digest.hexdigest()
    return fingerprints
