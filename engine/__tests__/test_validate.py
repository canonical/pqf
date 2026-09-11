"""Tests for engine/validate.py — schema and repository validation."""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from engine.validate import validate_file, validate_repository

_SCHEMAS_DIR = Path(__file__).parent.parent.parent / "config" / "schemas"
_DIM_SCHEMA = json.loads((_SCHEMAS_DIR / "dimensions.schema.json").read_text())
_PROD_SCHEMA = json.loads((_SCHEMAS_DIR / "product.schema.json").read_text())
REPO_ROOT = Path(__file__).parent.parent.parent


def _validate_dict(data: dict, schema: dict) -> list[str]:
    """Validate a plain dict against a schema; return human-readable error messages."""
    validator = jsonschema.Draft7Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = " > ".join(str(p) for p in err.path) or "(root)"
        errors.append(f"  {loc}: {err.message}")
    return errors


@pytest.fixture
def prod_schema():
    return _PROD_SCHEMA


# ── Dimensions schema ─────────────────────────────────────────────────────────


class TestDimensionsSchema:
    def test_missing_required_fields_fail(self, tmp_path):
        bad = {"dimensions": {"my_dim": {"label": "X"}}}
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _DIM_SCHEMA)
        assert any("description" in e or "required" in e for e in errors)

    def test_invalid_dimension_key_fails(self, tmp_path):
        bad = {
            "dimensions": {
                "My-Dim!": {
                    "label": "X",
                    "description": "Y",
                    "scorer": "scorers/x/scorer.py",
                    "outputs": {"val": {"type": "boolean", "label": "V", "description": "D"}},
                    "medals": {"bronze": ["val == true"]},
                }
            }
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _DIM_SCHEMA)
        assert errors

    def test_invalid_output_type_fails(self, tmp_path):
        bad = {
            "dimensions": {
                "my_dim": {
                    "label": "X",
                    "description": "Y",
                    "scorer": "scorers/my_dim/scorer.py",
                    "outputs": {"val": {"type": "integer", "label": "V", "description": "D"}},
                    "medals": {"bronze": ["val == true"]},
                }
            }
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _DIM_SCHEMA)
        assert any("integer" in e or "enum" in e for e in errors)

    def test_invalid_criterion_syntax_fails(self, tmp_path):
        bad = {
            "dimensions": {
                "my_dim": {
                    "label": "X",
                    "description": "Y",
                    "scorer": "scorers/my_dim/scorer.py",
                    "outputs": {"val": {"type": "boolean", "label": "V", "description": "D"}},
                    "medals": {"bronze": ["val is true"]},  # 'is' not a valid operator
                }
            }
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _DIM_SCHEMA)
        assert errors

    def test_empty_criteria_list_fails(self, tmp_path):
        bad = {
            "dimensions": {
                "my_dim": {
                    "label": "X",
                    "description": "Y",
                    "scorer": "scorers/my_dim/scorer.py",
                    "outputs": {"val": {"type": "boolean", "label": "V", "description": "D"}},
                    "medals": {"bronze": []},
                }
            }
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _DIM_SCHEMA)
        assert errors

    def test_scorer_path_must_match_pattern(self, tmp_path):
        bad = {
            "dimensions": {
                "my_dim": {
                    "label": "X",
                    "description": "Y",
                    "scorer": "run_scorer.py",  # wrong path format
                    "outputs": {"val": {"type": "boolean", "label": "V", "description": "D"}},
                    "medals": {"bronze": ["val == true"]},
                }
            }
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _DIM_SCHEMA)
        assert errors


# ── Product schema ────────────────────────────────────────────────────────────


