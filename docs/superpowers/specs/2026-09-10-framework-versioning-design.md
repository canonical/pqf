# PQF Framework Versioning Design

## Context

PQF currently evaluates every tracked product against one mutable framework contract. Changes to
dimension criteria, metric logic, product membership, or product composition take effect as soon as
they merge. A newly added component can immediately lower its parent product's result, and a newly
raised quality bar can immediately lower many products at once.

The existing remediation-window model tries to soften these transitions with per-product,
per-dimension deadlines. In practice, those clocks are difficult to explain and operate. They also
do not distinguish clearly between:

- a product regressing against an unchanged standard,
- a future standard intentionally raising the bar,
- a new product or component entering the portfolio,
- a measurement implementation changing,
- a previously informational signal becoming score-affecting.

PQF needs an explicit framework lifecycle that separates today's official compliance view from
the next cycle's readiness view.

## Goals

- Define complete, named framework versions with explicit lifecycle states.
- Keep exactly one official active framework and at most one upcoming framework.
- Evaluate the active and upcoming frameworks independently.
- Make upcoming requirements and catalog changes visible before activation.
- Activate a new framework atomically at a cycle boundary.
- Preserve archived framework results as immutable historical snapshots.
- Support product, component, composition, and target-grade changes at version boundaries.
- Allow metric implementations to evolve without version conditionals inside scorer logic.
- Replace remediation deadlines with straightforward compliance progress.
- Preserve the current unversioned PQF site as a static regression and historical reference.
- Establish clean extension points for project-repository checks and automated roadmap planning.

## Non-Goals

- A dedicated cross-version diff view in the first iteration.
- More than one upcoming framework version.
- Per-product framework adoption or readiness attestation.
- Per-product or per-dimension remediation deadlines.
- Backward compatibility between the current unversioned payload and the new versioned payload.
- Project-repository checks against a selected framework version.
- Automated Jira roadmap or work-item creation.

Project-repository checks and Jira roadmap generation will be filed as separate follow-up issues.

## Decision Summary

1. Framework contracts are stored as full snapshots in version-specific directories.
2. Each version declares its own status; repository-wide validation enforces lifecycle invariants.
3. Catalog definitions remain independent source data with version membership boundaries.
4. Product target grades are version-scoped and change only when explicitly declared.
5. Stable metric IDs select explicit implementation revisions.
6. Active and upcoming results are computed independently; reuse is an optional optimization.
7. Active results refresh nightly, upcoming results refresh weekly, and both support manual runs.
8. Archived result artifacts are frozen and never recomputed.
9. The UI selects one complete framework view at a time.
10. Remediation windows are removed in favor of live version compliance progress.
11. The last pre-versioning site is deployed permanently at `/legacy/` and is not linked from the
    new UI.

## Framework Version Model

### Directory layout

Each framework version has a complete resolved contract:

```text
framework/
  versions/
    v0/
      framework.yaml
      dimensions.yaml
    v1/
      framework.yaml
      dimensions.yaml
```

`framework.yaml` contains lifecycle and display metadata:

```yaml
id: v0
sequence: 0
label: "PQF V0"
status: active
description: "The dependable minimum PQF quality baseline."
```

`dimensions.yaml` is a complete snapshot of the dimensions, outputs, implementation revisions,
applicability rules, aggregation rules, required metrics, and medal criteria for that version. It
does not inherit from another framework at runtime.

New versions are created through a command that copies the active resolved contract into a new
directory and updates the new version's identity and status. Maintainers then edit the copy. This
keeps review diffs focused while ensuring every contract can be understood without traversing an
inheritance chain.

### Lifecycle states

Supported states are:

- `upcoming`: the single next framework under preparation,
- `active`: the single official framework used for current compliance,
- `archived`: a former active framework whose published results are frozen.

Repository validation enforces:

- exactly one active version,
- at most one upcoming version,
- any number of archived versions,
- unique IDs and sequence numbers,
- lifecycle order consistent with sequence order,
- no transition from archived back to active or upcoming.

Activation is a single reviewed source change that marks the old active version `archived` and the
upcoming version `active`. A new upcoming version may be created later.

