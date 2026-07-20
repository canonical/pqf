import pytest

from engine.catalog_discovery import normalize_docs_product, canonical_docs_id, normalize_pqf_product


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
