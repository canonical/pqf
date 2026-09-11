from pathlib import Path

import pytest
import yaml

from engine.framework import FrameworkStatus, discover_frameworks
from engine.workflow_matrix import SCHEDULE_CADENCES, select_frameworks


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

    # Two cron entries: nightly (active) + weekly (upcoming). The cadence is derived
    # from the cron literal by engine.workflow_matrix.SCHEDULE_CADENCES, so the
    # declared crons must match that mapping exactly — otherwise a schedule change
    # would silently score the wrong framework versions.
    crons = [entry["cron"] for entry in on["schedule"]]
    assert sorted(crons) == sorted(SCHEDULE_CADENCES), (
        "declared cron entries must match engine.workflow_matrix.SCHEDULE_CADENCES exactly"
    )
    assert SCHEDULE_CADENCES["0 2 * * *"] == "nightly"
    assert SCHEDULE_CADENCES["0 3 * * 1"] == "weekly"

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

    # ---- determine-matrix: builds the framework/product matrix ----
    determine_matrix = jobs["determine-matrix"]
    assert determine_matrix["outputs"]["matrix"] == "${{ steps.build.outputs.matrix }}"
    assert determine_matrix["outputs"]["versions"] == "${{ steps.build.outputs.versions }}"
    build_step = next(step for step in determine_matrix["steps"] if step.get("id") == "build")
    build_run = build_step["run"]
    assert "engine.workflow_matrix" in build_run
    # Cadence for scheduled runs is derived from the cron literal by the tested
    # mapping, never by comparing cron strings in YAML.
    assert '--schedule "$EVENT_SCHEDULE"' in build_run
    assert "0 3 * * 1" not in build_run, (
        "cadence must be derived by engine.workflow_matrix, not by a cron literal "
        "duplicated in shell"
    )
    assert "--cadence manual" in build_run
    assert "--cadence changed" in build_run
    assert "--changed-paths-file" in build_run
    assert build_step["env"]["DISPATCH_VERSION"] == "${{ github.event.inputs.framework_version }}"

    # First-run bootstrap: the matrix script is told where the published site is so
    # live versions missing a portfolio there are scored automatically.
    assert "--published-dir .gh-pages-data" in build_run
    pages_checkout = next(
        step
        for step in determine_matrix["steps"]
        if step.get("name") == "Check out current Pages data"
    )
    assert pages_checkout["with"]["ref"] == "gh-pages"
    assert pages_checkout["with"]["path"] == ".gh-pages-data"
    assert pages_checkout["continue-on-error"] is True, (
        "a missing gh-pages branch must bootstrap every live version, not fail the run"
    )
    matrix_names = step_names(determine_matrix)
    assert matrix_names.index("Check out current Pages data") < matrix_names.index(
        "Build framework/product matrix"
    )

    # A force-push / new branch has no usable base commit; the diff must not explode.
    assert "0000000000000000000000000000000000000000" in build_run
    assert "git ls-files" in build_run

    # ---- compute-metrics: one job per (version, product), looping dimensions ----
    compute_metrics = jobs["compute-metrics"]
    assert compute_metrics["needs"] == "determine-matrix"
    assert (
        compute_metrics["strategy"]["matrix"]
        == "${{ fromJson(needs.determine-matrix.outputs.matrix) }}"
    )
    scorer_step = next(
        step
        for step in compute_metrics["steps"]
        if step.get("name") == "Run every dimension for this framework version"
    )
    scorer_run = scorer_step["run"]
    assert "scorers/run.py" in scorer_run
    assert "--list-dimensions" in scorer_run, (
        "each job must discover its framework version's dimensions itself"
    )
    assert "for dimension in $dimensions; do" in scorer_run
    assert '--dimension "$dimension"' in scorer_run
    assert '--product-yaml "products/$PRODUCT.yaml"' in scorer_run
    assert "matrix.dimension" not in scorer_run, (
        "dimension must not be a matrix axis; jobs loop over dimensions instead"
    )
    assert "matrix.dimension" not in yaml.safe_dump(compute_metrics), (
        "the matrix is (framework_version, product) only"
    )
    assert "Check if product needs rescoring" not in step_names(compute_metrics), (
        "per-product PR rescore skip removed; filtering is now version-level via determine-matrix"
    )

    upload_step = next(
        step for step in compute_metrics["steps"] if step.get("name") == "Upload scorer output"
    )
    assert upload_step["with"]["name"] == (
        "scorer-output-${{ matrix.framework_version }}-${{ matrix.product }}"
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

    # ---- assemble-versions: one assemble run per selected version ----
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

    # ---- run-engine: preserves archived/untouched versions, rebuilds version index ----
    run_engine = jobs["run-engine"]
    assert run_engine["needs"] == [
        "determine-matrix",
        "compute-metrics",
        "merge-computed",
        "assemble-versions",
    ]

    # Upstream failure must block publishing; 'skipped' only counts as "no work"
    # when the version selection was genuinely empty.
    gate = " ".join(run_engine["if"].split())
    assert "needs.determine-matrix.result == 'success'" in gate
    assert "needs.determine-matrix.outputs.versions == '[]'" in gate, (
        "'skipped' upstream jobs may only be tolerated when the selection was empty"
    )
    assert "needs.determine-matrix.outputs.versions != '[]'" in gate
    for upstream in ["compute-metrics", "merge-computed", "assemble-versions"]:
        assert f"needs.{upstream}.result == 'skipped'" in gate, (
            f"{upstream} may only be skipped when there is no work"
        )
        assert f"needs.{upstream}.result == 'success'" in gate, (
            f"{upstream} must have succeeded when there is work"
        )
        assert f"needs.{upstream}.result == 'failure'" not in gate
        interchangeable = (
            f"(needs.{upstream}.result == 'success' || needs.{upstream}.result == 'skipped')"
        )
        assert interchangeable not in gate, (
            f"{upstream} success must not be interchangeable with skipped"
        )

    carry_forward_step = next(
        step
        for step in run_engine["steps"]
        if step.get("name") == "Carry forward previously published artifacts"
    )
    carry_forward_run = carry_forward_step["run"]
    # Archived versions are never rescored; they survive only via this copy.
    assert ".gh-pages-data/versions/." in carry_forward_run
    assert "rm -rf public/badges" in carry_forward_run, (
        "repo-tracked badges must be cleared so removed products cannot accumulate"
    )
    assert "cp -R .gh-pages-data/badges" not in carry_forward_run, (
        "root badges are regenerated from the active version, not accumulated from gh-pages"
    )

    root_publish_step = next(
        step
        for step in run_engine["steps"]
        if step.get("name") == "Publish active version at the stable root paths"
    )
    root_publish_run = root_publish_step["run"]
    assert "engine/badges.py" in root_publish_run
    assert "--output-dir public/badges/" in root_publish_run, (
        "active badges must stay at the stable root path public/badges/"
    )
    assert "rm -rf public/badges" in root_publish_run, (
        "badges are regenerated into a cleared directory so removed products drop out"
    )
    assert 'cp "$portfolio" public/portfolio.json' in root_publish_run

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
    assert pages_checkout["continue-on-error"] is True

    names = step_names(run_engine)
    assert names.index("Check out current Pages data") < names.index(
        "Carry forward previously published artifacts"
    )
    assert names.index("Carry forward previously published artifacts") < names.index(
        "Download freshly computed framework versions"
    )
    assert names.index("Download freshly computed framework versions") < names.index(
        "Publish active version at the stable root paths"
    )
    assert names.index("Publish active version at the stable root paths") < names.index(
        "Regenerate framework version index"
    )
    assert names.index("Regenerate framework version index") < names.index(
        "Upload engine artifacts"
    )

    engine_upload = next(
        step for step in run_engine["steps"] if step.get("name") == "Upload engine artifacts"
    )
    assert engine_upload["with"]["name"] == "engine-artifacts"
    assert engine_upload["with"]["path"] == "public/", (
        "the artifact root is the contents of public/, so consumers extract into public/"
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
    # 'needs: run-engine' without a status function keeps the implicit success()
    # gate, so a blocked run-engine also blocks the deploy.
    assert "always()" not in expr

    names = step_names(deploy_job)
    assert "Reset public data" in names
    assert "Download engine artifacts" in names
    assert "Build UI" in names
    assert "Deploy to GitHub Pages (attempt 1)" in names
    assert "Wait before deploy retry" in names
    assert "Deploy to GitHub Pages (retry)" in names

    # Verify ordering: reset, then download, then build
    assert names.index("Reset public data") < names.index("Download engine artifacts")
    assert names.index("Download engine artifacts") < names.index("Build UI"), (
        "Download engine artifacts must run before Build UI"
    )

    reset_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Reset public data"
    )
    for stale in ["public/badges", "public/versions", "public/portfolio.json"]:
        assert stale in reset_step["run"]

    artifact_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Download engine artifacts"
    )
    assert artifact_step["with"]["name"] == "engine-artifacts"
    assert artifact_step["with"]["path"] == "public", (
        "engine-artifacts must be extracted into public/ so framework-versions.json, "
        "versions/ and badges/ reach Vite's publicDir"
    )

    deploy_step = next(
        step
        for step in deploy_job["steps"]
        if step.get("name") == "Deploy to GitHub Pages (attempt 1)"
    )
    assert deploy_step["uses"] == "peaceiris/actions-gh-pages@v4"
    assert deploy_step["continue-on-error"] is True
    assert deploy_step["with"]["keep_files"] is True, (
        "keep_files preserves /legacy/ and other already-published Pages content"
    )
    retry_step = next(
        step for step in deploy_job["steps"] if step.get("name") == "Deploy to GitHub Pages (retry)"
    )
    assert retry_step["with"]["keep_files"] is True

    # ---- PR preview path must remain artifact-driven ----
    assert "build-preview" in jobs, "expected 'build-preview' job for PR previews"
    preview = jobs["build-preview"]
    assert preview["needs"] == "run-engine"
    # Only run on PRs in canonical/pqf (the real repo)
    preview_if = preview.get("if", "")
    assert "github.event_name == 'pull_request'" in preview_if
    assert "github.repository == 'canonical/pqf'" in preview_if
    assert "always()" not in preview_if

    preview_names = step_names(preview)
    # Step name includes extra context in YAML; check substring for robustness
    assert any("Download engine artifacts" in n for n in preview_names), (
        "preview must download engine-artifacts"
    )
    assert "Reset public data" in preview_names
    assert "Build UI" in preview_names, "preview must build the UI"

    # Verify ordering: reset, download, build
    idx_dl = next(i for i, n in enumerate(preview_names) if "Download engine artifacts" in n)
    assert preview_names.index("Reset public data") < idx_dl
    assert idx_dl < preview_names.index("Build UI"), (
        "preview must download engine artifacts before building UI"
    )

    dl_step = next(
        step for step in preview["steps"] if "Download engine artifacts" in step.get("name", "")
    )
    # Confirm it downloads the named artifact into Vite's publicDir
    assert dl_step["with"]["name"] == "engine-artifacts"
    assert dl_step["with"]["path"] == "public"

    assert "github.event.action != 'closed'" in preview_if

    preview_deploy_step = next(
        step for step in preview["steps"] if step.get("name") == "Deploy PR preview"
    )
    # comment key must be absent so the action posts a PR link comment automatically
    assert "comment" not in preview_deploy_step["with"], (
        "removing 'comment: false' lets the preview action post a PR link comment; do not re-add it"
    )

    assert "cleanup-preview" not in jobs, "cleanup moved to dedicated cleanup-preview workflow"


def test_compute_metrics_never_schedules_archived_framework_versions() -> None:
    """Archived versions must survive only via the gh-pages carry-forward copy."""
    frameworks = discover_frameworks(Path("framework/versions"))
    archived_ids = [f.id for f in frameworks if f.status == FrameworkStatus.ARCHIVED]

    for cadence in ("nightly", "weekly"):
        selected = select_frameworks(frameworks, cadence=cadence)
        assert not ({f.id for f in selected} & set(archived_ids))

    for archived_id in archived_ids:
        with pytest.raises(ValueError, match="archived"):
            select_frameworks(frameworks, cadence="manual", framework_version=archived_id)


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
