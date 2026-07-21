"""Catalog discovery normalization primitives.

Contains:
- normalize_docs_product(raw: dict) -> dict
- normalize_pqf_product(raw: dict) -> dict
- canonical_docs_id(raw: dict) -> str
- load_pqf_schema_fields(path: str) -> set[str]
- parse_ui_types_fields(path: str) -> set[str]
"""

import json
import re
from pathlib import Path
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


def build_reverse_usage_graph(products: list[dict]) -> dict[str, set[str]]:
    """Return product_id -> set of product_ids that reference it as a component."""
    product_ids = {p["id"] for p in products if p.get("id")}
    reverse: dict[str, set[str]] = {pid: set() for pid in product_ids}
    for product in products:
        parent_id = product.get("id")
        if not parent_id:
            continue
        for component in product.get("components", []) or []:
            if not isinstance(component, dict):
                continue
            name = component.get("name")
            if not name:
                continue
            child_id = RENAME_MAP.get(name, name)
            if child_id in product_ids and child_id != parent_id:
                reverse.setdefault(child_id, set()).add(parent_id)
    return reverse


def classify_product_role(
    product: dict,
    overrides: dict[str, str] | None = None,
    used_by: set[str] | None = None,
) -> str:
    """Classify a product as 'root' or 'leaf'.

    Deterministic override lookup precedence (highest -> lowest):
      1. exact product id as provided in the product object
      2. canonical id (RENAME_MAP[product_id]) if different
      3. legacy id (inverse of RENAME_MAP) if product_id is the canonical form

    Rules:
    - If an override exists for any of the lookup ids above, the first match
      in the precedence order is used. Only 'root' and 'leaf' (case-insensitive)
      are accepted. Unknown values raise ValueError.
    - Otherwise, products referenced by other products' component lists are
      classified as 'leaf'.
    - Otherwise, if the product has any component with role == 'primary' and
      type in the supported charm/snap types, classify as 'root'.
    - Otherwise classify as 'leaf'.
    """
    overrides = overrides or {}
    used_by = used_by or set()
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

    if used_by:
        return "leaf"

    primary_types = {"k8s-charm", "machine-charm", "subordinate-charm", "snap"}
    components = product.get("components", []) or []
    primary_components = [
        c for c in components if c.get("role") == "primary" and c.get("type") in primary_types
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

    def missing_from_schema(available: set[str]) -> list[str]:
        missing = []
        for f in PUBLIC_TARGET_FIELDS:
            top = f.split(".")[0]
            if f not in available and top not in available:
                missing.append(f)
        return sorted(missing)

    def missing_from_ui(available: set[str]) -> list[str]:
        missing = []
        for f in PUBLIC_TARGET_FIELDS:
            top = f.split(".")[0]
            if f == "ownership.squad":
                if (f not in available) and (top not in available) and ("squad" not in available):
                    missing.append(f)
            elif f not in available and top not in available:
                missing.append(f)
        return sorted(missing)

    schema_missing = missing_from_schema(set(pqf_schema_fields or []))
    ui_missing = missing_from_ui(set(ui_product_fields or []))
    return {"schema_missing_fields": schema_missing, "ui_missing_fields": ui_missing}


def load_pqf_schema_fields(path: str) -> set[str]:
    """Load top-level property names from a PQF product JSON Schema file.

    Returns a set of property names present in the schema's `properties` object.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"pqf schema not found: {path!r}")
    text = p.read_text(encoding="utf-8")
    obj = json.loads(text)
    props = obj.get("properties", {}) or {}
    return set(props.keys())


def parse_ui_types_fields(path: str) -> set[str]:
    """Parse a TypeScript `Product` interface and return its top-level field names.

    The parser is deterministic and tolerant of formatting: it searches for the
    `export interface Product {` token and collects identifiers defined before
    the matching closing brace. Optional properties (ending with `?`) are
    supported. Comments and trailing commas are ignored.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"ui types file not found: {path!r}")
    text = p.read_text(encoding="utf-8")

    # Find the Product interface start
    m = re.search(r"export\s+interface\s+Product\s*\{", text)
    if not m:
        raise ValueError("Product interface not found in UI types file")
    start = m.end()
    fields: set[str] = set()
    depth = 1
    for raw_line in text[start:].splitlines():
        line = re.sub(r"//.*$", "", raw_line).strip()
        if line and depth == 1:
            mprop = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\??\s*:\s*", line)
            if mprop:
                fields.add(mprop.group(1))
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
    return fields


def build_field_mapping_report(
    docs_fields: set[str] | None = None,
    pqf_schema_fields: set[str] | None = None,
    ui_product_fields: set[str] | None = None,
) -> list[dict]:
    """Produce a minimal field mapping report describing how docs fields map to PQF schema and UI.

    This returns a list of mapping entries with keys:
      - source_field: the docs field name
      - pqf_field: mapped pqf schema field (or None)
      - ui_field: mapped ui field (or None)

    The implementation is intentionally conservative and only maps a handful
    of well-known fields used by the PQF importer. When docs_fields is provided
    this function is source-driven and will report mappings for the actual
    docs fields observed (including unmapped/extra fields). An explicit empty
    docs_fields (i.e. set()) is treated as a deliberate source-driven input
    and will produce an empty mapping list.
    """
    docs_provided = docs_fields is not None
    docs_fields = set(docs_fields or [])
    pqf_schema_fields = set(pqf_schema_fields or [])
    ui_product_fields = set(ui_product_fields or [])

    mappings = []
    # canonical mappings from docs -> pqf
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

    # Determine source fields to report: if docs_fields was provided (even if empty),
    # use it verbatim. Otherwise fall back to the known canonical mapping keys.
    source_fields = sorted(docs_fields) if docs_provided else sorted(simple_map.keys())

    # Excluded docs fields that must not be reintroduced into mapping/reporting
    EXCLUDED_DOCS_FIELDS = {"deployments", "communication"}

    for src in source_fields:
        # Skip excluded fields defensively
        if src in EXCLUDED_DOCS_FIELDS:
            continue
        # Skip generic ownership fields; only ownership.squad is allowed
        if src == "ownership" or (src.startswith("ownership.") and src != "ownership.squad"):
            continue

        pqf_field = simple_map.get(src)
        pqf_present = None
        ui_field = None

        if pqf_field:
            # PQF presence may be expressed as the dotted name or the top-level container
            top = pqf_field.split(".")[0]
            # Prefer exact dotted presence for ownership.squad when available
            if pqf_field in pqf_schema_fields:
                pqf_present = pqf_field
            elif top in pqf_schema_fields:
                pqf_present = top

            if pqf_field == "ownership.squad":
                # Prefer ui dotted exposure if present, otherwise top-level 'squad'
                if "ownership.squad" in ui_product_fields:
                    ui_field = "ownership.squad"
                elif "squad" in ui_product_fields:
                    ui_field = "squad"
            else:
                if pqf_field in ui_product_fields:
                    ui_field = pqf_field

        else:
            # No canonical mapping known for this docs field.
            # Detect if UI or PQF happens to contain the same name.
            if src in pqf_schema_fields:
                pqf_present = src
            if src in ui_product_fields:
                ui_field = src

        mappings.append({"source_field": src, "pqf_field": pqf_present, "ui_field": ui_field})

    return mappings
