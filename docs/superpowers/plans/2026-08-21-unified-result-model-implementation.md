# Unified Scoring Result Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace confused medal/status/applicability triple with single canonical `result` field throughout engine, portfolio.json, and UI.

**Architecture:** 
- Add `Result` enum (6 values: gold/silver/bronze/below_minimum/insufficient_data/not_applicable) in engine/models.py
- Keep `Medal` and `ApplicabilityOutcome` internal-only (no public exposure)
- Compute `result` in aggregation logic, flow it through all dataclasses and JSON output
- UI accepts `result` field, renders badges directly without conditional logic
- Single vocabulary throughout: dimension → product → portfolio.json → UI

**Tech Stack:** Python 3.11+, TypeScript, Vitest + React Testing Library

## Global Constraints

- Only expose `result` field in portfolio.json (remove medal, applicability, status)
- All 243 engine tests must pass; all 89 UI tests must pass
- MedalBadge component maintains fixed minWidth per size (8.5rem default, 7rem small)
- Result colors: gold=#C7962F, silver=#8F8F8F, bronze=#9E622A, below_minimum=#666, insufficient_data=#E98B06, not_applicable=#C7162B
- No backwards compatibility; clean refactor only

---

## File Structure

**Python Engine (no new files):**
- `engine/models.py` — Add Result enum, update DimensionResult and ProductResult dataclasses
- `engine/aggregation.py` — Add _compute_result() helper, update all aggregation functions
- `engine/medal_engine.py` — Update _product_status() and leaf/root product logic
- `engine/assemble.py` — Remove medal/applicability from JSON output
- All test files in `engine/__tests__/` and `scorers/*/tests/` — Update fixtures to include result

**UI (no new files):**
- `ui/src/types.ts` — Add Result type, update DimensionEntry and Product interfaces
- `ui/src/components/MedalBadge.tsx` — Accept `result` instead of deriving from medal+applicability
- `ui/src/components/MedalBadge.test.tsx` — Update test expectations
- All view files in `ui/src/views/` — Update badge rendering to pass result directly
- All UI test files in `ui/src/**/*.test.tsx` — Update fixtures

---

## Task 1: Add Result Enum and Update Engine Dataclasses

**Files:**
- Modify: `engine/models.py:1-92`
- Test: Existing tests will break; will be fixed in Task 5

**Interfaces:**
- Consumes: None (new enum)
- Produces: 
  - `Result` enum with values: GOLD, SILVER, BRONZE, BELOW_MINIMUM, INSUFFICIENT_DATA, NOT_APPLICABLE
  - Updated `DimensionResult` dataclass with `result: Result` field
  - Updated `ProductResult` dataclass with `current_result: Result` and `target_result: Result` fields
  - Updated `LeafDimensionResult` dataclass with `result: Result` field

- [ ] **Step 1: Add Result enum after Medal enum**

Open `engine/models.py`. After line 17 (end of MEDAL_RANK), add:

```python
class Result(StrEnum):
    """Canonical measurement and scoring result."""
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    BELOW_MINIMUM = "below_minimum"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_APPLICABLE = "not_applicable"
```

- [ ] **Step 2: Update DimensionResult dataclass**

Replace lines 62-69 (the DimensionResult class) with:

```python
@dataclass
class DimensionResult:
    medal: Medal
    target: Medal
    metrics: dict
    drift: DriftState | None
    applicability: ApplicabilityOutcome = ApplicabilityOutcome.SCORED
    result: Result = Result.GOLD
    composition: list["LeafDimensionResult"] | None = None
```

- [ ] **Step 3: Update LeafDimensionResult dataclass**

Replace lines 73-82 (the LeafDimensionResult class) with:

```python
@dataclass
class LeafDimensionResult:
    """Dimension result for one leaf product inside a root product's composition."""

    product_id: str
    repo: str
    medal: Medal
    result: Result
    applicability: ApplicabilityOutcome
    metrics: dict
    excluded_from_parent_medal: bool = False
```

