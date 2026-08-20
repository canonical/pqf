import pytest

from engine.graph import build_graph, resolve_leaf_units, resolve_leaf_units_for
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
        "composed_of": [{"id": "bad-charm", "product_type": "charm"}],
    }
    with pytest.raises(ValueError, match="missing required 'source'"):
        build_graph([bad_root])


def test_resolve_leaf_units_for_returns_only_leaves_of_root():
    # discourse uses ref: to postgresql-k8s (shared leaf)
    # resolve_leaf_units_for should return only postgresql-k8s for discourse
    graph = build_graph([STANDALONE_LEAF, ROOT_WITH_REF])
    units = resolve_leaf_units_for(graph, "discourse")
    assert len(units) == 1
    assert units[0].product_id == "postgresql-k8s"


def test_resolve_leaf_units_for_returns_self_for_top_level_leaf_product():
    graph = build_graph([STANDALONE_LEAF])
    units = resolve_leaf_units_for(graph, "postgresql-k8s")
    assert len(units) == 1
    assert units[0].product_id == "postgresql-k8s"
    assert units[0].repo == "canonical/postgresql-k8s-operator"
    assert units[0].target_medal == "gold"


def test_resolve_leaf_units_for_excludes_leaves_from_other_products():
    # matrix has inline synapse; discourse refs postgresql-k8s
    # scoring matrix should not include postgresql-k8s
    graph = build_graph([ROOT_WITH_INLINE, STANDALONE_LEAF, ROOT_WITH_REF])
    matrix_units = resolve_leaf_units_for(graph, "matrix")
    matrix_ids = [u.product_id for u in matrix_units]
    assert "synapse" in matrix_ids
    assert "postgresql-k8s" not in matrix_ids


def test_resolve_leaf_units_for_shared_leaf_appears_for_each_consumer():
    # Both discourse and a second product can ref the same standalone leaf.
    second_consumer = {
        "id": "other",
        "product_type": "root",
        "name": "Other",
        "lifecycle": "stable",
        "target_medal": "bronze",
        "ownership": {"squad": "emea"},
        "composed_of": [{"ref": "postgresql-k8s"}],
    }
    graph = build_graph([STANDALONE_LEAF, ROOT_WITH_REF, second_consumer])
    discourse_units = resolve_leaf_units_for(graph, "discourse")
    other_units = resolve_leaf_units_for(graph, "other")
    assert any(u.product_id == "postgresql-k8s" for u in discourse_units)
    assert any(u.product_id == "postgresql-k8s" for u in other_units)


def test_resolve_leaf_units_for_unknown_root_raises():
    graph = build_graph([ROOT_WITH_INLINE])
    with pytest.raises(ValueError, match="not found in graph"):
        resolve_leaf_units_for(graph, "nonexistent")


def test_inline_leaf_has_no_own_target_medal():
    """Inline leaf target_medal is None — it must be inherited, not stored."""
    graph = build_graph([ROOT_WITH_INLINE])
    assert graph.nodes["synapse"].target_medal is None


def test_inline_leaf_inherits_root_target_in_resolve_leaf_units():
    """resolve_leaf_units substitutes the parent root's target for inline leaves."""
    graph = build_graph([ROOT_WITH_INLINE])
    units = resolve_leaf_units(graph)
    synapse_unit = next(u for u in units if u.product_id == "synapse")
    assert synapse_unit.target_medal == "gold"  # root matrix target


def test_inline_leaf_inherits_root_target_in_resolve_leaf_units_for():
    """resolve_leaf_units_for substitutes the scoring root's target for inline leaves."""
    graph = build_graph([ROOT_WITH_INLINE])
    units = resolve_leaf_units_for(graph, "matrix")
    synapse_unit = next(u for u in units if u.product_id == "synapse")
    assert synapse_unit.target_medal == "gold"  # root matrix target


def test_standalone_ref_leaf_keeps_own_target():
    """ref: leaves keep their own target_medal — they own their quality accountability."""
    graph = build_graph([STANDALONE_LEAF, ROOT_WITH_REF])
    units = resolve_leaf_units_for(graph, "discourse")
    pg_unit = next(u for u in units if u.product_id == "postgresql-k8s")
    assert pg_unit.target_medal == "gold"  # postgresql-k8s own target, not discourse's silver
