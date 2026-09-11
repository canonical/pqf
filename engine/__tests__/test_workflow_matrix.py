import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from engine.framework import discover_frameworks
from engine.workflow_matrix import build_matrix_rows, select_frameworks

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
    assert {row["dimension"] for row in rows} == {"documentation", "test_verification"}


def test_weekly_selection_returns_only_upcoming_rows(fixtures):
    framework_root, products_dir = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(frameworks, cadence="weekly")
    assert [f.id for f in selected] == ["v2"]

    rows = build_matrix_rows(frameworks, selected, products_dir)
    assert {row["framework_version"] for row in rows} == {"v2"}
    assert {row["product"] for row in rows} == {"matrix", "new-in-v2"}


def test_manual_selection_accepts_active_version(fixtures):
    framework_root, _ = fixtures
    frameworks = discover_frameworks(framework_root)

    selected = select_frameworks(frameworks, cadence="manual", framework_version="v1")
    assert [f.id for f in selected] == ["v1"]


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


def test_cli_prints_compact_json_matrix_for_nightly(fixtures):
    framework_root, products_dir = fixtures

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.workflow_matrix",
            "--framework-root",
            str(framework_root),
            "--products-dir",
            str(products_dir),
            "--cadence",
            "nightly",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert completed.returncode == 0, completed.stderr
    assert "\n" not in completed.stdout.strip()
    payload = json.loads(completed.stdout)
    assert set(payload) == {"include"}
    assert {row["framework_version"] for row in payload["include"]} == {"v1"}


def test_cli_manual_cadence_requires_framework_version_argument(fixtures):
    framework_root, products_dir = fixtures

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.workflow_matrix",
            "--framework-root",
            str(framework_root),
            "--products-dir",
            str(products_dir),
            "--cadence",
            "manual",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert completed.returncode != 0
    assert "required" in completed.stderr


def test_cli_rejects_archived_manual_selection(fixtures):
    framework_root, products_dir = fixtures

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.workflow_matrix",
            "--framework-root",
            str(framework_root),
            "--products-dir",
            str(products_dir),
            "--cadence",
            "manual",
            "--framework-version",
            "v0",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert completed.returncode != 0
    assert "archived" in completed.stderr
