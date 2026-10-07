import json

import pytest

from engine.metric_outcomes import (
    MetricOutcome,
    MetricState,
    insufficient_data,
    measured,
    not_applicable,
    parse_metric_outcome,
    serialize_metric_outcome,
)


@pytest.mark.parametrize(
    ("value", "value_type"),
    [(False, "boolean"), (True, "boolean"), (0, "number"), (1.5, "number"), ("", "string")],
)
def test_measured_values_round_trip(value, value_type):
    outcome = measured(value)
    payload = json.loads(json.dumps(serialize_metric_outcome(outcome)))
    assert parse_metric_outcome(payload, {"type": value_type}, metric_key="signal") == outcome
    assert outcome.state == MetricState.MEASURED
    assert type(outcome.value) is type(value)


@pytest.mark.parametrize("factory", [not_applicable, insufficient_data])
def test_unmeasured_results_round_trip(factory):
    outcome = factory("Machine charm.")
    assert (
        parse_metric_outcome(
            serialize_metric_outcome(outcome), {"type": "boolean"}, metric_key="signal"
        )
        == outcome
    )
    assert outcome.value is None
    assert outcome.reason == "Machine charm."


@pytest.mark.parametrize(
    "raw",
    [
        True,
        None,
        "not_applicable",
        {},
        {"state": "measured"},
        {"state": "measured", "value": None},
        {"state": "unknown", "value": None, "reason": "Unknown."},
        {"state": "not_applicable", "value": True, "reason": "Not a charm."},
        {"state": "not_applicable", "value": None},
        {"state": "insufficient_data", "value": None, "reason": "  "},
        {"state": "measured", "value": True, "extra": "unexpected"},
        {"state": "measured", "value": True, "reason": 7},
    ],
)
def test_parser_rejects_invalid_payloads_with_metric_context(raw):
    with pytest.raises(ValueError, match="signal"):
        parse_metric_outcome(raw, {"type": "boolean"}, metric_key="signal")


@pytest.mark.parametrize(
    ("value", "value_type"),
    [(True, "number"), (1, "boolean"), ("true", "boolean"), (2, "string")],
)
def test_parser_enforces_contract_value_type(value, value_type):
    with pytest.raises(ValueError, match="signal"):
        parse_metric_outcome(
            {"state": "measured", "value": value},
            {"type": value_type},
            metric_key="signal",
        )


@pytest.mark.parametrize("value", [None, [], {}, float("nan"), float("inf"), float("-inf")])
def test_measured_constructor_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        measured(value)


@pytest.mark.parametrize("factory", [not_applicable, insufficient_data])
@pytest.mark.parametrize("reason", ["", " ", None, 123])
def test_unmeasured_constructor_requires_reason(factory, reason):
    with pytest.raises(ValueError):
        factory(reason)


def test_direct_construction_cannot_bypass_validation():
    with pytest.raises(ValueError):
        MetricOutcome(MetricState.NOT_APPLICABLE, True, "Not a charm.")
    with pytest.raises(ValueError):
        MetricOutcome("unknown", None, "Unknown.")


def test_parser_rejects_unknown_declared_type():
    with pytest.raises(ValueError, match="signal"):
        parse_metric_outcome(
            {"state": "measured", "value": True}, {"type": "unknown"}, metric_key="signal"
        )
