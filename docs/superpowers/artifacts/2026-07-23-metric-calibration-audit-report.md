# PQF Metric Calibration Audit Report (Baseline)

Date: 2026-07-23  
Author: Copilot (assistant)

## 1) Executive summary

Current metric outcomes are dominated by detection gaps, not true product quality gaps.

Evidence from local runs and current artifacts shows:
- `test_verification`: `latest_build_passing` true for only **5/78** leaf units (6.4%)
- `documentation`: several core booleans are true for **0/78**
- `substrate_compat`: `supports_juju_4` true for **0/78**
- `security_ssdlc`: `canonical_repo_automation_registered` true for **0/78**
- Portfolio medals skew heavily to bronze/unrated in ways inconsistent with observed repo health.

This indicates **systematic false negatives** from narrow matching logic and source-of-truth assumptions.

---

## 2) Method used

1. Reviewed current metric contracts in `config/dimensions.yaml`.
2. Ran local scoring with LLM path enabled (`OPENROUTER_API_KEY` set).
3. Generated metric distributions from `computed/*.json` and `public/portfolio.json`.
4. Reviewed scorer logic files for all dimensions.
5. Spot-checked reported false negatives (example: `canonical/saml-integrator-operator` latest commit checks all green, while PQF metric reported `latest_build_passing: false` in leaf metrics for saml-integrator under matrix composition).

---

## 3) Baseline distribution (current logic)

Leaf entries scanned from `computed/*`: **78**

### Dimension medal distribution (portfolio view)

- `test_verification`: bronze 109, silver 2
- `documentation`: bronze 111
- `substrate_compat`: bronze 78, silver 18, unrated 15
- `security_ssdlc`: bronze 28, silver 71, gold 12
- `support_engagement`: bronze 95, silver 3, gold 8, unrated 5

### High-signal metric distributions

- `test_verification.coverage_pct` nonzero: **4/78**
- `test_verification.latest_build_passing` true: **5/78**
- `documentation.readme_meets_structure` true: **0/78**
- `documentation.documentation_workflows_passing` true: **0/78**
- `substrate_compat.supports_juju_4` true: **0/78**
- `security_ssdlc.canonical_repo_automation_registered` true: **0/78**

---

## 4) Root-cause findings by dimension/metric

## A. test_verification

### coverage_pct / stability_pct / latest_build_passing
- Current source is only Allure `widgets/summary.json` when `allure_report_url` exists.
- If missing/invalid, scorer emits `coverage_pct=0`, `stability_pct=0`, `latest_build_passing=false`.
- This conflates **unmeasurable** with **failing**.
- Example mismatch: saml-integrator repo has green latest checks, but PQF leaf metric can still be false without usable Allure signal.

**Accepted variation to support**
- Repos that do not publish Allure but have CI status checks.

**Change needed**
- Add fallback build source from GitHub checks when Allure is absent.
- Mark coverage/stability as unmeasurable (not zero) when no compatible coverage source exists.

### integration_test_evidence_present
- Workflow pattern matching is useful but still narrow.
- Should parse broader workflow conventions and test commands.

### uses_ops_testing / uses_jubilant
- Metrics are detectable and reasonably informative as informational signals.
- Not ideal as hard gates for medal progression.

---

## B. documentation

### readme_meets_structure / contributing_meets_structure
- Both are **0/78 true**.
- Section requirements are too strict and assume a single document taxonomy/heading vocabulary.

### documentation_workflows_passing
- Requires explicit lint + links + build check names with strict matching.
- Many repos use consolidated or differently named docs jobs.

### diataxis_coverage
- File-path heuristics are too narrow (`docs/tutorial.md`, etc.), missing valid docs layouts.

### tutorial_tested
- Requires tutorial files + check names with tutorial + test intent; too naming-dependent.

### uses_rtd_hosting / recent_release_notes_present
- Valid as informational metrics, but too strict for gating at current detection fidelity.

**Change needed**
- Move from rigid filename/check-name matching to broader deterministic repo-shape detection.
- Reclassify some metrics as informational before re-enabling them as medal gates.

---

## C. substrate_compat

### supports_juju_3 / supports_juju_4 / substrate_test_evidence_present / uses_canonical_k8s
- Detection depends on narrowly matched workflow text (e.g., `juju-channel:.*3/stable`).
- `supports_juju_4` and `uses_canonical_k8s` at 0% strongly suggests pattern miss, not universal absence.

**Accepted variation to support**
- Matrix strategy, templated actions, reusable workflows, and alternate key naming.

**Change needed**
- Parse workflow YAML structure instead of regex-only text scanning.

---

## D. security_ssdlc

### canonical_repo_automation_registered
- **0/78 true**; likely source mismatch.
- Current implementation uses GitHub code search on `canonical/canonical-repo-automation`, which can fail for private/internal visibility or non-code representation of onboarding.

### branch_protection_required_checks / renovate_enabled
- Strong signals (high true rate), likely reliable.

### sast_workflow_present / cve_tracking_process_present
- Useful but may need broader tooling keyword support and clearer process markers.

**Change needed**
- Replace canonical-repo-automation detection with a dedicated deterministic source (API/list file) rather than free-text code search.

---

## E. support_engagement

### avg_triage_days / avg_pr_review_days / response_coverage_rate
- Severe inflation and zeros caused by data semantics:
  - issues endpoint `since` filters by updated time, not created time (old issues can still appear)
  - no minimum sample threshold
  - zero can represent “no data” and “instant response,” which should be separated

### ownership_signal / has_jira_sync
- Ownership signal is robust.
- Jira sync detection from a specific file path is useful but may miss accepted alternatives.

**Change needed**
- Add sample-size and recency thresholds.
- Distinguish missing sample (`unrated`) from measured zero.

---

## 5) Unrated vs bronze policy (proposed)

- **Bronze** = metric/dimension is measurable and measured, but does not satisfy higher thresholds.
- **Unrated** = metric cannot be measured with available deterministic evidence OR sample is insufficient.

Implementation implication:
- Scorers must stop defaulting unknown/unavailable to `0`/`false` for gated metrics.
- Engine applicability should support dimension-level insufficient-data semantics based on measurability completeness.

---

## 6) Priority remediation order

1. **P0** test_verification fallback:
   - fix `latest_build_passing` false negatives by adding GitHub checks fallback.
2. **P0** canonical_repo_automation signal source:
   - replace code-search heuristic with deterministic source.
3. **P1** documentation detector broadening:
   - normalize accepted docs layouts/workflow naming.
4. **P1** substrate workflow parsing:
   - structured YAML parsing for Juju/substrate signals.
5. **P1** support engagement semantics:
   - sample thresholds and no-data handling.
6. **P2** rubric recalibration:
   - reintroduce strict gates only after detector fidelity improves.

---

## 7) Output of this audit phase

This report is the factual baseline for:
1. design spec: metric-calibration architecture and policy
2. implementation plan: metric-by-metric remediation in prioritized phases

