# Phase 2 Metric Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the documentation dimension to baseline presence checks and fix leaf scoring so top-level charm/snap products still score correctly.

**Architecture:** Keep the documentation scorer deterministic and minimal: it should report whether required docs exist and whether docs CI evidence exists, without trying to enforce a maturity template. In the engine, keep `resolve_leaf_units_for()` as the central scoring lookup, but make it return a real leaf unit when the requested product is itself a top-level charm/snap leaf instead of returning an empty list. Validate the change with the existing pytest suite and the local scoring pipeline.

**Tech Stack:** Python 3, PyYAML, pytest, Makefile targets, existing PQF scoring CLI.

## Global Constraints

- Documentation metrics are baseline presence checks only: file exists, file is non-empty, no template-shape or heading taxonomy requirement.
- `documentation_workflows_passing` is informational only and must not gate medals.
- Top-level charm/snap product YAMLs remain scorable as leaf products, but they should not be treated as roots.
- Keep metrics simple, distinguish measured-low from unmeasured, use only sanctioned structural variants.

---

### Task 1: Simplifying the documentation metric contract

**Files:**
- Modify: `config/dimensions.yaml`
- Modify: `scorers/documentation/logic.py`
- Modify: `scorers/documentation/__tests__/test_logic.py`
- Modify: `engine/__tests__/test_integration.py`
- Modify: `docs/local-scoring.md`

**Interfaces:**
- Consumes: `compute_metrics(unit, github_token, openrouter_api_key, model=None)` from `scorers/documentation/logic.py`
- Produces: documentation metric keys `readme_present`, `contributing_present`, `has_security`, `documentation_workflows_passing`, `diataxis_coverage`, `tutorial_tested`, `uses_rtd_hosting`, `recent_release_notes_present`
- Produces: documentation rubric that only gates bronze on `readme_present`, `contributing_present`, and `has_security`

- [ ] **Step 1: Write the failing test**

Replace the current documentation expectation with a baseline-presence assertion in `scorers/documentation/__tests__/test_logic.py`:

```python
def test_compute_metrics_uses_presence_keys(mocker):
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path in {"README.md", "CONTRIBUTING.md", "SECURITY.md"},
    )
    mocker.patch(
        "scorers.documentation.logic.repo_file_text",
        side_effect=lambda repo, path, token: {
            "README.md": "# Project\n",
            "CONTRIBUTING.md": "# Contributing\n",
        }.get(path, ""),
    )
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {"name": "docs lint", "conclusion": "success"},
            {"name": "link check", "conclusion": "success"},
            {"name": "docs build", "conclusion": "success"},
        ],
    )

    result = compute_metrics(UNIT, "gh-token", "or-key")

    assert result["readme_present"] is True
    assert result["contributing_present"] is True
    assert result["has_security"] is True
    assert result["documentation_workflows_passing"] is True
    assert "readme_meets_structure" not in result
    assert "contributing_meets_structure" not in result
```

Also update `engine/__tests__/test_integration.py` so the fixture and config assertions use the renamed keys:

```python
"documentation": {
    "readme_present": True,
    "contributing_present": True,
    "has_security": True,
    "documentation_workflows_passing": True,
    "diataxis_coverage": 3,
    "tutorial_tested": False,
    "uses_rtd_hosting": False,
    "recent_release_notes_present": False,
},
```

and:

```python
assert dimensions["dimensions"]["documentation"]["required_metrics_for_scoring"] == [
    "readme_present",
    "contributing_present",
    "has_security",
]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py engine/__tests__/test_integration.py -v
```

Expected: fail with missing `readme_present` / `contributing_present` keys and stale rubric expectations.

- [ ] **Step 3: Write the minimal implementation**

Update `scorers/documentation/logic.py` so the baseline metrics are presence-based:

```python
def _readme_present(unit: EvaluationUnit, github_token: str | None) -> bool:
    return bool(_file_text(unit, "README.md", github_token).strip())


def _contributing_present(unit: EvaluationUnit, github_token: str | None) -> bool:
    return bool(_file_text(unit, "CONTRIBUTING.md", github_token).strip())


return {
    "readme_present": _readme_present(unit, github_token),
    "contributing_present": _contributing_present(unit, github_token),
    "has_security": _file_exists(unit, "SECURITY.md", github_token),
    "documentation_workflows_passing": _documentation_workflows_passing(check_runs),
    "diataxis_coverage": _diataxis_coverage(unit, github_token),
    "tutorial_tested": _tutorial_tested(unit, github_token, check_runs),
    "uses_rtd_hosting": _uses_rtd_hosting(unit, github_token),
    "recent_release_notes_present": _recent_release_notes_present(unit, github_token),
}
```

Update `config/dimensions.yaml` so documentation only gates bronze on the new presence metrics:

```yaml
documentation:
  required_metrics_for_scoring:
    - readme_present
    - contributing_present
    - has_security
  outputs:
    readme_present: {type: boolean, label: "README present", description: "README.md exists and is non-empty."}
    contributing_present: {type: boolean, label: "CONTRIBUTING present", description: "CONTRIBUTING.md exists and is non-empty."}
    has_security: {type: boolean, label: "SECURITY present", description: "SECURITY.md exists in the primary repository."}
    documentation_workflows_passing: {type: boolean, label: "Documentation workflows passing", description: "Documentation-specific CI workflows (lint, link-check, build) are present and passing on default branch."}
  medals:
    bronze: ["readme_present == true", "contributing_present == true", "has_security == true"]
```

