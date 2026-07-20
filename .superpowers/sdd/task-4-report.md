# Task 4 Report: Updated assemble.py + new portfolio JSON shape

## Status

DONE

## Commits

- `b140c25` feat: update assemble.py and merge_computed.py for graph-aware portfolio

## Test Summary

162 passed, 1 xfailed — all tests green across engine and scorer suites.

## What Was Done

### TDD Approach

1. **Replaced `engine/__tests__/test_assemble.py`** with the new 6-test suite from the brief. Confirmed 4/6 tests failed immediately (old code missing `product_type`, `applicability`, `context_refs`, `applies_to`).

2. **Rewrote `engine/assemble.py`** with the graph-aware version:
   - Uses `build_graph` to build a `ProductGraph` from YAML files
   - Loads `leaf_metrics` envelope from computed JSON files (new format)
   - Calls `compute_leaf_product` for charm/snap nodes
   - Calls `compute_root_product` for root nodes
   - `_build_dimensions_meta` now emits `applies_to` and `aggregation` fields
   - `_result_to_dict` now takes `(result, node: ProductNode)` — emits `product_type`, `is_portfolio_entry`, `composed_of`, `context_refs`, `parent_product_ids`
   - `_dim_to_dict` serialises `applicability` and `composition` fields
   - **Key fix over brief**: filtered `products_out` by `node.is_portfolio_entry` so inline leaf products (e.g. `synapse`) do not appear as top-level portfolio entries

3. **Updated `engine/merge_computed.py`**: output assembly block now produces `leaf_metrics: {leaf-id: {dim: {metrics}}}` instead of `metrics: {dim: {metrics}}`.

4. **Fixed lint issues**: removed unused imports (`Medal`, `Path`, `yaml`), fixed import ordering, broke two long lines.

## Concerns

None. The brief's `products_out` list comprehension would have included inline leaves (violating `test_inline_leaf_not_in_top_level_products`). Added `and node.is_portfolio_entry` guard — this is the correct behaviour and is consistent with the `is_portfolio_entry` field already present on `ProductNode`.
: Portfolio Overview View

## Status: DONE

## Implementation Summary

Successfully implemented the Portfolio Overview view (`/`) with all specified features:

### Features Implemented

1. **Summary Statistics Cards**
   - At or above target percentage (calculates using MEDAL_ORDER)
   - Overdue products count
   - Remediating products count

2. **Search/Filter**
   - Input type="search" with aria-label
   - Filters by product name or squad (case-insensitive)
   - Instant client-side filtering

3. **Compliance Heatmap**
   - Table showing products × dimensions
   - Product names link to `/products/:id`
   - Dimension names link to `/dimensions/:id`
   - Shows MedalBadge (small) and DriftChip for each cell
   - Horizontal scroll for overflow

4. **Products Table**
   - Sortable columns: Product, Lifecycle, Current medal
   - Shows Target and Current medals as badges
   - Shows worst drift status (prioritizes 'overdue' over 'remediating')
   - Correct aria-sort attributes (ascending/descending/none)
   - Click header to sort, click again to reverse

5. **Footer**
   - Data generation timestamp (localized)
   - Link to "/about" page

### Technical Details

- **MEDAL_ORDER**: `{ gold: 4, silver: 3, bronze: 2, unrated: 1 }` for comparisons
- **Loading/Error States**: LoadingSpinner and error notification
- **Memoization**: `useMemo` for products, stats, and dimensions
- **Type Safety**: All props correctly typed, aria-sort uses correct HTML attributes
- **Shared Components**: Leverages MedalBadge, DriftChip, LoadingSpinner
- **Routing**: Uses react-router Link with HashRouter compatibility

### Tests

Created comprehensive test suite in `ui/src/views/__tests__/Overview.test.tsx`:

1. ✅ Shows page heading
2. ✅ Renders product name as link
3. ✅ Shows current medal
4. ✅ Filters by search input
5. ✅ Shows summary stat: 0% at target

**Test Result**: All 5 tests passing

### Build Verification

- ✅ TypeScript compiles cleanly (no errors)
- ✅ Build succeeds (`npm run build`)
- ✅ Bundle size: Overview-BKfGdQIT.js 14.33 kB (gzip: 4.88 kB)

## Commits

- **ba0b7a0** - feat: add Portfolio Overview view with heatmap and product table

## Self-Review Findings

### Spec Compliance ✅

- [x] Page heading "Portfolio overview" (p-heading--2)
- [x] Three summary stat cards in row/col-4 layout
- [x] Search input with type="search" and aria-label
- [x] Compliance heatmap with dimension columns
- [x] Product names link to `/products/:id`
- [x] Dimension names link to `/dimensions/:id`
- [x] MedalBadge size="small" in heatmap and table
- [x] DriftChip shown for drift entries
- [x] Sortable product table with aria-sort
- [x] Footer with timestamp and "About" link
- [x] Loading and error states handled
- [x] MEDAL_ORDER comparisons correct

### Code Quality ✅

- Clean functional components with hooks
- Proper memoization to avoid unnecessary re-renders
- Type-safe throughout (no `any` types)
- Accessible (searchbox, aria-sort, semantic HTML)
- Follows existing code patterns
- No unused imports or variables
- Proper error handling

### No Concerns

All requirements met. Implementation is production-ready.

## Files Modified

1. `ui/src/views/Overview.tsx` - Full implementation (203 lines)
2. `ui/src/views/__tests__/Overview.test.tsx` - New test file (5 tests)

## Next Steps

None required. Task complete and ready for integration.

---

**Completed**: 2026-06-30
**Author**: GitHub Copilot


## Task 4 - Field mapping and schema/UI gap report generation

Status: DONE

Commits:
- c62f5f0 feat: add field mapping and schema-ui gap reporting (engine/catalog_discovery.py, tests)

Test summary:
- Ran focused tests: engine/__tests__/test_catalog_discovery.py — 11 passed

Concerns:
- None. Implementation is conservative and limited to discovery reporting; it does not modify existing schemas or UI.

Report path: ./.superpowers/sdd/task-4-report.md

- Fixed build_gap_report to treat UI 'squad' as equivalent to 'ownership.squad' so UI ownership is not a false-positive.\n- Made build_field_mapping_report source-driven: it now reports mappings for actual docs_fields input and reflects missing/extra fields.\nTests: added unit tests covering both fixes.

### Lint-only fixes applied (2026-07-20)

- Commit: a088f3a - style: fix lint findings (sort imports, wrap long comment)
- Verification: make lint -> all checks passed; pytest engine/__tests__/test_catalog_discovery.py -v -> 13 passed
- Concerns: None
- Report path: ./.superpowers/sdd/task-4-report.md


### Task 4 follow-up fixes (2026-07-20)

- Commit: 004ccbb - catalog_discovery: preserve intended UI field targets and respect explicit empty docs_fields
- Verification: pytest engine/__tests__/test_catalog_discovery.py -v -> 15 passed
- Lint: make lint -> all checks passed
- Summary: build_field_mapping_report now preserves the intended ui_field target even when that field is not present in ui_product_fields, and treats an explicit empty docs_fields (set()) as a deliberate source-driven input producing an empty mapping list.

Report path: ./.superpowers/sdd/task-4-report.md
