import responses as resp_lib

from engine.models import EvaluationUnit, ProductType
from scorers.test_verification.logic import _uses_jubilant, _uses_ops_testing, compute_metrics

UNIT = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
    allure_report_url="https://canonical.github.io/synapse-operator/_latest",
)

UNIT_NO_ALLURE = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
    allure_report_url="",
)


def test_returns_zeros_when_no_allure_url():
    result = compute_metrics(UNIT_NO_ALLURE)
    assert result["coverage_pct"] == 0
    assert result["stability_pct"] == 0
    assert result["latest_build_passing"] is False


@resp_lib.activate
def test_coverage_from_allure_summary():
    resp_lib.add(
        resp_lib.GET,
        "https://canonical.github.io/synapse-operator/_latest/widgets/summary.json",
        json={"statistic": {"total": 100, "passed": 87, "failed": 0, "broken": 0}},
        status=200,
    )
    result = compute_metrics(UNIT)
    assert result["coverage_pct"] == 87
    assert result["latest_build_passing"] is True


@resp_lib.activate
def test_build_failing_when_failures_present():
    resp_lib.add(
        resp_lib.GET,
        "https://canonical.github.io/synapse-operator/_latest/widgets/summary.json",
        json={"statistic": {"total": 100, "passed": 90, "failed": 5, "broken": 5}},
        status=200,
    )
    result = compute_metrics(UNIT)
    assert result["latest_build_passing"] is False
    assert result["stability_pct"] == 90


def test_uses_ops_testing_true_when_no_harness(mocker):
    mocker.patch("scorers.test_verification.logic._search_code", return_value=0)
    assert _uses_ops_testing(["canonical/synapse-operator"], "token") is True


def test_uses_jubilant_true_when_jubilant_found(mocker):
    mocker.patch("scorers.test_verification.logic._search_code", return_value=1)
    assert _uses_jubilant(["canonical/synapse-operator"], "token") is True
