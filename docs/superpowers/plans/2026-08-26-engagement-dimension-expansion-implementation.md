# Engagement Dimension Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename PQF's `support_engagement` dimension to `engagement`, keep medal gating based on maintainer responsiveness, and add an informational GitHub traffic metric `repo_views_14d`.

**Architecture:** Update the dimension contract and scorer package name first so the repo consistently speaks in terms of `engagement`. Then extend the scorer's GitHub IO path with a small `traffic/views` fetch that returns `null` when unavailable without affecting measurability gates. Finally, normalize legacy drift-history keys during portfolio assembly so remediation continuity survives the rename.

**Tech Stack:** Python 3, requests, PyYAML, pytest, responses, GitHub Actions YAML, Makefile-driven validation

## Global Constraints

- Preserve the scorer pure/IO split: `logic.py` contains deterministic computation; `scorer.py` remains the environment-reading wrapper.
- `config/dimensions.yaml` is the single scorer contract; the renamed scorer must emit exactly the configured outputs.
- `repo_views_14d` is informational only: do not add it to `required_metrics_for_scoring` or any bronze/silver/gold criteria.
- GitHub traffic must come from `GET /repos/{owner}/{repo}/traffic/views`; the API only exposes the last 14 days and requires repository write access.
- Missing traffic data must surface as `null`, not `0`, and must never force `insufficient_data`.
- Preserve drift continuity by migrating legacy `support_engagement` drift-history entries to `engagement`.
- Never hand-edit `computed/` or `public/portfolio.json`; only regenerate them with existing make targets for verification.
- Use existing commands only: `make test`, `make build`, `make score-no-llm PRODUCT=<id>`, `make _merge PRODUCT=<id>`, `make _assemble`.
- Update directly related docs when the public name or metric contract changes: `README.md`, `AGENTS.md`, and `docs/local-scoring.md`.

## File Structure Map

| Path | Responsibility |
| --- | --- |
| `config/dimensions.yaml` | Rename the dimension key/metadata and add the informational `repo_views_14d` output contract. |
| `scorers/engagement/logic.py` | Compute maintainer responsiveness metrics plus `repo_views_14d` from GitHub traffic. |
| `scorers/engagement/scorer.py` | Leaf-product wrapper using the renamed scorer package. |
| `scorers/engagement/__tests__/test_logic.py` | Unit tests for rename continuity and traffic metric behavior. |
| `engine/assemble.py` | Normalize legacy drift-history keys before assembling the portfolio. |
| `engine/__tests__/test_assemble.py` | Unit tests for drift-history migration. |
| `engine/__tests__/test_integration.py` | Contract-level integration test covering the renamed dimension and new optional metric. |
| `Makefile` | Route local scoring output through `engagement.json` and the renamed scorer path. |
| `.github/workflows/compute-metrics.yml` | Run the renamed scorer and emit `/tmp/scorers/.../engagement.json`. |
| `README.md` | Update the top-level dimension list to `engagement`. |
| `AGENTS.md` | Update the contributor guide's dimension table to the new name and metric set. |
| `docs/local-scoring.md` | Update scorer/measurability guidance to refer to `engagement`. |

---

### Task 1: Rename the dimension contract and package references

**Files:**
- Create: `scorers/engagement/__init__.py`
- Create: `scorers/engagement/logic.py`
- Create: `scorers/engagement/scorer.py`
- Create: `scorers/engagement/__tests__/__init__.py`
- Create: `scorers/engagement/__tests__/test_logic.py`
- Modify: `config/dimensions.yaml`
- Modify: `engine/__tests__/test_integration.py`
- Modify: `Makefile`
- Modify: `.github/workflows/compute-metrics.yml`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/local-scoring.md`
- Delete: `scorers/support_engagement/__init__.py`
- Delete: `scorers/support_engagement/logic.py`
- Delete: `scorers/support_engagement/scorer.py`
- Delete: `scorers/support_engagement/__tests__/__init__.py`
- Delete: `scorers/support_engagement/__tests__/test_logic.py`

**Interfaces:**
- Consumes: existing `compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]` scorer contract.
- Produces:
  - dimension key `engagement` in `config/dimensions.yaml`,
  - scorer path `scorers/engagement/scorer.py`,
  - scorer output file `.pqf-score/<product>/engagement.json`,
  - integration fixture dimension key `engagement`.

- [ ] **Step 1: Write the failing contract test**

Update `engine/__tests__/test_integration.py` so the fixture and assertions expect `engagement` instead of `support_engagement`:

```python
_FIXTURE_COMPUTED = {
    "product_id": "matrix",
    "computed_at": "2026-06-29T20:00:00+00:00",
    "metrics": {
        # ...
        "engagement": {
            "avg_triage_days": 3.0,
            "avg_pr_review_days": 4.0,
            "response_coverage_rate": 85,
            "ownership_signal": True,
            "has_jira_sync": False,
        },
    },
}

