from __future__ import annotations

import json
from pathlib import Path

import yaml

from scorers import batch, registry


def _write_framework(root: Path, version_id: str, sequence: int, outputs: dict) -> None:
    version_dir = root / version_id
    version_dir.mkdir(parents=True)
    (version_dir / "framework.yaml").write_text(
        yaml.safe_dump(
            {
                "id": version_id,
                "sequence": sequence,
                "label": version_id,
                "status": "active" if version_id == "v1" else "upcoming",
                "description": version_id,
            }
        )
    )
    (version_dir / "dimensions.yaml").write_text(
        yaml.safe_dump(
            {
                "dimensions": {
                    "test_verification": {
                        "label": "Tests",
                        "description": "Tests",
                        "scorer": "scorers/test_verification/scorer.py",
                        "applies_to": {"product_types": ["charm"]},
                        "aggregation": "worst_in_scope",
                        "outputs": outputs,
                        "medals": {"bronze": ["latest_build_passing == true"]},
                    }
                }
            }
        )
    )


def _output(implementation: str) -> dict:
    return {
        "implementation": implementation,
        "type": "boolean",
        "label": implementation,
        "description": implementation,
    }


def test_batch_scores_versions_with_shared_cache_and_preserves_artifact_names(
    monkeypatch, tmp_path
):
    framework_root = tmp_path / "framework"
    _write_framework(
        framework_root,
        "v1",
        1,
        {"latest_build_passing": _output("latest-build-passing/v1")},
    )
    _write_framework(
        framework_root,
        "v2",
        2,
        {
            "latest_build_passing": _output("latest-build-passing/v1"),
            "integration_test_evidence_present": _output("integration-test-evidence-present/v1"),
        },
    )
    products_dir = tmp_path / "products"
    products_dir.mkdir()
    product_path = products_dir / "demo.yaml"
    product_path.write_text(
        yaml.safe_dump(
            {
                "id": "demo",
                "product_type": "charm",
                "name": "Demo",
                "introduced_in": "v1",
                "source": {"repo": "canonical/demo"},
                "targets": {"v1": "bronze"},
            }
        )
    )
    output_dir = tmp_path / "output"
    calls = 0

    def fake_runner(unit, context):
        nonlocal calls
        calls += 1
        return {
            "latest_build_passing": True,
            "integration_test_evidence_present": False,
        }

    monkeypatch.setattr(
        registry,
        "RUNNERS",
        {**registry.RUNNERS, "test_verification": fake_runner},
    )
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    result = batch.main(
        [
            "--framework-root",
            str(framework_root),
            "--framework-versions-json",
            '["v1","v2"]',
            "--product-yaml",
            str(product_path),
            "--products-dir",
            str(products_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert calls == 1
    assert sorted(path.name for path in output_dir.glob("*.json")) == [
        "v1__demo__test_verification.json",
        "v2__demo__test_verification.json",
    ]
    assert json.loads((output_dir / "v1__demo__test_verification.json").read_text()) == {
        "demo": {"latest_build_passing": True}
    }
    assert json.loads((output_dir / "v2__demo__test_verification.json").read_text()) == {
        "demo": {
            "integration_test_evidence_present": False,
            "latest_build_passing": True,
        }
    }
