from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.framework import discover_frameworks, get_framework  # noqa: E402
from engine.models import EvaluationUnit, ProductType  # noqa: E402
from scorers import registry  # noqa: E402

FRAMEWORKS = discover_frameworks(REPO_ROOT / "framework" / "versions")
UNIT = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
)


def _dimension_config(version_id: str, dimension_name: str) -> dict:
    framework = get_framework(FRAMEWORKS, version_id)
    return framework.dimensions["dimensions"][dimension_name]


def test_run_dimension_executes_shared_runner_once_and_filters_selected_outputs(monkeypatch):
    calls: list[tuple[EvaluationUnit, registry.ScorerContext]] = []

    def fake_runner(unit: EvaluationUnit, context: registry.ScorerContext) -> dict[str, object]:
        calls.append((unit, context))
        return {
            "latest_build_passing": True,
            "uses_jubilant": False,
            "coverage_pct": 93,
        }

    monkeypatch.setattr(registry, "RUNNERS", {**registry.RUNNERS, "test_verification": fake_runner})
    context = registry.ScorerContext(github_token="token")
    config = {
        "outputs": {
            "latest_build_passing": {"implementation": "latest-build-passing/v1"},
            "uses_jubilant": {"implementation": "uses-jubilant/v1"},
        }
    }

    metrics = registry.run_dimension(UNIT, "test_verification", config, context)

    assert metrics == {
        "latest_build_passing": True,
        "uses_jubilant": False,
    }
    assert calls == [(UNIT, context)]


def test_run_dimension_reuses_cached_runner_across_contracts_and_filters_outputs(monkeypatch):
    calls: list[tuple[EvaluationUnit, registry.ScorerContext]] = []

    def fake_runner(unit: EvaluationUnit, context: registry.ScorerContext) -> dict[str, object]:
        calls.append((unit, context))
        return {
            "latest_build_passing": True,
            "integration_test_evidence_present": False,
            "uses_jubilant": False,
            "coverage_pct": 93,
            "stability_pct": 99,
        }

    monkeypatch.setattr(registry, "RUNNERS", {**registry.RUNNERS, "test_verification": fake_runner})
    context = registry.ScorerContext(github_token="token")
    runner_cache: registry.RunnerCache = {}

    v0_metrics = registry.run_dimension(
        UNIT,
        "test_verification",
        _dimension_config("v0", "test_verification"),
        context,
        runner_cache=runner_cache,
    )
    v1_metrics = registry.run_dimension(
        UNIT,
        "test_verification",
        _dimension_config("v1", "test_verification"),
        context,
        runner_cache=runner_cache,
    )

    assert len(calls) == 1
    assert "integration_test_evidence_present" not in v0_metrics
    assert v1_metrics["integration_test_evidence_present"] is False


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    [
        ("product_id", "different-product"),
        ("product_type", ProductType.SNAP),
        ("repo", "canonical/different-operator"),
        ("subpath", "operators/different"),
        ("allure_report_url", "https://example.test/allure"),
        ("documentation_url", "https://example.test/docs"),
        ("target_medal", "gold"),
    ],
)
def test_run_dimension_cache_separates_every_evaluation_unit_field(
    field_name, changed_value, monkeypatch
):
    calls = 0

    def fake_runner(unit: EvaluationUnit, context: registry.ScorerContext) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"latest_build_passing": True}

    monkeypatch.setattr(registry, "RUNNERS", {**registry.RUNNERS, "test_verification": fake_runner})
    config = {
        "outputs": {
            "latest_build_passing": {"implementation": "latest-build-passing/v1"},
        }
    }
    context = registry.ScorerContext(github_token="token")
    runner_cache: registry.RunnerCache = {}

    registry.run_dimension(UNIT, "test_verification", config, context, runner_cache=runner_cache)
    registry.run_dimension(
        replace(UNIT, **{field_name: changed_value}),
        "test_verification",
        config,
        context,
        runner_cache=runner_cache,
    )

    assert calls == 2


