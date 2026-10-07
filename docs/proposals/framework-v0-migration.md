# V0 alignment goal and migration assessment

## Goal

Implement the team's [V0 proposal](framework-v0.md) for the 27.04 cycle:
**Testing, Documentation and Security (SSDLC)**. Engagement belongs to
[V1](framework-v1.md). This is the agreed scope direction, not permission to replace the live
contract without review. The measurement decisions below have now been resolved for implementation.

Assessment baseline: local `main` at `efce6c2`, with V0 active and V1 upcoming.
Compared against the versioned contracts, registry, scorer implementations, rubric evaluator
and aggregation logic. Implementation now replaces V0 with the agreed target.

## Assessment

The scope is coherent: Testing grades adoption of agreed tools and platforms; Documentation
grades contributor/user guidance and Sphinx Stack adoption; Security makes all three protections
a baseline. CI health and AI documentation coverage remain informational.

Testing has grown from two metrics to nine. The tool-adoption checks are relatively narrow;
the complex areas are branch-aware CI health and platform configuration/run evidence.
Keep their logic bounded rather than expanding repository-specific heuristics.

### Measurement decisions resolved for implementation

| Topic | What needs settling |
| --- | --- |
| Applicability | Missing charm integration tests must not exempt a charm from Jubilant or `charm-ci` requirements. Non-charm products are exempt; genuinely sanctioned exceptions need explicit rules. Missing a required pipeline is a failure, not an exemption from its platform checks. |
| Entirely non-applicable rubrics | All graded Testing metrics are charm-specific. Snaps must receive a not-applicable Testing result, not Gold because every condition was skipped. Terraform absence alone may be legitimate N/A. |
| CI branch discovery | Charmhub tracks are not branch names: the team policy maps workload tracks to `track/<major>.<minor>` and main to `latest/edge`. Define which published tracks remain in scope, missing-branch handling, and discovery for snaps or other repositories. |
| CI evidence attribution | A PR head is not automatically proof of the merged result, especially after squash merges or subsequent changes. Define accepted merged-PR evidence, latest reruns, pending/cancelled/skipped jobs, and which jobs “all jobs” includes. Keep per-branch evidence even if the headline value is one boolean. |
| Moving Juju targets | “Latest stable Juju 4” and “current LTS” can change scores without repo changes. Specify an authoritative source and record the resolved release/channel and evaluation time, or pin cycle targets. Define whether patch currency is part of the standard. |
| Documentation content | “Actionable guidance” and “beyond a heading” need deterministic rules. Define template comparison/normalization and authoritative template revisions; do not turn these gates into subjective AI reviews. |
| Negative-only detectors | No Harness reference does not prove Ops Testing is used. No self-hosted flag does not prove GitHub-hosted unit tests exist. Agree whether these measure absence of deprecated configuration or positive adoption. |
| Security tiers | Bronze, Silver and Gold have identical requirements. The current engine selects Gold first, so a compliant repo gets Gold, not Bronze. This can be an intentional universal baseline, but it must be stated plainly. The approving-review question is not yet an approved Silver gate. |
| Root uncertainty | Current aggregation takes the worst scored component and can omit insufficient components. Decide explicitly whether required unknown component evidence should block the root result. This policy must not depend on payload format. |

### Resolved: one model, no legacy compatibility

The tool is pre-adoption and has no dependent consumers. Replace scalar metric payloads with one
structured result throughout scorers, computed envelopes, the engine, public data and UI:
**measured value**, **not applicable**, or **insufficient data**, with reasons for non-measured states.

There is one evaluator, no scalar adapters, no separate outcome-metadata map, no per-metric format
opt-in and no legacy scoring paths. Metric YAML retains its ordinary type, implementation and rubric
fields; scorer logic owns eligibility. This does not require a general-purpose YAML detection language.

All current producers, consumers and fixtures migrate together. Regenerate active/upcoming results
before deployment and prevent stale scalar artifacts being carried forward. Preserve framework
snapshots, digests and immutable implementation revisions for provenance, not obsolete behavior.
Archived scoring remains frozen; any archived payload migration must be format-only and reviewed.

The detailed first slice is the
[metric outcomes foundation plan](../superpowers/plans/2026-10-07-v0-metric-outcomes-foundation.md).

