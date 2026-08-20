from engine.models import MEDAL_RANK, DimensionResult, DriftState, Medal, ProductResult, Status


def test_medal_values_are_lowercase_strings():
    assert Medal.UNRATED == "unrated"
    assert Medal.BRONZE == "bronze"
    assert Medal.SILVER == "silver"
    assert Medal.GOLD == "gold"


def test_medal_rank_ordering():
    assert MEDAL_RANK[Medal.UNRATED] < MEDAL_RANK[Medal.BRONZE]
    assert MEDAL_RANK[Medal.BRONZE] < MEDAL_RANK[Medal.SILVER]
    assert MEDAL_RANK[Medal.SILVER] < MEDAL_RANK[Medal.GOLD]


def test_medal_comparable_via_rank():
    medals = [Medal.GOLD, Medal.BRONZE, Medal.SILVER, Medal.UNRATED]
    assert min(medals, key=lambda m: MEDAL_RANK[m]) == Medal.UNRATED


def test_drift_state_instantiation():
    drift = DriftState(
        status="remediating",
        first_seen_at="2026-06-01T00:00:00+00:00",
        deadline="2026-12-01T00:00:00+00:00",
    )
    assert drift.status == "remediating"
    assert drift.first_seen_at == "2026-06-01T00:00:00+00:00"
    assert drift.deadline == "2026-12-01T00:00:00+00:00"


def test_dimension_result_instantiation():
    dim = DimensionResult(
        medal=Medal.SILVER,
        target=Medal.GOLD,
        status=Status.SILVER,
        metrics={"coverage_pct": 85},
        drift=None,
    )
    assert dim.medal == Medal.SILVER
    assert dim.drift is None


def test_product_result_instantiation():
    result = ProductResult(
        product_id="matrix",
        current_medal=Medal.BRONZE,
        target_medal=Medal.GOLD,
        current_status=Status.BRONZE,
        dimensions={},
    )
    assert result.product_id == "matrix"
    assert result.current_medal == Medal.BRONZE
