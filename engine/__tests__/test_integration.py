from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_framework_version(
    root: Path,
    *,
    version_id: str,
    sequence: int,
    status: str,
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
        yaml.safe_dump(
            {
                "dimensions": {
                    "test_verification": {
                        "label": "Test verification",
                        "description": "Automated test health.",
                        "scorer": "scorers/test_verification/scorer.py",
                        "applies_to": {"product_types": ["charm"]},
                        "aggregation": "worst_in_scope",
                        "outputs": {
                            "latest_build_passing": {
                                "implementation": "latest-build-passing/v1",
                                "type": "boolean",
                                "label": "Latest build passing",
                                "description": "Latest CI summary has no failures.",
                            }
                        },
                        "medals": {"bronze": ["latest_build_passing == true"]},
                    }
                }
            },
            sort_keys=False,
        )
    )


def _write_product(products_dir: Path) -> None:
    products_dir.mkdir(parents=True, exist_ok=True)
    (products_dir / "matrix.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "matrix",
                "product_type": "root",
                "name": "Matrix",
                "lifecycle": "stable",
                "introduced_in": "v0",
                "targets": {"v0": "gold", "v1": "gold"},
                "ownership": {"squad": "americas"},
                "composed_of": [],
            },
            sort_keys=False,
        )
    )


def _create_temp_project(tmp_path: Path, *, archived_v0: bool = False) -> Path:
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    (project_root / "Makefile").write_text((REPO_ROOT / "Makefile").read_text())
    (project_root / "engine").symlink_to(REPO_ROOT / "engine", target_is_directory=True)
    (project_root / "scorers").symlink_to(REPO_ROOT / "scorers", target_is_directory=True)

    config_dir = project_root / "config"
    config_dir.mkdir()
    (config_dir / "dimensions.yaml").write_text("dimensions: [broken\n")

    framework_root = project_root / "framework" / "versions"
    _write_framework_version(
        framework_root,
        version_id="v0",
        sequence=0,
        status="archived" if archived_v0 else "active",
    )
    _write_framework_version(
        framework_root,
        version_id="v1",
        sequence=1,
        status="active" if archived_v0 else "upcoming",
    )

    _write_product(project_root / "products")
    return project_root


def _run_make(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GITHUB_TOKEN"] = "test-token"
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        ["make", "--no-print-directory", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=env,
    )


def test_versioned_local_commands_require_framework_version(tmp_path):
    project_root = _create_temp_project(tmp_path)

    completed = _run_make(project_root, "_assemble", "SOURCE_REVISION=test-sha")

    assert completed.returncode != 0
    assert "FRAMEWORK_VERSION is required" in completed.stderr


def test_versioned_local_commands_build_selected_portfolios_and_version_index(tmp_path):
    project_root = _create_temp_project(tmp_path)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    listed = subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.framework",
            "--root",
            str(project_root / "framework" / "versions"),
            "--version",
            "v1",
            "--list-dimensions",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=env,
    )

    assert listed.returncode == 0, listed.stderr
    assert listed.stdout.strip() == "test_verification"

    for framework_version in ("v0", "v1"):
        completed = _run_make(
            project_root,
            "score-no-llm",
            "PRODUCT=matrix",
            f"FRAMEWORK_VERSION={framework_version}",
        )
        assert completed.returncode == 0, completed.stderr
        score_path = (
            project_root / ".pqf-score" / framework_version / "matrix" / "test_verification.json"
        )
        assert json.loads(score_path.read_text()) == {}

        completed = _run_make(
            project_root,
            "_merge",
            "PRODUCT=matrix",
            f"FRAMEWORK_VERSION={framework_version}",
        )
        assert completed.returncode == 0, completed.stderr
        assert f"computed/versions/{framework_version}/matrix.json updated" in completed.stdout

        computed_path = project_root / "computed" / "versions" / framework_version / "matrix.json"
        merged = json.loads(computed_path.read_text())
        assert merged["framework_version"] == framework_version
        assert merged["leaf_metrics"] == {}

        completed = _run_make(
            project_root,
            "_assemble",
            f"FRAMEWORK_VERSION={framework_version}",
            "SOURCE_REVISION=test-sha",
        )
        assert completed.returncode == 0, completed.stderr
        assert f"public/versions/{framework_version}/portfolio.json updated" in completed.stdout

        portfolio_path = project_root / "public" / "versions" / framework_version / "portfolio.json"
        portfolio = json.loads(portfolio_path.read_text())
        assert portfolio["framework"]["id"] == framework_version
        assert portfolio["products"][0]["id"] == "matrix"

    completed = _run_make(project_root, "_version-index")

    assert completed.returncode == 0, completed.stderr
    index_path = project_root / "public" / "framework-versions.json"
    index = json.loads(index_path.read_text())
    assert index == {
        "versions": [
            {
                "id": "v0",
                "sequence": 0,
                "label": "PQF V0",
                "status": "active",
                "description": "v0 contract",
                "portfolio_url": "versions/v0/portfolio.json",
                "generated_at": index["versions"][0]["generated_at"],
                "contract_digest": index["versions"][0]["contract_digest"],
            },
            {
                "id": "v1",
                "sequence": 1,
                "label": "PQF V1",
                "status": "upcoming",
                "description": "v1 contract",
                "portfolio_url": "versions/v1/portfolio.json",
                "generated_at": index["versions"][1]["generated_at"],
                "contract_digest": index["versions"][1]["contract_digest"],
            },
        ]
    }


def test_versioned_local_commands_reject_archived_framework_scoring(tmp_path):
    project_root = _create_temp_project(tmp_path, archived_v0=True)

    completed = _run_make(
        project_root,
        "score-no-llm",
        "PRODUCT=matrix",
        "FRAMEWORK_VERSION=v0",
    )

    assert completed.returncode != 0
    assert "Framework version v0 is archived" in completed.stderr