**Implementation scope:** the shared result type, strict construction/JSON validation, scorer
transport, evaluator, root uncertainty, assembly and dashboard migrate together. The V0 contract
selects changed measurement revisions. No generated artifacts are committed; the publish matrix
requires fresh live data before deploying the new reader.

### Resolved: required uncertainty and positive adoption

An applicable component with insufficient required evidence makes its root dimension insufficient.
Explicitly excluded and N/A components do not count; a root with none remaining is N/A.
Ops Testing requires positive `ops.testing` adoption and no legacy Harness in component unit tests.
GitHub-hosted testing requires identifiable unit jobs, not merely the absence of a self-hosted flag.
Missing expected tests or configuration is measured failure.

### Resolved: CI branch policy and stable Juju targets

For charms, inspect the default branch and `track/<track>` for every published non-`latest`
Charmhub track. Missing mapped branches are insufficient data. Snaps inspect the default branch
for now. Do not borrow unproven PR-head results after squash merges; latest branch evidence must
be attributable to its commit. CI health remains informational.

V0 pins Juju `4/stable` and `3.6/stable` in the contract. It does not grade current patch currency
or silently follow future LTS changes.

### Resolved: documentation customization and exemptions

README, CONTRIBUTING and SECURITY use the same root-level deterministic body/template rule.
Compare against template commit `8299de3ec4a264c853d48c6bb09903677e38cbd7`; SECURITY is not a
subjective reporting-guidance detector. Snaps are Sphinx N/A; upstream-docs exclusions require
a reviewed `documentation_exemption` reason. Explicit leaf docs repository/path fields select
the authoritative source for the optional AI assessment.

### Resolved: Renovate onboarding evidence

The team chose enabled configuration **plus an open Dependency Dashboard authored by the verified
Renovate bot**. Configuration alone, a human-created dashboard, closed issues and update PRs do not
qualify. This is observable onboarding evidence, not a claim that the service is currently running.
Dashboard timestamps are not reliable heartbeats, so V0 adds no recency heuristic or activity clock.
Required issue/config acquisition errors fail the job.

### Resolved: platform configuration, not run health

Canonical K8s, Juju 4 and Juju LTS grade the required integration-test `charm-ci`
configuration only. Configuration must be linked to the actual integration job; unused
Concierge files do not count. Missing required configuration is a measured failure.
Successful or failing runs belong to informational `ci_passing`, not these medal gates.

### Resolved: Sphinx Stack adoption

Any valid Sphinx Stack version recorded in the applicable `docs/_dev/version` qualifies
for Gold; V0 does not impose a minimum version. An absent or invalid version is measured
non-adoption, an approved exemption is N/A, and unavailable evidence is insufficient data.
Define the version parser and payload representation in the implementation plan.

The referenced repolint checks are useful prior art, not complete scoring specifications:
`ck8s` checks `providers.k8s` configuration, not passing runs; `use_gh_runners` is limited to
`operator-workflows/test.yaml`; `tf_v1` can pass an empty module list; and Harness detection
searches broadly for the word. PQF should reuse their standard intent without inheriting
false positives, empty-evidence success or overly narrow encodings.

## Current V0 to target V0

### Testing

Keep the internal dimension key `test_verification` unless a rename has a concrete benefit;
change its display label to **Testing**. Put platform metrics in this dimension as agreed,
not in a new V0 `substrate_compat` dimension.

