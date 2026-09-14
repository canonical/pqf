from engine.models import MEDAL_RANK, DimensionResult, Medal, ProductResult, Result


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


def test_dimension_result_instantiation():
    dim = DimensionResult(
        medal=Medal.SILVER,
        target=Medal.GOLD,
        meets_target=False,
        result=Result.SILVER,
        metrics={"coverage_pct": 85},
    )
    assert dim.medal == Medal.SILVER
    assert dim.meets_target is False


def test_product_result_instantiation():
    result = ProductResult(
        product_id="matrix",
        current_medal=Medal.BRONZE,
        target_medal=Medal.GOLD,
        meets_target=False,
        current_result=Result.BRONZE,
        target_result=Result.GOLD,
        dimensions={},
    )
    assert result.product_id == "matrix"
    assert result.current_medal == Medal.BRONZE
    assert result.meets_target is False