There is no separate version registry. Tools discover `framework/versions/*/framework.yaml` and
validate the collection as one state machine.

### Contract governance

An active contract is intended to be immutable as part of the framework owners' operating
contract, but the engine does not make legitimate corrections technically impossible. CI
classifies changes to active versions as:

- metadata-only,
- additive informational measurement,
- scoring-semantic,
- catalog membership or target changes.

Scoring-semantic changes include metric implementation revisions, applicability, required metrics,
criteria, aggregation, and target changes. Pull requests prominently report these changes and the
affected versions and products so framework owners can make an explicit decision.

Archived result artifacts remain authoritative and are never regenerated. Changes to archived
source contracts are strongly flagged because they cannot change historical results. Every
portfolio artifact embeds the resolved contract metadata and digest used to produce it.

### Archive policy

The archive policy has four rules.

**Frozen measurements.** Archived repository scorers must never run. No cadence, manual dispatch,
bootstrap, or recovery path may schedule an archived version for scoring, so the measured values
in an archived artifact can never change.

**Migratable payload format.** Archived portfolio payloads are not write-protected. A reviewed
format migration may transform an archived artifact so a newer UI schema can read it, provided it
preserves the recorded metric values, results, product membership, generation time, and the
original scoring-contract identity (framework ID and contract digest). PR review is the governance
gate for such a migration; the engine deliberately does not add a hard lock preventing changes to
archived files.

**No archived rescoring.** Because the payload's contract digest must survive a migration, digest
validation is applied to archived artifacts exactly as to live ones. A digest mismatch on an
archived artifact means the archived scoring rules were changed after the fact. That is an error,
never a trigger to recompute.

**Scoring-only digest.** `contract_digest` hashes only what determines how a version scores: the
semantic dimensions contract plus the identity fields that scope it (`id`, and `sequence`, which
resolves catalog membership boundaries). Lifecycle and display metadata is excluded: framework
`status`, `label`, and `description`, dimension `label` and `description`, and output `label`,
`description`, `range`, and `ai_assisted`. Activation from `active` to `archived` and UI-copy edits
therefore leave the digest of already-published artifacts unchanged. Live versions whose published
portfolio records a stale digest are recomputed automatically; archived versions never are.

## Version-Aware Product Catalog

Product catalog definitions remain in `products/*.yaml`; they are not duplicated into each
framework directory. Version boundaries control whether catalog entities and relationships are in
scope.

### Membership boundaries

The following may declare `introduced_in` and optional `retired_in`:

- top-level products,
- inline components,
- standalone components,
- composition edges connecting an existing component to a root product.

Inclusion is start-inclusive and retirement-exclusive:

```text
introduced_in <= selected version < retired_in
```

For example, a Hive Metastore component introduced in V1 is absent from V0 computation and
artifacts, but present in the upcoming V1 readiness view:

```yaml
composed_of:
  - id: hive-metastore-k8s
    product_type: charm
    introduced_in: v1
    source:
      repo: canonical/hive-metastore-k8s-operator
```

A version boundary on a composition edge is distinct from a standalone component's own portfolio
membership. This allows an existing tracked component to join or leave a root product at a later
framework version.

Validation rejects:

- boundaries referencing unknown versions,
- retirement at or before introduction,
- a composition edge active when either endpoint is inactive,
- references to components that do not exist in the selected version.

### Version-scoped targets

Products keep their own target grades. Targets are sparse versioned declarations:

```yaml
targets:
  v0: bronze
  v1: silver
```

The target for a selected version is the declaration with the greatest sequence not exceeding that
version. A product must declare a target at its introduction boundary. The target remains in force
until changed or the product is retired.

Inline components continue to inherit their parent root's target unless they explicitly own a
standalone target under the existing product graph rules.

## Metric Identity and Implementation Revisions

Metric IDs describe stable user-facing concepts. Implementation IDs identify concrete measurement
logic revisions.

```yaml
outputs:
  integration_test_evidence_present:
    implementation: integration-test-evidence/v2
    type: boolean
    label: "Integration test evidence"
    informational: false
```

A scorer registry maps implementation IDs to pure metric functions. The runner:

