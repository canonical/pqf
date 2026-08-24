# UX Wording Alignment Design

**Date:** 2026-08-24  
**Scope:** User-facing website copy only (docs/specs to be updated as follow-on)  
**Audience:** Product teams, platform engineers using PQF UI  
**Goal:** Establish canonical terminology so UI language is consistent, clear, and reduces confusion about model semantics.

---

## Problem

The PQF website currently mixes terminology inconsistently:
- "medal", "result", "status", "score" used interchangeably for outcomes
- "metrics" and "evidence" treated as synonyms
- "rubric", "criteria", "constraints" overlap without clear distinction
- "dimension" vs. implied "compliance axis" distinction missing

This causes user confusion about what they're looking at and whether non-medal outcomes (sub-min, no data, N/A) are first-class or edge cases.

---

## Solution: Canonical Vocabulary Model

### Core Definitions

| Term | Definition | Context |
|------|-----------|---------|
| **Portfolio** | Complete tracked set of products | Site-wide umbrella |
| **Product** | One tracked item (root or leaf) in portfolio | Product listing, detail pages |
| **Dimension** | One quality or compliance axis for a product (umbrella term) | Navigation, tables, filters |
| **Compliance axis** | A dimension specifically focused on policy/standards/governance (subset descriptor) | Used when distinction from other dimension types matters |
| **Metric** | One measured signal within a dimension | Metric keys, metadata (coverage_pct, has_readme, etc.) |
| **Result** | The scored outcome shown: gold/silver/bronze/sub-min/no data/N/A | Tables, badges, filters, all contexts showing outcomes |
| **Medal** | Reserved: the three rated tiers (gold/silver/bronze) or target ambition | Target goals ("target: gold"), tier references ("gold medal") |
| **Rubric** | The dimension's complete scoring rules across all tiers | Section headers, conceptual references |
| **Criteria** | Individual checks within a rubric tier (cumulative per tier) | Criterion strings ("coverage_pct >= 80"), tier explanations |
| **Evidence** | Concrete metric values supporting a result (narrowly scoped) | Metric value displays, detail views |
| **Target** | The product team's committed medal goal for a dimension | Label: "Target", values: gold/silver/bronze |
| **Current** | The product's latest measured result for a dimension | Label: "Current", values: any result including N/A |

### Key Distinctions

**1. Result ≠ Medal**
- **Result:** Includes all outcomes: gold, silver, bronze, below_minimum, insufficient_data, not_applicable
- **Medal:** Only the rated tiers: gold, silver, bronze; used for target/aspiration
- **Rule:** Use **result** when filtering, displaying, or explaining all outcomes; use **medal** only for tier references or target context

**2. Criteria ≠ Rubric**
- **Criteria:** Individual rules ("coverage_pct >= 80", "has_readme == true")
- **Rubric:** The complete framework across all tiers
- **Rule:** Section headers say "Medal rubric"; explanations refer to "Bronze criteria" or "Silver criteria"

**3. Metrics ≠ Evidence**
- **Metrics:** The measured signal names (coverage_pct, latest_build_passing, etc.)
- **Evidence:** The rendered values shown in a table or detail view
- **Rule:** Don't substitute; "Evidence column shows metric values" is clearer than "Evidence shows metrics"

**4. Dimension ≠ Compliance Axis**
- **Dimension:** Umbrella term for all quality/compliance axes
- **Compliance axis:** Contextual descriptor for policy-focused dimensions (e.g., SSDLC, Substrate Compat)
- **Rule:** Use **dimension** in UI labels and navigation; reserve **compliance axis** for documentation or when the distinction clarifies scope

---

## Semantic Risks & Design Decisions

### Risk 1: Root Product Medal Aggregation
**Issue:** When a root product's dimension result is derived from worst-of-leaves, the UI should clarify it's an aggregation, not a direct score.  
**Current behavior:** Shown in "Dependencies" section with sub-products table.  
**Decision:** Keep current behavior; add a tooltip or small note: "Root result reflects worst component result."

### Risk 2: Target-Contextual N/A
**Issue:** When a metric isn't part of a product's target tier, the UI shows "N/A". This is a display choice, not a model issue.  
**Current behavior:** Metric Distribution page shows "N/A" in threshold result when metric not applicable to target.  
**Decision:** Clarify in explanatory text: "Threshold result shows N/A if this metric is not part of your product's target medal tier."

### Risk 3: Sub-Min vs. No Data Distinction
**Issue:** Both are non-medal outcomes, but semantically different (measured-and-failed vs. unmeasurable).  
**Current behavior:** Filter labels: "Sub-min" and "No data" are separate options.  
**Decision:** Keep separate labels; add tooltip on filters: "Sub-min = measured below bronze threshold. No data = unable to measure."

