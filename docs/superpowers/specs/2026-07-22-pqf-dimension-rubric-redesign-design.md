# PQF Dimension Metric and Rubric Redesign

## Context

PQF is in a strong proof-of-concept state for product modeling, overlap handling, imported products, and the dashboard UX. Its current weakness is the scoring foundation itself: several dimensions still rely on fake or semi-fake logic, and some medal thresholds are arbitrary rather than policy-backed. That makes current medals useful for demonstrating the tool, but not yet trustworthy enough for squads to use for planning and prioritization.

The next iteration must make PQF a credible product-quality decision tool without overwhelming users with too many metrics. The redesign should therefore favor a small, explainable set of high-signal metrics per dimension, while allowing additional signals to exist as informational guidance.

## Goals

- Make PQF scores trusted and explainable on a product-by-product basis.
- Keep all five existing dimensions active so computed medals remain valid portfolio-wide.
- Replace fake or semi-fake logic with deterministic evidence wherever possible.
- Use a small core metric set per dimension so the tool stays approachable for new users.
- Keep AI-assisted metrics visible where useful, but non-gating in v1.
- Align metrics and thresholds with Canonical practices and selected external guidance where that improves trust.

## Non-Goals

- Maximizing metric count per dimension.
- Designing a weighted composite scoring model for v1.
- Using AI to gate bronze, silver, or gold medals in v1.
- Perfectly encoding every policy source on day one.

## Decision Summary

1. Keep the existing five dimensions: `test_verification`, `documentation`, `substrate_compat`, `security_ssdlc`, and `support_engagement`.
2. Use a **core-gated** model: each dimension has a small deterministic core set of medal-driving metrics plus optional informational metrics.
3. Treat any metric not referenced in medal criteria as informational by definition; no explicit informational flag is required.
4. Keep AI-assisted metrics informational only in v1.
5. Define **bronze** as the minimum production-ready bar, **silver** as a strong consistent engineering baseline, and **gold** as a strict best-practice excellence bar.
6. Prefer deterministic evidence from repository configuration, CI workflows, test artifacts, and documented process signals over inferred or heuristic checks.
7. Review repolint and other Canonical guidance sources, but import only high-signal checks that improve trust and explainability.

## Scoring Policy

### Core vs informational metrics

Each dimension should expose two kinds of signals:

- **Core metrics**: directly referenced by medal criteria and therefore capable of changing the medal.
- **Informational metrics**: surfaced in the UI to guide teams, but not referenced by medal criteria.

This keeps the medal model simple while preserving room for richer evidence and future expansion.

### Tier semantics

- **Bronze**: the product meets the minimum quality expectations to be considered production-ready in that dimension.
- **Silver**: the product demonstrates a stronger, more consistent engineering baseline.
- **Gold**: the product meets a strict, limited set of excellence criteria. Gold should be intentionally hard to earn.

### AI-assisted policy

AI-assisted checks remain valuable for subjective areas such as landing-page quality or broad documentation characterization, but they should not gate medals in v1. They should be clearly labeled in the UI and used to guide improvement rather than determine readiness.

## Dimension Designs

### 1. Test Verification

#### Intent

Measure whether the product has credible automated verification with enough breadth and reliability to justify engineering confidence.

#### Core metrics

- `coverage_pct`
- `latest_build_passing`
- `stability_pct`
- `integration_test_evidence_present`

#### Informational metrics

- `uses_ops_testing`
- `uses_jubilant`
- future flakiness or retry-pattern signals if they can be measured reliably

#### Threshold direction

- **Bronze** should require a passing latest build plus a meaningful minimum coverage floor.
- **Silver** should require stronger coverage and stable CI behavior.
- **Gold** should require very high coverage and very high CI stability.
- `integration_test_evidence_present` should become a silver-or-higher differentiator so products cannot reach higher tiers with only shallow unit-test evidence.

#### Notes

The current `uses_jubilant` signal is useful, but it should not be the core proxy for integration quality. The main gate should be deterministic evidence that integration testing exists and runs, regardless of the exact framework.

### 2. Documentation

#### Intent

Measure whether the repository exposes the minimum documentation and process structure needed for users, contributors, and security reporters to work effectively.

#### Core metrics

- `has_readme`
- `has_contributing`
- `has_security`
- `release_notes_process_enabled`

#### Informational metrics

- `uses_rtd_hosting`
- `landing_page_quality`
- `diataxis_coverage`
- `docs_lint_passing`
- `docs_style_checks_passing`
- `links_passing`

#### Threshold direction

- **Bronze** should require the foundational repository docs and release-notes process signal.
- **Silver** should reward stronger documentation maturity once the technical-author baseline is finalized.
- **Gold** should remain selective and only adopt additional doc gates once the team has a stable, policy-backed list.

#### Notes

- Documentation lint/style/link checks should be sourced from CI or workflow evidence, not AI.
- The exact v1 silver/gold documentation gates should remain compatible with the upcoming technical-author guidance.
- `uses_rtd_hosting` is valuable as an informational maturity signal even if it does not gate medals initially.
- `landing_page_quality` can remain AI-assisted and informational in v1 because it reflects a current strategic objective without being deterministic enough to gate medals yet.

### 3. Substrate Compatibility

#### Intent

Measure whether a product makes clear, evidenced compatibility commitments across the Juju and substrate environments that matter to Platform Engineering.

#### Core metrics

- `supports_juju_3`
- `supports_juju_4`
- `substrate_test_evidence_present`

#### Informational metrics

