from dataclasses import dataclass
from enum import StrEnum


class Medal(StrEnum):
    UNRATED = "unrated"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


MEDAL_RANK: dict[Medal, int] = {
    Medal.UNRATED: 0,
    Medal.BRONZE: 1,
    Medal.SILVER: 2,
    Medal.GOLD: 3,
}


class ProductType(StrEnum):
    ROOT = "root"
    CHARM = "charm"
    SNAP = "snap"


class ApplicabilityOutcome(StrEnum):
    SCORED = "scored"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class EvaluationUnit:
    """Single leaf product to score — the fundamental unit of computation."""

    product_id: str
    product_type: ProductType
    repo: str
    subpath: str | None = None
    allure_report_url: str = ""
    documentation_url: str = ""
    target_medal: str = "bronze"


@dataclass
class DriftState:
    status: str  # "remediating" | "overdue"
    first_seen_at: str  # ISO 8601 with UTC timezone
    deadline: str  # ISO 8601 with UTC timezone


@dataclass
class DimensionResult:
    medal: Medal
    target: Medal
    metrics: dict
    drift: DriftState | None
    applicability: ApplicabilityOutcome = ApplicabilityOutcome.SCORED
    composition: list["LeafDimensionResult"] | None = None


@dataclass
class LeafDimensionResult:
    """Dimension result for one leaf product inside a root product's composition."""

    product_id: str
    repo: str
    medal: Medal
    applicability: ApplicabilityOutcome
    metrics: dict
    excluded_from_parent_medal: bool = False


@dataclass
class ProductResult:
    product_id: str
    current_medal: Medal
    target_medal: Medal
    dimensions: dict[str, DimensionResult]
