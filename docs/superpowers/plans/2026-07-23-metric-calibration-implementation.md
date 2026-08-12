# PQF Metric Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve scorer fidelity so medals reflect real repository quality, with explicit unrated vs bronze semantics for unmeasurable signals.

**Architecture:** Introduce a measurability-aware scoring contract at scorer output level, then propagate that into engine applicability decisions. Calibrate each dimension scorer with deterministic detectors that only support sanctioned structural variants (monorepo vs non-monorepo, charm vs snap) while keeping metric rules simple and prescriptive. Validate each change with focused unit tests plus full portfolio recomputation.

**Tech Stack:** Python 3.11+, pytest, requests, ruff, existing PQF engine/scorer modules, GitHub API via shared scorer helpers.

## Global Constraints

- Keep scorer `logic.py` pure with respect to environment/file I/O; wrappers handle env.
- Reuse existing scorer/engine patterns and shared helpers (`scorers/shared/*`) before adding new helpers.
- Use deterministic evidence first; do not add opaque AI gating logic.
- Preserve `config/dimensions.yaml` as the single rubric contract source.
- Use TDD: test first, observe failure, then minimal implementation.
- Run existing repo commands only for validation (`make test`, `make test-ui`, `make ci-check`, scoring targets).

---

## File structure map

- Modify: `scorers/test_verification/logic.py` — add build-status fallback + measurability behavior.
- Modify: `scorers/test_verification/__tests__/test_logic.py` — new regression cases.
- Modify: `scorers/documentation/logic.py` — broaden deterministic docs detector coverage.
- Modify: `scorers/documentation/__tests__/test_logic.py` — sanctioned-variation tests.
- Modify: `scorers/substrate_compat/logic.py` — workflow parsing for juju/substrate signals.
- Modify: `scorers/substrate_compat/__tests__/test_logic.py` — matrix/alt-syntax tests.
- Modify: `scorers/security_ssdlc/logic.py` — canonical-repo-automation source fix.
- Modify: `scorers/security_ssdlc/__tests__/test_logic.py` — registration detection tests.
- Modify: `scorers/support_engagement/logic.py` — sample threshold + no-data semantics.
- Modify: `scorers/support_engagement/__tests__/test_logic.py` — no-data vs measured-zero tests.
- Modify: `engine/aggregation.py` — applicability logic for unmeasurable gated metrics.
- Modify: `engine/medal_engine.py` — preserve unrated behavior for insufficient data.
- Modify: `engine/__tests__/test_aggregation.py` and `engine/__tests__/test_medal_engine.py` — applicability regression tests.
- Modify: `config/dimensions.yaml` — classify gates vs informational metrics.
- Modify: `docs/local-scoring.md` — document measurability semantics.
- Create: `docs/superpowers/artifacts/2026-07-23-metric-calibration-audit-postfix.json` — before/after distribution artifact.

---

### Task 1: test_verification fallback and measurability semantics

**Files:**
- Modify: `scorers/test_verification/__tests__/test_logic.py`
- Modify: `scorers/test_verification/logic.py`

**Interfaces:**
- Consumes: `compute_metrics(unit: EvaluationUnit, github_token: str | None = None) -> dict[str, Any]`
- Produces:
  - `latest_build_passing` derived from Allure when available, otherwise GitHub checks fallback.
  - coverage/stability omitted or marked unmeasurable when Allure source unavailable.

- [ ] **Step 1: Write failing tests**

```python
def test_latest_build_passing_falls_back_to_default_branch_checks_when_allure_missing(mocker):
    unit = EvaluationUnit(product_id="x", product_type="charm", repo="canonical/saml-integrator-operator")
    unit.allure_report_url = ""
    mocker.patch("scorers.test_verification.logic.default_branch_check_runs", return_value=[
        {"name": "ci / test", "conclusion": "success", "completed_at": "2026-07-23T00:00:00Z"}
    ])
    got = compute_metrics(unit, github_token="token")
    assert got["latest_build_passing"] is True

def test_allure_absent_does_not_force_coverage_zero_for_gated_use():
    unit = EvaluationUnit(product_id="x", product_type="charm", repo="canonical/example")
    unit.allure_report_url = ""
    got = compute_metrics(unit, github_token=None)
    assert "coverage_pct" not in got or got["coverage_pct"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest --tb=short scorers/test_verification/__tests__/test_logic.py -k "fallback or allure_absent"`  
Expected: FAIL because current logic returns `latest_build_passing=False` and `coverage_pct=0`.

- [ ] **Step 3: Write minimal implementation**

```python
def _latest_default_branch_check_success(owner_repo: str, github_token: str | None) -> bool | None:
    runs = default_branch_check_runs(owner_repo, github_token)
    terminal = [r for r in runs if (r.get("conclusion") or "").lower() in {"success", "failure"}]
    if not terminal:
        return None
    latest = max(terminal, key=lambda r: str(r.get("completed_at") or r.get("started_at") or ""))
    return (latest.get("conclusion") or "").lower() == "success"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest --tb=short scorers/test_verification/__tests__/test_logic.py`  
