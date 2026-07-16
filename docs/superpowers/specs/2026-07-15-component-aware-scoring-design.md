# Component-Aware PQF Scoring and UX Design (Hybrid Graph Model)

## Context

PQF currently treats a product mostly as a single scoring unit with component lists used primarily as documentation context. This breaks down for:

- products composed of multiple charms/snaps,
- mono-repos with multiple independently meaningful components (e.g. backup-operators),
- split-repo products where each charm lives in its own repo (e.g. Wazuh),
- external dependencies from other teams that should be visible but excluded from medal impact,
- dimensions that logically apply to some product types but not others.

This design adopts a hybrid graph model that preserves summary-first UX while making component-level scoring and impact explicit.

## Goals

- Keep root product views simple and decision-friendly.
- Compute quality where it semantically belongs (product/repo/subpath level).
- Exclude external/context dependencies from medal impact by default.
- Support mono-repo and split-repo products with one model.
- Make composed product impact on root medals transparent and traceable.
- Keep the number of product YAML files proportional to root products (~32), not leaf implementation details (~100+).

## Non-Goals

- Backward compatibility with the current schema.
- A "components without product definitions" model — untracked things are context refs, not partial products.
- Separate portfolio entities for OCI rocks — rocks are build artifacts of charms and have no independent portfolio presence.
- Component-first dashboard as default landing UX.

## Decision Summary

1. Every tracked entity is a **product** with a product YAML and a `product_type` (`root`, `charm`, `snap`).
2. `product_type` drives dimension applicability and UX — no per-product flags needed.
3. OCI rocks are build artifacts of charms, not separate portfolio products.
4. Leaf products (charms/snaps) that belong to exactly one root product are declared **inline** inside that root product YAML. Only shared or independently tracked leaf products get their own YAML file.
5. Composition is product-to-product (`composed_of` list); untracked external deps go in `context_refs`.
6. The engine deduplicates scoring by `(repo, subpath)` — the same repo scored twice (e.g. shared across two root products) runs once and reuses results.
7. Root products aggregate from composed products using worst-in-scope roll-up.
8. Context refs are excluded from all medal computation; `not_applicable` dimensions are excluded from medal math.

## Domain Model

### Product types

Everything scored and shown in the portfolio is a **product**. Products have a `product_type`:

- `root` — a product composed of other products (e.g. Matrix, Wazuh). Has no direct source repo of its own.
- `charm` — a Juju charm. Scored directly against its source repo (and optional subpath for mono-repos). Its rock(s) are build artifacts, not separate portfolio entities.
- `snap` — a Snap package. Scored directly against its source repo.
- _(extensible: further types added as enum values)_

### Inline leaf products vs standalone leaf products

To keep the file count proportional to root products rather than the full set of implementation artifacts, leaf products follow this rule:

**Inline** (declared inside the root product YAML):
- belongs to exactly one root product,
- is owned by the same team,
- would not be meaningfully browsed in isolation.

**Standalone** (its own `products/<id>.yaml`):
- shared across two or more root products, OR
- independently tracked and browsed on its own merit.

The engine treats both identically. The distinction is purely a file-organisation choice for human maintainability.

### Context references

Anything referenced by a product that is **not** a first-class tracked product — external dependencies, components from other teams, or things not substantial enough for their own product definition — is listed as a **context ref**. Context refs have:

- a display label
- a `repo` (optional, for linking to GitHub)
- no product definition, no scoring, no medal impact

Context refs are shown in the product UI for transparency but excluded from medal computation entirely.

### Relationships

- `composed_of` edges from root product -> leaf products, with optional `excluded_from_parent_medal: true` per edge for exceptional cases
- `context_refs` list on any product for display-only dependency information

### Product definition fields

**Root product YAML** (`products/<id>.yaml`):