| Metric | Current behavior | Required change |
| --- | --- | --- |
| `ci_passing` | `latest_build_passing` gates Bronze/Gold. Uses unscoped Allure summary or the single latest terminal check on default-branch HEAD. | New informational metric/revision. Discover scoped branches, inspect all relevant jobs and attribute runs to commits. Do not reuse unproven Allure evidence. Retain branch-level provenance. |
| `uses_ops_testing` | Scorer returns it, but no contract output or registry binding exists. Searches one Harness import repo-wide. | Bind a new metric; implement agreed deprecated-Harness/positive-adoption rule within component scope. |
| `uses_gh_runners_unit_testing` | Absent. | Add workflow-aware unit-test runner detection, covering approved encodings and explicit defaults. |
| `uses_jubilant` | Repository-wide code-search match for `import jubilant`. | New revision for component-scoped integration-test inspection and supported imports; do not let one component satisfy all others. |
| `uses_tf_v1_provider` | Absent. | Inspect all in-scope Terraform modules and Juju provider constraints. No modules is N/A, not successful adoption. Agree constraint semantics rather than copying a literal regex. |
| `uses_charm_ci` | Absent; V1 has a generic integration-evidence detector. | Add parsed reusable integration-workflow detection. An incidental text mention must not count; `operator-workflows` alone does not satisfy this adoption gate. |
| `supports_canonical_k8s` | V1-only `uses_canonical_k8s` scans workflows and even accepts a MicroK8s bootstrap command. | New metric in Testing. Read relevant charm metadata and linked Concierge config; distinguish Canonical K8s from MicroK8s. Grade configuration only, not run success. |
| `supports_juju_4` | V1-only revision matches exact `juju-channel` workflow strings. | New revision/binding in Testing for charm-ci/Concierge config and resolved stable target. Do not repoint the existing V1 binding in place. |
| `supports_juju_lts` | Absent; V1 has `supports_juju_3`. | Add target-aware LTS metric; do not assume Juju 3 support is implied by Juju 4. |

Replace the rubric with the proposal's explicit Bronze/Silver/Gold conditions. `ci_passing`
must leave `required_metrics_for_scoring`; missing informational health cannot block a medal.
Define missing evidence policy for graded metrics without making unrelated upper-tier signals
silently exempt.

### Documentation

| Metric | Current behavior | Required change |
| --- | --- | --- |
| `readme_present` | Non-empty README at component subpath when configured. | New revision for repo-root policy, agreed template rejection and deterministic content checks. |
| `contributing_present` | Non-empty CONTRIBUTING at component subpath. | Same root/template correction with shared repo evidence. |
| `has_security` | SECURITY file exists at component subpath. | New revision using exactly the README/CONTRIBUTING root/body/template rule. |
| `uses_sphinx_stack` | Absent. | Add version-valued output and explicit exemptions. Any valid version qualifies for Gold; absent or invalid versions do not. Resolve root/component docs scope. |
| `diataxis_coverage_ai` | Reads README and docs index only; missing key or broad exception returns zero. | Keep informational. New revision for authoritative docs coverage and evidence; unavailable assessment must not masquerade as zero coverage. Separate optional AI work from deterministic gates. |

Move SECURITY into Silver and Sphinx Stack into Gold. Remove `uses_rtd_hosting` from V0;
V1 records whether to retain or drop that independent hosting signal.

### Security

| Metric | Current behavior | Required change |
| --- | --- | --- |
| `renovate_enabled` | Local config or repository code-search mention. Central automation registration is returned separately. | New revision verifying actual Canonical Renovate onboarding/enabled state. Central repo registration alone is not proof Renovate is enabled. |
| `branch_protection_required_checks` | Classic protection endpoint only. | New revision combining effective classic protection and applicable rulesets, with required checks and agreed bypass semantics. |
| `signed_commits_required` | Classic protection endpoint only. | New revision covering effective signature requirements from applicable rulesets as well. |

Put all three requirements into the baseline, preserving the team's identical-tier choice unless
clarified otherwise. Authentication/rate-limit/server failures must fail acquisition after
supported retries; absence of a rule can be measured false. Do not conflate either with N/A.

### Dropped, moved or retained

- **Move Engagement out of V0:** `ownership_signal` and `response_coverage_rate` leave the active
  contract. V1 keeps ownership, counts and responsiveness candidates.
- **Replace rather than duplicate CI health:** `latest_build_passing` leaves V0's graded outputs;
  `ci_passing` is informational.
- **Replace RTD in the V0 proposal:** `uses_rtd_hosting` leaves V0; Sphinx Stack is the new Gold gate.
- **Consolidate platform checks into Testing:** no separate V0 substrate dimension. V1's older
  Juju 3 signal is superseded in intent by V0's explicit LTS check, not deferred as a new feature.
- **Leave broader candidates in V1:** release notes, changelog, docs CI, SAST, CVE process,
  dependency coverage, LICENSE/CODEOWNERS/PR templates, Ubuntu support and rootless execution.

## Delivery sequence

