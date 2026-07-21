# Artifact-Driven Production Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make production deploys use fresh `engine-artifacts` directly so merged data changes update the live PQF site without requiring generated files to be committed back to `main`.

**Architecture:** Keep the existing PR preview model unchanged and extend it to production: `compute-metrics.yml` remains the source of fresh assembled data, then a new production deploy job builds the UI from downloaded `engine-artifacts` and publishes it. `deploy-pages.yml` is narrowed to UI-only pushes and must explicitly skip mixed UI+data commits so it cannot overwrite a fresh artifact-driven deploy with stale checked-in `public/`.

**Tech Stack:** GitHub Actions workflow YAML, existing `peaceiris/actions-gh-pages@v4` Pages publishing, existing Python/pytest test suite with `yaml.safe_load`, existing Node/Vite UI build via `make build`.

## Global Constraints

- Keep the PR preview path intact: `build-preview` in `.github/workflows/compute-metrics.yml` must continue building from downloaded `engine-artifacts`.
- `compute-metrics.yml` must own production deploys for `push`es to `main` that touch `products/**`, `config/**`, `scorers/**`, or `engine/**`, plus `schedule` and `workflow_dispatch`.
- Production deploys for data-affecting changes must build the UI from downloaded `engine-artifacts`, not from checked-in generated `public/`.
- `commit-artifacts` must no longer be on the critical path for live-site freshness; removing the job entirely is acceptable.
- `deploy-pages.yml` must be restricted to UI-only production deploys and must explicitly guard against mixed UI+data commits.
- For mixed commits that touch both `ui/**` and data-affecting paths, the artifact-driven production deploy path must win and the UI-only deploy path must be skipped.
- Preserve the existing `gh-pages` publishing mechanism.
- Do not redesign scorer behavior, PR preview UX, or introduce a second artifacts PR flow.

---

### Task 1: Move production data deploys into `compute-metrics.yml`

**Files:**
- Create: `engine/__tests__/test_workflows.py`
- Modify: `.github/workflows/compute-metrics.yml`
- Test: `engine/__tests__/test_workflows.py`

**Interfaces:**
- Consumes: downloaded `engine-artifacts` from `run-engine` (`computed/`, `public/`, `drift-history.json`)
- Produces:
  - helper `load_workflow(path: str) -> dict` in `engine/__tests__/test_workflows.py`
  - helper `step_names(job: dict) -> list[str]` in `engine/__tests__/test_workflows.py`
  - workflow job `deploy-production` in `.github/workflows/compute-metrics.yml`
  - removal of workflow job key `commit-artifacts`

- [ ] **Step 1: Write the failing workflow test**

Create `engine/__tests__/test_workflows.py` with this initial content:

```python
from pathlib import Path

import yaml


def load_workflow(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def step_names(job: dict) -> list[str]:
    return [step.get("name", step.get("uses", "")) for step in job["steps"]]


def test_compute_metrics_deploys_production_from_engine_artifacts() -> None:
    workflow = load_workflow(".github/workflows/compute-metrics.yml")
    jobs = workflow["jobs"]

    assert "deploy-production" in jobs
    assert "commit-artifacts" not in jobs

    deploy_job = jobs["deploy-production"]
    assert deploy_job["needs"] == "run-engine"
    assert (
        deploy_job["if"]
        == "github.event_name != 'pull_request' && github.repository == 'canonical/pqf'"
    )

    names = step_names(deploy_job)
    assert "Download engine artifacts" in names
    assert "Build UI" in names
    assert "Deploy to GitHub Pages" in names

    artifact_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Download engine artifacts"
    )
    assert artifact_step["with"]["name"] == "engine-artifacts"

    deploy_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Deploy to GitHub Pages"
    )
    assert deploy_step["uses"] == "peaceiris/actions-gh-pages@v4"
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
pytest --tb=short engine/__tests__/test_workflows.py::test_compute_metrics_deploys_production_from_engine_artifacts
```

Expected: FAIL with an assertion that `deploy-production` is missing and/or `commit-artifacts` is still present.

- [ ] **Step 3: Add the production deploy job and remove `commit-artifacts`**

Edit `.github/workflows/compute-metrics.yml` so the tail of the workflow looks like this:

```yaml
  # ── 5. Build and deploy production site from fresh engine artifacts ───────────
  deploy-production:
    needs: run-engine
    if: github.event_name != 'pull_request' && github.repository == 'canonical/pqf'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download engine artifacts
        uses: actions/download-artifact@v4
        with:
          name: engine-artifacts

      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: ui/package-lock.json

      - name: Install UI dependencies
        run: npm install
        working-directory: ui

      - name: Build UI
        run: npm run build
        working-directory: ui
        # Vite copies ../public/ (downloaded from engine-artifacts) into dist/

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ui/dist
          destination_dir: .
          keep_files: true
```

Also remove this entire obsolete job:

```yaml
  # ── 5. Commit artifacts back to main ────────────────────────────────────────
  commit-artifacts:
    needs: run-engine
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.ref }}
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Download engine artifacts
        uses: actions/download-artifact@v4
        with:
          name: engine-artifacts

      - name: Commit and push artifacts
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add computed/ public/ drift-history.json
          if git diff --cached --quiet; then
            echo "No changes to commit."
          else
            git commit -m "chore: update computed metrics and portfolio [skip ci]"
            git push
          fi
```

- [ ] **Step 4: Run the targeted test to verify it passes**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
pytest --tb=short engine/__tests__/test_workflows.py::test_compute_metrics_deploys_production_from_engine_artifacts
```

Expected: PASS

- [ ] **Step 5: Run the Python suite to verify workflow tests integrate cleanly**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
make test
```

