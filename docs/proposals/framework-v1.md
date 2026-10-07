# PQF V1 — candidate backlog

V1 is for the cycle after 27.04. [V0](framework-v0.md) is the immediate alignment goal;
this document captures later ideas, not additional V0 commitments.

Candidates below are not an approved scoring contract. Medal placement and measurement rules
must be agreed before implementation. A candidate may remain informational or be dropped.

V1 uses the same metric result model as V0: measured value, not applicable, or insufficient data.
Scorers determine eligibility; the engine handles those states uniformly. No separate legacy
format or additional YAML payload setting is required.

## 1. Testing and platform compatibility

### Integration-test evidence

**Existing ID:** `integration_test_evidence_present`

Check that integration tests exist and are invoked by CI, including approved shared workflows.
Distinct from V0's `uses_charm_ci`, which measures adoption of a particular pipeline.

**Decision needed:** does this add useful coverage beyond the V0 tool-adoption checks?

### Test pass rate and stability

**Existing IDs:** `coverage_pct`, `stability_pct`\
**Proposed status:** informational

Show results from a test report whose branch, commit and measurement time are known.
These existing metrics are test-outcome percentages, **not code coverage**.

**Decision needed:** retain both percentages only if they convey distinct, useful information.

### Ubuntu 26.04 support

Check support for the agreed Ubuntu base or runtime using explicit build and test evidence.

**Decisions needed:** which products does this apply to, and is declaring the base sufficient,
or must CI exercise it?

### Rootless charms and rocks

Track adoption of the agreed non-root execution model.

**Decisions needed:** define separate charm and rock expectations, legitimate exemptions,
and evidence of actual runtime behavior rather than a configuration declaration alone.

## 2. Documentation and contribution guidance

### Release-notes process

**Existing ID:** `release_notes_process_implemented`

Check adoption of the agreed release-notes process, including its structure and automation.

**Decision needed:** agree the standard before making its particular workflow mandatory.

### Changelog present

**Existing ID:** `has_changelog`\
**Proposed status:** informational

Check for a maintained changelog at an agreed location. The current detector checks root
`CHANGELOG.md`; [issue #42](https://github.com/canonical/pqf/issues/42) identifies
`docs/changelog.md` as another relevant convention.

### Documentation CI passing

**Existing ID:** `documentation_workflows_passing`\
**Proposed status:** informational

Check the latest relevant documentation lint, link-check and build jobs, including shared
workflows. Reuse the branch/run attribution rules agreed for V0's `ci_passing`.

### License present

Check that an appropriate license is present and discoverable.

**Decision needed:** file presence only, or validation of the license and its scope?

### CODEOWNERS present

Check that review ownership is explicit and covers the relevant repository paths.

**Decision needed:** distinguish this review-routing signal from owning-squad identification.

### Pull-request template present

Check that contributors have an agreed template for describing and validating changes.

**Decision needed:** is presence sufficient, or is specific content required?

### Read the Docs hosting

**Existing ID:** `uses_rtd_hosting`

Removed from the V0 proposal in favor of Sphinx Stack adoption. Hosting and documentation
tooling are different signals; retain this only if hosting needs its own measurement.

**Decision needed:** retain as informational, grade it, or drop it entirely?

## 3. Security (SSDLC)

### Static security analysis

**Existing ID:** `sast_workflow_present`

Check adoption of the agreed static security analysis, including analysis delegated through
shared workflows.

**Decision needed:** configuration presence, execution, or successful results?

### CVE tracking process

**Existing ID:** `cve_tracking_process_present`\
**Proposed status:** informational

Check evidence of an agreed vulnerability-maintenance process, not merely a mention of “CVE.”

### Renovate dependency coverage

Extend the V0 onboarding check to verify applicable dependency classes are actually managed:

- Python dependencies;
- charm dependencies; and
- Git dependencies.

**Decisions needed:** define each class, supported configuration, and how to prove it is enabled.

### Required approving review

Possible extension to V0's branch protection baseline: require at least one approving review.

**Decision needed:** is this a later Silver requirement or part of the baseline? It remains an
open question in V0, not an additional approved requirement.

## 4. Engagement

*Is ownership clear, and how much open work is visible?*

Engagement has moved out of V0 entirely. The initial V1 candidate is an ownership baseline
with informational workload counts; response-time metrics remain separate candidates.

### Candidate medal rubric

| Grade | Requires |
| --- | --- |
| Bronze | Ownership declared |

No distinct Silver or Gold requirements have been agreed.

### Ownership declared

**ID:** `ownership_signal`\
**Applies to:** tracked product repositories\
**What it measures:** whether the repository's owning squad is explicit and discoverable.

**Measurement:** read GitHub topics and check for exactly one valid owning-squad topic.

**Decision needed:** missing or conflicting topics are measurable ownership gaps, not evidence
retrieval failures. Agree the failure result and canonical topic format before implementation.

### Open pull requests

**Proposed ID:** `open_pr_count`\
**Status:** informational\
**Applies to:** tracked product repositories

Count open GitHub pull requests at measurement time, without a quality threshold.

**Decision needed:** include bot-authored PRs or show them separately?

### Open issues

**Proposed ID:** `open_issue_count`\
**Status:** informational\
**Applies to:** tracked product repositories

Count open GitHub issues at measurement time, explicitly excluding pull requests.

**Accepted variation for both counts:** root products show component detail; totals count each
repository once so monorepo components do not duplicate the same backlog.

### Responsiveness

**Existing IDs:** `response_coverage_rate`, `avg_triage_days`, `avg_pr_review_days`

Measure responses to issues and PRs, time to first issue response, and time to first PR review.
These are candidates, not agreed service commitments.

The earlier proposal suggested coverage thresholds of 80% / 90%, triage of 3 / 2 days,
and review of 5 / 3 days for Silver / Gold.

**Decisions needed:** observation window, bot handling, eligible responses, treatment of
unanswered items and empty samples, and whether those targets fit the team's working practices.

### Jira sync and repository traffic

**Existing IDs:** `has_jira_sync`, `repo_views_14d`\
**Proposed status:** informational

Retain only if these signals support an actual team decision. Neither is a quality measure
by itself; traffic also requires appropriate GitHub access.

## Before adopting a candidate

- Agree the practice and its applicability.
- Define passing, failing, insufficient-data and not-applicable outcomes.
- Validate representative fleet results, including monorepos and shared workflows.
- Justify its medal placement, or keep it informational.
- Use a new implementation revision when changing an existing measurement.

The [metric proposal template](framework-metric-proposal-template.md) can be used to develop
any candidate into a reviewable specification.
