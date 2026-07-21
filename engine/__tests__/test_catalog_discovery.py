import json
import subprocess
import sys
from pathlib import Path

from engine.catalog_discovery import (
    build_field_mapping_report,
    build_gap_report,
    build_inventory_report,
    canonical_docs_id,
    normalize_docs_product,
    normalize_pqf_product,
)


def test_normalize_docs_product_maps_service_level_to_target_medal():
    raw = {
        "product": {
            "id": "discourse",
            "name": "Discourse",
            "service_level": "silver",
            "summary": "Forum",
            "description": "Long",
            "documentation_url": "https://docs.example/discourse",
        },
        "ownership": {"squad": "Americas"},
        "links": [{"name": "Charmhub", "url": "https://charmhub.io/discourse-k8s"}],
        "components": [],
        "deployments": [{"environment_name": "prod"}],
        "communication": [{"type": "mattermost", "public": False}],
    }
    normalized = normalize_docs_product(raw)
    assert normalized["id"] == "discourse"
    assert normalized["target_medal"] == "silver"
    assert "deployments" not in normalized
    assert "communication" not in normalized
    # documentation_url should be preserved
    assert normalized["documentation_url"] == "https://docs.example/discourse"


def test_canonical_docs_id_rename():
    raw = {"product": {"id": "wordpress"}}
    assert canonical_docs_id(raw) == "wordpress-k8s"


def test_normalize_pqf_product_preserves_structural_fields():
    raw = {
        "id": "myprod",
        "name": "My Product",
        "target_medal": "bronze",
        "summary": "S",
        "description": "D",
        "product_type": "service",
        # include extra ownership metadata that should be dropped by normalization
        "ownership": {"squad": "Platform", "team_email": "team@canonical.com", "owners": ["alice"]},
        "source": "git",
        "lifecycle": "production",
        "composed_of": ["component-a", "component-b"],
        "context_refs": {"jira": "PROJ-1"},
        "documentation_url": "https://docs/myprod",
    }
    normalized = normalize_pqf_product(raw)
    assert normalized["product_type"] == "service"
    # ownership should only contain squad information
    assert normalized["ownership"] == {"squad": "Platform"}
    assert normalized["squad"] == "Platform"
    assert normalized["source"] == "git"
    assert normalized["lifecycle"] == "production"
    assert normalized["composed_of"] == ["component-a", "component-b"]
    assert normalized["context_refs"]["jira"] == "PROJ-1"
    assert normalized["documentation_url"] == "https://docs/myprod"


def test_inventory_report_detects_missing_and_id_mismatch():
    docs_products = [{"id": "wordpress-k8s"}, {"id": "discourse"}]
    pqf_products = [{"id": "wordpress"}, {"id": "discourse"}]
    report = build_inventory_report(docs_products, pqf_products)
    assert report["missing_in_pqf"] == ["wordpress-k8s"]
    assert report["id_mismatches"] == [{"pqf_id": "wordpress", "docs_id": "wordpress-k8s"}]


def test_classifier_respects_force_leaf_override():
    from engine.catalog_discovery import classify_product_role

    product = {
        "id": "saml-integrator",
        "components": [{"name": "saml-integrator", "role": "primary", "type": "k8s-charm"}],
    }
    role = classify_product_role(product, overrides={"saml-integrator": "leaf"})
    assert role == "leaf"


def test_default_root_classification_without_override():
    from engine.catalog_discovery import classify_product_role

    product = {
        "id": "saml-integrator",
        "components": [{"name": "saml-integrator", "role": "primary", "type": "k8s-charm"}],
    }
    # No overrides provided -> primary charm component should classify as root
    role = classify_product_role(product)
    assert role == "root"


def test_referenced_product_is_leaf_without_override():
    from engine.catalog_discovery import classify_product_role

    product = {
        "id": "saml-integrator",
        "components": [{"name": "saml-integrator", "role": "primary", "type": "k8s-charm"}],
    }
    role = classify_product_role(product, used_by={"matrix"})
    assert role == "leaf"


def test_override_lookup_respects_canonical_id():
    from engine.catalog_discovery import classify_product_role

    # Product uses legacy id 'wordpress' but override is provided for canonical docs id
    product = {"id": "wordpress", "components": []}
    role = classify_product_role(product, overrides={"wordpress-k8s": "root"})
    assert role == "root"