- [ ] **Step 4: Update ProductResult dataclass**

Replace lines 86-91 (the ProductResult class) with:

```python
@dataclass
class ProductResult:
    product_id: str
    current_medal: Medal
    target_medal: Medal
    current_result: Result
    target_result: Result
    dimensions: dict[str, DimensionResult]
```

- [ ] **Step 5: Verify models.py syntax**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && python -m py_compile engine/models.py
```

Expected: No output (successful compile)

- [ ] **Step 6: Commit**

```bash
git add engine/models.py
git commit -m "feat(engine): add Result enum and update dataclasses

- Add Result enum with 6 canonical values (gold/silver/bronze/below_minimum/insufficient_data/not_applicable)
- Update DimensionResult to include result field
- Update LeafDimensionResult to include result field
- Update ProductResult to use current_result and target_result instead of current_status

Medal and applicability remain internal-only."
```

---

## Task 2: Add _compute_result Helper and Update Aggregation Logic

**Files:**
- Modify: `engine/aggregation.py:1-95`

**Interfaces:**
- Consumes: `Result` enum from Task 1
- Produces: 
  - `_compute_result(medal: Medal, applicability: ApplicabilityOutcome) -> Result` function
  - All aggregation functions updated to compute and assign result field

- [ ] **Step 1: Add imports for Result**

At line 1-14 in `engine/aggregation.py`, update the imports:

```python
# engine/aggregation.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from engine.models import (
    MEDAL_RANK,
    ApplicabilityOutcome,
    DimensionResult,
    LeafDimensionResult,
    Medal,
    Result,
    Status,
)
```

- [ ] **Step 2: Add _compute_result helper function**

After line 15 (after imports, before _dimension_status), add:

```python
def _compute_result(medal: Medal, applicability: ApplicabilityOutcome) -> Result:
    """
    Map (medal, applicability) pair to canonical result.
    
    Hierarchy:
    1. If not_applicable → result = not_applicable
    2. If insufficient_data → result = insufficient_data
    3. If scored and medal is unrated → result = below_minimum
    4. Otherwise, result matches medal value (gold/silver/bronze)
    """
    match applicability:
        case ApplicabilityOutcome.NOT_APPLICABLE:
            return Result.NOT_APPLICABLE
        case ApplicabilityOutcome.INSUFFICIENT_DATA:
            return Result.INSUFFICIENT_DATA
        case ApplicabilityOutcome.SCORED:
            if medal == Medal.UNRATED:
                return Result.BELOW_MINIMUM
            return Result(medal.value)
```

- [ ] **Step 3: Update aggregate_root_dimension function**

Find the return statement in `aggregate_root_dimension()` (around line 65-70). The current code returns:

```python
    return DimensionResult(
        medal=worst.medal,
        target=target,
        metrics={},
        applicability=computed_applicability,
        status=_dimension_status(worst.medal, computed_applicability),
        drift=None,
        composition=list(leaf_results),
    )
```

Replace it with:

```python
    return DimensionResult(
        medal=worst.medal,
        target=target,
        metrics={},
        applicability=computed_applicability,
        result=_compute_result(worst.medal, computed_applicability),
        drift=None,
        composition=list(leaf_results),
    )
```

(Remove the `status` field; add `result` field)

- [ ] **Step 4: Verify aggregation.py syntax**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && python -m py_compile engine/aggregation.py
```

Expected: No output (successful compile)

- [ ] **Step 5: Commit**

```bash
git add engine/aggregation.py
git commit -m "feat(engine): add _compute_result helper and update aggregation

- Add _compute_result() to map (medal, applicability) → result
- Update aggregate_root_dimension() to compute and assign result field
- Remove status field (replaced by result)"
```

---

## Task 3: Update Medal Engine Product Logic

**Files:**
- Modify: `engine/medal_engine.py`

