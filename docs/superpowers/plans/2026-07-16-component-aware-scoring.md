# Component-Aware PQF Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate PQF from a flat component-list model to a typed product graph model where dimensions are scored per leaf product (charm/snap), aggregated worst-in-scope into root products, and displayed with component-level impact in the UI.

**Architecture:** Each product YAML declares a `product_type` (`root`/`charm`/`snap`). Root products compose leaf products via `composed_of` (inline entries or `ref:` links to standalone YAMLs); untracked dependencies go in `context_refs`. Scorers run per `EvaluationUnit` (one per leaf); the engine aggregates using worst-in-scope; `portfolio.json` carries per-leaf evidence that the UI surfaces in expandable composition rows.

**Tech Stack:** Python 3.12, pytest, responses, ruff; React 19 + Vite + TypeScript strict; Vitest + React Testing Library; Playwright CLI for E2E visual validation.

## Global Constraints

- `product_type` enum values: `root`, `charm`, `snap` (extensible; no `rock` — rocks are charm build artifacts)
- `applies_to.product_types` in dimensions.yaml must be a subset of `["root","charm","snap"]`
- `aggregation` in dimensions.yaml: `worst_in_scope` only in v1
- Inline leaf product IDs must be globally unique (validated at graph-build time)
- `product_type: root` never has `source.repo`; `product_type: charm | snap` always has `source.repo`
- Medal colours: gold `#C7962F`, silver `#8F8F8F`, bronze `#9E622A`, unrated `#666`, remediating `#E98B06`, overdue `#C7162B`
- `@canonical/react-components` only — no Tailwind, no shadcn, no custom CSS frameworks
- TypeScript strict mode; no `any` except in test mocks
- Run `make lint` and `make test-all` before each commit
- GHA `compute-metrics.yml` changes are **out of scope** — document as follow-up in Task 10

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `config/schemas/product.schema.json` | New product YAML schema |
| Modify | `config/schemas/dimensions.schema.json` | Add `applies_to` + `aggregation` |
| Modify | `config/dimensions.yaml` | Add `applies_to` + `aggregation` to all 5 dimensions |
| Modify | `engine/models.py` | Add `ProductType`, `ApplicabilityOutcome`, `EvaluationUnit`, `LeafDimensionResult`; update `DimensionResult` |
| Create | `engine/graph.py` | `ProductNode`, `ProductGraph`, `build_graph()`, `resolve_leaf_units()` |
| Create | `engine/aggregation.py` | `aggregate_root_dimension()`, `compute_leaf_applicability()` |
| Modify | `engine/medal_engine.py` | `compute_leaf_product()`, `compute_root_product()` (graph-aware) |
| Modify | `engine/assemble.py` | Use graph; emit new portfolio JSON shape |
| Modify | `engine/merge_computed.py` | Output new `leaf_metrics` envelope |
| Modify | `engine/validate.py` | Add cross-product-ref graph integrity check |
| Create | `engine/__tests__/test_graph.py` | Graph builder tests |
| Create | `engine/__tests__/test_aggregation.py` | Aggregation tests |
| Modify | `engine/__tests__/test_medal_engine.py` | Update for new signatures |
| Modify | `engine/__tests__/test_assemble.py` | Update for new portfolio shape |
| Modify | `engine/__tests__/test_validate.py` | New schema validation tests |
| Modify | `products/*.yaml` (8 files) | Migrate to new schema |
| Modify | `computed/*.json` (8 files) | Migrate to `leaf_metrics` envelope |
| Modify | `scorers/test_verification/logic.py` | Accept `EvaluationUnit` |
| Modify | `scorers/test_verification/scorer.py` | Iterate leaf units, output per-leaf dict |
| Modify | `scorers/test_verification/__tests__/test_logic.py` | Use `EvaluationUnit` fixtures |
| Modify | `scorers/documentation/logic.py` | Accept `EvaluationUnit` |
| Modify | `scorers/documentation/scorer.py` | Iterate leaf units |
| Modify | `scorers/documentation/__tests__/test_logic.py` | Use `EvaluationUnit` fixtures |
| Modify | `scorers/substrate_compat/logic.py` | Accept `EvaluationUnit` |
| Modify | `scorers/substrate_compat/scorer.py` | Iterate leaf units |
| Modify | `scorers/substrate_compat/__tests__/test_logic.py` | Use `EvaluationUnit` fixtures |
| Modify | `scorers/security_ssdlc/logic.py` | Accept `EvaluationUnit` |
| Modify | `scorers/security_ssdlc/scorer.py` | Iterate leaf units |
| Modify | `scorers/security_ssdlc/__tests__/test_logic.py` | Use `EvaluationUnit` fixtures |
| Modify | `scorers/support_engagement/logic.py` | Accept `EvaluationUnit` |
| Modify | `scorers/support_engagement/scorer.py` | Iterate leaf units |
| Modify | `scorers/support_engagement/__tests__/test_logic.py` | Use `EvaluationUnit` fixtures |
| Modify | `ui/src/types.ts` | New portfolio types |
| Modify | `ui/src/views/Overview.tsx` | Filter `is_portfolio_entry`, stats fix |
| Modify | `ui/src/views/ProductDetail.tsx` | Leaf vs root views, composition impact, context refs |
| Modify | `ui/src/views/__tests__/Overview.test.tsx` | Update for new types |
| Modify | `ui/src/views/__tests__/ProductDetail.test.tsx` | Root + leaf view tests |
| Modify | `docs/architecture.md` | Update data flow + new Product Graph Model section |
| Modify | `docs/adding-a-product.md` | New schema examples + inline-vs-standalone guide |
| Modify | `docs/adding-a-dimension.md` | `applies_to` + `EvaluationUnit` contract |

---

### Task 1: New config schemas + dimensions.yaml `applies_to`

**Files:**
- Modify: `config/schemas/product.schema.json`
- Modify: `config/schemas/dimensions.schema.json`
- Modify: `config/dimensions.yaml`
- Modify: `engine/__tests__/test_validate.py`

**Interfaces:**
- Produces: validated JSON schemas consumed by `engine/validate.py` and CI
- Produces: `applies_to.product_types` + `aggregation` fields in every dimension (consumed by Tasks 3, 4)

- [ ] **Step 1: Write failing schema validation tests**

Add these tests to `engine/__tests__/test_validate.py`. First look at the existing test file to understand the fixture pattern (`prod_schema`, `dim_schema` fixtures and `_validate_dict` helper), then append:

```python
# New product schema test fixtures
ROOT_PRODUCT_VALID = {
    "id": "test-root",
    "product_type": "root",
    "name": "Test Root",
    "lifecycle": "stable",
    "target_medal": "silver",
    "ownership": {"squad": "emea"},
    "composed_of": [
        {
            "id": "test-charm",
            "product_type": "charm",
            "source": {"repo": "canonical/test-charm"},
            "target_medal": "silver",
        }
    ],
}

LEAF_PRODUCT_VALID = {
    "id": "test-charm",
    "product_type": "charm",
    "name": "Test Charm",
    "lifecycle": "stable",
    "target_medal": "silver",
    "ownership": {"squad": "emea"},
    "source": {"repo": "canonical/test-charm"},
}

LEAF_WITH_SUBPATH = {
    "id": "backup-charm",
    "product_type": "charm",
    "name": "Backup Charm",
    "lifecycle": "stable",
    "target_medal": "bronze",
    "ownership": {"squad": "emea"},
    "source": {"repo": "canonical/backup-operators", "subpath": "charms/backup"},
}

ROOT_MISSING_PRODUCT_TYPE = {
    "id": "bad",
    "name": "Bad",
    "lifecycle": "stable",
    "target_medal": "silver",
    "ownership": {"squad": "emea"},
}

LEAF_MISSING_SOURCE = {
    "id": "bad-charm",
    "product_type": "charm",
    "name": "Bad Charm",
    "lifecycle": "stable",
    "target_medal": "silver",
    "ownership": {"squad": "emea"},
}

ROOT_WITH_SOURCE = {
    **ROOT_PRODUCT_VALID,
    "source": {"repo": "canonical/something"},  # root must NOT have source
}


def test_root_product_valid(prod_schema):
    assert _validate_dict(ROOT_PRODUCT_VALID, prod_schema) == []


def test_leaf_product_valid(prod_schema):
    assert _validate_dict(LEAF_PRODUCT_VALID, prod_schema) == []


def test_leaf_with_subpath_valid(prod_schema):
    assert _validate_dict(LEAF_WITH_SUBPATH, prod_schema) == []


def test_product_type_required(prod_schema):
    errors = _validate_dict(ROOT_MISSING_PRODUCT_TYPE, prod_schema)
    assert any("product_type" in e for e in errors)


def test_root_must_have_composed_of(prod_schema):
    bad = {k: v for k, v in ROOT_PRODUCT_VALID.items() if k != "composed_of"}
    errors = _validate_dict(bad, prod_schema)
    assert any("composed_of" in e for e in errors)


def test_leaf_must_have_source(prod_schema):
    errors = _validate_dict(LEAF_MISSING_SOURCE, prod_schema)
    assert any("source" in e for e in errors)
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest engine/__tests__/test_validate.py -v -k "test_root_product_valid or test_leaf_product_valid or test_product_type_required or test_root_must_have_composed_of or test_leaf_must_have_source"
```

