# Metric Page Target-Contextual Threshold Result Design

**Tracking:** Metric Distribution semantics fix  
**Author:** Copilot  
**Date:** 2026-08-24  
**Status:** Design phase

---

## Problem Statement

The Metric Distribution page currently shows `Threshold result` by evaluating a metric across the full rubric, not the product’s current target tier. That creates confusing rows such as:

- a bronze-target product showing `Sub-min` for a metric that only starts at silver,
- the same metric showing `—` in `Gap to target`,
- informational metrics still appearing to participate in medal-style status text.

This is misleading because the page is supposed to answer a narrower question:

> “For this product, does this metric matter at its current target tier?”

The page should not imply that a metric is sub-minimum when the target tier does not define that metric at all.

## Goal

Make `Threshold result` on Metric Distribution target-contextual:

- if the metric is introduced by the product’s target tier, evaluate it there;
- if the metric is not introduced by the product’s target tier, show `N/A`;
- keep engine/scoring policy unchanged.

## Scope

In scope:

- Metric Distribution row semantics,
- target-tier applicability checks,
- `Threshold result` display logic,
- `Gap to target` consistency when a metric is not applicable to the product’s target tier.

Out of scope:

- medal rubric changes in `config/dimensions.yaml`,
- engine scoring changes,
- product-level medal computation,
- informational metric criteria hiding (already handled separately).

## Design

### 1. Introduce target-tier applicability for metric rows

For each metric row, determine whether the product’s target tier actually defines a criterion for the current metric.

- If the target tier has a criterion for the metric:
  - evaluate the metric value against that tier.
- If the target tier does not have a criterion for the metric:
  - mark the metric as `N/A` for `Threshold result`,
  - return no gap value (`—`) for `Gap to target`.

This means a bronze-target product with a metric introduced at silver no longer shows `Sub-min`; it shows `N/A`.

### 2. Keep global rubric semantics out of this page’s status column

`Threshold result` should stop answering “did the metric fail anywhere in the rubric?”
Instead, it should answer “how does this metric compare to the product’s current target tier?”

This preserves the distinction between:

- **Metric Distribution** = target-contextual per-product view,
- **dimension scoring** = overall rubric aggregation.

### 3. Preserve existing engine behavior

The engine and portfolio JSON should remain unchanged.

This change is only about how the UI interprets already-computed metric evidence:

- same metric values,
- same tier criteria,
- different interpretation on the page.

### 4. Keep gap display consistent with applicability

When a metric is not introduced by the target tier, `Gap to target` should not try to manufacture a comparison. It should stay `—`.

That keeps the page internally consistent:

- `Threshold result: N/A`
- `Gap to target: —`

for metrics outside the target tier.

## Validation

The change is correct when:

- `release_notes_process_implemented` on a bronze-target product shows `N/A`, not `Sub-min`,
- `contributing_present` on a bronze-target product still shows a concrete result when bronze defines that metric,
- informational metrics do not become sub-minimum just because they have higher-tier evidence,
- engine-derived product medals stay unchanged.

## Testing

Minimum validation:

- unit tests for a bronze-target metric that starts at silver returning `N/A`,
- unit tests for a bronze-target metric defined in bronze still returning a concrete result,
- UI tests that verify `Threshold result` and `Gap to target` stay aligned for in-scope and out-of-scope metrics.
