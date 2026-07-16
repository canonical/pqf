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
- A "components without product definitions" model — untracked things are context refs, not partial products.
- Component-first dashboard as default landing UX.

## Decision Summary

1. Every tracked entity is a **product** with a product YAML and a `product_type` (`root`, `charm`, `snap`, `rock`, ...).
2. `product_type` drives dimension applicability and UX — no per-product flags needed.
3. Composition is product-to-product (`composed_of` list); untracked external deps go in `context_refs`.
4. Root products aggregate from composed products using worst-in-scope roll-up.
5. Context refs are excluded from all medal computation; `not_applicable` dimensions are excluded from medal math.

## Domain Model

### Entity types: products

Everything that is scored and shown in the portfolio is a **product**. Products have a product definition file (`products/<id>.yaml`) and a `product_type` that drives dimension applicability and UX:

- `root` — a product composed of other products and/or context refs (e.g. Matrix, Wazuh)
- `charm` — a Juju charm
- `snap` — a Snap package
- `rock` — an OCI/Rock image
- _(extensible: further types added as enum values without model changes)_

### Context references

Anything referenced by a product that is **not** a first-class tracked product — external dependencies, components from other teams, or things not substantial enough for their own product definition — is listed as a **context ref**. Context refs have:

- a display label
- a `repo` (optional, for linking to GitHub)
- no product definition, no scoring, no medal impact

Context refs are shown in the product UI for transparency but are excluded from medal computation automatically and completely.

### Relationships

- `composes` edges from product -> product (child product), with optional `excluded_from_parent_medal: true` per edge for exceptional cases
- `references` edges from product -> context ref (for context-only display)

### Product definition fields (revised)

Each product YAML declares:

- `id`: stable identifier (matches filename)
- `product_type`: `root` | `charm` | `snap` | `rock` | ...
- `name`, `description`, `lifecycle`, `target_medal`: as today
- `ownership.squad`: owning squad
- `source.repo`: `owner/repo` — the primary GitHub repository
- `source.subpath`: optional path for mono-repo targeting
- `composed_of`: list of product IDs this product is built from (each with optional `excluded_from_parent_medal`)
- `context_refs`: list of lightweight dependency refs (label + optional repo) for display only

### Key invariants

- If it has a product YAML, it is tracked and scored. No flags needed.
- If it is referenced as a composed product, that product YAML must exist (hard validation error if not).
- If it should not be scored, it goes in `context_refs`, not `composed_of`.
- `product_type` is the single knob controlling dimension applicability and which metrics make sense.

## Scoring and Aggregation Model

### Evaluation unit

Scoring executes on an evaluation unit keyed by:

- `product_id`
- `product_type`
- `source.repo`
- optional `source.subpath`

Leaf products (`charm`, `snap`, `rock`) are always scored directly. Root products are scored by aggregating their composed products' results.

### Dimension applicability

Each dimension declares which `product_type` values it applies to. Evaluating a dimension against an incompatible product type produces `not_applicable` and that product is excluded from any parent roll-up for that dimension.

Applicability outcomes:

- `scored`
- `not_applicable` — product type incompatible with this dimension
- `insufficient_data` — applicable but no data available (e.g. no Allure URL)

### Roll-up rule for root product dimension medal

- Consider only composed products where the `composed_of` edge does **not** have `excluded_from_parent_medal: true`.
- Root dimension medal = **minimum** medal among those in-scope composed product evaluations (worst-in-scope wins).
- `not_applicable` composed products are excluded from aggregation math.
- Context refs are never included in any medal computation.
- If no applicable scored composed product evaluation exists, root dimension returns `unrated` with explicit reason.

### Root product current medal

Current medal remains the minimum across applicable root dimension medals. Dimensions returning `not_applicable` for all composed products do not pull the root product's medal down.

## Dimension Configuration Changes

Each dimension config explicitly declares:

- `applies_to.product_types`: list of product types this dimension applies to (e.g. `[charm, snap]` but not `root`)
- `aggregation`: `worst_in_scope` (extensible later for per-dimension overrides)

