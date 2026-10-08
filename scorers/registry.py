from __future__ import annotations

import ast
import hashlib
import inspect
import json
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

from engine import metric_outcomes, models
from engine.metric_outcomes import MetricOutcome, parse_metric_outcome, serialize_metric_outcome
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
    juju4_track: str = "4/stable"
    juju_lts_track: str = "3.6/stable"


@dataclass(frozen=True)
class MetricBinding:
    dimension: str
    output_key: str
    runner_key: str


@dataclass(frozen=True)
class RunnerCacheKey:
    runner_key: str
    source_digest: str
    unit: EvaluationUnit
    context: ScorerContext


RunnerCache = dict[RunnerCacheKey, dict[str, MetricOutcome]]


def _run_v0_testing(unit: EvaluationUnit, context: ScorerContext) -> dict[str, MetricOutcome]:
    return test_verification_logic.compute_v0_metrics(
        unit,
        context.github_token,
        juju4_track=context.juju4_track,
        juju_lts_track=context.juju_lts_track,
    )


def _run_v0_documentation(unit: EvaluationUnit, context: ScorerContext) -> dict[str, MetricOutcome]:
    return documentation_logic.compute_v0_metrics(
        unit,
        context.github_token,
        context.openrouter_api_key,
        model=context.openrouter_model,
        docs_repo=unit.documentation_repo or None,
        docs_path=unit.documentation_path,
        has_user_facing_docs=unit.has_user_facing_documentation,
    )


def _run_v0_security(unit: EvaluationUnit, context: ScorerContext) -> dict[str, MetricOutcome]:
    return security_ssdlc_logic.compute_v0_metrics(unit, context.github_token)


def _run_test_verification(
    unit: EvaluationUnit, context: ScorerContext
) -> dict[str, MetricOutcome]:
    return test_verification_logic.compute_metrics(unit, github_token=context.github_token or None)


def _run_documentation(unit: EvaluationUnit, context: ScorerContext) -> dict[str, MetricOutcome]:
    return documentation_logic.compute_metrics(
        unit,
        context.github_token,
        context.openrouter_api_key,
        model=context.openrouter_model,
    )


def _run_substrate_compat(unit: EvaluationUnit, context: ScorerContext) -> dict[str, MetricOutcome]:
    return substrate_compat_logic.compute_metrics(unit, context.github_token)


def _run_security_ssdlc(unit: EvaluationUnit, context: ScorerContext) -> dict[str, MetricOutcome]:
    return security_ssdlc_logic.compute_metrics(unit, context.github_token)


def _run_engagement(unit: EvaluationUnit, context: ScorerContext) -> dict[str, MetricOutcome]:
    return engagement_logic.compute_metrics(unit, context.github_token)


