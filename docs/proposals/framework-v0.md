# PQF V0 (27.04 cycle)

> **27.04 alignment goal:** the team-reviewed scope below is the V0 implementation target. Decisions and delivery status are recorded in the [migration assessment](framework-v0-migration.md).

## Purpose

V0 should give leadership and engineering teams a shared, trustworthy view of product quality. It is deliberately small: every metric must represent an agreed practice, be easy to understand and produce results teams can confidently act on.

V0 is our scope commitment for 27.04. Candidate metrics that need more discussion or measurement work remain in [V1](framework-v1.md) for a later cycle.

## Decisions requested

For each dimension, please review:

1. whether the proposed metrics represent the practices we want teams to adopt;\
2. whether the measurement reflects those practices accurately;\
3. which repository variations the measurement must support; and\
4. whether the Bronze, Silver and Gold rubric sets the right expectations.

The intent is to agree to the standard first. Implementation changes follow from that agreement.

To propose an additional V0 metric, copy the [metric proposal template](framework-metric-proposal-template.md) into the appropriate dimension below.

## Measurement principles

- **Align on a common way.** When a repository differs for no agreed reason, treat it as alignment work rather than adding another detector variant.\
- **Support real structural differences.** Measurements must account for monorepos, charms and snaps, K8s and machine charms, root products and components, and approved shared workflows such as `charm-ci` and `operator-workflows`.\
- **Keep metrics simple and deterministic.** A metric should be understandable in one sentence and produce the same result from the same evidence.\
- **Distinguish failure from missing evidence.** A measured failure, insufficient data and a non-applicable metric are different outcomes. Only a measured failure represents non-compliance.

Each metric reports one of those outcomes explicitly. Metric logic determines applicability;
the engine applies the common scoring rules. A dimension with no applicable graded requirements
is not applicable, not automatically Gold.

Any additional variation should be agreed as a supported practice before it is added to a measurement.