Expected: FAIL (old schema doesn't have `product_type`)

- [ ] **Step 3: Replace `config/schemas/product.schema.json`**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://github.com/srbouffard/pqf/config/schemas/product.schema.json",
  "title": "PQF Product Definition",
  "type": "object",
  "required": ["id", "product_type", "name", "lifecycle", "target_medal", "ownership"],
  "additionalProperties": false,
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*$",
      "description": "Unique product identifier. Kebab-case. Must match filename (without .yaml)."
    },
    "product_type": {
      "type": "string",
      "enum": ["root", "charm", "snap"],
      "description": "root: composed of other products. charm/snap: scored directly against source repo."
    },
    "name": {"type": "string", "minLength": 1},
    "description": {"type": "string", "minLength": 1},
    "lifecycle": {
      "type": "string",
      "enum": ["experimental", "beta", "stable", "legacy"]
    },
    "target_medal": {
      "type": "string",
      "enum": ["bronze", "silver", "gold"]
    },
    "ownership": {
      "type": "object",
      "required": ["squad"],
      "additionalProperties": false,
      "properties": {
        "squad": {"type": "string", "minLength": 1},
        "stakeholders": {"type": "array", "items": {"type": "string"}},
        "users": {"type": "array", "items": {"type": "string"}}
      }
    },
    "documentation_url": {"type": "string", "format": "uri"},
    "source": {"$ref": "#/definitions/Source"},
    "composed_of": {
      "type": "array",
      "minItems": 1,
      "items": {"$ref": "#/definitions/ComposedEntry"}
    },
    "context_refs": {
      "type": "array",
      "items": {"$ref": "#/definitions/ContextRef"}
    }
  },
  "if": {
    "properties": {"product_type": {"const": "root"}}
  },
  "then": {
    "required": ["composed_of"],
    "not": {"required": ["source"]}
  },
  "else": {
    "required": ["source"]
  },
  "definitions": {
    "Source": {
      "type": "object",
      "required": ["repo"],
      "additionalProperties": false,
      "properties": {
        "repo": {
          "type": "string",
          "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
          "description": "GitHub owner/repo slug."
        },
        "subpath": {
          "type": "string",
          "description": "Optional path within the repo for mono-repo components, e.g. charms/synapse."
        }
      }
    },
    "ComposedEntry": {
      "oneOf": [
        {
          "description": "Reference to a standalone leaf product defined in products/<id>.yaml.",
          "type": "object",
          "required": ["ref"],
          "additionalProperties": false,
          "properties": {
            "ref": {
              "type": "string",
              "pattern": "^[a-z][a-z0-9-]*$",
              "description": "product_id of the standalone leaf product YAML."
            },
            "excluded_from_parent_medal": {
              "type": "boolean",
              "description": "If true, this product's dimension scores do not roll up into the parent medal."
            }
          }
        },
        {
          "description": "Inline leaf product — owned by this team, belongs to this root only.",
          "type": "object",
          "required": ["id", "product_type", "source", "target_medal"],
          "additionalProperties": false,
          "properties": {
            "id": {
              "type": "string",
              "pattern": "^[a-z][a-z0-9-]*$",
              "description": "Stable identifier for this leaf. Must be globally unique."
            },
            "product_type": {
              "type": "string",
              "enum": ["charm", "snap"]
            },
            "source": {"$ref": "#/definitions/Source"},
            "target_medal": {
              "type": "string",
              "enum": ["bronze", "silver", "gold"]
            },
            "allure_report_url": {
              "type": "string",
              "format": "uri",
              "description": "Allure report base URL for test_verification scoring."
            },
            "documentation_url": {
              "type": "string",
              "format": "uri"
            },
            "excluded_from_parent_medal": {"type": "boolean"}
          }
        }
      ]
    },
    "ContextRef": {
      "type": "object",
      "required": ["label"],
      "additionalProperties": false,
      "properties": {
        "label": {
          "type": "string",
          "minLength": 1,
          "description": "Display name for this dependency."
        },
        "repo": {
          "type": "string",
          "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
          "description": "Optional GitHub owner/repo for linking. Not scored."
        }
      }
    }
  }
}
```

- [ ] **Step 4: Update `config/schemas/dimensions.schema.json` — add `applies_to` and `aggregation` to the `Dimension` definition**

In the `Dimension` object:
- Add `"applies_to"` and `"aggregation"` to `"required"` list
- Add to `"properties"`:

```json
"applies_to": {
  "type": "object",
  "required": ["product_types"],
  "additionalProperties": false,
  "description": "Declares which product types this dimension scores. Products of other types return not_applicable.",
  "properties": {
    "product_types": {
      "type": "array",
      "minItems": 1,
      "items": {"type": "string", "enum": ["root", "charm", "snap"]},
      "description": "List of product_type values this dimension applies to."
    }
  }
},
"aggregation": {
  "type": "string",
  "enum": ["worst_in_scope"],
  "description": "How leaf results are aggregated into the root product medal. worst_in_scope: minimum medal among in-scope leaves."
}
```

- [ ] **Step 5: Add `applies_to` and `aggregation` to all 5 dimensions in `config/dimensions.yaml`**

For `test_verification`, `documentation`, `security_ssdlc`, `support_engagement` — add after `scorer:`:
```yaml
applies_to:
  product_types: [charm, snap]
aggregation: worst_in_scope
```

For `substrate_compat` — add after `scorer:`:
```yaml
applies_to:
  product_types: [charm]
aggregation: worst_in_scope
```

- [ ] **Step 6: Run the new tests**

```
pytest engine/__tests__/test_validate.py -v
make lint
```

Expected: all new schema tests pass; lint clean. (`make validate` will still fail for products — that's expected until Task 5.)

- [ ] **Step 7: Commit**

```bash
git add config/schemas/ config/dimensions.yaml engine/__tests__/test_validate.py
git commit -m "feat: new product schema (product_type, composed_of, context_refs) and dimension applies_to"
```

---

### Task 2: Engine data models + product graph builder

**Files:**
- Modify: `engine/models.py`
- Create: `engine/graph.py`
- Create: `engine/__tests__/test_graph.py`

**Interfaces:**
- Produces: `ProductType`, `ApplicabilityOutcome`, `EvaluationUnit`, `LeafDimensionResult` (consumed by Tasks 3, 4, 6)
- Produces: `ProductGraph`, `build_graph(product_dicts: list[dict]) -> ProductGraph` (consumed by Tasks 3, 4)
- Produces: `resolve_leaf_units(graph: ProductGraph) -> list[EvaluationUnit]` (consumed by Task 6)

- [ ] **Step 1: Write failing tests for graph builder**

Create `engine/__tests__/test_graph.py`:

```python
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
```

- [ ] **Step 2: Run failing tests**

```
pytest engine/__tests__/test_graph.py -v
```

Expected: FAIL — `engine.graph` does not exist yet

- [ ] **Step 3: Add new types to `engine/models.py`**

Add after the existing `Medal` and `MEDAL_RANK` definitions:

```python
class ProductType(StrEnum):
    ROOT = "root"
    CHARM = "charm"
    SNAP = "snap"


class ApplicabilityOutcome(StrEnum):
    SCORED = "scored"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class EvaluationUnit:
    """Single leaf product to score — the fundamental unit of computation."""
    product_id: str
    product_type: ProductType
    repo: str
    subpath: str | None = None
    allure_report_url: str = ""
    documentation_url: str = ""
    target_medal: str = "bronze"


@dataclass
class LeafDimensionResult:
    """Dimension result for one leaf product inside a root product's composition."""
    product_id: str
    repo: str
    medal: Medal
    applicability: ApplicabilityOutcome
    metrics: dict
    excluded_from_parent_medal: bool = False
```

Also update `DimensionResult` to add `applicability` and `composition`:

```python
@dataclass
class DimensionResult:
    medal: Medal
    target: Medal
    applicability: ApplicabilityOutcome
    metrics: dict
    drift: DriftState | None
    composition: list["LeafDimensionResult"] | None = None
```

- [ ] **Step 4: Create `engine/graph.py`**

```python
# engine/graph.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.models import EvaluationUnit, ProductType


@dataclass
class CompositionEdge:
    product_id: str
    excluded_from_parent_medal: bool = False


@dataclass
class ContextRef:
    label: str
    repo: str | None = None


@dataclass
class ProductNode:
    id: str
    product_type: ProductType
    name: str
    target_medal: str
    ownership_squad: str
    source_repo: str | None
    source_subpath: str | None
    allure_report_url: str
    documentation_url: str
    is_inline: bool
    is_portfolio_entry: bool
    lifecycle: str = "stable"
    description: str = ""
    composed_of: list[CompositionEdge] = field(default_factory=list)
    context_refs: list[ContextRef] = field(default_factory=list)
    parent_ids: list[str] = field(default_factory=list)


@dataclass
class ProductGraph:
    nodes: dict[str, ProductNode]  # product_id -> ProductNode


def _node_from_product_dict(d: dict[str, Any]) -> ProductNode:
    source = d.get("source", {})
    return ProductNode(
        id=d["id"],
        product_type=ProductType(d["product_type"]),
        name=d.get("name", d["id"]),
        target_medal=d["target_medal"],
        ownership_squad=d.get("ownership", {}).get("squad", ""),
        source_repo=source.get("repo"),
        source_subpath=source.get("subpath"),
        allure_report_url=d.get("allure_report_url", ""),
        documentation_url=d.get("documentation_url", ""),
        is_inline=False,
        is_portfolio_entry=True,
        lifecycle=d.get("lifecycle", "stable"),
        description=d.get("description", ""),
    )


def _node_from_inline(entry: dict[str, Any], parent_id: str) -> ProductNode:
    source = entry["source"]
    return ProductNode(
        id=entry["id"],
        product_type=ProductType(entry["product_type"]),
        name=entry.get("name", entry["id"]),
        target_medal=entry["target_medal"],
        ownership_squad="",
        source_repo=source["repo"],
        source_subpath=source.get("subpath"),
        allure_report_url=entry.get("allure_report_url", ""),
        documentation_url=entry.get("documentation_url", ""),
        is_inline=True,
        is_portfolio_entry=False,
        parent_ids=[parent_id],
    )