1. resolves the selected framework contract,
2. filters the product graph to entities active in that framework,
3. resolves the metric implementations declared by that contract,
4. executes only those implementations,
5. evaluates the selected framework's criteria.

Metric functions receive explicit evaluation inputs. They do not receive a framework version and
do not branch on version IDs. A changed detector can therefore become
`integration-test-evidence/v2` while retaining the stable
`integration_test_evidence_present` metric identity.

Implementation revision IDs are immutable. A logic correction creates a new revision and updates
the active or upcoming contract to select it; framework-owner review decides whether that change is
appropriate mid-cycle. This keeps the semantic change visible in the contract instead of silently
changing every version that references an existing implementation ID.

Unknown implementation IDs are validation errors. Criteria may reference only outputs declared in
the same dimension snapshot.

Archived framework results do not require their scorer implementations to remain executable
forever because archived artifacts are never recomputed. Implementations must remain available
while referenced by the active or upcoming contract.

## Initial V0 and V1 Contracts

V0 and V1 preserve the current target medal declared by each product. The migration converts each
existing `target_medal` into identical `v0` and `v1` entries. Teams may change those targets through
normal framework-owner review later.

### V0 bedrock

V0 provides a useful three-medal portfolio distribution with a deliberately small set of
deterministic requirements.

| Dimension | Bronze | Silver | Gold | Informational |
|---|---|---|---|---|
| Test verification | Latest build passing | No separate tier | Latest build passing and uses Jubilant | None |
| Documentation | README present | README and CONTRIBUTING present | README, CONTRIBUTING, and SECURITY present | Diátaxis coverage (AI), RTD hosting |
| Security | Renovate enabled | Renovate and branch protection enabled | Renovate, branch protection, and signed commits enabled | None |
| Engagement | Ownership signal present | Ownership and response coverage at least 80% | Ownership and response coverage at least 90% | None |

The absent test-verification silver criterion is intentional. A silver-target product satisfies
that dimension only by reaching its gold tier.

V0 does not include substrate compatibility as a scored dimension.

### V1 first operational bar

V1 copies V0 and promotes a conservative set of existing, deterministic signals:

| Dimension | Bronze | Silver | Gold | Informational |
|---|---|---|---|---|
| Test verification | Latest build passing | Latest build passing and integration-test evidence present | Silver criteria and uses Jubilant | Coverage, stability |
| Documentation | README present | README and CONTRIBUTING present | Silver criteria, SECURITY present, and release-notes process implemented | Documentation workflow status, Diátaxis coverage (AI), RTD hosting, CHANGELOG presence |
| Substrate compatibility | Juju 3 support | Juju 3 support and substrate test evidence present | Juju 4 support and substrate test evidence present | Canonical Kubernetes usage |
| Security | Renovate enabled | Renovate and branch protection enabled | Silver criteria, signed commits, and SAST workflow present | CVE-process evidence |
| Engagement | Ownership signal present | Ownership, response coverage at least 80%, average triage at most 3 days, and average PR review at most 5 days | Ownership, response coverage at least 90%, average triage at most 2 days, and average PR review at most 3 days | Jira sync, repository views |

Signals remain visible when informational. Promoting any of them into scoring requires a later
framework version or an explicitly reviewed active-contract correction.

## Computation and Artifact Lifecycle

### Independent computation

Active and upcoming versions are independent computation targets. A framework may:

- add or remove dimensions,
- add or remove metrics,
- select different metric implementation revisions,
- change criteria and applicability,
- include a different product graph,
- use different product targets.

The engine therefore must not assume that raw metric results can be reused across versions. Exact
implementation results may be cached later using an implementation ID and input fingerprint, but
cache reuse is an internal optimization and never part of correctness. Recorded implementation
fingerprints cover each runner's logic plus scoring-relevant shared helpers and prompt assets.

### Cadence

- **Active:** recompute nightly and after relevant PQF source changes.
- **Upcoming:** recompute weekly, after relevant framework/catalog/scorer changes, and through
  manual dispatch.
- **Archived:** never run scorers or assembly.
- **Pull requests:** compute previews only for affected active or upcoming contracts and catalog
  scopes.