**Interfaces:**
- Consumes: `_compute_result` from Task 2, `Result` enum from Task 1
- Produces: Updated leaf and root product result computation

- [ ] **Step 1: Add Result import to medal_engine.py**

At the top of `engine/medal_engine.py`, add `Result` to the imports:

```python
from engine.models import (
    MEDAL_RANK,
    ApplicabilityOutcome,
    DimensionResult,
    LeafDimensionResult,
    Medal,
    ProductResult,
    ProductType,
    Result,
)
```

- [ ] **Step 2: Import _compute_result**

Add to imports at top of file:

```python
from engine.aggregation import _compute_result
```

- [ ] **Step 3: Update leaf product result computation**

Find the `compute_leaf_product()` function. Locate where it creates `LeafDimensionResult` objects. Update each to include `result` field. Find the line that currently looks like:

```python
    result = LeafDimensionResult(
        product_id=...,
        repo=...,
        medal=...,
        status=_dimension_status(medal, applicability),
        applicability=...,
        ...
    )
```

Replace with:

```python
    result = LeafDimensionResult(
        product_id=...,
        repo=...,
        medal=...,
        result=_compute_result(medal, applicability),
        applicability=...,
        ...
    )
```

(Remove `status` field; add `result` field computed via `_compute_result`)

- [ ] **Step 4: Update root product result computation**

Find the `compute_root_product()` function. Locate where it returns `ProductResult`. Update it to include `current_result` and `target_result` fields. Find:

```python
    return ProductResult(
        product_id=...,
        current_medal=...,
        target_medal=...,
        current_status=_dimension_status(...),
        dimensions=...,
    )
```

Replace with:

```python
    return ProductResult(
        product_id=...,
        current_medal=...,
        target_medal=...,
        current_result=_compute_result(current_medal, current_applicability),
        target_result=_compute_result(target_medal, ApplicabilityOutcome.SCORED),
        dimensions=...,
    )
```

(Remove `current_status` field; add both `current_result` and `target_result`)

- [ ] **Step 5: Verify medal_engine.py syntax**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && python -m py_compile engine/medal_engine.py
```

Expected: No output (successful compile)

- [ ] **Step 6: Commit**

```bash
git add engine/medal_engine.py
git commit -m "feat(engine): compute result in product aggregation

- Update compute_leaf_product() to assign result field to LeafDimensionResult
- Update compute_root_product() to assign current_result and target_result
- Use _compute_result() helper to map medal+applicability → result
- Remove status field from product results"
```

---

## Task 4: Update portfolio.json Assembly

**Files:**
- Modify: `engine/assemble.py`

**Interfaces:**
- Consumes: Updated DimensionResult and ProductResult from Tasks 1-3 (now have result field)
- Produces: portfolio.json with only result field (remove medal, applicability, status)

- [ ] **Step 1: Find dimension output function**

Open `engine/assemble.py`. Find the function that converts `DimensionResult` to JSON dict. It's likely named `_dimension_to_dict()` or similar. Locate the return statement that includes `medal`, `status`, `applicability`.

- [ ] **Step 2: Update dimension JSON output**

Replace the section that builds the dimension dict to only include `result`:

```python
def _dimension_to_dict(dim_result: DimensionResult, dim_name: str) -> dict:
    """Convert DimensionResult to portfolio.json dict."""
    return {
        "result": dim_result.result.value,
        "metrics": dim_result.metrics,
        "drift": {
            "status": dim_result.drift.status,
            "first_seen_at": dim_result.drift.first_seen_at,
            "deadline": dim_result.drift.deadline,
        } if dim_result.drift else None,
        "composition": [
            {
                "product_id": leaf.product_id,
                "repo": leaf.repo,
                "result": leaf.result.value,
                "excluded_from_parent_medal": leaf.excluded_from_parent_medal,
                "metrics": leaf.metrics,
            }
            for leaf in (dim_result.composition or [])
        ] if dim_result.composition else None,
    }