@pytest.mark.parametrize(
    "changed_context",
    [
        registry.ScorerContext(github_token="different-token"),
        registry.ScorerContext(github_token="token", openrouter_api_key="different-key"),
        registry.ScorerContext(github_token="token", openrouter_model="different-model"),
    ],
)
def test_run_dimension_cache_separates_every_context_field(changed_context, monkeypatch):
    calls = 0

    def fake_runner(unit: EvaluationUnit, context: registry.ScorerContext) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"latest_build_passing": True}

    monkeypatch.setattr(registry, "RUNNERS", {**registry.RUNNERS, "test_verification": fake_runner})
    config = {
        "outputs": {
            "latest_build_passing": {"implementation": "latest-build-passing/v1"},
        }
    }
    runner_cache: registry.RunnerCache = {}

    registry.run_dimension(
        UNIT,
        "test_verification",
        config,
        registry.ScorerContext(github_token="token"),
        runner_cache=runner_cache,
    )
    registry.run_dimension(
        UNIT,
        "test_verification",
        config,
        changed_context,
        runner_cache=runner_cache,
    )

    assert calls == 2


def test_run_dimension_cache_separates_runner_keys(monkeypatch):
    calls: list[str] = []

    def first_runner(unit: EvaluationUnit, context: registry.ScorerContext) -> dict[str, object]:
        calls.append("first")
        return {"latest_build_passing": True}

    def second_runner(unit: EvaluationUnit, context: registry.ScorerContext) -> dict[str, object]:
        calls.append("second")
        return {"latest_build_passing": False}

    monkeypatch.setattr(
        registry,
        "RUNNERS",
        {**registry.RUNNERS, "test_verification": first_runner, "alternate": second_runner},
    )
    monkeypatch.setattr(
        registry,
        "RUNNER_SOURCE_FILES",
        {
            **registry.RUNNER_SOURCE_FILES,
            "alternate": registry.RUNNER_SOURCE_FILES["test_verification"],
        },
    )
    monkeypatch.setattr(
        registry,
        "METRIC_BINDINGS",
        {
            **registry.METRIC_BINDINGS,
            "latest-build-passing/alternate": registry.MetricBinding(
                dimension="test_verification",
                output_key="latest_build_passing",
                runner_key="alternate",
            ),
        },
    )
    runner_cache: registry.RunnerCache = {}

    first = registry.run_dimension(
        UNIT,
        "test_verification",
        {"outputs": {"latest_build_passing": {"implementation": "latest-build-passing/v1"}}},
        registry.ScorerContext(github_token="token"),
        runner_cache=runner_cache,
    )
    second = registry.run_dimension(
        UNIT,
        "test_verification",
        {"outputs": {"latest_build_passing": {"implementation": "latest-build-passing/alternate"}}},
        registry.ScorerContext(github_token="token"),
        runner_cache=runner_cache,
    )

    assert first == {"latest_build_passing": True}
    assert second == {"latest_build_passing": False}
    assert calls == ["first", "second"]


def test_run_dimension_cache_separates_changes_to_each_registered_source(tmp_path, monkeypatch):
    source_paths = tuple(tmp_path / name for name in ("logic.py", "helper.py", "prompt.md"))
    for source_path in source_paths:
        source_path.write_text("version-1")
    monkeypatch.setattr(
        registry,
        "RUNNER_SOURCE_FILES",
        {**registry.RUNNER_SOURCE_FILES, "test_verification": source_paths},
    )
    calls = 0

    def fake_runner(unit: EvaluationUnit, context: registry.ScorerContext) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"latest_build_passing": True}

    monkeypatch.setattr(registry, "RUNNERS", {**registry.RUNNERS, "test_verification": fake_runner})
    config = {
        "outputs": {
            "latest_build_passing": {"implementation": "latest-build-passing/v1"},
        }
    }
    context = registry.ScorerContext(github_token="token")

    for changed_source in source_paths:
        runner_cache: registry.RunnerCache = {}
        registry.run_dimension(
            UNIT, "test_verification", config, context, runner_cache=runner_cache
        )
        changed_source.write_text("version-2")
        registry.run_dimension(
            UNIT, "test_verification", config, context, runner_cache=runner_cache
        )
        changed_source.write_text("version-1")

    assert calls == 2 * len(source_paths)