**References:** [Live V0 dashboard](https://canonical.github.io/pqf/#/v0) · [PQF repository](https://github.com/canonical/pqf)

---

## 1\. Testing

*Are we confident that the code on the published branch works as intended, on what is intended?*

### Proposed medal rubric

| Grade | Requires |
| :---- | :---- |
| Bronze | `uses_ops_testing` + `uses_gh_runners_unit_testing` |
| Silver | Bronze + `uses_jubilant` + `uses_tf_v1_provider` |
| Gold | Silver + `uses_charm_ci` + `supports_canonical_k8s` + `supports_juju_4` + `supports_juju_lts` |

### Latest CI passing

**ID:** `ci_passing` (formerly `latest_build_passing`)\
**Implementation:** `ci-passing/v1`\
**Applies to:** all repositories\
**What it measures:** whether the latest code merged to the published branches passed its tests. This is an informational metric only and is not taken into account in the medal criterias.

**Measurement**

1. Find the tracks published from the charmhub api ([https\://api.charmhub.io/v2/charms/info/synapse?fields=channel-map](https://api.charmhub.io/v2/charms/info/synapse?fields=channel-map)).\
2. Include the default branch and `track/<track>` for each published non-`latest` Charmhub track. A published track without that branch is insufficient data. Snaps currently check only the default branch.
3. Find the CI run that validated the code for the respective target branches:\
   - use check runs attached directly to the target branch’s latest commit; or\
   - for PR-only workflows, use merged-PR evidence only when its tested head is provably the target branch commit. Unattributable squash-merge evidence is insufficient data.
4. Return `true` only when all jobs are completed successfully.\
5. Return *insufficient data* when no relevant run or required job can be identified.

**Accepted variations**

- It should pass on all "published" branches. If we have track 1 and track 2 published from 2 branches, both should be green.

### Uses Jubilant

**ID:** `uses_jubilant`\
**Implementation:** `uses-jubilant/v2`\
**Applies to:** charms\
**What it measures:** whether charm integration tests use Jubilant\
**Measurement**

1. Locate integration tests in the repository or component subpath.\
2. Similar to repolint logic [here](https://github.com/canonical/repolint/blob/main/src/repolint/checks/jubilant.py#L19), return `true` when the test code imports or otherwise uses the `jubilant` package.\
3. Missing integration tests are a measured failure. Only non-charms are *not applicable*.

**Accepted variations**

- Integration tests may live at the repository root or inside a monorepo component.\
- Any valid Python import form for `jubilant` counts.

### Uses `charm-ci` for integration tests

**ID:** `uses_charm_ci`\
**Implementation:** `uses-charm-ci/v1`\
**Applies to:** charms\
**What it measures:** whether integration tests run through `charm-ci` workflow.

**Measurement**

1. Inspect parsed GitHub Actions integration jobs and return `true` when they call Canonical `charm-ci`. A comment or unused string is not evidence.
2. Return `false` otherwise.\
3. Return *not applicable* for none-charm repositories only.

**Accepted variations**

- The `charm-ci` workflow may be called from a repository-level workflow or a monorepo component workflow.

### Uses Ops Testing

**ID:** `uses_ops_testing`\
**Implementation:** `uses-ops-testing/v1`\
**Applies to:** charms\
**What it measures:** whether repo uses ops.testing instead of the old Harness.\
**Measurement**

1. Inspect component unit tests for Python imports of `ops.testing` and legacy Harness, following the intent of [repolint](https://github.com/canonical/repolint/blob/main/src/repolint/checks/ops_testing.py).
2. Return `true` only with positive Ops Testing usage and no legacy Harness usage.
3. Missing tests or imports are measured failure, not successful adoption.
4. Return *not applicable* for none-charm products.

**Accepted variations**

- Tests may live at the repository root or inside a monorepo component.

### Uses TF V1 Provider

**ID:** `uses_tf_v1_provider`\
**Implementation:** `uses-tf-v1-provider/v1`\
**Applies to:** charms\
**What it measures:** repository uses Terraform Juju provider v1\
**Measurement**

1. Following logic from repolint [here](https://github.com/canonical/repolint/blob/main/src/repolint/checks/tf_v1.py),\
2. Return `true` when all Terraform modules use Juju provider v1.\
3. Return `false` otherwise.\
4. Return *not applicable* when repo has no terraform modules.

**Accepted variations**

- Tests may live at the repository root or inside a monorepo component.

### Uses GitHub-hosted runners for unit tests

**ID:** `uses_gh_runners_unit_testing`\
**Implementation:** `uses-gh-runners-unit-testing/v1`\
**Applies to:** charms\
**What it measures:** repository uses GitHub-hosted runners for unit tests\
**Measurement**

1. Inspect identifiable unit-test jobs, including the sanctioned `operator-workflows/test.yaml` and `charm-ci` callers.
2. Require positive GitHub-hosted runner configuration. Self-hosted unit tests fail.
3. Missing unit-test jobs are measured failure; unresolved dynamic runner configuration is insufficient data.
4. Return *not applicable* for none-charm products.

**Accepted variations**

- Tests may live at the repository root or inside a monorepo component.

### Tested on Canonical K8s

**ID:** `supports_canonical_k8s`\
**Implementation:** `supports-canonical-k8s/v1`\
**Applies to:** K8s charms\
**What it measures:** whether the charm's integration-test `charm-ci` configuration targets Canonical Kubernetes rather than only MicroK8s. Successful runs are reported separately by `ci_passing`.

**Measurement**

1. Follow this [example logic](https://github.com/canonical/repolint/blob/main/src/repolint/checks/contains_k8s_charm.py) to check if the charm is k8s or not. Return *not applicable* for machine charms and snaps.\
2. Inspect the integration-test charm-ci configuration used by the charm, similar to the logic from [repolint here](https://github.com/canonical/repolint/blob/main/src/repolint/checks/ck8s.py).\
3. Return `true` when at least one integration-test job is configured to deploy to Canonical K8s through `charm-ci`. The configuration must be used by that job; an unused Concierge file does not count.
4. Return `false` when the required configuration is absent, including when only MicroK8s is configured.
5. Return *insufficient data* when evidence cannot be acquired or interpreted confidently. Do not inspect run success for this metric.

**Accepted variations**

- Monorepo configuration may be shared at the root or scoped to the component.

### Tested on Juju 4

**ID:** `supports_juju_4`\
**Implementation:** `supports-juju-4/v2`\
**Applies to:** charms\
**What it measures:** whether the charm's integration-test `charm-ci` configuration targets the required stable Juju 4 release. Successful runs are reported separately by `ci_passing`.

**Measurement**

1. Read the cycle contract's pinned Juju 4 track: `4/stable`. Patch-release currency is not a V0 requirement.
2. Inspect the integration-test charm-ci configuration used by the repository.\
3. Return `true` when at least one integration-test job targets `4/stable` through `charm-ci`. An unused Concierge file does not count.
4. Return `false` when the required configuration is absent.
5. Return *insufficient data* when evidence cannot be acquired or interpreted confidently. Do not inspect run success for this metric.

**Accepted variations**

- Monorepo configuration may be shared at the root or scoped to the component.

### Tested on Juju LTS

**ID:** `supports_juju_lts`\
**Implementation:** `supports-juju-lts/v1`\
**Applies to:** charms\
**What it measures:** whether the charm's integration-test `charm-ci` configuration targets the current Juju LTS, currently Juju 3. Successful runs are reported separately by `ci_passing`.

**Measurement**

1. Read the cycle contract's pinned LTS track: `3.6/stable`. Patch-release currency is not a V0 requirement.
2. Inspect the integration-test charm-ci configuration used by the repository.\
3. Return `true` when at least one integration-test job targets `3.6/stable` through `charm-ci`. An unused Concierge file does not count.
4. Return `false` when the required configuration is absent.
5. Return *insufficient data* when evidence cannot be acquired or interpreted confidently. Do not inspect run success for this metric.

**Accepted variations**

- Monorepo configuration may be shared at the root or scoped to the component.

---

## 2\. Documentation

*Can users and contributors find the information they need?*

### Proposed medal rubric

| Grade | Requires |
| :---- | :---- |
| Bronze | README present |
| Silver | Bronze \+ CONTRIBUTING present \+ SECURITY present |
| Gold | Silver + a valid Sphinx Stack version recorded by `uses_sphinx_stack` |

### README present

**ID:** `readme_present`\
**Implementation:** `readme-present/v2`\
**Applies to:** charms and snaps\
**What it measures:** whether the repository provides a clear entry point explaining the product and how to get started.

**Measurement**

1. Check for a non-empty `README.md` at the repository root.\
2. Compare against the [PFE template](https://github.com/canonical/platform-engineering-charm-template/tree/8299de3ec4a264c853d48c6bb09903677e38cbd7), ignoring whitespace and comments.
3. Return `true` when it exists and contains content beyond a heading or placeholder.

**Accepted variations**

- A monorepo uses one root README as the repository entry point. Component documentation may supplement it but does not replace it.

### CONTRIBUTING present

**ID:** `contributing_present`\
**Implementation:** `contributing-present/v2`\
**Applies to:** charms and snaps\
**What it measures:** whether contributors can find instructions for making and validating changes.

**Measurement**

1. Check for a non-empty `CONTRIBUTING.md` at the repository root.\
2. Check that the [CONTRIBUTING.md](http://CONTRIBUTING.md) contents does not match the [default template](https://github.com/canonical/platform-engineering-charm-template/blob/main/CONTRIBUTING.md) PFE uses.\
3. Return `true` when it differs from the pinned template and has body content beyond headings, comments or placeholders. This is a deterministic customization check, not a subjective quality review.

**Accepted variations**

- A monorepo uses one root CONTRIBUTING file. It may link to component-specific instructions.

### SECURITY present

**ID:** `has_security`\
**Implementation:** `security-file-present/v2`\
**Applies to:** charms and snaps\
**What it measures:** whether users can find the supported process for reporting security vulnerabilities.

**Measurement**

1. Check for a non-empty `SECURITY.md` at the repository root.\
2. Apply the same pinned-template comparison and body-content rule as README and CONTRIBUTING. Do not infer the quality of reporting guidance.

**Accepted variations**

- A monorepo uses one root SECURITY file for all components.

### Uses Canonical Sphinx Stack

**ID:** `uses_sphinx_stack`\
**Implementation:** `uses-sphinx-stack/v1`\
**Applies to:** charms and snaps that publish user-facing documentation\
**What it measures:** whether user-facing documentation is published through Canonical's [Sphinx Stack](https://github.com/canonical/sphinx-stack) solution.

**Measurement**

1. Snap components are N/A. Upstream-docs exemptions require a reviewed `documentation_exemption` reason in the product/component YAML, never an ad-hoc repository-name check.
2. Check that the sphinx stack version is accessible at `docs/_dev/version`\
3. Return the recorded version as the metric value when it is a valid Sphinx Stack version. Any valid version qualifies for Gold; V0 imposes no minimum version.
4. Return a measured non-adoption result when the required file is absent or does not contain a valid version.
5. Return *not applicable* for approved exemptions, and *insufficient data* when evidence cannot be acquired or interpreted confidently.

**Accepted variations**

- Docs configuration may be at the repository root or at an agreed monorepo component path.

**Open questions**

- Which products legitimately do not need sphinx stack?\
- Should we also be checking for “LICENSE present” and “CODEOWNERS present”? Similar pattern to README/CONTRIBUTING/SECURITY.

### Diátaxis coverage (AI)

**ID:** `diataxis_coverage_ai`\
**Implementation:** `diataxis-coverage-ai/v2`\
**Status:** informational only\
**Applies to:** products with user-facing documentation\
**What it measures:** indicative coverage of the four Diátaxis documentation modes: tutorials, how-to guides, reference and explanation.

**Measurement**

1. Review the authoritative documentation set, not only the README.\
2. Assign one point for meaningful coverage of each Diátaxis mode.\
3. Report a score from 0 to 4 with brief supporting evidence.\
4. Never use this metric to determine a medal.

**Accepted variations**

- Documentation may be stored in the product repository or in an authoritative linked documentation repository.\
- Section names do not need to use Diátaxis terminology when the content clearly serves the same purpose.

---

## 3\. Security (SSDLC)

*Are the basic dependency-management and repository protections in place?*

### Proposed medal rubric

| Grade | Requires |
| :---- | :---- |
| Bronze | Renovate enabled, Signed commits required,  Branch protection with required checks |
| Silver | Bronze |
| Gold | Silver |

All tiers deliberately have the same security baseline. A compliant product receives Gold;
there are no artificial partial-compliance tiers. Approving reviews remain a V1 discussion.

### Renovate enabled

**ID:** `renovate_enabled`\
**Implementation:** `renovate-enabled/v2`\
**Applies to:** charms and snaps\
**What it measures:** whether Renovate is configured and has visible bot-authored onboarding evidence. This is not a runtime-health check.

**Measurement**

Return `true` only when the repository has enabled Renovate configuration **and an open Dependency
Dashboard authored by the verified Renovate bot**. A human-created issue, closed dashboard, update
PR, or configuration alone does not qualify. Do not use issue update time as a heartbeat; a stale
dashboard can remain after service removal.

**Accepted variations**

- N/A

### Branch protection with required checks

**ID:** `branch_protection_required_checks`\
**Implementation:** `branch-protection-required-checks/v2`\
**Applies to:** charms and snaps\
**What it measures:** whether changes can merge to the default branch only after required automated checks pass.

**Measurement**

1. Resolve the repository's default branch.\
2. Read its branch-protection or ruleset configuration.\
3. Return `true` when required status checks are enabled and at least one check is required.

**Accepted variations**

- Protection may be configured through classic branch protection or a repository ruleset.

**Open questions**

- Should Silver also check for at least one approving review?

### Signed commits required

**ID:** `signed_commits_required`\
**Implementation:** `signed-commits-required/v2`\
**Applies to:** charms and snaps\
**What it measures:** whether every commit reaching the default branch must have a verified signature.

**Measurement**

1. Resolve the repository's default branch.\
2. Read its branch-protection or ruleset configuration.\
3. Return `true` when signed commits are required.

**Accepted variations**

- Enforcement may come from classic branch protection or a repository ruleset.

---
