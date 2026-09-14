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


def test_returns_unmeasurable_when_no_allure_url_and_no_github_token():
    result = compute_metrics(UNIT_NO_ALLURE)
    assert result["coverage_pct"] is None
    assert result["stability_pct"] is None
    assert result["latest_build_passing"] is None


def test_latest_build_passing_falls_back_to_default_branch_checks_when_allure_missing(mocker):
    mocker.patch(
        "scorers.test_verification.logic.default_branch_check_runs",
        return_value=[
            {"name": "ci / test", "conclusion": "success", "completed_at": "2026-07-23T00:00:00Z"}
        ],
    )
    result = compute_metrics(UNIT_NO_ALLURE, "gh-token")
    assert result["latest_build_passing"] is True


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
    mocker.patch("scorers.test_verification.logic.search_code_count", return_value=0)
    assert _uses_ops_testing(["canonical/synapse-operator"], "token") is True


def test_uses_jubilant_true_when_jubilant_found(mocker):
    mocker.patch("scorers.test_verification.logic.search_code_count", return_value=1)
    assert _uses_jubilant(["canonical/synapse-operator"], "token") is True


def _allure_response(total, passed, failed, broken):
    class R:
        def __init__(self, total, passed, failed, broken):
            self._j = {
                "statistic": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "broken": broken,
                }
            }
            self.status_code = 200
            self.ok = True

        def json(self):
            return self._j

        def raise_for_status(self):
            return None

    return R(total, passed, failed, broken)


def test_compute_metrics_detects_integration_test_evidence(mocker):
    mocker.patch(
        "scorers.test_verification.logic.requests.get",
        return_value=_allure_response(10, 9, 1, 0),
    )
    mocker.patch(
        "scorers.test_verification.logic.workflow_files",
        return_value=[
            ("ci.yaml", "jobs:\n  integration:\n    steps:\n      - run: pytest -m integration\n"),
        ],
    )
    mocker.patch("scorers.test_verification.logic.search_code_count", side_effect=[0, 1])

    result = compute_metrics(UNIT, "gh-token")
    assert result["integration_test_evidence_present"] is True
    assert result["uses_ops_testing"] is True
    assert result["uses_jubilant"] is True


def test_compute_metrics_defaults_integration_evidence_to_false_without_workflow_match(mocker):
    mocker.patch(
        "scorers.test_verification.logic.requests.get",
        return_value=_allure_response(10, 10, 0, 0),
    )
    mocker.patch(
        "scorers.test_verification.logic.workflow_files",
        return_value=[("ci.yaml", "jobs:\n  unit:\n    steps:\n      - run: pytest\n")],
    )
    mocker.patch("scorers.test_verification.logic.search_code_count", side_effect=[0, 0])

    result = compute_metrics(UNIT, "gh-token")
    assert result["integration_test_evidence_present"] is False
