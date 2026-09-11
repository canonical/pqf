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


def step_names(job: dict) -> list[str]:
    return [step.get("name", step.get("uses", "")) for step in job["steps"]]


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
