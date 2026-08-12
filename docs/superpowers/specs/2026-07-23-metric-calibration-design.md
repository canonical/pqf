# PQF Metric Calibration Design Spec

## Goal

Raise metric fidelity so PQF medals reflect actual product quality posture rather than detector gaps, while preserving deterministic behavior and a simple onboarding signal set.

## Problem statement

Current scoring has a high false-negative rate caused by:
- narrow detector patterns (workflow naming/path assumptions),
- source coupling (Allure-only build status),
- and unknown-as-failure defaults (`0`/`false`) that collapse unmeasurable and failing into the same outcome.

This suppresses signal quality and makes medals difficult to trust for planning.

## Scope

In scope:
- recalibrate metric logic for all dimensions,
- codify unrated vs bronze semantics,
- add per-metric measurability handling,
- phase metric gate re-enablement based on detector confidence.

Out of scope:
- broad new metric expansion,
- UI redesign beyond existing observability views,
- replacing deterministic signals with opaque AI scoring.

## Design principles

1. **Deterministic-first**
   - Prefer explicit API/files/workflow evidence.
2. **Measured vs unmeasurable separation**
   - `bronze` means measured-low; `unrated` means cannot be measured reliably.
3. **Prescriptive-with-bounded-variation detection**
   - Support only sanctioned structural variants (monorepo vs single-repo, charm vs snap).
   - Do not normalize arbitrary team-by-team differences when PQF is intentionally driving alignment.
   - Keep each metric rule explicit and easy to explain in one sentence.
4. **Progressive strictness**
   - Gate only metrics with demonstrated detector reliability.
5. **Traceable scoring**
   - Each metric should expose enough provenance to explain outcomes.

## Proposed architecture changes

## 1) Metric measurability contract

For each dimension metric:
- define `measurement_source` (e.g., `allure`, `github_checks`, `workflow_parse`, `repo_files`),
- define `measurement_status` (`measured`, `unavailable`, `insufficient_sample`),
- emit value only when measured, otherwise omit or emit explicit null-like marker interpreted as unmeasurable.

Engine changes:
- dimension applicability for leafs becomes `INSUFFICIENT_DATA` when required gated metrics are unmeasurable.
- root aggregation preserves `UNRATED` when all in-scope leaves are insufficient/not-applicable.

## 2) Detector normalization layer

Add per-dimension normalization helpers:
- workflow parser utilities (structured YAML token extraction),
- check-run family matchers limited to sanctioned aliases,
- evidence-source fallbacks with clear priority.

This avoids duplicating brittle regex logic in each scorer.

## 3) Gate strategy split

Classify metrics into:
- **Gating metrics**: high-confidence deterministic signals used in medal criteria.
- **Informational metrics**: visible in UI/reporting, not used for medal tiers until confidence target is met.

## 4) Calibration loop

For each metric:
1. run across full portfolio,
2. inspect distribution and outliers,
3. spot-check against source repositories,
4. decide whether observed variation is sanctioned (support) or misalignment (fail),
5. implement logic updates + tests,
6. re-run distribution and verify improved alignment.

## Dimension-level design decisions

## test_verification
- Add `latest_build_passing` fallback to default-branch check-run status when Allure is absent.
- Keep Allure for coverage/stability where available; otherwise treat as unmeasurable, not zero.
- Keep integration/jubilant/ops signals primarily informational until fidelity validated.

## documentation
- Expand README/CONTRIBUTING detection only for sanctioned layout variants
  (for example mono-repo scoped docs paths), not arbitrary heading styles.
- Replace strict docs workflow-name requirements with a bounded alias map
  that reflects approved workflows.
- Broaden Diátaxis detection to directory and file-family patterns.
- Keep RTD/release-notes as informational until detector maturity.

## substrate_compat
- Replace regex text scans with parsed workflow signal extraction for Juju channels/matrix and substrate targets.
- Accept alternate naming conventions for Canonical K8s and integration jobs.

## security_ssdlc
- Replace canonical-repo-automation code-search heuristic with deterministic onboarding source.
- Keep branch protection and renovate as primary gates.
- Expand SAST and CVE process detection only where aliases map to approved security workflow patterns.

## support_engagement
- Introduce sample-size thresholds and minimum-observation logic.
- Differentiate no-data from measured-zero.
- Keep ownership signal as low-cost foundational gate.

## Validation and testing strategy

1. Unit tests per scorer for each accepted variation.
2. Portfolio-level regression check:
   - pre/post metric distributions,
   - medal distribution drift report.
3. Golden-case spot checks for selected representative repos (including saml-integrator-operator build-status case).
4. CI checks:
   - existing lint/test/build only (no new toolchain).

## Success criteria

1. No metric remains at pathological all-false/all-zero rates without explicit rationale.
2. False-negative examples identified in audit are corrected or explicitly documented as intentional.
3. `unrated` is used only for truly unmeasurable/insufficient cases.
4. Medal outputs become decision-usable for triage and roadmap planning.

## Risks and mitigations

- Risk: overfitting or excessive permissiveness.
  - Mitigation: define only sanctioned variation classes and treat other divergence as actionable misalignment.
- Risk: introducing permissive patterns that inflate scores.
  - Mitigation: keep deterministic evidence requirements and cross-check with spot audits.
- Risk: private-data dependence (repo automation registration).
  - Mitigation: use source guaranteed accessible in CI context.

## Deliverables from implementation phase

1. Updated scorer logic and tests per metric.
2. Updated metric criteria and informational/gating classification in `config/dimensions.yaml`.
3. Updated local-scoring docs for new measurement semantics.
4. Updated audit artifact showing before/after distribution improvements.
