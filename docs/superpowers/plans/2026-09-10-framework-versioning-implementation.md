# PQF Framework Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independently computed upcoming, active, and frozen archived PQF framework versions, ship the approved V0/V1 contracts, and preserve the pre-versioning site at `/legacy/`.

**Architecture:** Full framework snapshots live under `framework/versions/<id>/`; product YAMLs carry version membership and sparse target histories. A version-aware scorer runner resolves immutable metric implementation IDs, writes version-addressed computed artifacts, and assembles self-describing portfolios. The React application routes every view through a selected framework version and loads that version's portfolio.

**Tech Stack:** Python 3.11, dataclasses, PyYAML, jsonschema, pytest, GitHub Actions, React 19, TypeScript 5.8, TanStack Query, React Router 7, Canonical React Components, Vitest, React Testing Library, Playwright.

## Global Constraints

- Keep scorer logic's pure/IO boundary: framework selection, environment reads, and file access stay outside pure calculation functions.
- `framework/versions/<id>/dimensions.yaml` is the complete scoring contract for that version; there is no runtime inheritance.
- Exactly one framework is `active`; at most one is `upcoming`; archived results are never recomputed.
- V0 and V1 preserve every product's current `target_medal`.
- V0 and V1 are computed independently; reuse is optional and must not affect correctness.
- Active refreshes nightly; upcoming refreshes weekly; both allow manual refresh.
- Product/component membership is start-inclusive at `introduced_in` and end-exclusive at `retired_in`.
- Stable metric IDs select immutable implementation revision IDs; scorer logic never branches on framework IDs.
- Remove remediation deadlines and drift states from the versioned engine and UI.
- Preserve the final pre-versioning static site at `/legacy/`; do not link it from the new UI.
- Do not add backward compatibility for the unversioned portfolio payload.
- Do not implement project-repository checks or Jira roadmap generation in this plan.
- Use only existing `make` targets for validation, extending the Makefile where version parameters are required.

---

## File Structure

### New framework and engine files

- `framework/versions/v0/framework.yaml` — V0 identity and active lifecycle state.
- `framework/versions/v0/dimensions.yaml` — approved V0 bedrock contract.
- `framework/versions/v1/framework.yaml` — V1 identity and upcoming lifecycle state.
- `framework/versions/v1/dimensions.yaml` — approved V1 operational contract.
- `config/schemas/framework.schema.json` — framework metadata schema.
- `engine/framework.py` — version discovery, lifecycle validation, contract loading, and digests.
- `engine/versioning.py` — version boundary and sparse target resolution.
- `engine/version_index.py` — `public/framework-versions.json` generation.
- `engine/workflow_matrix.py` — active/upcoming product/dimension job matrix generation.
- `scorers/registry.py` — immutable implementation-ID registry and dimension-runner adapters.
- `scorers/run.py` — generic version-aware scorer CLI.

### New UI files

- `ui/src/hooks/useFrameworkVersions.ts` — version-index query.
- `ui/src/providers/FrameworkVersionProvider.tsx` — selected-version routing context.
- `ui/src/components/VersionSelector.tsx` — upcoming/active/archived selector.
- `ui/src/components/VersionSelector.test.tsx` — selector behavior.
- `ui/e2e/framework-versions.spec.ts` — end-to-end version navigation.

### Modified files

- `config/schemas/dimensions.schema.json` — require implementation IDs.
- `config/schemas/product.schema.json` — add membership boundaries and target histories.
- `products/*.yaml` — migrate all current entities to V0/V1 membership and targets.
- `engine/models.py` — framework metadata and compliance-oriented result fields.
- `engine/graph.py` — build a graph for a selected framework version.
- `engine/medal_engine.py` — remove drift and compute `meets_target`.
- `engine/aggregation.py` — remove drift inputs and outputs.
- `engine/assemble.py` — assemble one selected framework into a versioned artifact.
- `engine/merge_computed.py` — write version metadata and implementation fingerprints.
- `engine/validate.py` — validate all framework snapshots and cross-file invariants.
- `engine/badges.py` — generate stable badges from the active portfolio.
- `Makefile` — require `FRAMEWORK_VERSION` for scoring and add version-index/assembly targets.
- `.github/workflows/compute-metrics.yml` — independent active/upcoming computation and publication.
- `.github/workflows/deploy-pages.yml` — preserve versioned data and `/legacy/`.
- `.github/workflows/deploy-legacy.yml` — one-time immutable legacy deployment.
- `ui/src/types.ts` — version index, framework metadata, and compliance types; remove drift.
- `ui/src/App.tsx` — version-prefixed routes and active-version redirect.
- `ui/src/hooks/usePortfolio.ts` — fetch `versions/<id>/portfolio.json`.
- `ui/src/components/GlobalNav.tsx` — version-aware links and selector placement.
- `ui/src/views/*.tsx` and `ui/src/views/__tests__/*.test.tsx` — remove drift UI and consume version context.
- `docs/architecture.md`, `docs/local-scoring.md`, `docs/adding-a-product.md`, `docs/adding-a-metric.md`, and `docs/adding-a-dimension.md` — versioned operating model.

### Deleted files

- `config/dimensions.yaml`
- `engine/drift_tracker.py`
- `engine/__tests__/test_drift_tracker.py`
- `ui/src/components/DriftChip.tsx`
- `ui/src/components/DriftChip.test.tsx`
- `drift-history.json`

---

### Task 1: Framework Contracts and Discovery

