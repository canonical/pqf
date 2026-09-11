from pathlib import Path

import yaml


def load_workflow(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def step_names(job: dict) -> list[str]:
    return [step.get("name", step.get("uses", "")) for step in job["steps"]]


def test_deploy_legacy_workflow_deploys_selected_historical_ref_to_legacy() -> None:
    workflow = load_workflow(".github/workflows/deploy-legacy.yml")

    on = workflow.get("on") or workflow.get(True) or {}
    assert set(on) == {"workflow_dispatch"}

    dispatch = on["workflow_dispatch"]
    inputs = dispatch["inputs"]
    assert "ref" in inputs
    assert inputs["ref"]["required"] is True

    jobs = workflow["jobs"]
    assert list(jobs) == ["deploy"]
    deploy_job = jobs["deploy"]

    checkout_step = next(
        step for step in deploy_job["steps"] if step.get("uses") == "actions/checkout@v4"
    )
    assert checkout_step["with"]["ref"] == "${{ inputs.ref }}"

    setup_node_step = next(
        step for step in deploy_job["steps"] if step.get("uses") == "actions/setup-node@v4"
    )
    assert setup_node_step["with"]["node-version"] == "22"

    assert "Build UI" in step_names(deploy_job)

    deploy_step = next(
        step for step in deploy_job["steps"] if step.get("uses") == "peaceiris/actions-gh-pages@v4"
    )
    assert deploy_step["with"]["publish_dir"] == "ui/dist"
    assert deploy_step["with"]["destination_dir"] == "legacy"
    assert deploy_step["with"]["keep_files"] is True

    assert not any(
        "scorer" in step.get("name", "").lower() or "scorer" in step.get("run", "").lower()
        for step in deploy_job["steps"]
        if isinstance(step.get("run"), str)
    )


def test_compute_metrics_deploys_production_from_engine_artifacts() -> None:
    workflow = load_workflow(".github/workflows/compute-metrics.yml")
    jobs = workflow["jobs"]

    # Workflow-level ownership triggers
    # YAML 1.1 treats the bare key 'on' as a boolean, so it can be parsed as True.
    on = workflow.get("on") or workflow.get(True) or {}
    assert "schedule" in on, "expected 'schedule' trigger at workflow level"

    # Two cron entries: nightly (active) + weekly (upcoming), distinguished
    # at runtime by github.event.schedule.
    crons = [entry["cron"] for entry in on["schedule"]]
    assert "0 2 * * *" in crons, "expected nightly cron for active framework version"
    assert "0 3 * * 1" in crons, "expected weekly cron for upcoming framework version"

    assert "workflow_dispatch" in on, "expected 'workflow_dispatch' trigger at workflow level"
    dispatch_inputs = on["workflow_dispatch"]["inputs"]
    assert "framework_version" in dispatch_inputs
    assert dispatch_inputs["framework_version"]["required"] is True

    push = on.get("push", {})
    assert push["branches"] == ["main"]
    paths = push.get("paths", [])
    for pattern in [
        "products/**",
        "framework/**",
        "config/**",
        "scorers/**",
        "!scorers/**/__tests__/**",
        "engine/**",
        "!engine/__tests__/**",
    ]:
        assert pattern in paths, f"push.paths must include '{pattern}'"

    pull_request = on.get("pull_request", {})
    assert pull_request.get("types", []) == ["opened", "reopened", "synchronize"], (
        "pull_request trigger should only include active PR events; "
        "closed PR cleanup is in a separate workflow"
    )
    pr_paths = pull_request.get("paths", [])
    for pattern in [
        "products/**",
        "framework/**",
        "config/**",
        "scorers/**",
        "!scorers/**/__tests__/**",
        "engine/**",
        "!engine/__tests__/**",
        "ui/**",
    ]:
        assert pattern in pr_paths, f"pull_request.paths must include '{pattern}'"

    for job_name in [
        "change-report",
        "determine-matrix",
        "compute-metrics",
        "merge-computed",
        "assemble-versions",
        "run-engine",
        "build-preview",
        "deploy-production",
    ]:
        assert job_name in jobs, f"expected '{job_name}' job"
    assert "commit-artifacts" not in jobs
    assert "discover-products" not in jobs, "discover-products replaced by determine-matrix"

    # ---- change-report: semantic change summary posted to PR ----
    change_report = jobs["change-report"]
    assert change_report["if"] == "github.event_name == 'pull_request'"
    change_report_run = next(
        step["run"] for step in change_report["steps"] if "change_report" in step.get("run", "")
    )
    assert "python3 -m engine.change_report --base-ref" in change_report_run
    assert "origin/${{ github.base_ref }}" in change_report_run
    assert "$GITHUB_STEP_SUMMARY" in change_report_run

    # ---- determine-matrix: builds the framework/product/dimension matrix ----
    determine_matrix = jobs["determine-matrix"]
    assert determine_matrix["outputs"]["matrix"] == "${{ steps.build.outputs.matrix }}"
    assert determine_matrix["outputs"]["versions"] == "${{ steps.build.outputs.versions }}"
    build_step = next(step for step in determine_matrix["steps"] if step.get("id") == "build")
    assert "engine.workflow_matrix --cadence" in build_step["run"]
    assert "nightly" in build_step["run"]
    assert "weekly" in build_step["run"]
    assert "manual" in build_step["run"]
    assert "github.event.inputs.framework_version" in build_step["run"]

    # ---- compute-metrics: runs the generic scorer per matrix row ----
    compute_metrics = jobs["compute-metrics"]
    assert compute_metrics["needs"] == "determine-matrix"
    assert (
        compute_metrics["strategy"]["matrix"]
        == "${{ fromJson(needs.determine-matrix.outputs.matrix) }}"
    )
    scorer_step = next(
        step for step in compute_metrics["steps"] if step.get("name") == "Run generic scorer"
    )
    assert "scorers/run.py" in scorer_step["run"]
    assert "--framework-version ${{ matrix.framework_version }}" in scorer_step["run"]
    assert "--dimension ${{ matrix.dimension }}" in scorer_step["run"]
    assert "--product-yaml products/${{ matrix.product }}.yaml" in scorer_step["run"]
    assert "Check if product needs rescoring" not in step_names(compute_metrics), (
        "per-product PR rescore skip removed; filtering is now version-level via determine-matrix"
    )

    # ---- merge-computed: merges per-dimension outputs into per-version/product envelopes ----
    merge_computed = jobs["merge-computed"]
    assert merge_computed["needs"] == ["determine-matrix", "compute-metrics"]
    merge_step = next(
        step
        for step in merge_computed["steps"]
        if step.get("name") == "Merge scorer outputs into versioned computed envelopes"
    )
    assert "engine/merge_computed.py" in merge_step["run"]
    assert "--framework-version" in merge_step["run"]
    assert "--contract-digest" in merge_step["run"]
    assert "--implementation-fingerprints" in merge_step["run"]

    # ---- assemble-versions: one assemble + badges run per selected version ----
    assemble_versions = jobs["assemble-versions"]
    assert assemble_versions["needs"] == ["determine-matrix", "merge-computed"]
    assert assemble_versions["strategy"]["matrix"]["framework_version"] == (
        "${{ fromJson(needs.determine-matrix.outputs.versions) }}"
    )
    assemble_step = next(
        step
        for step in assemble_versions["steps"]
        if step.get("name") == "Assemble versioned portfolio"
    )
    assert "engine/assemble.py" in assemble_step["run"]
    assert "--framework-version ${{ matrix.framework_version }}" in assemble_step["run"]
    assert "public/versions/${{ matrix.framework_version }}/portfolio.json" in assemble_step["run"]

    badges_step = next(
        step for step in assemble_versions["steps"] if step.get("name") == "Generate active badges"
    )
    assert badges_step["if"] == "steps.status.outputs.status == 'active'", (
        "badges must only be generated for the active framework version"
    )

    # ---- run-engine: preserves archived/untouched versions, rebuilds version index ----
    run_engine = jobs["run-engine"]
    assert run_engine["needs"] == ["determine-matrix", "assemble-versions"]
    carry_forward_step = next(
        step
        for step in run_engine["steps"]
        if step.get("name") == "Carry forward previously published artifacts"
    )
    assert ".gh-pages-data/versions/." in carry_forward_step["run"]
    assert "cp .gh-pages-data/portfolio.json public/portfolio.json" in carry_forward_step["run"]
    assert "cp -R .gh-pages-data/badges public/badges" in carry_forward_step["run"]

    version_index_step = next(
        step
        for step in run_engine["steps"]
        if step.get("name") == "Regenerate framework version index"
    )
    assert "engine/version_index.py" in version_index_step["run"]
    assert "public/framework-versions.json" in version_index_step["run"]

    pages_checkout = next(
        step for step in run_engine["steps"] if step.get("name") == "Check out current Pages data"
    )
    assert pages_checkout["with"]["ref"] == "gh-pages"
    assert pages_checkout["with"]["path"] == ".gh-pages-data"

    names = step_names(run_engine)
    assert names.index("Check out current Pages data") < names.index(
        "Carry forward previously published artifacts"
    )
    assert names.index("Carry forward previously published artifacts") < names.index(
        "Regenerate framework version index"
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
    assert "Deploy to GitHub Pages (attempt 1)" in names
    assert "Wait before deploy retry" in names
    assert "Deploy to GitHub Pages (retry)" in names

    # Verify ordering: Download engine artifacts must come before Build UI
    idx_artifacts = names.index("Download engine artifacts")
    idx_build = names.index("Build UI")
    assert idx_artifacts < idx_build, "Download engine artifacts must run before Build UI"

    artifact_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Download engine artifacts"
    )
    assert artifact_step["with"]["name"] == "engine-artifacts"

    deploy_step = next(
        step
        for step in deploy_job["steps"]
        if step.get("name") == "Deploy to GitHub Pages (attempt 1)"
    )
    assert deploy_step["uses"] == "peaceiris/actions-gh-pages@v4"
    assert deploy_step["continue-on-error"] is True
    assert deploy_step["with"]["keep_files"] is True

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

    preview_deploy_step = next(
        step for step in preview["steps"] if step.get("name") == "Deploy PR preview"
    )
    # comment key must be absent so the action posts a PR link comment automatically
    assert "comment" not in preview_deploy_step["with"], (
        "removing 'comment: false' lets the preview action post a PR link comment; do not re-add it"
    )

    assert "cleanup-preview" not in jobs, "cleanup moved to dedicated cleanup-preview workflow"


def test_deploy_pages_only_runs_for_ui_changes_and_skips_mixed_commits() -> None:
    workflow = load_workflow(".github/workflows/deploy-pages.yml")

    on = workflow.get("on") or workflow.get(True) or {}
    push = on.get("push", {})
    assert push["branches"] == ["main"]
    assert "paths" not in push

    jobs = workflow["jobs"]
    assert "detect-scope" not in jobs

    deploy_job = jobs["deploy"]
    assert "needs" not in deploy_job
    assert "if" not in deploy_job

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
    assert "framework-versions.json" in sync_step["run"], (
        "deploy-pages must also carry forward the framework version index"
    )
    assert ".gh-pages-data/versions/." in sync_step["run"], (
        "deploy-pages must also carry forward public/versions/ (active/upcoming/archived)"
    )

    names = step_names(deploy_job)
    assert "Check out current Pages data" in names
    assert "Sync deployed public data" in names
    assert "Build UI" in names
    assert "Deploy to GitHub Pages (attempt 1)" in names
    assert "Wait before deploy retry" in names
    assert "Deploy to GitHub Pages (retry)" in names

    assert names.index("Sync deployed public data") < names.index("Build UI")


def test_cleanup_preview_workflow_runs_only_on_pr_close() -> None:
    workflow = load_workflow(".github/workflows/cleanup-preview.yml")

    on = workflow.get("on") or workflow.get(True) or {}
    pull_request = on.get("pull_request", {})
    assert pull_request.get("types") == ["closed"]

    jobs = workflow["jobs"]
    assert "cleanup-preview" in jobs
    cleanup = jobs["cleanup-preview"]
    assert cleanup.get("if") == "github.repository == 'canonical/pqf'"

    step = next(step for step in cleanup["steps"] if step.get("name") == "Remove PR preview")
    assert step["uses"] == "rossjrw/pr-preview-action@v1"
    assert step["with"]["action"] == "remove"
    assert step["with"]["preview-branch"] == "gh-pages"
    assert step["with"]["umbrella-dir"] == "pr-preview"
    assert step["with"]["pr-number"] == "${{ github.event.pull_request.number }}"
    assert step["with"]["comment"] is False
