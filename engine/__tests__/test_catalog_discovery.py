from engine.catalog_discovery import (
    build_inventory_report,
    canonical_docs_id,
    normalize_docs_product,
    normalize_pqf_product,
    build_gap_report,
    build_field_mapping_report,
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


def test_build_field_mapping_report_is_source_driven():
    docs_fields = {"id", "service_level", "ownership.squad", "extra_field"}
    pqf_schema_fields = {"id", "target_medal", "documentation_url", "ownership"}
    ui_product_fields = {"id", "target_medal", "squad"}

    mappings = build_field_mapping_report(docs_fields=docs_fields,
                                          pqf_schema_fields=pqf_schema_fields,
                                          ui_product_fields=ui_product_fields)

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
