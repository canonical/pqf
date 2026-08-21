# Unified Scoring Result Model Design

**Tracking:** PQF score/status/medal semantic cleanup  
**Author:** Copilot  
**Date:** 2026-08-21  
**Status:** Design phase

---

## Problem Statement

The current PQF scoring model has scattered semantics across three separate concepts:

1. **`medal`** (engine output): `gold | silver | bronze | unrated` — what the rubric computes
2. **`status`** (user-facing): `gold | silver | bronze | below_minimum | insufficient_data | not_applicable` — intended to disambiguate
3. **`applicability`** (internal): `scored | insufficient_data | not_applicable` — classification for why a result exists

This creates semantic confusion because the same information flows through the system under three names:

- A dimension that was measured but scored below the bronze threshold shows `medal=unrated` + `applicability=scored` + `status=below_minimum`. 
  - **Problem:** "unrated" contradicts "below_minimum" — these describe the same thing, but different names create confusion in the UI and during debugging.

- A dimension that couldn't be measured shows `medal=unrated` + `applicability=insufficient_data` + `status=insufficient_data`.
  - **Problem:** `medal` and `applicability` both map to the same `status`, creating redundancy without clarity.

- A dimension that doesn't apply to this product type shows `medal=unrated` + `applicability=not_applicable` + `status=not_applicable`.
  - **Problem:** Again, three names for one concept.

This design proposes a single canonical `result` field that replaces the consumer-facing `status`, keeps `medal` as an internal ranking helper, and removes the public `applicability` field (kept internal only).

---

## Solution Overview

Introduce a canonical **`result`** enum with six values that combines medal and applicability semantics:

```
result := gold | silver | bronze | below_minimum | insufficient_data | not_applicable
```

- **Scoring Results (all measured):** `gold`, `silver`, `bronze`, `below_minimum`
  - These fold the rubric decision into one value. No separate `medal` or `applicability` exposed.
  - `below_minimum` replaces the confusing `medal=unrated + applicability=scored` combination.
  
