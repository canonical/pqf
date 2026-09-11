from engine.badges import badge_state, generate_badge

_GOLD_PRODUCT = {
    "id": "matrix",
    "current_result": "gold",
    "dimensions": {
        "test_verification": {"meets_target": True},
        "documentation": {"meets_target": True},
    },
}

_BRONZE_PRODUCT = {
    "id": "indico",
    "current_result": "bronze",
    "dimensions": {
        "test_verification": {"meets_target": False},
        "documentation": {"meets_target": True},
    },
}

_INSUFFICIENT_DATA_PRODUCT = {
    "id": "indico",
    "current_result": "insufficient_data",
    "dimensions": {
        "test_verification": {"meets_target": False},
        "documentation": {"meets_target": True},
    },
}


def test_badge_state_uses_current_result():
    assert badge_state(_GOLD_PRODUCT) == "gold"


def test_badge_state_handles_bronze_result():
    assert badge_state(_BRONZE_PRODUCT) == "bronze"


def test_badge_state_handles_insufficient_data_result():
    assert badge_state(_INSUFFICIENT_DATA_PRODUCT) == "insufficient_data"


def test_generate_badge_returns_svg_string():
    svg = generate_badge(_GOLD_PRODUCT)
    assert svg.strip().startswith("<svg")
    assert "quality" in svg
    assert "gold" in svg
    assert "#FFB700" in svg


def test_generate_badge_uses_neutral_color_for_insufficient_data():
    svg = generate_badge(_INSUFFICIENT_DATA_PRODUCT)
    assert "insufficient_data" in svg
    assert "#9F9F9F" in svg