def build_graph(product_dicts: list[dict[str, Any]]) -> ProductGraph:
    """
    Build and validate the product graph from parsed product YAML dicts.
    Raises ValueError on duplicate IDs, missing refs, or invalid structure.
    """
    nodes: dict[str, ProductNode] = {}

    # Pass 1: register all top-level products
    for d in product_dicts:
        pid = d["id"]
        if pid in nodes:
            raise ValueError(f"Duplicate product ID: {pid!r}")
        nodes[pid] = _node_from_product_dict(d)

    # Pass 2: wire composition edges and register inline leaves
    for d in product_dicts:
        if d["product_type"] != "root":
            continue
        root_id = d["id"]
        root_node = nodes[root_id]

        for entry in d.get("composed_of", []):
            if "ref" in entry:
                ref_id = entry["ref"]
                if ref_id not in nodes:
                    raise ValueError(
                        f"In product {root_id!r}: ref {ref_id!r} not found. "
                        f"Create products/{ref_id}.yaml or use an inline entry."
                    )
                if root_id not in nodes[ref_id].parent_ids:
                    nodes[ref_id].parent_ids.append(root_id)
                root_node.composed_of.append(
                    CompositionEdge(
                        product_id=ref_id,
                        excluded_from_parent_medal=entry.get("excluded_from_parent_medal", False),
                    )
                )
            else:
                inline_id = entry["id"]
                if inline_id in nodes:
                    raise ValueError(
                        f"Duplicate product ID {inline_id!r}: defined inline in {root_id!r} "
                        f"but already exists as another product."
                    )
                inline_node = _node_from_inline(entry, root_id)
                nodes[inline_id] = inline_node
                root_node.composed_of.append(
                    CompositionEdge(
                        product_id=inline_id,
                        excluded_from_parent_medal=entry.get("excluded_from_parent_medal", False),
                    )
                )

        for cr in d.get("context_refs", []):
            root_node.context_refs.append(ContextRef(label=cr["label"], repo=cr.get("repo")))

    return ProductGraph(nodes=nodes)


def resolve_leaf_units(graph: ProductGraph) -> list[EvaluationUnit]:
    """Return one EvaluationUnit for every leaf (charm/snap) product in the graph."""
    return [
        EvaluationUnit(
            product_id=node.id,
            product_type=node.product_type,
            repo=node.source_repo or "",
            subpath=node.source_subpath,
            allure_report_url=node.allure_report_url,
            documentation_url=node.documentation_url,
            target_medal=node.target_medal,
        )
        for node in graph.nodes.values()
        if node.product_type in (ProductType.CHARM, ProductType.SNAP)
    ]
```

- [ ] **Step 5: Run graph tests**

```
pytest engine/__tests__/test_graph.py -v
make lint
```

Expected: all 13 tests pass; lint clean

- [ ] **Step 6: Commit**

```bash
git add engine/models.py engine/graph.py engine/__tests__/test_graph.py
git commit -m "feat: add ProductGraph, EvaluationUnit, and graph builder"
```

---

### Task 3: Aggregation engine + updated medal_engine

**Files:**
- Create: `engine/aggregation.py`
- Modify: `engine/medal_engine.py`
- Create: `engine/__tests__/test_aggregation.py`
- Modify: `engine/__tests__/test_medal_engine.py`

**Interfaces:**
- Consumes: `ProductGraph`, `EvaluationUnit`, `LeafDimensionResult`, `ApplicabilityOutcome` (Task 2)
- Produces: `compute_leaf_applicability(product_type, metrics, dim_config) -> ApplicabilityOutcome`
- Produces: `aggregate_root_dimension(leaf_results, dim_config, drift_history, product_id, target_medal, now) -> DimensionResult`
- Produces: `compute_leaf_product(product_id, product_type, leaf_metrics, dimensions_config, drift_history, target_medal) -> ProductResult` (consumed by Task 4)
- Produces: `compute_root_product(root_id, graph, all_leaf_results, dimensions_config, drift_history, target_medal, now) -> ProductResult` (consumed by Task 4)

- [ ] **Step 1: Write failing aggregation tests**

Create `engine/__tests__/test_aggregation.py`:

```python
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
    return LeafDimensionResult(product_id, f"canonical/{product_id}", medal, applicability, {}, excluded)


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
    leaves = [_leaf("a", Medal.GOLD), _leaf("b", Medal.UNRATED, ApplicabilityOutcome.NOT_APPLICABLE)]
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
```

- [ ] **Step 2: Run failing tests**

```
pytest engine/__tests__/test_aggregation.py -v
```

Expected: FAIL — `engine.aggregation` doesn't exist

- [ ] **Step 3: Create `engine/aggregation.py`**

```python
# engine/aggregation.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from engine.drift_tracker import compute_dimension_drift
from engine.models import (
    MEDAL_RANK,
    ApplicabilityOutcome,
    DimensionResult,
    LeafDimensionResult,
    Medal,
)


def compute_leaf_applicability(
    product_type: str,
    metrics: dict[str, Any],
    dim_config: dict[str, Any],
) -> ApplicabilityOutcome:
    """Determine if this dimension applies to this product type and has data."""
    applies_to = dim_config.get("applies_to", {}).get("product_types", [])
    if product_type not in applies_to:
        return ApplicabilityOutcome.NOT_APPLICABLE
    if not metrics:
        return ApplicabilityOutcome.INSUFFICIENT_DATA
    return ApplicabilityOutcome.SCORED


def aggregate_root_dimension(
    leaf_results: list[LeafDimensionResult],
    dim_config: dict[str, Any],
    drift_history: dict,
    product_id: str,
    target_medal: str,
    now: datetime | None,
) -> DimensionResult:
    """
    Aggregate per-leaf dimension results into a root DimensionResult.
    Rule: minimum medal among in-scope (not excluded, scored) leaves.
    """
    target = Medal(target_medal)

    in_scope = [
        r for r in leaf_results
        if not r.excluded_from_parent_medal
        and r.applicability == ApplicabilityOutcome.SCORED
    ]

    if not in_scope:
        all_na = not leaf_results or all(
            r.applicability == ApplicabilityOutcome.NOT_APPLICABLE for r in leaf_results
        )
        applicability = (
            ApplicabilityOutcome.NOT_APPLICABLE if all_na
            else ApplicabilityOutcome.INSUFFICIENT_DATA
        )
        return DimensionResult(
            medal=Medal.UNRATED,
            target=target,
            applicability=applicability,
            metrics={},
            drift=None,
            composition=list(leaf_results),
        )

    worst = min(in_scope, key=lambda r: MEDAL_RANK[r.medal])
    drift = (
        compute_dimension_drift(product_id, "", worst.medal, target, drift_history)
        if now is not None
        else None
    )

    return DimensionResult(
        medal=worst.medal,
        target=target,
        applicability=ApplicabilityOutcome.SCORED,
        metrics={},
        drift=drift,
        composition=list(leaf_results),
    )
```

- [ ] **Step 4: Rewrite `engine/medal_engine.py`**

```python
# engine/medal_engine.py
from __future__ import annotations

from datetime import datetime

from engine.aggregation import aggregate_root_dimension, compute_leaf_applicability
from engine.drift_tracker import compute_dimension_drift
from engine.graph import ProductGraph
from engine.models import (
    MEDAL_RANK,
    ApplicabilityOutcome,
    DimensionResult,
    LeafDimensionResult,
    Medal,
    ProductResult,
    ProductType,
)
from engine.rubric import evaluate_rubric


def compute_leaf_product(
    product_id: str,
    product_type: str,
    leaf_metrics: dict[str, dict],
    dimensions_config: dict,
    drift_history: dict,
    target_medal: str,
) -> ProductResult:
    """
    Compute medals for a leaf product (charm/snap) directly from its per-dimension metrics.
    leaf_metrics: {dim_name: {metric_key: value, ...}}
    """
    target = Medal(target_medal)
    dimension_results: dict[str, DimensionResult] = {}

    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        metrics = leaf_metrics.get(dim_name, {})
        applicability = compute_leaf_applicability(product_type, metrics, dim_config)

        if applicability != ApplicabilityOutcome.SCORED:
            dim_medal = Medal.UNRATED
        else:
            dim_medal = evaluate_rubric(metrics, dim_config["medals"])

        drift = compute_dimension_drift(product_id, dim_name, dim_medal, target, drift_history)
        dimension_results[dim_name] = DimensionResult(
            medal=dim_medal,
            target=target,
            applicability=applicability,
            metrics=metrics,
            drift=drift,
            composition=None,
        )

    scored = [
        r for r in dimension_results.values()
        if r.applicability == ApplicabilityOutcome.SCORED
    ]
    current_medal = (
        min(scored, key=lambda r: MEDAL_RANK[r.medal]).medal if scored else Medal.UNRATED
    )

    return ProductResult(
        product_id=product_id,
        current_medal=current_medal,
        target_medal=target,
        dimensions=dimension_results,
    )


def compute_root_product(
    root_id: str,
    graph: ProductGraph,
    all_leaf_results: dict[str, ProductResult],
    dimensions_config: dict,
    drift_history: dict,
    target_medal: str,
    now: datetime | None = None,
) -> ProductResult:
    """
    Compute medals for a root product by aggregating composed leaf results.
    all_leaf_results: {leaf_product_id: ProductResult}
    """
    target = Medal(target_medal)
    root_node = graph.nodes[root_id]
    dimension_results: dict[str, DimensionResult] = {}

    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        leaf_dim_results: list[LeafDimensionResult] = []
        for edge in root_node.composed_of:
            leaf_result = all_leaf_results.get(edge.product_id)
            if leaf_result is None:
                continue
            leaf_dim = leaf_result.dimensions.get(dim_name)
            if leaf_dim is None:
                continue
            leaf_node = graph.nodes.get(edge.product_id)
            leaf_dim_results.append(
                LeafDimensionResult(
                    product_id=edge.product_id,
                    repo=leaf_node.source_repo if leaf_node else "",
                    medal=leaf_dim.medal,
                    applicability=leaf_dim.applicability,
                    metrics=leaf_dim.metrics,
                    excluded_from_parent_medal=edge.excluded_from_parent_medal,
                )
            )

        dimension_results[dim_name] = aggregate_root_dimension(
            leaf_dim_results, dim_config, drift_history, root_id, target_medal, now
        )

    scored = [
        r for r in dimension_results.values()
        if r.applicability == ApplicabilityOutcome.SCORED
    ]
    current_medal = (
        min(scored, key=lambda r: MEDAL_RANK[r.medal]).medal if scored else Medal.UNRATED
    )

    return ProductResult(
        product_id=root_id,
        current_medal=current_medal,
        target_medal=target,
        dimensions=dimension_results,
    )