- **Non-Scoring Results:** `insufficient_data`, `not_applicable`
  - `insufficient_data` = required metrics missing (can't measure)
  - `not_applicable` = out of scope for this product type

**Internal only:**
- `medal` remains as an enum for ranking/aggregation logic, never exposed in API or portfolio.json
- `applicability` remains as classification logic in engine (computed from config), never exposed in API

**Outward vocabulary:**
- Engine, aggregation, assemble.py, portfolio.json, UI — all use `result` field
- Single field, single meaning, no confusion

---

## Detailed Model

### 1. Engine Type Definitions (models.py)

Add a new enum:

```python
class Result(StrEnum):
    """Canonical measurement and scoring result."""
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    BELOW_MINIMUM = "below_minimum"           # Measured, but below bronze threshold
    INSUFFICIENT_DATA = "insufficient_data"   # Missing required metrics
    NOT_APPLICABLE = "not_applicable"         # Out of scope for this product type
```

Keep `Medal` enum as-is (internal-only for rubric computation and ranking).

Update dataclasses:

```python
@dataclass
class DimensionResult:
    medal: Medal                                        # Internal only (for ranking)
    target: Medal                                       # Internal only
    metrics: dict
    drift: DriftState | None
    applicability: ApplicabilityOutcome = ApplicabilityOutcome.SCORED  # Internal only
    result: Result = Result.GOLD                        # ← NEW: canonical public field
    composition: list["LeafDimensionResult"] | None = None
```

```python
@dataclass
class ProductResult:
    product_id: str
    current_medal: Medal                       # Internal only (for ranking)
    target_medal: Medal                        # Internal only
    current_result: Result                     # ← NEW: canonical public field
    target_result: Result                      # ← NEW: always matches target medal (gold/silver/bronze)
    dimensions: dict[str, DimensionResult]
    # Note: no applicability field; result encompasses it
```

**Why this structure:**
- `medal` and `applicability` remain internally for computation (no re-architecting the scoring engine)
- `result` is the first-class user-facing field
- Dataclass ensures both are always kept in sync via aggregation logic

### 2. Aggregation Rules (aggregation.py)

Add a helper to compute result from medal + applicability:

```python
def _compute_result(medal: Medal, applicability: ApplicabilityOutcome) -> Result:
    """
    Map (medal, applicability) to canonical result.
    
    Hierarchy:
    1. If not_applicable → result = not_applicable
    2. If insufficient_data → result = insufficient_data
    3. If scored and medal is unrated → result = below_minimum
    4. Otherwise, result = medal value (gold/silver/bronze)
    """
    match applicability:
        case ApplicabilityOutcome.NOT_APPLICABLE:
            return Result.NOT_APPLICABLE
        case ApplicabilityOutcome.INSUFFICIENT_DATA:
            return Result.INSUFFICIENT_DATA
        case ApplicabilityOutcome.SCORED:
            if medal == Medal.UNRATED:
                return Result.BELOW_MINIMUM
            return Result(medal.value)  # gold/silver/bronze
```

Update `aggregate_root_dimension()` to compute `result` alongside `medal`:

```python
result = DimensionResult(
    medal=worst.medal,
    target=target,
    applicability=computed_applicability,
    result=_compute_result(worst.medal, computed_applicability),  # ← NEW
    metrics={},
    drift=None,
    composition=list(leaf_results),
)
```

Same pattern in `compute_leaf_product()` and `compute_root_product()` in medal_engine.py.

### 3. Portfolio Assembly (assemble.py)

When writing `portfolio.json`, include `result` field alongside `medal` (for backwards compatibility during transition):

```python
def _dim_to_dict(dim_result: DimensionResult, ...) -> dict:
    return {
        # Keep medal/applicability for now (backwards compat)
        "medal": dim_result.medal.value,
        "target": dim_result.target.value,
        "applicability": dim_result.applicability.value,
        # Add canonical result field
        "result": dim_result.result.value,
        # ... rest of fields ...
    }

def _result_to_dict(result: ProductResult, ...) -> dict:
    return {
        # Keep medal for now
        "current_medal": result.current_medal.value,
        "target_medal": result.target_medal.value,
        # Add canonical result fields
        "current_result": result.current_result.value,
        "target_result": result.target_result.value,
        # No applicability in output (internal-only)
        # ... rest of fields ...
    }
```

**Backwards compatibility strategy:**
- Keep `medal`, `applicability` in JSON output during transition (no consumers broken)
- Add new `result` field
- UI prefers reading `result` if present, falls back to deriving from `medal+applicability`
- Plan for future deprecation of old fields once all consumers updated

### 4. UI Type Definitions (ui/src/types.ts)

Add Result type:

```typescript
export type Result =
  | "gold"
  | "silver"
  | "bronze"
  | "below_minimum"
  | "insufficient_data"
  | "not_applicable";
```

Update interfaces:

```typescript
export interface Dimension {
  medal: Medal;           // Keep for now, not exposed in UI
  target: Medal;
  metrics: Record<string, unknown>;
  result: Result;         // ← NEW: use this for rendering
  applicability?: string; // ← Optional, not used in UI
}

export interface Product {
  id: string;
  name: string;
  current_medal: Medal;      // Keep for now
  target_medal: Medal;
  current_result: Result;    // ← NEW: use this
  target_result: Result;     // ← NEW
  dimensions: Record<string, Dimension>;
  // No applicability field
}
```

### 5. UI Rendering (all views)

Simplify all medal badge rendering to use the `result` field directly:

**Before:**
```typescript
function renderDimensionBadge(dimension: Dimension) {
  if (dimension.applicability === "not_applicable") {
    return <MedalBadge medal="unrated" />;
  }
  if (dimension.applicability === "insufficient_data") {
    return <MedalBadge medal="insufficient_data" />;
  }
  if (dimension.medal === "unrated") {
    return <MedalBadge medal="below_minimum" />;
  }
  return <MedalBadge medal={dimension.medal} />;
}
```

**After:**
```typescript
// No helper needed — just use the result field directly
<MedalBadge result={dimension.result} />
```

Update MedalBadge component to accept `result` instead of deriving it:

```typescript
interface MedalBadgeProps {
  result: Result;
  size?: "small" | "default";
}

export function MedalBadge({ result, size = "default" }: MedalBadgeProps) {
  const resultColors = {
    gold: "#C7962F",
    silver: "#8F8F8F",
    bronze: "#9E622A",
    below_minimum: "#666",
    insufficient_data: "#E98B06",
    not_applicable: "#C7162B",
  };
  
  return (
    <Badge
      color={resultColors[result]}
      minWidth={size === "small" ? "7rem" : "8.5rem"}
    >
      {result.replace("_", " ").toUpperCase()}
    </Badge>
  );
}
```

All views (ProductDetail, Overview, ProductsExplorer, tables, etc.) become cleaner:

```typescript
<MedalBadge result={product.current_result} size="small" />
<MedalBadge result={dimension.result} />
```

---

## Data Flow Example

**Scenario: Charm repo with documentation dimension, missing required metrics**

1. **Scorer runs** (`scorers/documentation/scorer.py`):
   - Fetches repo metadata, README, contributing guide
   - Required metric `readme_exists` = false
   - Returns metrics with missing required signals

2. **Aggregation** (leaf product):
   ```
   medal = Medal.UNRATED (no signals passed rubric)
   applicability = INSUFFICIENT_DATA (required_metrics_for_scoring has nulls)
   result = Result.INSUFFICIENT_DATA (via _compute_result)
   ```

3. **Root product aggregation** (if charm is in umbrella):
   ```
   Leaves: [charm1(INSUFFICIENT_DATA), charm2(GOLD), ...]
   Worst: charm1(INSUFFICIENT_DATA)
   aggregated result = Result.INSUFFICIENT_DATA (propagated)
   ```

4. **Portfolio JSON**:
   ```json
   {
     "id": "charm-name",
     "dimensions": {
       "documentation": {
         "result": "insufficient_data",
         "medal": "unrated",
         "applicability": "insufficient_data"
       }
     }
   }
   ```

5. **UI Render**:
   - Read `result = "insufficient_data"`
   - Render badge with "INSUFFICIENT DATA" label, orange (#E98B06) background
   - No conditional logic needed

---

## Migration Timeline

### Phase 1: Engine & Portfolio (this PR)
- Add `Result` enum
- Update dataclasses to include `result` field
- Add `_compute_result()` helper
- Update aggregation logic
- Update portfolio.json to include result fields (keep medal/applicability for now)
- All engine tests pass

### Phase 2: UI Consumption (this PR)
- Update types.ts to add Result type
- Update all views to read `result` field
- Simplify badge rendering helpers
- Remove conditional logic
- All UI tests pass

### Phase 3: Deprecation (future)
- Plan for removing public `medal`, `applicability` fields from portfolio.json after all downstream consumers (dashboards, integrations) updated
- Could be a separate PR 1-2 sprints later

---

## Success Criteria

- ✅ Single field `result` used throughout engine, aggregation, portfolio, UI
- ✅ No confusion between medal, status, applicability in user-facing output
- ✅ All 243 engine tests pass
- ✅ All 89 UI tests pass
- ✅ Portfolio.json includes result field for all dimensions and products
- ✅ Badge rendering simplified (no conditional helpers)
- ✅ Backwards compatibility maintained (medal/applicability still in JSON during transition)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Downstream consumers break if portfolio.json changes | High | Keep `medal`, `applicability` in JSON during phase 1-2; deprecate later with notice |
| Test fixtures miss the new `result` field | High | Update all fixtures in one pass; catch with type checking |
| UI components still reference `medal` or `applicability` | Medium | Search all views for `medal`, `applicability` references; replace with `result` |
| MedalBadge colors differ from enum mapping | Medium | Hard-code color mapping in component; document in spec |

---

## Implementation Scope

**Files to change:**
1. `engine/models.py` — Add Result enum, update dataclasses
2. `engine/aggregation.py` — Add _compute_result(), update return statements
3. `engine/medal_engine.py` — Compute result in leaf and root product logic
4. `engine/assemble.py` — Include result in portfolio.json
5. All test files — Update fixtures to include result field
6. `ui/src/types.ts` — Add Result type, update interfaces
7. `ui/src/components/MedalBadge.tsx` — Accept `result` instead of deriving
8. `ui/src/views/ProductDetail.tsx` — Use result field directly
9. `ui/src/views/Overview.tsx` — Use result field directly
10. `ui/src/views/ProductsExplorer.tsx` — Use result field directly
11. All UI test files — Update fixtures
12. `docs/architecture.md` (optional) — Document new result field and deprecation path

**Estimated effort:** ~8-10 hours (engine ~3h, UI ~3h, tests ~2-3h, verification ~1h)

---

## Questions for User

Before proceeding to implementation, please confirm:

1. ✅ Is this approach aligned with your vision for unifying the semantics?
2. ✅ Do you want to keep `medal` and `applicability` in portfolio.json for backwards compatibility during phase 1-2, then deprecate later?
3. ✅ Are there downstream consumers of portfolio.json that I should be aware of (dashboards, integrations, exports)?
4. ✅ Should we update documentation (docs/architecture.md, docs/local-scoring.md) as part of this refactor?