class TestProductSchema:
    def test_all_product_yamls_are_valid(self, tmp_path):
        products_dir = Path(__file__).parent.parent.parent / "products"
        failures = []
        for path in sorted(products_dir.glob("*.yaml")):
            errors = validate_file(path, _PROD_SCHEMA)
            if errors:
                failures.append(f"{path.name}:\n" + "\n".join(errors))
        assert not failures, "Product YAMLs are invalid:\n\n" + "\n\n".join(failures)

    def test_missing_required_fields_fail(self, tmp_path):
        bad = {"name": "Missing ID"}
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _PROD_SCHEMA)
        assert any("id" in e or "required" in e for e in errors)

    def test_invalid_lifecycle_fails(self, tmp_path):
        bad = {
            "id": "my-product",
            "name": "X",
            "lifecycle": "ancient",  # not a valid enum value
            "introduced_in": "v0",
            "targets": {"v0": "bronze", "v1": "bronze"},
            "ownership": {"squad": "team-a"},
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _PROD_SCHEMA)
        assert errors

    def test_invalid_targets_fails(self, tmp_path):
        bad = {
            "id": "my-product",
            "name": "X",
            "lifecycle": "stable",
            "introduced_in": "v0",
            "targets": {"v0": "platinum"},  # not valid
            "ownership": {"squad": "team-a"},
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _PROD_SCHEMA)
        assert errors

    def test_invalid_introduced_in_fails(self, tmp_path):
        bad = {
            "id": "my-product",
            "name": "X",
            "lifecycle": "stable",
            "introduced_in": "version-0",
            "targets": {"v0": "bronze"},
            "ownership": {"squad": "team-a"},
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _PROD_SCHEMA)
        assert errors

    def test_invalid_component_type_fails(self, tmp_path):
        bad = {
            "id": "my-product",
            "name": "X",
            "lifecycle": "stable",
            "introduced_in": "v0",
            "targets": {"v0": "bronze", "v1": "bronze"},
            "ownership": {"squad": "team-a"},
            "components": {
                "foundational": [{"id": "c1", "type": "container", "github_repo": "org/repo"}]
            },
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _PROD_SCHEMA)
        assert errors

    def test_invalid_github_repo_format_fails(self, tmp_path):
        bad = {
            "id": "my-product",
            "name": "X",
            "lifecycle": "stable",
            "introduced_in": "v0",
            "targets": {"v0": "bronze", "v1": "bronze"},
            "ownership": {"squad": "team-a"},
            "components": {
                "foundational": [{"id": "c1", "type": "charm", "github_repo": "just-repo-no-owner"}]
            },
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _PROD_SCHEMA)
        assert errors

    def test_unknown_field_fails(self, tmp_path):
        bad = {
            "id": "my-product",
            "name": "X",
            "lifecycle": "stable",
            "introduced_in": "v0",
            "targets": {"v0": "bronze", "v1": "bronze"},
            "ownership": {"squad": "team-a"},
            "unknown_future_field": "oops",
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _PROD_SCHEMA)
        assert errors


# New product schema test fixtures
ROOT_PRODUCT_VALID = {
    "id": "test-root",
    "product_type": "root",
    "name": "Test Root",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "silver", "v1": "silver"},
    "ownership": {"squad": "emea"},
    "composed_of": [
        {
            "id": "test-charm",
            "product_type": "charm",
            "introduced_in": "v0",
            "source": {"repo": "canonical/test-charm"},
        }
    ],
}

LEAF_PRODUCT_VALID = {
    "id": "test-charm",
    "product_type": "charm",
    "name": "Test Charm",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "silver", "v1": "silver"},
    "ownership": {"squad": "emea"},
    "source": {"repo": "canonical/test-charm"},
}

LEAF_WITH_SUBPATH = {
    "id": "backup-charm",
    "product_type": "charm",
    "name": "Backup Charm",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "bronze", "v1": "bronze"},
    "ownership": {"squad": "emea"},
    "source": {"repo": "canonical/backup-operators", "subpath": "charms/backup"},
}

ROOT_MISSING_PRODUCT_TYPE = {
    "id": "bad",
    "name": "Bad",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "silver", "v1": "silver"},
    "ownership": {"squad": "emea"},
}

LEAF_MISSING_SOURCE = {
    "id": "bad-charm",
    "product_type": "charm",
    "name": "Bad Charm",
    "lifecycle": "stable",
    "introduced_in": "v0",
    "targets": {"v0": "silver", "v1": "silver"},
    "ownership": {"squad": "emea"},
}

ROOT_WITH_SOURCE = {
    **ROOT_PRODUCT_VALID,
    "source": {"repo": "canonical/something"},  # root must NOT have source
}


def test_root_product_valid(prod_schema):
    assert _validate_dict(ROOT_PRODUCT_VALID, prod_schema) == []


def test_leaf_product_valid(prod_schema):
    assert _validate_dict(LEAF_PRODUCT_VALID, prod_schema) == []


def test_leaf_with_subpath_valid(prod_schema):
    assert _validate_dict(LEAF_WITH_SUBPATH, prod_schema) == []


def test_product_type_required(prod_schema):
    errors = _validate_dict(ROOT_MISSING_PRODUCT_TYPE, prod_schema)
    assert any("product_type" in e for e in errors)


