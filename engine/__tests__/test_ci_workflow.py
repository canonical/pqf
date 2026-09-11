"""Tests for `.github/workflows/ci.yml`'s Playwright E2E job.

Task 11 added `ui/e2e/**` Playwright coverage but never wired it into CI, so the suite only ran
locally via `make e2e`. This asserts the workflow actually installs Chromium (via Playwright's
supported install command) and runs `make e2e`, so a missing/misconfigured CI job fails a test
instead of silently shipping uncovered E2E code.
"""

from pathlib import Path

import yaml


def load_workflow(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def step_runs(job: dict) -> list[str]:
    return [step["run"] for step in job["steps"] if isinstance(step.get("run"), str)]


def test_ci_workflow_runs_playwright_e2e_in_its_own_job() -> None:
    workflow = load_workflow(".github/workflows/ci.yml")
    jobs = workflow["jobs"]

    # A dedicated job (rather than folded into the existing `ui` typecheck/test/build job) keeps
    # the fast unit-test feedback loop from being blocked on browser installs.
    e2e_job = jobs.get("e2e")
    assert e2e_job is not None, "ci.yml must define a dedicated `e2e` job for Playwright tests"

    runs = step_runs(e2e_job)

    checkout_step = next(
        step for step in e2e_job["steps"] if step.get("uses") == "actions/checkout@v4"
    )
    assert checkout_step is not None

    setup_node_step = next(
        step for step in e2e_job["steps"] if step.get("uses") == "actions/setup-node@v4"
    )
    assert setup_node_step["with"]["node-version"] == "22"
    assert setup_node_step["with"]["cache"] == "npm"
    assert setup_node_step["with"]["cache-dependency-path"] == "ui/package-lock.json"

    assert any("make install-ui" in run for run in runs)

    # Chromium must be installed via Playwright's own supported command, not manually downloaded.
    install_step = next(
        step
        for step in e2e_job["steps"]
        if isinstance(step.get("run"), str) and "playwright install" in step["run"]
    )
    assert "chromium" in install_step["run"]

    assert any(step.get("uses", "").startswith("actions/cache") for step in e2e_job["steps"]), (
        "the e2e job must cache the Playwright browser install (e.g. ~/.cache/ms-playwright) "
        "to avoid re-downloading Chromium on every run"
    )

    assert any("make e2e" in run for run in runs), (
        "the e2e job must run the existing `make e2e` target"
    )

    # Should not duplicate the unit-test/build job's responsibilities.
    assert not any("make test-ui" in run for run in runs)
    assert not any("make build" in run for run in runs)


def test_ci_workflow_ui_job_unchanged_by_e2e_addition() -> None:
    workflow = load_workflow(".github/workflows/ci.yml")
    ui_job = workflow["jobs"]["ui"]
    runs = step_runs(ui_job)

    # The existing typecheck/test/build job must not grow a Playwright browser install or `make
    # e2e` invocation — that responsibility belongs solely to the new `e2e` job.
    assert not any("playwright install" in run for run in runs)
    assert not any("make e2e" in run for run in runs)


def test_ci_workflow_ui_job_typechecks_via_project_references() -> None:
    """`npx tsc --noEmit` against the root `ui/tsconfig.json` is a dead step.

    That root config has `"files": []` and only `"references"` to
    `tsconfig.app.json`/`tsconfig.node.json`/`tsconfig.e2e.json` — running plain `tsc --noEmit`
    against it checks zero files and always exits 0, silently, even when `ui/src` or `ui/e2e` has
    real type errors. Only build mode (`tsc -b`) walks the referenced projects. Confirmed locally:
    a deliberate type error in `ui/src/main.tsx` was invisible to `tsc --noEmit` but caught by
    `tsc -b --force` (exit 2). `make build`'s `npm run build` script already runs `tsc -b && vite
    build`, so it is a real typecheck covering app, node, and (since Task 11's follow-up wired
    `tsconfig.e2e.json` into the references) the E2E suite too.
    """
    workflow = load_workflow(".github/workflows/ci.yml")
    ui_job = workflow["jobs"]["ui"]
    runs = step_runs(ui_job)

    assert not any("tsc --noEmit" in run for run in runs), (
        "`npx tsc --noEmit` against the project-references root tsconfig is a no-op that never "
        "checks any files — replace it with `tsc -b` (directly or via `make build`)"
    )

    # The real typecheck must come from a project-reference build: either its own `tsc -b` step,
    # or the existing `make build` step (whose `npm run build` script is `tsc -b && vite build`).
    # It must be owned by exactly one step so the same compile doesn't run twice in one job.
    typecheck_runs = [run for run in runs if "tsc -b" in run or "make build" in run]
    assert len(typecheck_runs) == 1, (
        "the ui job must run a project-reference build/typecheck (`tsc -b` or `make build`) "
        "exactly once — one step should own both typecheck and build to avoid redundant work"
    )


def test_ci_workflow_e2e_job_has_timeout() -> None:
    workflow = load_workflow(".github/workflows/ci.yml")
    e2e_job = workflow["jobs"]["e2e"]

    assert "timeout-minutes" in e2e_job, (
        "the e2e job must set timeout-minutes so a hung browser or dev-server can't block CI "
        "indefinitely"
    )
    assert isinstance(e2e_job["timeout-minutes"], int)
    assert 0 < e2e_job["timeout-minutes"] <= 30


def test_ci_workflow_e2e_job_uploads_report_and_results_on_failure() -> None:
    workflow = load_workflow(".github/workflows/ci.yml")
    e2e_job = workflow["jobs"]["e2e"]

    upload_steps = [
        step
        for step in e2e_job["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@v4")
    ]
    assert upload_steps, (
        "the e2e job must upload ui/playwright-report and ui/test-results as artifacts so "
        "traces/screenshots from a CI failure are downloadable, not lost"
    )

    for step in upload_steps:
        condition = step.get("if", "")
        assert "always()" in condition or "failure()" in condition, (
            f"upload-artifact step {step.get('name')!r} must run on failure (if: always() or "
            "failure()) so artifacts survive a failing run, not just a passing one"
        )

    all_paths = "\n".join(step.get("with", {}).get("path", "") for step in upload_steps)
    assert "ui/playwright-report" in all_paths
    assert "ui/test-results" in all_paths
