from pathlib import Path

import yaml


def load_workflow(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def step_names(job: dict) -> list[str]:
    return [step.get("name", step.get("uses", "")) for step in job["steps"]]


def test_compute_metrics_deploys_production_from_engine_artifacts() -> None:
    workflow = load_workflow(".github/workflows/compute-metrics.yml")
    jobs = workflow["jobs"]

    # Workflow-level ownership triggers
    # YAML 1.1 treats the bare key 'on' as a boolean, so it can be parsed as True.
    on = workflow.get("on") or workflow.get(True) or {}
    assert "schedule" in on, "expected 'schedule' trigger at workflow level"
    assert "workflow_dispatch" in on, "expected 'workflow_dispatch' trigger at workflow level"

    push = on.get("push", {})
    paths = push.get("paths", [])
    for pattern in ["products/**", "config/**", "scorers/**", "engine/**"]:
        assert pattern in paths, f"push.paths must include '{pattern}'"

    pull_request = on.get("pull_request", {})
    assert "closed" in pull_request.get("types", []), "pull_request trigger must include 'closed'"

    assert "deploy-production" in jobs
    assert "commit-artifacts" not in jobs

    closed_pr_guard = "github.event_name != 'pull_request' || github.event.action != 'closed'"
    for job_name in ["discover-products", "compute-metrics", "run-engine"]:
        assert jobs[job_name]["if"] == closed_pr_guard, (
            f"{job_name} must be skipped for pull_request.closed cleanup-only runs"
        )

    deploy_job = jobs["deploy-production"]
    assert deploy_job["needs"] == "run-engine"
    # Production deploy must be allowed for schedule, workflow_dispatch,
    # or pushes to main in canonical/pqf.
    expr = deploy_job["if"]
    assert "github.event_name == 'schedule'" in expr
    assert "github.event_name == 'workflow_dispatch'" in expr
    assert "github.event_name == 'push'" in expr
    assert "github.ref == 'refs/heads/main'" in expr
    assert "github.repository == 'canonical/pqf'" in expr

    names = step_names(deploy_job)
    assert "Download engine artifacts" in names
    assert "Build UI" in names
    assert "Deploy to GitHub Pages" in names

    # Verify ordering: Download engine artifacts must come before Build UI
    idx_artifacts = names.index("Download engine artifacts")
    idx_build = names.index("Build UI")
    assert idx_artifacts < idx_build, "Download engine artifacts must run before Build UI"

    artifact_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Download engine artifacts"
    )
    assert artifact_step["with"]["name"] == "engine-artifacts"

    deploy_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Deploy to GitHub Pages"
    )
    assert deploy_step["uses"] == "peaceiris/actions-gh-pages@v4"

    # ---- PR preview path must remain artifact-driven ----
    assert "build-preview" in jobs, "expected 'build-preview' job for PR previews"
    preview = jobs["build-preview"]
    assert preview["needs"] == "run-engine"
    # Only run on PRs in canonical/pqf (the real repo)
    preview_if = preview.get("if", "")
    assert "github.event_name == 'pull_request'" in preview_if
    assert "github.repository == 'canonical/pqf'" in preview_if

    preview_names = step_names(preview)
    # Step name includes extra context in YAML; check substring for robustness
    assert any("Download engine artifacts" in n for n in preview_names), (
        "preview must download engine-artifacts"
    )
    assert "Build UI" in preview_names, "preview must build the UI"

    # Verify ordering: download occurs before build in preview job
    idx_dl = next(i for i, n in enumerate(preview_names) if "Download engine artifacts" in n)
    idx_build_preview = preview_names.index("Build UI")
    assert idx_dl < idx_build_preview, "preview must download engine artifacts before building UI"

    dl_step = next(
        step for step in preview["steps"] if "Download engine artifacts" in step.get("name", "")
    )
    # Confirm it downloads the named artifact
    assert dl_step["with"]["name"] == "engine-artifacts"

    assert "github.event.action != 'closed'" in preview_if

    assert "cleanup-preview" in jobs, "expected 'cleanup-preview' job for closed PRs"
    cleanup = jobs["cleanup-preview"]
    cleanup_if = cleanup.get("if", "")
    assert "github.event_name == 'pull_request'" in cleanup_if
    assert "github.event.action == 'closed'" in cleanup_if
    assert "github.repository == 'canonical/pqf'" in cleanup_if

    cleanup_step = next(
        step for step in cleanup["steps"] if step.get("name") == "Remove PR preview"
    )
    assert cleanup_step["uses"] == "rossjrw/pr-preview-action@v1"
    assert cleanup_step["with"]["action"] == "remove"
    assert cleanup_step["with"]["preview-branch"] == "gh-pages"
    assert cleanup_step["with"]["umbrella-dir"] == "pr-preview"
    assert cleanup_step["with"]["pr-number"] == "${{ github.event.pull_request.number }}"


def test_deploy_pages_only_runs_for_ui_changes_and_skips_mixed_commits() -> None:
    workflow = load_workflow(".github/workflows/deploy-pages.yml")

    on = workflow.get("on") or workflow.get(True) or {}
    push = on.get("push", {})
    assert push["branches"] == ["main"]
    assert push["paths"] == ["ui/**", ".github/workflows/deploy-pages.yml"]

    jobs = workflow["jobs"]
    assert "detect-scope" in jobs

    detect_scope = jobs["detect-scope"]
    detect_step = next(
        step
        for step in detect_scope["steps"]
        if step.get("name") == "Detect data-affecting changes"
    )
    # The detect step must handle the all-zero "before" (initial commit) case by
    # diffing against the empty tree object instead of the root commit.
    assert "0000000000000000000000000000000000000000" in detect_step["run"]
    assert "git hash-object -t tree" in detect_step["run"]
    assert '"$base"' in detect_step["run"]
    assert "git diff --name-only" in detect_step["run"]
    assert "products/ config/ scorers/ engine/" in detect_step["run"]
    assert detect_scope["outputs"]["data_changed"] == "${{ steps.scope.outputs.data_changed }}"

    deploy_job = jobs["deploy"]
    assert deploy_job["needs"] == "detect-scope"
    assert deploy_job["if"] == "needs.detect-scope.outputs.data_changed != 'true'"

    pages_checkout = next(
        step for step in deploy_job["steps"] if step.get("name") == "Check out current Pages data"
    )
    assert pages_checkout["uses"] == "actions/checkout@v4"
    assert pages_checkout["with"]["ref"] == "gh-pages"
    assert pages_checkout["with"]["path"] == ".gh-pages-data"

    sync_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Sync deployed public data"
    )
    assert "cp .gh-pages-data/portfolio.json public/portfolio.json" in sync_step["run"]
    assert "cp -R .gh-pages-data/badges public/badges" in sync_step["run"]

    names = step_names(deploy_job)
    assert "Check out current Pages data" in names
    assert "Sync deployed public data" in names
    assert "Build UI" in names
    assert "Deploy to GitHub Pages" in names

    assert names.index("Sync deployed public data") < names.index("Build UI")