**Files:**
- Create: `framework/versions/v0/framework.yaml`
- Create: `framework/versions/v0/dimensions.yaml`
- Create: `framework/versions/v1/framework.yaml`
- Create: `framework/versions/v1/dimensions.yaml`
- Create: `config/schemas/framework.schema.json`
- Create: `engine/framework.py`
- Create: `engine/__tests__/test_framework.py`
- Modify: `config/schemas/dimensions.schema.json`

**Interfaces:**
- Produces: `FrameworkStatus`, `FrameworkVersion`, `discover_frameworks(root: Path) -> list[FrameworkVersion]`, `get_framework(frameworks, version_id) -> FrameworkVersion`, and `contract_digest(framework) -> str`.
- Produces CLI: `python3 -m engine.framework --root framework/versions --version v1
  --list-dimensions`.
- `FrameworkVersion.dimensions` is the parsed complete contract used by later tasks.

- [ ] **Step 1: Write failing discovery and invariant tests**

Add tests that create temporary `v0` and `v1` directories and assert:

```python
frameworks = discover_frameworks(tmp_path)
assert [(f.id, f.status) for f in frameworks] == [
    ("v0", FrameworkStatus.ACTIVE),
    ("v1", FrameworkStatus.UPCOMING),
]
assert get_framework(frameworks, "v1").sequence == 1
```

