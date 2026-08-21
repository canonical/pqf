# Documentation + SSDLC Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calibrate documentation and SSDLC scoring so medals rely on high-confidence deterministic signals, while exposing one AI-assisted informational documentation metric.

**Architecture:** Keep existing scorer entrypoints and data flow, and refine metrics in-place in `scorers/documentation/logic.py`, `scorers/security_ssdlc/logic.py`, and `config/dimensions.yaml`. Replace weak release-notes inference with process evidence, remove tutorial-testing, add signed-commit detection, and reintroduce AI Diataxis via the existing OpenRouter inputs already passed into documentation scoring. Validate with targeted scorer tests plus config/integration checks.

**Tech Stack:** Python 3.11, pytest, pytest-mock, OpenAI Python client (`openai`), GitHub REST signals, Makefile test targets.

## Global Constraints

- Keep medal/status propagation canonical in engine outputs; no UI-only conditional behavior.
- Documentation bronze remains baseline presence (`readme_present`, `contributing_present`, `has_security`).
- `uses_rtd_hosting` remains informational-only and does not gate medals.
- AI Diataxis is informational-only at launch (showcase metric, non-gating).
- Remove `tutorial_tested` from scorer output, config outputs, and tests.
- SSDLC must use Renovate (not Dependabot) conventions already in repo.
- Reuse existing scorer patterns and shared GitHub signal helpers; do not introduce new external tooling.

---

### Task 1: Rework documentation metric contract and medal gating

**Files:**
- Modify: `config/dimensions.yaml`
- Modify: `scorers/documentation/logic.py`
- Modify: `scorers/documentation/__tests__/test_logic.py`

**Interfaces:**
- Consumes: `compute_metrics(unit: EvaluationUnit, github_token: str, openrouter_api_key: str, model: str = ...) -> dict[str, Any]`
- Produces metric keys: `readme_present`, `contributing_present`, `has_security`, `documentation_workflows_passing`, `diataxis_coverage_ai`, `uses_rtd_hosting`, `release_notes_process_implemented`
- Produces rubric: bronze/silver/gold for documentation in `config/dimensions.yaml`

- [ ] **Step 1: Write failing tests for renamed/removed documentation metrics**

Update `scorers/documentation/__tests__/test_logic.py` expectations:

```python
assert result == {
    "readme_present": False,
    "contributing_present": False,
    "has_security": False,
    "documentation_workflows_passing": False,
    "diataxis_coverage_ai": 0,
    "uses_rtd_hosting": False,
    "release_notes_process_implemented": False,
}
```

Add an explicit regression that removed keys are absent:

```python
assert "tutorial_tested" not in result
assert "recent_release_notes_present" not in result
assert "diataxis_coverage" not in result
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py -v
```

Expected: FAIL with missing renamed keys and/or stale `tutorial_tested` expectations.

- [ ] **Step 3: Implement contract changes in scorer and config**

In `scorers/documentation/logic.py`, update the returned metrics shape:

```python
return {
    "readme_present": _readme_present(unit, github_token),
    "contributing_present": _contributing_present(unit, github_token),
    "has_security": _file_exists(unit, "SECURITY.md", github_token),
    "documentation_workflows_passing": _documentation_workflows_passing(check_runs),
    "diataxis_coverage_ai": _diataxis_coverage_ai(
        unit, github_token, openrouter_api_key, model=model
    ),
    "uses_rtd_hosting": _uses_rtd_hosting(unit, github_token),
    "release_notes_process_implemented": _release_notes_process_implemented(
        unit, github_token
    ),
}
```

In `config/dimensions.yaml`, update documentation outputs and medals:

```yaml
documentation:
  outputs:
    diataxis_coverage_ai: {type: number, range: "0–4", label: "Diátaxis coverage (AI)", description: "AI-assisted Diátaxis assessment (informational).", informational: true}
    uses_rtd_hosting: {type: boolean, label: "Uses RTD hosting", description: "Documentation points at a Read the Docs host.", informational: true}
    release_notes_process_implemented: {type: boolean, label: "Release notes process implemented", description: "Repository has canonical release-notes workflow + structure evidence."}
  medals:
    bronze: ["readme_present == true", "contributing_present == true", "has_security == true"]
    silver: ["readme_present == true", "contributing_present == true", "has_security == true", "release_notes_process_implemented == true"]
    gold: ["readme_present == true", "contributing_present == true", "has_security == true", "release_notes_process_implemented == true", "documentation_workflows_passing == true"]
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py -v
```

