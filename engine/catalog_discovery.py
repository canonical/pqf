"""Catalog discovery normalization primitives.

Contains:
- normalize_docs_product(raw: dict) -> dict
- normalize_pqf_product(raw: dict) -> dict
- canonical_docs_id(raw: dict) -> str
"""
from typing import Dict, Any

RENAME_MAP = {
    "wordpress": "wordpress-k8s",
}


def canonical_docs_id(raw: Dict[str, Any]) -> str:
    # Use docs product.id as canonical id, with explicit rename handling
    product = raw.get("product", {}) if isinstance(raw, dict) else {}
    pid = product.get("id") or raw.get("id")
    if not pid:
        raise ValueError("missing product id")
    return RENAME_MAP.get(pid, pid)


def normalize_docs_product(raw: Dict[str, Any]) -> Dict[str, Any]:
    product = raw.get("product", {})
    ownership = raw.get("ownership", {})
    normalized = {
        "id": canonical_docs_id(raw),
        "name": product.get("name", product.get("id")),
        "target_medal": product.get("service_level"),
        "summary": product.get("summary", ""),
        "description": product.get("description", ""),
        "squad": (ownership.get("squad") or "").lower(),
        "links": raw.get("links", []),
        "components": raw.get("components", []),
    }
    # Exclude deployments and communication from migration inputs
    return normalized


def normalize_pqf_product(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Minimal normalizer for existing PQF product dicts. Keep documentation_url
    # and links; do not add service_level.
    normalized = {
        "id": raw.get("id"),
        "name": raw.get("name", raw.get("id")),
        "target_medal": raw.get("target_medal"),
        "summary": raw.get("summary", ""),
        "description": raw.get("description", ""),
        "documentation_url": raw.get("documentation_url"),
        "links": raw.get("links", []),
        "components": raw.get("components", []),
    }
    return normalized