Dimension definitions remain the contract for outputs, criteria, and medal rubrics. `applies_to` is the new addition that enables clean `not_applicable` resolution without per-product hacks.

## Engine Architecture

Pipeline:

1. Load all product YAMLs; validate `composed_of` references resolve to known products.
2. Build product graph (product-to-product edges + context refs).
3. Resolve evaluation units (product_id + repo + optional subpath) for leaf products.
4. Run dimension scorers per leaf product evaluation unit; filter by `applies_to.product_types`.
5. Compute per-leaf-product dimension medals via rubric rules.
6. Aggregate into root product dimension results (worst-in-scope over non-excluded composed products).
7. Emit portfolio payload including composed product evidence tree with applicability states and context refs.

## Scorer Contract Changes

Scorers consume an explicit evaluation context instead of assuming a single primary repo:

- `product_id`
- `product_type`
- `repo`
- optional `subpath`
- product metadata needed for the dimension

Outputs include provenance metadata for traceability in UI evidence:

- `product_id`
- `dimension`
- `repo`
- `subpath` (if present)

## UI/UX Design

### Product Detail (default: summary-first)

Keep current top-level summary card and dimensions table as primary view. Works for leaf products (charm/snap/rock) and root products alike.

For **root products**, add per-dimension expandable **Composed Product Impact**:

- list composed products contributing to the dimension score,
- highlight the worst-scoring product driving the roll-up (with a clear visual indicator),
- show `not_applicable` composed products as excluded with reason,
- show context refs in a separate "Dependencies (context only)" section with repo links.

For **leaf products** (charm/snap/rock), the dimensions table shows metrics directly as today, with no composition layer.

### Portfolio overview

All products — root and leaf — appear in the portfolio overview. Leaf products that are composed into root products show a "Part of: X" link. Root products show an expandable composition summary.

### Header indicators (root products only)

Add compact counters to the root product header card:

- N composed products (in-scope for medal),
- N context-only dependencies (excluded).

### Progressive disclosure

Simple by default — product type determines what's shown. All composition evidence reachable within one click from the dimensions row.

## Error Handling and Validation

Fail fast with explicit errors for:

- `composed_of` references a product ID that does not have a product YAML,
- duplicate product IDs across product files,
- `product_type` value not in the known enum,
- missing required fields (`source.repo`, `product_type`, `ownership.squad`),
- circular composition graphs,
- invalid `source.subpath` that cannot be resolved for a known repo.

No silent fallback to success-shaped defaults for graph/config integrity issues.

## Testing Strategy

- Engine unit tests:
  - product graph construction and validation (missing refs, circular graphs, bad product_type),
  - dimension applicability resolution by `product_type`,
  - worst-in-scope aggregation behavior for root products,
  - `not_applicable` and `insufficient_data` exclusion from medal calculation.
- Scorer tests:
  - repo-level vs repo+subpath evaluation behavior.
- UI tests:
  - leaf product detail renders dimensions directly,
  - root product detail renders composition impact expansion,
  - context refs shown in dependencies section, never in medal rows.
- Integration fixtures:
  - mono-repo root product (backup-operators-style: one repo, multiple charm subpaths),
  - split-repo root product (wazuh-style: multiple repos, each its own product),
  - self-contained single-repo product (discourse-style: one charm, one repo, no composition).

## Open Questions Resolved

- Every tracked product has a product YAML. No tracking flags needed.
- `product_type` drives dimension applicability — no per-product overrides needed.
- External/untracked dependencies go in `context_refs`, never in `composed_of`.
- `composed_of` references must resolve to existing product YAMLs (hard validation).
- Root products aggregate from composed products (worst-in-scope, excluding `not_applicable`).
- `excluded_from_parent_medal: true` per composition edge available for edge cases.
- All products (leaf and root) appear in the portfolio.

## Implementation Readiness

This design is approved as a clean-slate target model for the current active-development phase of PQF and is ready for detailed implementation planning.