Expected: PASS with updated metric names and removed tutorial signal.

- [ ] **Step 5: Commit**

```bash
git add config/dimensions.yaml scorers/documentation/logic.py scorers/documentation/__tests__/test_logic.py
git commit -m "feat(documentation): recalibrate metric contract and medal tiers"
```

### Task 2: Tighten release-notes process detection to canonical workflow evidence

**Files:**
- Modify: `scorers/documentation/logic.py`
- Modify: `scorers/documentation/__tests__/test_logic.py`

**Interfaces:**
- Produces: `_release_notes_process_implemented(unit: EvaluationUnit, github_token: str | None) -> bool`
- Consumes: `workflow_files(owner_repo, github_token)`, `repo_file_exists`, `repo_releases`

- [ ] **Step 1: Write failing tests for workflow + structure evidence**

Add tests in `scorers/documentation/__tests__/test_logic.py`:

```python
def test_release_notes_process_requires_canonical_workflow_and_structure(mocker):
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path in {
            "docs/release-notes/common.yaml",
            "docs/release-notes/releases/release0001.yaml",
            "docs/release-notes/template/release-template.md.j2",
        },
    )
    mocker.patch(
        "scorers.documentation.logic.workflow_files",
        return_value=[("release-notes.yaml", "uses: canonical/release-notes-automation/.github/workflows/action.yml@main")],
    )
    mocker.patch(
        "scorers.documentation.logic.repo_releases",
        return_value=[{"draft": False, "body": "notes 1"}, {"draft": False, "body": "notes 2"}],
    )
    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["release_notes_process_implemented"] is True
```

And negative case:

```python
def test_release_notes_process_fails_without_workflow_reference(mocker):
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=True)
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[("ci.yaml", "name: CI")])
    mocker.patch(
        "scorers.documentation.logic.repo_releases",
        return_value=[{"draft": False, "body": "notes 1"}, {"draft": False, "body": "notes 2"}],
    )
    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["release_notes_process_implemented"] is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py::test_release_notes_process_requires_canonical_workflow_and_structure scorers/documentation/__tests__/test_logic.py::test_release_notes_process_fails_without_workflow_reference -v
```

Expected: FAIL because current logic does not require workflow references.

- [ ] **Step 3: Implement canonical release-notes detection**

In `scorers/documentation/logic.py`, replace `_recent_release_notes_present` with:

```python
def _release_notes_process_implemented(unit: EvaluationUnit, github_token: str | None) -> bool:
    required_structure = (
        "docs/release-notes/common.yaml",
        "docs/release-notes/releases",
        "docs/release-notes/template",
    )
    has_structure = (
        _file_exists(unit, required_structure[0], github_token)
        and _file_exists(unit, required_structure[1], github_token)
        and _file_exists(unit, required_structure[2], github_token)
    )
    if not has_structure:
        return False

    workflow_texts = [content.lower() for _, content in workflow_files(unit.repo, github_token)]
    has_generation_workflow = any(
        "canonical/release-notes-automation/.github/workflows/action.yml" in text
        for text in workflow_texts
    )
    if not has_generation_workflow:
        return False

    non_draft = [r for r in repo_releases(unit.repo, github_token) if not r.get("draft", False)]
    if len(non_draft) < 2:
        return False
    latest_two = sorted(
        non_draft,
        key=lambda r: str(r.get("published_at") or r.get("created_at") or r.get("tag_name") or ""),
        reverse=True,
    )[:2]
    return all(str(rel.get("body", "")).strip() for rel in latest_two)
```

Also update imports at top:

```python
from scorers.shared.github_signals import (
    default_branch_check_runs,
    repo_file_exists,
    repo_file_text,
    repo_releases,
    workflow_files,
)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py -v
```

Expected: PASS for release-notes positive/negative cases with deterministic workflow evidence.

- [ ] **Step 5: Commit**

```bash
git add scorers/documentation/logic.py scorers/documentation/__tests__/test_logic.py
git commit -m "feat(documentation): require canonical release-notes process evidence"
```

### Task 3: Reintroduce AI-assisted Diataxis informational metric

**Files:**
- Modify: `scorers/documentation/logic.py`
- Modify: `scorers/documentation/__tests__/test_logic.py`
- Modify: `config/dimensions.yaml`

**Interfaces:**
- Produces: `_diataxis_coverage_ai(unit, github_token, openrouter_api_key, model) -> int`
- Consumes: prompt file `scorers/documentation/prompts/diataxis_check.md`
- Uses OpenRouter-compatible client: `OpenAI(api_key=openrouter_api_key, base_url="https://openrouter.ai/api/v1")`