```

- [ ] **Step 5: Run all engine tests**

```
pytest engine/__tests__/test_aggregation.py engine/__tests__/test_medal_engine.py -v
make lint
```

Expected: all tests pass; lint clean. (Some old medal_engine tests may need minor fixture updates — fix any that fail due to the new `applicability` field on `DimensionResult`.)

- [ ] **Step 6: Commit**

```bash
git add engine/aggregation.py engine/medal_engine.py engine/__tests__/test_aggregation.py engine/__tests__/test_medal_engine.py
git commit -m "feat: worst-in-scope aggregation and graph-aware medal engine"
```

---

### Task 4: Updated assemble.py + new portfolio JSON shape

**Files:**
- Modify: `engine/assemble.py`
- Modify: `engine/merge_computed.py`
- Modify: `engine/__tests__/test_assemble.py`

**Interfaces:**
- Consumes: `build_graph`, `resolve_leaf_units` (Task 2); `compute_leaf_product`, `compute_root_product` (Task 3)
- Produces: `assemble_portfolio(...) -> dict` — portfolio with new per-product shape including `product_type`, `is_portfolio_entry`, `composition` in dimension entries

New per-product entry shape:
```json
{
  "id": "matrix",
  "product_type": "root",
  "name": "Matrix (Synapse)",
  "description": "...",
  "lifecycle": "stable",
  "target_medal": "gold",
  "current_medal": "bronze",
  "squad": "americas",
  "is_portfolio_entry": true,
  "documentation_url": "...",
  "source": null,
  "composed_of": [{"product_id": "synapse", "excluded_from_parent_medal": false}],
  "context_refs": [{"label": "PostgreSQL", "repo": "canonical/postgresql-k8s-operator"}],
  "parent_product_ids": [],
  "dimensions": {
    "test_verification": {
      "medal": "bronze",
      "target": "gold",
      "applicability": "scored",
      "metrics": {},
      "drift": null,
      "composition": [
        {
          "product_id": "synapse",
          "repo": "canonical/synapse-operator",
          "medal": "bronze",
          "applicability": "scored",
          "metrics": {"coverage_pct": 60},
          "excluded_from_parent_medal": false
        }
      ]
    }
  }
}
```

New computed file shape (`computed/{product-id}.json`):
```json
{
  "product_id": "matrix",
  "computed_at": "2026-01-01T00:00:00+00:00",
  "leaf_metrics": {
    "synapse": {
      "test_verification": {"coverage_pct": 60, "stability_pct": 90, "latest_build_passing": true, "uses_ops_testing": true, "uses_jubilant": false},
      "documentation": {"has_readme": true, "has_contributing": true, "has_security": true, "diataxis_coverage": 3, "style_linter_passing": false, "links_passing": true}
    }
  }
}
```

- [ ] **Step 1: Write failing assembly tests**

Replace all tests in `engine/__tests__/test_assemble.py` with:

```python
import json
from pathlib import Path
import pytest
import yaml
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
                "coverage_pct": {"type": "number", "label": "Coverage", "description": "...", "range": "0-100"}
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
    target_medal: gold
context_refs:
  - label: PostgreSQL
    repo: canonical/postgresql-k8s-operator
