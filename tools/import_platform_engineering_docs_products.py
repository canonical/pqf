#!/usr/bin/env python3
"""Temporary migration helper to import docs products into PQF product YAMLs.

This script is intentionally outside the engine because it performs one-off
data migration from platform-engineering-docs into this repository. Remove it
after cutover once internal docs consume PQF as source of truth.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

SCORABLE_TYPES = {
    "k8s-charm": "charm",
    "machine-charm": "charm",
    "subordinate-charm": "charm",
    "snap": "snap",
}

COMPONENT_SOURCE_OVERRIDES: dict[tuple[str, str], dict[str, str]] = {
    ("mattermost", "mattermost"): {"repo": "canonical/mattermost-k8s-operator"},
}


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", (text or "").strip().lower())
    return re.sub(r"-{2,}", "-", value).strip("-")


def _parse_github_source(url: str) -> dict[str, str] | None:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    source: dict[str, str] = {"repo": f"{parts[0]}/{parts[1]}"}
    if len(parts) >= 5 and parts[2] in {"tree", "blob"}:
        subpath = "/".join(parts[4:]).strip("/")
        if subpath:
            source["subpath"] = subpath
    return source


def _resolve_component_source(product_id: str, component: dict) -> dict[str, str] | None:
    key = (product_id, _slug(str(component.get("name") or "")))
    override = COMPONENT_SOURCE_OVERRIDES.get(key)
    if override:
        return dict(override)
    return _parse_github_source(str(component.get("repository") or ""))


def _pick_documentation_url(raw: dict) -> str | None:
    product = raw.get("product", {})
    doc_url = product.get("documentation_url") or raw.get("documentation_url")
    if doc_url:
        return str(doc_url)
    links = raw.get("links") or []
    for link in links:
        if not isinstance(link, dict):
            continue
        name = str(link.get("name") or "").lower()
        url = str(link.get("url") or "")
        if not url:
            continue
        if any(k in name for k in ("documentation", "docs", "readme")):
            return url
        if "documentation." in url or "charmhub.io" in url:
            return url
    for link in links:
        if isinstance(link, dict) and link.get("url"):
            return str(link["url"])
    return None


def _build_inline_components(
    product_id: str,
    target_medal: str,
    components: list[dict],
) -> tuple[list[dict], list[dict]]:
    composed_of: list[dict] = []
    context_refs: list[dict] = []
    seen_inline_ids: set[str] = set()
    seen_context: set[tuple[str, str | None]] = set()

    scorable_candidates: list[dict] = []
    for component in components:
        component_type = component.get("type")
        source = _resolve_component_source(product_id, component)
        if component_type in SCORABLE_TYPES and source:
            scorable_candidates.append(component)

    preferred = [
        c
        for c in scorable_candidates
        if str(c.get("role") or "").strip().lower() in {"primary", "secondary"}
    ]
    selected_for_composed = preferred or scorable_candidates[:1]

    selected_ids = {id(c) for c in selected_for_composed}
    for component in components:
        component_type = component.get("type")
        source = _resolve_component_source(product_id, component)
        name = str(component.get("name") or "component")
        if id(component) in selected_ids and component_type in SCORABLE_TYPES and source:
            base_id = f"{product_id}-{_slug(name)}"
            inline_id = base_id
            if inline_id in seen_inline_ids:
                inline_id = f"{base_id}-{SCORABLE_TYPES[component_type]}"
            idx = 2
            while inline_id in seen_inline_ids:
                inline_id = f"{base_id}-{idx}"
                idx += 1
            seen_inline_ids.add(inline_id)
            composed_of.append(
                {
                    "id": inline_id,
                    "product_type": SCORABLE_TYPES[component_type],
                    "source": source,
                    "target_medal": target_medal,
                }
            )
            continue

        label = name.replace("-", " ").strip().title() or "Dependency"
        repo = source.get("repo") if source else None
        context_key = (label, repo)
        if context_key in seen_context:
            continue
        seen_context.add(context_key)
        ref: dict[str, str] = {"label": label}
        if repo:
            ref["repo"] = repo
        context_refs.append(ref)

    return composed_of, context_refs


def _convert_docs_product(raw: dict) -> tuple[str, dict]:
    product = raw.get("product", {})
    product_id = _slug(str(product.get("id") or ""))
    if not product_id:
        raise ValueError("product.id is required")
    target_medal = str(product.get("service_level") or "bronze").strip().lower()
    if target_medal not in {"bronze", "silver", "gold"}:
        target_medal = "bronze"
    name = str(product.get("name") or product_id)
    summary = str(product.get("summary") or "").strip()
    description = str(product.get("description") or "").strip() or summary or name
    ownership = raw.get("ownership") or {}
    squad = str(ownership.get("squad") or "unknown").strip().lower()
    stakeholders = [
        str(item.get("name"))
        for item in (ownership.get("stakeholders") or [])
        if isinstance(item, dict) and item.get("name")
    ]
    documentation_url = _pick_documentation_url(raw)
    composed_of, context_refs = _build_inline_components(
        product_id=product_id,
        target_medal=target_medal,
        components=list(raw.get("components") or []),
    )
    if not composed_of:
        raise ValueError(f"{product_id}: no scorable components with GitHub repositories found")

    entry: dict = {
        "id": product_id,
        "product_type": "root",
        "name": name,
        "description": description,
        "lifecycle": "stable",
        "target_medal": target_medal,
        "ownership": {"squad": squad},
        "composed_of": composed_of,
    }
    if stakeholders:
        entry["ownership"]["stakeholders"] = stakeholders
    if documentation_url:
        entry["documentation_url"] = documentation_url
    if context_refs:
        entry["context_refs"] = context_refs
    return product_id, entry


def _load_docs_products(path: Path) -> list[dict]:
    products: list[dict] = []
    for f in sorted(path.iterdir()):
        if f.suffix.lower() not in {".yaml", ".yml"} or not f.is_file():
            continue
        if f.name in {"schema.yaml", "template.yaml"}:
            continue
        products.append(yaml.safe_load(f.read_text(encoding="utf-8")) or {})
    return products


def _write_yaml(path: Path, payload: dict) -> None:
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import docs product YAMLs into PQF products/")
    parser.add_argument("--docs-products-dir", required=True)
    parser.add_argument("--output-dir", default="products")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)

    docs_dir = Path(args.docs_products_dir)
    output_dir = Path(args.output_dir)
    if not docs_dir.exists() or not docs_dir.is_dir():
        print(f"Error: docs products directory not found: {docs_dir}", file=sys.stderr, flush=True)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.clean:
        for existing in output_dir.glob("*.yaml"):
            existing.unlink()

    try:
        imported = 0
        for raw in _load_docs_products(docs_dir):
            product_id, converted = _convert_docs_product(raw)
            _write_yaml(output_dir / f"{product_id}.yaml", converted)
            imported += 1
        print(f"Imported {imported} products into {output_dir}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
