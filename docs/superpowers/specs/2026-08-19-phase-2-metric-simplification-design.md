# Phase 2 Metric Simplification Design

## Goal

Turn Phase 2 from an audit-only exercise into a concrete simplification pass that makes PQF's documentation dimension honest, easier to understand, and more useful for baseline portfolio reasoning.

## Problem statement

The current documentation dimension is too strict for the portfolio as it exists today:
- `readme_meets_structure` and `contributing_meets_structure` are effectively detecting a specific doc template rather than whether the repo has the required documents.
- `documentation_workflows_passing` is useful evidence, but it is too immature and naming-sensitive to gate medals right now.
- Some products are modeled as top-level charm/snap entries while also being owned through a root product. `saml-integrator` is one example: it is a top-level product, but `matrix` already references it via `composed_of`.

This creates false negatives and prevents PQF from showing a meaningful baseline spread.

## Scope

In scope:
- simplify documentation metric semantics to baseline presence checks,
- rename the documentation outputs so they describe what they actually measure,
- move documentation workflow evidence to informational-only,
- enforce the stricter product-ownership model for scoring,
- document and verify the effect through local scoring.

Out of scope:
- broadening documentation maturity beyond baseline presence,
- changing other dimensions,
- changing portfolio model semantics beyond the orphan/top-level charm/snap rule,
- UI changes.

## Design

### 1. Documentation metric simplification

Replace the current structure-oriented documentation metrics with presence-oriented metrics:
- `readme_meets_structure` -> `readme_present`
- `contributing_meets_structure` -> `contributing_present`

These new metrics should be deterministic and minimal:
- file exists,
- file is non-empty,
- no template-shape or heading taxonomy requirement.

`has_security` remains as-is.

`documentation_workflows_passing` should remain emitted by the scorer, but it must stop participating in medal gating. It becomes informational only.

The documentation rubric should use the baseline presence checks only:
- bronze: `readme_present`, `contributing_present`, `has_security`
- silver/gold: deferred until a separate maturity metric exists

### 2. Product ownership and scoring model

Use the stricter ownership model:
- a charm/snap must be either:
  - part of a root product's `composed_of`, or
  - an inline leaf under a root product.
- top-level charm/snap product YAMLs without an owning root context are not independently scorable.

For `resolve_leaf_units_for(graph, root_product_id)`, if the product has no `composed_of` leaves that resolve to charm/snap units, the scorer should fail with a clear error rather than silently returning an empty set.

This keeps ownership clear and prevents orphan top-level product YAMLs from producing misleading empty scores.

### 3. `saml-integrator` relationship

`saml-integrator` should be treated as part of another product rather than as a standalone scorable root in this path. The current catalog already reflects this through `matrix`'s `composed_of` reference.

The expected outcome is that `matrix` continues to score `saml-integrator` through composition, while a direct standalone score request for `saml-integrator` is rejected as structurally unsupported unless its ownership model is changed.

### 4. Documentation and history

Update the contributor-facing guidance so future work preserves the calibration philosophy:
- keep metrics simple,
- distinguish measured-low from unmeasured,
- use only sanctioned structural variants,
- keep immature signals informational until they are reliable enough to gate medals.

Record the remaining calibration phases in the roadmap document so this simplification work stays anchored to the larger calibration effort.

## Validation

The change is correct when:
- documentation metrics rename cleanly in the scorer, config, and tests,
- documentation medals no longer depend on workflow gating,
- standalone top-level charm/snap scoring fails fast with a clear structural error,
- `matrix` still resolves `saml-integrator` through composition,
- local scoring produces a more realistic spread after the simplification.

## Testing

Minimum validation:
- unit tests for the renamed documentation metrics,
- unit tests for the documentation workflow metric becoming informational,
- graph/scoring tests for the stricter ownership model,
- a targeted local score run for `matrix` and `saml-integrator`.

