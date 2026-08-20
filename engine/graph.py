# engine/graph.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.models import EvaluationUnit, ProductType


@dataclass
class CompositionEdge:
    product_id: str
    excluded_from_parent_medal: bool = False


@dataclass
class ContextRef:
    label: str
    repo: str | None = None


@dataclass
class ProductNode:
    id: str
    product_type: ProductType
    name: str
    target_medal: str | None  # None for inline leaves — they inherit from their parent root
    ownership_squad: str
    source_repo: str | None
    source_subpath: str | None
    allure_report_url: str
    documentation_url: str
    is_inline: bool
    is_portfolio_entry: bool
    lifecycle: str = "stable"
    description: str = ""
    composed_of: list[CompositionEdge] = field(default_factory=list)
    context_refs: list[ContextRef] = field(default_factory=list)
    parent_ids: list[str] = field(default_factory=list)


@dataclass
class ProductGraph:
    nodes: dict[str, ProductNode]  # product_id -> ProductNode


def _node_from_product_dict(d: dict[str, Any]) -> ProductNode:
    source = d.get("source", {})
    return ProductNode(
        id=d["id"],
        product_type=ProductType(d["product_type"]),
        name=d.get("name", d["id"]),
        target_medal=d["target_medal"],
        ownership_squad=d.get("ownership", {}).get("squad", ""),
        source_repo=source.get("repo"),
        source_subpath=source.get("subpath"),
        allure_report_url=d.get("allure_report_url", ""),
        documentation_url=d.get("documentation_url", ""),
        is_inline=False,
        is_portfolio_entry=True,
        lifecycle=d.get("lifecycle", "stable"),
        description=d.get("description", ""),
    )


def _node_from_inline(entry: dict[str, Any], parent_id: str) -> ProductNode:
    if "source" not in entry:
        raise ValueError(f"Inline product {entry.get('id')!r} is missing required 'source' field.")
    source = entry["source"]
    return ProductNode(
        id=entry["id"],
        product_type=ProductType(entry["product_type"]),
        name=entry.get("name", entry["id"]),
        target_medal=None,  # inherited from parent root at evaluation time
        ownership_squad="",
        source_repo=source["repo"],
        source_subpath=source.get("subpath"),
        allure_report_url=entry.get("allure_report_url", ""),
        documentation_url=entry.get("documentation_url", ""),
        is_inline=True,
        is_portfolio_entry=False,
        parent_ids=[parent_id],
    )


def build_graph(product_dicts: list[dict[str, Any]]) -> ProductGraph:
    """
    Build and validate the product graph from parsed product YAML dicts.
    Raises ValueError on duplicate IDs, missing refs, or invalid structure.
    """
    nodes: dict[str, ProductNode] = {}

    # Pass 1: register all top-level products
    for d in product_dicts:
        pid = d["id"]
        if pid in nodes:
            raise ValueError(f"Duplicate product ID: {pid!r}")
        nodes[pid] = _node_from_product_dict(d)

    # Pass 2: wire composition edges and register inline leaves
    for d in product_dicts:
        if d["product_type"] != "root":
            continue
        root_id = d["id"]
        root_node = nodes[root_id]

        for entry in d.get("composed_of", []):
            if "ref" in entry:
                ref_id = entry["ref"]
                if ref_id not in nodes:
                    raise ValueError(
                        f"In product {root_id!r}: ref {ref_id!r} not found. "
                        f"Create products/{ref_id}.yaml or use an inline entry."
                    )
                if root_id not in nodes[ref_id].parent_ids:
                    nodes[ref_id].parent_ids.append(root_id)
                root_node.composed_of.append(
                    CompositionEdge(
                        product_id=ref_id,
                        excluded_from_parent_medal=entry.get("excluded_from_parent_medal", False),
                    )
                )
            else:
                inline_id = entry["id"]
                if inline_id in nodes:
                    raise ValueError(
                        f"Duplicate product ID {inline_id!r}: defined inline in {root_id!r} "
                        f"but already exists as another product."
                    )
                inline_node = _node_from_inline(entry, root_id)
                nodes[inline_id] = inline_node
                root_node.composed_of.append(
                    CompositionEdge(
                        product_id=inline_id,
                        excluded_from_parent_medal=entry.get("excluded_from_parent_medal", False),
                    )
                )

        for cr in d.get("context_refs", []):
            root_node.context_refs.append(ContextRef(label=cr["label"], repo=cr.get("repo")))

    return ProductGraph(nodes=nodes)


def resolve_leaf_units(graph: ProductGraph) -> list[EvaluationUnit]:
    """Return one EvaluationUnit for every leaf (charm/snap) product in the graph."""
    units = []
    for node in graph.nodes.values():
        if node.product_type not in (ProductType.CHARM, ProductType.SNAP):
            continue
        # Inline leaves inherit target from their single parent root
        if node.target_medal is None:
            parent = graph.nodes.get(node.parent_ids[0]) if node.parent_ids else None
            target = parent.target_medal if parent else "bronze"
        else:
            target = node.target_medal
        units.append(
            EvaluationUnit(
                product_id=node.id,
                product_type=node.product_type,
                repo=node.source_repo or "",
                subpath=node.source_subpath,
                allure_report_url=node.allure_report_url,
                documentation_url=node.documentation_url,
                target_medal=target,
            )
        )
    return units


def resolve_leaf_units_for(graph: ProductGraph, root_product_id: str) -> list[EvaluationUnit]:
    """Return EvaluationUnits for leaves that belong to the given root product.

    Inline leaves inherit target_medal from this root. Standalone leaves (resolved
    via ref:) keep their own target_medal for their standalone page, but are scored
    here using their own target since they own their quality accountability.
    """
    root = graph.nodes.get(root_product_id)
    if root is None:
        raise ValueError(f"Product {root_product_id!r} not found in graph.")

    if root.product_type in (ProductType.CHARM, ProductType.SNAP) and not root.composed_of:
        target = root.target_medal if root.target_medal is not None else "bronze"
        return [
            EvaluationUnit(
                product_id=root.id,
                product_type=root.product_type,
                repo=root.source_repo or "",
                subpath=root.source_subpath,
                allure_report_url=root.allure_report_url,
                documentation_url=root.documentation_url,
                target_medal=target,
            )
        ]

    leaf_ids = {edge.product_id for edge in root.composed_of}
    units = []
    for node in graph.nodes.values():
        if node.id not in leaf_ids:
            continue
        if node.product_type not in (ProductType.CHARM, ProductType.SNAP):
            continue
        # Inline leaves have no target of their own — use the root's target
        target = root.target_medal if node.target_medal is None else node.target_medal
        units.append(
            EvaluationUnit(
                product_id=node.id,
                product_type=node.product_type,
                repo=node.source_repo or "",
                subpath=node.source_subpath,
                allure_report_url=node.allure_report_url,
                documentation_url=node.documentation_url,
                target_medal=target,
            )
        )
    return units