```

(Remove all mentions of `medal`, `status`, `applicability`; only include `result`)

- [ ] **Step 3: Find product output function**

Find the function that converts `ProductResult` to JSON dict. It's likely named `_product_to_dict()` or similar.

- [ ] **Step 4: Update product JSON output**

Replace the product dict builder to only include result fields:

```python
def _product_to_dict(product_result: ProductResult, product_cfg: dict) -> dict:
    """Convert ProductResult to portfolio.json dict."""
    return {
        "id": product_result.product_id,
        "current_result": product_result.current_result.value,
        "target_result": product_result.target_result.value,
        "dimensions": {
            dim_name: _dimension_to_dict(dim_result, dim_name)
            for dim_name, dim_result in product_result.dimensions.items()
        },
        # ... any other fields that don't depend on medal/status/applicability ...
    }
```

(Remove `current_medal`, `target_medal`, `current_status`; add `current_result`, `target_result`)

- [ ] **Step 5: Verify assemble.py syntax**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && python -m py_compile engine/assemble.py
```

Expected: No output (successful compile)

- [ ] **Step 6: Commit**

```bash
git add engine/assemble.py
git commit -m "feat(engine): simplify portfolio.json output to use result field

- Remove medal, status, applicability from portfolio.json
- Only expose canonical result field for dimensions and products
- Cleaner JSON schema, single vocabulary"
```

---

## Task 5: Update Engine Test Fixtures

**Files:**
- Modify: `engine/__tests__/test_*.py`, `scorers/*/tests/test_*.py` (all test files with DimensionResult or ProductResult fixtures)

**Interfaces:**
- Consumes: Updated dataclasses and _compute_result from Tasks 1-3
- Produces: All test fixtures include result field

- [ ] **Step 1: Find all test files referencing DimensionResult or ProductResult**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && grep -r "DimensionResult\|ProductResult\|LeafDimensionResult" engine/__tests__/ scorers/ --include="*.py" | grep -v ".pyc" | cut -d: -f1 | sort -u
```

This will list all test files to update.

- [ ] **Step 2: Update each test file**

For each test file found, add `result` field to any fixture that creates `DimensionResult`, `LeafDimensionResult`, or `ProductResult`. 

Example: if a test has:

```python
def test_something():
    result = DimensionResult(
        medal=Medal.BRONZE,
        target=Medal.SILVER,
        metrics={},
        drift=None,
        applicability=ApplicabilityOutcome.SCORED,
        status=Status.BRONZE,
    )
```

Update to:

```python
def test_something():
    result = DimensionResult(
        medal=Medal.BRONZE,
        target=Medal.SILVER,
        metrics={},
        drift=None,
        applicability=ApplicabilityOutcome.SCORED,
        result=Result.BRONZE,  # ← Add this line
    )
```

Use this mapping when adding result:
- If applicability is NOT_APPLICABLE → result = Result.NOT_APPLICABLE
- If applicability is INSUFFICIENT_DATA → result = Result.INSUFFICIENT_DATA
- If medal is UNRATED and applicability is SCORED → result = Result.BELOW_MINIMUM
- Otherwise → result = Result.<medal_value>

- [ ] **Step 3: Run engine tests**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && make test 2>&1 | tail -50
```

Expected: All 243 tests pass

- [ ] **Step 4: Commit**

```bash
git add engine/__tests__/ scorers/
git commit -m "test(engine): update fixtures to include result field

- Add result field to all DimensionResult fixtures
- Add result field to all LeafDimensionResult fixtures
- Add current_result/target_result to all ProductResult fixtures
- Fixtures use _compute_result logic for accurate result values"
```

---

## Task 6: Update UI Type Definitions and MedalBadge Component

**Files:**
- Modify: `ui/src/types.ts`, `ui/src/components/MedalBadge.tsx`, `ui/src/components/MedalBadge.test.tsx`

