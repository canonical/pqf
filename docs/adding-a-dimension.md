# Adding a Quality Dimension

This guide explains how to create a new quality dimension with a scorer in PQF.

---

## Overview

A quality dimension is one axis of the medal rubric (e.g., Test Verification, Documentation, Security). Adding a dimension requires:

1. An entry in `config/dimensions.yaml` — declares the dimension's outputs and medal criteria
2. A new `scorers/<name>/` directory with `logic.py`, `scorer.py`, and tests

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

If your dimension only applies to charms, set `applies_to.product_types: [charm]`. Root products automatically return `not_applicable` for this dimension and are not penalized in their medal calculation.

### Medal criteria syntax

Each criterion is a string evaluated against the product's computed metrics:

| Syntax | Example |
|--------|---------|
| `metric >= value` | `coverage_pct >= 80` |
| `metric <= value` | `avg_triage_days <= 5` |
| `metric == true` | `has_readme == true` |
| `metric == false` | `has_violations == false` |

Medal tiers are **cumulative** — a product earning silver must also satisfy all bronze criteria.

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
- Accepts `unit: EvaluationUnit` and optionally `github_token: str | None`
- Returns `dict[str, Any]` with **exactly** the keys declared in `dimensions.yaml` outputs
- Has **no side effects** — no `os.environ`, no file I/O, no print statements

Use `unit.repo`, `unit.subpath`, `unit.allure_report_url`, and `unit.documentation_url` to access the leaf product's source information.

```python
from __future__ import annotations
from typing import Any
import requests

from engine.models import EvaluationUnit

_GITHUB_API = "https://api.github.com"


def _make_github_session(github_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"******",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return session


def compute_metrics(unit: EvaluationUnit, github_token: str | None = None) -> dict[str, Any]:
    some_boolean = False
    some_number = 0.0

    if github_token and unit.repo:
        session = _make_github_session(github_token)
        # ... make API calls, compute metrics
        resp = session.get(f"{_GITHUB_API}/repos/{unit.repo}", timeout=15)
        if resp.ok:
            some_boolean = True
            some_number = 75.0

    return {
        "some_boolean": some_boolean,
        "some_number": some_number,
    }
```

---

## Step 4: Write tests in `__tests__/test_logic.py`

Mock all HTTP with `@responses.activate`. Never make real network calls in tests.

```python
import pytest
import responses as resp_lib
from engine.models import EvaluationUnit, ProductType
from scorers.my_dimension.logic import compute_metrics

UNIT = EvaluationUnit(
    product_id="test-charm",
    product_type=ProductType.CHARM,
    repo="canonical/test-repo",
)


def test_returns_defaults_when_no_token():
    result = compute_metrics(UNIT)
    assert result["some_boolean"] is False
    assert result["some_number"] == 0.0


@resp_lib.activate
def test_some_boolean_true_when_api_ok():
    resp_lib.add(
        resp_lib.GET,
        "https://api.github.com/repos/canonical/test-repo",
        json={"default_branch": "main"},
        status=200,
    )
    result = compute_metrics(UNIT, github_token="test-token")
    assert result["some_boolean"] is True


@resp_lib.activate
def test_some_boolean_false_when_api_fails():
    resp_lib.add(
        resp_lib.GET,
        "https://api.github.com/repos/canonical/test-repo",
        status=403,
    )
    result = compute_metrics(UNIT, github_token="test-token")
    assert result["some_boolean"] is False
```

Run the tests:

```bash
python3 -m pytest scorers/my_dimension/ -v
```

---

## Step 5: Write `scorer.py` (IO wrapper)

```python
#!/usr/bin/env python3
"""my_dimension scorer — reads GITHUB_TOKEN from env, calls logic.compute_metrics per leaf unit."""
import argparse
import json
import os
import sys
from pathlib import Path
import yaml

from engine.graph import build_graph, resolve_leaf_units
from scorers.my_dimension.logic import compute_metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-yaml", required=True)
    args = parser.parse_args()

    product = yaml.safe_load(Path(args.product_yaml).read_text())
    graph = build_graph([product])
    units = resolve_leaf_units(graph)

    github_token = os.environ.get("GITHUB_TOKEN")

    results = {}
    for unit in units:
        results[unit.product_id] = compute_metrics(unit, github_token=github_token)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## Step 6: Register the scorer in `Makefile`

Add the new scorer to the `score` target in `Makefile`:

```makefile
	$(PYTHON) scorers/my_dimension/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/my_dimension.json
```

---

## Step 7: Checklist before opening a PR

- [ ] `config/dimensions.yaml` has the new dimension with `label`, `description`, `applies_to`, `aggregation`, `outputs`, and `medals`
- [ ] `scorers/my_dimension/logic.py` accepts `EvaluationUnit` and returns exactly the keys declared in `outputs`
- [ ] `scorers/my_dimension/__tests__/test_logic.py` tests all main code paths (token missing, API ok, API failing)
- [ ] `make test` passes (all Python tests)
- [ ] `make lint` passes
- [ ] `make score PRODUCT=<any-product>` runs without error (needs real `GITHUB_TOKEN`)

---

## Mocking LLM calls (for AI-assisted scorers)

If your scorer uses OpenRouter, mock the client with `pytest-mock`:

```python
def test_llm_scorer(mocker):
    mock_client = mocker.patch("scorers.my_dimension.logic.openai.OpenAI")
    mock_instance = mock_client.return_value
    mock_instance.chat.completions.create.return_value = mocker.Mock(
        choices=[mocker.Mock(message=mocker.Mock(content='{"result": true}'))]
    )
    result = compute_metrics(UNIT, github_token="tok", openrouter_api_key="key")
    assert result["result"] is True
```
