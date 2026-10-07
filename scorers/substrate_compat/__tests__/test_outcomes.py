from engine.metric_outcomes import MetricOutcome
from engine.models import EvaluationUnit, ProductType
from scorers.substrate_compat.logic import compute_metrics


def test_substrate_results_use_structured_contract():
    outcomes = compute_metrics(EvaluationUnit("demo", ProductType.CHARM, ""), "token")
    assert all(isinstance(outcome, MetricOutcome) for outcome in outcomes.values())
