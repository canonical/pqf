import pytest

from engine.metric_outcomes import measured
from engine.models import Medal
from engine.rubric import eval_condition, evaluate_rubric

# --- Numeric comparisons ---


def test_gte_true():
    assert eval_condition({"coverage_pct": measured(90)}, "coverage_pct >= 90") is True


def test_gte_false():
    assert eval_condition({"coverage_pct": measured(89)}, "coverage_pct >= 90") is False


def test_gt_true():
    assert eval_condition({"coverage_pct": measured(91)}, "coverage_pct > 90") is True


def test_gt_boundary_false():
    assert eval_condition({"coverage_pct": measured(90)}, "coverage_pct > 90") is False


def test_lte_true():
    assert eval_condition({"avg_triage_days": measured(3)}, "avg_triage_days <= 5") is True


def test_lte_false():
    assert eval_condition({"avg_triage_days": measured(6)}, "avg_triage_days <= 5") is False


def test_lt_true():
    assert eval_condition({"avg_triage_days": measured(2)}, "avg_triage_days < 5") is True


def test_lt_boundary_false():
    assert eval_condition({"avg_triage_days": measured(5)}, "avg_triage_days < 5") is False


def test_eq_numeric():
    assert eval_condition({"diataxis_coverage": measured(4)}, "diataxis_coverage == 4") is True


def test_neq_numeric():
    assert eval_condition({"diataxis_coverage": measured(3)}, "diataxis_coverage != 4") is True


# --- Boolean comparisons ---


def test_bool_eq_true_passes():
    assert (
        eval_condition({"latest_build_passing": measured(True)}, "latest_build_passing == true")
        is True
    )


def test_bool_eq_true_fails_when_false():
    assert (
        eval_condition({"latest_build_passing": measured(False)}, "latest_build_passing == true")
        is False
    )


def test_bool_eq_false_passes():
    assert eval_condition({"has_readme": measured(False)}, "has_readme == false") is True


def test_bool_neq():
    assert eval_condition({"ssdlc_onboarded": measured(False)}, "ssdlc_onboarded != true") is True


# --- Missing key ---


def test_missing_key_returns_false():
    assert eval_condition({}, "coverage_pct >= 70") is False


def test_missing_key_bool_returns_false():
    assert eval_condition({}, "latest_build_passing == true") is False


# --- Invalid condition ---


def test_invalid_condition_raises_value_error():
    with pytest.raises(ValueError, match="Invalid condition"):
        eval_condition({}, "this is not valid")


def test_condition_with_extra_spaces_is_valid():
    assert eval_condition({"coverage_pct": measured(90)}, "  coverage_pct  >=  90  ") is True


# --- evaluate_rubric tests ---

# Rubric with explicit bronze, silver, and gold conditions
FULL_RUBRIC = {
    "bronze": ["coverage_pct >= 70", "latest_build_passing == true"],
    "silver": ["coverage_pct >= 80", "stability_pct >= 85", "latest_build_passing == true"],
    "gold": ["coverage_pct >= 90", "stability_pct >= 98", "latest_build_passing == true"],
}

# Rubric without explicit bronze (fallback behavior)
NO_BRONZE_RUBRIC = {
    "silver": ["supports_juju_3 == true"],
    "gold": ["supports_juju_4 == true", "supports_ck8s == true"],
}


def test_returns_gold_when_all_gold_conditions_met():
    metrics = {
        "coverage_pct": measured(95),
        "stability_pct": measured(99),
        "latest_build_passing": measured(True),
    }
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.GOLD


def test_returns_silver_when_gold_fails_but_silver_passes():
    metrics = {
        "coverage_pct": measured(85),
        "stability_pct": measured(90),
        "latest_build_passing": measured(True),
    }
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.SILVER


def test_returns_bronze_when_only_bronze_conditions_met():
    # coverage 75 passes bronze (>=70) but not silver (>=80)
    metrics = {"coverage_pct": measured(75), "latest_build_passing": measured(True)}
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.BRONZE


def test_returns_unrated_when_explicit_bronze_conditions_fail():
    # coverage 60 < 70 — fails bronze threshold
    metrics = {"coverage_pct": measured(60), "latest_build_passing": measured(True)}
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.UNRATED


def test_returns_unrated_when_build_failing_despite_good_coverage():
    metrics = {
        "coverage_pct": measured(95),
        "stability_pct": measured(99),
        "latest_build_passing": measured(False),
    }
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.UNRATED


def test_bronze_fallback_when_no_bronze_key_and_nothing_passes():
    # Fails silver and gold — but no explicit bronze → fallback to bronze
    metrics = {
        "supports_juju_3": measured(False),
        "supports_juju_4": measured(False),
        "supports_ck8s": measured(False),
    }
    assert evaluate_rubric(metrics, NO_BRONZE_RUBRIC) == Medal.BRONZE


def test_silver_when_no_bronze_key_and_silver_passes():
    metrics = {
        "supports_juju_3": measured(True),
        "supports_juju_4": measured(False),
        "supports_ck8s": measured(False),
    }
    assert evaluate_rubric(metrics, NO_BRONZE_RUBRIC) == Medal.SILVER


def test_gold_when_no_bronze_key_and_all_gold_pass():
    metrics = {
        "supports_juju_3": measured(True),
        "supports_juju_4": measured(True),
        "supports_ck8s": measured(True),
    }
    assert evaluate_rubric(metrics, NO_BRONZE_RUBRIC) == Medal.GOLD


def test_empty_metrics_with_explicit_bronze_returns_unrated():
    assert evaluate_rubric({}, FULL_RUBRIC) == Medal.UNRATED


def test_empty_metrics_with_no_bronze_key_returns_bronze():
    assert evaluate_rubric({}, NO_BRONZE_RUBRIC) == Medal.BRONZE
