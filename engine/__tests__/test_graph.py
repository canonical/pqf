from pathlib import Path

import pytest

from engine.framework import FrameworkStatus, FrameworkVersion
from engine.graph import build_graph, resolve_leaf_units, resolve_leaf_units_for
from engine.models import ProductType


def _framework(version_id: str, sequence: int, status: FrameworkStatus) -> FrameworkVersion:
    return FrameworkVersion(
        id=version_id,
        sequence=sequence,
        label=f"PQF {version_id.upper()}",
        status=status,
        description=f"{version_id} contract",
        directory=Path("."),
        dimensions={"dimensions": {}},
    )


FRAMEWORKS = [
    _framework("v0", 0, FrameworkStatus.ACTIVE),
    _framework("v1", 1, FrameworkStatus.UPCOMING),
]
FRAMEWORK_BY_ID = {framework.id: framework for framework in FRAMEWORKS}


def _build_graph(*product_dicts: dict, version_id: str = "v0"):
    return build_graph(list(product_dicts), FRAMEWORKS, FRAMEWORK_BY_ID[version_id])


ROOT_WITH_INLINE = {
    "id": "matrix",
    "product_type": "root",
    "name": "Matrix",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "gold", "v1": "gold"},
    "ownership": {"squad": "americas"},
    "composed_of": [
        {
            "id": "synapse",
            "product_type": "charm",
            "introduced_in": "v0",
            "source": {"repo": "canonical/synapse-operator"},
            "allure_report_url": "https://canonical.github.io/synapse-operator/_latest",
        },
        {
            "id": "hive",
            "product_type": "charm",
            "introduced_in": "v1",
            "source": {"repo": "canonical/hive-operator"},
        },
    ],
    "context_refs": [{"label": "PostgreSQL", "repo": "canonical/postgresql-k8s-operator"}],
}

STANDALONE_LEAF = {
    "id": "postgresql-k8s",
    "product_type": "charm",
    "name": "PostgreSQL K8s",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "gold", "v1": "gold"},
    "ownership": {"squad": "data"},
    "source": {"repo": "canonical/postgresql-k8s-operator"},
}

ROOT_WITH_REF = {
    "id": "discourse",
    "product_type": "root",
    "name": "Discourse",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "silver", "v1": "silver"},
    "ownership": {"squad": "americas"},
    "composed_of": [{"ref": "postgresql-k8s", "introduced_in": "v0"}],
}

ROOT_WITH_V1_ONLY_REF = {
    "id": "hive-consumer",
    "product_type": "root",
    "name": "Hive Consumer",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "bronze", "v1": "bronze"},
    "ownership": {"squad": "emea"},
    "composed_of": [{"ref": "postgresql-k8s", "introduced_in": "v1"}],
}


def test_inline_leaf_registered_in_graph():
    graph = _build_graph(ROOT_WITH_INLINE)
    assert "synapse" in graph.nodes


def test_inline_leaf_is_not_portfolio_entry():
    graph = _build_graph(ROOT_WITH_INLINE)
    assert graph.nodes["synapse"].is_portfolio_entry is False
    assert graph.nodes["synapse"].is_inline is True


def test_root_is_portfolio_entry():
    graph = _build_graph(ROOT_WITH_INLINE)
    assert graph.nodes["matrix"].is_portfolio_entry is True


def test_inline_leaf_parent_is_root():
    graph = _build_graph(ROOT_WITH_INLINE)
    assert graph.nodes["synapse"].parent_ids == ["matrix"]


def test_standalone_leaf_is_portfolio_entry():
    graph = _build_graph(STANDALONE_LEAF)
    assert graph.nodes["postgresql-k8s"].is_portfolio_entry is True
    assert graph.nodes["postgresql-k8s"].is_inline is False


def test_ref_resolves_to_standalone():
    graph = _build_graph(STANDALONE_LEAF, ROOT_WITH_REF)
    edge = graph.nodes["discourse"].composed_of[0]
    assert edge.product_id == "postgresql-k8s"
    assert "discourse" in graph.nodes["postgresql-k8s"].parent_ids


def test_missing_ref_raises():
    with pytest.raises(ValueError, match="ref 'postgresql-k8s'"):
        _build_graph(ROOT_WITH_REF)


def test_duplicate_id_raises():
    dup = {**ROOT_WITH_INLINE, "name": "Duplicate"}
    with pytest.raises(ValueError, match="Duplicate product ID"):
        _build_graph(ROOT_WITH_INLINE, dup)


def test_inline_id_collision_with_top_level_raises():
    conflict = {**STANDALONE_LEAF, "id": "synapse"}
    with pytest.raises(ValueError, match="Duplicate product ID"):
        _build_graph(ROOT_WITH_INLINE, conflict)


def test_context_refs_attached_to_root():
    graph = _build_graph(ROOT_WITH_INLINE)
    refs = graph.nodes["matrix"].context_refs
    assert len(refs) == 1
    assert refs[0].label == "PostgreSQL"
    assert refs[0].repo == "canonical/postgresql-k8s-operator"


def test_resolve_leaf_units_returns_only_leaves():
    graph = _build_graph(ROOT_WITH_INLINE)
    units = resolve_leaf_units(graph)
    assert len(units) == 1
    assert units[0].product_id == "synapse"
    assert units[0].repo == "canonical/synapse-operator"
    assert units[0].product_type == ProductType.CHARM
    assert units[0].allure_report_url == "https://canonical.github.io/synapse-operator/_latest"