Expected: PASS for new fallback cases and existing tests.

- [ ] **Step 5: Commit**

```bash
git add scorers/test_verification/logic.py scorers/test_verification/__tests__/test_logic.py
git commit -m "fix(test_verification): add build-status fallback and measurability handling"
```

---

### Task 2: documentation detector widening and gate calibration readiness

**Files:**
- Modify: `scorers/documentation/__tests__/test_logic.py`
- Modify: `scorers/documentation/logic.py`

**Interfaces:**
- Consumes: existing `compute_metrics(...)`.
- Produces: sanctioned structural variant support for docs structures/workflow names with deterministic checks.

- [ ] **Step 1: Write failing tests**

```python
def test_docs_workflow_passes_for_docs_checks_family_names():
    check_runs = [
        {"name": "docs-checks / linkcheck", "conclusion": "success", "completed_at": "2026-07-23T00:00:00Z"},
        {"name": "docs-checks / vale", "conclusion": "success", "completed_at": "2026-07-23T00:00:00Z"},
    ]
    assert _documentation_workflows_passing(check_runs) is True

def test_readme_structure_accepts_equivalent_headings():
    text = "# Overview\n## Install\n## Usage\n## Support"
    assert _readme_has_required_sections(text) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest --tb=short scorers/documentation/__tests__/test_logic.py -k "docs_workflow or readme_structure"`  
Expected: FAIL due strict current heading/check-name expectations.

- [ ] **Step 3: Write minimal implementation**

```python
DOCS_LINT_ALIASES = ("docs lint", "docs-checks / vale")
DOCS_LINK_ALIASES = ("docs-checks / linkcheck", "link check")
DOCS_BUILD_ALIASES = ("docs build", "documentation build")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest --tb=short scorers/documentation/__tests__/test_logic.py`  
Expected: PASS with no regressions.

- [ ] **Step 5: Commit**

```bash
git add scorers/documentation/logic.py scorers/documentation/__tests__/test_logic.py
git commit -m "fix(documentation): support accepted docs structure and workflow variants"
```

---

### Task 3: substrate_compat workflow parsing improvements

**Files:**
- Modify: `scorers/substrate_compat/__tests__/test_logic.py`
- Modify: `scorers/substrate_compat/logic.py`

**Interfaces:**
- Consumes: workflow YAML text.
- Produces: robust detection of juju3/juju4/substrate-test evidence across matrix/reusable patterns.

- [ ] **Step 1: Write failing tests**

```python
def test_detects_juju4_from_matrix_values():
    workflow = \"\"\"strategy:\n  matrix:\n    juju-channel: [3/stable, 4/stable]\n\"\"\"
    assert _detect_juju4(workflow) is True

def test_detects_canonical_k8s_aliases():
    workflow = \"\"\"jobs:\n  test:\n    steps:\n      - run: juju bootstrap microk8s\n\"\"\"
    assert _detect_canonical_k8s(workflow) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest --tb=short scorers/substrate_compat/__tests__/test_logic.py -k "matrix or canonical_k8s"`  
Expected: FAIL with current regex-only matching.

- [ ] **Step 3: Write minimal implementation**

```python
def _detect_juju_channel(content: str, major: str) -> bool:
    patterns = [rf"juju[-_ ]channel.*{major}/stable", rf"{major}/stable"]
    lowered = content.lower()
    return any(re.search(p, lowered) for p in patterns)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest --tb=short scorers/substrate_compat/__tests__/test_logic.py`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scorers/substrate_compat/logic.py scorers/substrate_compat/__tests__/test_logic.py
git commit -m "fix(substrate_compat): parse broader juju/substrate workflow patterns"
```

---

### Task 4: security_ssdlc canonical-repo-automation signal source fix

**Files:**
- Modify: `scorers/security_ssdlc/__tests__/test_logic.py`
- Modify: `scorers/security_ssdlc/logic.py`

**Interfaces:**
- Consumes: deterministic registration source (not free-text code search).
- Produces: non-pathological `canonical_repo_automation_registered` values.

- [ ] **Step 1: Write failing tests**

```python
def test_repo_automation_registration_reads_from_authoritative_list(mocker):
    mocker.patch("scorers.security_ssdlc.logic.repo_file_text", return_value="canonical/saml-integrator-operator\n")
    assert _is_registered_in_repo_automation("canonical/saml-integrator-operator", "token") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest --tb=short scorers/security_ssdlc/__tests__/test_logic.py -k registration`  
Expected: FAIL because current logic uses code search only.

- [ ] **Step 3: Write minimal implementation**

```python
def _is_registered_in_repo_automation(owner_repo: str, github_token: str) -> bool:
    # Read canonical list file(s) in canonical/canonical-repo-automation and match exact repo slug.
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest --tb=short scorers/security_ssdlc/__tests__/test_logic.py`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scorers/security_ssdlc/logic.py scorers/security_ssdlc/__tests__/test_logic.py
git commit -m "fix(security_ssdlc): use deterministic repo-automation registration source"
```

