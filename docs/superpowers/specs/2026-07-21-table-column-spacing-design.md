# UX: Table and Dependency Column Spacing Refinement

**Date:** 2026-07-21  
**Status:** Draft  
**Branch:** chore-add-missing-products

---

## Problem Statement

Two UI surfaces still allocate space poorly even after the dependency alignment fix:

1. **Product detail → Dependencies → Sub-products**
   - The row now aligns, but the product-name column is still too dominant.
   - The repo column does not get enough space relative to its content.
   - Type is predictable and should remain compact.

2. **Products page table**
   - The Product column is too tight and can overflow visually.
   - Type, Target, and Squad consume more width than their content requires.
   - The Repo column is too small for the expected repo strings.

The goal is not to redesign these views, but to rebalance column widths so the most informative content gets the most space while compact metadata stays compact.

---

## Decisions Made

| Question | Decision |
|----------|----------|
| Priority columns | Product and Repo get the most width |
| Compact columns | Type, Target, Squad stay intentionally small and stable |
| Overflow behavior | Long Product/Repo content truncates with ellipsis instead of distorting layout |
| Products page structure | Keep semantic HTML table, do not convert to CSS grid |
| Dependencies structure | Keep grid rows, but rebalance the grid tracks |

---

## Approaches Considered

### 1. Explicit width strategy per surface (**recommended**)

- Keep the current semantics:
  - detail page dependency rows stay CSS grid
  - products page stays an HTML table
- Introduce explicit width allocation instead of relying on mostly content-driven sizing

**Pros**
- Lowest churn
- Predictable across browsers
- Easy to regression-test
- Preserves accessibility and existing structure

**Cons**
- Needs tuning of a few concrete width values

### 2. Convert both surfaces to CSS grid

- Replace the products table with a grid-based layout to match the dependency rows

**Pros**
- Full control over track sizing everywhere

**Cons**
- Higher implementation risk
- More layout churn
- Worse fit for the products explorer, which is genuinely tabular data

### 3. Keep current structure and only tweak padding/font sizes

**Pros**
- Smallest code change

**Cons**
- Does not solve the actual width-allocation problem
- Likely to regress or still feel imbalanced

---

## Recommended Design

### 1. Product detail dependency rows

Keep the existing four-column grid, but rebalance the tracks so Product is primary without being greedy, and Repo gets a guaranteed useful width.

#### Column intent

1. **Medal** — fixed compact
2. **Product** — flexible primary column
3. **Type** — fixed compact
4. **Repo** — flexible but bounded secondary column

#### Sizing strategy

- Move from a highly product-dominant layout to a more balanced split:
  - `auto minmax(0, 1.1fr) auto minmax(14rem, 0.9fr)` or equivalent
- Preserve:
  - `min-width: 0` on shrinkable cells
  - ellipsis on Product and Repo links
  - nowrap on Type

#### Expected result

- Product names still read comfortably
- Repo links no longer feel squeezed against the far edge
- Type stays visually compact
- Rows remain aligned even in stricter browsers

---

### 2. Products page table

Keep the semantic table, but make width allocation explicit using column sizing rather than letting content heuristics dominate.

#### Column intent

1. **Product** — widest column
2. **Type** — compact fixed width
3. **Medal** — compact fixed width
4. **Target** — compact fixed width
5. **Squad** — compact fixed width
6. **Repo** — second widest column

#### Sizing strategy

Use a `<colgroup>` (or equivalent table-column styling) so widths are stable for both grouped and flat rows.

Recommended balance:

- Product: ~34–38%
- Type: fixed compact width
- Medal: fixed compact width
- Target: fixed compact width
- Squad: fixed compact width
- Repo: ~24–30%

Specific implementation can use percentages for Product/Repo and `rem`-based widths for the compact metadata columns.

#### Cell behavior

- Product cells:
  - allow truncation/ellipsis where needed
  - keep the tree connector intact for grouped leaf rows
- Repo cells:
  - allow truncation/ellipsis
  - do not force the row wider than its assigned column
- Type / Target / Squad:
  - remain nowrap
  - do not expand beyond their compact content needs

---

## Testing Strategy

### Product detail tests

Add or update tests to verify:

- dependency rows use the revised grid template
- shrinkable Product and Repo cells keep `min-width: 0`
- repo links remain ellipsized rather than forcing layout drift

### Products page tests

Add tests to verify:

- explicit column sizing is present
- Product and Repo cells opt into overflow-safe rendering
- compact columns remain fixed/nowrap

### Existing validation

After implementation:

- `make test-ui`
- `make build`
- live preview check on both:
  - `/products/matrix`
  - `/products`

---

## Out of Scope

- redesigning the products explorer information architecture
- changing which columns exist
- making the products table responsive via card stacking
- changing medal semantics or product data
- broader typography or spacing redesign outside these two surfaces