1. **Resolve the measurement decisions above.** Clean the exported V0 formatting and freeze the
   intended behavior, types, exemptions and rubric predicates. This precedes scorer implementation.
2. **Implement metric-level outcomes.** Follow [issue #43](https://github.com/canonical/pqf/issues/43)
   through one uniform payload, evaluator, assembly and UI. Convert existing runners and fixtures
   together; no legacy compatibility layer. Guard against vacuous Gold when no graded metrics apply.
   Resolve root uncertainty as a separate policy decision, not a side effect of serialization.
3. **Add bounded evidence acquisition and new immutable revisions.** Shared repo/branch/config
   acquisition feeds pure evaluators; do not add environment reads or framework-version branches
   inside measurement logic. Register all source fingerprints used by cached runners.
4. **Wire the candidate contract and all display surfaces.** Update V0 outputs, applicability,
   rubric and labels; adapt metric value rendering, threshold displays, filters and docs.
   Validate in isolation before replacing the active contract.
5. **Calibrate on representative products.** Include single charms, machine/K8s monorepo
   components, Terraform-free charms, snaps, shared CI callers and docs exemptions.
   Include Traefik from [issue #42](https://github.com/canonical/pqf/issues/42).
6. **Roll out the reviewed V0 update.** Rescore through normal generation/deployment commands,
   explain changed results, and publish the agreed alignment guidance. Do not hand-edit generated
   measurements, version indexes or portfolios. Deploy structured artifact readers and regenerated
   data together; do not carry forward obsolete scalar envelopes.

### Versioning and rollout guardrails

V0 is currently **active**, so updating it changes the official quality view. Implementation
revisions listed in the proposal are illustrative, not permission to mutate existing revisions.
Use new IDs for changed measurements; the proposal's `ci_passing/v1` also needs the schema-compatible
hyphenated form `ci-passing/v1`.

The registry currently binds an implementation to both dimension and output key. Moving a V1
substrate implementation into Testing therefore requires a deliberate new binding/revision or
registry design change, not just a YAML move. Reconcile V1 contract references explicitly; do not
keep obsolete runtime paths just for compatibility or silently mutate existing measurement revisions.

Published-artifact inventory contains V0, V1 and the separate `/legacy/` snapshot, with no archived
framework artifacts requiring migration. Do not edit archived scoring contracts. The V1 discussion document is a candidate backlog;
its existing upcoming YAML contract will need a separate reviewed reconciliation rather than
being assumed to inherit V0 changes automatically.

### Completion bar

The target is ready when teams can explain each result and verify its evidence, exceptions never
look like failures or automatic medals, changed metrics use immutable revisions, and representative
fleet results match the agreed standard. Relevant validation includes schema checks, Python and UI
tests, and verified generated/displayed outcomes—not just detector unit tests.

### Delivery evidence and activation

The implementation covers all three V0 dimensions and the uniform result pipeline, with changed
measurement revisions registered separately from V1's current revisions. Review corrections
include unit-only Ops Testing, explicit Juju Terraform provider source, and comment-insensitive
template comparisons.

Live calibration and normal generation commands covered Traefik, the Mailserver Operators
machine/snap monorepo, and an upcoming V1 artifact. Traefik currently measures Testing below
minimum, Documentation Gold and Security Gold. Dovecot measures Testing Silver; the OpenDKIM
snap's Testing result is N/A, not Gold. These are representative checks, not a claim that the
entire product set has been measured locally.

Before production activation, configure **`PQF_GITHUB_TOKEN`** with the read permissions described
in [architecture](../architecture.md#measurement-failures). The ordinary Actions token cannot
read other repositories' classic branch protections. The secret was absent during implementation;
no user credential was copied into repository secrets. Merge triggers full live-version
regeneration; the new dashboard must deploy only after that succeeds. Generated measurements,
product sets and version indexes are not included in the PR.

**Sources:** `framework/versions/v0/dimensions.yaml`, `framework/versions/v1/dimensions.yaml`,
`scorers/registry.py`, the dimension scorers, `engine/rubric.py`, `engine/aggregation.py`,
the proposal's linked repolint checks, and the
[team's branch/track policy](https://github.com/canonical/platform-engineering-docs/blob/main/docs/reference/charm-development/trunk-based-development.md).
