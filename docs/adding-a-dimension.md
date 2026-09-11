# Adding a Quality Dimension

This guide explains how to create a brand-new quality dimension with a scorer in PQF — for
example, adding an entirely new axis like "Observability" or "Accessibility" to the medal rubric.

> **Adding a metric to an existing dimension?** That is a more common and simpler task. See
> [adding-a-metric.md](adding-a-metric.md) instead — it covers the common case with a full
> example.

---

## When to add a new dimension vs. a new metric

Add a **new metric** (to an existing dimension) when the signal you want to measure fits naturally
within an existing quality axis and shares the same scorer infrastructure.

Add a **new dimension** when:
- The quality axis is conceptually distinct from all existing dimensions (Test Verification,
  Documentation, Security, Substrate Compatibility, Engagement)
- It requires its own scorer binary with different API calls or external integrations
- The team has agreed to track this axis across PQF-tracked products

---

## Overview

A quality dimension is one axis of the result rubric (e.g., Test Verification, Documentation, Security). Dimensions are declared **per framework version**, so adding a dimension requires:

1. An entry in one framework version's `framework/versions/<version>/dimensions.yaml` — declares the dimension's outputs (each selecting a metric implementation revision) and result criteria
2. Metric implementation bindings in `scorers/registry.py`
3. A new `scorers/<name>/` directory with `logic.py`, `scorer.py`, and tests
4. A runner entry in `scorers/registry.py` so the dimension can be dispatched

> **Which framework version?** Add new dimensions to the **upcoming** version
> (`framework/versions/v1/`). Adding a scored dimension to the **active** version changes today's
> official compliance view and needs explicit framework-owner review; CI's semantic change report
> flags it as a scoring-semantic change. **Archived** versions are frozen and must never be edited
> to change scoring. A framework contract is a full snapshot — editing one version never affects
> another.

---

## Step 1: Add the dimension to the framework contract

Add a new top-level entry under `dimensions:` in `framework/versions/<version>/dimensions.yaml`:

```yaml
  my_dimension:
    label: "My Dimension"
    description: "One sentence describing what this dimension measures."
    scorer: scorers/my_dimension/scorer.py
    applies_to:
      product_types: [charm, snap]   # which product types this dimension scores
    aggregation: worst_in_scope
    required_metrics_for_scoring:
      - some_boolean
    outputs:
      some_boolean:
        implementation: "my-boolean-signal/v1"
        type: boolean
        label: "Human-readable label"
        description: "What this metric checks and how."
        # ai_assisted: true   # Uncomment if scored by LLM, not GitHub API
      some_number:
        implementation: "my-number-signal/v1"
        type: number
        range: "0–100"
        label: "Human-readable label"
        description: "What this metric measures."
    medals:
      bronze:
        - some_boolean == true
      silver:
        - some_number >= 70
      gold:
        - some_number >= 90
```

Each output selects an immutable **metric implementation revision**. The metric ID (`some_number`)
is the stable, user-facing concept; the implementation ID (`my-number-signal/v1`) identifies the
concrete measurement logic. Changing how a metric is measured means publishing a new revision
(`.../v2`) and pointing a contract at it — never editing an existing revision's behaviour in place.

`required_metrics_for_scoring` lists the keys that must be measurable for the dimension to be
scored; a `null` value for any of them makes the dimension `insufficient_data` / `unrated`. Keep
that list to signals you can measure reliably across the fleet.

If your dimension only applies to charms, set `applies_to.product_types: [charm]`. Root products automatically return `not_applicable` for this dimension and are not penalized in their result calculation.

### Result criteria syntax

Each criterion is a string evaluated against the product's computed metrics:

| Syntax | Example |
|--------|---------|
| `metric >= value` | `coverage_pct >= 80` |
| `metric <= value` | `avg_triage_days <= 5` |
| `metric == true` | `has_readme == true` |
| `metric == false` | `has_violations == false` |

Result tiers are **cumulative** — a product earning silver must also satisfy all bronze criteria.

### `ai_assisted` flag

Set `ai_assisted: true` on any output metric that is scored by an LLM rather than deterministic API checks. The UI renders an **✦ AI** badge next to that metric in the Dimension Detail page.

---

## Step 2: Create the scorer directory

