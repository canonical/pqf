# engine/__tests__/test_medal_engine.py
from engine.medal_engine import compute_leaf_product, compute_product
from engine.models import ApplicabilityOutcome, Medal, Status

# Minimal two-dimension config for testing (no applies_to → compute_product only)
_DIMENSIONS = {
    "dimensions": {
        "test_verification": {
            "medals": {
                "bronze": ["coverage_pct >= 70", "latest_build_passing == true"],
                "silver": ["coverage_pct >= 80"],
                "gold": ["coverage_pct >= 90"],
            }
        },
        "documentation": {
            "medals": {
                "bronze": ["has_readme == true"],
                "silver": ["diataxis_coverage >= 4"],
                "gold": ["style_linter_passing == true", "diataxis_coverage == 4"],
            }
        },
    }
}

# Dimensions with applies_to for compute_leaf_product tests
_DIMENSIONS_WITH_APPLICABILITY = {
    "dimensions": {
        "test_verification": {
            "applies_to": {"product_types": ["charm", "snap"]},
            "required_metrics_for_scoring": ["coverage_pct", "latest_build_passing"],
            "medals": {
                "bronze": ["coverage_pct >= 70", "latest_build_passing == true"],
                "silver": ["coverage_pct >= 80"],
                "gold": ["coverage_pct >= 90"],
            },
        },
        "documentation": {
            "applies_to": {"product_types": ["charm", "snap"]},
            "medals": {
                "bronze": ["has_readme == true"],
                "silver": ["diataxis_coverage >= 4"],
                "gold": ["style_linter_passing == true", "diataxis_coverage == 4"],
            },
        },
    }
}

_PRODUCT = {"id": "test-product", "target_medal": "gold"}


def test_current_medal_is_lowest_across_dimensions():
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": 95, "latest_build_passing": True},
            # documentation only meets bronze
            "documentation": {
                "has_readme": True,
                "diataxis_coverage": 2,
                "style_linter_passing": False,
            },
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    assert result.current_medal == Medal.BRONZE
    assert result.current_status == Status.BRONZE
    assert result.dimensions["test_verification"].medal == Medal.GOLD
    assert result.dimensions["test_verification"].status == Status.GOLD
    assert result.dimensions["documentation"].medal == Medal.BRONZE
    assert result.dimensions["documentation"].status == Status.BRONZE


def test_all_gold_dimensions_gives_gold_product():
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": 95, "latest_build_passing": True},
            "documentation": {
                "has_readme": True,
                "diataxis_coverage": 4,
                "style_linter_passing": True,
            },
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    assert result.current_medal == Medal.GOLD
    assert result.current_status == Status.GOLD


def test_all_silver_gives_silver_product():
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": 85, "latest_build_passing": True},
            "documentation": {
                "has_readme": True,
                "diataxis_coverage": 4,
                "style_linter_passing": False,
            },
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    assert result.current_medal == Medal.SILVER
    assert result.current_status == Status.SILVER