def test_invalid_override_raises():
    from engine.catalog_discovery import classify_product_role

    product = {"id": "foo", "components": []}
    try:
        classify_product_role(product, overrides={"foo": "unknown-role"})
    except ValueError as e:
        assert "invalid override value" in str(e)
    else:
        raise AssertionError("Expected ValueError for invalid override value")


def test_conflicting_override_keys_precedence():
    """When both exact and canonical override keys exist, the exact product id wins."""
    from engine.catalog_discovery import classify_product_role

    product = {"id": "wordpress", "components": []}
    overrides = {"wordpress": "leaf", "wordpress-k8s": "root"}
    role = classify_product_role(product, overrides=overrides)
    assert role == "leaf"


def test_reverse_rename_key_support():
    """A product with canonical id should honor a legacy-keyed override.

    e.g. product id 'wordpress-k8s' should respect overrides keyed as 'wordpress'.
    """
    from engine.catalog_discovery import classify_product_role

    product = {"id": "wordpress-k8s", "components": []}
    role = classify_product_role(product, overrides={"wordpress": "root"})
    assert role == "root"


def test_gap_report_flags_links_as_missing():
    report = build_gap_report(
        pqf_schema_fields={"documentation_url", "ownership", "composed_of"},
        ui_product_fields={"documentation_url", "squad", "composed_of"},
    )
    assert "links" in report["schema_missing_fields"]
    assert "links" in report["ui_missing_fields"]


def test_gap_report_treats_squad_as_equivalent_for_ui_ownership():
    # UI exposes 'squad' as a top-level field; ensure ownership.squad is not
    # reported as missing when 'squad' is present in UI fields.
    report = build_gap_report(
        pqf_schema_fields={"documentation_url", "ownership", "composed_of"},
        ui_product_fields={"documentation_url", "squad", "composed_of"},
    )
    assert "ownership.squad" not in report["ui_missing_fields"]


def test_gap_report_does_not_treat_squad_as_schema_alias():
    report = build_gap_report(
        pqf_schema_fields={"id", "name", "squad", "documentation_url"},
        ui_product_fields={"id", "name", "squad", "documentation_url"},
    )
    assert "ownership.squad" in report["schema_missing_fields"]


def test_build_field_mapping_report_is_source_driven():
    docs_fields = {"id", "service_level", "ownership.squad", "extra_field"}
    pqf_schema_fields = {"id", "target_medal", "documentation_url", "ownership"}
    ui_product_fields = {"id", "target_medal", "squad"}

    mappings = build_field_mapping_report(
        docs_fields=docs_fields,
        pqf_schema_fields=pqf_schema_fields,
        ui_product_fields=ui_product_fields,
    )

    # convert to dict for easy lookup
    by_src = {m["source_field"]: m for m in mappings}

    # service_level should map to target_medal in both PQF and UI
    svc = by_src["service_level"]
    assert svc["pqf_field"] == "target_medal"
    assert svc["ui_field"] == "target_medal"

    # ownership.squad should detect PQF 'ownership' container and UI 'squad'
    own = by_src["ownership.squad"]
    assert own["pqf_field"] == "ownership"
    assert own["ui_field"] == "squad"

    # extra_field has no mapping -> both pqf_field and ui_field should be None
    extra = by_src["extra_field"]
    assert extra["pqf_field"] is None
    assert extra["ui_field"] is None


def test_build_field_mapping_report_leaves_ui_field_empty_when_missing():
    # When the UI does not advertise the mapped field, the report should show
    # it as missing (ui_field is None) rather than pretending it exists.
    docs_fields = {"service_level"}
    pqf_schema_fields = {"id", "target_medal"}
    ui_product_fields = {"id"}  # target_medal missing from UI

    mappings = build_field_mapping_report(
        docs_fields=docs_fields,
        pqf_schema_fields=pqf_schema_fields,
        ui_product_fields=ui_product_fields,
    )
    by_src = {m["source_field"]: m for m in mappings}
    svc = by_src["service_level"]
    assert svc["pqf_field"] == "target_medal"
    assert svc["ui_field"] is None