Update `docs/local-scoring.md` so the contract examples and metric names match the new baseline semantics.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
pytest scorers/documentation/__tests__/test_logic.py engine/__tests__/test_integration.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add config/dimensions.yaml scorers/documentation/logic.py scorers/documentation/__tests__/test_logic.py engine/__tests__/test_integration.py docs/local-scoring.md
git commit -m "fix(documentation): simplify baseline metric contract"
```

### Task 2: Returning a real leaf unit for standalone top-level charm/snap products

**Files:**
- Modify: `engine/graph.py`
- Modify: `engine/__tests__/test_graph.py`

**Interfaces:**
- Consumes: `resolve_leaf_units_for(graph: ProductGraph, root_product_id: str) -> list[EvaluationUnit]`
- Produces: a single `EvaluationUnit` when the requested product is a top-level charm/snap leaf with no `composed_of` entries, while preserving current root composition behavior

- [ ] **Step 1: Write the failing test**

Add a direct regression test to `engine/__tests__/test_graph.py`:

```python
def test_resolve_leaf_units_for_returns_self_for_top_level_leaf_product():
    graph = build_graph([STANDALONE_LEAF])

    units = resolve_leaf_units_for(graph, "postgresql-k8s")

    assert len(units) == 1
    assert units[0].product_id == "postgresql-k8s"
    assert units[0].repo == "canonical/postgresql-k8s-operator"
    assert units[0].target_medal == "gold"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest engine/__tests__/test_graph.py::test_resolve_leaf_units_for_returns_self_for_top_level_leaf_product -v
```

Expected: fail because `resolve_leaf_units_for()` currently returns an empty list for `STANDALONE_LEAF`.

- [ ] **Step 3: Write the minimal implementation**

Update `engine/graph.py` so `resolve_leaf_units_for()` falls back to the product itself when the requested node is a charm/snap leaf with no composed leaves:

```python
def resolve_leaf_units_for(graph: ProductGraph, root_product_id: str) -> list[EvaluationUnit]:
    root = graph.nodes.get(root_product_id)
    if root is None:
        raise ValueError(f"Product {root_product_id!r} not found in graph.")

    if root.product_type in (ProductType.CHARM, ProductType.SNAP) and not root.composed_of:
        target = root.target_medal or "bronze"
        return [
            EvaluationUnit(
                product_id=root.id,
                product_type=root.product_type,
                repo=root.source_repo or "",
                subpath=root.source_subpath,
                allure_report_url=root.allure_report_url,
                documentation_url=root.documentation_url,
                target_medal=target,
            )
        ]

    leaf_ids = {edge.product_id for edge in root.composed_of}
    units = []
    for node in graph.nodes.values():
        if node.id not in leaf_ids:
            continue
        if node.product_type not in (ProductType.CHARM, ProductType.SNAP):
            continue
        target = root.target_medal if node.target_medal is None else node.target_medal
        units.append(
            EvaluationUnit(
                product_id=node.id,
                product_type=node.product_type,
                repo=node.source_repo or "",
                subpath=node.source_subpath,
                allure_report_url=node.allure_report_url,
                documentation_url=node.documentation_url,
                target_medal=target,
            )
        )
    return units
```

Keep the existing root composition behavior unchanged so `matrix` still resolves `synapse` and `saml-integrator` through `composed_of`.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
pytest engine/__tests__/test_graph.py -v
```

Expected: pass, including the existing composition tests.

- [ ] **Step 5: Commit**

```bash
git add engine/graph.py engine/__tests__/test_graph.py
git commit -m "fix(graph): score standalone leaf products directly"
```

### Task 3: Re-score and verify the portfolio outputs

**Files:**
- Modify: `computed/*.json`
- Modify: `public/portfolio.json`

**Interfaces:**
- Consumes: updated documentation metric names and updated leaf resolution behavior
- Produces: refreshed computed artifacts and a portfolio JSON that reflects the new baseline documentation rubric

- [ ] **Step 1: Run the failing-to-passing verification**

Run:

```bash
make score-no-llm PRODUCT=matrix
make score-no-llm PRODUCT=saml-integrator
```

Expected:
- `matrix` scores normally and includes `saml-integrator` through composition.
- `saml-integrator` returns a real leaf result instead of an empty output.

- [ ] **Step 2: Rebuild the portfolio**

Run:

```bash
make score-all-no-llm
```

Expected: completes successfully and regenerates `computed/*.json` plus `public/portfolio.json`.

- [ ] **Step 3: Sanity-check the resulting spread**

Run:

```bash
python3 - <<'PY'
import json
from collections import Counter
portfolio = json.loads(open("public/portfolio.json").read())
counts = Counter((p["dimensions"]["documentation"]["medal"] for p in portfolio["products"] if p["product_type"] in ("charm", "snap")))
print(dict(counts))
PY
```

Expected: documentation no longer reports an all-bronze portfolio caused by template-shape false negatives.

- [ ] **Step 4: Commit**

```bash
git add computed public/portfolio.json
git commit -m "chore: refresh computed metrics after documentation simplification"
```
