import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from engine.framework import contract_digest, discover_frameworks, get_framework
from engine.versioning import is_in_version
from engine.workflow_matrix import (
    SCHEDULE_CADENCES,
    bootstrap_selection,
    build_matrix_rows,
    cadence_for_schedule,
    missing_live_versions,
    select_frameworks,
    stale_live_versions,
)

REPO_ROOT = Path(__file__).parent.parent.parent


def _dimensions(names: list[str]) -> dict:
    return {
        "dimensions": {
            name: {
                "label": name,
                "description": name,
                "scorer": f"scorers/{name}/scorer.py",
                "applies_to": {"product_types": ["charm", "snap"]},
                "aggregation": "worst_in_scope",
                "outputs": {
                    "some_metric": {
                        "implementation": "some-metric/v1",
                        "type": "boolean",
                        "label": "Some metric",
                        "description": "Some metric.",
                    }
                },
                "medals": {"bronze": ["some_metric == true"]},
            }
            for name in names
        }
    }


def _write_framework_version(
    root: Path,
    *,
    version_id: str,
    sequence: int,
    status: str,
    dimension_names: list[str],
) -> None:
    version_dir = root / version_id
    version_dir.mkdir(parents=True)
    (version_dir / "framework.yaml").write_text(
        yaml.safe_dump(
            {
                "id": version_id,
                "sequence": sequence,
                "label": f"PQF {version_id.upper()}",
                "status": status,
                "description": f"{version_id} contract",
            },
            sort_keys=False,
        )
    )
    (version_dir / "dimensions.yaml").write_text(
        yaml.safe_dump(_dimensions(dimension_names), sort_keys=False)
    )


def _write_product(
    products_dir: Path,
    *,
    product_id: str,
    introduced_in: str,
    retired_in: str | None = None,
) -> None:
    products_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": product_id,
        "product_type": "charm",
        "name": product_id,
        "introduced_in": introduced_in,
        "targets": {introduced_in: "bronze"},
    }
    if retired_in:
        data["retired_in"] = retired_in
    (products_dir / f"{product_id}.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def _write_published_portfolio(
    published_dir: Path,
    frameworks: list,
    version_id: str,
    *,
    digest: str | None = None,
) -> None:
    """Publish a portfolio for `version_id`, recording its current contract digest."""
    version_dir = published_dir / "versions" / version_id
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "portfolio.json").write_text(
        json.dumps(
            {
                "framework": {"id": version_id},
                "contract_digest": digest or contract_digest(get_framework(frameworks, version_id)),
            }
        )
    )


@pytest.fixture
def fixtures(tmp_path):
    framework_root = tmp_path / "framework" / "versions"
    _write_framework_version(
        framework_root,
        version_id="v0",
        sequence=0,
        status="archived",
        dimension_names=["documentation"],
    )
    _write_framework_version(
        framework_root,
        version_id="v1",
        sequence=1,
        status="active",
        dimension_names=["documentation", "test_verification"],
    )
    _write_framework_version(
        framework_root,
        version_id="v2",
        sequence=2,
        status="upcoming",
        dimension_names=["documentation"],
    )

    products_dir = tmp_path / "products"
    _write_product(products_dir, product_id="early-only", introduced_in="v0", retired_in="v1")
    _write_product(products_dir, product_id="matrix", introduced_in="v0")
    _write_product(products_dir, product_id="new-in-v2", introduced_in="v2")

    return framework_root, products_dir


def test_nightly_selection_returns_only_active_rows(fixtures):
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(frameworks, cadence="nightly")
    assert [f.id for f in selected] == ["v1"]

    rows = build_matrix_rows(frameworks, selected, products_dir)
    assert {row["framework_version"] for row in rows} == {"v1"}
    assert {row["product"] for row in rows} == {"matrix"}