- [ ] **Step 1: Write failing AI-metric tests**

Add tests in `scorers/documentation/__tests__/test_logic.py`:

```python
def test_diataxis_ai_metric_uses_openrouter_result(mocker):
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.return_value = mocker.Mock(
        choices=[mocker.Mock(message=mocker.Mock(content='{"diataxis_coverage": 3, "reasoning": "has 3 types"}'))]
    )
    mocker.patch("scorers.documentation.logic.OpenAI", return_value=fake_client)
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="# Docs")
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=True)
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")
    assert result["diataxis_coverage_ai"] == 3
```

And failure-safe informational fallback:

```python
def test_diataxis_ai_metric_falls_back_to_zero_when_api_key_missing(mocker):
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "", model="openrouter/test-model")
    assert result["diataxis_coverage_ai"] == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py::test_diataxis_ai_metric_uses_openrouter_result scorers/documentation/__tests__/test_logic.py::test_diataxis_ai_metric_falls_back_to_zero_when_api_key_missing -v
```

Expected: FAIL because AI helper does not exist yet.

- [ ] **Step 3: Implement AI Diataxis scoring helper**

In `scorers/documentation/logic.py`, add imports:

```python
import json
from openai import OpenAI
```

Add helper:

```python
def _diataxis_coverage_ai(
    unit: EvaluationUnit,
    github_token: str | None,
    openrouter_api_key: str,
    model: str,
) -> int:
    if not openrouter_api_key:
        return 0

    prompt = (_PROMPTS_DIR / "diataxis_check.md").read_text()
    readme = _file_text(unit, "README.md", github_token)
    docs_index = _file_text(unit, "docs/index.md", github_token)
    payload = f"{prompt}\n\nRepository context:\nREADME:\n{readme}\n\ndocs/index.md:\n{docs_index}"

    client = OpenAI(api_key=openrouter_api_key, base_url="https://openrouter.ai/api/v1")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": payload}],
    )
    raw = response.choices[0].message.content or "{}"
    parsed = json.loads(raw)
    value = int(parsed.get("diataxis_coverage", 0))
    return max(0, min(4, value))
```

Use helper in `compute_metrics()` and ensure `diataxis_coverage_ai` output is marked `informational: true` in `config/dimensions.yaml`.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py -v
```

Expected: PASS with deterministic fallback (`0`) and AI response parse path.

- [ ] **Step 5: Commit**

```bash
git add scorers/documentation/logic.py scorers/documentation/__tests__/test_logic.py config/dimensions.yaml
git commit -m "feat(documentation): add AI-assisted diataxis informational metric"
```

### Task 4: Add SSDLC signed-commit metric and recalibrate tier gates

**Files:**
- Modify: `scorers/security_ssdlc/logic.py`
- Modify: `scorers/security_ssdlc/__tests__/test_logic.py`
- Modify: `config/dimensions.yaml`
- Modify: `engine/__tests__/test_integration.py`

**Interfaces:**
- Produces: `_has_signed_commits_required(owner_repo: str, github_token: str) -> bool`
- Produces metric key: `signed_commits_required`
- Updates security_ssdlc medals: bronze/silver/gold to include signed commits at gold

- [ ] **Step 1: Write failing signed-commit tests**

Add to `scorers/security_ssdlc/__tests__/test_logic.py`:

```python
def test_signed_commits_required_true(mocker):
    def fake_github_get(url, token, accept=None):
        if url.endswith("/repos/canonical/test-repo"):
            return _Response(True, {"default_branch": "main"})
        if url.endswith("/branches/main/protection"):
            return _Response(
                True,
                {
                    "required_status_checks": {"contexts": ["ci/test"], "checks": []},
                    "required_signatures": {"enabled": True},
                },
            )
        return _Response(False, {})

    mocker.patch("scorers.security_ssdlc.logic.github_get", side_effect=fake_github_get)
    result = compute_metrics(UNIT, "token")
    assert result["signed_commits_required"] is True
```

And false case:

```python
def test_signed_commits_required_false_when_not_configured(mocker):
    def fake_github_get(url, token, accept=None):
        if url.endswith("/repos/canonical/test-repo"):
            return _Response(True, {"default_branch": "main"})
        if url.endswith("/branches/main/protection"):
            return _Response(True, {"required_status_checks": {"contexts": ["ci"], "checks": []}})
        return _Response(False, {})

    mocker.patch("scorers.security_ssdlc.logic.github_get", side_effect=fake_github_get)
    result = compute_metrics(UNIT, "token")
    assert result["signed_commits_required"] is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest scorers/security_ssdlc/__tests__/test_logic.py -v