def test_missing_dimension_in_computed_treated_as_empty_metrics():
    # test_verification metrics missing entirely
    computed = {
        "metrics": {
            "documentation": {
                "has_readme": True,
                "diataxis_coverage": 4,
                "style_linter_passing": True,
            },
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    # test_verification gets empty metrics → bronze conditions fail → unrated
    assert result.dimensions["test_verification"].medal == Medal.UNRATED
    assert result.dimensions["test_verification"].status == Status.BELOW_MINIMUM
    assert result.current_medal == Medal.UNRATED
    assert result.current_status == Status.BELOW_MINIMUM


def test_compute_product_required_metric_none_keeps_dimension_unrated():
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": None, "latest_build_passing": True},
            "documentation": {
                "has_readme": True,
                "diataxis_coverage": 4,
                "style_linter_passing": True,
            },
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS_WITH_APPLICABILITY, {})
    assert result.dimensions["test_verification"].applicability == (
        ApplicabilityOutcome.INSUFFICIENT_DATA
    )
    assert result.dimensions["test_verification"].medal == Medal.UNRATED
    assert result.dimensions["test_verification"].status == Status.INSUFFICIENT_DATA
    assert result.current_medal == Medal.GOLD
    assert result.current_status == Status.GOLD


def test_entirely_empty_computed_gives_unrated():
    result = compute_product(_PRODUCT, {}, _DIMENSIONS, {})
    assert result.current_medal == Medal.UNRATED
    assert result.current_status == Status.BELOW_MINIMUM


def test_dimension_results_contain_target_medal():
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": 85, "latest_build_passing": True},
            "documentation": {"has_readme": True, "diataxis_coverage": 2},
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    for dim in result.dimensions.values():
        assert dim.target == Medal.GOLD


def test_product_id_and_target_medal_in_result():
    result = compute_product(_PRODUCT, {}, _DIMENSIONS, {})
    assert result.product_id == "test-product"
    assert result.target_medal == Medal.GOLD


def test_drift_is_none_for_dimension_when_no_history():
    # With empty drift_history, compute_dimension_drift returns None
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": 85, "latest_build_passing": True},
            "documentation": {"has_readme": True, "diataxis_coverage": 2},
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    # Documentation is bronze, target is gold → drifting, but no history entry yet → None
    assert result.dimensions["documentation"].drift is None


# --- compute_leaf_product tests ---


def test_leaf_product_all_gold():
    metrics = {
        "test_verification": {"coverage_pct": 95, "latest_build_passing": True},
        "documentation": {"has_readme": True, "diataxis_coverage": 4, "style_linter_passing": True},
    }
    result = compute_leaf_product("p", "charm", metrics, _DIMENSIONS_WITH_APPLICABILITY, {}, "gold")
    assert result.current_medal == Medal.GOLD
    assert result.current_status == Status.GOLD
    assert result.dimensions["test_verification"].applicability == ApplicabilityOutcome.SCORED
    assert result.dimensions["test_verification"].status == Status.GOLD


def test_leaf_product_not_applicable_for_wrong_type():
    metrics = {
        "test_verification": {"coverage_pct": 95, "latest_build_passing": True},
        "documentation": {"has_readme": True, "diataxis_coverage": 4, "style_linter_passing": True},
    }
    result = compute_leaf_product("p", "root", metrics, _DIMENSIONS_WITH_APPLICABILITY, {}, "gold")
    # "root" not in applies_to → all NOT_APPLICABLE → current_medal UNRATED
    assert result.current_medal == Medal.UNRATED
    assert result.current_status == Status.NOT_APPLICABLE
    for dim in result.dimensions.values():
        assert dim.applicability == ApplicabilityOutcome.NOT_APPLICABLE
        assert dim.status == Status.NOT_APPLICABLE


def test_leaf_product_insufficient_data_excluded_from_medal():
    # Only documentation has metrics; test_verification is empty → INSUFFICIENT_DATA
    metrics = {
        "documentation": {"has_readme": True, "diataxis_coverage": 4, "style_linter_passing": True},
    }
    result = compute_leaf_product("p", "charm", metrics, _DIMENSIONS_WITH_APPLICABILITY, {}, "gold")
    assert (
        result.dimensions["test_verification"].applicability
        == ApplicabilityOutcome.INSUFFICIENT_DATA
    )
    assert result.dimensions["test_verification"].medal == Medal.UNRATED
    assert result.dimensions["test_verification"].status == Status.INSUFFICIENT_DATA
    # Only scored dimension is documentation (gold) → current_medal is gold
    assert result.current_medal == Medal.GOLD
    assert result.current_status == Status.GOLD


def test_leaf_product_required_metric_none_returns_insufficient_data():
    metrics = {
        "test_verification": {"coverage_pct": None, "latest_build_passing": True},
        "documentation": {"has_readme": True, "diataxis_coverage": 4, "style_linter_passing": True},
    }
    result = compute_leaf_product("p", "charm", metrics, _DIMENSIONS_WITH_APPLICABILITY, {}, "gold")
    assert (
        result.dimensions["test_verification"].applicability
        == ApplicabilityOutcome.INSUFFICIENT_DATA
    )
    assert result.dimensions["test_verification"].status == Status.INSUFFICIENT_DATA
    assert result.dimensions["test_verification"].medal == Medal.UNRATED
    assert result.current_medal == Medal.GOLD


def test_leaf_product_required_metrics_present_scores_normally():
    metrics = {
        "test_verification": {"coverage_pct": 75, "latest_build_passing": True},
        "documentation": {"has_readme": True, "diataxis_coverage": 4, "style_linter_passing": True},
    }
    result = compute_leaf_product("p", "charm", metrics, _DIMENSIONS_WITH_APPLICABILITY, {}, "gold")
    assert result.dimensions["test_verification"].applicability == ApplicabilityOutcome.SCORED
    assert result.dimensions["test_verification"].medal == Medal.BRONZE
    assert result.current_medal == Medal.BRONZE


def test_leaf_product_id_and_target_medal():
    result = compute_leaf_product(
        "my-charm", "charm", {}, _DIMENSIONS_WITH_APPLICABILITY, {}, "silver"
    )
    assert result.product_id == "my-charm"
    assert result.target_medal == Medal.SILVER
