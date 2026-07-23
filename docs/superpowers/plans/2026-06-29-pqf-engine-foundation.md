# PQF Engine Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data schemas, condition evaluator, medal computation engine, and drift tracker that form the computational core of the PQF tool.

**Architecture:** Portfolio definitions live in `products/*.yaml` (manually maintained) and `config/dimensions.yaml` (scorer contracts + medal rubrics). A set of pure Python functions reads those files alongside scorer-produced `computed/*.json` files, evaluates rubric conditions, and determines per-product medal grades and compliance drift. The CLI entry point wires file I/O around these pure functions so GitHub Actions can call it per product.

**Tech Stack:** Python 3.11+, pytest, pyyaml, python-dateutil, ruff

## Global Constraints

- Python >= 3.11 (use built-in type hints: `dict[str, Any]`, `list[str]`, `X | None`)
- All `engine/` modules except `__main__.py` must be pure functions — no file I/O, no network calls, no side effects (makes them fully unit-testable)
- Medal string values (lowercase): `"unrated"`, `"bronze"`, `"silver"`, `"gold"`
- Condition format in `dimensions.yaml`: `<metric_key> <operator> <value>` — operators: `>=`, `<=`, `>`, `<`, `==`, `!=`
- `drift-history.json` timestamps use ISO 8601 with UTC timezone: `2026-06-01T00:00:00+00:00`
- All tests use pytest; run from repo root: `pytest engine/__tests__/ -v`
- Repo name: `canonical/platform-engineering/pqf`

---

## File Map

```
(repo root)/
├── products/
│   └── matrix.yaml                   # Sample product (created in Task 7)
├── config/
│   └── dimensions.yaml               # Full rubric config with all 5 dimensions (Task 7)
├── computed/
│   └── matrix.json                   # Sample computed metrics for integration test (Task 7)
├── drift-history.json                # Initialized as {} (Task 1)
├── pyproject.toml                    # Python project config + deps (Task 1)
├── README.md                         # Project overview (Task 1)
└── engine/
    ├── __init__.py                   # Empty (Task 1)
    ├── models.py                     # Medal enum, MEDAL_RANK, DriftState, DimensionResult, ProductResult (Task 2)
    ├── rubric.py                     # eval_condition(), evaluate_rubric() (Tasks 3-4)
    ├── medal_engine.py               # compute_product() (Task 5)
    ├── drift_tracker.py              # compute_dimension_drift(), update_drift_history() (Task 6)
    ├── __main__.py                   # CLI entry point (Task 7)
    └── __tests__/
        ├── test_models.py            # Medal ordering, dataclass instantiation (Task 2)
        ├── test_rubric.py            # eval_condition + evaluate_rubric (Tasks 3-4)
        ├── test_medal_engine.py      # compute_product (Task 5)
        ├── test_drift_tracker.py     # compute_dimension_drift + update_drift_history (Task 6)
        └── test_integration.py      # End-to-end CLI smoke test (Task 7)
```

---

### Task 1: Repository Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `engine/__init__.py`
- Create: `products/.gitkeep`
- Create: `config/.gitkeep`
- Create: `computed/.gitkeep`
- Create: `drift-history.json`
- Create: `README.md`

**Interfaces:**
- Produces: Python environment with pytest, pyyaml, python-dateutil, ruff available

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p products config computed public engine/__tests__
touch products/.gitkeep config/.gitkeep computed/.gitkeep public/.gitkeep
touch engine/__init__.py engine/__tests__/__init__.py
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "pqf-engine"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "python-dateutil>=2.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.9",
]

[tool.pytest.ini_options]
testpaths = ["engine/__tests__"]
addopts = "-v"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

- [ ] **Step 3: Create `drift-history.json`**

```json
{}
```

- [ ] **Step 4: Create `README.md`**

```markdown
# PQF — Product Quality Framework

A tool to track the quality and compliance state of Canonical Platform Engineering's product portfolio.

## Structure

- `products/` — one YAML file per product (manually maintained, PR-reviewed)
- `config/dimensions.yaml` — medal rubrics and scorer contracts
- `computed/` — GHA-written raw metrics per product (never hand-edited)
- `engine/` — pure Python medal computation
- `ui/` — React 19 dashboard (separate plan)

## Running the engine locally

```bash
pip install -e ".[dev]"
python -m engine \
  --product products/matrix.yaml \
  --computed computed/matrix.json \
  --dimensions config/dimensions.yaml \
  --drift-history drift-history.json
```

## Running tests

```bash
pytest engine/__tests__/ -v
```
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected output: `Successfully installed pqf-engine-0.1.0 ...`

- [ ] **Step 6: Verify pytest runs with zero tests**

```bash
pytest engine/__tests__/ -v
```

Expected output: `no tests ran` or `collected 0 items`. No errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml engine/__init__.py engine/__tests__/__init__.py \
        products/.gitkeep config/.gitkeep computed/.gitkeep public/.gitkeep \
        drift-history.json README.md
git commit -m "feat: scaffold pqf engine repository"
```

---

### Task 2: Data Models

**Files:**
- Create: `engine/models.py`
- Create: `engine/__tests__/test_models.py`

**Interfaces:**
- Produces:
  - `Medal` — `str` enum with values `"unrated"`, `"bronze"`, `"silver"`, `"gold"`
  - `MEDAL_RANK: dict[Medal, int]` — maps `Medal.UNRATED=0`, `BRONZE=1`, `SILVER=2`, `GOLD=3`
  - `DriftState(status: str, first_seen_at: str, deadline: str)` — dataclass
  - `DimensionResult(medal: Medal, target: Medal, metrics: dict, drift: DriftState | None)` — dataclass
  - `ProductResult(product_id: str, current_medal: Medal, target_medal: Medal, dimensions: dict[str, DimensionResult])` — dataclass

- [ ] **Step 1: Write the failing tests**

