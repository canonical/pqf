import pytest

from engine.graph import build_graph, resolve_leaf_units
from engine.models import ProductType

ROOT_WITH_INLINE = {
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
            "allure_report_url": "https://canonical.github.io/synapse-operator/_latest",
        },
    ],
    "context_refs": [{"label": "PostgreSQL", "repo": "canonical/postgresql-k8s-operator"}],
}

STANDALONE_LEAF = {
    "id": "postgresql-k8s",
    "product_type": "charm",
    "name": "PostgreSQL K8s",
    "lifecycle": "stable",
    "target_medal": "gold",
    "ownership": {"squad": "data"},
    "source": {"repo": "canonical/postgresql-k8s-operator"},
}

ROOT_WITH_REF = {
    "id": "discourse",
    "product_type": "root",
    "name": "Discourse",
    "lifecycle": "stable",
    "target_medal": "silver",
    "ownership": {"squad": "americas"},
    "composed_of": [{"ref": "postgresql-k8s"}],
}


def test_inline_leaf_registered_in_graph():
    graph = build_graph([ROOT_WITH_INLINE])
    assert "synapse" in graph.nodes


def test_inline_leaf_is_not_portfolio_entry():
    graph = build_graph([ROOT_WITH_INLINE])
    assert graph.nodes["synapse"].is_portfolio_entry is False
    assert graph.nodes["synapse"].is_inline is True


def test_root_is_portfolio_entry():
    graph = build_graph([ROOT_WITH_INLINE])
    assert graph.nodes["matrix"].is_portfolio_entry is True


def test_inline_leaf_parent_is_root():
    graph = build_graph([ROOT_WITH_INLINE])
    assert graph.nodes["synapse"].parent_ids == ["matrix"]


def test_standalone_leaf_is_portfolio_entry():
    graph = build_graph([STANDALONE_LEAF])
    assert graph.nodes["postgresql-k8s"].is_portfolio_entry is True
    assert graph.nodes["postgresql-k8s"].is_inline is False


def test_ref_resolves_to_standalone():
    graph = build_graph([STANDALONE_LEAF, ROOT_WITH_REF])
    edge = graph.nodes["discourse"].composed_of[0]
    assert edge.product_id == "postgresql-k8s"
    assert "discourse" in graph.nodes["postgresql-k8s"].parent_ids


def test_missing_ref_raises():
    with pytest.raises(ValueError, match="ref 'postgresql-k8s'"):
        build_graph([ROOT_WITH_REF])


def test_duplicate_id_raises():
    dup = {**ROOT_WITH_INLINE, "name": "Duplicate"}
    with pytest.raises(ValueError, match="Duplicate product ID"):
        build_graph([ROOT_WITH_INLINE, dup])


def test_inline_id_collision_with_top_level_raises():
    # standalone leaf has same id as inline leaf in root
    conflict = {**STANDALONE_LEAF, "id": "synapse"}
    with pytest.raises(ValueError, match="Duplicate product ID"):
        build_graph([ROOT_WITH_INLINE, conflict])


def test_context_refs_attached_to_root():
    graph = build_graph([ROOT_WITH_INLINE])
    refs = graph.nodes["matrix"].context_refs
    assert len(refs) == 1
    assert refs[0].label == "PostgreSQL"
    assert refs[0].repo == "canonical/postgresql-k8s-operator"


def test_resolve_leaf_units_returns_only_leaves():
    graph = build_graph([ROOT_WITH_INLINE])
    units = resolve_leaf_units(graph)
    assert len(units) == 1
    assert units[0].product_id == "synapse"
    assert units[0].repo == "canonical/synapse-operator"
    assert units[0].product_type == ProductType.CHARM
    assert units[0].allure_report_url == "https://canonical.github.io/synapse-operator/_latest"


def test_resolve_leaf_units_root_not_included():
    graph = build_graph([ROOT_WITH_INLINE])
    unit_ids = [u.product_id for u in resolve_leaf_units(graph)]
    assert "matrix" not in unit_ids


def test_standalone_leaf_included_in_units():
    graph = build_graph([STANDALONE_LEAF])
    units = resolve_leaf_units(graph)
    assert any(u.product_id == "postgresql-k8s" for u in units)


def test_inline_missing_source_raises():
    bad_root = {
        **ROOT_WITH_INLINE,
        "composed_of": [{"id": "bad-charm", "product_type": "charm", "target_medal": "bronze"}],
    }
    with pytest.raises(ValueError, match="missing required 'source'"):
        build_graph([bad_root])