def test_weekly_selection_returns_only_upcoming_rows(fixtures):
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(frameworks, cadence="weekly")
    assert [f.id for f in selected] == ["v2"]

    rows = build_matrix_rows(frameworks, selected, products_dir)
    assert {row["framework_version"] for row in rows} == {"v2"}
    assert {row["product"] for row in rows} == {"matrix", "new-in-v2"}


def test_matrix_rows_are_version_and_product_only(fixtures):
    """Dimensions are looped inside each job, so they must not appear in the matrix."""
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(frameworks, cadence="nightly")
    rows = build_matrix_rows(frameworks, selected, products_dir)

    assert rows, "expected at least one matrix row"
    for row in rows:
        assert set(row) == {"framework_version", "product"}
    assert len(rows) == len({(row["framework_version"], row["product"]) for row in rows}), (
        "one row per (framework version, product); no duplicates"
    )


def test_manual_selection_accepts_active_version(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(frameworks, cadence="manual", framework_version="v1")
    assert [f.id for f in selected] == ["v1"]


def test_manual_selection_also_includes_unpublished_changed_versions(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(
        frameworks,
        cadence="manual",
        framework_version="v2",
        changed_paths=["framework/versions/v1/dimensions.yaml"],
    )

    assert [f.id for f in selected] == ["v1", "v2"]


def test_manual_selection_accepts_upcoming_version(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(frameworks, cadence="manual", framework_version="v2")
    assert [f.id for f in selected] == ["v2"]


def test_manual_selection_rejects_archived_version(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    with pytest.raises(ValueError, match="archived"):
        select_frameworks(frameworks, cadence="manual", framework_version="v0")


def test_manual_selection_requires_framework_version(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    with pytest.raises(ValueError, match="--framework-version is required"):
        select_frameworks(frameworks, cadence="manual")


def test_scheduled_cadences_reject_explicit_framework_version(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    with pytest.raises(ValueError, match="not supported"):
        select_frameworks(frameworks, cadence="nightly", framework_version="v1")


def test_scheduled_cadence_also_includes_unpublished_changed_versions(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(
        frameworks,
        cadence="weekly",
        changed_paths=["framework/versions/v1/dimensions.yaml"],
    )

    assert [f.id for f in selected] == ["v1", "v2"]


def test_unknown_cadence_is_rejected(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    with pytest.raises(ValueError, match="Unknown cadence"):
        select_frameworks(frameworks, cadence="hourly")


def test_catalog_filtering_excludes_products_outside_selected_version(fixtures):
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)
    v1 = next(f for f in frameworks if f.id == "v1")

    rows = build_matrix_rows(frameworks, [v1], products_dir)

    products_in_rows = {row["product"] for row in rows}
    assert "early-only" not in products_in_rows, (
        "early-only is retired_in v1 and must be excluded from v1's matrix"
    )
    assert "new-in-v2" not in products_in_rows, (
        "new-in-v2 is introduced_in v2 and must be excluded from v1's matrix"
    )
    assert products_in_rows == {"matrix"}


# ── Cadence derived from the declared cron literals ───────────────────────────


def test_cadence_for_schedule_maps_declared_crons():
    assert cadence_for_schedule("0 2 * * *") == "nightly"
    assert cadence_for_schedule("0 3 * * 1") == "weekly"
    assert cadence_for_schedule("  0 3 * * 1  ") == "weekly"


def test_cadence_for_schedule_rejects_unknown_cron():
    with pytest.raises(ValueError, match="Unknown schedule cron"):
        cadence_for_schedule("0 4 * * 1")


# ── Changed-path selection (push / pull_request) ──────────────────────────────


def test_changed_cadence_selects_only_the_touched_version(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(
        frameworks,
        cadence="changed",
        changed_paths=["framework/versions/v2/dimensions.yaml"],
    )
    assert [f.id for f in selected] == ["v2"]


def test_changed_cadence_never_selects_archived_versions(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(
        frameworks,
        cadence="changed",
        changed_paths=["framework/versions/v0/dimensions.yaml"],
    )
    assert selected == []


def test_changed_cadence_treats_shared_inputs_as_broad(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    for path in [
        "scorers/documentation/logic.py",
        "engine/assemble.py",
        "config/schemas/dimensions.schema.json",
        "products/matrix.yaml",
        ".github/workflows/compute-metrics.yml",
        "framework/README.md",
    ]:
        selected = select_frameworks(frameworks, cadence="changed", changed_paths=[path])
        assert [f.id for f in selected] == ["v1", "v2"], f"{path} should affect every live version"


def test_changed_cadence_ignores_test_only_changes(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(
        frameworks,
        cadence="changed",
        changed_paths=[
            "engine/__tests__/test_assemble.py",
            "scorers/documentation/__tests__/test_logic.py",
        ],
    )
    assert selected == []


def test_changed_cadence_requires_changed_paths(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    with pytest.raises(ValueError, match="--changed-paths-file is required"):
        select_frameworks(frameworks, cadence="changed")


# ── First-run bootstrap of live versions missing from the published site ──────


def test_missing_live_versions_reports_every_live_version_when_nothing_published(
    fixtures, tmp_path
):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    missing = missing_live_versions(frameworks, tmp_path / "never-published")
    assert [f.id for f in missing] == ["v1", "v2"], (
        "archived versions are never bootstrapped; both live versions are missing"
    )


def test_bootstrap_adds_live_version_absent_from_published_site(fixtures, tmp_path):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1")

    selected = select_frameworks(frameworks, cadence="nightly")
    bootstrapped = bootstrap_selection(frameworks, selected, published)

    assert [f.id for f in bootstrapped] == ["v1", "v2"], (
        "v2 has no published portfolio, so it must be scored even though nightly "
        "only selects the active version"
    )


def test_bootstrap_is_a_noop_when_every_live_version_is_published(fixtures, tmp_path):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1")
    _write_published_portfolio(published, frameworks, "v2")

    selected = select_frameworks(frameworks, cadence="nightly")
    bootstrapped = bootstrap_selection(frameworks, selected, published)

    assert [f.id for f in bootstrapped] == ["v1"]


def test_bootstrap_never_adds_archived_versions(fixtures, tmp_path):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"

    bootstrapped = bootstrap_selection(frameworks, [], published)
    assert "v0" not in [f.id for f in bootstrapped]


def test_stale_live_versions_flags_a_published_portfolio_with_an_outdated_digest(
    fixtures, tmp_path
):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1", digest="superseded-contract")
    _write_published_portfolio(published, frameworks, "v2")

    stale = stale_live_versions(frameworks, published)
    assert [f.id for f in stale] == ["v1"]


def test_stale_live_versions_ignores_versions_matching_the_current_contract(fixtures, tmp_path):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1")
    _write_published_portfolio(published, frameworks, "v2")

    assert stale_live_versions(frameworks, published) == []


def test_stale_live_versions_flags_unreadable_or_digestless_portfolios(fixtures, tmp_path):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v2")

    broken = published / "versions" / "v1" / "portfolio.json"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("{not json")
    assert [f.id for f in stale_live_versions(frameworks, published)] == ["v1"]

    broken.write_text(json.dumps({"framework": {"id": "v1"}}))
    assert [f.id for f in stale_live_versions(frameworks, published)] == ["v1"]


def test_stale_live_versions_never_reports_archived_versions(fixtures, tmp_path):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v0", digest="superseded-contract")
    _write_published_portfolio(published, frameworks, "v1")
    _write_published_portfolio(published, frameworks, "v2")

    assert stale_live_versions(frameworks, published) == [], (
        "archived measurements are frozen: a stale archived artifact is never rescored"
    )


def test_bootstrap_adds_live_version_with_a_stale_contract_digest(fixtures, tmp_path):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1")
    _write_published_portfolio(published, frameworks, "v2", digest="superseded-contract")

    selected = select_frameworks(frameworks, cadence="nightly")
    bootstrapped = bootstrap_selection(frameworks, selected, published)

    assert [f.id for f in bootstrapped] == ["v1", "v2"], (
        "v2 is published but was scored against a superseded contract, so it must be "
        "recomputed even though nightly only selects the active version"
    )


def test_cli_bootstraps_live_versions_with_a_stale_published_digest(fixtures, tmp_path):
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)
    changed = tmp_path / "changed.txt"
    changed.write_text("docs/readme.md\n")
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1")
    _write_published_portfolio(published, frameworks, "v2", digest="superseded-contract")

    completed = _run_cli(
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
        "--cadence",
        "changed",
        "--changed-paths-file",
        str(changed),
        "--published-dir",
        str(published),
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert {row["framework_version"] for row in payload["include"]} == {"v2"}


def test_bootstrap_does_not_duplicate_already_selected_versions(fixtures, tmp_path):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"

    selected = select_frameworks(frameworks, cadence="nightly")
    bootstrapped = bootstrap_selection(frameworks, selected, published)

    assert [f.id for f in bootstrapped] == ["v1", "v2"]


# ── Real catalog: matrix size and shape ───────────────────────────────────────


def _real_products() -> list[dict]:
    return [
        yaml.safe_load(path.read_text()) for path in sorted((REPO_ROOT / "products").glob("*.yaml"))
    ]


def test_real_catalog_product_filenames_match_product_ids():
    products_dir = REPO_ROOT / "products"
    for path in sorted(products_dir.glob("*.yaml")):
        product = yaml.safe_load(path.read_text())
        assert path.stem == product["id"], f"{path.name} must match product id {product['id']}"


def _real_expected_row_count(version_ids: set[str]) -> int:
    frameworks = discover_frameworks(REPO_ROOT / "framework" / "versions")
    products = _real_products()
    return sum(
        1
        for framework in frameworks
        if framework.id in version_ids
        for product in products
        if is_in_version(product, frameworks, framework)
    )


def _real_dimension_matrix_size(version_ids: set[str]) -> int:
    """Size the previous (version, product, dimension) matrix, for comparison."""
    frameworks = discover_frameworks(REPO_ROOT / "framework" / "versions")
    products = _real_products()
    return sum(
        len(framework.dimensions["dimensions"])
        for framework in frameworks
        if framework.id in version_ids
        for product in products
        if is_in_version(product, frameworks, framework)
    )


def test_real_catalog_matrix_is_one_job_per_version_and_product():
    """A push/PR touching shared inputs must stay at one job per live version+product."""
    frameworks = discover_frameworks(REPO_ROOT / "framework" / "versions")
    live_ids = {f.id for f in frameworks if f.status.value in ("active", "upcoming")}

    selected = select_frameworks(
        frameworks,
        cadence="changed",
        changed_paths=["scorers/documentation/logic.py"],
    )
    assert {f.id for f in selected} == live_ids

    rows = build_matrix_rows(frameworks, selected, REPO_ROOT / "products")

    expected = _real_expected_row_count(live_ids)
    assert len(rows) == expected
    assert len(rows) == len({(row["framework_version"], row["product"]) for row in rows})
    for row in rows:
        assert set(row) == {"framework_version", "product"}

    assert len(rows) < _real_dimension_matrix_size(live_ids), (
        "the version/product matrix must be strictly smaller than the previous "
        "version/product/dimension matrix"
    )

    assert len(rows) <= 256, (
        f"GitHub Actions refuses a matrix with more than 256 jobs; the real catalog "
        f"produces {len(rows)} rows for live versions {sorted(live_ids)}"
    )


def test_real_catalog_nightly_matrix_covers_only_the_active_version():
    frameworks = discover_frameworks(REPO_ROOT / "framework" / "versions")
    active_ids = {f.id for f in frameworks if f.status.value == "active"}

    selected = select_frameworks(frameworks, cadence="nightly")
    rows = build_matrix_rows(frameworks, selected, REPO_ROOT / "products")

    assert {row["framework_version"] for row in rows} == active_ids
    assert len(rows) == _real_expected_row_count(active_ids)


# ── CLI ───────────────────────────────────────────────────────────────────────


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "engine.workflow_matrix", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_cli_prints_compact_json_matrix_for_nightly(fixtures):
    framework_root, products_dir = fixtures

    completed = _run_cli(
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
        "--cadence",
        "nightly",
    )

    assert completed.returncode == 0, completed.stderr
    assert "\n" not in completed.stdout.strip()
    payload = json.loads(completed.stdout)
    assert set(payload) == {"include"}
    assert {row["framework_version"] for row in payload["include"]} == {"v1"}
    assert all(set(row) == {"framework_version", "product"} for row in payload["include"])


def test_cli_derives_cadence_from_schedule_cron(fixtures):
    framework_root, products_dir = fixtures

    completed = _run_cli(
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
        "--schedule",
        "0 3 * * 1",
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert {row["framework_version"] for row in payload["include"]} == {"v2"}


def test_cli_rejects_unknown_schedule_cron(fixtures):
    framework_root, products_dir = fixtures

    completed = _run_cli(
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
        "--schedule",
        "0 9 * * 3",
    )

    assert completed.returncode != 0
    assert "Unknown schedule cron" in completed.stderr


def test_cli_requires_exactly_one_of_cadence_or_schedule(fixtures):
    framework_root, products_dir = fixtures
    base = [
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
    ]

    neither = _run_cli(*base)
    assert neither.returncode != 0
    assert "exactly one of --cadence or --schedule" in neither.stderr

    both = _run_cli(*base, "--cadence", "nightly", "--schedule", "0 2 * * *")
    assert both.returncode != 0
    assert "exactly one of --cadence or --schedule" in both.stderr


def test_cli_changed_cadence_reads_changed_paths_file(fixtures, tmp_path):
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)
    changed = tmp_path / "changed.txt"
    changed.write_text("framework/versions/v2/dimensions.yaml\n")
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1")
    _write_published_portfolio(published, frameworks, "v2")

    completed = _run_cli(
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
        "--cadence",
        "changed",
        "--changed-paths-file",
        str(changed),
        "--published-dir",
        str(published),
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert {row["framework_version"] for row in payload["include"]} == {"v2"}


def test_cli_bootstraps_live_versions_missing_from_published_dir(fixtures, tmp_path):
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)
    changed = tmp_path / "changed.txt"
    changed.write_text("docs/readme.md\n")
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1")

    completed = _run_cli(
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
        "--cadence",
        "changed",
        "--changed-paths-file",
        str(changed),
        "--published-dir",
        str(published),
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert {row["framework_version"] for row in payload["include"]} == {"v2"}, (
        "an unrelated change selects nothing, but the unpublished live version v2 "
        "must still be bootstrapped"
    )


def test_cli_manual_cadence_requires_framework_version_argument(fixtures):
    framework_root, products_dir = fixtures

    completed = _run_cli(
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
        "--cadence",
        "manual",
    )

    assert completed.returncode != 0
    assert "required" in completed.stderr


def test_cli_rejects_archived_manual_selection(fixtures, tmp_path):
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)
    published = tmp_path / "gh-pages"
    _write_published_portfolio(published, frameworks, "v1")
    _write_published_portfolio(published, frameworks, "v2")

    completed = _run_cli(
        "--framework-root",
        str(framework_root),
        "--products-dir",
        str(products_dir),
        "--cadence",
        "manual",
        "--framework-version",
        "v0",
        "--published-dir",
        str(published),
    )

    assert completed.returncode != 0
    assert "archived" in completed.stderr


def test_schedule_cadences_cover_exactly_two_cadences():
    assert set(SCHEDULE_CADENCES.values()) == {"nightly", "weekly"}
