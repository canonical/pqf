import pytest

from engine.metric_outcomes import measured
from engine.models import EvaluationUnit, ProductType
from scorers import registry


def test_registry_rejects_scalar_runner_outputs(monkeypatch):
    monkeypatch.setattr(
        registry, "RUNNERS", {"test_verification": lambda unit, context: {"uses_jubilant": True}}
    )
    with pytest.raises(ValueError, match="MetricOutcome"):
        registry.run_dimension(
            EvaluationUnit("demo", ProductType.CHARM, "canonical/demo"),
            "test_verification",
            {
                "outputs": {
                    "uses_jubilant": {"implementation": "uses-jubilant/v1", "type": "boolean"}
                }
            },
            registry.ScorerContext("token"),
        )


def test_registry_validates_measured_value_against_contract(monkeypatch):
    monkeypatch.setattr(
        registry,
        "RUNNERS",
        {"test_verification": lambda unit, context: {"uses_jubilant": measured("wrong")}},
    )
    with pytest.raises(ValueError, match="boolean"):
        registry.run_dimension(
            EvaluationUnit("demo", ProductType.CHARM, "canonical/demo"),
            "test_verification",
            {
                "outputs": {
                    "uses_jubilant": {"implementation": "uses-jubilant/v1", "type": "boolean"}
                }
            },
            registry.ScorerContext("token"),
        )
