from __future__ import annotations

import sys
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
