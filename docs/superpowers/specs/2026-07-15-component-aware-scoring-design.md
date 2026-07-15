# Component-Aware PQF Scoring and UX Design (Hybrid Graph Model)

## Context

PQF currently treats a product mostly as a single scoring unit with component lists used primarily as documentation context. This breaks down for:

- products composed of multiple charms/snaps/rocks/sub-products,
- mixed ownership boundaries (team-owned vs external dependencies),
- mono-repos with multiple independently meaningful components,
- split-repo products with distributed component ownership and evidence,
- dimensions that logically apply to some component types but not others.

This design adopts a hybrid graph model that preserves summary-first UX while making component-level scoring and impact explicit.

## Goals

- Keep root product views simple and decision-friendly.
- Compute quality where it semantically belongs (component/repo/subpath level).
- Exclude external/context dependencies from medal impact by default.
- Support mono-repo and split-repo products with one model.
- Make component impact on root medals transparent and traceable.

## Non-Goals

- Backward compatibility with the current schema.
- Full “everything is always a first-class product” ontology in v1.
- Component-first dashboard as default landing UX.

## Decision Summary

1. Use a graph-native hybrid model.
2. Promote only team-owned independently tracked components to first-class products.
3. Default external dependencies to context-only (excluded from medal roll-up).
4. Use worst-in-scope component roll-up for root product dimension medals.
5. Represent non-applicable dimensions explicitly and exclude them from medal math.

## Domain Model

### Entity types

- `product` (root portfolio-facing product)
- `component` (typed as `charm`, `snap`, `rock`, `sub_product`, etc.)

### Relationships

- `composes` edges from product -> component (and optionally component -> component).

### Required component reference fields

- `component_id`: stable identifier
- `kind`: component type (`charm`, `snap`, `rock`, `sub_product`, ...)
- `ownership_boundary`: `team_owned` | `external`
- `evaluation_scope`: `in_medal` | `context_only`
- `independently_tracked`: boolean
- `source.repo`: `owner/repo`
- `source.subpath`: optional path for mono-repo component targeting

### First-class product promotion rule

A component is shown as its own product entry only when `independently_tracked=true` and it is intentionally managed as a team-owned tracked unit. Otherwise it remains a referenced component in parent product evidence.

## Scoring and Aggregation Model

### Evaluation unit

Scoring executes on an evaluation unit keyed by:

- `entity_id`
- `repo`
- optional `subpath`
- `entity_kind`

### Dimension applicability outcomes

Each dimension evaluation produces one of:

- `scored`
- `not_applicable`
- `skipped_out_of_scope`
- `insufficient_data`

### Roll-up rule for root product dimension medal

- Consider only `in_medal` + `team_owned` component evaluations with `scored`.
- Root dimension medal = **minimum** medal among those in-scope component evaluations (worst-in-scope).
- `not_applicable` is excluded from aggregation math.
- `skipped_out_of_scope` is visible in evidence but excluded from medal impact.
- If no applicable in-scope scored evaluation exists, root dimension returns `unrated` with explicit reason.

### Root product current medal

Current medal remains the minimum across applicable root dimension medals.

## Dimension Configuration Changes

Each dimension config includes:

- `applies_to.entity_types`: list of entity kinds
- optional `applies_to.capabilities`: predicates for applicability
- `aggregation`: initially `worst_in_scope` (extensible later)

Dimension definitions remain the contract for outputs and criteria, but now also define applicability and aggregation semantics.

## Engine Architecture

Pipeline:

1. Load product/component definitions and build entity graph.
2. Resolve evaluation units (repo and repo+subpath).
3. Run dimension scorers per evaluation unit.
4. Compute per-unit dimension medals via rubric rules.
5. Aggregate per-component and root product dimension results (worst-in-scope).
6. Emit portfolio payload including component evidence tree and exclusion rationale.

## Scorer Contract Changes

Scorers consume explicit evaluation context rather than assuming one primary repo:

- `repo`
- optional `subpath`
- `entity_kind`
- product/component metadata needed for the dimension

Outputs include provenance metadata for traceability in UI evidence:

- `entity_id`
- `dimension`
- `repo`
- `subpath` (if present)

## UI/UX Design

### Product Detail (default: summary-first)

Keep current top-level summary card and dimensions table as primary view.

Add per-dimension expandable **Component Impact**:

- list in-scope team-owned contributors,
- clearly identify the worst component driving rolled-up medal,
- list excluded external/context components in separate section with rationale badges.

### Drilldown evidence view

Provide a component evidence view showing:

- component identity and ownership boundary,
- repo/subpath evaluation target,
- applicability status (`scored`, `not_applicable`, `skipped_out_of_scope`, `insufficient_data`),
- metric values and derived medal.

### Header indicators

Add compact counters:

- in-scope components,
- excluded external dependencies,
- not-applicable dimensions.

This preserves clarity through progressive disclosure: simple by default, deep evidence on demand.

## Error Handling and Validation

Fail fast with explicit errors for:

- missing required component fields,
- duplicate/conflicting `component_id`,
- invalid graph links,
- invalid `source.subpath` resolution,
- invalid applicability/aggregation declarations.

No silent fallback to success-shaped defaults for graph/config integrity issues.

## Testing Strategy

- Engine unit tests:
  - graph construction and validation,
  - applicability state resolution,
  - worst-in-scope aggregation behavior,
  - non-applicable exclusion from medal calculation.
- Scorer tests:
  - repo-level vs repo+subpath evaluation behavior.
- UI tests:
  - summary-first render integrity,
  - component impact expansion states,
  - excluded external component representation.
- Integration fixtures:
  - mono-repo composition (e.g., backup-operators-style),
  - split-repo composition (wazuh-style),
  - self-contained single repo product (discourse-style).

## Open Questions Resolved

- External dependencies default behavior: excluded from medal, shown as context.
- First-class component products: only for independently tracked team-owned components.
- Mono-repo treatment: support repo + optional subpath selectors.
- Root UI default: summary-first with expandable component evidence.
- Aggregation default: worst-in-scope component wins.
- Non-applicable dimensions: explicit `not_applicable`, excluded from medal math.

## Implementation Readiness

This design is approved as a clean-slate target model for the current active-development phase of PQF and is ready for detailed implementation planning.
