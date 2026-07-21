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

    assert "deploy-production" in jobs
    assert "commit-artifacts" not in jobs

    deploy_job = jobs["deploy-production"]
    assert deploy_job["needs"] == "run-engine"
    # Production deploy must be allowed for schedule, workflow_dispatch, or pushes to main in canonical/pqf
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
    assert any("Download engine artifacts" in n for n in preview_names), "preview must download engine-artifacts"
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