def test_root_must_have_composed_of(prod_schema):
    bad = {k: v for k, v in ROOT_PRODUCT_VALID.items() if k != "composed_of"}
    errors = _validate_dict(bad, prod_schema)
    assert any("composed_of" in e for e in errors)


def test_leaf_must_have_source(prod_schema):
    errors = _validate_dict(LEAF_MISSING_SOURCE, prod_schema)
    assert any("source" in e for e in errors)


def test_root_must_not_have_source(prod_schema):
    errors = _validate_dict(ROOT_WITH_SOURCE, prod_schema)
    assert any("source" in e for e in errors)


def test_ref_entry_requires_introduced_in(prod_schema):
    bad = {
        **ROOT_PRODUCT_VALID,
        "composed_of": [{"ref": "test-charm"}],
    }
    errors = _validate_dict(bad, prod_schema)
    assert errors


def _minimal_dimension(
    *,
    medals: dict | None = None,
    required_metrics_for_scoring: list[str] | None = None,
    outputs: dict | None = None,
) -> dict:
    return {
        "test_verification": {
            "label": "Test verification",
            "description": "Automated test health.",
            "scorer": "scorers/test_verification/scorer.py",
            "applies_to": {"product_types": ["charm", "snap"]},
            "aggregation": "worst_in_scope",
            "required_metrics_for_scoring": required_metrics_for_scoring
            or ["latest_build_passing"],
            "outputs": outputs
            or {
                "latest_build_passing": {
                    "implementation": "latest-build-passing/v1",
                    "type": "boolean",
                    "label": "Latest build passing",
                    "description": "Latest CI summary has no failures.",
                }
            },
            "medals": medals or {"bronze": ["latest_build_passing == true"]},
        }
    }


def _minimal_leaf_product(
    *,
    product_id: str = "test-charm",
    introduced_in: str = "v0",
    targets: dict | None = None,
) -> dict:
    return {
        "id": product_id,
        "product_type": "charm",
        "name": "Test Charm",
        "lifecycle": "stable",
        "introduced_in": introduced_in,
        "targets": targets or {"v0": "bronze", "v1": "bronze"},
        "ownership": {"squad": "team-a"},
        "source": {"repo": f"canonical/{product_id}"},
    }


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
        yaml.safe_dump({"dimensions": dimensions or _minimal_dimension()}, sort_keys=False)
    )


def _write_repository_fixture(
    tmp_path: Path,
    *,
    v0_dimensions: dict | None = None,
    v1_dimensions: dict | None = None,
    products: list[dict] | None = None,
) -> tuple[Path, Path]:
    framework_root = tmp_path / "framework" / "versions"
    _write_framework_version(
        framework_root,
        version_id="v0",
        sequence=0,
        status="active",
        dimensions=v0_dimensions,
    )
    _write_framework_version(
        framework_root,
        version_id="v1",
        sequence=1,
        status="upcoming",
        dimensions=v1_dimensions or v0_dimensions,
    )

    products_dir = tmp_path / "products"
    products_dir.mkdir(parents=True)
    for product in products or [_minimal_leaf_product()]:
        (products_dir / f"{product['id']}.yaml").write_text(
            yaml.safe_dump(product, sort_keys=False)
        )
    return framework_root, products_dir