```

Expected: FAIL because `signed_commits_required` is not yet produced.

- [ ] **Step 3: Implement metric and tier updates**

In `scorers/security_ssdlc/logic.py`, add:

```python
def _has_signed_commits_required(owner_repo: str, github_token: str) -> bool:
    repo_resp = github_get(f"{_GITHUB_API}/repos/{owner_repo}", github_token)
    if not repo_resp.ok:
        return False
    default_branch = repo_resp.json().get("default_branch", "main")
    prot_resp = github_get(
        f"{_GITHUB_API}/repos/{owner_repo}/branches/{default_branch}/protection",
        github_token,
    )
    if not prot_resp.ok:
        return False
    signatures = prot_resp.json().get("required_signatures", {})
    return bool(signatures.get("enabled", False))
```

Include in `compute_metrics()`:

```python
signed_commits_required = (
    _has_signed_commits_required(unit.repo, github_token) if unit.repo else False
)

return {
    "renovate_enabled": renovate_enabled,
    "canonical_repo_automation_registered": canonical_repo_automation_registered,
    "branch_protection_required_checks": branch_protection,
    "signed_commits_required": signed_commits_required,
    "sast_workflow_present": sast_workflow_present,
    "cve_tracking_process_present": cve_tracking_process_present,
}
```

In `config/dimensions.yaml` update outputs + tiers:

```yaml
security_ssdlc:
  outputs:
    signed_commits_required: {type: boolean, label: "Signed commits required", description: "Default branch protection enforces signed commits."}
  medals:
    bronze: ["renovate_enabled == true", "canonical_repo_automation_registered == true"]
    silver: ["renovate_enabled == true", "canonical_repo_automation_registered == true", "branch_protection_required_checks == true"]
    gold: ["renovate_enabled == true", "canonical_repo_automation_registered == true", "branch_protection_required_checks == true", "signed_commits_required == true", "sast_workflow_present == true", "cve_tracking_process_present == true"]
```

Update any fixture assertions in `engine/__tests__/test_integration.py` that enumerate SSDLC metric keys.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest scorers/security_ssdlc/__tests__/test_logic.py engine/__tests__/test_integration.py -v
```

Expected: PASS with signed-commit metric included and config assertions updated.

- [ ] **Step 5: Commit**

```bash
git add scorers/security_ssdlc/logic.py scorers/security_ssdlc/__tests__/test_logic.py config/dimensions.yaml engine/__tests__/test_integration.py
git commit -m "feat(ssdlc): add signed-commit metric and recalibrate tiers"
```

### Task 5: End-to-end calibration verification

**Files:**
- Modify: `docs/local-scoring.md`

**Interfaces:**
- Consumes: updated documentation + SSDLC metric schema and medal tiers
- Produces: contributor guidance aligned with the new calibrated contract

- [ ] **Step 1: Define the docs validation gate**

Use scorer/config tests as the quality gate for this docs update (the repository does not define a dedicated docs test target for `docs/local-scoring.md`).

- [ ] **Step 2: Run targeted test suite for both scorers**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py scorers/security_ssdlc/__tests__/test_logic.py engine/__tests__/test_integration.py -v
```

Expected: PASS (if still failing, return to prior tasks before editing docs).

- [ ] **Step 3: Update local scoring guide for new metric names**

In `docs/local-scoring.md`, update documentation and SSDLC sections to reflect:

```md
- Documentation medals:
  - Bronze: readme_present + contributing_present + has_security
  - Silver: Bronze + release_notes_process_implemented
  - Gold: Silver + documentation_workflows_passing
  - Informational: uses_rtd_hosting, diataxis_coverage_ai

- SSDLC medals:
  - Bronze: renovate_enabled + canonical_repo_automation_registered
  - Silver: Bronze + branch_protection_required_checks
  - Gold: Silver + signed_commits_required + sast_workflow_present + cve_tracking_process_present
```

- [ ] **Step 4: Run final validation command**

Run:

```bash
make test
```

Expected: PASS for full Python test suite.

- [ ] **Step 5: Commit**

```bash
git add docs/local-scoring.md
git commit -m "docs: update local scoring guide for docs and SSDLC calibration"
```