```bash
mkdir -p scorers/my_dimension/__tests__
touch scorers/my_dimension/__init__.py
touch scorers/my_dimension/logic.py
touch scorers/my_dimension/scorer.py
touch scorers/my_dimension/__tests__/__init__.py
touch scorers/my_dimension/__tests__/test_logic.py
```

---

## Step 3: Write `logic.py` (pure function)

`logic.py` must contain a `compute_metrics` function that:
- Accepts `unit: EvaluationUnit` and any credentials it needs (e.g. `github_token: str`)
- Returns `dict[str, Any]` with **exactly** the keys declared in `dimensions.yaml` `outputs`
- Has **no side effects** — no `os.environ`, no file I/O, no print statements

Use `unit.repo`, `unit.subpath`, `unit.allure_report_url`, and `unit.documentation_url` to access
the leaf product's source information.

Use helpers from `scorers.shared.github_signals` rather than making raw `requests` calls — they
handle auth retry, base URL, and monorepo subpath scoping automatically. See
[adding-a-metric.md — Reference: shared GitHub signal helpers](adding-a-metric.md#reference-shared-github-signal-helpers)
for the full list.

```python
from __future__ import annotations
from typing import Any

from engine.models import EvaluationUnit
from scorers.shared.github_signals import repo_file_exists, workflow_files


def _my_boolean_check(unit: EvaluationUnit, github_token: str | None) -> bool:
    """Return True if the repository has the expected signal."""
    return repo_file_exists(unit.repo, "SOME_FILE.md", github_token)


def _my_number_check(unit: EvaluationUnit, github_token: str | None) -> float:
    """Return a score 0–100 based on some repository signal."""
    files = workflow_files(unit.repo, github_token)
    # ... derive a number from the files
    return 75.0 if files else 0.0


def compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]:
    return {
        "some_boolean": _my_boolean_check(unit, github_token),
        "some_number": _my_number_check(unit, github_token),
    }
```

For a real example of a complete `logic.py`, read
[`scorers/documentation/logic.py`](../scorers/documentation/logic.py) — it shows the standard
import pattern, helper structure, and `compute_metrics` signature used across the project.

---

## Step 4: Write tests in `__tests__/test_logic.py`

Use `pytest-mock` to patch shared helpers at their import site in `logic.py`. Never make real
network calls in tests.

```python
from engine.models import EvaluationUnit, ProductType
from scorers.my_dimension.logic import compute_metrics

UNIT = EvaluationUnit(
    product_id="test-charm",
    product_type=ProductType.CHARM,
    repo="canonical/test-repo",
)


def test_returns_defaults_when_signals_missing(mocker):
    mocker.patch("scorers.my_dimension.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.my_dimension.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "test-token")

    assert result == {
        "some_boolean": False,
        "some_number": 0.0,
    }


def test_boolean_true_when_file_exists(mocker):
    mocker.patch(
        "scorers.my_dimension.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path == "SOME_FILE.md",
    )
    mocker.patch("scorers.my_dimension.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "test-token")
    assert result["some_boolean"] is True
```

> **Why `scorers.my_dimension.logic.repo_file_exists` and not
> `scorers.shared.github_signals.repo_file_exists`?**
> Python's mock patches the name as it is used in the module under test. Since `logic.py`
> imports `repo_file_exists` directly, you patch it at its import site in `logic`.

Run the tests:

```bash
python3 -m pytest scorers/my_dimension/ -v
```

### Mocking LLM calls (for AI-assisted scorers)

If your scorer uses OpenRouter, mock the OpenAI client with `pytest-mock`:

```python
def test_llm_scorer(mocker):
    mock_client = mocker.patch("scorers.my_dimension.logic.OpenAI")
    mock_instance = mock_client.return_value
    mock_instance.chat.completions.create.return_value = mocker.Mock(
        choices=[mocker.Mock(message=mocker.Mock(content='{"result": true}'))]
    )
    result = compute_metrics(UNIT, github_token="tok", openrouter_api_key="key")
    assert result["result"] is True
```

---

## Step 5: Write `scorer.py` (thin wrapper)

Scorer execution is centralised in the version-aware runner `scorers/run.py`. It resolves the
framework contract, rejects archived versions, builds the version-filtered product graph, resolves
leaf units, reads credentials from the environment, and dispatches the implementation revisions the
selected contract declares. Your `scorer.py` is a four-line compatibility wrapper that pins the
dimension:

```python
#!/usr/bin/env python3
"""my_dimension scorer compatibility wrapper."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scorers.run import main as run_main  # noqa: E402


def main() -> int:
    return run_main(fixed_dimension="my_dimension")


if __name__ == "__main__":
    sys.exit(main())
```

Do not read credentials in `logic.py`, and never branch on the framework version inside metric
logic. If your dimension needs an additional credential, add it to `ScorerContext` in
`scorers/registry.py` and pass it through the runner function.

---

## Step 6: Register the runner and metric implementations

`scorers/registry.py` is the dispatch table. Add three things:

```python
# 1. a runner that calls your pure logic
def _run_my_dimension(unit: EvaluationUnit, context: ScorerContext) -> dict[str, Any]:
    return my_dimension_logic.compute_metrics(unit, context.github_token)


# 2. register it (and its source file, used for implementation fingerprints)
RUNNERS = MappingProxyType({..., "my_dimension": _run_my_dimension})
RUNNER_SOURCE_FILES = MappingProxyType({..., "my_dimension": Path(my_dimension_logic.__file__).resolve()})


# 3. bind each implementation revision declared by the contract
METRIC_BINDINGS = MappingProxyType({
    ...,
    "my-boolean-signal/v1": MetricBinding(
        dimension="my_dimension",
        output_key="some_boolean",
        runner_key="my_dimension",
    ),
    "my-number-signal/v1": MetricBinding(
        dimension="my_dimension",
        output_key="some_number",
        runner_key="my_dimension",
    ),
})
```

`make validate` fails if a contract declares an unknown implementation, one that belongs to another
dimension, one that resolves to a different output key, or one whose runner is not registered. No
`Makefile` change is needed: `make score` discovers the selected framework version's dimensions
with `python -m engine.framework --list-dimensions` and loops over them.

---

## Step 7: Verify locally

Run the full pipeline against the framework version you edited to see your new dimension in the
dashboard. Every runtime command takes an explicit `FRAMEWORK_VERSION`:

```bash
make validate
make score-no-llm PRODUCT=<any-product> FRAMEWORK_VERSION=<version>
make _merge PRODUCT=<any-product> FRAMEWORK_VERSION=<version>
make _assemble FRAMEWORK_VERSION=<version>
make _version-index
make dev   # → http://localhost:5173, then pick that version in the framework selector
```

The generated `computed/`, `public/`, and `.pqf-score/` files are GHA-maintained previews —
inspect them locally, but never commit them. See [Run PQF locally](local-scoring.md) for
AI-assisted scoring, full-portfolio runs, and generated-artifact guidance.

---

## Step 8: Checklist before opening a PR

- [ ] `framework/versions/<version>/dimensions.yaml` has the new dimension with `label`, `description`, `applies_to`, `aggregation`, `required_metrics_for_scoring`, `outputs` (each with an `implementation`), and `medals`
- [ ] The dimension was added to the **upcoming** version, or an active-contract change was explicitly agreed with framework owners
- [ ] `scorers/registry.py` — runner, runner source file, and one `MetricBinding` per declared implementation
- [ ] `scorers/my_dimension/logic.py` is a pure function — no `os.environ`, no file I/O, no framework-version branching; returns exactly the keys declared in `outputs`
- [ ] `scorers/my_dimension/scorer.py` delegates to `scorers.run.main(fixed_dimension=...)`
- [ ] `scorers/my_dimension/__tests__/test_logic.py` tests all main code paths (signals present, signals missing)
- [ ] `make validate` passes
- [ ] `make test` passes (all Python tests)
- [ ] `make lint` passes
- [ ] `make score-no-llm PRODUCT=<any-product> FRAMEWORK_VERSION=<version>` runs without error
- [ ] `make _merge PRODUCT=<any-product> FRAMEWORK_VERSION=<version> && make _assemble FRAMEWORK_VERSION=<version>` updates `public/versions/<version>/portfolio.json`
- [ ] New dimension appears correctly in the dashboard under that framework version (`make dev`)
- [ ] No generated `computed/`, `public/`, or `.pqf-score/` preview files are staged
