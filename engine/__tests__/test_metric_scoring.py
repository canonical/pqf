from engine.aggregation import aggregate_root_dimension
from engine.medal_engine import compute_leaf_product
from engine.metric_outcomes import insufficient_data, measured, not_applicable
from engine.models import ApplicabilityOutcome, LeafDimensionResult, Medal, Result

CONFIG = {
    "dimensions": {
        "testing": {
            "applies_to": {"product_types": ["charm", "snap"]},
            "required_metrics_for_scoring": ["unit", "k8s"],
            "medals": {
                "bronze": ["unit == true"],
                "gold": ["unit == true", "k8s == true"],
            },
        }
    }
}


def test_machine_charm_skips_only_nonapplicable_requirement():
    result = compute_leaf_product(
        "machine",
        "charm",
        {"testing": {"unit": measured(True), "k8s": not_applicable("Machine charm.")}},
        CONFIG,
        "gold",
    )
    assert result.current_result == Result.GOLD
    assert result.meets_target


def test_entirely_nonapplicable_dimension_never_awards_gold():
    result = compute_leaf_product(
        "snap",
        "snap",
        {"testing": {key: not_applicable("Not a charm.") for key in ("unit", "k8s")}},
        CONFIG,
        "gold",
    )
    assert result.current_result == Result.NOT_APPLICABLE
    assert not result.meets_target


def test_required_unknown_is_not_failure_or_success():
    result = compute_leaf_product(
        "charm",
        "charm",
        {"testing": {"unit": measured(True), "k8s": insufficient_data("Unknown substrate.")}},
        CONFIG,
        "gold",
    )
    assert result.current_result == Result.INSUFFICIENT_DATA
    assert not result.meets_target


def test_root_does_not_hide_unknown_component():
    leaves = [
        LeafDimensionResult(
            "a", "canonical/a", Medal.GOLD, Result.GOLD, ApplicabilityOutcome.SCORED, {}
        ),
        LeafDimensionResult(
            "b",
            "canonical/b",
            Medal.UNRATED,
            Result.INSUFFICIENT_DATA,
            ApplicabilityOutcome.INSUFFICIENT_DATA,
            {},
        ),
    ]
    result = aggregate_root_dimension(leaves, CONFIG["dimensions"]["testing"], "gold")
    assert result.result == Result.INSUFFICIENT_DATA
    assert not result.meets_target


def test_string_adoption_criterion():
    result = compute_leaf_product(
        "charm",
        "charm",
        {"docs": {"stack": measured("1.2.3")}},
        {"dimensions": {"docs": {"medals": {"gold": ['stack != ""']}}}},
        "gold",
    )
    assert result.current_result == Result.GOLD


def test_absent_stack_does_not_pass_string_adoption():
    result = compute_leaf_product(
        "charm",
        "charm",
        {"docs": {"stack": measured("")}},
        {"dimensions": {"docs": {"medals": {"bronze": ['stack != ""']}}}},
        "gold",
    )
    assert result.current_result == Result.BELOW_MINIMUM


def test_numeric_threshold_is_not_truncated_to_integer():
    from engine.rubric import eval_condition

    assert not eval_condition({"count": measured(80)}, "count >= 80.5")


def test_root_with_only_excluded_components_is_not_applicable():
    leaf = LeafDimensionResult(
        product_id="optional",
        repo="canonical/demo",
        medal=Medal.GOLD,
        result=Result.GOLD,
        applicability=ApplicabilityOutcome.SCORED,
        metrics={},
        excluded_from_parent_medal=True,
    )
    assert aggregate_root_dimension([leaf], {}, "gold").result == Result.NOT_APPLICABLE
