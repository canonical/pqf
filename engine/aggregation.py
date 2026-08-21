# engine/aggregation.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from engine.models import (
    MEDAL_RANK,
    ApplicabilityOutcome,
    DimensionResult,
    LeafDimensionResult,
    Medal,
    Result,
    Status,
)


def _compute_result(medal: Medal, applicability: ApplicabilityOutcome) -> Result:
    """
    Map (medal, applicability) pair to canonical result.

    Hierarchy:
    1. If not_applicable → result = not_applicable
    2. If insufficient_data → result = insufficient_data
    3. If scored and medal is unrated → result = below_minimum
    4. Otherwise, result matches medal value (gold/silver/bronze)
    """
    match applicability:
        case ApplicabilityOutcome.NOT_APPLICABLE:
            return Result.NOT_APPLICABLE
        case ApplicabilityOutcome.INSUFFICIENT_DATA:
            return Result.INSUFFICIENT_DATA
        case ApplicabilityOutcome.SCORED:
            if medal == Medal.UNRATED:
                return Result.BELOW_MINIMUM
            return Result(medal.value)


def _dimension_status(medal: Medal, applicability: ApplicabilityOutcome) -> Status:
    if applicability == ApplicabilityOutcome.NOT_APPLICABLE:
        return Status.NOT_APPLICABLE
    if applicability == ApplicabilityOutcome.INSUFFICIENT_DATA:
        return Status.INSUFFICIENT_DATA
    if medal == Medal.UNRATED:
        return Status.BELOW_MINIMUM
    return Status(medal.value)


def compute_leaf_applicability(
    product_type: str | None,
    metrics: dict[str, Any],
    dim_config: dict[str, Any],
) -> ApplicabilityOutcome:
    """Determine if this dimension applies to this product type and has data."""
    applies_to_cfg = dim_config.get("applies_to")
    if applies_to_cfg is not None and product_type is not None:
        applies_to = applies_to_cfg.get("product_types", [])
        if product_type not in applies_to:
            return ApplicabilityOutcome.NOT_APPLICABLE
    if not metrics:
        return ApplicabilityOutcome.INSUFFICIENT_DATA
    required_metrics = dim_config.get("required_metrics_for_scoring", [])
    if any(metrics.get(metric_name) is None for metric_name in required_metrics):
        return ApplicabilityOutcome.INSUFFICIENT_DATA
    return ApplicabilityOutcome.SCORED


def aggregate_root_dimension(
    leaf_results: list[LeafDimensionResult],
    dim_config: dict[str, Any],
    drift_history: dict,
    product_id: str,
    target_medal: str,
    now: datetime | None,
) -> DimensionResult:
    """
    Aggregate per-leaf dimension results into a root DimensionResult.
    Rule: minimum medal among in-scope (not excluded, scored) leaves.
    """
    target = Medal(target_medal)

    in_scope = [
        r
        for r in leaf_results
        if not r.excluded_from_parent_medal and r.applicability == ApplicabilityOutcome.SCORED
    ]

    if not in_scope:
        all_na = not leaf_results or all(
            r.applicability == ApplicabilityOutcome.NOT_APPLICABLE for r in leaf_results
        )
        applicability = (
            ApplicabilityOutcome.NOT_APPLICABLE
            if all_na
            else ApplicabilityOutcome.INSUFFICIENT_DATA
        )
        return DimensionResult(
            medal=Medal.UNRATED,
            target=target,
            applicability=applicability,
            result=_compute_result(Medal.UNRATED, applicability),
            metrics={},
            drift=None,
            composition=list(leaf_results),
        )

    worst = min(in_scope, key=lambda r: MEDAL_RANK[r.medal])

    return DimensionResult(
        medal=worst.medal,
        target=target,
        applicability=ApplicabilityOutcome.SCORED,
        result=_compute_result(worst.medal, ApplicabilityOutcome.SCORED),
        metrics={},
        drift=None,  # root drift tracked by assemble.py after full assembly
        composition=list(leaf_results),
    )
