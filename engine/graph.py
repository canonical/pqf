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
    target_medal: str
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
    source = entry["source"]
    return ProductNode(
        id=entry["id"],
        product_type=ProductType(entry["product_type"]),
        name=entry.get("name", entry["id"]),
        target_medal=entry["target_medal"],
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
    return [
        EvaluationUnit(
            product_id=node.id,
            product_type=node.product_type,
            repo=node.source_repo or "",
            subpath=node.source_subpath,
            allure_report_url=node.allure_report_url,
            documentation_url=node.documentation_url,
            target_medal=node.target_medal,
        )
        for node in graph.nodes.values()
        if node.product_type in (ProductType.CHARM, ProductType.SNAP)
    ]