assert dims["engagement"]["medal"] == "silver"
assert dimensions["dimensions"]["engagement"]["required_metrics_for_scoring"] == [
    "avg_triage_days",
    "avg_pr_review_days",
    "response_coverage_rate",
]
```

- [ ] **Step 2: Run the targeted test to prove the rename is not wired yet**

Run:

```bash
pytest --tb=short engine/__tests__/test_integration.py -q
```

Expected: FAIL because `config/dimensions.yaml` and the scorer references still expose `support_engagement`.

- [ ] **Step 3: Rename the dimension and package everywhere the live contract uses it**

Move the scorer package:

```bash
git mv scorers/support_engagement scorers/engagement
```

Update `config/dimensions.yaml`:

```yaml
  engagement:
    label: "Engagement"
    description: "Maintainer responsiveness and user engagement metrics from GitHub."
    scorer: "scorers/engagement/scorer.py"
    applies_to:
      product_types: ["root", "charm", "snap"]
    aggregation: "worst_in_scope"
    required_metrics_for_scoring:
      - avg_triage_days
      - avg_pr_review_days
      - response_coverage_rate
    outputs:
      avg_triage_days: {type: number, range: "≥ 0 days", label: "Avg. triage time", description: "Average days from issue creation to first non-author response."}
      avg_pr_review_days: {type: number, range: "≥ 0 days", label: "Avg. PR review time", description: "Average days from PR opening to first submitted review."}
      response_coverage_rate: {type: number, range: "0–100", label: "Response coverage", description: "Percentage of recent issues and PRs that received a first response within the measurement window."}
      ownership_signal: {type: boolean, label: "Ownership signal", description: "Repository exposes clear ownership through a squad topic."}
      has_jira_sync: {type: boolean, label: "Jira sync configured", description: "Repository has GitHub-to-Jira sync configuration.", informational: true}
    medals:
      bronze: ["ownership_signal == true"]
      silver: ["avg_triage_days <= 3", "avg_pr_review_days <= 5", "response_coverage_rate >= 80", "ownership_signal == true"]
      gold: ["avg_triage_days <= 2", "avg_pr_review_days <= 3", "response_coverage_rate >= 90", "ownership_signal == true"]
```

Update the renamed wrapper import in `scorers/engagement/scorer.py`:

```python
"""engagement scorer — iterates leaf products and outputs per-leaf metrics."""

from scorers.engagement.logic import compute_metrics
```

Update pipeline references in `Makefile` and `.github/workflows/compute-metrics.yml`:

```make
$(PYTHON) scorers/engagement/scorer.py --product-yaml products/$(PRODUCT).yaml --products-dir products/ \
	> $(SCORE_DIR)/$(PRODUCT)/engagement.json
```

```yaml
- name: Run engagement scorer
  run: |
    python scorers/engagement/scorer.py \
      --product-yaml products/${{ matrix.product }}.yaml \
      --products-dir products/ \
      > /tmp/scorers/${{ matrix.product }}/engagement.json
```

Update public docs:

```md
Products are scored automatically across five quality dimensions (test coverage, documentation, security, substrate compatibility, engagement) and awarded a **bronze / silver / gold** medal based on configurable criteria.
```

```md
| `engagement` | `avg_triage_days`, `avg_pr_review_days`, `response_coverage_rate`, `ownership_signal`, `has_jira_sync`, `repo_views_14d` | Silver: triage ≤ 3d, PR ≤ 5d, response coverage ≥ 80. Gold: triage ≤ 2d, PR ≤ 3d, response coverage ≥ 90. `repo_views_14d` is informational only. |
```

```md
- `engagement` requires the sampled response metrics that can otherwise be `null`
```

- [ ] **Step 4: Run the renamed contract tests**

Run:

```bash
pytest --tb=short engine/__tests__/test_integration.py scorers/engagement/__tests__/test_logic.py -q
```

Expected: PASS. The scorer package is renamed, the config key is `engagement`, and the integration fixture resolves the renamed dimension.

- [ ] **Step 5: Commit the rename-only slice**

Run:

```bash
git add config/dimensions.yaml \
  engine/__tests__/test_integration.py \
  Makefile \
  .github/workflows/compute-metrics.yml \
  README.md AGENTS.md docs/local-scoring.md \
  scorers/engagement \
  scorers/support_engagement
