# Safe Cross-Version Scorer Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score each product's selected framework versions in one process, reusing measurements only when the evaluation unit, scorer context, runner identity, and complete runner-source fingerprint are identical, while reducing engagement medals to ownership-only criteria.

**Architecture:** The workflow matrix groups selected framework versions by product. A batch scorer processes every grouped version and shares an in-memory `RunnerCache`; `run_dimension` keys entries with the complete evaluation-unit identity, immutable scorer context, runner key, and digest of every file registered in `RUNNER_SOURCE_FILES`. Contracts continue to select and filter output implementations independently, so cached raw runner output cannot bypass version-specific output declarations.

**Tech Stack:** Python 3.12, pytest, GitHub Actions YAML, existing PQF framework/registry/graph modules.

## Global Constraints

- Cache reuse requires exact equality of evaluation-unit identity, scorer context, runner key, and complete runner-source fingerprint.
- Framework contracts remain authoritative for selected output implementations and criteria.
- Response coverage and timing metrics remain available as measurements but are neither required for engagement scoring nor used in engagement medal criteria.
- GitHub acquisition failures that would otherwise create false required metrics must fail scoring rather than publish success-shaped data.
- Use existing `make` targets for validation.

---

### Task 1: Ownership-only engagement criteria

**Files:**
- Modify: `framework/versions/v0/dimensions.yaml`
- Modify: `framework/versions/v1/dimensions.yaml`
- Test: `engine/__tests__/test_validate.py`

**Interfaces:**
- Consumes: existing framework dimension contract schema.
- Produces: V0 and V1 engagement contracts whose only required metric and only medal criterion is `ownership_signal`.

- [ ] **Step 1: Write failing contract assertions**

Assert for both V0 and V1 that `required_metrics_for_scoring == ["ownership_signal"]` and every engagement medal contains exactly `["ownership_signal == true"]`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest --tb=short engine/__tests__/test_validate.py -q`

Expected: FAIL because response coverage and V1 response-time metrics are still required and used by silver/gold.

- [ ] **Step 3: Update both contracts**

Keep all existing outputs, but set:

```yaml
required_metrics_for_scoring:
  - ownership_signal
medals:
  bronze: ["ownership_signal == true"]
  silver: ["ownership_signal == true"]
  gold: ["ownership_signal == true"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest --tb=short engine/__tests__/test_validate.py -q`

Expected: PASS.

### Task 2: Fingerprint-guarded runner cache

**Files:**
- Modify: `scorers/registry.py`
- Modify: `scorers/__tests__/test_registry.py`

**Interfaces:**
- Produces: `RunnerCache`, an in-memory mapping accepted by `run_dimension(..., runner_cache=None)`.
- Cache key: runner key, complete runner-source digest, all `EvaluationUnit` fields, and `ScorerContext`.

- [ ] **Step 1: Write failing cache tests**

Call `run_dimension` for V0 and V1 configurations sharing a runner and cache. Assert one runner invocation when all key inputs match; then assert a second invocation after changing a registered runner source or evaluation-unit field.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest --tb=short scorers/__tests__/test_registry.py -q`

Expected: FAIL because `run_dimension` has no shared cache.

- [ ] **Step 3: Implement the minimal cache**

Add a source-digest helper over every path in `RUNNER_SOURCE_FILES`, an immutable key containing every safety input, and optional cache lookup/population around runner execution. Continue filtering runner output through selected metric bindings after lookup.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest --tb=short scorers/__tests__/test_registry.py -q`

Expected: PASS.

### Task 3: Product-grouped batch scoring

**Files:**
- Create: `scorers/batch.py`
- Create: `scorers/__tests__/test_batch.py`
- Modify: `engine/workflow_matrix.py`
- Modify: `engine/__tests__/test_workflow_matrix.py`
- Modify: `.github/workflows/compute-metrics.yml`
- Modify: `engine/__tests__/test_workflows.py`

**Interfaces:**
- Consumes: `RunnerCache`, selected version IDs, product YAML, framework root, and products directory.
- Produces: `${version}__${product}__${dimension}.json` files matching the existing merge job contract.
- Matrix row: `{"product": str, "framework_versions": list[str]}`.

- [ ] **Step 1: Write failing matrix and batch tests**

Assert selected versions are grouped into one row per product, version membership respects lifecycle boundaries, batch output filenames retain the existing routing shape, and identical runners across versions execute once.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest --tb=short engine/__tests__/test_workflow_matrix.py engine/__tests__/test_workflows.py scorers/__tests__/test_batch.py -q`

Expected: FAIL because rows are version/product pairs and no batch scorer exists.

- [ ] **Step 3: Implement grouped rows and batch scorer**

Group versions per product in sequence order. In `scorers.batch`, build the version-specific graph and contract for each version, resolve leaf units, invoke each dimension with one shared cache, and write the existing artifact filenames.

- [ ] **Step 4: Wire the workflow**

Flatten `framework_versions` to compute the `versions` job output. Pass the row's JSON version list to `python -m scorers.batch`, and upload one uniquely named artifact per product.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest --tb=short engine/__tests__/test_workflow_matrix.py engine/__tests__/test_workflows.py scorers/__tests__/test_batch.py -q`

Expected: PASS.

### Task 4: Fail closed on required GitHub acquisition

**Files:**
- Modify: `scorers/shared/github_signals.py`
- Modify: `scorers/engagement/logic.py`
- Modify: `scorers/substrate_compat/logic.py`
- Modify: corresponding scorer tests.

**Interfaces:**
- Produces: an explicit acquisition exception for exhausted/rate-limited list and file reads after authenticated-to-anonymous fallback.

- [ ] **Step 1: Write failing acquisition tests**

Assert a final 403/429 response for engagement issue/PR pagination and substrate workflow listing raises an explicit exception rather than returning empty/false measurements. Preserve valid 404 semantics for absent optional files/directories.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest --tb=short scorers/engagement/__tests__/test_logic.py scorers/substrate_compat/__tests__/test_logic.py -q`

Expected: FAIL because final errors are still converted to empty evidence.

- [ ] **Step 3: Implement explicit failure**

Raise the shared acquisition exception only for responses that mean evidence could not be acquired; retain valid absence handling.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest --tb=short scorers/engagement/__tests__/test_logic.py scorers/substrate_compat/__tests__/test_logic.py -q`

Expected: PASS.

#### Final review evidence

- RED: the required-acquisition regression matrix produced 24 expected failures for
  400/405/422 responses across pagination, topics, workflow listing/files, Jira, comments, and
  reviews.
- GREEN: required GitHub acquisition now raises `GitHubAcquisitionError` for every unsuccessful
  final response. Workflow-directory 404 and Jira-config 404 remain contextual valid absences.
- Optional traffic responses remain non-fatal and return `None`; exception messages include only
  status and URL, preserving response-body and token redaction.

### Task 5: End-to-end verification and preview

**Files:**
- Verify all modified files.

**Interfaces:**
- Produces: a green PR workflow and a preview whose portfolios are generated from the branch head without universal insufficient-data regressions.

- [ ] **Step 1: Run repository checks**

Run: `make validate && make lint && make format-check && make test`

Expected: all commands exit 0.

- [ ] **Step 2: Push the branch and monitor PR #33**

Run the compute workflow through the PR synchronization event and wait for completion.

- [ ] **Step 3: Verify published evidence**

Fetch both preview portfolios, verify their `source_revision`, inspect engagement/substrate distributions, and confirm the preview URL returns HTTP 200.