```python
# engine/__tests__/test_models.py
import pytest
from engine.models import Medal, MEDAL_RANK, DriftState, DimensionResult, ProductResult


def test_medal_values_are_lowercase_strings():
    assert Medal.UNRATED == "unrated"
    assert Medal.BRONZE == "bronze"
    assert Medal.SILVER == "silver"
    assert Medal.GOLD == "gold"


def test_medal_rank_ordering():
    assert MEDAL_RANK[Medal.UNRATED] < MEDAL_RANK[Medal.BRONZE]
    assert MEDAL_RANK[Medal.BRONZE] < MEDAL_RANK[Medal.SILVER]
    assert MEDAL_RANK[Medal.SILVER] < MEDAL_RANK[Medal.GOLD]


def test_medal_comparable_via_rank():
    medals = [Medal.GOLD, Medal.BRONZE, Medal.SILVER, Medal.UNRATED]
    assert min(medals, key=lambda m: MEDAL_RANK[m]) == Medal.UNRATED


def test_drift_state_instantiation():
    drift = DriftState(
        status="remediating",
        first_seen_at="2026-06-01T00:00:00+00:00",
        deadline="2026-12-01T00:00:00+00:00",
    )
    assert drift.status == "remediating"
    assert drift.first_seen_at == "2026-06-01T00:00:00+00:00"
    assert drift.deadline == "2026-12-01T00:00:00+00:00"


def test_dimension_result_instantiation():
    dim = DimensionResult(
        medal=Medal.SILVER,
        target=Medal.GOLD,
        metrics={"coverage_pct": 85},
        drift=None,
    )
    assert dim.medal == Medal.SILVER
    assert dim.drift is None


def test_product_result_instantiation():
    result = ProductResult(
        product_id="matrix",
        current_medal=Medal.BRONZE,
        target_medal=Medal.GOLD,
        dimensions={},
    )
    assert result.product_id == "matrix"
    assert result.current_medal == Medal.BRONZE
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest engine/__tests__/test_models.py -v
```

Expected: `ERRORS` — `ModuleNotFoundError: No module named 'engine.models'`

- [ ] **Step 3: Create `engine/models.py`**

```python
# engine/models.py
from dataclasses import dataclass
from enum import Enum


class Medal(str, Enum):
    UNRATED = "unrated"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


MEDAL_RANK: dict["Medal", int] = {
    Medal.UNRATED: 0,
    Medal.BRONZE: 1,
    Medal.SILVER: 2,
    Medal.GOLD: 3,
}


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


@dataclass
class ProductResult:
    product_id: str
    current_medal: Medal
    target_medal: Medal
    dimensions: dict[str, DimensionResult]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest engine/__tests__/test_models.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add engine/models.py engine/__tests__/test_models.py
git commit -m "feat: add PQF data models (Medal, DriftState, DimensionResult, ProductResult)"
```

---

### Task 3: Condition Evaluator

**Files:**
- Create: `engine/rubric.py` (partial — `eval_condition` only)
- Create: `engine/__tests__/test_rubric.py` (partial)

**Interfaces:**
- Consumes: nothing from prior tasks (standalone utility)
- Produces:
  - `eval_condition(metrics: dict[str, Any], condition: str) -> bool`
    - Returns `True` if the condition holds given the metrics dict
    - Returns `False` if the metric key is missing from the dict
    - Raises `ValueError` if the condition string cannot be parsed

- [ ] **Step 1: Write the failing tests**

```python
# engine/__tests__/test_rubric.py
import pytest
from engine.rubric import eval_condition


# --- Numeric comparisons ---

def test_gte_true():
    assert eval_condition({"coverage_pct": 90}, "coverage_pct >= 90") is True


def test_gte_false():
    assert eval_condition({"coverage_pct": 89}, "coverage_pct >= 90") is False


def test_gt_true():
    assert eval_condition({"coverage_pct": 91}, "coverage_pct > 90") is True


def test_gt_boundary_false():
    assert eval_condition({"coverage_pct": 90}, "coverage_pct > 90") is False


def test_lte_true():
    assert eval_condition({"avg_triage_days": 3}, "avg_triage_days <= 5") is True


def test_lte_false():
    assert eval_condition({"avg_triage_days": 6}, "avg_triage_days <= 5") is False


def test_eq_numeric():
    assert eval_condition({"diataxis_coverage": 4}, "diataxis_coverage == 4") is True


def test_neq_numeric():
    assert eval_condition({"diataxis_coverage": 3}, "diataxis_coverage != 4") is True


# --- Boolean comparisons ---

def test_bool_eq_true_passes():
    assert eval_condition({"latest_build_passing": True}, "latest_build_passing == true") is True


def test_bool_eq_true_fails_when_false():
    assert eval_condition({"latest_build_passing": False}, "latest_build_passing == true") is False


def test_bool_eq_false_passes():
    assert eval_condition({"has_readme": False}, "has_readme == false") is True


def test_bool_neq():
    assert eval_condition({"ssdlc_onboarded": False}, "ssdlc_onboarded != true") is True


# --- Missing key ---

def test_missing_key_returns_false():
    assert eval_condition({}, "coverage_pct >= 70") is False


def test_missing_key_bool_returns_false():
    assert eval_condition({}, "latest_build_passing == true") is False


# --- Invalid condition ---

def test_invalid_condition_raises_value_error():
    with pytest.raises(ValueError, match="Invalid condition"):
        eval_condition({}, "this is not valid")


def test_condition_with_extra_spaces_is_valid():
    assert eval_condition({"coverage_pct": 90}, "  coverage_pct  >=  90  ") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest engine/__tests__/test_rubric.py -v
```

Expected: `ERRORS` — `ModuleNotFoundError: No module named 'engine.rubric'`

- [ ] **Step 3: Create `engine/rubric.py` with `eval_condition`**

