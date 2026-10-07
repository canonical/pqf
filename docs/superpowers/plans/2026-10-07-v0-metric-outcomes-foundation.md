# V0 Metric Outcomes Foundation Implementation Plan

> **For agentic workers:** Use executing-plans to implement task-by-task with review checkpoints. The user authorized completing the full V0 alignment and opening a PR in the current checkout.

**Goal:** give every metric one clear result model: measured value, not applicable, or insufficient data.

**Architecture:** scorers, computed envelopes, the engine, public artifacts and UI all use the
same structured metric result. Scorers determine eligibility from product context and evidence;
one engine evaluator owns scoring. Old scalar payloads are rejected, not adapted.

**Tech Stack:** Python, JSON Schema, pytest, TypeScript strict mode, Canonical React components,
Vitest/React Testing Library and Playwright.

## Global constraints

- The tool is pre-adoption with no dependent consumers. No backward-compatible payload reader,
  per-metric format opt-in, parallel evaluator or scalar-plus-metadata representation is needed.
- Retain framework snapshots, implementation revisions, contract digests and source fingerprints.
  These provide provenance, not a requirement to keep obsolete runtime behavior.
- Changed measurements get new implementation revisions; do not silently mutate old revisions.
- Never change archived scoring semantics or hand-edit generated measurements/artifacts.
- The foundation and agreed V0 metric/rubric changes ship as one coordinated release.
- Use one uniform result model for both current V0 and upcoming V1.
- Required acquisition failures still fail jobs after supported retries. Result states cannot
  swallow authentication, rate-limit or server failures.
- Scorers decide metric applicability; the engine must not contain repository/tool-specific rules.
- Missing required tests or configuration is not an exemption.
- A measured `false`, `0` or empty string is a real value, not missing data.
- Entirely non-applicable graded requirements yield dimension N/A, never Gold.
- Informational metrics cannot gate medals or make a dimension insufficient.
- Preserve the dimension-level product-type filter. No new YAML eligibility-expression language.
- Use existing `make` commands; restore dependencies only after missing-dependency failures.
- Keep work in the current checkout; the requested PR is the delivery boundary.

## Delivery boundaries

