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
)


def compute_leaf_applicability(
    product_type: str,
    metrics: dict[str, Any],
    dim_config: dict[str, Any],
) -> ApplicabilityOutcome:
    """Determine if this dimension applies to this product type and has data."""
    applies_to_cfg = dim_config.get("applies_to")
    if applies_to_cfg is not None:
        applies_to = applies_to_cfg.get("product_types", [])
        if product_type not in applies_to:
            return ApplicabilityOutcome.NOT_APPLICABLE
    if not metrics:
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
            metrics={},
            drift=None,
            composition=list(leaf_results),
        )

    worst = min(in_scope, key=lambda r: MEDAL_RANK[r.medal])

    return DimensionResult(
        medal=worst.medal,
        target=target,
        applicability=ApplicabilityOutcome.SCORED,
        metrics={},
        drift=None,  # root drift tracked by assemble.py after full assembly
        composition=list(leaf_results),
    )