- optional advanced substrate capability signals
- future maturity signals imported from charm guidance or repolint if they prove high-signal

#### Threshold direction

- **Bronze** should require a clear supported Juju baseline appropriate for the product.
- **Silver** should require stronger evidence that declared compatibility is tested, not merely stated.
- **Gold** should require next-generation compatibility plus credible evidence coverage.

#### Notes

The previous `supports_ck8s` signal was too narrow and ambiguous as a stand-alone medal gate. The redesigned dimension should focus on declared compatibility plus deterministic proof that the declared substrates are actually exercised or documented in a verifiable way.

### 4. Security / SSDLC

#### Intent

Measure whether the repository is wired into Canonical’s baseline security automation and review controls, while creating room to grow this dimension over time.

#### Core metrics

- `renovate_enabled`
- `canonical_repo_automation_registered`
- `branch_protection_required_checks`
- `sast_workflow_present`

#### Informational metrics

- `cve_tracking_process_present`
- future secret-scanning, release-hardening, or advisory-management signals

#### Threshold direction

- **Bronze** should require the minimum repo-management and branch-safety controls.
- **Silver** should require dependency update automation and a present security-analysis workflow.
- **Gold** should require the strongest practical combination of those controls once the repo landscape is baselined.

#### Notes

- Replace `dependabot_enabled` with `renovate_enabled`.
- Central registration with `canonical-repo-automation` is a first-class signal because it reflects how security and repo settings are actually managed.
- This dimension is intentionally designed as a foundation for future growth; it should start with existing signals the organization already expects, not speculative ideal-state criteria.

### 5. Support Engagement

#### Intent

Measure whether the owning team is responsive enough that users and contributors can get issues triaged and changes reviewed in a reasonable time.

#### Core metrics

- `avg_triage_days`
- `avg_pr_review_days`
- `response_coverage_rate`
- `ownership_signal`

#### Informational metrics

- `has_jira_sync`
- other routing or workflow hygiene signals

#### Threshold direction

- **Bronze** should require acceptable responsiveness plus a clear ownership signal.
- **Silver** should tighten responsiveness expectations and require better response coverage.
- **Gold** should represent consistently fast response behavior, not just good averages distorted by a few outliers.

#### Notes

The current time-based metrics are directionally good, but they should be complemented by a coverage-oriented signal so squads cannot appear healthy if only a subset of issues or PRs receive timely attention.

## External Guidance Alignment

PQF should use external and adjacent internal sources as inputs, not as unfiltered imports.

### repolint

repolint is a strong candidate source for deterministic repository compliance checks, especially where it already validates high-signal hygiene or policy conformance. It should be reviewed dimension by dimension, and only checks that are:

- understandable by non-experts,
- durable across repositories,
- low-noise, and
- clearly connected to product quality

should be copied into PQF.

### Canonical policy and guidance sources

Relevant sources include SSDLC directives, documentation compliance guidance, and charm maturity guidance. If these sources disagree, the implementation should choose the threshold that best supports the v1 goals of trust and explainability, and record the rationale in the scorer or supporting docs rather than trying to average all sources mechanically.

## Implementation Blueprint

### Phase A: Metric contract redesign

- Update `config/dimensions.yaml` for all five dimensions.
- Revise metric names, descriptions, and medal criteria to reflect the new core-gated model.
- Leave informational metrics in `outputs` without referencing them in `medals`.

### Phase B: Deterministic signal wiring

- Replace fake or semi-fake scorer logic with deterministic checks based on repository files, GitHub configuration, workflow definitions, published artifacts, and other verifiable inputs.
- Reuse existing CI and repo automation evidence where available instead of inventing new proxies.
- Keep AI limited to informational outputs such as landing-page quality.

### Phase C: External baseline alignment

- Review repolint and other guidance sources for candidate checks.
- Import only the subset that strengthens PQF without making it noisy or opaque.
- Document any policy conflicts and the selected rationale.

### Phase D: Tier calibration and validation

- Run the redesigned scorers across the imported product set.
- Inspect medal distribution and failed criteria per product.
- Tune thresholds to maximize trust and explainability, not to maximize pass rates.

### Phase E: Governance

- Add a lightweight rubric review loop for future metric and threshold changes.
- Treat each criterion change as a product decision that needs explicit rationale.

## Validation Strategy

The redesign is successful when:

- products receive medals that are explainable by a small number of understandable failed or passing gates,
- squads can tell what to fix next without reading raw scorer code,
- informational metrics enrich decisions without making medals feel arbitrary, and
- portfolio-wide results look believable when compared with known team expectations.

## Risks and Mitigations

### Risk: too many metrics creep into medal logic

Mitigation: enforce the small core-set rule per dimension and keep additional signals informational.

### Risk: policy-backed documentation criteria are still evolving

Mitigation: keep documentation silver/gold gates conservative until the technical-author guidance is finalized.

### Risk: SSDLC expectations outpace current repo reality

Mitigation: start with existing, verifiable controls already expected in practice, then expand later.

### Risk: averages hide poor support behavior

Mitigation: add `response_coverage_rate` alongside average time metrics.

## Open Follow-Up Inputs

The following inputs should be incorporated during implementation calibration, but they do not block this design:

- the technical-author recommended documentation baseline,
- the exact release-notes process documentation and detection strategy,
- the repolint check shortlist worth adopting,
- the best deterministic source for `canonical_repo_automation_registered`, and
- whether charm maturity guidance yields any high-signal substrate criteria beyond compatibility and test evidence.
