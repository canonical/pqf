import json

import pytest

from engine.assemble import assemble_portfolio

DIMS_CONFIG = {
    "dimensions": {
        "test_verification": {
            "label": "Test Verification",
            "description": "...",
            "scorer": "scorers/test_verification/scorer.py",
            "applies_to": {"product_types": ["charm", "snap"]},
            "aggregation": "worst_in_scope",
            "outputs": {
                "coverage_pct": {
                    "type": "number",
                    "label": "Coverage",
                    "description": "...",
                    "range": "0-100",
                }
            },
            "medals": {
                "silver": ["coverage_pct >= 80"],
                "bronze": ["coverage_pct >= 70"],
            },
        }
    }
}

ROOT_YAML = """\
id: matrix
product_type: root
name: Matrix
lifecycle: stable
target_medal: gold
ownership:
  squad: americas
composed_of:
  - id: synapse
    product_type: charm
    source:
      repo: canonical/synapse-operator
context_refs:
  - label: PostgreSQL
    repo: canonical/postgresql-k8s-operator
"""

COMPUTED_JSON = {
    "product_id": "matrix",
    "computed_at": "2026-01-01T00:00:00+00:00",
    "leaf_metrics": {"synapse": {"test_verification": {"coverage_pct": 75}}},
}


@pytest.fixture
def portfolio(tmp_path):
    (tmp_path / "products").mkdir()
    (tmp_path / "products" / "matrix.yaml").write_text(ROOT_YAML)
    (tmp_path / "computed").mkdir()
    (tmp_path / "computed" / "matrix.json").write_text(json.dumps(COMPUTED_JSON))
    return assemble_portfolio(
        products_dir=tmp_path / "products",
        computed_dir=tmp_path / "computed",
        dimensions_config=DIMS_CONFIG,
        drift_history={},
        update_drift=False,
    )


def test_portfolio_contains_root_product(portfolio):
    ids = [p["id"] for p in portfolio["products"]]
    assert "matrix" in ids


def test_root_product_has_correct_type(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    assert matrix["product_type"] == "root"
    assert matrix["is_portfolio_entry"] is True


def test_inline_leaf_included_in_products_but_not_portfolio_entry(portfolio):
    """Inline leaves are included so their detail page is accessible, but not portfolio entries."""
    ids = [p["id"] for p in portfolio["products"]]
    assert "synapse" in ids
    synapse = next(p for p in portfolio["products"] if p["id"] == "synapse")
    assert synapse["is_portfolio_entry"] is False


def test_root_dimension_has_composition(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    dim = matrix["dimensions"]["test_verification"]
    assert dim["result"] == "bronze"
    assert dim["composition"] is not None
    assert len(dim["composition"]) == 1
    assert dim["composition"][0]["product_id"] == "synapse"
    assert dim["composition"][0]["result"] == "bronze"  # 75 >= 70


def test_root_product_has_current_status(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    assert matrix["current_result"] == "bronze"


def test_context_refs_in_portfolio(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    assert len(matrix["context_refs"]) == 1
    assert matrix["context_refs"][0]["label"] == "PostgreSQL"


def test_dimensions_meta_has_applies_to(portfolio):
    meta = portfolio["dimensions_meta"]["test_verification"]
    assert "charm" in meta["applies_to"]
    assert meta["aggregation"] == "worst_in_scope"


def test_migrate_legacy_dimension_keys_support_engagement_to_engagement():
    """Drift history with support_engagement key is migrated to engagement."""
    from engine.assemble import _migrate_legacy_dimension_keys

    drift_history = {
        "product1": {
            "support_engagement": {
                "status": "remediating",
                "first_seen_at": "2026-06-01T00:00:00+00:00",
                "deadline": "2026-06-15T00:00:00+00:00",
            },
            "test_verification": {"status": "resolved"},
        },
        "product2": {
            "support_engagement": {"status": "resolved"},
        },
    }

    _migrate_legacy_dimension_keys(drift_history)

    # Old keys should be gone
    assert "support_engagement" not in drift_history["product1"]
    assert "support_engagement" not in drift_history["product2"]

    # New keys should exist with same data
    assert drift_history["product1"]["engagement"]["status"] == "remediating"
    assert drift_history["product1"]["engagement"]["first_seen_at"] == "2026-06-01T00:00:00+00:00"
    assert drift_history["product1"]["engagement"]["deadline"] == "2026-06-15T00:00:00+00:00"
    assert drift_history["product2"]["engagement"]["status"] == "resolved"

    # Other dimensions should be untouched
    assert drift_history["product1"]["test_verification"]["status"] == "resolved"


def test_migrate_legacy_dimension_keys_no_op_if_no_legacy_keys():
    """Migration is a no-op if no legacy keys are present."""
    from engine.assemble import _migrate_legacy_dimension_keys

    drift_history = {
        "product1": {
            "engagement": {"status": "resolved"},
            "test_verification": {"status": "resolved"},
        }
    }
    original = json.loads(json.dumps(drift_history))  # deep copy

    _migrate_legacy_dimension_keys(drift_history)

    assert drift_history == original


def test_migrate_legacy_dimension_keys_handles_empty_drift_history():
    """Migration handles empty drift history gracefully."""
    from engine.assemble import _migrate_legacy_dimension_keys

    drift_history = {}

    _migrate_legacy_dimension_keys(drift_history)

    assert drift_history == {}