"""

COMPUTED_JSON = {
    "product_id": "matrix",
    "computed_at": "2026-01-01T00:00:00+00:00",
    "leaf_metrics": {
        "synapse": {
            "test_verification": {"coverage_pct": 75}
        }
    }
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


def test_inline_leaf_not_in_top_level_products(portfolio):
    ids = [p["id"] for p in portfolio["products"]]
    assert "synapse" not in ids


def test_root_dimension_has_composition(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    dim = matrix["dimensions"]["test_verification"]
    assert dim["applicability"] == "scored"
    assert dim["composition"] is not None
    assert len(dim["composition"]) == 1
    assert dim["composition"][0]["product_id"] == "synapse"
    assert dim["composition"][0]["medal"] == "bronze"  # 75 >= 70


def test_context_refs_in_portfolio(portfolio):
    matrix = next(p for p in portfolio["products"] if p["id"] == "matrix")
    assert len(matrix["context_refs"]) == 1
    assert matrix["context_refs"][0]["label"] == "PostgreSQL"


def test_dimensions_meta_has_applies_to(portfolio):
    meta = portfolio["dimensions_meta"]["test_verification"]
    assert "charm" in meta["applies_to"]
    assert meta["aggregation"] == "worst_in_scope"
```

- [ ] **Step 2: Run failing tests**

```
pytest engine/__tests__/test_assemble.py -v
```

Expected: FAIL

- [ ] **Step 3: Rewrite `engine/assemble.py`**

```python
# engine/assemble.py
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from engine.drift_tracker import update_drift_history
from engine.graph import build_graph
from engine.medal_engine import compute_leaf_product, compute_root_product
from engine.models import Medal, ProductType


def _build_dimensions_meta(dimensions_config: dict) -> dict:
    meta = {}
    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        medals_meta: dict = {}
        for tier, conditions in dim_config.get("medals", {}).items():
            medals_meta[tier] = {"criteria": conditions}
        outputs_meta = {}
        for metric_name, metric_cfg in dim_config.get("outputs", {}).items():
            if not isinstance(metric_cfg, dict):
                continue
            outputs_meta[metric_name] = {
                "label": metric_cfg.get("label", metric_name),
                "description": metric_cfg.get("description", ""),
                "type": metric_cfg.get("type", "unknown"),
                "range": metric_cfg.get("range", ""),
                "ai_assisted": metric_cfg.get("ai_assisted", False),
            }
        meta[dim_name] = {
            "label": dim_config.get("label", dim_name.replace("_", " ").title()),
            "description": dim_config.get("description", ""),
            "applies_to": dim_config.get("applies_to", {}).get("product_types", []),
            "aggregation": dim_config.get("aggregation", "worst_in_scope"),
            "outputs": outputs_meta,
            "medals": medals_meta,
        }
    return meta


def _dim_to_dict(dim_result) -> dict:
    composition = None
    if dim_result.composition is not None:
        composition = [
            {
                "product_id": lr.product_id,
                "repo": lr.repo,
                "medal": lr.medal.value,
                "applicability": lr.applicability.value,
                "metrics": lr.metrics,
                "excluded_from_parent_medal": lr.excluded_from_parent_medal,
            }
            for lr in dim_result.composition
        ]
    return {
        "medal": dim_result.medal.value,
        "target": dim_result.target.value,
        "applicability": dim_result.applicability.value,
        "metrics": dim_result.metrics,
        "drift": {
            "status": dim_result.drift.status,
            "first_seen_at": dim_result.drift.first_seen_at,
            "deadline": dim_result.drift.deadline,
        } if dim_result.drift else None,
        "composition": composition,
    }


def _result_to_dict(result, node) -> dict:
    return {
        "id": result.product_id,
        "product_type": node.product_type.value,
        "name": node.name,
        "description": node.description,
        "lifecycle": node.lifecycle,
        "target_medal": result.target_medal.value,
        "current_medal": result.current_medal.value,
        "squad": node.ownership_squad,
        "is_portfolio_entry": node.is_portfolio_entry,
        "documentation_url": node.documentation_url,
        "source": {"repo": node.source_repo, "subpath": node.source_subpath} if node.source_repo else None,
        "composed_of": [
            {"product_id": e.product_id, "excluded_from_parent_medal": e.excluded_from_parent_medal}
            for e in node.composed_of
        ] if node.product_type == ProductType.ROOT else None,
        "context_refs": [
            {"label": cr.label, "repo": cr.repo} for cr in node.context_refs
        ],
        "parent_product_ids": node.parent_ids,
        "dimensions": {
            name: _dim_to_dict(dim) for name, dim in result.dimensions.items()
        },
    }


def assemble_portfolio(
    products_dir,
    computed_dir,
    dimensions_config,
    drift_history,
    update_drift,
) -> dict:
    products_dir = Path(products_dir)
    computed_dir = Path(computed_dir)
    now = datetime.now(UTC)

    product_dicts = [
        yaml.safe_load(p.read_text())
        for p in sorted(products_dir.glob("*.yaml"))
        if not p.name.startswith(".")
    ]
    graph = build_graph(product_dicts)

    # Load leaf metrics from computed files:
    # computed/{root-id}.json → {"leaf_metrics": {"leaf-id": {"dim": {metrics}}}}
    leaf_computed: dict[str, dict[str, dict]] = {}  # leaf_id -> dim_name -> metrics
    for path in sorted(computed_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for leaf_id, leaf_data in data.get("leaf_metrics", {}).items():
            if leaf_id not in leaf_computed:
                leaf_computed[leaf_id] = {}
            for key, value in leaf_data.items():
                if isinstance(value, dict):  # only dimension metric dicts
                    leaf_computed[leaf_id][key] = value

    # Compute leaf product results
    leaf_results = {}
    for node in graph.nodes.values():
        if node.product_type in (ProductType.CHARM, ProductType.SNAP):
            leaf_results[node.id] = compute_leaf_product(
                node.id,
                node.product_type.value,
                leaf_computed.get(node.id, {}),
                dimensions_config,
                drift_history,
                node.target_medal,
            )

    # Compute root product results
    root_results = {}
    for node in graph.nodes.values():
        if node.product_type == ProductType.ROOT:
            root_results[node.id] = compute_root_product(
                node.id, graph, leaf_results,
                dimensions_config, drift_history, node.target_medal, now,
            )

    if update_drift:
        for pid, result in {**root_results, **leaf_results}.items():
            for dim_name, dim_result in result.dimensions.items():
                update_drift_history(
                    pid, dim_name, dim_result.medal, result.target_medal, drift_history, now
                )

    # All products in graph order; root products first for stable ordering
    all_results = {**root_results, **leaf_results}
    products_out = [
        _result_to_dict(all_results[node.id], node)
        for node in graph.nodes.values()
        if node.id in all_results
    ]

    return {
        "generated_at": now.isoformat(),
        "products": products_out,
        "dimensions_meta": _build_dimensions_meta(dimensions_config),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PQF portfolio assembler")
    parser.add_argument("--products-dir", required=True)
    parser.add_argument("--computed-dir", required=True)
    parser.add_argument("--dimensions", required=True)
    parser.add_argument("--drift-history", required=True, dest="drift_history")
    parser.add_argument("--output", required=True)
    parser.add_argument("--update-drift", action="store_true", dest="update_drift")
    args = parser.parse_args()

    dimensions_config = yaml.safe_load(Path(args.dimensions).read_text())
    drift_history_path = Path(args.drift_history)
    drift_history = json.loads(drift_history_path.read_text())

    portfolio = assemble_portfolio(
        products_dir=args.products_dir,
        computed_dir=args.computed_dir,
        dimensions_config=dimensions_config,
        drift_history=drift_history,
        update_drift=args.update_drift,
    )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(portfolio, indent=2) + "\n")

    if args.update_drift:
        drift_history_path.write_text(json.dumps(drift_history, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Update `engine/merge_computed.py`** to output the new `leaf_metrics` envelope

The scorer.py wrappers (updated in Task 6) will output `{"leaf-id": {"metric": value}, ...}`. `merge_computed.py` assembles per-dimension scorer output files into a single computed file. Update `main()` as follows:

```python
# Replace the existing output assembly block in main():
leaf_metrics: dict = {}
for dim_name in dims_config.get("dimensions", {}):
    path = scorer_dir / f"{dim_name}.json"
    if not path.exists():
        continue
    try:
        dim_data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"Warning: skipping {dim_name} — {e}", file=sys.stderr)
        continue
    # dim_data is now {"leaf-id": {"metric": value, ...}, ...}
    if isinstance(dim_data, dict):
        for leaf_id, metrics in dim_data.items():
            if isinstance(metrics, dict):
                leaf_metrics.setdefault(leaf_id, {})[dim_name] = metrics

output = {
    "product_id": args.product_id,
    "computed_at": datetime.now(UTC).isoformat(),
    "leaf_metrics": leaf_metrics,
}
```

- [ ] **Step 5: Run all engine tests**

```
pytest engine/ -v
make lint
```

Expected: all tests pass; lint clean

- [ ] **Step 6: Commit**

```bash
git add engine/assemble.py engine/merge_computed.py engine/__tests__/test_assemble.py
git commit -m "feat: update assemble.py and merge_computed.py for graph-aware portfolio"
```

---

### Task 5: Migrate product YAMLs + computed files

**Files:**
- Modify: all `products/*.yaml` (8 files)
- Modify: all `computed/*.json` (8 files)

Pattern: `product_type: root`; `components.foundational` → inline leaves in `composed_of` with `target_medal`; `components.feature` + `components.auxiliary` → `context_refs`; `allure_report_url` moves from root to the inline leaf that owns the report.

- [ ] **Step 1: Migrate `products/discourse.yaml`**

```yaml
id: discourse
product_type: root
name: "Discourse"
description: "An open-source, community- and customer-friendly discussion platform."
lifecycle: stable
target_medal: silver
ownership:
  squad: americas
  stakeholders:
    - "IS"
    - "Community Team"
  users:
    - "Internal Canonical"
    - "Ubuntu community"
documentation_url: "https://charmhub.io/discourse-k8s"
composed_of:
  - id: discourse-k8s
    product_type: charm
    source:
      repo: canonical/discourse-k8s-operator
    target_medal: silver
    allure_report_url: "https://canonical.github.io/discourse-k8s-operator/_latest"
context_refs:
  - label: "PostgreSQL K8s"
    repo: canonical/postgresql-k8s-operator
  - label: "Redis K8s"
    repo: canonical/redis-k8s-operator
  - label: "NGINX Ingress Integrator"
    repo: canonical/nginx-ingress-integrator-operator
```

- [ ] **Step 2: Migrate `products/matrix.yaml`**

```yaml
id: matrix
product_type: root
name: "Matrix (Synapse)"
description: "Open-standard chat for secure real-time collaboration"
lifecycle: stable
target_medal: gold
ownership:
  squad: americas
  stakeholders:
    - "IS Operations"
    - "Community Team"
  users:
    - "PFE"
documentation_url: "https://charmhub.io/synapse"
composed_of:
  - id: synapse
    product_type: charm
    source:
      repo: canonical/synapse-operator
    target_medal: gold
    allure_report_url: "https://canonical.github.io/synapse-operator/_latest"
  - id: saml-integrator
    product_type: charm
    source:
      repo: canonical/saml-integrator-operator
    target_medal: gold
context_refs:
  - label: "PostgreSQL K8s"
    repo: canonical/postgresql-k8s-operator
  - label: "Synapse Stats Exporter"
    repo: canonical/synapse-operator
```

- [ ] **Step 3: Migrate `products/netbox.yaml`**

```yaml
id: netbox
product_type: root
name: "NetBox"
description: "The world's most popular ecosystem for operating, automating, and securing networks and infrastructure."
lifecycle: stable
target_medal: bronze
ownership:
  squad: emea
  stakeholders:
    - "IS"
  users:
    - "IS Network team"
documentation_url: "https://netboxlabs.com/"
composed_of:
  - id: netbox-k8s
    product_type: charm
    source:
      repo: canonical/netbox-k8s-operator
    target_medal: bronze
    allure_report_url: "https://canonical.github.io/netbox-k8s-operator/_latest"
```

- [ ] **Step 4: Migrate `products/wazuh.yaml`**

```yaml
id: wazuh
product_type: root
name: "Wazuh"
description: "A platform that unifies XDR and SIEM protection for endpoints and cloud workloads."
lifecycle: stable
target_medal: silver
ownership:
  squad: emea
  stakeholders:
    - "Security Operations"
  users:
    - "Security Operations Team"
documentation_url: "https://wazuh.com/"
composed_of:
  - id: wazuh-server
    product_type: charm
    source:
      repo: canonical/wazuh-server-operator
    target_medal: silver
    allure_report_url: "https://canonical.github.io/wazuh-server-operator/_latest"
  - id: wazuh-indexer
    product_type: charm
    source:
      repo: canonical/wazuh-indexer-operator
    target_medal: silver
  - id: wazuh-dashboard
    product_type: charm
    source:
      repo: canonical/wazuh-dashboard-operator
    target_medal: silver
context_refs:
  - label: "Traefik K8s"
    repo: canonical/traefik-k8s-operator
```

- [ ] **Step 5: Migrate the remaining 4 products (`wordpress-k8s.yaml`, `indico.yaml`, `mattermost.yaml`, `jenkins.yaml`)**

Read each file, then apply the same pattern:
1. Add `product_type: root`
2. Move `components.foundational` entries to `composed_of` inline leaves — each with `target_medal` matching the root's `target_medal` and `allure_report_url` from root level (or empty string if none)
3. Move `components.feature` and `components.auxiliary` to `context_refs` (label = the component `id`, repo = the component's `github_repo`)
4. Remove `allure_report_url` from root level (it now lives on the charm leaf)
5. Remove the `components:` block entirely

- [ ] **Step 6: Validate all products**

```
make validate
```

Expected:
```
✓ config/dimensions.yaml
✓ products/discourse.yaml
✓ products/matrix.yaml
... (all 8 products)
All files valid.
```

- [ ] **Step 7: Migrate `computed/*.json` to new `leaf_metrics` envelope**

Run this script from the repo root:

```bash
python3 - <<'EOF'
import json, yaml, pathlib

products_dir = pathlib.Path("products")
computed_dir = pathlib.Path("computed")

for prod_path in sorted(products_dir.glob("*.yaml")):
    prod = yaml.safe_load(prod_path.read_text())
    prod_id = prod["id"]
    computed_path = computed_dir / f"{prod_id}.json"
    if not computed_path.exists():
        continue
    old = json.loads(computed_path.read_text())
    if "leaf_metrics" in old:
        print(f"Already migrated: {computed_path}")
        continue
    # Map old metrics to the first inline leaf
    leaves = [e for e in prod.get("composed_of", []) if "id" in e]
    if not leaves:
        print(f"Skipping {prod_id}: no inline leaves")
        continue
    first_leaf_id = leaves[0]["id"]
    new_data = {
        "product_id": prod_id,
        "computed_at": old.get("computed_at", ""),
        "leaf_metrics": {
            first_leaf_id: old.get("metrics", {})
        }
    }
    computed_path.write_text(json.dumps(new_data, indent=2) + "\n")
    print(f"Migrated {computed_path} → leaf_metrics.{first_leaf_id}")
EOF
```

- [ ] **Step 8: Run all Python tests**

```
make test
```

Expected: all tests pass

- [ ] **Step 9: Commit**

```bash
git add products/ computed/
git commit -m "feat: migrate all product YAMLs and computed files to graph schema"
```

---

### Task 6: Update scorer contracts

**Files:**
- Modify: `scorers/*/logic.py` (5 files)
- Modify: `scorers/*/scorer.py` (5 files)
- Modify: `scorers/*/__tests__/test_logic.py` (5 files)

**Interfaces:**
- Consumes: `EvaluationUnit` from `engine.models` (Task 2)
- Produces: `compute_metrics(unit: EvaluationUnit, ...) -> dict[str, Any]`
- Scorer output: `{"leaf-product-id": {"metric": value, ...}, ...}` — one entry per leaf, consumed by `merge_computed.py`

- [ ] **Step 1: Update `scorers/test_verification/logic.py`**

Change the function signature and replace `product`-dict access with `unit` fields:

```python
from engine.models import EvaluationUnit

def compute_metrics(unit: EvaluationUnit, github_token: str | None = None) -> dict[str, Any]:
    """
    Fetch test metrics from the evaluation unit's Allure report URL.
    Checks uses_ops_testing and uses_jubilant against unit.repo.
    """
    coverage_pct = 0
    stability_pct = 0
    latest_build_passing = False

    url = unit.allure_report_url.strip()
    if url:
        summary_url = url.rstrip("/") + "/widgets/summary.json"
        resp = requests.get(summary_url, timeout=30)
        resp.raise_for_status()
        stat = resp.json().get("statistic", {})
        total = stat.get("total", 0)
        if total > 0:
            passed = stat.get("passed", 0)
            failed = stat.get("failed", 0)
            broken = stat.get("broken", 0)
            coverage_pct = round(passed / total * 100)
            stability_pct = round((total - failed - broken) / total * 100)
            latest_build_passing = failed == 0 and broken == 0

    uses_ops = False
    uses_jub = False
    if github_token and unit.repo:
        uses_ops = _uses_ops_testing([unit.repo], github_token)
        uses_jub = _uses_jubilant([unit.repo], github_token)

    return {
        "coverage_pct": coverage_pct,
        "stability_pct": stability_pct,
        "latest_build_passing": latest_build_passing,
        "uses_ops_testing": uses_ops,
        "uses_jubilant": uses_jub,
    }
```

Remove the old `_all_repos` helper (no longer needed — scorers run per leaf).

- [ ] **Step 2: Update `scorers/test_verification/scorer.py`**

```python
#!/usr/bin/env python3
"""test_verification scorer — iterates leaf products and outputs per-leaf metrics."""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from engine.graph import build_graph, resolve_leaf_units
from scorers.test_verification.logic import compute_metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-yaml", required=True)
    args = parser.parse_args()

    product = yaml.safe_load(Path(args.product_yaml).read_text())
    graph = build_graph([product])
    units = resolve_leaf_units(graph)
    github_token = os.environ.get("GITHUB_TOKEN")

    results = {}
    for unit in units:
        results[unit.product_id] = compute_metrics(unit, github_token=github_token)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Update `scorers/test_verification/__tests__/test_logic.py`**

Replace product-dict fixtures with `EvaluationUnit` fixtures:

```python
import responses as resp_lib
from engine.models import EvaluationUnit, ProductType
from scorers.test_verification.logic import compute_metrics

UNIT = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
    allure_report_url="https://canonical.github.io/synapse-operator/_latest",
)

UNIT_NO_ALLURE = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
    allure_report_url="",
)


def test_returns_zeros_when_no_allure_url():
    result = compute_metrics(UNIT_NO_ALLURE)
    assert result["coverage_pct"] == 0
    assert result["stability_pct"] == 0
    assert result["latest_build_passing"] is False


@resp_lib.activate
def test_coverage_from_allure_summary():
    resp_lib.add(
        resp_lib.GET,
        "https://canonical.github.io/synapse-operator/_latest/widgets/summary.json",
        json={"statistic": {"total": 100, "passed": 87, "failed": 0, "broken": 0}},
        status=200,
    )
    result = compute_metrics(UNIT)
    assert result["coverage_pct"] == 87
    assert result["latest_build_passing"] is True


@resp_lib.activate
def test_build_failing_when_failures_present():
    resp_lib.add(
        resp_lib.GET,
        "https://canonical.github.io/synapse-operator/_latest/widgets/summary.json",
        json={"statistic": {"total": 100, "passed": 90, "failed": 5, "broken": 5}},
        status=200,
    )
    result = compute_metrics(UNIT)
    assert result["latest_build_passing"] is False
    assert result["stability_pct"] == 90
```

- [ ] **Step 4: Run test_verification tests**

```
pytest scorers/test_verification/ -v
```

Expected: all tests pass

- [ ] **Step 5: Update `scorers/documentation/logic.py`**

Change signature to `compute_metrics(unit: EvaluationUnit, github_token: str, openrouter_api_key: str, model: str = "anthropic/claude-sonnet-4.5") -> dict[str, Any]`.

Replace `primary = _primary_repo(product)` with `primary = unit.repo or None`.
Replace `doc_url = product.get("documentation_url", "")` with `doc_url = unit.documentation_url.strip()`.
Remove `_primary_repo` helper function.

- [ ] **Step 6: Update `scorers/documentation/scorer.py`** — same pattern as test_verification scorer.py (iterate leaf units via `resolve_leaf_units`, pass `openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")`)

- [ ] **Step 7: Update `scorers/documentation/__tests__/test_logic.py`** — replace product-dict fixtures with `EvaluationUnit` fixtures

- [ ] **Step 8: Update `scorers/substrate_compat/logic.py`**

Change signature to `compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]`.
Replace the foundational-repo loop with `_fetch_workflow_contents(unit.repo, github_token)` (single repo).
Remove `_primary_repo` helper and repo-list extraction.

- [ ] **Step 9: Update `scorers/substrate_compat/scorer.py`** — same pattern

- [ ] **Step 10: Update `scorers/substrate_compat/__tests__/test_logic.py`** — use `EvaluationUnit` fixtures

- [ ] **Step 11: Update `scorers/security_ssdlc/logic.py`**

Change signature to `compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]`.
Replace foundational-repo loop with single `unit.repo` for dependabot, codeql, and branch-protection checks.
Remove `_primary_repo` helper and foundational-repos extraction.

- [ ] **Step 12: Update `scorers/security_ssdlc/scorer.py`** and **`__tests__/test_logic.py`**

- [ ] **Step 13: Update `scorers/support_engagement/logic.py`**

Change signature to `compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]`.
Replace `foundational = product.get("components", {}).get("foundational", [])` and the loop with single `repo = unit.repo`.
Replace `primary = _primary_repo(product)` with `primary = unit.repo`.
Remove `_primary_repo` helper.

- [ ] **Step 14: Update `scorers/support_engagement/scorer.py`** and **`__tests__/test_logic.py`**

- [ ] **Step 15: Run all scorer tests**

```
pytest scorers/ -v
make lint
```

Expected: all scorer tests pass; lint clean

- [ ] **Step 16: Commit**

```bash
git add scorers/
git commit -m "feat: update all scorers to accept EvaluationUnit and output per-leaf dicts"
```

---

### Task 7: Update UI types and Overview

**Files:**
- Modify: `ui/src/types.ts`
- Modify: `ui/src/views/Overview.tsx`
- Modify: `ui/src/views/__tests__/Overview.test.tsx`

**Interfaces:**
- Consumes: new `portfolio.json` shape from Task 4
- Produces: updated TypeScript types; Overview filters to `is_portfolio_entry === true` products only

- [ ] **Step 1: Write failing UI tests for new product types**

In `ui/src/views/__tests__/Overview.test.tsx`, add or replace mock data with:

```typescript
// types.ts will be updated before these tests can pass
const rootProduct: Product = {
  id: 'matrix', product_type: 'root', name: 'Matrix', lifecycle: 'stable',
  target_medal: 'gold', current_medal: 'bronze', squad: 'americas',
  is_portfolio_entry: true, context_refs: [], parent_product_ids: [],
  composed_of: [{product_id: 'synapse', excluded_from_parent_medal: false}],
  dimensions: {},
}

const inlineLeaf: Product = {
  id: 'synapse', product_type: 'charm', name: 'Synapse', lifecycle: 'stable',
  target_medal: 'gold', current_medal: 'bronze', squad: '',
  is_portfolio_entry: false, context_refs: [], parent_product_ids: ['matrix'],
  composed_of: null, source: {repo: 'canonical/synapse-operator', subpath: null},
  dimensions: {},
}

it('shows only portfolio entry products in table', () => {
  // render portfolio with [rootProduct, inlineLeaf]
  // expect Matrix to be visible, Synapse to not appear in table
})

it('excludes inline leaf products from stats counts', () => {
  // stats (at-target %, overdue, remediating) should count only portfolio entries
})
```

- [ ] **Step 2: Run failing tests**

```
cd ui && npm test -- --run Overview
```

Expected: FAIL (type errors due to missing fields)

- [ ] **Step 3: Replace `ui/src/types.ts` with new types**

```typescript
export type Medal = 'gold' | 'silver' | 'bronze' | 'unrated'
export type DriftStatus = 'remediating' | 'overdue'
export type Lifecycle = 'experimental' | 'beta' | 'stable' | 'legacy'
export type ProductType = 'root' | 'charm' | 'snap'
export type ApplicabilityOutcome = 'scored' | 'not_applicable' | 'insufficient_data'

export interface DriftInfo {
  status: DriftStatus
  first_seen_at: string
  deadline: string
}

export interface LeafDimensionResult {
  product_id: string
  repo: string
  medal: Medal
  applicability: ApplicabilityOutcome
  metrics: Record<string, string | number | boolean>
  excluded_from_parent_medal: boolean
}

export interface DimensionEntry {
  medal: Medal
  target: Medal
  applicability: ApplicabilityOutcome
  drift: DriftInfo | null
  metrics: Record<string, string | number | boolean>
  composition: LeafDimensionResult[] | null
}

export interface ComposedRef {
  product_id: string
  excluded_from_parent_medal: boolean
}

export interface ContextRef {
  label: string
  repo: string | null
}

export interface SourceRef {
  repo: string
  subpath: string | null
}

export interface Product {
  id: string
  product_type: ProductType
  name: string
  description?: string
  lifecycle: Lifecycle
  target_medal: Medal
  current_medal: Medal
  squad: string
  is_portfolio_entry: boolean
  documentation_url?: string
  source?: SourceRef
  composed_of: ComposedRef[] | null
  context_refs: ContextRef[]
  parent_product_ids: string[]
  dimensions: Record<string, DimensionEntry>
}

export interface MedalCriteria {
  criteria: string[]
}

export interface OutputMeta {
  label: string
  description: string
  type: string
  range: string
  ai_assisted?: boolean
}

export interface DimensionMeta {
  label?: string
  description?: string
  applies_to?: string[]
  aggregation?: string
  outputs?: Record<string, OutputMeta>
  medals: {
    bronze?: MedalCriteria
    silver?: MedalCriteria
    gold?: MedalCriteria
  }
}

export interface Portfolio {
  generated_at: string
  products: Product[]
  dimensions_meta: Record<string, DimensionMeta>
}
```

- [ ] **Step 4: Update `ui/src/views/Overview.tsx`**

In the `products` memo, filter to portfolio entries before filtering by search:
```typescript
const filtered = portfolio.products
  .filter(p => p.is_portfolio_entry)   // ← add this line
  .filter(p => /* existing search filter */)
```

In the `stats` memo, add the same filter:
```typescript
const portfolioProducts = portfolio.products.filter(p => p.is_portfolio_entry)
const total = portfolioProducts.length
const atTarget = portfolioProducts.filter(
  p => MEDAL_ORDER[p.current_medal] >= MEDAL_ORDER[p.target_medal]
).length
const overdue = portfolioProducts.filter(/* existing drift check */).length
const remediating = portfolioProducts.filter(/* existing drift check */).length
```

- [ ] **Step 5: Run UI tests**

```
cd ui && npm test -- --run Overview
```

Expected: all Overview tests pass

- [ ] **Step 6: Commit**

```bash
git add ui/src/types.ts ui/src/views/Overview.tsx ui/src/views/__tests__/Overview.test.tsx
git commit -m "feat: update UI types and Overview for product_type and is_portfolio_entry"
```

---

### Task 8: UI ProductDetail — leaf and root views

**Files:**
- Modify: `ui/src/views/ProductDetail.tsx`
- Modify: `ui/src/views/__tests__/ProductDetail.test.tsx`

**Interfaces:**
- Root products: dimensions table with expandable `CompositionImpact` section per dimension row; header counters; `context_refs` card
- Leaf products: dimensions table with direct metrics (no composition); "Part of: X" parent links in header

- [ ] **Step 1: Write failing tests for root and leaf product views**

In `ui/src/views/__tests__/ProductDetail.test.tsx`:

```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'
import ProductDetail from '../ProductDetail'
// import usePortfolio mock setup — follow existing test patterns in the file

const rootProduct: Product = {
  id: 'matrix', product_type: 'root', name: 'Matrix', lifecycle: 'stable',
  target_medal: 'gold', current_medal: 'bronze', squad: 'americas',
  is_portfolio_entry: true, documentation_url: 'https://charmhub.io/synapse',
  context_refs: [{label: 'PostgreSQL K8s', repo: 'canonical/postgresql-k8s-operator'}],
  parent_product_ids: [],
  composed_of: [{product_id: 'synapse', excluded_from_parent_medal: false}],
  dimensions: {
    test_verification: {
      medal: 'bronze', target: 'gold', applicability: 'scored', drift: null, metrics: {},
      composition: [{
        product_id: 'synapse', repo: 'canonical/synapse-operator',
        medal: 'bronze', applicability: 'scored',
        metrics: {coverage_pct: 65, latest_build_passing: true},
        excluded_from_parent_medal: false,
      }],
    },
  },
}

const leafProduct: Product = {
  id: 'synapse', product_type: 'charm', name: 'Synapse Charm', lifecycle: 'stable',
  target_medal: 'gold', current_medal: 'bronze', squad: '',
  is_portfolio_entry: false,
  context_refs: [], parent_product_ids: ['matrix'],
  composed_of: null, source: {repo: 'canonical/synapse-operator', subpath: null},
  dimensions: {
    test_verification: {
      medal: 'bronze', target: 'gold', applicability: 'scored', drift: null,
      metrics: {coverage_pct: 65, latest_build_passing: true},
      composition: null,
    },
  },
}

it('root product shows composition count in header', () => {
  // render rootProduct — expect "1 composed product" text
})

it('root product shows context refs card', () => {
  // render rootProduct — expect "Dependencies (context only)" section
  // expect "PostgreSQL K8s" listed
})

it('root product dimension row shows composition expand button', () => {
  // render rootProduct — expect "1 component in scope" expand button
})

it('clicking composition expands to show leaf breakdown', () => {
  // render rootProduct, click "1 component in scope"
  // expect synapse product_id visible
})

it('leaf product shows Part of chip', () => {
  // render leafProduct with matrix in portfolio
  // expect "Part of:" label and "Matrix" chip
})

it('leaf product shows direct metrics without composition layer', () => {
  // render leafProduct — expect coverage_pct visible, no composition expand button
})
```

- [ ] **Step 2: Run failing tests**

```
cd ui && npm test -- --run ProductDetail
```

Expected: FAIL

- [ ] **Step 3: Update `ui/src/views/ProductDetail.tsx`**

Add `import React from 'react'` at top if not present.

Add `MEDAL_ORDER` constant:
```typescript
const MEDAL_ORDER: Record<Medal, number> = { gold: 3, silver: 2, bronze: 1, unrated: 0 }
```

Add `CompositionImpact` component (above `ProductDetail`):
```tsx
function CompositionImpact({ composition }: { composition: LeafDimensionResult[] }) {
  const [expanded, setExpanded] = React.useState(false)
  const inScope = composition.filter(
    c => !c.excluded_from_parent_medal && c.applicability === 'scored'
  )
  const worst = inScope.length > 0
    ? inScope.reduce((a, b) => MEDAL_ORDER[a.medal] <= MEDAL_ORDER[b.medal] ? a : b)
    : null

  return (
    <div>
      <button
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
        style={{
          fontSize: '0.75rem', background: 'none', border: 'none',
          cursor: 'pointer', color: '#06c', padding: 0, textDecoration: 'underline',
        }}
      >
        {expanded ? '▾' : '▸'} {composition.length} component{composition.length !== 1 ? 's' : ''} in scope
      </button>
      {expanded && (
        <div style={{ marginTop: '0.5rem', paddingLeft: '1rem', borderLeft: '2px solid #e5e5e5' }}>
          {composition.map(c => (
            <div
              key={c.product_id}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.25rem 0', fontSize: '0.875rem' }}
            >
              <MedalBadge medal={c.medal} size="small" />
              <span style={{ fontWeight: c.product_id === worst?.product_id ? 600 : 400 }}>
                {c.product_id}
              </span>
              {c.product_id === worst?.product_id && (
                <span style={{ fontSize: '0.6875rem', color: '#C7162B' }}>← worst</span>
              )}
              {c.excluded_from_parent_medal && (
                <span style={{ fontSize: '0.6875rem', color: '#666' }}>excluded</span>
              )}
              {c.applicability === 'not_applicable' && (
                <span style={{ fontSize: '0.6875rem', color: '#666' }}>N/A</span>
              )}
              {c.repo && (
                <a href={`https://github.com/${c.repo}`} target="_blank" rel="noreferrer"
                   style={{ fontSize: '0.75rem', color: '#666' }}>
                  {c.repo} ↗
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

In the product header card, add after the squad row:

1. Parent product chips (for leaf products):
```tsx
{product.parent_product_ids.length > 0 && (
  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
    <span className="u-text--muted" style={{ fontSize: '0.75rem' }}>Part of:</span>
    {product.parent_product_ids.map(parentId => {
      const parent = portfolio.products.find(p => p.id === parentId)
      return parent ? (
        <Link key={parentId} to={`/products/${parentId}`}
              className="p-chip" style={{ fontSize: '0.75rem', textDecoration: 'none', padding: '0.15rem 0.5rem' }}>
          {parent.name}
        </Link>
      ) : null
    })}
  </div>
)}
```

2. Composition counters (for root products):
```tsx
{product.product_type === 'root' && product.composed_of && (
  <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
    <div>
      <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>COMPOSED OF</span>
      <span>{product.composed_of.length} product{product.composed_of.length !== 1 ? 's' : ''}</span>
    </div>
    {product.context_refs.length > 0 && (
      <div>
        <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>CONTEXT DEPS</span>
        <span>{product.context_refs.length}</span>
      </div>
    )}
  </div>
)}
```

In the dimensions table Evidence cell, replace `MetricsList` with conditional rendering:
```tsx
<td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
  {entry.composition && entry.composition.length > 0 ? (
    <CompositionImpact composition={entry.composition} />
  ) : (
    <MetricsList
      metrics={entry.metrics}
      thresholds={targetThresholds}
      metaOutputs={dimMeta?.outputs}
    />
  )}
</td>
```

Replace the old Components card with a Context Dependencies card:
```tsx
{product.context_refs.length > 0 && (
  <div className="p-card u-sv3">
    <h2 className="p-heading--4" style={{ marginBottom: '0.5rem' }}>Dependencies (context only)</h2>
    <p className="u-text--muted" style={{ fontSize: '0.875rem', marginBottom: '0.75rem' }}>
      These dependencies are shown for context. They are not owned by this squad and do not affect the medal score.
    </p>
    <ul className="p-list" style={{ marginBottom: 0 }}>
      {product.context_refs.map((cr, i) => (
        <li key={i} className="p-list__item"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0' }}>
          <span>{cr.label}</span>
          {cr.repo && (
            <a href={`https://github.com/${cr.repo}`} target="_blank" rel="noreferrer"
               style={{ fontSize: '0.875rem', color: '#666' }}>
              {cr.repo} ↗
            </a>
          )}
        </li>
      ))}
    </ul>
  </div>
)}
```

- [ ] **Step 4: Run all UI tests**

```
cd ui && npm test
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add ui/src/views/ProductDetail.tsx ui/src/views/__tests__/ProductDetail.test.tsx
git commit -m "feat: ProductDetail with composition impact for root products and parent links for leaves"
```

---

### Task 9: Playwright visual validation

This task validates the full rendered UI using playwright-cli. No code files are modified; any issues found here are fixed before the final commit.

- [ ] **Step 1: Regenerate `public/portfolio.json` from migrated products**

```bash
python3 engine/assemble.py \
  --products-dir products/ \
  --computed-dir computed/ \
  --dimensions config/dimensions.yaml \
  --drift-history drift-history.json \
  --output public/portfolio.json
```

Verify the output contains root products with `product_type: "root"` and `composition` arrays in dimensions.

- [ ] **Step 2: Start the Vite dev server**

```bash
cd ui && npm run dev &
sleep 4
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/
```

Expected: `200`

- [ ] **Step 3: Open playwright-cli and navigate to the portfolio overview**

```
playwright-cli open
playwright-cli goto http://localhost:5173/
playwright-cli snapshot
playwright-cli screenshot
```

Verify in snapshot:
- Product table shows root products (matrix, discourse, wazuh, etc.)
- Inline leaf products (synapse, discourse-k8s, etc.) do NOT appear as rows
- Stats cards show counts
- No TypeScript/React errors in console

- [ ] **Step 4: Navigate to a root product and verify composition impact**

```
playwright-cli goto http://localhost:5173/products/matrix
playwright-cli snapshot
playwright-cli screenshot
```

Verify:
- Header shows "COMPOSED OF: 2 products" (synapse + saml-integrator)
- Dimensions table rows each have a "N components in scope" expand button instead of flat metric chips
- "Dependencies (context only)" card shows PostgreSQL K8s and Synapse Stats Exporter

- [ ] **Step 5: Expand a composition impact row**

```
playwright-cli click "[aria-expanded='false']"
playwright-cli snapshot
playwright-cli screenshot
```

Verify:
- Leaf breakdown visible with medal badges per leaf
- Worst component marked with "← worst"
- GitHub repo links present

- [ ] **Step 6: Navigate to a leaf product (via URL)**

```
playwright-cli goto http://localhost:5173/products/synapse
playwright-cli snapshot
```

Verify:
- "Part of: Matrix (Synapse)" chip visible in header
- Dimensions table shows direct metrics (coverage_pct etc.) — no composition expand button
- No "Dependencies (context only)" card (leaf has no context_refs)

- [ ] **Step 7: Navigate to the Dimensions overview and a dimension detail**

```
playwright-cli goto http://localhost:5173/
playwright-cli click "text=test_verification"
playwright-cli snapshot
playwright-cli screenshot
playwright-cli close
```

Verify: dimension detail page loads without errors, shows product scores

- [ ] **Step 8: Stop dev server and run full test suite**

```bash
kill %1
make test-all
```

Expected: all Python and UI tests pass

- [ ] **Step 9: Fix any issues found during validation, then commit**

```bash
git add -A
git commit -m "fix: UI corrections from Playwright visual validation"
```

(Skip this commit if no issues were found.)

---

### Task 10: Update documentation

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/adding-a-product.md`
- Modify: `docs/adding-a-dimension.md`

- [ ] **Step 1: Update `docs/architecture.md`**

Replace the Data Flow diagram with:
```
products/*.yaml          config/dimensions.yaml
      │                          │
      │           ┌──────────────┘
      ▼           ▼
  engine/graph.py              (builds product graph; extracts inline leaves)
      │
      ▼
  evaluation units             (one per leaf product: repo + optional subpath)
      │
      ▼
  scorers/{dim}/scorer.py      (per evaluation unit; outputs per-leaf metric dict)
      │
      ▼
  computed/{product}.json      (leaf_metrics envelope; GHA-written, never hand-edited)
      │
      ▼
  engine/assemble.py           (worst-in-scope aggregation → medals; portfolio assembly)
      │
      ├─► public/portfolio.json    (single data source for UI)
      └─► public/badges/
      │
      ▼
  ui/ (React 19 + Vite)
      │
      ▼
  GitHub Pages
```

Add a new section **Product Graph Model** after Component Responsibilities that covers:
- `product_type` enum and what each means
- inline vs standalone leaf rule (with the 3-criterion decision table)
- context refs: definition and medal exclusion guarantee
- scoring deduplication by (repo, subpath)
- follow-up note: GHA deduplication is a planned improvement

Update the computed/ row in Component Responsibilities: describe `leaf_metrics` envelope.

- [ ] **Step 2: Rewrite `docs/adding-a-product.md`**

Replace the old schema examples with the new `product_type: root` + `composed_of` + `context_refs` format.

Show two full examples:
1. Single-charm product (netbox-style):
```yaml
id: netbox
product_type: root
name: "NetBox"
description: "..."
lifecycle: stable
target_medal: bronze
ownership:
  squad: emea
documentation_url: "https://netboxlabs.com/"
composed_of:
  - id: netbox-k8s
    product_type: charm
    source:
      repo: canonical/netbox-k8s-operator
    target_medal: bronze
    allure_report_url: "https://canonical.github.io/netbox-k8s-operator/_latest"
```

2. Multi-charm product (wazuh-style):
```yaml
id: wazuh
product_type: root
name: "Wazuh"
description: "..."
lifecycle: stable
target_medal: silver
ownership:
  squad: emea
documentation_url: "https://wazuh.com/"
composed_of:
  - id: wazuh-server
    product_type: charm
    source:
      repo: canonical/wazuh-server-operator
    target_medal: silver
    allure_report_url: "https://canonical.github.io/wazuh-server-operator/_latest"
  - id: wazuh-indexer
    product_type: charm
    source:
      repo: canonical/wazuh-indexer-operator
    target_medal: silver
context_refs:
  - label: "Traefik K8s"
    repo: canonical/traefik-k8s-operator
```

Add **When to use `composed_of` vs `context_refs`** decision box:

> Use `composed_of` (inline leaf) when:
> - Your squad owns the quality of this charm/snap
> - It belongs to exactly this one root product
>
> Use `composed_of` with `ref:` when:
> - It is a standalone product that also gets tracked independently (its own product YAML)
>
> Use `context_refs` when:
> - It is owned by another squad
> - You only want it visible for context, not affecting your medal

Remove all references to `components.foundational/feature/auxiliary`.

- [ ] **Step 3: Update `docs/adding-a-dimension.md`**

Add `applies_to` and `aggregation` to the YAML template:
```yaml
  my_dimension:
    label: "My Dimension"
    description: "One sentence."
    scorer: scorers/my_dimension/scorer.py
    applies_to:
      product_types: [charm, snap]   # which product types this dimension scores
    aggregation: worst_in_scope
    outputs:
      ...
    medals:
      ...
```

Update `logic.py` template signature to accept `EvaluationUnit`:
```python
from engine.models import EvaluationUnit

def compute_metrics(unit: EvaluationUnit, github_token: str | None = None) -> dict[str, Any]:
    # use unit.repo, unit.subpath, unit.allure_report_url, unit.documentation_url
    ...
```

Update scorer.py template to iterate leaf units:
```python
product = yaml.safe_load(Path(args.product_yaml).read_text())
graph = build_graph([product])
units = resolve_leaf_units(graph)
results = {}
for unit in units:
    results[unit.product_id] = compute_metrics(unit, github_token=github_token)
print(json.dumps(results, indent=2))
```

Update the test template to use `EvaluationUnit` fixture:
```python
from engine.models import EvaluationUnit, ProductType

UNIT = EvaluationUnit(
    product_id="test-charm",
    product_type=ProductType.CHARM,
    repo="canonical/test-repo",
)

def test_returns_defaults_when_no_token():
    result = compute_metrics(UNIT)
    assert result["some_boolean"] is False
```

Add explanation: *"If your dimension only applies to charms, set `applies_to.product_types: [charm]`. Root products automatically return `not_applicable` for this dimension and are not penalized in their medal calculation."*

- [ ] **Step 4: Run full test suite to confirm docs changes broke nothing**

```
make test-all
make validate
make lint
```

Expected: all green

- [ ] **Step 5: Commit**

```bash
git add docs/
git commit -m "docs: update architecture, adding-a-product, and adding-a-dimension for graph model"
```

---

## Follow-ups (out of scope)

- **GHA `compute-metrics.yml` update:** The workflow currently runs scorers per root product. It should be updated to resolve and iterate leaf evaluation units, enabling true `(repo, subpath)` deduplication when the same charm is shared across multiple root products. This is a separate PR.
- **Standalone leaf product YAMLs:** The tooling supports `ref:` links to standalone leaf products. Create `products/postgresql-k8s.yaml` (and others) when the team wants to track individual charms independently in the portfolio.
- **Mono-repo subpath scoring:** A charm in `canonical/backup-operators` with `source.subpath: charms/backup` is modelled in the schema and graph. Scorer logic updates to scope GitHub API calls to the subpath are a follow-up once that product is onboarded.