def test_run_dimension_rejects_unknown_implementation_id():
    with pytest.raises(ValueError, match="unknown metric implementation"):
        registry.run_dimension(
            UNIT,
            "test_verification",
            {"outputs": {"latest_build_passing": {"implementation": "missing/v1"}}},
            registry.ScorerContext(github_token="token"),
        )


def test_run_dimension_rejects_wrong_dimension_binding():
    with pytest.raises(ValueError, match="belongs to dimension 'test_verification'"):
        registry.run_dimension(
            UNIT,
            "documentation",
            {"outputs": {"readme_present": {"implementation": "latest-build-passing/v1"}}},
            registry.ScorerContext(github_token="token"),
        )


def test_run_dimension_rejects_missing_output_from_runner(monkeypatch):
    def fake_runner(unit: EvaluationUnit, context: registry.ScorerContext) -> dict[str, object]:
        return {"latest_build_passing": True}

    monkeypatch.setattr(registry, "RUNNERS", {**registry.RUNNERS, "test_verification": fake_runner})

    with pytest.raises(ValueError, match="did not return expected output 'uses_jubilant'"):
        registry.run_dimension(
            UNIT,
            "test_verification",
            {
                "outputs": {
                    "latest_build_passing": {"implementation": "latest-build-passing/v1"},
                    "uses_jubilant": {"implementation": "uses-jubilant/v1"},
                }
            },
            registry.ScorerContext(github_token="token"),
        )


def test_implementation_fingerprints_hash_complete_runner_sources(tmp_path, monkeypatch):
    logic = tmp_path / "logic.py"
    helper = tmp_path / "helper.py"
    prompt = tmp_path / "prompt.md"
    logic.write_text("logic-v1")
    helper.write_text("helper-v1")
    prompt.write_text("prompt-v1")
    monkeypatch.setattr(
        registry,
        "RUNNER_SOURCE_FILES",
        {**registry.RUNNER_SOURCE_FILES, "test_verification": (logic, helper, prompt)},
    )

    fingerprints = registry.implementation_fingerprints(
        {
            "outputs": {
                "latest_build_passing": {"implementation": "latest-build-passing/v1"},
                "uses_jubilant": {"implementation": "uses-jubilant/v1"},
            }
        }
    )

    assert set(fingerprints) == {
        "latest-build-passing/v1",
        "uses-jubilant/v1",
    }
    assert len(fingerprints["latest-build-passing/v1"]) == 64
    assert fingerprints["latest-build-passing/v1"] == fingerprints["uses-jubilant/v1"]

    initial = fingerprints["latest-build-passing/v1"]
    helper.write_text("helper-v2")
    helper_changed = registry.implementation_fingerprints(
        {
            "outputs": {
                "latest_build_passing": {"implementation": "latest-build-passing/v1"},
            }
        }
    )
    assert helper_changed["latest-build-passing/v1"] != initial

    helper.write_text("helper-v1")
    prompt.write_text("prompt-v2")
    prompt_changed = registry.implementation_fingerprints(
        {
            "outputs": {
                "latest_build_passing": {"implementation": "latest-build-passing/v1"},
            }
        }
    )
    assert prompt_changed["latest-build-passing/v1"] != initial


@pytest.mark.parametrize("framework_id", ["v0", "v1"])
def test_repo_framework_output_implementations_all_resolve(framework_id):
    framework = get_framework(FRAMEWORKS, framework_id)

    for dimension_config in framework.dimensions["dimensions"].values():
        implementations = {
            output["implementation"] for output in dimension_config["outputs"].values()
        }
        assert set(registry.implementation_fingerprints(dimension_config)) == implementations