Add explicit failing cases for two active versions, two upcoming versions, duplicate sequences,
an archived version after the active sequence, and an unknown requested version.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest engine/__tests__/test_framework.py -v`

Expected: collection fails because `engine.framework` does not exist.

- [ ] **Step 3: Implement framework discovery**

Create immutable types and deterministic loading:

```python
class FrameworkStatus(StrEnum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class FrameworkVersion:
    id: str
    sequence: int
    label: str
    status: FrameworkStatus
    description: str
    directory: Path
    dimensions: dict[str, Any]
```

`discover_frameworks()` must load `*/framework.yaml` and the sibling `dimensions.yaml`, sort by
`sequence`, validate the collection, and raise `ValueError` with all conflicting IDs named.
`contract_digest()` must SHA-256 a canonical JSON encoding, using `sort_keys=True` and compact
separators, of the scoring contract only: `id`, `sequence`, and the complete `dimensions`
contract. Lifecycle and display metadata (`status`, `label`, `description`) must be excluded, so
activation from active to archived and label/description edits leave the digest unchanged while
criteria or implementation changes alter it.

Add a small module CLI whose `--list-dimensions` mode prints selected dimension IDs separated by
spaces for Makefile and workflow loops.

- [ ] **Step 4: Add framework and implementation schema fields**

`framework.schema.json` requires `id`, `sequence`, `label`, `status`, and `description`, disallows
unknown fields, and restricts IDs to `^v[0-9]+$`.

In `dimensions.schema.json`, add required output property:

```json
"implementation": {
  "type": "string",
  "pattern": "^[a-z][a-z0-9-]*/v[1-9][0-9]*$"
}
```

Keep dimensions scored and require at least one medal tier. Informational behavior remains an
output-level property.

- [ ] **Step 5: Add the approved V0 and V1 snapshots**

V0 contains:

- `test_verification`: `latest_build_passing` and `uses_jubilant`; bronze requires latest build,
  gold requires latest build plus Jubilant, with no silver criterion.
- `documentation`: bronze README, silver README+CONTRIBUTING, gold
  README+CONTRIBUTING+SECURITY; Diataxis AI and RTD informational.
- `security_ssdlc`: bronze Renovate, silver Renovate+branch protection, gold
  Renovate+branch protection+signed commits.
- `engagement`: bronze ownership, silver ownership+coverage >=80, gold
  ownership+coverage >=90.
- no `substrate_compat`.

V1 contains the exact tables from
`docs/superpowers/specs/2026-09-10-framework-versioning-design.md#initial-v0-and-v1-contracts`.
Assign each selected output an implementation ID matching Task 3's registry, such as
`latest-build-passing/v1`, `readme-present/v1`, and `ownership-signal/v1`.

- [ ] **Step 6: Run framework tests**

Run: `pytest engine/__tests__/test_framework.py engine/__tests__/test_validate.py -v`

Expected: all framework tests pass; existing validation tests may still fail until Task 5 migrates
the validator and catalog schema.

- [ ] **Step 7: Commit**

```bash
git add framework config/schemas/framework.schema.json \
  config/schemas/dimensions.schema.json engine/framework.py \
  engine/__tests__/test_framework.py
git commit -m "feat: define versioned framework contracts"
```

---

### Task 2: Version-Aware Catalog and Targets

**Files:**
- Create: `engine/versioning.py`
- Create: `engine/__tests__/test_versioning.py`
- Modify: `config/schemas/product.schema.json`
- Modify: `engine/graph.py`
- Modify: `engine/models.py`
- Modify: `engine/assemble.py`
- Modify: `engine/__tests__/test_graph.py`
- Modify: `scorers/*/scorer.py`
- Modify: `products/*.yaml`

**Interfaces:**
- Consumes: `FrameworkVersion.sequence`.
- Produces: `VersionBoundary`, `is_in_version(data, versions, selected) -> bool`,
  `resolve_target(data, versions, selected) -> str`, and
  `build_graph(product_dicts, frameworks, selected_framework) -> ProductGraph`.

- [ ] **Step 1: Write failing boundary and target tests**

Cover start-inclusive/end-exclusive behavior and sparse target resolution:

```python
assert is_in_version({"introduced_in": "v1"}, frameworks, v1)
assert not is_in_version({"introduced_in": "v1"}, frameworks, v0)
assert not is_in_version(
    {"introduced_in": "v0", "retired_in": "v1"}, frameworks, v1
)
assert resolve_target(
    {"introduced_in": "v0", "targets": {"v0": "bronze", "v1": "silver"}},
    frameworks,
    v1,
) == "silver"
```

Add graph tests proving a V1-only inline Hive-like component and a V1-only `ref:` composition edge
are absent from V0 and included in V1.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest engine/__tests__/test_versioning.py engine/__tests__/test_graph.py -v`

Expected: failures for missing versioning helpers and old `build_graph` signature.

- [ ] **Step 3: Implement boundary and target resolution**

Use framework sequence numbers, never lexical version comparison. Raise `ValueError` for unknown
boundaries, invalid ranges, or missing target at introduction. Return the latest target declaration
whose sequence is not greater than the selected version.

- [ ] **Step 4: Filter graph nodes and edges**

Update graph construction so it:

1. excludes top-level products outside the selected version,
2. excludes inline leaves outside the selected version,
3. applies boundaries on `ref:` edges independently,
4. rejects active edges with inactive endpoints,
5. stores the resolved target on every active node.

Remove target inheritance lookups from `resolve_leaf_units*`; consume the graph node's already
resolved target.

- [ ] **Step 5: Update existing graph callers**

Update `engine/assemble.py`, every `scorers/*/scorer.py`, and graph/aggregation test fixtures to
discover frameworks and pass an explicit selected version. Add `--framework-root` and
`--framework-version` to temporary dimension scorer CLIs; Task 3 will consolidate their duplicate
argument handling. Do not add an implicit active-version fallback.

- [ ] **Step 6: Update product schema**

Replace required `target_medal` with:

```yaml
introduced_in: v0
targets:
  v0: gold
  v1: gold
```

Add optional `retired_in` to products and inline leaves. Add `introduced_in` and `retired_in` to
`ref:` composition entries. Require version IDs to match `^v[0-9]+$`; require target values to be
`bronze`, `silver`, or `gold`.

- [ ] **Step 7: Migrate every current product**

For each `products/*.yaml`:

- add `introduced_in: v0` after `lifecycle`,
- replace `target_medal: <grade>` with:

```yaml
targets:
  v0: <grade>
  v1: <grade>
```

- add `introduced_in: v0` to every inline leaf and every `ref:` entry,
- do not add `retired_in` where no retirement is planned.

Preserve each existing grade exactly in both versions.

- [ ] **Step 8: Run graph and schema tests**

Run: `pytest engine/__tests__/test_versioning.py engine/__tests__/test_graph.py engine/__tests__/test_validate.py -v`

Expected: all tests pass after Task 5 wires cross-file validation; until then, only the standalone
schema assertions and graph tests must pass.

- [ ] **Step 9: Commit**

```bash
git add engine/versioning.py engine/graph.py engine/models.py engine/assemble.py \
  engine/__tests__/test_versioning.py engine/__tests__/test_graph.py \
  config/schemas/product.schema.json scorers products
git commit -m "feat: version product membership and targets"
```

---

### Task 3: Metric Implementation Registry and Generic Runner

**Files:**
- Create: `scorers/registry.py`
- Create: `scorers/run.py`
- Create: `scorers/__tests__/test_registry.py`
- Create: `scorers/__tests__/test_run.py`
- Modify: `scorers/*/scorer.py`

**Interfaces:**
- Consumes: output `implementation` IDs from a selected `FrameworkVersion`.
- Produces: `ScorerContext`, `MetricBinding`,
  `run_dimension(unit, dimension_name, dimension_config, context) -> dict[str, Any]`,
  `implementation_fingerprints(dimension_config) -> dict[str, str]`, and CLI JSON shaped as
  `{leaf_id: {metric_id: value}}`.

- [ ] **Step 1: Write failing registry tests**

Test that two output IDs bound to the same dimension callable execute that callable once and filter
the returned mapping:

```python
metrics = run_dimension(unit, "test_verification", config, context)
assert metrics == {
    "latest_build_passing": True,
    "uses_jubilant": False,
}
compute.assert_called_once_with(unit, github_token="token")
```

Test unknown IDs, wrong-dimension bindings, and missing returned output keys as explicit errors.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest scorers/__tests__/test_registry.py scorers/__tests__/test_run.py -v`

Expected: collection fails because the registry and generic runner do not exist.

- [ ] **Step 3: Implement the registry**

Define:

```python
@dataclass(frozen=True)
class ScorerContext:
    github_token: str
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4.5"


@dataclass(frozen=True)
class MetricBinding:
    dimension: str
    output_key: str
    runner_key: str
```

Register every V0/V1 implementation ID. `runner_key` maps to a thin adapter around the existing
dimension `compute_metrics()` function. Group selected bindings by `runner_key`, execute each
adapter once per evaluation unit, and extract only selected output keys.

`implementation_fingerprints()` hashes the source file for every selected binding and returns a
mapping from implementation ID to SHA-256. These fingerprints are recorded separately from the
contract digest.

- [ ] **Step 4: Implement the generic scorer CLI**

`scorers/run.py` accepts:

```text
--framework-root framework/versions
--framework-version v1
--dimension test_verification
--product-yaml products/matrix.yaml
--products-dir products
```

It discovers frameworks, builds the selected version's graph, rejects archived computation,
constructs `ScorerContext` from environment variables, and prints the existing per-leaf JSON
shape.

- [ ] **Step 5: Convert dimension scorer files to compatibility wrappers**

Make each `scorers/<dimension>/scorer.py` call `scorers.run.main()` with its fixed dimension only
until Makefile and workflow callers move in Task 6. Keep wrappers small and remove duplicate graph
loading.

- [ ] **Step 6: Run scorer tests**

Run: `pytest scorers/__tests__/test_registry.py scorers/__tests__/test_run.py scorers -v`

Expected: all scorer tests pass; existing logic tests remain unchanged.

- [ ] **Step 7: Commit**

```bash
git add scorers
git commit -m "feat: dispatch versioned metric implementations"
```

---

### Task 4: Versioned Results Without Drift

**Files:**
- Modify: `engine/models.py`
- Modify: `engine/medal_engine.py`
- Modify: `engine/aggregation.py`
- Modify: `engine/assemble.py`
- Modify: `engine/merge_computed.py`
- Modify: `engine/badges.py`
- Create: `engine/version_index.py`
- Modify: `engine/__tests__/test_medal_engine.py`
- Modify: `engine/__tests__/test_aggregation.py`
- Modify: `engine/__tests__/test_assemble.py`
- Modify: `engine/__tests__/test_badges.py`
- Create: `engine/__tests__/test_version_index.py`
- Delete: `engine/drift_tracker.py`
- Delete: `engine/__tests__/test_drift_tracker.py`
- Delete: `drift-history.json`

**Interfaces:**
- Consumes: selected `FrameworkVersion`, selected graph, and
  `computed/versions/<id>/<product>.json`.
- Produces: `public/versions/<id>/portfolio.json`,
  `build_version_index(frameworks, public_dir) -> dict`, and `ProductResult.meets_target`.

- [ ] **Step 1: Rewrite result tests around compliance**

Replace drift assertions with:

```python
assert result.meets_target is False
assert result.dimensions["documentation"].meets_target is True
```

Add assembly tests asserting `framework`, `contract_digest`, `source_revision`,
`implementation_fingerprints`, and `compliance_summary` are embedded. Add a regression test that
assembling V1 does not modify an existing V0 portfolio file.

- [ ] **Step 2: Run result tests and confirm failure**

Run: `pytest engine/__tests__/test_medal_engine.py engine/__tests__/test_aggregation.py engine/__tests__/test_assemble.py engine/__tests__/test_version_index.py -v`

Expected: failures for missing compliance fields and version metadata.

- [ ] **Step 3: Remove drift from the domain model**

Delete `DriftState` and every drift parameter. Add `meets_target: bool` to `DimensionResult` and
`ProductResult`, computed with:

```python
MEDAL_RANK[current_medal] >= MEDAL_RANK[target_medal]
```

Keep `insufficient_data` distinct from measured-low; insufficient data never meets target.

- [ ] **Step 4: Version computed envelopes**

`merge_computed.py` must accept `--framework-version`, `--contract-digest`, and a JSON
implementation-fingerprint mapping. Emit:

```json
{
  "framework_version": "v1",
  "contract_digest": "<sha256>",
  "implementation_fingerprints": {},
  "product_id": "matrix",
  "computed_at": "<UTC ISO-8601>",
  "leaf_metrics": {}
}
```

Reject a scorer output missing a dimension declared by the selected contract instead of warning
and continuing.

- [ ] **Step 5: Assemble one selected version**

Replace drift arguments with `--framework-root`, `--framework-version`, and `--source-revision`.
Read only `computed/versions/<version>`, verify every envelope's version and contract digest, and
write `public/versions/<version>/portfolio.json`.

Compute portfolio summary counts for `total`, `meeting_target`, `below_target`, and
`insufficient_data`. Embed complete dimension metadata and selected implementation fingerprints.

- [ ] **Step 6: Generate the version index**

`engine/version_index.py` reads framework metadata and existing version portfolios. For each
version, emit:

```json
{
  "id": "v1",
  "sequence": 1,
  "label": "PQF V1",
  "status": "upcoming",
  "description": "...",
  "portfolio_url": "versions/v1/portfolio.json",
  "generated_at": "...",
  "contract_digest": "..."
}
```

Fail when an active/upcoming portfolio is absent or has a mismatched digest. Permit archived
entries only when their frozen portfolio exists. Archived entries are read as-is — never
recomputed — and the index publishes the archived scoring-contract identity recorded in the
payload (its contract digest and generation time), so a reviewed format migration of an archived
artifact is accepted as long as it preserves that identity. A mismatched archived digest still
fails, because it means the archived scoring rules changed.

- [ ] **Step 7: Keep badge URLs active-only**

Update `engine/badges.py` callers so `public/badges/` is generated only from the active
`portfolio.json`. This preserves stable external badge URLs without creating version-selection
semantics for badges.

- [ ] **Step 8: Run engine tests**

Run: `pytest engine/__tests__/test_medal_engine.py engine/__tests__/test_aggregation.py engine/__tests__/test_assemble.py engine/__tests__/test_badges.py engine/__tests__/test_version_index.py -v`

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add engine .gitignore
git rm engine/drift_tracker.py engine/__tests__/test_drift_tracker.py drift-history.json
git commit -m "feat: assemble versioned compliance results"
```

---

### Task 5: Cross-File Validation and Change Classification

**Files:**
- Modify: `engine/validate.py`
- Create: `engine/change_report.py`
- Modify: `engine/__tests__/test_validate.py`
- Create: `engine/__tests__/test_change_report.py`

**Interfaces:**
- Consumes: framework directories, product catalog, implementation registry, and optional base Git
  revision.
- Produces: `validate_repository(...) -> list[str]` and a human-readable semantic change report.

- [ ] **Step 1: Write failing repository-validation tests**

Cover:

- dimension without medals,
- criteria referencing undeclared output,
- required metric referencing undeclared output,
- unknown implementation ID,
- missing target at introduction,
- invalid active composition edge.

- [ ] **Step 2: Write failing change-classification tests**

Given base/head contract dictionaries, assert output categories for metadata-only, added
informational metric, implementation revision change, rubric change, and target change.

- [ ] **Step 3: Run focused tests**

Run: `pytest engine/__tests__/test_validate.py engine/__tests__/test_change_report.py -v`

Expected: failures for missing cross-file validator and change reporter.

- [ ] **Step 4: Implement cross-file validation**

Keep JSON Schema validation for shape, then call framework, catalog, rubric-reference, and registry
checks. Print all errors in one run. Update CLI defaults to `--framework-root framework/versions`
and remove the single `--dimensions` default.

- [ ] **Step 5: Implement semantic change reporting**

`engine/change_report.py --base-ref <sha>` loads framework and product YAML from the base ref using
`git show`, compares with the worktree, and prints Markdown sections:

```text
Metadata-only changes
Additive informational measurements
Scoring-semantic changes
Catalog membership or target changes
```

Return exit code 0 even when reviewed semantic changes exist; return non-zero only for invalid
input. This is governance visibility, not a technical lock.

- [ ] **Step 6: Run validation tests**

Run: `pytest engine/__tests__/test_validate.py engine/__tests__/test_change_report.py -v`

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add engine/validate.py engine/change_report.py engine/__tests__ \
  config/schemas
git commit -m "feat: validate framework lifecycle and semantics"
```

---

### Task 6: Version-Aware Local Commands

**Files:**
- Modify: `Makefile`
- Modify: `docs/local-scoring.md`
- Modify: `engine/__tests__/test_integration.py`

**Interfaces:**
- Consumes: Tasks 1-5 CLIs.
- Produces: `make score`, `make score-no-llm`, `make _merge`, and `make _assemble` with explicit
  `FRAMEWORK_VERSION`.

- [ ] **Step 1: Add failing command-level integration tests**

Run generic scorer, merge, and assembly subprocesses against a temporary product and framework.
Assert output paths include `versions/v1` and archived computation exits non-zero.

- [ ] **Step 2: Update Makefile parameters**

Add:

```make
FRAMEWORK_VERSION ?= $(error FRAMEWORK_VERSION is required. Example: FRAMEWORK_VERSION=v1)
FRAMEWORK_DIR := framework/versions/$(FRAMEWORK_VERSION)
VERSION_SCORE_DIR := $(SCORE_DIR)/$(FRAMEWORK_VERSION)/$(PRODUCT)
VERSION_COMPUTED_DIR := computed/versions/$(FRAMEWORK_VERSION)
VERSION_PUBLIC_DIR := public/versions/$(FRAMEWORK_VERSION)
```

Replace five hard-coded scorer commands with one loop over dimensions discovered from the selected
contract and `python3 scorers/run.py`. Pass selected version paths to merge and assembly. Add
`_version-index`.

- [ ] **Step 3: Update local-scoring documentation**

Use exact commands:

```bash
make score-no-llm PRODUCT=matrix FRAMEWORK_VERSION=v1
make _merge PRODUCT=matrix FRAMEWORK_VERSION=v1
make _assemble FRAMEWORK_VERSION=v1
make _version-index
```

Explain active/upcoming eligibility, archived rejection, versioned output paths, and weekly
upcoming freshness.

- [ ] **Step 4: Run command integration tests**

Run: `pytest engine/__tests__/test_integration.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add Makefile docs/local-scoring.md engine/__tests__/test_integration.py
git commit -m "feat: select framework versions in local scoring"
```

---

### Task 7: Preserve the Pre-Versioning Site

**Files:**
- Create: `.github/workflows/deploy-legacy.yml`
- Modify: `.github/workflows/deploy-pages.yml`
- Modify: `engine/__tests__/test_workflows.py`

**Interfaces:**
- Produces: a one-time manual workflow that deploys a requested pre-versioning Git ref to
  `gh-pages:/legacy/`.

- [ ] **Step 1: Add failing workflow tests**

Assert `deploy-legacy.yml`:

- is `workflow_dispatch` only,
- requires a `ref` input,
- checks out that ref,
- builds the UI from that ref,
- deploys `ui/dist` to `legacy`,
- uses `keep_files: true`.

Assert normal deploys preserve `legacy/`.

- [ ] **Step 2: Run workflow tests and confirm failure**

Run: `pytest engine/__tests__/test_workflows.py -v`

Expected: failure because `deploy-legacy.yml` is absent.

- [ ] **Step 3: Implement the manual legacy workflow**

Use `actions/checkout@v4` with `${{ inputs.ref }}`, Node 22, `npm install`, `npm run build`, and
`peaceiris/actions-gh-pages@v4` with:

```yaml
publish_dir: ui/dist
destination_dir: legacy
keep_files: true
```

The workflow must not invoke scorers; it snapshots the selected commit's already compatible static
site and data.

- [ ] **Step 4: Preserve legacy during normal deploys**

Keep `keep_files: true` and ensure public-data synchronization copies only version index, version
directories, and badges instead of deleting the checked-out Pages tree.

- [ ] **Step 5: Run workflow tests**

Run: `pytest engine/__tests__/test_workflows.py -v`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/deploy-legacy.yml .github/workflows/deploy-pages.yml \
  engine/__tests__/test_workflows.py
git commit -m "ci: preserve pre-versioning site"
```

---

### Task 8: Compute and Publish Active and Upcoming Versions

**Files:**
- Create: `engine/workflow_matrix.py`
- Create: `engine/__tests__/test_workflow_matrix.py`
- Modify: `.github/workflows/compute-metrics.yml`
- Modify: `engine/__tests__/test_workflows.py`

**Interfaces:**
- Consumes: framework discovery and version-aware scorer/merge/assembly commands.
- Produces: matrix rows shaped as `{"framework_version": "v1", "product": "matrix"}`.

> **Approved amendment (user-approved):** the matrix is
> `(framework_version, product)`, **not** `(framework_version, product, dimension)`.
> Each job discovers and runs every dimension its framework version declares,
> sequentially. This caps push/PR at 68 jobs (34 products x 2 live versions) instead of
> 306, amortizes checkout/install across all dimensions, and merges once per run.

> **Clarified archive policy (user-approved):**
> - **Frozen measurements** — archived repository scorers must never run, on any cadence,
>   dispatch, or bootstrap path.
> - **Migratable payload format** — archived portfolio payloads are not write-protected. A
>   reviewed format migration may transform an archived artifact for a newer UI schema as long
>   as it preserves recorded metric values, results, product membership, generation time, and
>   the original scoring-contract identity. PR review is the governance gate; the engine adds
>   no hard lock on archive files.
> - **No archived rescoring** — digest validation is not relaxed for archives. A digest
>   mismatch on an archived artifact means the archived scoring rules changed, which is an
>   error, not a trigger to recompute.
> - **Scoring-only digest** — `contract_digest` hashes only scoring semantics (the complete
>   dimensions contract, plus `id` and `sequence`, which scope it and resolve catalog
>   membership). `status`, `label`, and `description` are excluded, so activation from active
>   to archived and label/description edits preserve the digest.

- [ ] **Step 1: Write failing matrix tests**

Assert nightly selection returns only active rows, weekly selection returns only upcoming rows,
manual selection accepts active/upcoming, archived selection fails, and catalog filtering excludes
products outside the selected version.

Also assert, on the real catalog, that the matrix is one row per
(framework version, product) with no `dimension` key and no duplicates, that it is
strictly smaller than the equivalent version/product/dimension matrix, and that it stays within
GitHub Actions' hard limit (`len(rows) <= 256`).

- [ ] **Step 2: Implement matrix generation**

`python3 -m engine.workflow_matrix --cadence nightly|weekly|manual|changed
[--framework-version <id>] [--changed-paths-file <file>] [--published-dir <dir>]` must print
compact JSON for `$GITHUB_OUTPUT`, with rows containing only `framework_version` and `product`.

Cadence must also be derivable from the schedule cron with
`--schedule "<cron>"`, resolved through an exact, tested `SCHEDULE_CADENCES` mapping that
rejects any undeclared cron. Never compare cron literals in workflow shell.

`--cadence changed` selects live versions from a list of changed paths: a change under
`framework/versions/<id>/` affects only that version; changes to shared inputs
(`scorers/`, `engine/`, `config/`, `products/`, the workflow, or `framework/` files outside a
known version directory) affect every live version. `__tests__/` paths are ignored.

- [ ] **Step 3: Refactor the workflow**

Use two cron entries:

```yaml
- cron: "0 2 * * *"
- cron: "0 3 * * 1"
```

Pass `github.event.schedule` to the matrix script and let it map the cron to a cadence. Build a
version/product matrix; each compute job lists its framework version's dimensions via
`python3 -m engine.framework --list-dimensions` and loops `scorers/run.py` over them, uploading
one artifact per (version, product). Merge per version/product once, assemble each selected
version, then publish.

On push and PR events, diff the changed paths into a file and use `--cadence changed`. On manual
dispatch, require a version choice discovered and validated by the matrix script. Handle a
missing/zero `github.event.before` by treating the whole tree as changed.

- [ ] **Step 4: Bootstrap, preserve, and publish**

`determine-matrix` checks out the published `gh-pages` data (tolerating a missing branch) and
passes it as `--published-dir`. Every live version whose portfolio there is missing, unreadable,
or recorded against a different contract digest is added to the matrix automatically, so the
version index can always be rebuilt instead of failing late. Archived versions are never added.

Before publishing, copy the published `versions/<id>` directories into the deployment artifact,
which is what preserves archived versions; never schedule or matrix archived scorer jobs.
Regenerate the active version's `portfolio.json` and badges at the stable root paths
`public/portfolio.json` and `public/badges/`, clearing `public/badges/` first so products removed
from the catalog cannot accumulate. `keep_files: true` on deploy preserves `/legacy/`.

Upload the publish artifact from `public/`, and have every consumer download it with
`path: public` (after clearing repo-tracked `public/` data) so `framework-versions.json`,
`versions/`, badges, and the root portfolio all reach Vite's `publicDir`.

- [ ] **Step 5: Gate publishing and deployment on upstream success**

`run-engine` must run only when `determine-matrix` succeeded and either every upstream compute
job succeeded, or the version selection was genuinely empty (`versions == '[]'`) and those jobs
were therefore skipped. Never treat `skipped` as success when there was work to do. Deploy jobs
keep the implicit `success()` gate on `run-engine`.

- [ ] **Step 6: Add semantic change report to pull requests**

Run `python3 -m engine.change_report --base-ref origin/${{ github.base_ref }}` before compute jobs
and append its Markdown to `$GITHUB_STEP_SUMMARY`.

- [ ] **Step 7: Run workflow tests**

Run: `pytest engine/__tests__/test_workflow_matrix.py engine/__tests__/test_workflows.py -v`

Expected: all pass. `test_workflows.py` must assert the workflow's declared cron entries match
`SCHEDULE_CADENCES` exactly, that artifacts are downloaded with `path: public`, and that the
`run-engine` gate blocks on upstream failure.

- [ ] **Step 8: Commit**

```bash
git add engine/workflow_matrix.py engine/__tests__/test_workflow_matrix.py \
  engine/__tests__/test_workflows.py .github/workflows/compute-metrics.yml
git commit -m "ci: compute active and upcoming frameworks"
```

---

### Task 9: Version-Scoped UI Data and Navigation

**Files:**
- Modify: `ui/src/types.ts`
- Create: `ui/src/hooks/useFrameworkVersions.ts`
- Modify: `ui/src/hooks/usePortfolio.ts`
- Create: `ui/src/providers/FrameworkVersionProvider.tsx`
- Create: `ui/src/components/VersionSelector.tsx`
- Create: `ui/src/components/VersionSelector.test.tsx`
- Modify: `ui/src/components/GlobalNav.tsx`
- Modify: `ui/src/components/GlobalNav.test.tsx`
- Modify: `ui/src/App.tsx`

**Interfaces:**
- Produces: `FrameworkVersionSummary`, `FrameworkVersionIndex`,
  `useFrameworkVersions()`, `useFrameworkVersion()`, and `usePortfolio(versionId)`.
- Routes use `/:frameworkVersion/...`, for example `#/v1/products/matrix`.

- [ ] **Step 1: Write failing hook and selector tests**

Mock:

```json
{
  "versions": [
    {"id":"v1","sequence":1,"label":"PQF V1","status":"upcoming","portfolio_url":"versions/v1/portfolio.json"},
    {"id":"v0","sequence":0,"label":"PQF V0","status":"active","portfolio_url":"versions/v0/portfolio.json"}
  ]
}
```

Assert the selector groups statuses, marks V0 selected, navigates to the same sub-route under V1,
and displays the upcoming generated timestamp.

- [ ] **Step 2: Extend TypeScript types**

Remove `DriftInfo` and `DimensionEntry.drift`. Add:

```typescript
export type FrameworkStatus = 'upcoming' | 'active' | 'archived'

export interface FrameworkVersionSummary {
  id: string
  sequence: number
  label: string
  status: FrameworkStatus
  description: string
  portfolio_url: string
  generated_at: string
  contract_digest: string
}
```

Add framework metadata, implementation fingerprints, `meets_target`, and compliance summary to
`Portfolio`.

- [ ] **Step 3: Implement version-aware data hooks**

Fetch `${BASE_URL}framework-versions.json`. Fetch portfolios with:

```typescript
queryKey: ['portfolio', version.id]
queryFn: () => fetch(`${BASE_URL}${version.portfolio_url}`)
```

Reject an index entry whose fetched portfolio ID or digest does not match.

- [ ] **Step 4: Implement provider and routes**

`FrameworkVersionProvider` validates the `:frameworkVersion` route parameter against the index.
Bare `/` redirects to `/${active.id}` after loading. Unknown version IDs render an explicit
not-found state rather than silently switching versions. `framework-versions.json` is the source
of truth for lifecycle/display metadata (`status`, `label`, `description`); the embedded
`framework` block in each portfolio is provenance only and must not drive UI labels.

Nest every existing route under `/:frameworkVersion`, preserving the selected version in all
internal links.

- [ ] **Step 5: Implement the selector**

Use Canonical React Components' `Select` or form control. Order groups Upcoming, Active, Archived;
within each group order descending by sequence. On change, replace only the first route segment and
preserve the remainder of the path.

- [ ] **Step 6: Run focused UI tests**

Run: `cd ui && npm test -- src/components/VersionSelector.test.tsx src/components/GlobalNav.test.tsx`

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add ui/src/types.ts ui/src/hooks ui/src/providers ui/src/components \
  ui/src/App.tsx
git commit -m "feat: navigate framework versions in the UI"
```

---

### Task 10: Compliance UI and Drift Removal

**Files:**
- Modify: `ui/src/views/Overview.tsx`
- Modify: `ui/src/views/ProductDetail.tsx`
- Modify: `ui/src/views/DimensionDetail.tsx`
- Modify: `ui/src/views/DimensionsOverview.tsx`
- Modify: `ui/src/views/MetricDistribution.tsx`
- Modify: `ui/src/views/ProductsExplorer.tsx`
- Modify: `ui/src/lib/groupedPortfolioView.ts`
- Modify: `ui/src/views/__tests__/*.test.tsx`
- Modify: `ui/src/lib/groupedPortfolioView.test.ts`
- Delete: `ui/src/components/DriftChip.tsx`
- Delete: `ui/src/components/DriftChip.test.tsx`

**Interfaces:**
- Consumes: version-scoped `Portfolio` with `meets_target` and `compliance_summary`.
- Produces: no drift/remediation UI; all screens reflect the selected framework.

- [ ] **Step 1: Replace drift assertions with compliance assertions**

Update fixtures to include framework metadata and `meets_target`. Assert Overview shows
`meeting_target / total`, Product Detail identifies dimensions below target, and no
“remediating,” “overdue,” or deadline text renders.

- [ ] **Step 2: Run view tests and confirm failure**

Run: `make test-ui`

Expected: failures where views still require `drift`.

- [ ] **Step 3: Remove drift components and columns**

Delete `DriftChip`; remove imports, deadlines, drift counters, and drift filters. Render compact
“Meets target” / “Below target” statuses using existing status patterns and exact medal comparison
semantics from the payload.

- [ ] **Step 4: Add framework context labels**

Show:

- upcoming: `Planning against PQF V1 · refreshed <date>`,
- active: `Current framework · PQF V0`,
- archived: `Archived snapshot · generated <date>`.

Do not add a legacy-site link.

- [ ] **Step 5: Run UI tests and build**

Run: `make test-ui && make build`

Expected: all tests pass and TypeScript/Vite build succeeds.

- [ ] **Step 6: Commit**

```bash
git add ui/src
git rm ui/src/components/DriftChip.tsx ui/src/components/DriftChip.test.tsx
git commit -m "feat: show framework compliance progress"
```

---

### Task 11: Browser Verification and Version E2E

**Files:**
- Create: `ui/e2e/framework-versions.spec.ts`
- Modify: `ui/e2e/navigation.spec.ts`

**Interfaces:**
- Consumes: completed versioned UI and generated V0/V1 fixtures.
- Produces: browser coverage for version selection, complete view switching, and direct links.

- [ ] **Step 1: Write failing Playwright coverage**

Test:

1. bare root redirects to active V0,
2. selector switches to V1 without changing the current page,
3. V1-only product appears in V1 and is absent in V0,
4. direct `#/v1/dimensions/documentation` loads V1,
5. upcoming and archived labels render,
6. no legacy link appears.

- [ ] **Step 2: Run E2E and confirm failure**

Run: `make e2e`

Expected: new version tests fail before final fixture/routing adjustments.

- [ ] **Step 3: Fix route or fixture defects exposed by E2E**

Limit changes to the version provider, selector, route generation, and test fixture data. Do not
add cross-version diff behavior.

- [ ] **Step 4: Run E2E again**

Run: `make e2e`

Expected: all tests pass.

- [ ] **Step 5: Inspect with playwright-cli**

Run the existing dev target, then use `playwright-cli` to inspect V0 overview, V1 overview, a
V1-only product, and one dimension page at desktop and mobile widths. Compare the major navigation
and information hierarchy with the immutable `/legacy/` build; fix only regressions introduced by
version navigation.

- [ ] **Step 6: Commit**

```bash
git add ui/e2e ui/src
git commit -m "test: cover framework version navigation"
```

---

### Task 12: Contributor Documentation and Final Integration

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/adding-a-product.md`
- Modify: `docs/adding-a-metric.md`
- Modify: `docs/adding-a-dimension.md`
- Modify: `docs/views/overview.md`
- Modify: `README.md`
- Modify: `AGENTS.md` if it still names `config/dimensions.yaml` as the single contract.

**Interfaces:**
- Documents all operator-facing contracts introduced by Tasks 1-11.

- [ ] **Step 1: Update architecture and contributor guides**

Document:

- framework directory and lifecycle,
- full-snapshot authoring,
- metric ID versus implementation revision,
- product/component/edge boundaries,
- sparse targets,
- active/upcoming cadence,
- frozen archives,
- explicit local `FRAMEWORK_VERSION`,
- `/legacy/` purpose,
- prohibition on archived recomputation.
- framework compliance summaries in `docs/views/overview.md` replacing stale drift wording.

Replace statements that `config/dimensions.yaml` is the single config knob.

- [ ] **Step 2: Remove the unversioned contract**

Delete `config/dimensions.yaml` only after all callers use framework snapshots. Confirm:

Run: `rg "config/dimensions.yaml" --glob '!docs/superpowers/**'`

Expected: no runtime, workflow, or current-guide references.

- [ ] **Step 3: Run repository validation**

Run: `make validate`

Expected: all framework contracts and products are valid.

- [ ] **Step 4: Run Python checks**

Run: `make lint && make format-check && make test`

Expected: all pass.

- [ ] **Step 5: Run UI checks**

Run: `make test-ui && make build && make e2e`

Expected: all pass.

- [ ] **Step 6: Verify generated contracts locally**

Run:

```bash
make score-no-llm PRODUCT=matrix FRAMEWORK_VERSION=v0
make _merge PRODUCT=matrix FRAMEWORK_VERSION=v0
make _assemble FRAMEWORK_VERSION=v0
make score-no-llm PRODUCT=matrix FRAMEWORK_VERSION=v1
make _merge PRODUCT=matrix FRAMEWORK_VERSION=v1
make _assemble FRAMEWORK_VERSION=v1
make _version-index
```

Expected:

- V0 and V1 portfolios have different dimension contracts,
- both preserve Matrix's current target,
- version index marks V0 active and V1 upcoming,
- no drift fields exist,
- generated previews remain uncommitted.

- [ ] **Step 7: Commit documentation and contract removal**

```bash
git add README.md AGENTS.md docs
git rm config/dimensions.yaml
git commit -m "docs: explain framework version operations"
```

- [ ] **Step 8: Review the complete branch**

Run: `git diff --check main...HEAD && git status --short`

Expected: no whitespace errors and only intentional generated local previews remain untracked or
modified. Remove local generated previews without altering committed GHA-maintained artifacts.