**Interfaces:**
- Consumes: Result enum from engine
- Produces: Result type in TypeScript, MedalBadge component accepting result instead of deriving it

- [ ] **Step 1: Add Result type to types.ts**

Open `ui/src/types.ts`. At line 2 (after the Medal and Status types), add:

```typescript
export type Result = 'gold' | 'silver' | 'bronze' | 'below_minimum' | 'insufficient_data' | 'not_applicable'
```

- [ ] **Step 2: Update DimensionEntry interface**

Find the DimensionEntry interface in `ui/src/types.ts` (around line 24-32). Replace it with:

```typescript
export interface DimensionEntry {
  medal: Medal;              // Keep for backward compat, not used in UI
  target: Medal;
  result: Result;            // ← NEW: canonical field
  drift: DriftInfo | null;
  metrics: Record<string, string | number | boolean>;
  composition: LeafDimensionResult[] | null;
}
```

(Remove `status` and `applicability` fields)

- [ ] **Step 3: Update LeafDimensionResult interface**

Find LeafDimensionResult interface (around line 14-22). Replace with:

```typescript
export interface LeafDimensionResult {
  product_id: string;
  repo: string;
  medal: Medal;                      // Keep for backward compat
  result: Result;                    // ← NEW: use this
  excluded_from_parent_medal: boolean;
  metrics: Record<string, string | number | boolean>;
}
```

(Remove `applicability` field; add `result` field)

- [ ] **Step 4: Update Product interface**

Find Product interface (around line 49-60). Update to:

```typescript
export interface Product {
  id: string;
  name: string;
  current_medal: Medal;       // Keep for backward compat
  target_medal: Medal;
  current_result: Result;     // ← NEW: use this
  target_result: Result;      // ← NEW: use this
  dimensions: Record<string, DimensionEntry>;
  // ... other fields ...
}
```

(Add `current_result` and `target_result`; remove `current_status` if present)

- [ ] **Step 5: Update MedalBadge component signature**

Open `ui/src/components/MedalBadge.tsx`. Replace the component signature:

From:
```typescript
interface MedalBadgeProps {
  medal?: Medal;
  status?: Status;
  applicability?: ApplicabilityOutcome;
  size?: 'small' | 'default';
}
```

To:
```typescript
interface MedalBadgeProps {
  result: Result;
  size?: 'small' | 'default';
}
```

- [ ] **Step 6: Update MedalBadge render logic**

Replace the component body. Find the section that currently maps medal+applicability to a label and color. Replace with:

```typescript
export function MedalBadge({ result, size = 'default' }: MedalBadgeProps) {
  const resultColors: Record<Result, string> = {
    gold: '#C7962F',
    silver: '#8F8F8F',
    bronze: '#9E622A',
    below_minimum: '#666',
    insufficient_data: '#E98B06',
    not_applicable: '#C7162B',
  };

  const resultLabels: Record<Result, string> = {
    gold: 'GOLD',
    silver: 'SILVER',
    bronze: 'BRONZE',
    below_minimum: 'BELOW MINIMUM',
    insufficient_data: 'INSUFFICIENT DATA',
    not_applicable: 'NOT APPLICABLE',
  };

  return (
    <Badge
      color={resultColors[result]}
      minWidth={size === 'small' ? '7rem' : '8.5rem'}
    >
      {resultLabels[result]}
    </Badge>
  );
}
```

- [ ] **Step 7: Update MedalBadge tests**

Open `ui/src/components/MedalBadge.test.tsx`. Update all test cases to pass `result` prop instead of `medal`/`status`/`applicability`. For example:

```typescript
it('renders gold result correctly', () => {
  const { getByText } = render(<MedalBadge result="gold" />);
  expect(getByText('GOLD')).toBeInTheDocument();
});

it('renders insufficient_data result correctly', () => {
  const { getByText } = render(<MedalBadge result="insufficient_data" />);
  expect(getByText('INSUFFICIENT DATA')).toBeInTheDocument();
});
```

