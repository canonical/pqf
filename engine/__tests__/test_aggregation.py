from engine.aggregation import aggregate_root_dimension, compute_leaf_applicability
from engine.graph import build_graph
from engine.medal_engine import compute_leaf_product, compute_root_product
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

DIM_NO_APPLIES_TO = {
    "aggregation": "worst_in_scope",
    "medals": {"bronze": ["some_metric == true"]},
}

DIM_WITH_REQUIRED_METRICS = {
    "applies_to": {"product_types": ["charm"]},
    "aggregation": "worst_in_scope",
    "required_metrics_for_scoring": ["coverage_pct", "latest_build_passing"],
    "medals": {"bronze": ["coverage_pct >= 70", "latest_build_passing == true"]},
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


def test_leaf_applicability_insufficient_data_when_required_metric_is_none():
    outcome = compute_leaf_applicability(
        "charm",
        {"coverage_pct": None, "latest_build_passing": True},
        DIM_WITH_REQUIRED_METRICS,
    )
    assert outcome == ApplicabilityOutcome.INSUFFICIENT_DATA


def test_leaf_applicability_scored_when_applicable_with_metrics():
    outcome = compute_leaf_applicability("charm", {"some_metric": True}, DIM_ROOT_EXCLUDED)
    assert outcome == ApplicabilityOutcome.SCORED


def test_leaf_applicability_scored_when_required_metrics_are_present():
    outcome = compute_leaf_applicability(
        "charm",
        {"coverage_pct": 75, "latest_build_passing": True},
        DIM_WITH_REQUIRED_METRICS,
    )
    assert outcome == ApplicabilityOutcome.SCORED


def test_leaf_applicability_no_applies_to_defaults_to_applicable():
    outcome = compute_leaf_applicability("charm", {"some_metric": True}, DIM_NO_APPLIES_TO)
    assert outcome == ApplicabilityOutcome.SCORED


ROOT_GRAPH_DICT = {
    "id": "matrix",
    "product_type": "root",
    "name": "Matrix",
    "lifecycle": "stable",
    "target_medal": "gold",
    "ownership": {"squad": "americas"},
    "composed_of": [
        {
            "id": "synapse",
            "product_type": "charm",
            "source": {"repo": "canonical/synapse-operator"},
            "target_medal": "gold",
        }
    ],
}

LEAF_METRICS = {"test_verification": {"coverage_pct": 75}}

DIMS_WITH_APPLICABILITY = {
    "dimensions": {
        "test_verification": {
            "applies_to": {"product_types": ["charm", "snap"]},
            "aggregation": "worst_in_scope",
            "medals": {
                "silver": ["coverage_pct >= 80"],
                "bronze": ["coverage_pct >= 70"],
            },
        }
    }
}


def test_compute_root_product_aggregates_leaf():
    graph = build_graph([ROOT_GRAPH_DICT])
    leaf_result = compute_leaf_product(
        "synapse", "charm", LEAF_METRICS, DIMS_WITH_APPLICABILITY, {}, "gold"
    )
    result = compute_root_product(
        "matrix", graph, {"synapse": leaf_result}, DIMS_WITH_APPLICABILITY, {}, "gold"
    )
    assert result.product_id == "matrix"
    assert result.dimensions["test_verification"].medal.value == "bronze"
    assert result.dimensions["test_verification"].composition is not None
    assert len(result.dimensions["test_verification"].composition) == 1


def test_compute_root_product_missing_leaf_skipped():
    graph = build_graph([ROOT_GRAPH_DICT])
    result = compute_root_product("matrix", graph, {}, DIMS_WITH_APPLICABILITY, {}, "gold")
    assert result.dimensions["test_verification"].medal.value == "unrated"


def test_compute_root_product_excluded_leaf_not_counted():
    excluded_dict = {
        **ROOT_GRAPH_DICT,
        "composed_of": [
            {
                **ROOT_GRAPH_DICT["composed_of"][0],
                "excluded_from_parent_medal": True,
            }
        ],
    }
    graph = build_graph([excluded_dict])
    leaf_result = compute_leaf_product(
        "synapse", "charm", LEAF_METRICS, DIMS_WITH_APPLICABILITY, {}, "gold"
    )
    result = compute_root_product(
        "matrix", graph, {"synapse": leaf_result}, DIMS_WITH_APPLICABILITY, {}, "gold"
    )
    assert result.dimensions["test_verification"].medal.value == "unrated"
