import operator as op_module
import re
from typing import Any

from engine.models import Medal

_OPS: dict[str, Any] = {
    ">=": op_module.ge,
    "<=": op_module.le,
    ">": op_module.gt,
    "<": op_module.lt,
    "==": op_module.eq,
    "!=": op_module.ne,
}

CONDITION_PATTERN = r"^([a-z][a-z0-9_]*)\s*(>=|<=|!=|>|<|==)\s*(.+)$"
_CONDITION_RE = re.compile(CONDITION_PATTERN)


def parse_condition(condition: str) -> tuple[str, str, str]:
    """
    Parse `<metric_key><optional-space><operator><optional-space><value>`.

    The same grammar is used by rubric evaluation and repository validation so
    cross-file checks stay aligned with runtime condition evaluation.
    """
    match = _CONDITION_RE.match(condition.strip())
    if not match:
        raise ValueError(f"Invalid condition syntax: {condition!r}")

    key, op_str, raw_value = match.groups()
    return key, op_str, raw_value.strip()


def eval_condition(metrics: dict[str, Any], condition: str) -> bool:
    """
    Evaluate a single condition string against a metrics dict.

    Condition format: `<metric_key> <operator> <value>`
    Example: "coverage_pct >= 90", "latest_build_passing == true"

    Returns False (not raises) when the metric key is absent — missing
    data is treated as failing the condition conservatively.
    Raises ValueError for unparseable condition syntax.
    """
    key, op_str, raw_value = parse_condition(condition)

    left = metrics.get(key)
    if left is None:
        return False

    # Parse right-hand side to a Python value
    if raw_value.lower() == "true":
        right: Any = True
    elif raw_value.lower() == "false":
        right = False
    else:
        try:
            # Parse as number; preserve int vs float based on left
            right = float(raw_value)
            if isinstance(left, int) and not isinstance(left, bool):
                right = int(right)
        except ValueError:
            right = raw_value

    return _OPS[op_str](left, right)


def evaluate_rubric(metrics: dict[str, Any], rubric: dict) -> Medal:
    """
    Determine the highest medal tier a product achieves for one dimension.

    Checks tiers top-down (gold → silver). If a tier's conditions all
    pass, that tier is returned immediately.

    Bronze handling:
    - If `bronze` key exists in rubric: bronze is explicit — check its
      conditions. Pass → Medal.BRONZE. Fail → Medal.UNRATED (product
      hasn't met even the minimum threshold).
    - If no `bronze` key: bronze is the implicit fallback minimum. A
      product that fails silver and gold still gets Medal.BRONZE.
    """
    for tier in ("gold", "silver"):
        if tier in rubric and all(eval_condition(metrics, cond) for cond in rubric[tier]):
            return Medal(tier)

    if "bronze" in rubric:
        if all(eval_condition(metrics, cond) for cond in rubric["bronze"]):
            return Medal.BRONZE
        return Medal.UNRATED

    return Medal.BRONZE  # implicit fallback
