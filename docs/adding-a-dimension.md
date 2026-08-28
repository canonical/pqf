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

A quality dimension is one axis of the result rubric (e.g., Test Verification, Documentation, Security). Adding a dimension requires:

1. An entry in `config/dimensions.yaml` — declares the dimension's outputs and result criteria
2. A new `scorers/<name>/` directory with `logic.py`, `scorer.py`, and tests
3. Registration in the `Makefile`

---

## Step 1: Add the dimension to `config/dimensions.yaml`

Add a new top-level entry under `dimensions:`:

```yaml
  my_dimension:
    label: "My Dimension"
    description: "One sentence describing what this dimension measures."
    scorer: scorers/my_dimension/scorer.py
    applies_to:
      product_types: [charm, snap]   # which product types this dimension scores
    aggregation: worst_in_scope
    outputs:
      some_boolean:
        type: boolean
        label: "Human-readable label"
        description: "What this metric checks and how."
        # ai_assisted: true   # Uncomment if scored by LLM, not GitHub API
      some_number:
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

## Step 5: Write `scorer.py` (IO wrapper)

`scorer.py` is thin: it reads env vars, resolves leaf units, calls `compute_metrics`, and prints
JSON. Copy the pattern used by existing scorers exactly. In particular, keep the CLI arguments
and the `resolve_leaf_units_for(...)` call unchanged unless you have a specific reason to alter
them: PQF relies on that shape to resolve `ref:` entries and the correct set of leaf products.

```python
#!/usr/bin/env python3
"""my_dimension scorer — iterates leaf products and outputs per-leaf metrics."""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_all_products(products_dir: Path) -> list[dict]:
    return [yaml.safe_load(f.read_text()) for f in sorted(products_dir.glob("*.yaml"))]


def main() -> int:
    from engine.graph import build_graph, resolve_leaf_units_for
    from scorers.my_dimension.logic import compute_metrics

    parser = argparse.ArgumentParser()
    parser.add_argument("--product-yaml", required=True)
    parser.add_argument("--products-dir", default=None)
    args = parser.parse_args()

    github_token = os.environ["GITHUB_TOKEN"]

    product_path = Path(args.product_yaml)
    product = yaml.safe_load(product_path.read_text())
    product_id = product["id"]

    products_dir = Path(args.products_dir) if args.products_dir else product_path.parent
    all_products = _load_all_products(products_dir)
    graph = build_graph(all_products)
    units = resolve_leaf_units_for(graph, product_id)

    results = {}
    for unit in units:
        results[unit.product_id] = compute_metrics(unit, github_token)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

If your scorer requires additional credentials (e.g., `OPENROUTER_API_KEY`), read them from env
vars in `main()` and pass them as parameters to `compute_metrics` — never read them in `logic.py`.

---

## Step 6: Register the scorer in `Makefile`

Add the new scorer to the `score` and `score-no-llm` targets in `Makefile`. Find the existing
scorer lines (they all follow the same pattern) and add yours in alphabetical order:

```makefile
	$(PYTHON) scorers/my_dimension/scorer.py --product-yaml products/$(PRODUCT).yaml \
		--products-dir products \
		> $(SCORE_DIR)/$(PRODUCT)/my_dimension.json
```

Add it to **both** `score` and `score-no-llm` targets so `make score-all-no-llm` runs your scorer.

---

## Step 7: Verify locally

Run the full pipeline to see your new dimension appear in the dashboard:

```bash
make score-no-llm PRODUCT=<any-product>
make _merge PRODUCT=<any-product>
make _assemble
make dev   # → http://localhost:5173
```

See [Running scorers locally](local-scoring.md) for the full workflow.

---

## Step 8: Checklist before opening a PR

- [ ] `config/dimensions.yaml` has the new dimension with `label`, `description`, `applies_to`, `aggregation`, `outputs`, and `medals`
- [ ] `scorers/my_dimension/logic.py` is a pure function — no `os.environ`, no file I/O; returns exactly the keys declared in `outputs`
- [ ] `scorers/my_dimension/scorer.py` reads env vars and calls `compute_metrics`; uses `resolve_leaf_units_for`
- [ ] `scorers/my_dimension/__tests__/test_logic.py` tests all main code paths (signals present, signals missing)
- [ ] `Makefile` — scorer added to both `score` and `score-no-llm` targets
- [ ] `make test` passes (all Python tests)
- [ ] `make lint` passes
- [ ] `make score-no-llm PRODUCT=<any-product>` runs without error
- [ ] `make _merge PRODUCT=<any-product> && make _assemble` updates `public/portfolio.json`
- [ ] New dimension appears correctly in the dashboard (`make dev`)
