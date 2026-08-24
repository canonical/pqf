# PQF Architecture

---

## Data Flow

```
products/*.yaml          config/dimensions.yaml
      │                          │
      │           ┌──────────────┘
      ▼           ▼
  engine/graph.py              (builds product graph; extracts inline leaves)
      │
      ▼
  evaluation units             (one per leaf product: repo + optional subpath)
      │
      ▼
  scorers/{dim}/scorer.py      (per evaluation unit; outputs per-leaf metric dict)
      │
      ▼
  computed/{product}.json      (leaf_metrics envelope; GHA-written, never hand-edited)
      │
      ▼
  engine/assemble.py           (worst-in-scope aggregation → results; portfolio assembly)
      │
      ├─► public/portfolio.json    (single data source for UI)
      └─► public/badges/
      │
      ▼
  ui/ (React 19 + Vite)
      │
      ▼
  GitHub Pages
```

---

## Component Responsibilities

| Directory | Owner | Responsibility |
|-----------|-------|---------------|
| `products/` | PE team (PR-reviewed) | One YAML per product — manually maintained source of truth |
| `config/dimensions.yaml` | Contributors | Result rubrics, scorer contracts, output metadata |
| `scorers/{dim}/` | Contributors | `logic.py` (pure, testable) + `scorer.py` (IO wrapper) |
| `computed/` | GHA only | `leaf_metrics` envelope keyed by leaf product ID — **never hand-edited** |
| `engine/` | Contributors | Result computation, drift tracking, portfolio assembly |
| `public/` | GHA only | `portfolio.json` + badge SVGs — **never hand-edited** |
| `ui/` | Contributors | React SPA reading `portfolio.json` |
| `.github/workflows/` | Contributors | Two GHA workflows (see below) |

---

## Product Graph Model

### `product_type` enum

Every node in the product graph has a `product_type`:

| Value | Meaning |
|-------|---------|
| `root` | Top-level portfolio entry. Has no source repo of its own. Composed of one or more leaf products. Its result is the worst across all scored leaves. |
| `charm` | A Juju charm — the primary unit of quality scoring. Has a `source.repo` (and optionally `source.subpath` for mono-repos). |
| `snap` | A snap package. Same scoring contract as `charm`. |

### Inline leaf vs standalone leaf

A leaf product (charm or snap) that appears inside a root's `composed_of` list can be:

| Kind | When to use | How declared |
|------|-------------|--------------|
| **Inline** | Your squad owns it; it belongs to exactly one root product | Embed the full leaf definition in `composed_of` |
| **Standalone** | Shared across multiple roots *or* independently tracked in the portfolio | Own `products/<id>.yaml` file + a `ref: <id>` entry in `composed_of` |

Inline leaves are the common case. Use standalone leaves only when the same charm needs to appear under multiple root products or when the team wants to track it independently on the dashboard.

### `context_refs` — context-only dependencies

`context_refs` lists repos that provide context (e.g., a shared database charm owned by another squad) without being scored as part of this product:

- They appear in the UI for context
- They are **never** included in result computation
- They do not require a `products/` YAML file

### Scoring deduplication by `(repo, subpath)`

`engine/graph.py` returns one `EvaluationUnit` per unique `(repo, subpath)` pair. If the same charm appears under multiple root products, scorers only run once and the result is reused.

> **Planned improvement:** The `compute-metrics.yml` GHA workflow currently runs per root product. True `(repo, subpath)` deduplication at the workflow level (avoiding redundant scorer invocations across root products) is a planned follow-up PR.

---

## GitHub Actions Pipelines

### `compute-metrics.yml` — nightly scorer

**Triggers:** Scheduled nightly, push to `products/**`, `config/**`, `scorers/**`, or `engine/**`, manual dispatch

**Steps:**
1. Check out repo with write access
2. Install Python dependencies
3. Run each scorer against each product → write `computed/{product}.json`
4. Run `engine/assemble.py` → write `public/portfolio.json` and `public/badges/`
5. Update `drift-history.json`
6. Commit artifacts to `main` (`[skip ci]` to prevent re-triggering)