This is the first slice of the [V0 migration roadmap](../../proposals/framework-v0-migration.md),
addressing [issue #43](https://github.com/canonical/pqf/issues/43).
The same delivery implements Testing, Documentation, Security, informational CI, calibration and
rollout. Platform metrics grade configuration linked to `charm-ci`; Sphinx Stack adoption accepts
any valid recorded version.

The foundation necessarily changes the artifact format. Update all producers, consumers and
fixtures in one coordinated release and regenerate active/upcoming artifacts before deployment.
Do not publish new readers against old payloads. Old payloads are intentionally unsupported.
If archived artifacts exist, inventory them before implementation and arrange a reviewed
format-only migration preserving their values and scoring identity; do not rescore them.

## Single result interface

Keep the leaf/dimension/metric nesting, with each metric represented as:

```json
{
  "uses_jubilant": {"state": "measured", "value": true},
  "uses_tf_v1_provider": {
    "state": "not_applicable",
    "value": null,
    "reason": "No Terraform modules in this component."
  }
}
```

All outputs use this shape. Do not add `measurement_format` to YAML. Keep existing YAML fields
for metric identity, implementation revision, value type, description and medal criteria.

Create `engine/metric_outcomes.py` with:

```python
from dataclasses import dataclass
from enum import StrEnum


class MetricState(StrEnum):
    MEASURED = "measured"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_APPLICABLE = "not_applicable"


MetricScalar = str | int | float | bool


@dataclass(frozen=True)
class MetricOutcome:
    state: MetricState
    value: MetricScalar | None
    reason: str | None = None
```

Public interfaces:

- `measured(value: MetricScalar) -> MetricOutcome`
- `not_applicable(reason: str) -> MetricOutcome`
- `insufficient_data(reason: str) -> MetricOutcome`
- `parse_metric_outcome(raw: object, output_config: dict[str, Any], *, metric_key: str) -> MetricOutcome`
- `serialize_metric_outcome(outcome: MetricOutcome) -> dict[str, Any]`

Measured values must match the declared boolean/number/string type; numeric booleans and
non-finite numbers are invalid. Non-measured results require null value and non-empty reason.
Unknown states/fields, scalar inputs and inconsistent payloads raise contextual errors.
Only serialize at JSON boundaries. Internal models contain `MetricOutcome` objects; public
`metrics` contains the same state/value/reason objects. No second outcome map.

## Task 1: Result type, validation and authoring helpers

**Create:** `engine/metric_outcomes.py`, `engine/__tests__/test_metric_outcomes.py`\
**Modify:** `engine/models.py`, `engine/validate.py`\
**Tests:** `engine/__tests__/test_validate.py`, `engine/__tests__/test_models.py`

**Consumes:** existing output type declarations.\
**Produces:** the interfaces above and typed metric mappings in result models.

- [x] Add failing tests for three states, valid types, preserved false/zero/empty string,
  wrong types, scalar rejection, missing reasons, unknown fields and JSON round trips:

```python
def test_false_is_a_measured_value():
    outcome = parse_metric_outcome(
        {"state": "measured", "value": False},
        {"type": "boolean"},
        metric_key="uses_jubilant",
    )
    assert outcome == measured(False)


def test_not_applicable_round_trip():
    outcome = not_applicable("Machine charm.")
    assert parse_metric_outcome(
        serialize_metric_outcome(outcome),
        {"type": "boolean"},
        metric_key="supports_canonical_k8s",
    ) == outcome
```

- [x] Run `PYTEST_ADDOPTS="engine/__tests__/test_metric_outcomes.py engine/__tests__/test_validate.py engine/__tests__/test_models.py" make test`; observe failures.
- [x] Implement strict helpers and parsing. Validate at construction as well as JSON ingestion.
  Reject informational outputs used in rubric criteria or required-for-scoring lists.
- [x] Re-run selected tests and `make validate`. Existing framework YAML needs no format field.

## Task 2: Convert every scorer and transport boundary

**Modify:** `scorers/registry.py`, `scorers/run.py`, `engine/merge_computed.py`\
**Modify:** `scorers/test_verification/logic.py`, `scorers/documentation/logic.py`,
`scorers/substrate_compat/logic.py`, `scorers/security_ssdlc/logic.py`,
`scorers/engagement/logic.py`\
**Tests:** existing scorer tests, `scorers/__tests__/test_registry.py`,
`engine/__tests__/test_merge_computed.py`

**Consumes:** result helpers and contract output metadata.\
**Produces:** `dict[str, MetricOutcome]` from runners; structured JSON in scorer/computed output.

- [x] Add registry and merge tests that require structured results and reject raw scalars.
  Exercise measured false, N/A and insufficient data through the full JSON round trip.
- [x] Run `PYTEST_ADDOPTS="scorers/__tests__/test_registry.py engine/__tests__/test_merge_computed.py" make test`; confirm failures.
- [x] Convert all registered runners to return outcomes directly—not a registry adapter wrapping
  scalars. Retain present measurement rules until their separately reviewed calibration revisions.
  No API failures or unavailable AI assessment may become measured zero/false.
- [x] Use explicit insufficient-data reasons for unmeasurable results and N/A only for known
  eligibility exclusions. Publish new revisions where converting old missing/error behavior changes
  measurement meaning; update affected contract references and tests together.
- [x] Serialize in `scorers/run.py`; parse and validate at merge/load boundaries. Errors identify
  file, leaf, dimension and metric. Missing selected scorer outputs remain errors.
- [x] Register outcome helper source fingerprints where runners depend on them; retain complete
  cache identity and immutable measurement bindings.
- [x] Update all scorer fixtures and assertions; run
  `PYTEST_ADDOPTS="scorers engine/__tests__/test_merge_computed.py" make test`.

## Task 3: One evaluator for all dimensions

**Modify:** `engine/rubric.py`, `engine/aggregation.py`, `engine/medal_engine.py`\
**Tests:** `engine/__tests__/test_rubric.py`, `engine/__tests__/test_medal_engine.py`,
`engine/__tests__/test_aggregation.py`

**Consumes:** typed outcomes, existing criterion parser, contract requirements.\
**Produces:** consistent metric-aware dimension applicability and medal results.

- [x] Add failing tests for machine charm N/A, all-graded N/A, required insufficient,
  measured failure, optional insufficient and informational evidence.

```python
def test_no_graded_requirements_apply():
    metrics = {"uses_jubilant": not_applicable("Not a charm.")}
    config = {
        "applies_to": {"product_types": ["charm", "snap"]},
        "outputs": {"uses_jubilant": {"type": "boolean"}},
        "required_metrics_for_scoring": ["uses_jubilant"],
        "medals": {"bronze": ["uses_jubilant == true"]},
    }
    assert compute_leaf_applicability("snap", metrics, config) == (
        ApplicabilityOutcome.NOT_APPLICABLE
    )
```

- [x] Run `PYTEST_ADDOPTS="engine/__tests__/test_rubric.py engine/__tests__/test_medal_engine.py engine/__tests__/test_aggregation.py" make test`; confirm failures.
- [x] Implement a single policy:
  1. Dimension product-type exclusion wins.
  2. All rubric-referenced metrics explicitly N/A means dimension N/A.
  3. Applicable required metrics with insufficient/missing evidence make the dimension insufficient.
  4. Evaluate tiers top-down; skip explicit N/A predicates, compare measured values, and never
     pass an insufficient predicate.
  5. Failure to meet explicit Bronze means below minimum. Retain supported implicit-Bronze
     contract syntax, but it cannot override the all-N/A or required-insufficient guards.
- [x] Remove duplicate obsolete scalar evaluation paths. If `compute_product` is still needed,
  make it call the same evaluator; otherwise remove it and its obsolete callers/tests.
- [x] Implement the separately agreed root policy: applicable required unknown evidence blocks
  the root; excluded and N/A components do not count. Preserve the worst measured in-scope result.
- [x] Re-run tests. Verify a machine charm can reach Gold when its applicable requirements pass,
  but a snap with no graded Testing requirements gets N/A.

## Task 4: Structured assembly and UI throughout

**Modify:** `engine/assemble.py`, `ui/src/types.ts`, `ui/src/hooks/usePortfolio.ts`,
`ui/src/components/MetricsList.tsx`, `ui/src/components/RootMetricsList.tsx`,
`ui/src/views/ProductDetail.tsx`, `ui/src/views/MetricDistribution.tsx`,
`ui/src/lib/groupedPortfolioView.ts`\
**Tests:** `engine/__tests__/test_assemble.py`, `engine/__tests__/test_integration.py`,
`ui/src/components/MetricsList.test.tsx`, `ui/src/components/RootMetricsList.test.tsx`,
`ui/src/lib/groupedPortfolioView.test.ts`, `ui/src/views/__tests__/MetricDistribution.test.tsx`

**Consumes:** structured metric results.\
**Produces:** identical state/value/reason objects in public data and consistent UI handling.

- [x] Add serialization assertions:

```python
assert published_dimension["metrics"]["supports_canonical_k8s"] == {
    "state": "not_applicable", "value": None, "reason": "Machine charm."
}
```

- [x] Replace scalar `MetricValue` assumptions with a TypeScript discriminated union:

```typescript
export type MetricOutcome =
  | { state: 'measured'; value: string | number | boolean; reason?: string }
  | { state: 'not_applicable' | 'insufficient_data'; value: null; reason: string }
```

- [x] Parse/load structured artifact data with explicit format errors. No fallback that reads
  old scalar payloads. Serialize dataclasses/enums only at the Python JSON boundary.
- [x] Centralize measured-value access and outcome labels in a focused UI helper if shared
  logic is needed; never reconstruct eligibility in React.
- [x] Display neutral N/A and insufficient-data labels with accessible reasons. Compare
  thresholds only for measured values; exclude N/A from numeric gaps and graded denominators.
- [x] Root views preserve component outcomes, including unknown/N/A components. A “worst measured”
  summary must not imply all components were measured; show incomplete evidence explicitly.
  Do not invent aggregate string-version ordering.
- [x] Update every fixture and consumer of metric values, not just product detail.
- [x] Run `make test-ui`, `make build` and
  `PYTEST_ADDOPTS="engine/__tests__/test_assemble.py engine/__tests__/test_integration.py" make test`.
- [x] Load required UI/browser skills and verify detail, root and distribution views using
  generated structured fixtures. Close temporary helpers afterward.

## Task 5: Documentation, regeneration and coordinated release

**Modify:** `docs/architecture.md`, `docs/adding-a-metric.md`, `docs/local-scoring.md`,
`docs/proposals/framework-v0-migration.md`\
**Inspect:** `.github/workflows/compute-metrics.yml`, `.github/workflows/ci.yml`,
deployment workflow selected by current repository configuration\
**Tests:** `engine/__tests__/test_integration.py`, relevant workflow tests

**Consumes:** completed pipeline.\
**Produces:** one documented authoring model and a deployment that contains no stale scalar artifacts.

- [x] Document the three helpers, exact JSON shape, applicability responsibility, required
  evidence behavior and an example metric. YAML gains no payload setting or detection DSL.
- [x] Add end-to-end fixtures for K8s/machine charms, a snap, and a composed root.
  Confirm false/N/A/insufficient states survive scorer output, merge, assembly and UI.
- [x] Inventory checked-in/generated artifacts and CI carry-forward/deploy paths. Ensure the
  release forces regeneration for active/upcoming versions rather than carrying forward old
  scalar envelopes. A format-only change must not rely solely on unchanged contract digests.
- [x] Retain frozen archive measurements through a reviewed format-only migration if present.
  Keep `/legacy/` as its existing separate frozen site; do not make the new app support it.
- [x] Regenerate representative active/upcoming artifacts locally with explicit versions and
  prepare normal CI publication after merge. Do not hand-edit or commit GHA-written data.
- [x] Run `make validate`, `make lint`, `make format-check`, `make test-all`, `make build`,
  and `git diff --check`.
- [x] Update the migration roadmap for the delivered V0 metrics/rubric and representative live
  calibration. Record deployment prerequisites without claiming a full fleet rollout.
- [x] Prepare the requested PR's evidence and deployment prerequisites. Do not close issues
  before the review/merge process.

## Resolved policy decision: root uncertainty

The user chose to propagate insufficient required component evidence to the root dimension.
Explicitly excluded and N/A components do not count. No remaining graded components means N/A,
not an empty Gold medal. This is one explicit policy, independent of serialization format.

## Completion bar

Every producer and consumer uses one metric result representation; unsupported scalar artifacts
fail explicitly; no compatibility opt-ins/adapters remain. N/A never looks like failure or grants
an empty medal, unknown evidence never becomes success, and regenerated artifacts can be deployed
together with their readers. The existing framework provenance architecture remains intact.

## Verification and activation status

Implemented the foundation and complete agreed V0 contract together. Final verification:
796 Python tests, 210 UI tests, 15 E2E tests, schema validation, lint/format checks and production
build. Browser acceptance also used normally generated live Traefik and Mailserver Operators
data, including machine/snap N/A reasons and V1 switching. Review-found measurement defects were
fixed with regressions; generated artifacts are excluded from the PR.

Production activation remains a separate operational step: configure the cross-repository
read-only `PQF_GITHUB_TOKEN`, merge the reviewed PR, and let coordinated live-version regeneration
and deployment succeed. The old published site remains intact if scoring fails.