git commit -m "refactor: rename support_engagement to engagement"
```

---

### Task 2: Add the informational `repo_views_14d` metric to the scorer

**Files:**
- Modify: `config/dimensions.yaml`
- Modify: `scorers/engagement/logic.py`
- Modify: `scorers/engagement/scorer.py`
- Modify: `scorers/engagement/__tests__/test_logic.py`
- Modify: `engine/__tests__/test_integration.py`

**Interfaces:**
- Consumes: `compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]`.
- Produces:
  - `_fetch_repo_views_14d(owner_repo: str, session: requests.Session) -> int | None`,
  - `compute_metrics(...)[\"repo_views_14d\"]`,
  - `config/dimensions.yaml` output metadata for `repo_views_14d`.

- [ ] **Step 1: Write the failing scorer tests for traffic views**

Add these tests to `scorers/engagement/__tests__/test_logic.py`:

```python
@responses.activate
def test_includes_repo_views_14d_when_traffic_api_available():
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=_ISSUES,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues/1/comments",
        json=_COMMENTS_ISSUE_1,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues/2/comments",
        json=_COMMENTS_ISSUE_2,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=_PULLS,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/10/reviews",
        json=_REVIEWS_PR_10,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/11/reviews",
        json=_REVIEWS_PR_11,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/12/reviews",
        json=_REVIEWS_PR_12,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/traffic/views",
        json={"count": 321, "uniques": 42, "views": []},
        status=200,
    )
    _mock_repo_metadata("canonical/synapse-operator", topics=["squad-americas"], jira_sync=True)

    result = compute_metrics(UNIT, "token")

    assert result["repo_views_14d"] == 321
```

```python
@responses.activate
def test_repo_views_14d_is_none_when_traffic_api_is_unavailable():
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues",
        json=_ISSUES,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues/1/comments",
        json=_COMMENTS_ISSUE_1,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/issues/2/comments",
        json=_COMMENTS_ISSUE_2,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls",
        json=_PULLS,
        status=200,
        match_querystring=False,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/10/reviews",
        json=_REVIEWS_PR_10,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/11/reviews",
        json=_REVIEWS_PR_11,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/pulls/12/reviews",
        json=_REVIEWS_PR_12,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/traffic/views",
        json={"message": "Must have push access"},
        status=403,
    )
    _mock_repo_metadata("canonical/synapse-operator", topics=["squad-americas"], jira_sync=False)

    result = compute_metrics(UNIT, "token")

    assert result["avg_triage_days"] == 3.0
    assert result["avg_pr_review_days"] == 1.0
    assert result["response_coverage_rate"] == 100.0
    assert result["repo_views_14d"] is None
```

Also extend the integration fixture so the renamed dimension includes the optional metric:

```python
"engagement": {
    "avg_triage_days": 3.0,
    "avg_pr_review_days": 4.0,
    "response_coverage_rate": 85,
    "ownership_signal": True,
    "has_jira_sync": False,
    "repo_views_14d": 120,
},
```

Update the exact no-repo expectation in the existing test:

```python
assert result == {
    "avg_triage_days": 0.0,
    "avg_pr_review_days": 0.0,
    "response_coverage_rate": 0,
    "ownership_signal": False,
    "has_jira_sync": False,
    "repo_views_14d": None,
}
```

- [ ] **Step 2: Run the targeted scorer tests and watch them fail**

Run:

```bash
pytest --tb=short scorers/engagement/__tests__/test_logic.py -k repo_views_14d -q
```

Expected: FAIL because `compute_metrics()` does not yet return `repo_views_14d`.

- [ ] **Step 3: Implement the traffic fetch and mark the metric informational**

Update the output contract in `config/dimensions.yaml`:

```yaml
      repo_views_14d: {type: number, range: "≥ 0 views", label: "Repo views (14d)", description: "Total GitHub repository page views over the last 14 days.", informational: true}
```

Add a focused helper in `scorers/engagement/logic.py`:

```python
def _fetch_repo_views_14d(owner_repo: str, session: requests.Session) -> int | None:
    resp = session.get(f"{_GITHUB_API}/repos/{owner_repo}/traffic/views", timeout=15)
    if not resp.ok:
        return None
    payload = resp.json()
    count = payload.get("count")
    return count if isinstance(count, int) and count >= 0 else None
```

Extend the no-repo and normal return paths:

```python
    if not repo:
        return {
            "avg_triage_days": 0.0,
            "avg_pr_review_days": 0.0,
            "response_coverage_rate": 0,
            "ownership_signal": False,
            "has_jira_sync": False,
            "repo_views_14d": None,
        }
```

```python
    repo_views_14d = _fetch_repo_views_14d(repo, session)

    return {
        "avg_triage_days": avg_triage,
        "avg_pr_review_days": avg_pr,
        "response_coverage_rate": response_coverage_rate,
        "ownership_signal": squad_topic,
        "has_jira_sync": jira_sync,
        "repo_views_14d": repo_views_14d,
    }
```

Update the wrapper docstring in `scorers/engagement/scorer.py` so it describes both support responsiveness and informational traffic output.

- [ ] **Step 4: Run the scorer tests for the new metric**

Run:

```bash
pytest --tb=short scorers/engagement/__tests__/test_logic.py -q
```

Expected: PASS. The scorer should expose `repo_views_14d`, keep it nullable on traffic failure, and preserve existing support-response semantics.

- [ ] **Step 5: Commit the metric slice**

Run:

```bash
git add config/dimensions.yaml \
  scorers/engagement/logic.py \
  scorers/engagement/scorer.py \
  scorers/engagement/__tests__/test_logic.py \
  engine/__tests__/test_integration.py
git commit -m "feat(engagement): add informational repo traffic views"
```

---

### Task 3: Preserve drift history and verify the renamed scorer end-to-end

**Files:**
- Modify: `engine/assemble.py`
- Modify: `engine/__tests__/test_assemble.py`
- Modify: `engine/__tests__/test_integration.py`

**Interfaces:**
- Consumes: `drift_history: dict` loaded from `--drift-history`.
- Produces:
  - `_migrate_legacy_dimension_keys(drift_history: dict) -> None`,
  - assembled portfolio data keyed by `engagement`,
  - preserved remediation entries when history still uses `support_engagement`.

- [ ] **Step 1: Write the failing drift migration tests**

Add these tests to `engine/__tests__/test_assemble.py`:

```python
from engine.assemble import _migrate_legacy_dimension_keys, assemble_portfolio


def test_migrate_legacy_dimension_keys_moves_support_engagement_to_engagement():
    history = {
        "matrix": {
            "support_engagement": {
                "first_seen_at": "2026-06-01T00:00:00+00:00",
                "deadline": "2026-12-01T00:00:00+00:00",
            }
        }
    }

    _migrate_legacy_dimension_keys(history)

    assert "support_engagement" not in history["matrix"]
    assert history["matrix"]["engagement"]["deadline"] == "2026-12-01T00:00:00+00:00"
```

```python
def test_migrate_legacy_dimension_keys_preserves_existing_engagement_entry():
    history = {
        "matrix": {
            "support_engagement": {
                "first_seen_at": "2026-06-01T00:00:00+00:00",
                "deadline": "2026-12-01T00:00:00+00:00",
            },
            "engagement": {
                "first_seen_at": "2026-07-01T00:00:00+00:00",
                "deadline": "2027-01-01T00:00:00+00:00",
            },
        }
    }

    _migrate_legacy_dimension_keys(history)

    assert history["matrix"]["engagement"]["deadline"] == "2027-01-01T00:00:00+00:00"
    assert "support_engagement" not in history["matrix"]
```

- [ ] **Step 2: Run the focused engine test**

Run:

```bash
pytest --tb=short engine/__tests__/test_assemble.py -k engagement -q
```

Expected: FAIL because `_migrate_legacy_dimension_keys()` does not exist yet.

- [ ] **Step 3: Implement drift-history normalization before assembly**

Add a helper near the top of `engine/assemble.py`:

```python
_LEGACY_DIMENSION_KEYS = {
    "support_engagement": "engagement",
}


def _migrate_legacy_dimension_keys(drift_history: dict) -> None:
    for product_history in drift_history.values():
        if not isinstance(product_history, dict):
            continue
        for legacy_key, new_key in _LEGACY_DIMENSION_KEYS.items():
            legacy_entry = product_history.pop(legacy_key, None)
            if legacy_entry is not None and new_key not in product_history:
                product_history[new_key] = legacy_entry
```

Call it immediately after loading the drift history in `main()`:

```python
    drift_history = json.loads(drift_history_path.read_text())
    _migrate_legacy_dimension_keys(drift_history)
```

Keep the existing `assemble_portfolio(...)` and `update_drift_history(...)` flows unchanged after normalization.

- [ ] **Step 4: Run full validation for the renamed scorer path and end-to-end scoring**

Run:

```bash
make test
make score-no-llm PRODUCT=matrix
make _merge PRODUCT=matrix
make _assemble
make build
```

Expected:

- `make test` passes, including scorer and engine tests,
- `.pqf-score/matrix/engagement.json` is generated,
- `computed/matrix.json` and `public/portfolio.json` assemble successfully with `engagement`,
- `make build` passes with the refreshed data contract.

- [ ] **Step 5: Commit the migration and verification slice**

Run:

```bash
git add engine/assemble.py engine/__tests__/test_assemble.py engine/__tests__/test_integration.py
git commit -m "fix(engine): preserve engagement drift history across rename"
```