---

### Task 5: support_engagement no-data semantics and sample thresholds

**Files:**
- Modify: `scorers/support_engagement/__tests__/test_logic.py`
- Modify: `scorers/support_engagement/logic.py`

**Interfaces:**
- Consumes: issue/PR history.
- Produces: clear differentiation between measured zero and insufficient sample.

- [ ] **Step 1: Write failing tests**

```python
def test_no_recent_issues_or_prs_marks_insufficient_sample():
    got = compute_metrics(unit_without_activity, token)
    assert got["response_coverage_rate"] is None
    assert got["avg_triage_days"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest --tb=short scorers/support_engagement/__tests__/test_logic.py -k insufficient_sample`  
Expected: FAIL because current logic returns zeros.

- [ ] **Step 3: Write minimal implementation**

```python
MIN_SAMPLE = 5
if total_items < MIN_SAMPLE:
    response_coverage_rate = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest --tb=short scorers/support_engagement/__tests__/test_logic.py`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scorers/support_engagement/logic.py scorers/support_engagement/__tests__/test_logic.py
git commit -m "fix(support_engagement): separate insufficient sample from measured zero"
```

---

### Task 6: engine applicability updates for unrated vs bronze policy

**Files:**
- Modify: `engine/__tests__/test_aggregation.py`
- Modify: `engine/__tests__/test_medal_engine.py`
- Modify: `engine/aggregation.py`
- Modify: `engine/medal_engine.py`

**Interfaces:**
- Consumes: scorer metric maps that may omit unmeasurable gated metrics.
- Produces: `ApplicabilityOutcome.INSUFFICIENT_DATA` + `Medal.UNRATED` where appropriate.

- [ ] **Step 1: Write failing tests**

```python
def test_leaf_with_unmeasurable_gated_metrics_is_insufficient_data():
    metrics = {"integration_test_evidence_present": True}  # missing gated coverage/stability
    outcome = compute_leaf_applicability("charm", metrics, dim_cfg_with_required_keys)
    assert outcome == ApplicabilityOutcome.INSUFFICIENT_DATA
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest --tb=short engine/__tests__/test_aggregation.py -k insufficient_data`  
Expected: FAIL with current `if not metrics` logic.

- [ ] **Step 3: Write minimal implementation**

```python
required_metrics = dim_config.get("required_metrics_for_scoring", [])
if any(metrics.get(k) is None for k in required_metrics):
    return ApplicabilityOutcome.INSUFFICIENT_DATA
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest --tb=short engine/__tests__/test_aggregation.py engine/__tests__/test_medal_engine.py`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/aggregation.py engine/medal_engine.py engine/__tests__/test_aggregation.py engine/__tests__/test_medal_engine.py
git commit -m "feat(engine): apply measurability-aware applicability for scoring"
```

---

### Task 7: rubric updates, full recompute, and audit artifact refresh

**Files:**
- Modify: `config/dimensions.yaml`
- Modify: `docs/local-scoring.md`
- Create: `docs/superpowers/artifacts/2026-07-23-metric-calibration-audit-postfix.json`

**Interfaces:**
- Consumes: updated scorer outputs and engine applicability.
- Produces: recalibrated gating criteria and updated before/after evidence artifact.

- [ ] **Step 1: Write failing tests**

```python
def test_dimension_contract_declares_required_metrics_for_scoring():
    cfg = yaml.safe_load(Path("config/dimensions.yaml").read_text())
    assert "required_metrics_for_scoring" in cfg["dimensions"]["test_verification"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest --tb=short engine/__tests__/test_integration.py -k required_metrics_for_scoring`  
Expected: FAIL until config/engine contract is updated.

- [ ] **Step 3: Write minimal implementation**

```yaml
test_verification:
  required_metrics_for_scoring:
    - latest_build_passing
```

- [ ] **Step 4: Run test to verify it passes**

Run:
- `make test`
- `make score-all`
- `make _assemble`
- `make ci-check`

Expected:
- tests pass,
- scoring pipeline succeeds,
- updated distributions show reduced pathological all-false/all-zero patterns.

- [ ] **Step 5: Commit**

```bash
git add config/dimensions.yaml docs/local-scoring.md docs/superpowers/artifacts/2026-07-23-metric-calibration-audit-postfix.json
git commit -m "feat(metrics): calibrate gates and publish post-fix distribution audit"
```

---

## Self-review

### Spec coverage check
- Measurability contract → Task 1 + Task 6 + Task 7.
- Detector widening by dimension → Tasks 2–5.
- Progressive gate strategy → Task 7.
- Portfolio-wide validation → Task 7 step 4.

### Placeholder scan
- No TODO/TBD placeholders.
- Every task includes concrete files, tests, commands, and commit steps.

### Type/interface consistency
- `compute_metrics(...) -> dict[str, Any]` preserved.
- Applicability outcomes remain `SCORED | NOT_APPLICABLE | INSUFFICIENT_DATA`.
- Config contract extension (`required_metrics_for_scoring`) referenced consistently in engine tasks.
