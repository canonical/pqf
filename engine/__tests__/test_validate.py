"""Tests for engine/validate.py — schema validation of YAML config files."""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from engine.validate import validate_file

_SCHEMAS_DIR = Path(__file__).parent.parent.parent / "config" / "schemas"
_DIM_SCHEMA = json.loads((_SCHEMAS_DIR / "dimensions.schema.json").read_text())
_PROD_SCHEMA = json.loads((_SCHEMAS_DIR / "product.schema.json").read_text())


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
    def test_real_dimensions_yaml_is_valid(self, tmp_path):
        real_path = Path(__file__).parent.parent.parent / "config" / "dimensions.yaml"
        errors = validate_file(real_path, _DIM_SCHEMA)
        assert errors == [], "dimensions.yaml is invalid:\n" + "\n".join(errors)

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
    @pytest.mark.xfail(
        reason="Products not yet migrated to new product_type/source schema (Task 5)",
        strict=False,
    )
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
            "target_medal": "bronze",
            "ownership": {"squad": "team-a"},
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(bad))
        errors = validate_file(p, _PROD_SCHEMA)
        assert errors

    def test_invalid_target_medal_fails(self, tmp_path):
        bad = {
            "id": "my-product",
            "name": "X",
            "lifecycle": "stable",
            "target_medal": "platinum",  # not valid
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
            "target_medal": "bronze",
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
            "target_medal": "bronze",
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
            "target_medal": "bronze",
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
    "target_medal": "silver",
    "ownership": {"squad": "emea"},
    "composed_of": [
        {
            "id": "test-charm",
            "product_type": "charm",
            "source": {"repo": "canonical/test-charm"},
            "target_medal": "silver",
        }
    ],
}

LEAF_PRODUCT_VALID = {
    "id": "test-charm",
    "product_type": "charm",
    "name": "Test Charm",
    "lifecycle": "stable",
    "target_medal": "silver",
    "ownership": {"squad": "emea"},
    "source": {"repo": "canonical/test-charm"},
}

LEAF_WITH_SUBPATH = {
    "id": "backup-charm",
    "product_type": "charm",
    "name": "Backup Charm",
    "lifecycle": "stable",
    "target_medal": "bronze",
    "ownership": {"squad": "emea"},
    "source": {"repo": "canonical/backup-operators", "subpath": "charms/backup"},
}

ROOT_MISSING_PRODUCT_TYPE = {
    "id": "bad",
    "name": "Bad",
    "lifecycle": "stable",
    "target_medal": "silver",
    "ownership": {"squad": "emea"},
}

LEAF_MISSING_SOURCE = {
    "id": "bad-charm",
    "product_type": "charm",
    "name": "Bad Charm",
    "lifecycle": "stable",
    "target_medal": "silver",
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
