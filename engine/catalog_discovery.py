"""Catalog discovery normalization primitives.

Contains:
- normalize_docs_product(raw: dict) -> dict
- normalize_pqf_product(raw: dict) -> dict
- canonical_docs_id(raw: dict) -> str
"""
from typing import Any

RENAME_MAP = {
    "wordpress": "wordpress-k8s",
}


def canonical_docs_id(raw: dict[str, Any]) -> str:
    # Use docs product.id as canonical id, with explicit rename handling
    product = raw.get("product", {}) if isinstance(raw, dict) else {}
    product_id = product.get("id") or raw.get("id")
    if not product_id:
        raise ValueError("missing product id")
    return RENAME_MAP.get(product_id, product_id)


def normalize_docs_product(raw: dict[str, Any]) -> dict[str, Any]:
    product = raw.get("product", {})
    ownership = raw.get("ownership", {})
    # Try to preserve a top-level documentation_url if present on product or root
    doc_url = product.get("documentation_url") or raw.get("documentation_url")
    if not doc_url:
        # fallback: look for a link named docs/documentation/readme
        for link in raw.get("links", []):
            name = (link.get("name") or "").lower()
            if name in ("documentation", "docs", "readme") and link.get("url"):
                doc_url = link.get("url")
                break

    normalized = {
        "id": canonical_docs_id(raw),
        "name": product.get("name", product.get("id")),
        "target_medal": product.get("service_level"),
        "summary": product.get("summary", ""),
        "description": product.get("description", ""),
        "squad": (ownership.get("squad") or "").lower(),
        "documentation_url": doc_url,
        "links": raw.get("links", []),
        "components": raw.get("components", []),
    }
    # Exclude deployments and communication from migration inputs
    return normalized


def normalize_pqf_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize an existing PQF product dict while preserving structural
    fields required for inventory and classification.

    Preserved fields: product_type, ownership (and ownership.squad), source,
    lifecycle, composed_of, context_refs, documentation_url, links, components.
    """
    ownership = raw.get("ownership") or {}
    # Only retain squad ownership details; drop other ownership metadata.
    ownership_reduced = {"squad": ownership.get("squad")} if ownership else None

    normalized = {
        "id": raw.get("id"),
        "name": raw.get("name", raw.get("id")),
        "target_medal": raw.get("target_medal"),
        "summary": raw.get("summary", ""),
        "description": raw.get("description", ""),
        # structural fields preserved for later inventory/classification
        "product_type": raw.get("product_type"),
        # Expose only squad ownership to avoid leaking other internal details
        "ownership": ownership_reduced,
        "squad": ownership.get("squad") if ownership else None,
        "source": raw.get("source"),
        "lifecycle": raw.get("lifecycle"),
        "composed_of": raw.get("composed_of"),
        "context_refs": raw.get("context_refs"),
        "documentation_url": raw.get("documentation_url"),
        "links": raw.get("links", []),
        "components": raw.get("components", []),
    }
    return normalized


def build_inventory_report(docs_products: list[dict], pqf_products: list[dict]) -> dict:
    """Build inventory diff report between normalized docs products and PQF products.

    Report keys:
      - docs_count: number of unique docs ids
      - pqf_count: number of unique pqf ids
      - missing_in_pqf: list of docs ids not present in PQF
      - overlap: list of ids present in both
      - id_mismatches: list of mappings where PQF uses an old id that should
        map to a docs id (e.g. pqf_id: "wordpress", docs_id: "wordpress-k8s").
    """
    docs_ids = {p["id"] for p in docs_products}
    pqf_ids = {p["id"] for p in pqf_products}

    missing = sorted(docs_ids - pqf_ids)
    overlap = sorted(docs_ids & pqf_ids)

    # Detect id mismatches using the rename map: if a pqf id is an old name
    # that maps to a docs id, and the docs id is present but pqf id is not
    # listed as the canonical id, report the mismatch.
    id_mismatches = []
    # Build inverse mapping: old_name -> new_name (already RENAME_MAP maps old->new)
    for old_name, new_name in RENAME_MAP.items():
        if new_name in docs_ids and old_name in pqf_ids and new_name not in pqf_ids:
            id_mismatches.append({"pqf_id": old_name, "docs_id": new_name})

    return {
        "docs_count": len(docs_ids),
        "pqf_count": len(pqf_ids),
        "missing_in_pqf": missing,
        "overlap": overlap,
        "id_mismatches": id_mismatches,
    }


def classify_product_role(product: dict, overrides: dict[str, str] | None = None) -> str:
    """Classify a product as 'root' or 'leaf'.

    Rules:
    - If an override exists for product['id'], validate and return it.
      Only the contract values 'root' and 'leaf' (case-insensitive) are accepted.
      Known case variants are normalized to lowercase. Unknown values raise ValueError.
    - Otherwise, if the product has any component with role == 'primary' and
      type in the supported charm/snap types, classify as 'root'.
    - Otherwise classify as 'leaf'.
    """
    overrides = overrides or {}
    pid = product.get("id")
    # Support canonicalized ids for override lookups so mappings like
    # 'wordpress' -> 'wordpress-k8s' are respected regardless of which form
    # appears in the overrides dict. Check both the raw id and its canonical
    # mapping from RENAME_MAP.
    lookup_ids = {pid, RENAME_MAP.get(pid, pid)}
    for lookup in lookup_ids:
        if lookup in overrides:
            raw_val = overrides[lookup]
            if not isinstance(raw_val, str):
                raise TypeError(f"override for {lookup!r} must be a string")
            val = raw_val.strip().lower()
            if val in ("root", "leaf"):
                return val
            raise ValueError(
                f"invalid override value for {lookup!r}: {raw_val!r}; expected 'root' or 'leaf'"
            )

    primary_types = {"k8s-charm", "machine-charm", "subordinate-charm", "snap"}
    components = product.get("components", []) or []
    primary_components = [
        c
        for c in components
        if c.get("role") == "primary" and c.get("type") in primary_types
    ]
    return "root" if primary_components else "leaf"