```python
# engine/rubric.py
import operator as op_module
import re
from typing import Any

from engine.models import Medal, MEDAL_RANK

_OPS: dict[str, Any] = {
    ">=": op_module.ge,
    "<=": op_module.le,
    ">": op_module.gt,
    "<": op_module.lt,
    "==": op_module.eq,
    "!=": op_module.ne,
}

# Matches: <word> <operator> <value>
# Operators checked longest-first to avoid ">" matching ">="
_CONDITION_RE = re.compile(r"^(\w+)\s*(>=|<=|!=|>|<|==)\s*(.+)$")


def eval_condition(metrics: dict[str, Any], condition: str) -> bool:
    """
    Evaluate a single condition string against a metrics dict.

    Condition format: `<metric_key> <operator> <value>`
    Example: "coverage_pct >= 90", "latest_build_passing == true"

    Returns False (not raises) when the metric key is absent — missing
    data is treated as failing the condition conservatively.
    Raises ValueError for unparseable condition syntax.
    """
    match = _CONDITION_RE.match(condition.strip())
    if not match:
        raise ValueError(f"Invalid condition syntax: {condition!r}")

    key, op_str, raw_value = match.groups()
    raw_value = raw_value.strip()

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest engine/__tests__/test_rubric.py -v -k "eval_condition"
```

Expected: all `eval_condition` tests pass (18 tests)

- [ ] **Step 5: Commit**

```bash
git add engine/rubric.py engine/__tests__/test_rubric.py
git commit -m "feat: add condition evaluator (eval_condition)"
```

---

### Task 4: Rubric Evaluator

**Files:**
- Modify: `engine/rubric.py` (add `evaluate_rubric`)
- Modify: `engine/__tests__/test_rubric.py` (add `evaluate_rubric` tests)

**Interfaces:**
- Consumes: `eval_condition` from this file; `Medal` from `engine.models`
- Produces:
  - `evaluate_rubric(metrics: dict[str, Any], rubric: dict) -> Medal`
    - `rubric` is the `medals:` dict from `dimensions.yaml` for one dimension
    - Returns the highest tier (`gold > silver > bronze`) whose **all** conditions pass
    - If explicit `bronze` conditions exist and fail → returns `Medal.UNRATED`
    - If no `bronze` key in rubric → `Medal.BRONZE` is the implicit fallback minimum

- [ ] **Step 1: Append the failing tests to `engine/__tests__/test_rubric.py`**

Add these at the end of the existing file:

```python
# --- evaluate_rubric tests ---

from engine.rubric import evaluate_rubric
from engine.models import Medal

# Rubric with explicit bronze, silver, and gold conditions
FULL_RUBRIC = {
    "bronze": ["coverage_pct >= 70", "latest_build_passing == true"],
    "silver": ["coverage_pct >= 80", "stability_pct >= 85"],
    "gold": ["coverage_pct >= 90", "stability_pct >= 98"],
}

# Rubric without explicit bronze (fallback behavior)
NO_BRONZE_RUBRIC = {
    "silver": ["supports_juju_3 == true"],
    "gold": ["supports_juju_4 == true", "supports_ck8s == true"],
}


def test_returns_gold_when_all_gold_conditions_met():
    metrics = {"coverage_pct": 95, "stability_pct": 99, "latest_build_passing": True}
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.GOLD


def test_returns_silver_when_gold_fails_but_silver_passes():
    metrics = {"coverage_pct": 85, "stability_pct": 90, "latest_build_passing": True}
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.SILVER


def test_returns_bronze_when_only_bronze_conditions_met():
    # coverage 75 passes bronze (>=70) but not silver (>=80)
    metrics = {"coverage_pct": 75, "latest_build_passing": True}
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.BRONZE


def test_returns_unrated_when_explicit_bronze_conditions_fail():
    # coverage 60 < 70 — fails bronze threshold
    metrics = {"coverage_pct": 60, "latest_build_passing": True}
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.UNRATED


def test_returns_unrated_when_build_failing_despite_good_coverage():
    metrics = {"coverage_pct": 95, "stability_pct": 99, "latest_build_passing": False}
    assert evaluate_rubric(metrics, FULL_RUBRIC) == Medal.UNRATED


def test_bronze_fallback_when_no_bronze_key_and_nothing_passes():
    # Fails silver and gold — but no explicit bronze → fallback to bronze
    metrics = {"supports_juju_3": False, "supports_juju_4": False, "supports_ck8s": False}
    assert evaluate_rubric(metrics, NO_BRONZE_RUBRIC) == Medal.BRONZE


def test_silver_when_no_bronze_key_and_silver_passes():
    metrics = {"supports_juju_3": True, "supports_juju_4": False, "supports_ck8s": False}
    assert evaluate_rubric(metrics, NO_BRONZE_RUBRIC) == Medal.SILVER


def test_gold_when_no_bronze_key_and_all_gold_pass():
    metrics = {"supports_juju_3": True, "supports_juju_4": True, "supports_ck8s": True}
    assert evaluate_rubric(metrics, NO_BRONZE_RUBRIC) == Medal.GOLD


def test_empty_metrics_with_explicit_bronze_returns_unrated():
    assert evaluate_rubric({}, FULL_RUBRIC) == Medal.UNRATED


def test_empty_metrics_with_no_bronze_key_returns_bronze():
    assert evaluate_rubric({}, NO_BRONZE_RUBRIC) == Medal.BRONZE
```

- [ ] **Step 2: Run tests to verify new ones fail**

```bash
pytest engine/__tests__/test_rubric.py -v -k "evaluate_rubric"
```

Expected: `ERRORS` — `ImportError: cannot import name 'evaluate_rubric'`

- [ ] **Step 3: Add `evaluate_rubric` to `engine/rubric.py`**

Append to the existing `engine/rubric.py` (after `eval_condition`):

```python
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
```

- [ ] **Step 4: Run all rubric tests**

```bash
pytest engine/__tests__/test_rubric.py -v
```

Expected: all tests pass (28 tests total)

- [ ] **Step 5: Commit**

```bash
git add engine/rubric.py engine/__tests__/test_rubric.py
git commit -m "feat: add rubric evaluator (evaluate_rubric)"
```

---

### Task 5: Medal Engine

**Files:**
- Create: `engine/medal_engine.py`
- Create: `engine/__tests__/test_medal_engine.py`

