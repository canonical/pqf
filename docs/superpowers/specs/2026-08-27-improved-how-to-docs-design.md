# Design: Improved How-To Documentation for Adding Metrics and Dimensions

**Date:** 2026-08-27  
**Author:** Copilot (via brainstorming skill)  
**Status:** Implemented

---

## Problem

The existing `docs/adding-a-dimension.md` guide was incomplete as a practical tutorial:
- Used placeholder/fictional code rather than real patterns from the codebase
- Showed the wrong `scorer.py` pattern (`resolve_leaf_units` instead of `resolve_leaf_units_for`, missing `--products-dir` arg)
- Used `@responses.activate` mocking pattern instead of the `pytest-mock` pattern actually used in the project
- Did not explain *why* the pure/IO split exists or why helpers like `_file_exists` are used instead of `repo_file_exists` directly
- Had no concrete example — someone could read the guide and still not know how to add a metric in practice
- No visual feedback showing what the result looks like in the dashboard

Additionally, the guide conflated two distinct tasks: adding a metric to an existing dimension (common) vs. creating a whole new dimension (rare).

---

## Approach chosen: Split into two guides

- **`docs/adding-a-metric.md`** — Primary tutorial with a full example (`has_changelog` metric added to the `documentation` dimension), real code patterns, annotated diffs, and a dashboard screenshot
- **`docs/adding-a-dimension.md`** — Rewritten secondary guide for the rarer case of creating a brand-new dimension; cross-references the metric guide for scorer implementation patterns

This split matches how contributors actually work: adding a metric is far more common than spinning up a new dimension.

---

## What was built

### `docs/adding-a-metric.md` (new file)

- Concept map showing how a metric flows from `logic.py` → `dimensions.yaml` → `portfolio.json` → dashboard
- Prerequisites section
- 8-step example adding `has_changelog` to the `documentation` dimension
  - Steps use real code patterns from `scorers/documentation/logic.py`
  - Each step explains the *why* behind design decisions
  - Step 5 shows the correct `pytest-mock` test pattern including why to patch at the import site
  - Step 7 shows the dashboard screenshot of the new metric appearing
- Reference table of `shared.github_signals` helpers
- Troubleshooting FAQ covering the 6 most common errors

### `docs/adding-a-dimension.md` (rewritten)

- Added "when to add a dimension vs. a metric" decision guidance
- `scorer.py` template updated to match real `resolve_leaf_units_for` + `--products-dir` pattern
- `logic.py` template updated to use `shared.github_signals` helpers instead of raw `requests`
- Tests updated to use `pytest-mock` pattern (not `@responses.activate`)
- LLM mocking section corrected to match real OpenAI client mock pattern
- Checklist expanded to include `scorer.py` and `Makefile` entries

### Supporting changes

- `scorers/documentation/logic.py` — Added `_has_changelog` helper and returned `has_changelog` from `compute_metrics` (example implementation)
- `scorers/documentation/__tests__/test_logic.py` — Updated default-false test; added `test_has_changelog_true_when_file_exists` and `test_has_changelog_false_when_file_missing`
- `config/dimensions.yaml` — Added `has_changelog` to documentation dimension outputs (informational)
- `docs/screenshots/dimension-detail-documentation-after.png` — Playwright screenshot showing the new metric in the dashboard
- `AGENTS.md` — Updated "Further reading" section to include the new guide

---

## Constraints respected

- All test patterns use `pytest-mock` (consistent with the rest of the test suite)
- `logic.py` remains pure — no `os.environ`, no file I/O
- `scorer.py` uses `resolve_leaf_units_for` (not the deprecated `resolve_leaf_units`)
- `has_changelog` is `informational: true` — it does not gate medals without an explicit decision
- All 263 existing tests pass; `make lint` passes