RUNNERS = MappingProxyType(
    {
        "test_verification": _run_test_verification,
        "documentation": _run_documentation,
        "substrate_compat": _run_substrate_compat,
        "security_ssdlc": _run_security_ssdlc,
        "engagement": _run_engagement,
        "v0_testing": _run_v0_testing,
        "v0_documentation": _run_v0_documentation,
        "v0_security": _run_v0_security,
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
            Path(documentation_logic.__file__).resolve().parent
            / "prompts"
            / "diataxis_v0_check.md",
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

RUNNER_SOURCE_FILES = MappingProxyType(
    {
        **RUNNER_SOURCE_FILES,
        "v0_testing": (
            *RUNNER_SOURCE_FILES["test_verification"],
            *(
                Path(test_verification_logic.__file__).resolve().parent / name
                for name in ("evidence.py", "v0.py", "terraform.py")
            ),
        ),
        "v0_documentation": RUNNER_SOURCE_FILES["documentation"],
        "v0_security": (
            *RUNNER_SOURCE_FILES["security_ssdlc"],
            Path(security_ssdlc_logic.__file__).resolve().parent / "v0.py",
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

METRIC_BINDINGS = MappingProxyType(
    {
        **METRIC_BINDINGS,
        **{
            implementation: MetricBinding(dimension, output, runner)
            for dimension, runner, outputs in (
                (
                    "test_verification",
                    "v0_testing",
                    {
                        "uses_ops_testing": "uses-ops-testing/v1",
                        "uses_gh_runners_unit_testing": "uses-gh-runners-unit-testing/v1",
                        "uses_jubilant": "uses-jubilant/v2",
                        "uses_tf_v1_provider": "uses-tf-v1-provider/v1",
                        "uses_charm_ci": "uses-charm-ci/v1",
                        "supports_canonical_k8s": "supports-canonical-k8s/v1",
                        "supports_juju_4": "supports-juju-4/v2",
                        "supports_juju_lts": "supports-juju-lts/v1",
                    },
                ),
                (
                    "documentation",
                    "v0_documentation",
                    {
                        "readme_present": "readme-present/v2",
                        "contributing_present": "contributing-present/v2",
                        "has_security": "security-file-present/v2",
                        "uses_sphinx_stack": "uses-sphinx-stack/v1",
                        "diataxis_coverage_ai": "diataxis-coverage-ai/v2",
                    },
                ),
                (
                    "security_ssdlc",
                    "v0_security",
                    {
                        "renovate_enabled": "renovate-enabled/v2",
                        "branch_protection_required_checks": "branch-protection-required-checks/v2",
                        "signed_commits_required": "signed-commits-required/v2",
                    },
                ),
            )
            for output, implementation in outputs.items()
        },
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
    *,
    runner_cache: RunnerCache | None = None,
) -> dict[str, MetricOutcome]:
    context = replace(context, **dimension_config.get("parameters", {}))
    selected = _selected_bindings(dimension_config, dimension_name=dimension_name)
    runner_results: dict[str, dict[str, MetricOutcome]] = {}

    for _, binding in selected:
        if binding.runner_key in runner_results:
            continue
        cache_key = RunnerCacheKey(
            runner_key=binding.runner_key,
            source_digest=_runner_source_digest(binding.runner_key),
            unit=unit,
            context=context,
        )
        if runner_cache is not None and cache_key in runner_cache:
            outputs = runner_cache[cache_key]
        else:
            outputs = RUNNERS[binding.runner_key](unit, context)
            if runner_cache is not None:
                runner_cache[cache_key] = outputs
        runner_results[binding.runner_key] = outputs

    metrics: dict[str, MetricOutcome] = {}
    for implementation_id, binding in selected:
        outputs = runner_results[binding.runner_key]
        if binding.output_key not in outputs:
            raise ValueError(
                f"metric implementation {implementation_id!r} did not return expected output "
                f"{binding.output_key!r}"
            )
        outcome = outputs[binding.output_key]
        if not isinstance(outcome, MetricOutcome):
            raise ValueError(f"{implementation_id}: expected MetricOutcome.")
        metrics[binding.output_key] = parse_metric_outcome(
            serialize_metric_outcome(outcome),
            dimension_config["outputs"][binding.output_key],
            metric_key=binding.output_key,
        )

    return metrics


def _runner_source_digest(runner_key: str) -> str:
    digest = hashlib.sha256()
    for source_path in RUNNER_SOURCE_FILES[runner_key]:
        content = source_path.read_bytes()
        _update_digest(digest, "source", content)
    for shared_module in (metric_outcomes, models):
        _update_digest(digest, "result-contract", Path(shared_module.__file__).read_bytes())
    _update_digest(digest, "runner", _normalized_callable_source(RUNNERS[runner_key]))
    _update_digest(digest, "bindings", _runner_binding_metadata(runner_key))
    return digest.hexdigest()


def _update_digest(digest: Any, label: str, content: str | bytes) -> None:
    encoded = content.encode() if isinstance(content, str) else content
    for part in (label.encode(), encoded):
        digest.update(len(part).to_bytes(8, byteorder="big"))
        digest.update(part)


def _normalized_callable_source(runner: Callable[..., Any]) -> str:
    source = textwrap.dedent(inspect.getsource(runner))
    return ast.dump(ast.parse(source), annotate_fields=True, include_attributes=False)


def _binding_metadata(implementation_id: str, binding: MetricBinding) -> str:
    return json.dumps(
        {
            "dimension": binding.dimension,
            "implementation_id": implementation_id,
            "output_key": binding.output_key,
            "runner_key": binding.runner_key,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _runner_binding_metadata(runner_key: str) -> str:
    bindings = [
        _binding_metadata(implementation_id, binding)
        for implementation_id, binding in METRIC_BINDINGS.items()
        if binding.runner_key == runner_key
    ]
    return json.dumps(sorted(bindings), separators=(",", ":"))


def implementation_fingerprints(dimension_config: dict[str, Any]) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for implementation_id, binding in _selected_bindings(dimension_config):
        digest = hashlib.sha256()
        _update_digest(digest, "runner", _runner_source_digest(binding.runner_key))
        _update_digest(digest, "binding", _binding_metadata(implementation_id, binding))
        fingerprints[implementation_id] = digest.hexdigest()
    return fingerprints
