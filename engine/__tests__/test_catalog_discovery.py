from engine.catalog_discovery import (
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
        "ownership": {"squad": "Platform"},
        "source": "git",
        "lifecycle": "production",
        "composed_of": ["component-a", "component-b"],
        "context_refs": {"jira": "PROJ-1"},
        "documentation_url": "https://docs/myprod",
    }
    normalized = normalize_pqf_product(raw)
    assert normalized["product_type"] == "service"
    assert normalized["ownership"]["squad"] == "Platform"
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


def test_invalid_override_raises():
    from engine.catalog_discovery import classify_product_role

    product = {"id": "foo", "components": []}
    try:
        classify_product_role(product, overrides={"foo": "unknown-role"})
    except ValueError as e:
        assert "invalid override value" in str(e)
    else:
        raise AssertionError("Expected ValueError for invalid override value")
