from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scorers import run  # noqa: E402

FRAMEWORK_ROOT = REPO_ROOT / "framework" / "versions"


def _write_product(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _write_framework_version(
    root: Path,
    *,
    version_id: str,
    sequence: int,
    status: str,
    dimensions: dict | None = None,
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
            dimensions
            or {
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


def test_main_scores_each_leaf_for_selected_dimension(monkeypatch, tmp_path, capsys):
    product = {
        "id": "matrix",
        "product_type": "root",
        "name": "Matrix",
        "lifecycle": "stable",
        "introduced_in": "v0",
        "targets": {"v0": "gold", "v1": "gold"},
        "ownership": {"squad": "americas"},
        "composed_of": [
            {
                "id": "synapse",
                "product_type": "charm",
                "introduced_in": "v0",
                "source": {"repo": "canonical/synapse-operator"},
            },
            {
                "id": "hive",
                "product_type": "charm",
                "introduced_in": "v0",
                "source": {"repo": "canonical/hive-operator"},
            },
        ],
    }
    product_path = _write_product(tmp_path / "matrix.yaml", product)

    calls: list[tuple[str, str]] = []

    def fake_run_dimension(unit, dimension_name, dimension_config, context):
        calls.append((unit.product_id, dimension_name))
        return {
            "latest_build_passing": unit.product_id == "synapse",
            "uses_jubilant": unit.product_id == "hive",
        }

    monkeypatch.setattr(run, "run_dimension", fake_run_dimension)
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    exit_code = run.main(
        [
            "--framework-root",
            str(FRAMEWORK_ROOT),
            "--framework-version",
            "v1",
            "--dimension",
            "test_verification",
            "--product-yaml",
            str(product_path),
            "--products-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "synapse": {
            "latest_build_passing": True,
            "uses_jubilant": False,
        },
        "hive": {
            "latest_build_passing": False,
            "uses_jubilant": True,
        },
    }
    assert calls == [
        ("synapse", "test_verification"),
        ("hive", "test_verification"),
    ]


def test_main_rejects_archived_framework_version(tmp_path, capsys):
    _write_framework_version(tmp_path, version_id="v0", sequence=0, status="archived")
    _write_framework_version(tmp_path, version_id="v1", sequence=1, status="active")
    product_path = _write_product(
        tmp_path / "matrix.yaml",
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
    )

    exit_code = run.main(
        [
            "--framework-root",
            str(tmp_path),
            "--framework-version",
            "v0",
            "--dimension",
            "test_verification",
            "--product-yaml",
            str(product_path),
            "--products-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 1
    assert "archived" in capsys.readouterr().err


def test_main_uses_fixed_dimension_override(monkeypatch, tmp_path, capsys):
    product_path = _write_product(
        tmp_path / "matrix.yaml",
        {
            "id": "matrix",
            "product_type": "root",
            "name": "Matrix",
            "lifecycle": "stable",
            "introduced_in": "v0",
            "targets": {"v0": "gold", "v1": "gold"},
            "ownership": {"squad": "americas"},
            "composed_of": [
                {
                    "id": "synapse",
                    "product_type": "charm",
                    "introduced_in": "v0",
                    "source": {"repo": "canonical/synapse-operator"},
                }
            ],
        },
    )

    def fake_run_dimension(unit, dimension_name, dimension_config, context):
        return {"latest_build_passing": dimension_name == "test_verification"}

    monkeypatch.setattr(run, "run_dimension", fake_run_dimension)
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    exit_code = run.main(
        [
            "--framework-root",
            str(FRAMEWORK_ROOT),
            "--framework-version",
            "v0",
            "--product-yaml",
            str(product_path),
            "--products-dir",
            str(tmp_path),
        ],
        fixed_dimension="test_verification",
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {"synapse": {"latest_build_passing": True}}


@pytest.mark.parametrize(
    ("module_name", "fixed_dimension"),
    [
        ("scorers.test_verification.scorer", "test_verification"),
        ("scorers.documentation.scorer", "documentation"),
        ("scorers.security_ssdlc.scorer", "security_ssdlc"),
        ("scorers.substrate_compat.scorer", "substrate_compat"),
        ("scorers.engagement.scorer", "engagement"),
        ("scorers.support_engagement.scorer", "engagement"),
    ],
)
def test_dimension_wrappers_delegate_to_generic_runner(monkeypatch, module_name, fixed_dimension):
    module = importlib.import_module(module_name)
    captured: dict[str, object] = {}

    def fake_main(argv=None, *, fixed_dimension=None):
        captured["argv"] = argv
        captured["fixed_dimension"] = fixed_dimension
        return 17

    monkeypatch.setattr(module, "run_main", fake_main)

    assert module.main() == 17
    assert captured == {"argv": None, "fixed_dimension": fixed_dimension}