Expected: PASS, including the new `engine/__tests__/test_workflows.py`.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
git add .github/workflows/compute-metrics.yml engine/__tests__/test_workflows.py
git commit -m "fix: deploy production from compute artifacts"
```

---

### Task 2: Restrict `deploy-pages.yml` to UI-only pushes and guard mixed commits

**Files:**
- Modify: `.github/workflows/deploy-pages.yml`
- Modify: `engine/__tests__/test_workflows.py`
- Test: `engine/__tests__/test_workflows.py`

**Interfaces:**
- Consumes:
  - helper `load_workflow(path: str) -> dict`
  - helper `step_names(job: dict) -> list[str]`
- Produces:
  - workflow job `detect-scope` in `.github/workflows/deploy-pages.yml`
  - workflow output `jobs.detect-scope.outputs.data_changed`
  - job-level condition `needs.detect-scope.outputs.data_changed != 'true'` on `deploy`

- [ ] **Step 1: Extend the workflow test with the UI-only guard expectations**

Append this test to `engine/__tests__/test_workflows.py`:

```python
def test_deploy_pages_only_runs_for_ui_changes_and_skips_mixed_commits() -> None:
    workflow = load_workflow(".github/workflows/deploy-pages.yml")

    push = workflow["on"]["push"]
    assert push["branches"] == ["main"]
    assert push["paths"] == ["ui/**", ".github/workflows/deploy-pages.yml"]

    jobs = workflow["jobs"]
    assert "detect-scope" in jobs

    detect_scope = jobs["detect-scope"]
    detect_step = next(
        step for step in detect_scope["steps"] if step.get("name") == "Detect data-affecting changes"
    )
    assert "git diff --name-only" in detect_step["run"]
    assert "products/ config/ scorers/ engine/" in detect_step["run"]
    assert detect_scope["outputs"]["data_changed"] == "${{ steps.scope.outputs.data_changed }}"

    deploy_job = jobs["deploy"]
    assert deploy_job["needs"] == "detect-scope"
    assert deploy_job["if"] == "needs.detect-scope.outputs.data_changed != 'true'"

    names = step_names(deploy_job)
    assert "Build UI" in names
    assert "Deploy to GitHub Pages" in names
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
pytest --tb=short engine/__tests__/test_workflows.py::test_deploy_pages_only_runs_for_ui_changes_and_skips_mixed_commits
```

Expected: FAIL because `deploy-pages.yml` currently has no `paths` filter, no `detect-scope` job, and no mixed-change guard.

- [ ] **Step 3: Narrow `deploy-pages.yml` and add the changed-files guard**

Replace `.github/workflows/deploy-pages.yml` with this structure:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
    paths:
      - 'ui/**'
      - '.github/workflows/deploy-pages.yml'

permissions:
  contents: write

concurrency:
  group: gh-pages
  cancel-in-progress: false

jobs:
  detect-scope:
    runs-on: ubuntu-latest
    outputs:
      data_changed: ${{ steps.scope.outputs.data_changed }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - id: scope
        name: Detect data-affecting changes
        run: |
          before="${{ github.event.before }}"
          if [ "$before" = "0000000000000000000000000000000000000000" ]; then
            before="$(git rev-list --max-parents=0 HEAD)"
          fi

          if git diff --name-only "$before" "${{ github.sha }}" -- products/ config/ scorers/ engine/ | grep -q .; then
            echo "data_changed=true" >> "$GITHUB_OUTPUT"
          else
            echo "data_changed=false" >> "$GITHUB_OUTPUT"
          fi

  deploy:
    needs: detect-scope
    if: needs.detect-scope.outputs.data_changed != 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: ui/package-lock.json

      - name: Install UI dependencies
        run: npm install
        working-directory: ui

      - name: Build UI
        run: npm run build
        working-directory: ui
        # Vite copies ../public/ into dist/ automatically via publicDir config

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ui/dist
          destination_dir: .
          keep_files: true
```

- [ ] **Step 4: Run the targeted test to verify it passes**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
pytest --tb=short engine/__tests__/test_workflows.py::test_deploy_pages_only_runs_for_ui_changes_and_skips_mixed_commits
```

Expected: PASS

- [ ] **Step 5: Run the full validation set**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
make test
make test-ui
make build
```

Expected:

- `make test`: PASS
- `make test-ui`: PASS
- `make build`: PASS

- [ ] **Step 6: Inspect the final diff for workflow ownership**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
git --no-pager diff -- .github/workflows/compute-metrics.yml .github/workflows/deploy-pages.yml engine/__tests__/test_workflows.py
```

Expected diff characteristics:

- `compute-metrics.yml` contains `deploy-production`
- `compute-metrics.yml` no longer contains `commit-artifacts`
- `deploy-pages.yml` contains `paths:` limited to UI workflow changes
- `deploy-pages.yml` contains `detect-scope`
- `deploy-pages.yml` gates `deploy` on `data_changed != 'true'`

- [ ] **Step 7: Commit Task 2**

Run:

```bash
cd /home/samuel.bouffard@canonical.com/projects/srbouffard/pqf
git add .github/workflows/deploy-pages.yml engine/__tests__/test_workflows.py
git commit -m "fix: guard ui-only pages deploys"
```

---

## Self-Review Checklist

- **Spec coverage:** Task 1 covers artifact-driven production deploys and removal of `commit-artifacts` from the critical path. Task 2 covers UI-only `deploy-pages.yml` ownership and the mixed UI+data commit guard.
- **Placeholder scan:** No `TODO`, `TBD`, or unspecified “appropriate handling” steps remain.
- **Type consistency:** The plan uses one shared helper API in tests: `load_workflow(path: str) -> dict`, `step_names(job: dict) -> list[str]`, and the workflow output key `data_changed`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-21-artifact-driven-production-deploy.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
