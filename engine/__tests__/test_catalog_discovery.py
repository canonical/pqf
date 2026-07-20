import pytest

from engine.catalog_discovery import normalize_docs_product, canonical_docs_id


def test_normalize_docs_product_maps_service_level_to_target_medal():
    raw = {
        "product": {
            "id": "discourse",
            "name": "Discourse",
            "service_level": "silver",
            "summary": "Forum",
            "description": "Long",
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


def test_canonical_docs_id_rename():
    raw = {"product": {"id": "wordpress"}}
    assert canonical_docs_id(raw) == "wordpress-k8s"