```yaml
id: matrix
product_type: root
name: "Matrix (Synapse)"
description: "..."
lifecycle: stable
target_medal: gold
ownership:
  squad: americas
composed_of:
  - id: synapse              # inline leaf — defined here, owned by same team
    product_type: charm
    source:
      repo: canonical/synapse-operator
  - id: postgresql-k8s       # standalone leaf — has its own products/postgresql-k8s.yaml
    ref: postgresql-k8s
context_refs:
  - label: "NGINX Ingress Integrator"
    repo: canonical/nginx-ingress-integrator-operator
```

**Standalone leaf product YAML** (`products/<id>.yaml`):

```yaml
id: postgresql-k8s
product_type: charm
name: "PostgreSQL K8s"
description: "..."
lifecycle: stable
target_medal: gold
ownership:
  squad: data
source:
  repo: canonical/postgresql-k8s-operator
```

### Key invariants

- If it has a product YAML (inline or standalone), it is tracked and scored.
- A `ref:` in `composed_of` must match an existing standalone product YAML ID (hard validation error if not).
- Inline products belong to one and only one root product.
- Context refs are never in `composed_of` and never scored.
- `product_type: root` never has a `source.repo` — it has no scoreable source of its own.
- `product_type: charm | snap` always has `source.repo`.

## Scoring and Aggregation Model

### Evaluation unit

Scoring executes on an evaluation unit keyed by `(repo, subpath)`. This key is the canonical deduplication unit — if the same repo/subpath appears in multiple root products (e.g. a shared charm), it is scored exactly once and the cached result is reused for all parents.

Each evaluation unit also carries:
- `product_id`
- `product_type`
- `source.repo`
- optional `source.subpath`

Leaf products (`charm`, `snap`) are always scored directly. Root products are scored only by aggregating their composed products' results — they have no evaluation unit of their own.

### Dimension applicability

Each dimension declares which `product_type` values it applies to. Evaluating a dimension against an incompatible product type produces `not_applicable` — that product is excluded from any parent roll-up for that dimension.

Applicability outcomes:

- `scored` — evaluated and a medal awarded
- `not_applicable` — product type incompatible with this dimension
- `insufficient_data` — applicable but no data available (e.g. no Allure URL)

### Roll-up rule for root product dimension medal

- Consider only composed products whose edge does **not** have `excluded_from_parent_medal: true`.
- Root dimension medal = **minimum** medal among in-scope composed product evaluations (worst-in-scope wins).
- `not_applicable` and `insufficient_data` composed products are excluded from aggregation math.
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

1. Load all product YAMLs; extract inline leaf products from root product files.
2. Validate the product graph: no missing `ref:` targets, no circular composition, no duplicate IDs.
3. Resolve the deduplicated set of evaluation units by `(repo, subpath)`.
4. Run dimension scorers per evaluation unit; filter by `applies_to.product_types`.
5. Cache results by `(repo, subpath)` — the same repo scored for multiple root products uses the cached result.
6. Compute per-leaf-product dimension medals via rubric rules.
7. Aggregate into root product dimension results (worst-in-scope over non-excluded composed products).
8. Emit portfolio payload including composed product evidence tree with applicability states and context refs.

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

Keep current top-level summary card and dimensions table as primary view. Works for leaf and root products alike.

For **root products**, add per-dimension expandable **Composed Product Impact**:

- list composed products contributing to the dimension score,
- highlight the worst-scoring product driving the roll-up (clear visual indicator),
- show `not_applicable` / `insufficient_data` composed products as excluded with reason,
- show context refs in a separate "Dependencies (context only)" section with repo links.

For **leaf products** (charm/snap), the dimensions table shows metrics directly as today with no composition layer.

### Portfolio overview

All products — root and leaf (standalone only) — appear in the portfolio overview. Inline leaf products appear only within their parent root product's composition view, not as top-level portfolio rows. Standalone leaf products link back to their parent(s) with "Part of: X" chips.

### Header indicators (root products only)

Add compact counters to the root product header card:

- N composed products (in-scope for medal),
- N context-only dependencies (excluded).

### Progressive disclosure

Simple by default — product type determines what's shown. All composition evidence reachable within one click from the dimensions row.

