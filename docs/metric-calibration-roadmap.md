# Metric Calibration Roadmap

This document records the operating philosophy and the remaining phases of PQF metric-calibration work after the foundation improvements merged in PR #17. It exists so future humans and AI contributors can keep the work consistent, reviewable, and tightly controlled.

## Operating philosophy

PQF should remain **as simple as possible and as high-confidence as possible**. That means:

- prefer deterministic, explicit evidence over broad heuristics,
- support only a small set of sanctioned structural variants,
- keep each metric easy to explain,
- distinguish poor measured results from unmeasurable signals,
- and use PQF to drive alignment rather than absorb arbitrary repo drift.

### Sanctioned variance classes

The currently accepted variance classes are:

1. **monorepo vs non-monorepo**
2. **charm vs snap**
3. **root/meta product vs leaf aggregation context**
4. **equivalent YAML/workflow encodings of the same canonical signal**

Anything outside those classes should be treated cautiously. In most cases it is either:
- an alignment issue in the repo,
- a sign that the metric is still too immature to gate scoring, or
- a reason to mark the metric unmeasurable until a better standard is defined.

## Remaining phases

## Phase 2 — Cross-product metric audit

Objective: review every existing metric across tracked products and classify each result as:
- detector is correct,
- detector is wrong,
- rubric is too strict or too loose,
- repo is genuinely non-compliant, or
- metric is currently unmeasurable for that repo.

Why this phase exists:
- the foundation work improved fidelity, but trust comes from validating actual fleet outcomes, not just better unit tests.
- this phase produces the evidence needed to decide whether later changes belong in detectors, rubrics, or repo alignment work.

## Phase 3 — Sanctioned-variance catalog

Objective: document, per dimension and per metric, which variants are explicitly supported and which are intentionally not supported.

Why this phase exists:
- it prevents future contributors from growing scorer complexity in an ad hoc way,
- and turns the philosophy into a reusable review checklist for future PRs.

## Phase 4 — Metric-by-metric calibration pass

Objective: calibrate each metric using the Phase 2 audit results.

For each metric:
1. inspect the fleet-wide distribution,
2. spot-check representative repos,
3. tighten or simplify the detector,
4. decide whether the metric should be gating, informational, or deferred.

Why this phase exists:
- PQF only becomes useful for planning once each metric is both understandable and reasonably trustworthy.

## Phase 5 — Rubric recalibration

Objective: revisit medal thresholds and gating choices once metric trust is stronger.

Why this phase exists:
- even good detectors can produce noisy medals if the rubric includes too many immature signals or thresholds that do not reflect real quality posture.

## Phase 6 — Alignment follow-up

Objective: turn calibration findings into concrete follow-up work across tracked products.

Outputs may include:
- scorer fixes,
- repo standardization work,
- guidance updates,
- and candidate new standards where measurability is weak today.

Why this phase exists:
- PQF is not just a scoring surface; it should help drive better alignment and more intentional engineering standards.

## Phase 7 — Operationalization

Objective: use calibrated PQF results in regular product-review workflows.

Examples:
- recurring product reviews,
- roadmap planning,
- trend tracking,
- and UI/reporting improvements that help teams understand why they were scored the way they were.

Why this phase exists:
- calibration work is only complete when the scores are trustworthy enough to support decision-making, not just experimentation.

## Practical review rule for future changes

When a proposed scorer change adds complexity, ask:

1. Is this supporting one of the sanctioned variance classes?
2. Does it reduce a real false positive or false negative we have observed?
3. Is the resulting rule still easy to explain?
4. Would it be better to keep the detector prescriptive and fix repo alignment instead?
5. If the answer is still unclear, should the metric remain informational or unrated for now?

If those questions cannot be answered cleanly, the change is probably too complex.
