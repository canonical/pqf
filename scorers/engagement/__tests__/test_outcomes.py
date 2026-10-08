from engine.metric_outcomes import MetricOutcome, MetricState
from engine.models import EvaluationUnit, ProductType
from scorers.engagement.logic import compute_metrics


def test_optional_missing_views_are_explicitly_unknown():
    outcomes = compute_metrics(EvaluationUnit("demo", ProductType.CHARM, ""), "token")
    assert all(isinstance(outcome, MetricOutcome) for outcome in outcomes.values())
    assert outcomes["repo_views_14d"].state == MetricState.INSUFFICIENT_DATA
