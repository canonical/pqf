# UX: Evidence Restoration and Product Navigation Redesign

**Date:** 2026-07-17  
**Status:** Draft  
**Branch:** reason-through-sub-products-feedback

---

## Problem Statement

The component-aware scoring PR introduced a structural data change: root products no longer store
metrics directly on `DimensionEntry.metrics` (which is now `{}`). All metric data lives inside
`DimensionEntry.composition[].metrics` per leaf product. As a result, the per-metric evidence
table — the most actionable part of the product page — is no longer rendered. Users cannot see
individual metric values, threshold comparisons, or which specific metric is causing a poor medal.

Additionally, leaf/sub-products are only discoverable by accident (through the Dimension Detail
page), and the product hierarchy is not navigable in a first-class way.

---

## Decisions Made

| Question | Decision |
|----------|----------|
| Root product metric display | Show worst-leaf value per metric with target threshold coloring; ▸ expand reveals per-leaf breakdown |
| Target medals / drift | Root products only. Leaf pages show computed medal, no target or drift. |
| Metric threshold coloring on root page | Yes — colored against the root's target threshold |
| Sub-product navigation | Keep Overview root-only; add new `/products` page showing all types in hierarchy |
| Dependencies section layout | One unified card: composed_of first (scored, linked), then context_refs (not scored) |

---

## Design

### 1. Evidence display for root products

**Current state:** The Evidence column shows a `▸ N components in scope` button with no metric
values visible until expanded. The expanded view shows leaf names + medals only, not individual
metric values.

**New behaviour:**

For each dimension row of a root product:

- The Evidence cell renders a `<RootMetricsList>` component instead of `<CompositionImpact>`
- For each metric declared in `dimensions_meta[dim].outputs`:
  - Show the **worst value across all in-scope leaves for that specific metric** (not worst
    overall leaf — each metric independently picks the leaf with the worst value for it, so
    `coverage_pct` might show synapse's value while `stability_pct` shows a different leaf's)
  - "Worst" means: for `>=` / `>` thresholds — the lowest value; for `<=` / `<` thresholds — the
    highest value; for `==` thresholds — prefer `false` over `true`
  - Display with the same red/green threshold coloring as `MetricsList` today
  - If leaves disagree on the value: append a small `▸ N leaves` expand control inline
  - On expand: show per-leaf sub-rows (leaf name + their value for that metric, leaf whose value
    is shown at top level bolded)
  - When all leaves agree on a value for a metric (all equal), no expand control is shown — just
    the value

Example (Matrix / test_verification, 2 leaves):
```
Coverage       0%▸2 leaves    ← red (worst = synapse: 0%, target ≥70%)
  synapse        0%           ← bolded (worst)
  saml-int.      70%
Stability      0% ▸2 leaves   ← red
Build passing  ✗  ▸2 leaves   ← red
Ops testing    ✗              ← (both agree: ✗, no expand)
Jubilant       ✗              ← (both agree: ✗)
```

**For leaf/standalone product pages:** no change — renders `MetricsList` directly with target
threshold coloring (same as old main behaviour).

**Target threshold on root page:** The root product's `target_medal` is used to look up thresholds
in `dimensions_meta[dim].medals[target_medal].criteria`. This is already done today. The worst-leaf
value is compared against this threshold.

---

### 2. Composed-of chips in product header

**Current state:** Header shows "COMPOSED OF: 2 products" (a static count, not clickable).

**New behaviour:** Replace the count with linked chips for each leaf:
```
COMPONENTS
[synapse ↗]  [saml-integrator ↗]
```
Each chip links to `/products/<leaf-id>`. The chip label is the leaf's `product_id` (the product
name if available from the portfolio).

---

### 3. Dependencies card (unified)

**Current state:** Card is titled "Dependencies (context only)" and only shows `context_refs`.
The `composed_of` sub-products are not shown here.

**New behaviour:** Rename to "Dependencies". Two sub-sections in one card:

**Sub-products** (from `composed_of`):
- Each shown as a row with: product name (link to `/products/<id>`), product type chip, source
  repo link (from portfolio lookup)
- Label: "Scored — included in medal calculation"

**Context dependencies** (from `context_refs`):
- Each shown as a row with: label, repo link
- Label: "Context only — not scored by this team"

If `composed_of` is empty (standalone leaf product or root with no leaves), this sub-section is
omitted. If `context_refs` is empty, that sub-section is omitted. If both are empty, the card
is hidden.

---

### 4. Leaf product pages

Leaf products already have pages at `/products/:id`. Changes:

- **No target medal shown.** Remove the CURRENT / TARGET medal pair. Show only CURRENT medal with
  a label "Computed medal". No drift chip.
- **"Part of:" chips** (already implemented) — keep as-is, link to root product page.
- **Evidence:** Render `MetricsList` directly using the leaf's `entry.metrics`. No threshold
  coloring (no target to compare against).
- **No Dependencies card** unless the leaf itself has `context_refs` (unlikely but possible).

---

### 5. New Products page (`/products`)

A dedicated page accessible from the nav. Nav label: **Products**.

**Layout:** Grouped by root product. For each root:
- Root product row: name (link), product_type chip, current medal, squad
- Indented leaf rows: name (link), product_type chip, current medal, source repo link

For leaf products with no root parent (standalone leaves, `is_portfolio_entry: true`): shown in
a separate section "Standalone Products".

**Filters:** Product type (root / charm / snap), squad.

**This page is the canonical place to discover all products.** The Overview page continues to show
only root products.

---

### 6. Navigation updates

**GlobalNav:** Add "Products" link between "Portfolio" and "Dimensions":
```
Portfolio  |  Products  |  Dimensions  |  About  |  Docs ↗
```
Route: `/products`.

**App router:** Add `<Route path="/products" element={<ProductsExplorer />} />`.

---

## What is NOT changing

- Overview page: continues to show only root products (`is_portfolio_entry: true` + `product_type: root`)
- DimensionDetail page: no changes (already shows per-product medals correctly)
- Medal aggregation logic (engine): no changes
- Drift tracking: root products only, no change to engine

---

## Component breakdown

| Component / File | Change |
|-----------------|--------|
| `ui/src/views/ProductDetail.tsx` | Split rendering for root vs leaf; add `RootMetricsList`; fix composed_of chips; fix Dependencies card |
| `ui/src/components/RootMetricsList.tsx` | New component: worst-value display with per-leaf expand |
| `ui/src/views/ProductsExplorer.tsx` | New view: all products grouped by root |
| `ui/src/App.tsx` | Add `/products` route |
| `ui/src/components/GlobalNav.tsx` | Add Products nav item |
| `ui/src/views/__tests__/ProductDetail.test.tsx` | Update tests for new root/leaf rendering |
| `ui/src/views/__tests__/ProductsExplorer.test.tsx` | New tests |

---

## Out of scope

- Inline expand of leaf rows in Overview (deferred to future)
- Target medals per leaf product
- Root product drift changes
- Engine changes
