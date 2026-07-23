# UI metric observability design

Date: 2026-07-23
Owner: PQF maintainers
Status: Approved for planning

## Context

PQF scoring is currently hard to audit across products. The UI lacks fast ways to:

1. Compare dependency quality by dimension on a product page.
2. See dimension scores in root/sub-product grouping (same mental model as Products).
3. Inspect one metric across all roots and sub-products to validate metric quality.

This design addresses those gaps without backend changes.

## Goals

- Make dimension-level and metric-level score behavior observable across the portfolio.
- Reuse one grouping model so Product, Dimension, and Metric views stay consistent.
- Preserve existing `portfolio.json` contract and route structure where possible.

## Non-goals

- No scorer logic changes in this iteration.
- No new API/service; keep static-data architecture.
- No major visual redesign of global navigation.

## Chosen approach

Approach A (selected): build shared grouped-row primitives and reuse them across all three view changes.

Why:
- avoids duplicated root/leaf grouping logic,
- keeps sorting/filtering behavior aligned,
- lowers maintenance cost for future metric audits.

## Architecture

Add a shared UI transformation layer (pure functions) that derives:

- grouped product rows (`root -> leaves`)
- per-dimension cell model for heatmaps
- per-metric distribution rows with tier pass/fail flags

Suggested location:
- `ui/src/lib/groupedPortfolioView.ts` (or equivalent existing utility folder)

Consumers:
- `ProductDetail` dependencies panel
- `DimensionDetail` product scores table
- new `MetricDistribution` view

## Data flow

Input source remains `usePortfolio()` (`public/portfolio.json`).

Derived data:
- root/leaf membership from `product_type`, `composed_of`, and product index lookup
- dimension medals from `product.dimensions[dimensionId].medal`
- metric values from:
  - leaf `composition[].metrics` when viewing root-context grouped data
  - direct product dimension metrics when applicable
- pass/fail by tier from `dimensions_meta[dimensionId].medals.*.criteria`

No data mutation; all computations are in-memory and deterministic.

## UX changes

### 1) Product Detail dependencies as heatmap

Replace current sub-products list-only emphasis with a compact dimension heatmap table:
- rows: sub-products
- columns: dimensions
- cells: medal badges for that sub-product in that dimension

Keep existing dependency links (sub-products, PE-owned, external) below/adjacent so navigation behavior is preserved.

### 2) Dimension Detail grouped product scores

Change Product Scores section to mirror Products grouping style:
- root row first
- indented/tree-connected leaves beneath root
- same medal presentation and concise repo context

This lets users reason dimension scores using the same hierarchy they use elsewhere.

### 3) Dedicated metric distribution route

Add route:
- `/dimensions/:dimensionId/metrics/:metricKey`

Entry point:
- metric rows in Dimension view become links to this route.

Page content:
- grouped root/leaf table by default
- raw metric value column
- bronze/silver/gold pass/fail indicators for that metric where criteria exist
- filters: squad, medal, product type, and optional “show only failures”

## Error handling and edge cases

- Missing metric value: render `—` and mark tier checks as not evaluable.
- Metric not referenced in a tier: show `N/A` for that tier.
- Non-applicable dimension entries: preserve existing applicability semantics and render neutral cells.
- Invalid route metric/dimension: show existing not-found/notification pattern with back links.

## Testing strategy

Unit tests:
- shared grouping and metric evaluation utilities
- criterion parsing for single-metric tier checks
- edge cases: booleans, numbers, missing values, absent criteria

View tests:
- `ProductDetail.test.tsx`: dependency heatmap rows/columns/cells
- `DimensionDetail.test.tsx`: grouped root/leaf ordering and links
- new `MetricDistribution.test.tsx`: filters + tier pass/fail rendering

Verification commands:
- `make test-ui`
- `make ci-check`

## Rollout notes

- Ship all three UI improvements in one cycle (user-requested).
- After merge, use new metric page to drive metric-by-metric scorer logic calibration work.
