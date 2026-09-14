# engine/medal_engine.py
from __future__ import annotations

from engine.aggregation import _compute_result, aggregate_root_dimension, compute_leaf_applicability
from engine.graph import ProductGraph
from engine.models import (
    MEDAL_RANK,
    ApplicabilityOutcome,
    DimensionResult,
    LeafDimensionResult,
    Medal,
    ProductResult,
    Result,
)
from engine.rubric import evaluate_rubric


def _product_result(dimension_results: dict[str, DimensionResult], current_medal: Medal) -> Result:
    """Compute product result from dimension results and current medal."""
    if current_medal != Medal.UNRATED:
        return Result(current_medal.value)

    if any(
        dim.applicability == ApplicabilityOutcome.SCORED and dim.medal == Medal.UNRATED
        for dim in dimension_results.values()
    ):
        return Result.BELOW_MINIMUM

    if any(
        dim.applicability == ApplicabilityOutcome.INSUFFICIENT_DATA
        for dim in dimension_results.values()
    ):
        return Result.INSUFFICIENT_DATA

    if any(
        dim.applicability == ApplicabilityOutcome.NOT_APPLICABLE
        for dim in dimension_results.values()
    ):
        return Result.NOT_APPLICABLE

    return Result.INSUFFICIENT_DATA


def _dimension_meets_target(
    medal: Medal,
    applicability: ApplicabilityOutcome,
    target: Medal,
) -> bool:
    return applicability == ApplicabilityOutcome.SCORED and MEDAL_RANK[medal] >= MEDAL_RANK[target]


def _product_meets_target(
    dimension_results: dict[str, DimensionResult],
    current_medal: Medal,
    target_medal: Medal,
) -> bool:
    if not any(
        dim.applicability == ApplicabilityOutcome.SCORED for dim in dimension_results.values()
    ):
        return False

    if any(
        dim.applicability == ApplicabilityOutcome.INSUFFICIENT_DATA
        for dim in dimension_results.values()
    ):
        return False

    return MEDAL_RANK[current_medal] >= MEDAL_RANK[target_medal]


def compute_leaf_product(
    product_id: str,
    product_type: str,
    leaf_metrics: dict[str, dict],
    dimensions_config: dict,
    target_medal: str,
) -> ProductResult:
    """
    Compute medals for a leaf product (charm/snap) directly from its per-dimension metrics.
    leaf_metrics: {dim_name: {metric_key: value, ...}}
    """
    target = Medal(target_medal)
    dimension_results: dict[str, DimensionResult] = {}

    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        metrics = leaf_metrics.get(dim_name, {})
        applicability = compute_leaf_applicability(product_type, metrics, dim_config)

        if applicability != ApplicabilityOutcome.SCORED:
            dim_medal = Medal.UNRATED
        else:
            dim_medal = evaluate_rubric(metrics, dim_config["medals"])

        dimension_results[dim_name] = DimensionResult(
            medal=dim_medal,
            target=target,
            meets_target=_dimension_meets_target(dim_medal, applicability, target),
            applicability=applicability,
            result=_compute_result(dim_medal, applicability),
            metrics=metrics,
            composition=None,
        )

    scored = [
        result
        for result in dimension_results.values()
        if result.applicability == ApplicabilityOutcome.SCORED
    ]
    current_medal = (
        min(scored, key=lambda result: MEDAL_RANK[result.medal]).medal if scored else Medal.UNRATED
    )

    return ProductResult(
        product_id=product_id,
        current_medal=current_medal,
        target_medal=target,
        meets_target=_product_meets_target(dimension_results, current_medal, target),
        current_result=_product_result(dimension_results, current_medal),
        target_result=Result(target.value),
        dimensions=dimension_results,
    )


def compute_root_product(
    root_id: str,
    graph: ProductGraph,
    all_leaf_results: dict[str, ProductResult],
    dimensions_config: dict,
    target_medal: str,
) -> ProductResult:
    """
    Compute medals for a root product by aggregating composed leaf results.
    all_leaf_results: {leaf_product_id: ProductResult}
    """
    target = Medal(target_medal)
    root_node = graph.nodes[root_id]
    dimension_results: dict[str, DimensionResult] = {}

    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        leaf_dim_results: list[LeafDimensionResult] = []
        for edge in root_node.composed_of:
            leaf_result = all_leaf_results.get(edge.product_id)
            if leaf_result is None:
                continue
            leaf_dim = leaf_result.dimensions.get(dim_name)
            if leaf_dim is None:
                continue
            leaf_node = graph.nodes.get(edge.product_id)
            leaf_dim_results.append(
                LeafDimensionResult(
                    product_id=edge.product_id,
                    repo=leaf_node.source_repo if leaf_node else "",
                    medal=leaf_dim.medal,
                    result=leaf_dim.result,
                    applicability=leaf_dim.applicability,
                    metrics=leaf_dim.metrics,
                    excluded_from_parent_medal=edge.excluded_from_parent_medal,
                )
            )

        dimension_results[dim_name] = aggregate_root_dimension(
            leaf_dim_results,
            dim_config,
            target_medal,
        )

    scored = [
        result
        for result in dimension_results.values()
        if result.applicability == ApplicabilityOutcome.SCORED
    ]
    current_medal = (
        min(scored, key=lambda result: MEDAL_RANK[result.medal]).medal if scored else Medal.UNRATED
    )

    return ProductResult(
        product_id=root_id,
        current_medal=current_medal,
        target_medal=target,
        meets_target=_product_meets_target(dimension_results, current_medal, target),
        current_result=_product_result(dimension_results, current_medal),
        target_result=Result(target.value),
        dimensions=dimension_results,
    )


def compute_product(
    product: dict,
    computed: dict,
    dimensions_config: dict,
) -> ProductResult:
    """
    Compute medals for one product from the legacy unaggregated computed envelope.
    """
    target_medal = Medal(product["target_medal"])
    dimension_results: dict[str, DimensionResult] = {}

    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        metrics = computed.get("metrics", {}).get(dim_name, {})
        required_metrics = dim_config.get("required_metrics_for_scoring", [])
        applicability = ApplicabilityOutcome.SCORED
        if required_metrics and any(
            metrics.get(metric_name) is None for metric_name in required_metrics
        ):
            applicability = ApplicabilityOutcome.INSUFFICIENT_DATA

        if applicability != ApplicabilityOutcome.SCORED:
            dim_medal = Medal.UNRATED
        else:
            dim_medal = evaluate_rubric(metrics, dim_config["medals"])

        dimension_results[dim_name] = DimensionResult(
            medal=dim_medal,
            target=target_medal,
            meets_target=_dimension_meets_target(dim_medal, applicability, target_medal),
            result=_compute_result(dim_medal, applicability),
            metrics=metrics,
            applicability=applicability,
        )

    scored = [
        result
        for result in dimension_results.values()
        if result.applicability == ApplicabilityOutcome.SCORED
    ]
    current_medal = (
        min(scored, key=lambda result: MEDAL_RANK[result.medal]).medal if scored else Medal.UNRATED
    )

    return ProductResult(
        product_id=product["id"],
        current_medal=current_medal,
        target_medal=target_medal,
        meets_target=_product_meets_target(dimension_results, current_medal, target_medal),
        current_result=_product_result(dimension_results, current_medal),
        target_result=Result(target_medal.value),
        dimensions=dimension_results,
    )