## Error Handling and Validation

Fail fast with explicit errors for:

- `ref:` in `composed_of` targets a product ID that has no standalone product YAML,
- an inline leaf product ID collides with any standalone product ID,
- duplicate product IDs across any product files,
- `product_type` value not in the known enum,
- missing required fields (`source.repo` on leaf products, `product_type`, `ownership.squad`),
- `product_type: root` declaring a `source.repo` (roots have no direct source),
- `product_type: charm | snap` missing `source.repo`,
- circular composition graphs.

No silent fallback to success-shaped defaults for graph/config integrity issues.

## Testing Strategy

- Engine unit tests:
  - product graph construction and validation (missing refs, circular graphs, bad product_type, root with source.repo),
  - inline vs standalone leaf extraction,
  - deduplication of scoring by `(repo, subpath)` — same repo in two root products scores once,
  - dimension applicability resolution by `product_type`,
  - worst-in-scope aggregation behavior for root products,
  - `not_applicable` and `insufficient_data` exclusion from medal calculation.
- Scorer tests:
  - repo-level vs repo+subpath evaluation behavior.
- UI tests:
  - leaf product detail renders dimensions directly (no composition layer),
  - standalone leaf products appear in portfolio overview; inline leaf products do not,
  - root product detail renders composition impact expansion,
  - context refs shown in dependencies section, never in medal rows.
- Integration fixtures:
  - mono-repo root product (backup-operators-style: one repo, multiple charm subpaths, all inline),
  - split-repo root product (wazuh-style: multiple repos, inline leaf products per repo),
  - self-contained single-repo product (discourse-style: one charm, one repo, no composition),
  - shared leaf product (postgresql-k8s-style: standalone, referenced by multiple root products, scored once).

## Maintainer Guide

### When to inline a leaf product

Declare a leaf product **inline** in the root product YAML when all of the following are true:

1. It is owned by the same team as the root product.
2. It belongs to exactly one root product.
3. It would not be meaningfully browsed as a standalone portfolio entry.

### When to create a standalone leaf product YAML

Create a separate `products/<id>.yaml` when any of the following is true:

1. It is shared (composed into two or more root products).
2. It is independently tracked and meaningful as a standalone portfolio entry.
3. It is owned by a different team than the root product referencing it — in that case, consider whether it should be a `context_ref` instead.

### Rocks are not products

OCI rocks are build artifacts produced inside charm repositories. Do not create product YAMLs for rocks. The charm product that produces the rock is the tracked entity.

### Scoring deduplication

The engine scores by `(repo, subpath)`. If the same repo appears in multiple root products (because a charm is shared), it is scored once. You never need to worry about redundant compute or stale diverging results for shared repos.

### context_refs vs composed_of

Use `context_refs` for:
- external team dependencies you want visible in the UI for context
- infrastructure dependencies not owned by your squad

Use `composed_of` for:
- team-owned charms/snaps that directly contribute to the product's quality medal

If you're unsure: ask "does my squad own the quality of this thing?" If yes → `composed_of`. If no → `context_refs`.

## Open Questions Resolved

- Every tracked product has a product YAML (inline or standalone). No tracking flags needed.
- `product_type` drives dimension applicability — no per-product overrides needed.
- Rocks are build artifacts of charms, not separate portfolio products.
- Inline leaf products live inside their root product YAML; standalone leaves get their own file.
- Engine deduplicates scoring by `(repo, subpath)` — shared repos score once.
- External/untracked dependencies go in `context_refs`, never in `composed_of`.
- `ref:` in `composed_of` must resolve to an existing standalone product YAML ID (hard validation).
- Root products aggregate from composed products (worst-in-scope, excluding `not_applicable`).
- `excluded_from_parent_medal: true` per composition edge available for edge cases.
- Only standalone leaf products appear in the top-level portfolio overview.

## Implementation Readiness

This design is approved as a clean-slate target model for the current active-development phase of PQF and is ready for detailed implementation planning.