**Interfaces:**
- Consumes:
  - `evaluate_rubric(metrics, rubric) -> Medal` from `engine.rubric`
  - `compute_dimension_drift(product_id, dim_name, current_medal, target_medal, drift_history) -> DriftState | None` from `engine.drift_tracker` *(this module doesn't exist yet — the engine will import it; write the test using an empty `drift_history={}` which triggers the "no entry yet" path that returns None)*
  - `Medal`, `MEDAL_RANK`, `DimensionResult`, `ProductResult` from `engine.models`
- Produces:
  - `compute_product(product: dict, computed: dict, dimensions_config: dict, drift_history: dict) -> ProductResult`
    - `product` — parsed `products/{id}.yaml`
    - `computed` — parsed `computed/{id}.json` (may be `{}` on first run)
    - `dimensions_config` — parsed `config/dimensions.yaml`
    - `drift_history` — parsed `drift-history.json`
    - Pure function — reads drift_history but never mutates it

- [ ] **Step 1: Create a stub `engine/drift_tracker.py`** (needed for import to work)

```python
# engine/drift_tracker.py
# Stub — full implementation in Task 6
from engine.models import Medal, DriftState


def compute_dimension_drift(
    product_id: str,
    dim_name: str,
    current_medal: Medal,
    target_medal: Medal,
    drift_history: dict,
) -> DriftState | None:
    raise NotImplementedError


def update_drift_history(
    product_id: str,
    dim_name: str,
    current_medal: Medal,
    target_medal: Medal,
    drift_history: dict,
    now: object,
) -> None:
    raise NotImplementedError
```

- [ ] **Step 2: Write the failing tests**

```python
# engine/__tests__/test_medal_engine.py
import pytest
from engine.medal_engine import compute_product
from engine.models import Medal

# Minimal two-dimension config for testing
_DIMENSIONS = {
    "dimensions": {
        "test_verification": {
            "medals": {
                "bronze": ["coverage_pct >= 70", "latest_build_passing == true"],
                "silver": ["coverage_pct >= 80"],
                "gold": ["coverage_pct >= 90"],
            }
        },
        "documentation": {
            "medals": {
                "bronze": ["has_readme == true"],
                "silver": ["diataxis_coverage >= 4"],
                "gold": ["style_linter_passing == true", "diataxis_coverage == 4"],
            }
        },
    }
}

_PRODUCT = {"id": "test-product", "target_medal": "gold"}


def test_current_medal_is_lowest_across_dimensions():
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": 95, "latest_build_passing": True},
            # documentation only meets bronze
            "documentation": {"has_readme": True, "diataxis_coverage": 2, "style_linter_passing": False},
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    assert result.current_medal == Medal.BRONZE
    assert result.dimensions["test_verification"].medal == Medal.GOLD
    assert result.dimensions["documentation"].medal == Medal.BRONZE


def test_all_gold_dimensions_gives_gold_product():
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": 95, "latest_build_passing": True},
            "documentation": {"has_readme": True, "diataxis_coverage": 4, "style_linter_passing": True},
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    assert result.current_medal == Medal.GOLD


def test_all_silver_gives_silver_product():
    computed = {
        "metrics": {
            "test_verification": {"coverage_pct": 85, "latest_build_passing": True},
            "documentation": {"has_readme": True, "diataxis_coverage": 4, "style_linter_passing": False},
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    assert result.current_medal == Medal.SILVER


def test_missing_dimension_in_computed_treated_as_empty_metrics():
    # test_verification metrics missing entirely
    computed = {
        "metrics": {
            "documentation": {"has_readme": True, "diataxis_coverage": 4, "style_linter_passing": True},
        }
    }
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    # test_verification gets empty metrics → bronze conditions fail → unrated
    assert result.dimensions["test_verification"].medal == Medal.UNRATED
    assert result.current_medal == Medal.UNRATED


def test_entirely_empty_computed_gives_unrated():
    result = compute_product(_PRODUCT, {}, _DIMENSIONS, {})
    assert result.current_medal == Medal.UNRATED


def test_dimension_results_contain_target_medal():
    computed = {"metrics": {"test_verification": {"coverage_pct": 85, "latest_build_passing": True},
                             "documentation": {"has_readme": True, "diataxis_coverage": 2}}}
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    for dim in result.dimensions.values():
        assert dim.target == Medal.GOLD


def test_product_id_and_target_medal_in_result():
    result = compute_product(_PRODUCT, {}, _DIMENSIONS, {})
    assert result.product_id == "test-product"
    assert result.target_medal == Medal.GOLD


def test_drift_is_none_for_dimension_when_no_history():
    # With empty drift_history, compute_dimension_drift returns None
    computed = {"metrics": {"test_verification": {"coverage_pct": 85, "latest_build_passing": True},
                             "documentation": {"has_readme": True, "diataxis_coverage": 2}}}
    result = compute_product(_PRODUCT, computed, _DIMENSIONS, {})
    # Documentation is bronze, target is gold → drifting, but no history entry yet → None
    assert result.dimensions["documentation"].drift is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest engine/__tests__/test_medal_engine.py -v
```

Expected: `ERRORS` — `ModuleNotFoundError: No module named 'engine.medal_engine'`

- [ ] **Step 4: Create `engine/medal_engine.py`**

```python
# engine/medal_engine.py
from engine.drift_tracker import compute_dimension_drift
from engine.models import MEDAL_RANK, DimensionResult, Medal, ProductResult
from engine.rubric import evaluate_rubric


def compute_product(
    product: dict,
    computed: dict,
    dimensions_config: dict,
    drift_history: dict,
) -> ProductResult:
    """
    Compute the current medal and per-dimension results for a product.

    Pure function — reads drift_history but never mutates it.
    Call engine.drift_tracker.update_drift_history() separately to persist
    drift state changes.
    """
    target_medal = Medal(product["target_medal"])
    dimension_results: dict[str, DimensionResult] = {}

    for dim_name, dim_config in dimensions_config.get("dimensions", {}).items():
        metrics = computed.get("metrics", {}).get(dim_name, {})
        dim_medal = evaluate_rubric(metrics, dim_config["medals"])
        drift = compute_dimension_drift(
            product["id"], dim_name, dim_medal, target_medal, drift_history
        )
        dimension_results[dim_name] = DimensionResult(
            medal=dim_medal,
            target=target_medal,
            metrics=metrics,
            drift=drift,
        )

    if dimension_results:
        current_medal = min(
            dimension_results.values(),
            key=lambda r: MEDAL_RANK[r.medal],
        ).medal
    else:
        current_medal = Medal.UNRATED

    return ProductResult(
        product_id=product["id"],
        current_medal=current_medal,
        target_medal=target_medal,
        dimensions=dimension_results,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest engine/__tests__/test_medal_engine.py -v
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add engine/medal_engine.py engine/drift_tracker.py engine/__tests__/test_medal_engine.py
git commit -m "feat: add medal engine (compute_product)"
```

---

### Task 6: Drift Tracker

**Files:**
- Modify: `engine/drift_tracker.py` (replace stub with full implementation)
- Create: `engine/__tests__/test_drift_tracker.py`

**Interfaces:**
- Consumes: `Medal`, `MEDAL_RANK`, `DriftState` from `engine.models`; `dateutil.relativedelta`
- Produces:
  - `compute_dimension_drift(product_id, dim_name, current_medal, target_medal, drift_history) -> DriftState | None`
    - Returns `None` if product is at/above target (no drift)
    - Returns `None` if drifting but no history entry yet (caller must call `update_drift_history` first to record it; on the next run the entry will exist)
    - Returns `DriftState(status="remediating", ...)` if within deadline
    - Returns `DriftState(status="overdue", ...)` if past deadline
  - `update_drift_history(product_id, dim_name, current_medal, target_medal, drift_history, now) -> None`
    - Mutates `drift_history` in place
    - If drifting and no entry: record `first_seen_at=now`, `deadline=now + 6 months (gold) or 12 months (silver)`
    - If drifting and entry exists: leave untouched (preserves original clock)
    - If compliant (current ≥ target): remove entry (clears drift window)

- [ ] **Step 1: Write the failing tests**

```python
# engine/__tests__/test_drift_tracker.py
import pytest
from datetime import datetime, timezone
from engine.drift_tracker import compute_dimension_drift, update_drift_history
from engine.models import Medal


# Helper: UTC datetime factory
def utc(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


# ─── compute_dimension_drift ───────────────────────────────────────────────────

def test_no_drift_when_current_equals_target():
    assert compute_dimension_drift("matrix", "docs", Medal.GOLD, Medal.GOLD, {}) is None


def test_no_drift_when_current_exceeds_target():
    # Gold current, silver target → no drift
    assert compute_dimension_drift("matrix", "docs", Medal.GOLD, Medal.SILVER, {}) is None


def test_no_drift_when_bronze_target_and_above():
    assert compute_dimension_drift("matrix", "docs", Medal.BRONZE, Medal.BRONZE, {}) is None


def test_returns_none_when_drifting_but_no_history_entry():
    # First time we see this drift — history is empty, None returned
    # (update_drift_history must be called to record it)
    result = compute_dimension_drift("matrix", "docs", Medal.BRONZE, Medal.GOLD, {})
    assert result is None


def test_returns_remediating_when_within_deadline():
    history = {
        "matrix": {
            "docs": {
                "first_seen_at": "2026-06-01T00:00:00+00:00",
                "deadline": "2099-12-01T00:00:00+00:00",  # far future
            }
        }
    }
    result = compute_dimension_drift("matrix", "docs", Medal.BRONZE, Medal.GOLD, history)
    assert result is not None
    assert result.status == "remediating"
    assert result.first_seen_at == "2026-06-01T00:00:00+00:00"


def test_returns_overdue_when_past_deadline():
    history = {
        "matrix": {
            "docs": {
                "first_seen_at": "2020-01-01T00:00:00+00:00",
                "deadline": "2020-07-01T00:00:00+00:00",  # past
            }
        }
    }
    result = compute_dimension_drift("matrix", "docs", Medal.BRONZE, Medal.GOLD, history)
    assert result is not None
    assert result.status == "overdue"


# ─── update_drift_history ──────────────────────────────────────────────────────

def test_records_new_drift_gold_target_six_months():
    history = {}
    now = utc(2026, 6, 1)
    update_drift_history("matrix", "docs", Medal.BRONZE, Medal.GOLD, history, now)

    assert "matrix" in history
    assert "docs" in history["matrix"]
    assert history["matrix"]["docs"]["first_seen_at"] == "2026-06-01T00:00:00+00:00"
    # Gold target → 6 months → deadline December 1
    assert history["matrix"]["docs"]["deadline"] == "2026-12-01T00:00:00+00:00"


def test_records_new_drift_silver_target_twelve_months():
    history = {}
    now = utc(2026, 6, 1)
    update_drift_history("matrix", "docs", Medal.BRONZE, Medal.SILVER, history, now)

    assert history["matrix"]["docs"]["deadline"] == "2027-06-01T00:00:00+00:00"


def test_preserves_existing_clock_when_already_drifting():
    original_start = "2026-01-01T00:00:00+00:00"
    original_deadline = "2026-07-01T00:00:00+00:00"
    history = {
        "matrix": {
            "docs": {
                "first_seen_at": original_start,
                "deadline": original_deadline,
            }
        }
    }
    now = utc(2026, 6, 1)  # later time — should NOT reset the clock
    update_drift_history("matrix", "docs", Medal.BRONZE, Medal.GOLD, history, now)

    assert history["matrix"]["docs"]["first_seen_at"] == original_start
    assert history["matrix"]["docs"]["deadline"] == original_deadline


def test_clears_entry_when_compliant():
    history = {
        "matrix": {
            "docs": {
                "first_seen_at": "2026-01-01T00:00:00+00:00",
                "deadline": "2026-07-01T00:00:00+00:00",
            }
        }
    }
    now = utc(2026, 6, 1)
    # Now at gold, target is gold → compliant → clear
    update_drift_history("matrix", "docs", Medal.GOLD, Medal.GOLD, history, now)

    assert history.get("matrix", {}).get("docs") is None


def test_clears_entry_and_removes_empty_product_dict():
    history = {
        "matrix": {
            "docs": {"first_seen_at": "2026-01-01T00:00:00+00:00", "deadline": "2026-07-01T00:00:00+00:00"}
        }
    }
    now = utc(2026, 6, 1)
    update_drift_history("matrix", "docs", Medal.GOLD, Medal.GOLD, history, now)

    # "matrix" key removed entirely when no more drifting dimensions
    assert "matrix" not in history


def test_does_not_record_drift_for_bronze_target():
    # Bronze is the minimum — nothing below bronze to drift to
    history = {}
    now = utc(2026, 6, 1)
    update_drift_history("matrix", "docs", Medal.UNRATED, Medal.BRONZE, history, now)
    assert history == {}


def test_multiple_dimensions_tracked_independently():
    history = {}
    now = utc(2026, 6, 1)
    update_drift_history("matrix", "docs", Medal.BRONZE, Medal.GOLD, history, now)
    update_drift_history("matrix", "tests", Medal.SILVER, Medal.GOLD, history, now)

    assert "docs" in history["matrix"]
    assert "tests" in history["matrix"]
    # Fixing docs doesn't clear tests
    update_drift_history("matrix", "docs", Medal.GOLD, Medal.GOLD, history, now)
    assert "docs" not in history["matrix"]
    assert "tests" in history["matrix"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest engine/__tests__/test_drift_tracker.py -v
```

Expected: failures with `NotImplementedError` (stub functions)

- [ ] **Step 3: Replace `engine/drift_tracker.py` with full implementation**

```python
# engine/drift_tracker.py
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta

from engine.models import MEDAL_RANK, DriftState, Medal

# Remediation window per target medal tier
_REMEDIATION_MONTHS: dict[Medal, int] = {
    Medal.GOLD: 6,
    Medal.SILVER: 12,
}


def compute_dimension_drift(
    product_id: str,
    dim_name: str,
    current_medal: Medal,
    target_medal: Medal,
    drift_history: dict,
) -> DriftState | None:
    """
    Read-only. Returns the current drift state for a product+dimension.

    Returns None if:
    - Product is at or above its target for this dimension (no drift)
    - Product is drifting but no history entry exists yet (call
      update_drift_history to record it; it will appear on the next run)
    """
    if MEDAL_RANK[current_medal] >= MEDAL_RANK[target_medal]:
        return None

    entry = drift_history.get(product_id, {}).get(dim_name)
    if entry is None:
        return None

    deadline_dt = datetime.fromisoformat(entry["deadline"])
    if deadline_dt.tzinfo is None:
        deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    status = "overdue" if now > deadline_dt else "remediating"

    return DriftState(
        status=status,
        first_seen_at=entry["first_seen_at"],
        deadline=entry["deadline"],
    )


def update_drift_history(
    product_id: str,
    dim_name: str,
    current_medal: Medal,
    target_medal: Medal,
    drift_history: dict,
    now: datetime,
) -> None:
    """
    Mutates drift_history in place.

    - Compliant (current ≥ target): clears any existing entry
    - Drifting, no entry: records first_seen_at + computes deadline
    - Drifting, entry exists: leaves untouched (original clock preserved)
    - Bronze target: never records drift (bronze is the minimum floor)
    """
    product_history = drift_history.setdefault(product_id, {})

    if MEDAL_RANK[current_medal] >= MEDAL_RANK[target_medal]:
        # Compliant — clear drift entry
        product_history.pop(dim_name, None)
        if not product_history:
            drift_history.pop(product_id, None)
        return

    if target_medal not in _REMEDIATION_MONTHS:
        # Bronze target has no remediation window
        return

    if dim_name not in product_history:
        # First time seeing this drift — start the clock
        months = _REMEDIATION_MONTHS[target_medal]
        deadline = now + relativedelta(months=months)
        product_history[dim_name] = {
            "first_seen_at": now.isoformat(),
            "deadline": deadline.isoformat(),
        }
    # If entry already exists, leave it untouched (clock keeps running)
```

- [ ] **Step 4: Run all drift tracker tests**

```bash
pytest engine/__tests__/test_drift_tracker.py -v
```

Expected: `14 passed`

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
pytest engine/__tests__/ -v
```

Expected: all previously passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add engine/drift_tracker.py engine/__tests__/test_drift_tracker.py
git commit -m "feat: add drift tracker (compute_dimension_drift, update_drift_history)"
```

---

### Task 7: Sample Data, CLI Entry Point, and Integration Test

**Files:**
- Create: `products/matrix.yaml`
- Create: `config/dimensions.yaml`
- Create: `computed/matrix.json`
- Create: `engine/__main__.py`
- Create: `engine/__tests__/test_integration.py`

**Interfaces:**
- Consumes: `compute_product` from `engine.medal_engine`; `update_drift_history` from `engine.drift_tracker`; `Medal`, `ProductResult`, `DimensionResult`, `DriftState` from `engine.models`
- Produces: CLI runnable via `python -m engine --product ... --computed ... --dimensions ... --drift-history ...`; outputs a JSON portfolio entry to stdout

- [ ] **Step 1: Create `products/matrix.yaml`**

```yaml
# products/matrix.yaml
id: matrix
name: "Matrix (Synapse)"
description: "Open-standard chat for secure real-time collaboration"

lifecycle: stable          # experimental | beta | stable | legacy
target_medal: gold

ownership:
  squad: americas
  stakeholders:
    - "IS Operations"
    - "Community Team"
  users:
    - "PFE"

documentation_url: "https://charmhub.io/synapse"
allure_report_url: ""  # filled in by scorer

components:
  foundational:
    - id: synapse
      type: charm
      github_repo: canonical/synapse-operator
    - id: postgresql-k8s
      type: charm
      github_repo: canonical/postgresql-k8s-operator
  feature:
    - id: saml-integrator
      type: charm
      github_repo: canonical/saml-integrator-operator
  auxiliary:
    - id: synapse-stats-exporter
      type: charm
      github_repo: canonical/synapse-operator
```

- [ ] **Step 2: Create `config/dimensions.yaml`**

```yaml
# config/dimensions.yaml
# The single configuration knob for the entire scoring system.
# Adding a dimension = add an entry here + create scorers/<name>/scorer.py

dimensions:

  test_verification:
    scorer: scorers/test_verification/scorer.py
    outputs:
      coverage_pct: number          # 0-100
      stability_pct: number         # 0-100
      latest_build_passing: boolean
    medals:
      bronze:
        - coverage_pct >= 70
        - latest_build_passing == true
      silver:
        - coverage_pct >= 80
        - stability_pct >= 85
      gold:
        - coverage_pct >= 90
        - stability_pct >= 98

  documentation:
    scorer: scorers/documentation/scorer.py
    outputs:
      has_readme: boolean
      has_contributing: boolean
      has_security: boolean
      diataxis_coverage: number      # 0-4: tutorial/howto/reference/explanation
      style_linter_passing: boolean
      links_passing: boolean
    medals:
      bronze:
        - has_readme == true
        - has_contributing == true
        - has_security == true
        - links_passing == true
      silver:
        - diataxis_coverage >= 4
      gold:
        - style_linter_passing == true
        - diataxis_coverage == 4

  substrate_compat:
    scorer: scorers/substrate_compat/scorer.py
    outputs:
      supports_juju_3: boolean
      supports_juju_4: boolean
      supports_ck8s: boolean
    medals:
      # No explicit bronze: failing silver/gold → implicit bronze fallback.
      # A product on legacy substrates (e.g., Juju 2.9 only) lands at bronze.
      silver:
        - supports_juju_3 == true
      gold:
        - supports_juju_4 == true
        - supports_ck8s == true

  security_ssdlc:
    scorer: scorers/security_ssdlc/scorer.py
    outputs:
      cve_response: boolean          # team responds to critical CVEs
      ssdlc_standard: boolean        # aligns with SSDLC standard practices
      ssdlc_onboarded: boolean       # officially onboarded into company SSDLC
    medals:
      bronze:
        - cve_response == true
      silver:
        - ssdlc_standard == true
      gold:
        - ssdlc_onboarded == true

  support_engagement:
    scorer: scorers/support_engagement/scorer.py
    outputs:
      avg_triage_days: number        # average days to triage new issues
      avg_pr_review_days: number     # average days to review external PRs
    medals:
      # No explicit bronze: any level of support activity → implicit bronze.
      silver:
        - avg_triage_days <= 5
        - avg_pr_review_days <= 7
      gold:
        - avg_triage_days <= 2
        - avg_pr_review_days <= 3
```

- [ ] **Step 3: Create `computed/matrix.json`** (sample for local testing only)

```json
{
  "product_id": "matrix",
  "computed_at": "2026-06-29T20:00:00+00:00",
  "metrics": {
    "test_verification": {
      "coverage_pct": 87,
      "stability_pct": 94,
      "latest_build_passing": true
    },
    "documentation": {
      "has_readme": true,
      "has_contributing": true,
      "has_security": true,
      "diataxis_coverage": 3,
      "style_linter_passing": false,
      "links_passing": true
    },
    "substrate_compat": {
      "supports_juju_3": true,
      "supports_juju_4": false,
      "supports_ck8s": false
    },
    "security_ssdlc": {
      "cve_response": true,
      "ssdlc_standard": true,
      "ssdlc_onboarded": false
    },
    "support_engagement": {
      "avg_triage_days": 3,
      "avg_pr_review_days": 6
    }
  }
}
```

- [ ] **Step 4: Write the integration test**

```python
# engine/__tests__/test_integration.py
"""
End-to-end test: run the CLI against the sample matrix.yaml + matrix.json
and verify the expected medals are computed.

Expected per-dimension medals for computed/matrix.json:
  test_verification: silver  (coverage 87 >= 80, stability 94 >= 85; 87 < 90 → not gold)
  documentation:     bronze  (has all files + links_passing, but diataxis 3 < 4 → not silver)
  substrate_compat:  silver  (supports_juju_3=true; juju_4+ck8s false → not gold)
  security_ssdlc:    silver  (cve_response+ssdlc_standard=true; not onboarded → not gold)
  support_engagement: silver (triage 3 <= 5; pr_review 6 <= 7; both > gold threshold)

Overall current_medal: bronze (documentation pulls it down)
Target: gold → all dimensions drifting, but no history entries yet → drift=None
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def test_cli_computes_expected_medals_for_matrix():
    result = subprocess.run(
        [
            sys.executable, "-m", "engine",
            "--product", str(REPO_ROOT / "products/matrix.yaml"),
            "--computed", str(REPO_ROOT / "computed/matrix.json"),
            "--dimensions", str(REPO_ROOT / "config/dimensions.yaml"),
            "--drift-history", str(REPO_ROOT / "drift-history.json"),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed:\n{result.stderr}"

    output = json.loads(result.stdout)

    assert output["id"] == "matrix"
    assert output["current_medal"] == "bronze"
    assert output["target_medal"] == "gold"

    dims = output["dimensions"]
    assert dims["test_verification"]["medal"] == "silver"
    assert dims["documentation"]["medal"] == "bronze"
    assert dims["substrate_compat"]["medal"] == "silver"
    assert dims["security_ssdlc"]["medal"] == "silver"
    assert dims["support_engagement"]["medal"] == "silver"

    # No drift history entries yet → drift is null for all
    for dim in dims.values():
        assert dim["drift"] is None
```

- [ ] **Step 5: Run integration test to verify it fails**

```bash
pytest engine/__tests__/test_integration.py -v
```

Expected: `ERRORS` — `ModuleNotFoundError: No module named 'engine.__main__'`

- [ ] **Step 6: Create `engine/__main__.py`**

```python
# engine/__main__.py
"""
CLI entry point for the PQF medal engine.

Usage:
    python -m engine \
        --product products/matrix.yaml \
        --computed computed/matrix.json \
        --dimensions config/dimensions.yaml \
        --drift-history drift-history.json

    # With drift-history update (call after all per-dimension results are in):
    python -m engine ... --update-drift
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from engine.drift_tracker import update_drift_history
from engine.medal_engine import compute_product
from engine.models import DimensionResult, DriftState, Medal, ProductResult


def _drift_to_dict(drift: DriftState | None) -> dict | None:
    if drift is None:
        return None
    return {
        "status": drift.status,
        "first_seen_at": drift.first_seen_at,
        "deadline": drift.deadline,
    }


def _dimension_to_dict(dim: DimensionResult) -> dict:
    return {
        "medal": dim.medal.value,
        "target": dim.target.value,
        "metrics": dim.metrics,
        "drift": _drift_to_dict(dim.drift),
    }


def _result_to_portfolio_entry(result: ProductResult, product: dict) -> dict:
    """Produce the product entry as it appears in public/portfolio.json."""
    return {
        "id": result.product_id,
        "name": product.get("name", result.product_id),
        "description": product.get("description", ""),
        "lifecycle": product.get("lifecycle", ""),
        "target_medal": result.target_medal.value,
        "current_medal": result.current_medal.value,
        "squad": product.get("ownership", {}).get("squad", ""),
        "documentation_url": product.get("documentation_url", ""),
        "components": product.get("components", {}),
        "dimensions": {
            name: _dimension_to_dict(dim)
            for name, dim in result.dimensions.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PQF Medal Engine")
    parser.add_argument("--product", required=True, help="Path to products/<id>.yaml")
    parser.add_argument("--computed", required=True, help="Path to computed/<id>.json")
    parser.add_argument("--dimensions", required=True, help="Path to config/dimensions.yaml")
    parser.add_argument("--drift-history", required=True, dest="drift_history",
                        help="Path to drift-history.json")
    parser.add_argument("--update-drift", action="store_true", dest="update_drift",
                        help="Mutate drift-history.json with current run's results")
    args = parser.parse_args()

    product = yaml.safe_load(Path(args.product).read_text())

    computed_path = Path(args.computed)
    computed = json.loads(computed_path.read_text()) if computed_path.exists() else {}

    dimensions = yaml.safe_load(Path(args.dimensions).read_text())
    drift_history_path = Path(args.drift_history)
    drift_history = json.loads(drift_history_path.read_text())

    result = compute_product(product, computed, dimensions, drift_history)

    if args.update_drift:
        now = datetime.now(timezone.utc)
        for dim_name, dim_result in result.dimensions.items():
            update_drift_history(
                product["id"], dim_name, dim_result.medal,
                Medal(product["target_medal"]), drift_history, now,
            )
        drift_history_path.write_text(json.dumps(drift_history, indent=2) + "\n")

    entry = _result_to_portfolio_entry(result, product)
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Run the integration test**

```bash
pytest engine/__tests__/test_integration.py -v
```

Expected: `1 passed`

- [ ] **Step 8: Run the full test suite**

```bash
pytest engine/__tests__/ -v
```

Expected: all tests pass (≥ 50 tests)

- [ ] **Step 9: Verify the CLI works manually**

```bash
python -m engine \
  --product products/matrix.yaml \
  --computed computed/matrix.json \
  --dimensions config/dimensions.yaml \
  --drift-history drift-history.json
```

Expected output (abbreviated):
```json
{
  "id": "matrix",
  "name": "Matrix (Synapse)",
  "current_medal": "bronze",
  "target_medal": "gold",
  "dimensions": {
    "test_verification": { "medal": "silver", "drift": null, ... },
    "documentation": { "medal": "bronze", "drift": null, ... },
    ...
  }
}
```

- [ ] **Step 10: Run linter**

```bash
ruff check engine/ --fix
```

Expected: no errors (or auto-fixed)

- [ ] **Step 11: Final commit**

```bash
git add products/matrix.yaml config/dimensions.yaml computed/matrix.json \
        engine/__main__.py engine/__tests__/test_integration.py
git commit -m "feat: add CLI entry point, sample data, and integration test"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task(s) |
|---|---|
| `products/*.yaml` schema (id, name, lifecycle, target_medal, ownership, components) | Task 7 |
| `config/dimensions.yaml` with scorer contracts + medal rubrics | Task 7 |
| Medal levels: bronze/silver/gold/unrated | Task 2 |
| Current medal = lowest dimension score | Task 5 |
| Rubric: gold/silver/bronze with explicit and implicit bronze | Tasks 3-4 |
| Per-dimension drift tracking with independent windows | Task 6 |
| Drift deadlines: 6 months (gold target) / 12 months (silver target) | Task 6 |
| Drift statuses: remediating / overdue | Task 6 |
| Drift clock preserved when re-evaluating existing drift | Task 6 |
| Drift cleared when dimension returns to target | Task 6 |
| CLI entry point consuming all data files, outputting portfolio entry JSON | Task 7 |
| Missing computed data treated conservatively (unrated, not bronze) | Task 5 |

All spec requirements covered. ✅

**Placeholder scan:** No TBD, TODO, or incomplete steps found. ✅

**Type consistency check:**
- `Medal` enum used consistently throughout (never raw strings in function signatures)
- `drift_history` is always `dict` (parsed JSON, mutated in place)
- `compute_product` → `ProductResult`; `ProductResult.dimensions` → `dict[str, DimensionResult]`
- `DimensionResult.medal` and `.target` are always `Medal` instances ✅

---

## Next Plans

- **Plan 2: Scorers + GHA Pipeline** — 5 scorer folders (`test_verification`, `documentation`, `substrate_compat`, `security_ssdlc`, `support_engagement`) + `compute-metrics.yml` (matrix job) + badge SVG generation
- **Plan 3: UI** — React 19 + Vite app with 4 views (Overview, Product Detail, Dimension Detail, About) + `deploy-pages.yml`
