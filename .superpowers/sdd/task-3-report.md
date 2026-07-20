# Task 3 Report: Aggregation Engine + Updated Medal Engine

**Status:** ✅ DONE  
**Date:** 2026-07-16  
**Branch:** reason-through-sub-products-feedback

---

## Summary

Task 3 completed successfully via TDD. All 157 Python tests pass (+ 1 xfailed), lint clean.

## Commit

**SHA:** 91c0960  
**Subject:** feat: worst-in-scope aggregation and graph-aware medal engine

---

## Files Changed

| File | Action | Notes |
|------|--------|-------|
| `engine/aggregation.py` | Created | `compute_leaf_applicability()` + `aggregate_root_dimension()` |
| `engine/medal_engine.py` | Modified | Added `compute_leaf_product()` + `compute_root_product()`; kept `compute_product()` |
| `engine/__tests__/test_aggregation.py` | Created | 9 TDD tests (written before implementation) |
| `engine/__tests__/test_medal_engine.py` | Modified | Added `_DIMENSIONS_WITH_APPLICABILITY` fixture + 4 `compute_leaf_product` tests |

---

## TDD Sequence

1. **RED:** Wrote `test_aggregation.py` (exact from brief) → `ModuleNotFoundError` confirmed
2. **GREEN:** Implemented `engine/aggregation.py` → 9/9 pass
3. Added `compute_leaf_product()` and `compute_root_product()` to `medal_engine.py`
4. Added `_DIMENSIONS_WITH_APPLICABILITY` + 4 new tests to `test_medal_engine.py`
5. `make test` → 157 passed, 1 xfailed (baseline was 144; +13 new tests)
6. `make lint` → 4 E501 (line-too-long in test files)
7. `make format` → auto-fixed; lint clean

---

## Key Design Decision: `compute_product()` Retained

The brief specified rewriting `medal_engine.py` with only the two new functions. However, `assemble.py` and `__main__.py` (Task 4 scope) still import `compute_product`. Removing it would break `test_assemble.py` and `test_integration.py`, violating the `make test` requirement.

**Resolution:** Kept `compute_product()` as a legacy backward-compat function (no applicability filtering semantics) alongside the new functions. Task 4 will migrate callers and remove it.

---

## Concerns

**Minor:** `compute_product()` creates slight duplication in `medal_engine.py`. Intentional — Task 4 will clean up.

**Note for Task 4:** Dimensions in `config/dimensions.yaml` will need `applies_to` entries for `compute_leaf_product` to score them correctly. Without `applies_to`, all dimensions return `NOT_APPLICABLE` when processed by the new code path.

---

## Task 3 Fixup (2026-07-16)

**SHA:** af1a1c8  
**Subject:** fix: absent applies_to defaults to all types, remove broken drift in aggregation, add compute_root_product tests

### Fixes Applied

1. **Fix 1 (Critical):** `compute_leaf_applicability` — absent `applies_to` now treated as "applies to all types". Previously, missing `applies_to` defaulted to `[]` and silently failed every product type.

2. **Fix 2 (Important):** Removed broken `compute_dimension_drift("", ...)` call from `aggregate_root_dimension`. Drift is now unconditionally `None` at root level; root drift to be tracked by `assemble.py`. Removed unused `drift_tracker` import from `aggregation.py`.

3. **Fix 3 (Important):** Added 4 new tests: `test_leaf_applicability_no_applies_to_defaults_to_applicable`, `test_compute_root_product_aggregates_leaf`, `test_compute_root_product_missing_leaf_skipped`, `test_compute_root_product_excluded_leaf_not_counted`.

**Test result:** 161 passed, 1 xfailed — lint clean.

### Note

The "Note for Task 4" above (about needing `applies_to` entries) is now resolved: absent `applies_to` correctly falls through to SCORED/INSUFFICIENT_DATA rather than NOT_APPLICABLE.


---

# Task 3 Report: Implement root-vs-leaf classifier with overrides (2026-07-20)

Summary
-------
Implemented classify_product_role(product, overrides=None) in engine/catalog_discovery.py and added a unit test enforcing override behavior in engine/__tests__/test_catalog_discovery.py.

What changed
------------
- Added classify_product_role(product: dict, overrides: dict[str,str]|None = None) -> str
  - If overrides contains product['id'] -> return override
  - Else, find components where role == 'primary' and type in {k8s-charm, machine-charm, subordinate-charm, snap}
  - If any primary component -> 'root', else 'leaf'
- Added test: test_classifier_respects_force_leaf_override
- Kept canonical docs id rename map (wordpress -> wordpress-k8s) and mapping of product.service_level -> target_medal
- Preserved documentation_url and links handling
- Ensured deployments and communication fields are excluded from normalize_docs_product outputs

Verification
------------
- Ran the single new test: engine/__tests__/test_catalog_discovery.py::test_classifier_respects_force_leaf_override — PASSED
- Ran full test suite: 160 passed, 0 failed

Commits
-------
- feat: add root-vs-leaf classifier with override support
  - Files: engine/catalog_discovery.py, engine/__tests__/test_catalog_discovery.py
  - Commit SHA (HEAD): b891c7a

Concerns / Notes
----------------
- Overrides must use the canonical docs id (after renames). Callers should canonicalize IDs before passing overrides.
- Primary component type set is explicit; extend set if new component types warrant root classification.
- This change only implements the classifier and unit test; UI discovery reporting remains out of scope for this commit.

Report file path
----------------
.superpowers/sdd/task-3-report.md

---

End of Task 3 report.


## Reviewer Fixes (2026-07-20)

Applied fixes requested by Task 3 reviewer:

1. Enforced override contract in engine/catalog_discovery.py::classify_product_role:
   - Normalize known case variants and return only 'root' or 'leaf' (lowercase).
   - Reject non-string overrides with TypeError.
   - Reject unknown override values with explicit ValueError.
   - Preserve behavior for valid overrides.

2. Added tests in engine/__tests__/test_catalog_discovery.py:
   - test_default_root_classification_without_override
   - test_invalid_override_raises

Test evidence
-------------
- Command: pytest engine/__tests__/test_catalog_discovery.py -v
- Result: 7 passed

Commit
------
- SHA: 0a360fc
- Message: catalog_discovery: validate override outputs; normalize to 'root'/'leaf'; add tests for default root and invalid override

Concerns
--------
- Callers passing overrides should canonicalize product IDs (rename map) before use.


### Reviewer Fixes Applied (2026-07-20)

Status: ✅ Remaining Task 3 review findings fixed (only the two requested items)

Fixes:
1) normalize_pqf_product(): restrict `ownership` to only include `squad` (drop other ownership metadata).
2) classify_product_role(): canonicalize product id when looking up overrides (respect rename map such as wordpress -> wordpress-k8s).

Commit: 51efa17

One-line test summary: engine/__tests__/test_catalog_discovery.py — 8 passed

Concerns:
- None beyond caller awareness: override dict keys should use canonical ids when possible; classifier now checks both raw and canonical ids.

Report path: .superpowers/sdd/task-3-report.md

---

# Task 3 Reviewer Fixes Applied (2026-07-20)

Status: ✅ Done

Commits:
- SHA: 7fa5f73
  - Message: "catalog discovery: deterministic override lookup precedence; support legacy/canonical override keys both directions"
  - Files: engine/catalog_discovery.py, engine/__tests__/test_catalog_discovery.py

One-line test summary: engine/__tests__/test_catalog_discovery.py — 10 passed

Concerns:
- None. Deterministic precedence implemented (exact id -> canonical -> legacy); both override key forms supported and validated.

Report path: .superpowers/sdd/task-3-report.md