def test_resolve_leaf_units_root_not_included():
    graph = _build_graph(ROOT_WITH_INLINE)
    unit_ids = [u.product_id for u in resolve_leaf_units(graph)]
    assert "matrix" not in unit_ids


def test_standalone_leaf_included_in_units():
    graph = _build_graph(STANDALONE_LEAF)
    units = resolve_leaf_units(graph)
    assert any(u.product_id == "postgresql-k8s" for u in units)


def test_inline_missing_source_raises():
    bad_root = {
        **ROOT_WITH_INLINE,
        "composed_of": [{"id": "bad-charm", "product_type": "charm", "introduced_in": "v0"}],
    }
    with pytest.raises(ValueError, match="missing required 'source'"):
        _build_graph(bad_root)


def test_resolve_leaf_units_for_returns_only_leaves_of_root():
    graph = _build_graph(STANDALONE_LEAF, ROOT_WITH_REF)
    units = resolve_leaf_units_for(graph, "discourse")
    assert len(units) == 1
    assert units[0].product_id == "postgresql-k8s"


def test_resolve_leaf_units_for_returns_self_for_top_level_leaf_product():
    graph = _build_graph(STANDALONE_LEAF)
    units = resolve_leaf_units_for(graph, "postgresql-k8s")
    assert len(units) == 1
    assert units[0].product_id == "postgresql-k8s"
    assert units[0].repo == "canonical/postgresql-k8s-operator"
    assert units[0].target_medal == "gold"


def test_resolve_leaf_units_for_excludes_leaves_from_other_products():
    graph = _build_graph(ROOT_WITH_INLINE, STANDALONE_LEAF, ROOT_WITH_REF)
    matrix_units = resolve_leaf_units_for(graph, "matrix")
    matrix_ids = [u.product_id for u in matrix_units]
    assert "synapse" in matrix_ids
    assert "postgresql-k8s" not in matrix_ids


def test_resolve_leaf_units_for_shared_leaf_appears_for_each_consumer():
    second_consumer = {
        "id": "other",
        "product_type": "root",
        "name": "Other",
        "lifecycle": "stable",
        "introduced_in": "v0",
        "targets": {"v0": "bronze", "v1": "bronze"},
        "ownership": {"squad": "emea"},
        "composed_of": [{"ref": "postgresql-k8s", "introduced_in": "v0"}],
    }
    graph = _build_graph(STANDALONE_LEAF, ROOT_WITH_REF, second_consumer)
    discourse_units = resolve_leaf_units_for(graph, "discourse")
    other_units = resolve_leaf_units_for(graph, "other")
    assert any(u.product_id == "postgresql-k8s" for u in discourse_units)
    assert any(u.product_id == "postgresql-k8s" for u in other_units)


def test_resolve_leaf_units_for_unknown_root_raises():
    graph = _build_graph(ROOT_WITH_INLINE)
    with pytest.raises(ValueError, match="not found in graph"):
        resolve_leaf_units_for(graph, "nonexistent")


def test_inline_leaf_stores_resolved_target_medal():
    graph = _build_graph(ROOT_WITH_INLINE)
    assert graph.nodes["synapse"].target_medal == "gold"


def test_resolve_leaf_units_uses_resolved_target_medal():
    graph = _build_graph(ROOT_WITH_INLINE)
    units = resolve_leaf_units(graph)
    synapse_unit = next(u for u in units if u.product_id == "synapse")
    assert synapse_unit.target_medal == "gold"


def test_resolve_leaf_units_for_uses_resolved_target_medal():
    graph = _build_graph(ROOT_WITH_INLINE)
    units = resolve_leaf_units_for(graph, "matrix")
    synapse_unit = next(u for u in units if u.product_id == "synapse")
    assert synapse_unit.target_medal == "gold"


def test_standalone_ref_leaf_keeps_own_target():
    graph = _build_graph(STANDALONE_LEAF, ROOT_WITH_REF)
    units = resolve_leaf_units_for(graph, "discourse")
    pg_unit = next(u for u in units if u.product_id == "postgresql-k8s")
    assert pg_unit.target_medal == "gold"


def test_v1_only_inline_leaf_absent_from_v0_graph():
    graph = _build_graph(ROOT_WITH_INLINE, version_id="v0")
    assert "hive" not in graph.nodes
    assert [edge.product_id for edge in graph.nodes["matrix"].composed_of] == ["synapse"]


def test_v1_only_inline_leaf_included_in_v1_graph():
    graph = _build_graph(ROOT_WITH_INLINE, version_id="v1")
    assert "hive" in graph.nodes
    assert [edge.product_id for edge in graph.nodes["matrix"].composed_of] == ["synapse", "hive"]


def test_v1_only_ref_edge_absent_from_v0_graph():
    graph = _build_graph(STANDALONE_LEAF, ROOT_WITH_V1_ONLY_REF, version_id="v0")
    assert graph.nodes["hive-consumer"].composed_of == []


def test_v1_only_ref_edge_included_in_v1_graph():
    graph = _build_graph(STANDALONE_LEAF, ROOT_WITH_V1_ONLY_REF, version_id="v1")
    assert [edge.product_id for edge in graph.nodes["hive-consumer"].composed_of] == [
        "postgresql-k8s"
    ]


def test_active_ref_to_inactive_endpoint_raises():
    v1_leaf = {
        **STANDALONE_LEAF,
        "introduced_in": "v1",
        "targets": {"v1": "gold"},
    }
    with pytest.raises(ValueError, match="active.*inactive|inactive.*active"):
        _build_graph(v1_leaf, ROOT_WITH_REF, version_id="v0")