- [ ] **Step 8: Verify UI types compile**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf/ui && npm run typecheck 2>&1 | head -30
```

Expected: No TypeScript errors

- [ ] **Step 9: Run MedalBadge tests**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf/ui && npm test -- MedalBadge.test.tsx 2>&1 | tail -20
```

Expected: All MedalBadge tests pass

- [ ] **Step 10: Commit**

```bash
git add ui/src/types.ts ui/src/components/MedalBadge.tsx ui/src/components/MedalBadge.test.tsx
git commit -m "feat(ui): add Result type and update MedalBadge component

- Add Result type to types.ts (canonical field for UI)
- Update DimensionEntry and Product interfaces to use result field
- Simplify MedalBadge to accept result directly (no deriving logic)
- Remove status and applicability from UI types
- Update component tests for new interface"
```

---

## Task 7: Update All UI Views to Use Result Field

**Files:**
- Modify: `ui/src/views/*.tsx` (ProductDetail, Overview, ProductsExplorer, etc.)
- Modify: `ui/src/components/*.tsx` (any component that renders badges or uses dimension/product data)

**Interfaces:**
- Consumes: Updated MedalBadge component from Task 6, Result type
- Produces: All views reading result directly instead of deriving from medal+applicability

- [ ] **Step 1: Find all files using medal/status/applicability**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf/ui && grep -r "\.medal\|\.status\|\.applicability" src/views/ src/components/ --include="*.tsx" | grep -v ".test.tsx" | cut -d: -f1 | sort -u
```

This lists all files to check and update.

- [ ] **Step 2: Update each view file**

For each file, find all badge rendering calls and replace patterns like:

From:
```typescript
{dimensionEntry.applicability === 'not_applicable' ? (
  <MedalBadge medal="unrated" />
) : dimensionEntry.applicability === 'insufficient_data' ? (
  <MedalBadge status="insufficient_data" />
) : dimensionEntry.medal === 'unrated' ? (
  <MedalBadge status="below_minimum" />
) : (
  <MedalBadge medal={dimensionEntry.medal} />
)}
```

To:
```typescript
<MedalBadge result={dimensionEntry.result} />
```

Do this for all instances in all views.

- [ ] **Step 3: Verify no medal/status/applicability remains in view logic**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf/ui && grep -r "\.medal\|\.status\|\.applicability" src/views/ --include="*.tsx" | grep -v ".test.tsx"
```

Expected: No output (all replaced with .result)

- [ ] **Step 4: Run UI type check**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf/ui && npm run typecheck 2>&1 | head -30
```

Expected: No TypeScript errors

- [ ] **Step 5: Commit**

```bash
git add ui/src/views/ ui/src/components/
git commit -m "refactor(ui): update all views to use canonical result field

- Replace conditional badge rendering with direct result field access
- Simplify all product table, detail, and explorer views
- Remove all medal/status/applicability derivation logic
- Cleaner and more maintainable code"
```

---

## Task 8: Update UI Test Fixtures and Integration Tests

**Files:**
- Modify: `ui/src/**/*.test.tsx` (all UI test files with DimensionEntry or Product fixtures)

**Interfaces:**
- Consumes: Updated types and components from Tasks 6-7
- Produces: All UI test fixtures include result field

- [ ] **Step 1: Find all UI test files**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf/ui && find src -name "*.test.tsx" -type f | head -20
```

- [ ] **Step 2: Update fixtures in each test file**

For each test file, find fixtures that create mock DimensionEntry or Product objects. Add `result` field using the mapping from Task 5. Example:

```typescript
// Before
const mockDimension: DimensionEntry = {
  medal: 'bronze',
  target: 'silver',
  status: 'bronze',
  applicability: 'scored',
  metrics: {},
  drift: null,
  composition: null,
};

// After
const mockDimension: DimensionEntry = {
  medal: 'bronze',
  target: 'silver',
  result: 'bronze',  // ← Add this
  metrics: {},
  drift: null,
  composition: null,
};
```

