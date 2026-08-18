# Metric Calibration Governance Design

## Goal

Make PQF's metric-calibration philosophy explicit and durable so future human and AI contributors preserve simplicity, deterministic behavior, and high-confidence scoring as the framework evolves.

## Problem statement

The calibration work established a deliberate philosophy:
- keep metrics simple and explainable,
- support only a small set of sanctioned structural variants,
- distinguish low measured values from unmeasurable signals,
- and resist expanding detector complexity to absorb arbitrary repo drift.

Today that philosophy exists mostly in prior PRs, agent context, and conversation history. If it is not captured in the repo's primary guidance documents, future contributors may gradually reintroduce complexity, permissive heuristics, and ambiguous scoring semantics.

## Scope

In scope:
- encode the calibration philosophy in the repo's main contributor-facing documents,
- record the sanctioned-variance policy and the measured-vs-unmeasured distinction,
- document the remaining calibration phases so future work has a stable reference,
- create a PR containing only these governance/documentation changes.

Out of scope:
- new scorer logic,
- rubric changes,
- product rescoring,
- UI changes.

## Design principles

1. **One concise repo-wide statement, several context-specific reinforcements**
   - README should state the philosophy briefly and link deeper guidance.
   - AGENTS.md should contain the strict contributor rules for scorers and rubrics.
   - local-scoring docs should explain the operational semantics (`None`/`unrated`/`insufficient_data`).

2. **Low duplication, high visibility**
   - Avoid repeating long prose in multiple places.
   - Keep one roadmap-oriented document for calibration phases and reference it from broader docs.

3. **Policy should be actionable**
   - State not just the philosophy, but the concrete decision rules contributors must follow.
   - Explicitly name the sanctioned variant classes.

## Proposed documentation changes

### README.md
Add a short section describing PQF's metric-calibration philosophy:
- deterministic and prescriptive metrics,
- support only sanctioned structural variants,
- treat unmeasurable as unrated,
- use PQF to drive alignment rather than encode every local variation.

This section should link to AGENTS.md and the deeper docs.

### AGENTS.md
Add a dedicated section for scorer/rubric evolution rules:
- false-positive/false-negative reduction is required,
- metric logic must remain easy to explain in one sentence,
- only sanctioned variants are supported,
- sanctioned variants currently include monorepo vs non-monorepo, charm vs snap, root/meta vs leaf aggregation context, and equivalent YAML/workflow encodings of the same canonical signal,
- arbitrary team-specific drift should not be normalized into scorer logic,
- measured-low and unmeasurable must never be collapsed.

### docs/local-scoring.md
Extend the measurability section with:
- how contributors should think about `required_metrics_for_scoring`,
- examples of low-value vs unmeasured,
- reminder that gating should only use high-confidence measurable signals.

### New roadmap document
Create a dedicated doc capturing the remaining phases after the foundation work:
1. portfolio-wide metric audit,
2. sanctioned-variance catalog,
3. metric-by-metric calibration pass,
4. rubric recalibration,
5. alignment follow-up,
6. operationalization.

The roadmap should explain the objective of each phase and how it connects back to the philosophy.

## Success criteria

1. A future contributor can read the repo docs and infer the calibration philosophy without reading prior PRs.
2. The sanctioned-variance rule is explicit enough to prevent ad hoc detector expansion.
3. The next phases are recorded in a stable location that can be referenced in future PRs/issues.
4. The PR is documentation-only and easy to review.
