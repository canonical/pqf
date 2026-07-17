from engine.aggregation import aggregate_root_dimension, compute_leaf_applicability
from engine.models import ApplicabilityOutcome, LeafDimensionResult, Medal

DIM_CHARM_ONLY = {
    "applies_to": {"product_types": ["charm", "snap"]},
    "aggregation": "worst_in_scope",
    "medals": {"silver": ["coverage_pct >= 80"], "bronze": ["coverage_pct >= 70"]},
}

DIM_ROOT_EXCLUDED = {
    "applies_to": {"product_types": ["charm"]},
    "aggregation": "worst_in_scope",
    "medals": {"bronze": ["some_metric == true"]},
}


def _leaf(product_id, medal, applicability=ApplicabilityOutcome.SCORED, excluded=False):
    return LeafDimensionResult(
        product_id, f"canonical/{product_id}", medal, applicability, {}, excluded
    )


def test_worst_in_scope_picks_minimum():
    leaves = [_leaf("a", Medal.GOLD), _leaf("b", Medal.BRONZE)]
    result = aggregate_root_dimension(leaves, DIM_CHARM_ONLY, {}, "root", "gold", None)
    assert result.medal == Medal.BRONZE
    assert result.applicability == ApplicabilityOutcome.SCORED


def test_excluded_leaf_does_not_affect_roll_up():
    leaves = [_leaf("a", Medal.SILVER), _leaf("b", Medal.BRONZE, excluded=True)]
    result = aggregate_root_dimension(leaves, DIM_CHARM_ONLY, {}, "root", "gold", None)
    assert result.medal == Medal.SILVER


def test_not_applicable_leaf_excluded_from_roll_up():
    leaves = [
        _leaf("a", Medal.GOLD),
        _leaf("b", Medal.UNRATED, ApplicabilityOutcome.NOT_APPLICABLE),
    ]
    result = aggregate_root_dimension(leaves, DIM_CHARM_ONLY, {}, "root", "gold", None)
    assert result.medal == Medal.GOLD


def test_all_not_applicable_returns_unrated_and_not_applicable():
    leaves = [_leaf("a", Medal.UNRATED, ApplicabilityOutcome.NOT_APPLICABLE)]
    result = aggregate_root_dimension(leaves, DIM_CHARM_ONLY, {}, "root", "gold", None)
    assert result.medal == Medal.UNRATED
    assert result.applicability == ApplicabilityOutcome.NOT_APPLICABLE


def test_empty_leaf_list_returns_unrated():
    result = aggregate_root_dimension([], DIM_CHARM_ONLY, {}, "root", "gold", None)
    assert result.medal == Medal.UNRATED


def test_composition_included_in_result():
    leaves = [_leaf("a", Medal.GOLD), _leaf("b", Medal.SILVER)]
    result = aggregate_root_dimension(leaves, DIM_CHARM_ONLY, {}, "root", "gold", None)
    assert result.composition is not None
    assert len(result.composition) == 2


def test_leaf_applicability_not_applicable_for_wrong_type():
    outcome = compute_leaf_applicability("root", {"some_metric": True}, DIM_ROOT_EXCLUDED)
    assert outcome == ApplicabilityOutcome.NOT_APPLICABLE


def test_leaf_applicability_insufficient_data_when_no_metrics():
    outcome = compute_leaf_applicability("charm", {}, DIM_ROOT_EXCLUDED)
    assert outcome == ApplicabilityOutcome.INSUFFICIENT_DATA


def test_leaf_applicability_scored_when_applicable_with_metrics():
    outcome = compute_leaf_applicability("charm", {"some_metric": True}, DIM_ROOT_EXCLUDED)
    assert outcome == ApplicabilityOutcome.SCORED