---

## Copy Changes by Surface

### 1. Product Detail Page

**Header (Medals Row)**
- ✅ Already correct: "CURRENT", "TARGET" labels with result badges

**Dimensions Table**
- **Before:** "Medal" column
- **After:** "Current" column
- **Why:** Shows all results including N/A; "medal" is too narrow

**Evidence Column**
- **Before:** "Evidence" (currently renders metrics)
- **After:** Keep "Evidence" but clarify in product detail that it shows "metric values"
- **Tooltip:** "Metric values evaluated against bronze and target tier criteria"

### 2. Metric Distribution Page

**Explanatory Text**
- **Before:** "Threshold result shows how this metric value rates against the dimension's rubric (gold/silver/bronze/sub-min/no data)"
- **After:** "Threshold result shows how this metric value rates against your product's target medal tier (or N/A if the metric is not part of the target tier)."
- **Reason:** Clarifies it's target-contextual, not global rubric

**"Portfolio Distribution" Header**
- ✅ Already correct (renamed from "Fleet distribution")

**Gap to Target Explanation**
- **Before:** "Gap to target uses consistent labels (At target, Exceeds target, Below target, or —) against this product's target medal."
- **After:** (keep as-is; already clear)

**Filters**
- **Before:** "Medal" filter options: "All results", "Bronze", "Silver", "Gold", "Below minimum", "No data"
- **After:** Keep labels; clarify first option as "All results" (not "All medals")
- **Reasoning:** Avoids confusion when filtering on non-medal outcomes

### 3. Dimensions Overview Page

**Table Header**
- ✅ Already correct: "Dimensions" section

**Sorting/Filtering**
- If filters exist: Use "result" language, not "medal"

### 4. About Page

**Medal Levels Table**
- **Before:** Row for "unrated": "Not yet scored, or insufficient data."
- **After:** "Not yet scored or insufficient data." (minor grammar)
- **Add row:** Below the 4 existing rows, add "Sub-minimum" or expand "unrated" entry
- **Reasoning:** Makes it explicit that sub-min is a distinct outcome (measured, but failed bronze threshold)

---

## Implementation Approach

### Phase 1: Copy Updates (Website UI)
1. Update Product Detail page column headers and explanatory text
2. Update Metric Distribution page explanations and filter labels
3. Update About page medal levels table
4. Update any tooltips/help text in filters and column headers

### Phase 2: Docs Update (Follow-On)
1. Update `docs/README.md` to reference canonical terminology
2. Update `docs/architecture.md` with terminology section
3. Update view documentation (dimension-detail.md, product-detail.md, etc.) to use consistent terminology
4. Add a "Glossary" section to `docs/README.md`

### Phase 3: Code Label Standardization (Optional Follow-On)
1. Audit component prop names, variable names, and comments for consistency
2. No breaking changes to data model; this is UI/UX layer only

---

## Success Criteria

- [ ] All UI page copy uses vocabulary consistently
- [ ] Non-medal outcomes (sub-min, no data, N/A) are clearly distinct in language and UI
- [ ] "Result" is used for all outcomes; "medal" reserved for tier references
- [ ] "Metrics" and "evidence" are no longer interchangeable
- [ ] Product teams can read a page and understand the distinction between target, current, and rubric
- [ ] No user confusion about whether a product with "no data" for a dimension is failing or just unmeasured

---

## Rollout Plan

1. **Phase 1 (this PR):** Update website copy in isolated branch; test all pages for consistency
2. **Phase 2 (follow-on PR):** Update documentation and add glossary
3. **Phase 3 (optional):** Coordinate with teams if internal code/comments need updates

---

## Glossary (Reference)

**Bronze** – The minimum medal tier; required criteria must be met  
**Compliance axis** – A dimension focused on policy/standards (subset of dimensions)  
**Criteria** – Individual rules within a rubric tier; cumulative per tier  
**Current** – The product's latest measured result  
**Dimension** – One quality or compliance axis for a product  
**Evidence** – Concrete metric values supporting a result  
**Medal** – The rated tiers (gold/silver/bronze) or target ambition  
**Metric** – One measured signal within a dimension  
**No data** – Unable to measure the metric confidently  
**Not applicable** – Dimension or metric not relevant for this product  
**Portfolio** – Complete tracked set of products  
**Product** – One tracked item in the portfolio  
**Result** – The scored outcome (includes all statuses: gold/silver/bronze/sub-min/no data/N/A)  
**Rubric** – The dimension's complete scoring rules across all tiers  
**Sub-minimum** – Measured below the bronze (minimum) threshold  
**Target** – The product team's committed medal goal  