class TestRepositoryValidation:
    def test_live_repository_is_valid_against_framework_snapshots(self):
        errors = validate_repository(REPO_ROOT / "framework" / "versions", REPO_ROOT / "products")
        assert errors == []

    def test_reports_missing_framework_dimensions_snapshot_file(self, tmp_path):
        framework_root = tmp_path / "framework" / "versions"
        version_dir = framework_root / "v0"
        version_dir.mkdir(parents=True)
        (version_dir / "framework.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "v0",
                    "sequence": 0,
                    "label": "PQF V0",
                    "status": "active",
                    "description": "v0 contract",
                },
                sort_keys=False,
            )
        )
        products_dir = tmp_path / "products"
        products_dir.mkdir(parents=True)
        (products_dir / "test-charm.yaml").write_text(
            yaml.safe_dump(_minimal_leaf_product(), sort_keys=False)
        )

        errors = validate_repository(framework_root, products_dir)

        assert any("framework/versions/v0/dimensions.yaml" in error for error in errors)

    def test_reports_orphan_framework_dimensions_snapshot_file(self, tmp_path):
        framework_root = tmp_path / "framework" / "versions"
        version_dir = framework_root / "v0"
        version_dir.mkdir(parents=True)
        (version_dir / "dimensions.yaml").write_text(
            yaml.safe_dump({"dimensions": _minimal_dimension()}, sort_keys=False)
        )
        products_dir = tmp_path / "products"
        products_dir.mkdir(parents=True)
        (products_dir / "test-charm.yaml").write_text(
            yaml.safe_dump(_minimal_leaf_product(), sort_keys=False)
        )

        errors = validate_repository(framework_root, products_dir)

        assert any("framework/versions/v0/framework.yaml" in error for error in errors)

    def test_reports_missing_products_directory(self, tmp_path):
        framework_root, _ = _write_repository_fixture(tmp_path)

        errors = validate_repository(framework_root, tmp_path / "missing-products")

        assert any(
            "missing-products" in error and "missing required products directory" in error
            for error in errors
        )

    def test_reports_dimension_schema_errors_from_framework_snapshots(self, tmp_path):
        framework_root, products_dir = _write_repository_fixture(
            tmp_path,
            v0_dimensions={
                "test_verification": {
                    "label": "Test verification",
                    "description": "Automated test health.",
                    "scorer": "scorers/test_verification/scorer.py",
                    "applies_to": {"product_types": ["charm", "snap"]},
                    "aggregation": "worst_in_scope",
                    "outputs": {
                        "latest_build_passing": {
                            "implementation": "latest-build-passing/v1",
                            "type": "boolean",
                            "label": "Latest build passing",
                            "description": "Latest CI summary has no failures.",
                        }
                    },
                }
            },
        )

        errors = validate_repository(framework_root, products_dir)

        assert any(
            "framework/versions/v0/dimensions.yaml" in error and "medals" in error
            for error in errors
        )

    def test_reports_criteria_that_reference_undeclared_outputs(self, tmp_path):
        framework_root, products_dir = _write_repository_fixture(
            tmp_path,
            v0_dimensions=_minimal_dimension(
                medals={"bronze": ["coverage_pct >= 80"]},
            ),
        )

        errors = validate_repository(framework_root, products_dir)

        assert any(
            "criteria reference undeclared output 'coverage_pct'" in error for error in errors
        )

    def test_reports_required_metrics_that_are_not_declared_outputs(self, tmp_path):
        framework_root, products_dir = _write_repository_fixture(
            tmp_path,
            v0_dimensions=_minimal_dimension(
                required_metrics_for_scoring=["coverage_pct"],
            ),
        )

        errors = validate_repository(framework_root, products_dir)

        assert any(
            "required_metrics_for_scoring references undeclared output 'coverage_pct'" in error
            for error in errors
        )

    def test_reports_unknown_metric_implementation_ids(self, tmp_path):
        framework_root, products_dir = _write_repository_fixture(
            tmp_path,
            v0_dimensions=_minimal_dimension(
                outputs={
                    "latest_build_passing": {
                        "implementation": "latest-build-passing/v99",
                        "type": "boolean",
                        "label": "Latest build passing",
                        "description": "Latest CI summary has no failures.",
                    }
                },
            ),
        )

        errors = validate_repository(framework_root, products_dir)

        assert any(
            "unknown metric implementation 'latest-build-passing/v99'" in error for error in errors
        )

    def test_reports_missing_target_at_product_introduction(self, tmp_path):
        framework_root, products_dir = _write_repository_fixture(
            tmp_path,
            products=[_minimal_leaf_product(targets={"v1": "bronze"})],
        )

        errors = validate_repository(framework_root, products_dir)

        assert any(
            "Missing target declaration at introduced_in boundary v0" in error for error in errors
        )

    def test_reports_invalid_active_composition_edges(self, tmp_path):
        framework_root, products_dir = _write_repository_fixture(
            tmp_path,
            products=[
                {
                    "id": "test-root",
                    "product_type": "root",
                    "name": "Test Root",
                    "lifecycle": "stable",
                    "introduced_in": "v0",
                    "targets": {"v0": "bronze", "v1": "bronze"},
                    "ownership": {"squad": "team-a"},
                    "composed_of": [{"ref": "future-leaf", "introduced_in": "v0"}],
                },
                _minimal_leaf_product(
                    product_id="future-leaf",
                    introduced_in="v1",
                    targets={"v1": "bronze"},
                ),
            ],
        )

        errors = validate_repository(framework_root, products_dir)

        assert any(
            "active composition edge to inactive product 'future-leaf'" in error for error in errors
        )
