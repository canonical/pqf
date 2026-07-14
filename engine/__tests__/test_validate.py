"""Tests for engine/validate.py — schema validation of YAML config files."""

import json
from pathlib import Path

import yaml

from engine.validate import validate_file

_SCHEMAS_DIR = Path(__file__).parent.parent.parent / "config" / "schemas"
_DIM_SCHEMA = json.loads((_SCHEMAS_DIR / "dimensions.schema.json").read_text())
_PROD_SCHEMA = json.loads((_SCHEMAS_DIR / "product.schema.json").read_text())


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
