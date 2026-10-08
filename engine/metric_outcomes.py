"""The shared measurement result used by scorers, scoring and artifact consumers."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

METRIC_SCHEMA_VERSION = 1


class MetricState(StrEnum):
    MEASURED = "measured"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_APPLICABLE = "not_applicable"


MetricScalar = str | int | float | bool


@dataclass(frozen=True)
class MetricOutcome:
    state: MetricState
    value: MetricScalar | None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, MetricState):
            raise ValueError("Metric state must be a MetricState.")
        if self.reason is not None and (
            not isinstance(self.reason, str) or not self.reason.strip()
        ):
            raise ValueError("Metric reason must be a non-empty string.")
        if self.state == MetricState.MEASURED:
            if not isinstance(self.value, (str, int, float, bool)):
                raise ValueError("Measured metric value must be a scalar.")
            if isinstance(self.value, float) and not isfinite(self.value):
                raise ValueError("Measured metric value must be finite.")
        elif self.value is not None or self.reason is None:
            raise ValueError("Non-measured metrics require a null value and a reason.")


def measured(value: MetricScalar) -> MetricOutcome:
    return MetricOutcome(MetricState.MEASURED, value)


def not_applicable(reason: str) -> MetricOutcome:
    return MetricOutcome(MetricState.NOT_APPLICABLE, None, reason)


def insufficient_data(reason: str) -> MetricOutcome:
    return MetricOutcome(MetricState.INSUFFICIENT_DATA, None, reason)


def parse_metric_outcome(
    raw: object, output_config: dict[str, Any], *, metric_key: str
) -> MetricOutcome:
    """Validate a JSON measurement against its declared contract value type."""
    try:
        if not isinstance(raw, dict):
            raise ValueError("Metric result must be an object.")
        if set(raw) - {"state", "value", "reason"}:
            raise ValueError("Metric result contains unknown fields.")
        if "state" not in raw or "value" not in raw:
            raise ValueError("Metric result requires state and value.")
        state = raw["state"]
        if not isinstance(state, str):
            raise ValueError("Metric state must be a string.")
        outcome = MetricOutcome(MetricState(state), raw["value"], raw.get("reason"))
        value_type = output_config.get("type")
        if value_type not in {"boolean", "number", "string"}:
            raise ValueError(f"Unsupported metric value type {value_type!r}.")
        if outcome.state == MetricState.MEASURED:
            value = outcome.value
            valid = (
                (value_type == "boolean" and isinstance(value, bool))
                or (
                    value_type == "number"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                )
                or (value_type == "string" and isinstance(value, str))
            )
            if not valid:
                raise ValueError(f"Measured value must match declared type {value_type!r}.")
        return outcome
    except ValueError as exc:
        raise ValueError(f"Metric {metric_key!r}: {exc}") from exc


def serialize_metric_outcome(outcome: MetricOutcome) -> dict[str, Any]:
    payload: dict[str, Any] = {"state": outcome.state.value, "value": outcome.value}
    if outcome.reason is not None:
        payload["reason"] = outcome.reason
    return payload


def serialize_metrics(metrics: dict[str, MetricOutcome]) -> dict[str, dict[str, Any]]:
    return {key: serialize_metric_outcome(outcome) for key, outcome in metrics.items()}


def parse_metrics(
    raw: object, dimension_config: dict[str, Any], *, context: str
) -> dict[str, MetricOutcome]:
    if not isinstance(raw, dict):
        raise ValueError(f"{context}: metrics must be an object.")
    outputs = dimension_config.get("outputs", {})
    unexpected = set(raw) - set(outputs)
    if unexpected:
        raise ValueError(f"{context}: undeclared metrics {sorted(unexpected)!r}.")
    return {
        key: parse_metric_outcome(value, outputs[key], metric_key=f"{context}.{key}")
        for key, value in raw.items()
    }
