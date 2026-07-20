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

    Deterministic override lookup precedence (highest -> lowest):
      1. exact product id as provided in the product object
      2. canonical id (RENAME_MAP[product_id]) if different
      3. legacy id (inverse of RENAME_MAP) if product_id is the canonical form

    Rules:
    - If an override exists for any of the lookup ids above, the first match
      in the precedence order is used. Only 'root' and 'leaf' (case-insensitive)
      are accepted. Unknown values raise ValueError.
    - Otherwise, if the product has any component with role == 'primary' and
      type in the supported charm/snap types, classify as 'root'.
    - Otherwise classify as 'leaf'.
    """
    overrides = overrides or {}
    pid = product.get("id")
    if not pid:
        raise ValueError("product id is required for classification")

    # Compute canonical and legacy forms deterministically
    canonical = RENAME_MAP.get(pid, pid)
    # Build inverse map once to find a legacy id that maps to this pid (if any)
    inverse = {v: k for k, v in RENAME_MAP.items()}
    legacy = inverse.get(pid)

    # Ordered precedence list: exact -> canonical (if different) -> legacy (if present)
    lookup_order = [pid]
    if canonical != pid:
        lookup_order.append(canonical)
    if legacy and legacy not in lookup_order:
        lookup_order.append(legacy)

    for lookup in lookup_order:
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


# Public target fields expected across PQF schema and UI product model
PUBLIC_TARGET_FIELDS = {
    "id",
    "name",
    "description",
    "target_medal",
    "ownership.squad",
    "documentation_url",
    "links",
}


def build_gap_report(*, pqf_schema_fields: set[str], ui_product_fields: set[str]) -> dict:
    """Report missing public target fields in the schema and UI.

    Both inputs are sets of top-level field names present in the respective schemas.
    Fields that are nested in the public set (e.g. 'ownership.squad') are considered
    present if either the full dotted name is present in the provided set or the
    top-level container (e.g. 'ownership') is present.
    """
    def missing_from(target_fields: set[str], available: set[str]) -> list[str]:
        missing = []
        for f in PUBLIC_TARGET_FIELDS:
            # if dotted, check either the full dotted name or the top-level key
            top = f.split(".")[0]
            if f not in available and top not in available:
                missing.append(f)
        return sorted(missing)

    schema_missing = missing_from(PUBLIC_TARGET_FIELDS, set(pqf_schema_fields or []))
    ui_missing = missing_from(PUBLIC_TARGET_FIELDS, set(ui_product_fields or []))
    return {"schema_missing_fields": schema_missing, "ui_missing_fields": ui_missing}


def build_field_mapping_report(docs_fields: set[str] | None = None,
                               pqf_schema_fields: set[str] | None = None,
                               ui_product_fields: set[str] | None = None) -> list[dict]:
    """Produce a minimal field mapping report describing how docs fields map to PQF schema and UI.

    This returns a list of mapping entries with keys:
      - source_field: the docs field name
      - pqf_field: mapped pqf schema field (or None)
      - ui_field: mapped ui field (or None)

    The implementation is intentionally conservative and only maps a handful
    of well-known fields used by the PQF importer.
    """
    docs_fields = set(docs_fields or [])
    pqf_schema_fields = set(pqf_schema_fields or [])
    ui_product_fields = set(ui_product_fields or [])

    mappings = []
    # canonical mappings
    simple_map = {
        "id": "id",
        "name": "name",
        "service_level": "target_medal",
        "summary": "summary",
        "description": "description",
        "documentation_url": "documentation_url",
        "links": "links",
        "ownership.squad": "ownership.squad",
        "components": "components",
    }

    for src, pqf_field in simple_map.items():
        ui_field = pqf_field if pqf_field in ui_product_fields else None
        pqf_present = pqf_field if pqf_field in pqf_schema_fields else None
        mappings.append({"source_field": src, "pqf_field": pqf_present, "ui_field": ui_field})

    return mappings