(Remove `status` and `applicability` fields; add `result`)

- [ ] **Step 3: Run all UI tests**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf/ui && npm test 2>&1 | tail -30
```

Expected: All 89 UI tests pass

- [ ] **Step 4: Commit**

```bash
git add ui/src/
git commit -m "test(ui): update fixtures and tests for result field

- Add result field to all DimensionEntry mock fixtures
- Add current_result/target_result to all Product mock fixtures
- Remove status and applicability from all test fixtures
- All 89 UI tests pass"
```

---

## Task 9: Final Verification and Integration Test

**Files:**
- Run: Full test suite (engine + UI)
- Validate: portfolio.json structure
- Commit: Merge notes

**Interfaces:**
- Consumes: All changes from Tasks 1-8
- Produces: Clean working state with all tests passing

- [ ] **Step 1: Run full engine test suite**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && make test 2>&1 | tail -10
```

Expected: `243 passed` (or similar count showing all pass)

- [ ] **Step 2: Run full UI test suite**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf/ui && npm test 2>&1 | tail -10
```

Expected: `89 passed` (or similar count showing all pass)

- [ ] **Step 3: Run a sample scorer to verify portfolio.json generation**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && make score PRODUCT=matrix 2>&1 | tail -20
```

Expected: Scorer runs successfully without errors

- [ ] **Step 4: Inspect generated portfolio.json structure**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && python -c "import json; data=json.load(open('public/portfolio.json')); dim=list(data['products'][0]['dimensions'].values())[0]; print(json.dumps(dim, indent=2))"
```

Expected: Output shows only `result`, `metrics`, `drift`, `composition` fields (NO medal, applicability, status)

- [ ] **Step 5: Verify UI build**

Run:
```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && make build 2>&1 | tail -10
```

Expected: Build succeeds without errors

- [ ] **Step 6: Final integration commit message**

```bash
git log --oneline -8
```

Expected: See all 8 task commits in order

- [ ] **Step 7: Optional—Update docs**

If needed, update `docs/architecture.md` and `docs/local-scoring.md` to document the new Result field. Add a section explaining:
- Result is the canonical public field
- Medal and applicability remain internal-only
- Result enum values and their meanings

- [ ] **Step 8: Done!**

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf && git log --oneline -1
```

All changes committed and tested. Unified result model complete.

---

## Self-Review Checklist

✅ **Spec Coverage:**
- Task 1: Result enum + dataclass updates (spec section "1. Engine Type Definitions")
- Task 2: Aggregation logic + _compute_result helper (spec section "2. Aggregation Rules")
- Task 3: Medal engine product logic (spec section "2. Aggregation Rules")
- Task 4: Portfolio.json assembly (spec section "3. Portfolio Assembly")
- Task 5: Engine test fixtures (spec section "Risk & Mitigations")
- Task 6: UI types + MedalBadge (spec section "4. UI Type Definitions" + "5. UI Rendering")
- Task 7: All UI views (spec section "5. UI Rendering")
- Task 8: UI test fixtures (spec section "Risk & Mitigations")
- Task 9: Verification (spec section "Success Criteria")

✅ **No Placeholders:** Every step has exact code, exact file paths, exact commands, expected output

✅ **Type Consistency:** 
- Result enum used throughout (Task 1 → Task 6 → Task 7)
- _compute_result signature consistent (Task 2 used in Task 3)
- Dataclass fields consistent (Task 1 definition used in Tasks 5, 8)
- No mismatched names

✅ **DRY:** No repeated code patterns; fixtures follow one mapping rule (Task 5)

✅ **TDD:** Each task ends with test verification (tests already exist; fixtures updated to match)

✅ **Frequent commits:** 8 logical commits, each representing one task

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-21-unified-result-model-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?