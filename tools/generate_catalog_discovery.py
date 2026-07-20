#!/usr/bin/env python3
"""Generate PQF product catalog discovery artifact.

Usage:
    tools/generate_catalog_discovery.py \
        --docs-products-dir <dir> \
        --pqf-products-dir <dir> \
        --output <file>

This script loads product descriptors from the given directories (JSON/YAML),
normalizes them using engine.catalog_discovery primitives, and emits a discovery
report JSON with keys: inventory, classification, field_mapping, gaps.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - best-effort YAML support
    yaml = None  # type: ignore

from engine.catalog_discovery import (
    build_field_mapping_report,
    build_gap_report,
    build_inventory_report,
    classify_product_role,
    load_pqf_schema_fields,
    normalize_docs_product,
    normalize_pqf_product,
    parse_ui_types_fields,
)


def load_product_files(d: str) -> list[dict[str, Any]]:
    p = Path(d)
    if not p.exists() or not p.is_dir():
        # Caller-level code should validate existence; return empty to allow
        # best-effort behavior in callers that intentionally want that.
        return []
    products: list[dict[str, Any]] = []
    for f in sorted(p.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".yaml", ".yml", ".json"):
            continue
        try:
            text = f.read_text(encoding="utf-8")
            if f.suffix.lower() == ".json":
                obj = json.loads(text)
            else:
                if yaml:
                    obj = yaml.safe_load(text)
                else:
                    # fallback: try json for yaml files
                    try:
                        obj = json.loads(text)
                    except Exception:
                        # unreadable format -> skip
                        continue
            if isinstance(obj, dict):
                products.append(obj)
        except Exception:
            # ignore individual file errors
            continue
    return products


def infer_docs_fields(docs_products: list[dict[str, Any]]) -> set[str]:
    fields: set[str] = set()
    for raw in docs_products:
        # product.* keys
        product = raw.get("product") if isinstance(raw, dict) else None
        if isinstance(product, dict):
            for k in product.keys():
                fields.add(k)
        # top-level keys
        for k in raw.keys() if isinstance(raw, dict) else []:
            if k == "product":
                continue
            # Exclude non-migration fields that should not be exposed
            if k in ("deployments", "communication"):
                continue
            if k == "ownership":
                # Only expose squad ownership for migration; ignore other ownership
                # metadata to avoid reintroducing internal fields.
                if (
                    isinstance(raw.get("ownership"), dict)
                    and raw.get("ownership").get("squad") is not None
                ):
                    fields.add("ownership.squad")
                else:
                    # Do not add a generic 'ownership' field — it would reintroduce
                    # non-squad ownership details which are excluded by policy.
                    continue
            else:
                fields.add(k)
    return fields


def generate_discovery_report(
    docs_dir: str,
    pqf_dir: str,
    overrides_file: str | None = None,
    pqf_schema_path: str | None = None,
    ui_types_path: str | None = None,
) -> dict[str, Any]:
    # Fail fast if the docs source directory is absent — avoid silently
    # producing an empty artifact that masks missing input.
    docs_path = Path(docs_dir)
    if not docs_path.exists() or not docs_path.is_dir():
        raise FileNotFoundError(f"docs products directory not found: {docs_dir!r}")

    pqf_path = Path(pqf_dir)
    if not pqf_path.exists() or not pqf_path.is_dir():
        raise FileNotFoundError(f"pqf products directory not found: {pqf_dir!r}")

    docs_raw = load_product_files(docs_dir)
    pqf_raw = load_product_files(pqf_dir)

    docs_norm = [normalize_docs_product(r) for r in docs_raw]
    pqf_norm = [normalize_pqf_product(r) for r in pqf_raw]

    inventory = build_inventory_report(docs_norm, pqf_norm)

    # classification: default classify docs-normalized products
    overrides: dict[str, str] = {}
    if overrides_file:
        try:
            text = Path(overrides_file).read_text(encoding="utf-8")
            if overrides_file.endswith(".json"):
                overrides = json.loads(text)
            else:
                if yaml:
                    overrides = yaml.safe_load(text) or {}
        except Exception:
            overrides = {}

    classification: dict[str, str] = {}
    for p in docs_norm:
        classification[p["id"]] = classify_product_role(p, overrides=overrides)

    docs_fields = infer_docs_fields(docs_raw)

    # PQF schema fields: prefer explicit schema file when provided, otherwise
    # fall back to inferring from normalized pqf products.
    pqf_schema_fields: set[str] = set()
    if pqf_schema_path:
        # Prefer explicit schema file; let errors propagate so callers fail fast
        pqf_schema_fields = load_pqf_schema_fields(pqf_schema_path)
    else:
        for p in pqf_norm:
            pqf_schema_fields.update(p.keys())

    # UI product fields: prefer explicit ui types file when provided, otherwise
    # fall back to inferring from normalized pqf products.
    ui_product_fields: set[str] = set()
    if ui_types_path:
        # Prefer explicit UI types file; let errors propagate so callers fail fast
        ui_product_fields = parse_ui_types_fields(ui_types_path)
    else:
        for p in pqf_norm:
            # UI often exposes 'squad' as top-level
            if p.get("squad"):
                ui_product_fields.add("squad")
            ui_product_fields.update(p.keys())

    field_mapping = build_field_mapping_report(
        docs_fields=docs_fields,
        pqf_schema_fields=pqf_schema_fields,
        ui_product_fields=ui_product_fields,
    )

    gaps = build_gap_report(
        pqf_schema_fields=pqf_schema_fields,
        ui_product_fields=ui_product_fields,
    )

    return {
        "inventory": inventory,
        "classification": classification,
        "field_mapping": field_mapping,
        "gaps": gaps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate PQF catalog discovery report",
    )
    parser.add_argument("--docs-products-dir", required=True)
    parser.add_argument("--pqf-products-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--overrides", required=False)
    parser.add_argument(
        "--pqf-schema-path",
        required=False,
        help="Path to PQF product JSON Schema (config/schemas/product.schema.json)",
    )
    parser.add_argument(
        "--ui-types-path",
        required=False,
        help="Path to UI types file (ui/src/types.ts) to parse Product interface",
    )
    args = parser.parse_args(argv)

    try:
        report = generate_discovery_report(
            args.docs_products_dir,
            args.pqf_products_dir,
            args.overrides,
            pqf_schema_path=args.pqf_schema_path,
            ui_types_path=args.ui_types_path,
        )
    except Exception as e:
        # Fail loudly for CI and callers; print helpful message to stderr
        print(f"Error: {e}", flush=True)
        return 2

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote discovery report to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