Weekly upcoming computation ensures product-repository improvements become visible during planning
without doubling all nightly work. Maintainers can request an immediate refresh when needed.

### Artifact layout

```text
computed/
  versions/
    v0/
      <product>.json
    v1/
      <product>.json
public/
  framework-versions.json
  versions/
    v0/
      portfolio.json
    v1/
      portfolio.json
```

`framework-versions.json` is the authoritative source for lifecycle and display metadata. It is
generated from the discovered framework metadata and available artifacts. It contains the version
ID, sequence, label, status, description, artifact URL, generation timestamp, and contract digest.

Each `portfolio.json` embeds:

- framework identity, status, contract digest, and selected implementation fingerprints,
- generation timestamp and source revision,
- resolved dimension and metric metadata,
- the version-filtered product graph,
- resolved product target grades,
- product, dimension, component, and metric results,
- portfolio compliance summary counts.

Embedding the resolved metadata makes every artifact self-describing and prevents current source
configuration from changing the interpretation of a historical view. Archived portfolio metadata
may still reflect the generation-time lifecycle state of that snapshot, but the UI must never use
those embedded archived fields to decide how to label versions.

### Activation and freezing

When an activation change reaches the default branch, CI:

1. validates the old active-to-archived and upcoming-to-active transition,
2. leaves the former active portfolio and computed artifacts untouched,
3. recomputes the newly active framework immediately,
4. verifies the new live artifact's contract digest,
5. regenerates `framework-versions.json`,
6. deploys all version artifacts and the UI.

Failure to compute the newly active version prevents publication of a success-shaped partial
result. It does not alter the frozen archived artifact.

## Compliance Semantics

Framework versions replace remediation windows. The versioned model does not assign
per-product/per-dimension deadlines or derive remediating and overdue states.

For the selected version, PQF reports:

- each product's measured result,
- its resolved target grade,
- whether it meets that target,
- the dimensions and components preventing compliance,
- portfolio counts and percentages meeting the selected contract.

The upcoming view is a planning and readiness view. The active view is the official live compliance
view. Activation may intentionally lower results because the organization has deliberately adopted
a higher bar; the selected framework and its status make that change explicit.

## UI and User Experience

The UI first loads `public/framework-versions.json`, selects the single active version by default,
and then loads that version's complete portfolio. `framework-versions.json` is authoritative for
lifecycle/display metadata (`status`, `label`, `description`); a portfolio's embedded
`framework` block is historical provenance only and must not drive selector labels or version
badges.

A persistent selector at the top right groups versions as:

- Upcoming,
- Active,
- Archived.

The selection scopes every data view:

- portfolio overview,
- product details,
- dimensions,
- metric distributions,
- composition evidence,
- compliance summaries.

The upcoming view is clearly labeled as planning data and shows its last refresh time. Archived
views are labeled as frozen snapshots. A product introduced in V1 does not appear anywhere in V0,
including search and aggregate counts.

The first versioned UI does not provide a dedicated cross-version diff. Users inspect complete
version views independently. The artifact model leaves room for a later diff feature.

## Operator and CLI Experience

Version-aware commands accept an explicit framework selection:

```text
make score PRODUCT=<id> FRAMEWORK_VERSION=v1
```

The framework version is resolved before product graph construction and scorer dispatch. Commands
reject archived versions for recomputation but may validate or inspect their source contracts.

A framework creation command copies the active contract into the next version directory. It does
not create inherited or partial configuration.

Manual workflow dispatch accepts the active or upcoming version. Archived versions cannot be
selected for scoring.

## Legacy Site Snapshot

Before the versioned engine and UI replace the current deployment, CI builds the final
pre-versioning commit and deploys that complete static site to:

```text
/legacy/
```

This follows the existing GitHub Pages pattern used for PR preview destination directories. The
legacy build includes its own unversioned `portfolio.json` and relative assets, and is preserved by
all future deployments.

The legacy site:

- is immutable,
- is never recomputed,
- is not part of `framework-versions.json`,
- is not shown in the new UI's version selector,
- is not linked from the new UI,
- preserves metrics, dimensions, products, and behavior intentionally omitted from V0,
- provides a stable visual and behavioral regression reference during the major iteration.