def test_build_field_mapping_report_respects_explicit_empty_docs_fields():
    # An explicit empty docs_fields set signals a source-driven invocation and
    # should produce an empty mapping list rather than falling back to defaults.
    docs_fields = set()
    pqf_schema_fields = {"id", "target_medal"}
    ui_product_fields = {"id", "target_medal"}

    mappings = build_field_mapping_report(
        docs_fields=docs_fields,
        pqf_schema_fields=pqf_schema_fields,
        ui_product_fields=ui_product_fields,
    )
    assert mappings == []


def test_load_pqf_schema_fields_from_config():
    from engine.catalog_discovery import load_pqf_schema_fields

    fields = load_pqf_schema_fields("config/schemas/product.schema.json")
    # Expect top-level properties from the schema
    assert "id" in fields
    assert "ownership" in fields
    assert "target_medal" in fields


def test_parse_ui_types_fields_from_ui_file():
    from engine.catalog_discovery import parse_ui_types_fields

    fields = parse_ui_types_fields("ui/src/types.ts")
    # Expect several Product interface fields
    assert "id" in fields
    assert "squad" in fields
    assert "dimensions" in fields


def test_parse_ui_types_fields_ignores_nested_object_properties(tmp_path):
    from engine.catalog_discovery import parse_ui_types_fields

    ui_file = tmp_path / "types.ts"
    ui_file.write_text(
        """\
export interface Product {
  id: string
  nested: {
    inner: string
  }
  squad?: string
}
""",
        encoding="utf-8",
    )

    fields = parse_ui_types_fields(str(ui_file))
    assert "id" in fields
    assert "squad" in fields
    assert "inner" not in fields


def test_catalog_discovery_cli_writes_artifact(tmp_path):
    docs_dir = tmp_path / "docs-products"
    pqf_dir = tmp_path / "pqf-products"
    docs_dir.mkdir()
    pqf_dir.mkdir()

    docs_yaml = """\
schema_version: 1.1
product:
  id: discourse
  name: Discourse
  service_level: silver
  summary: test summary
  description: test description
ownership:
  squad: Americas
components: []
deployments: []
communication: []
links: []
"""
    pqf_yaml = """\
id: discourse
product_type: root
name: Discourse
lifecycle: stable
target_medal: silver
ownership:
  squad: americas
composed_of:
  - id: discourse-k8s
    product_type: charm
    source:
      repo: canonical/discourse-k8s-operator
    target_medal: silver
"""
    (docs_dir / "discourse.yaml").write_text(docs_yaml, encoding="utf-8")
    (pqf_dir / "discourse.yaml").write_text(pqf_yaml, encoding="utf-8")

    out_file = tmp_path / "discovery.json"
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "generate_catalog_discovery.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--docs-products-dir",
            str(docs_dir),
            "--pqf-products-dir",
            str(pqf_dir),
            "--pqf-schema-path",
            str(repo_root / "config" / "schemas" / "product.schema.json"),
            "--ui-types-path",
            str(repo_root / "ui" / "src" / "types.ts"),
            "--output",
            str(out_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert out_file.exists()
    report = json.loads(out_file.read_text(encoding="utf-8"))
    assert report["inventory"]["docs_count"] == 1


def test_catalog_discovery_cli_fails_on_non_object_docs_file(tmp_path):
    docs_dir = tmp_path / "docs-products"
    pqf_dir = tmp_path / "pqf-products"
    docs_dir.mkdir()
    pqf_dir.mkdir()

    (docs_dir / "bad.yaml").write_text("- not\n- an\n- object\n", encoding="utf-8")
    (pqf_dir / "ok.yaml").write_text(
        "id: test\nproduct_type: root\nname: Test\nlifecycle: stable\ntarget_medal: bronze\n"
        "ownership:\n  squad: emea\ncomposed_of:\n  - id: leaf\n    product_type: charm\n"
        "    source:\n      repo: canonical/leaf\n    target_medal: bronze\n",
        encoding="utf-8",
    )

    out_file = tmp_path / "discovery.json"
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "generate_catalog_discovery.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--docs-products-dir",
            str(docs_dir),
            "--pqf-products-dir",
            str(pqf_dir),
            "--pqf-schema-path",
            str(repo_root / "config" / "schemas" / "product.schema.json"),
            "--ui-types-path",
            str(repo_root / "ui" / "src" / "types.ts"),
            "--output",
            str(out_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "did not parse to a YAML/JSON object" in completed.stderr
