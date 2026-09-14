import json
from pathlib import Path

import pytest

from engine.merge_computed import merge_scorer_outputs

DIMENSIONS = {
    "dimensions": {
        "test_verification": {"outputs": {"coverage_pct": {"implementation": "coverage-pct/v1"}}},
        "documentation": {"outputs": {"has_readme": {"implementation": "readme-present/v1"}}},
    }
}


def _write_scorer_output(root: Path, dimension: str, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{dimension}.json").write_text(json.dumps(payload))


def test_merge_scorer_outputs_adds_version_metadata(tmp_path):
    scorer_dir = tmp_path / "scorers"
    _write_scorer_output(scorer_dir, "test_verification", {"synapse": {"coverage_pct": 75}})
    _write_scorer_output(scorer_dir, "documentation", {"synapse": {"has_readme": True}})

    merged = merge_scorer_outputs(
        product_id="matrix",
        scorer_dir=scorer_dir,
        dimensions_config=DIMENSIONS,
        framework_version="v1",
        contract_digest="digest-sha",
        implementation_fingerprints={"coverage-pct/v1": "abc", "readme-present/v1": "def"},
    )

    assert merged["framework_version"] == "v1"
    assert merged["contract_digest"] == "digest-sha"
    assert merged["implementation_fingerprints"] == {
        "coverage-pct/v1": "abc",
        "readme-present/v1": "def",
    }
    assert merged["product_id"] == "matrix"
    assert merged["leaf_metrics"] == {
        "synapse": {
            "test_verification": {"coverage_pct": 75},
            "documentation": {"has_readme": True},
        }
    }
    assert merged["computed_at"].endswith("+00:00")


def test_merge_scorer_outputs_requires_every_dimension_file(tmp_path):
    scorer_dir = tmp_path / "scorers"
    _write_scorer_output(scorer_dir, "test_verification", {"synapse": {"coverage_pct": 75}})

    with pytest.raises(ValueError, match="Missing scorer output for dimension documentation"):
        merge_scorer_outputs(
            product_id="matrix",
            scorer_dir=scorer_dir,
            dimensions_config=DIMENSIONS,
            framework_version="v1",
            contract_digest="digest-sha",
            implementation_fingerprints={"coverage-pct/v1": "abc"},
        )