This snapshot removes the need to carry the old payload or UI semantics into the versioned design.

## Error Handling and Validation

Repository validation fails on:

- zero or multiple active versions,
- multiple upcoming versions,
- duplicate version IDs or sequence values,
- invalid lifecycle ordering or transition,
- unknown version boundaries,
- invalid introduction/retirement ordering,
- missing target at product introduction,
- invalid target resolution,
- composition active outside either endpoint's membership,
- unknown metric implementation revisions,
- duplicate metric IDs,
- criteria referencing undeclared metrics,
- served active/upcoming artifacts whose contract digest does not match their contract.

Measurement failures remain explicit `insufficient_data` outcomes under the existing result model.
The engine must not silently omit failed metrics, publish partial success, or substitute results
from another version.

## Migration Plan

1. Produce and deploy the final pre-versioning site at `/legacy/`.
2. Define V0 as a deliberately small, dependable bedrock contract rather than a compatibility copy
   of every current metric and criterion.
3. Introduce framework discovery, lifecycle validation, implementation revision dispatch, and
   version-addressed artifacts.
4. Add catalog membership boundaries and version-scoped targets; onboard the current catalog into
   V0.
5. Remove remediation-window state and replace it with compliance progress.
6. Make all UI views version-scoped and add the framework selector.
7. Create V1 by copying V0, then add the first planned higher bar and upcoming catalog changes.
8. File separate GitHub issues for project-repository checks and Jira roadmap generation.

No backward-compatibility layer is added to the new engine or UI. The `/legacy/` deployment is the
reference for the previous major iteration.

## Testing Strategy

### Framework and catalog validation

- exactly one active and at most one upcoming framework,
- legal and illegal lifecycle transitions,
- full-snapshot framework creation,
- product/component introduction and retirement boundaries,
- composition-edge boundaries,
- sparse target resolution,
- unknown versions and invalid ranges.

### Metric execution

- stable metric IDs dispatch to the selected implementation revision,
- active and upcoming versions select different revisions independently,
- version conditionals are not required inside metric logic,
- unknown implementations fail validation,
- criteria cannot reference undeclared outputs,
- one version's failed computation cannot contaminate another.

### Results and artifacts

- V0 excludes a component introduced in V1,
- V1 includes the component and rolls its result into its parent,
- active results refresh without rewriting archived artifacts,
- activation freezes the old artifact and immediately computes the new active artifact,
- contract digests match served live artifacts,
- archived artifacts remain self-describing after source contracts evolve.

### UI

- active is selected by default,
- upcoming and archived groups render correctly,
- switching versions replaces all portfolio-scoped data,
- future products are absent from old versions,
- upcoming freshness and archived snapshot labels render,
- routes and direct links preserve the selected version,
- the current unversioned build remains available at `/legacy/`,
- visual and behavioral checks compare key new views with the legacy reference.

### Workflow

- active nightly scheduling,
- upcoming weekly scheduling,
- manual active/upcoming selection,
- rejection of archived recomputation,
- activation publication ordering,
- preservation of `/legacy/` and archived version directories.

## Future Extension Points

The initial implementation produces stable inputs for two later capabilities:

1. Project repositories can pin a framework version and run its selected checks before onboarding
   or activation.
2. Upcoming-version non-compliance gaps can generate proposed Jira roadmap work.

These capabilities are not part of this implementation. They will be tracked as separate
repository issues after the versioning foundation is specified.

## Success Criteria

- Users can select upcoming, active, and archived framework views from the UI.
- V0 and V1 can define different dimensions, metrics, implementation revisions, criteria, catalog
  membership, and targets.
- A V1-only component cannot affect V0 results.
- V0 freezes without recomputation when V1 activates.
- The active framework changes globally and atomically.
- No remediation deadlines remain in versioned result semantics.
- Framework owners receive clear review evidence for post-activation semantic changes.
- The pre-versioning site remains available and unchanged at `/legacy/`.
- The new engine and UI contain no backward-compatibility layer for the old unversioned payload.