### `deploy-pages.yml` — UI build and deploy

**Triggers:** Push to `main`

**Steps:**
1. Check out repo
2. Install Node dependencies (`npm install`)
3. Build Vite app (`npm run build`) → `ui/dist/`
4. Deploy `ui/dist/` to GitHub Pages

---

## Key Design Decisions

### Pure/IO split in scorers

Every scorer is split into two files:

- `logic.py` — a pure function `compute_metrics(unit: EvaluationUnit, ...) -> dict[str, Any]`. No `os.environ`, no file I/O. Receives all external data as parameters. This makes it fully unit-testable with mocks.
- `scorer.py` — a thin IO wrapper that reads env vars (`GITHUB_TOKEN`, `OPENROUTER_API_KEY`), builds the product graph, resolves leaf `EvaluationUnit` objects, calls `logic.py` for each unit, and prints JSON to stdout.

This split means the core scoring logic can be tested exhaustively without network access.

### AI-assisted scoring

Today, production result-gating metrics are deterministic. We still keep an OpenRouter
integration path available for future informational checks, but current contracts do not
require LLM responses to compute results.

**How it works:**

1. `scorer.py` reads `OPENROUTER_API_KEY` from the environment and passes it to `logic.py`.
2. `logic.py` creates an OpenAI-compatible client pointed at `https://openrouter.ai/api/v1`.
3. A prompt file in `scorers/{dim}/prompts/` defines the system prompt. The product's relevant content (e.g. README text) is passed as the user message.
4. If/when an AI metric is enabled, the LLM returns a structured JSON response parsed into metric values.
5. If `OPENROUTER_API_KEY` is not set, scorers continue with deterministic metrics so the pipeline never fails in environments without the key.

**Prompt files** live at `scorers/{dim}/prompts/{metric_name}.md` for dimensions that enable AI assistance.

```
You are a technical documentation reviewer...
Return ONLY valid JSON: {"<metric_name>": <value>}
```

**Current AI-assisted metrics:**

| Dimension | Metric | What the LLM evaluates |
|-----------|--------|------------------------|
| _None enabled for medal gating_ | _n/a_ | Deterministic metrics are used for all current dimensions |

**Default model:** `anthropic/claude-sonnet-4-5` (configurable via `OPENROUTER_MODEL` env var).

**In the UI:** If AI-assisted metrics are enabled, they display a ✦ AI badge in the
dimension detail Metrics table so users know the value is LLM-derived.

### `dimensions.yaml` as the single config knob

Adding a new quality dimension requires exactly two changes:
1. A new entry in `config/dimensions.yaml` — declares label, description, outputs (with metadata), and result criteria.
2. A new `scorers/<name>/scorer.py` that produces exactly the outputs declared.

No scorer hard-codes thresholds. Thresholds live only in `dimensions.yaml`. This means adjusting what "silver" means for a given metric is a one-line YAML change with no Python changes.

### Static `portfolio.json` (no backend)

The React dashboard has no server-side API. It fetches `portfolio.json` at startup and renders from that. This means:
- Zero infrastructure to maintain
- Instant GitHub Pages deployment
- Data is at most 24 hours stale (nightly scorer)

### Allure `_latest` symlink

Allure reports are published to `https://canonical.github.io/{repo}/_latest/` via a `_latest` symlink that always points to the most recent dated run. We use `_latest` rather than the dated path so the product YAML never needs to be updated when a new report is published.

---

## Result Computation

The `engine/` package computes results in three steps:

1. **Rubric evaluation** (`engine/rubric.py`): Parses criterion strings like `"coverage_pct >= 80"` and evaluates them against the product's computed metrics.
2. **Result assignment** (`engine/medal_engine.py`): Finds the highest tier where all criteria pass.
3. **Drift tracking** (`engine/drift_tracker.py`): Compares current result to previous run; starts/ends remediation windows.
