# Running Scorers Locally

This guide explains how to run the full scoring pipeline on your machine so you
can see the impact of changes to scorers, medal criteria, or product YAML files
in the local dashboard — without waiting for a nightly CI run.

---

## Prerequisites

- `make install` and `make install-ui` done
- `gh` CLI installed and authenticated (`gh auth login`)
- `OPENROUTER_API_KEY` — optional; currently unused by local scoring contracts.

`GITHUB_TOKEN` is auto-populated from `gh auth token` — you don't need to export it manually.

---

## The pipeline

```
products/*.yaml          ← source of truth (product definitions)
       │
       ▼
scorers/*/scorer.py      ← fetch live data from GitHub API (+ optionally LLM)
       │  outputs per-leaf metrics per dimension
       ▼
.pqf-score/<id>/         ← raw scorer output (one JSON file per dimension)
       │
       ▼
engine/merge_computed.py ← assembles dimension files into computed/<id>.json
       │
       ▼
computed/<id>.json       ← structured leaf_metrics envelope
       │
       ▼
engine/assemble.py       ← computes medals + builds portfolio JSON
       │
       ▼
public/portfolio.json    ← the single data source for the UI
       │
       ▼
make dev                 ← Vite dev server reads public/portfolio.json
```

---

## Score all products and refresh the UI

```bash
# Without LLM (recommended for local dev — fast, no API key needed):
make score-all-no-llm

# With LLM key exported (same deterministic outputs today):
make score-all
```

Both targets:
1. Run all 5 scorers for every product in `products/`
2. Merge raw outputs into `computed/<id>.json` for each product
3. Regenerate `public/portfolio.json`

Then start the dashboard:

```bash
make dev   # → http://localhost:5173
```

---

## Score a single product

Useful when iterating on one scorer or product YAML:

```bash
# Score + merge + assemble in three steps:
make score-no-llm PRODUCT=matrix   # runs all scorers, saves to .pqf-score/matrix/
make _merge PRODUCT=matrix         # → computed/matrix.json
make _assemble                     # → public/portfolio.json

# Or with key exported:
make score PRODUCT=matrix
make _merge PRODUCT=matrix
make _assemble
```

The dev server hot-reloads `public/portfolio.json` — no restart needed after `_assemble`.

---

## Iterating on a scorer or medal criteria

1. Edit `scorers/<dim>/logic.py` or `config/dimensions.yaml`
2. Run `make score-no-llm PRODUCT=<any-product>`
3. Run `make _merge PRODUCT=<any-product> && make _assemble`
4. Refresh the dashboard

For medal criteria changes (`config/dimensions.yaml`), step 2 is optional — the criteria
are evaluated by `assemble.py`, so `make _assemble` alone picks them up from the existing
`computed/` files.

---

## Documentation scoring without LLM

`score-no-llm` and `score` currently produce the same documentation outputs. The
documentation scorer is fully deterministic and emits:

- `readme_meets_structure`
- `contributing_meets_structure`
- `has_security`
- `documentation_workflows_passing`
- `diataxis_coverage`
- `tutorial_tested`
- `uses_rtd_hosting`
- `recent_release_notes_present`

---

## Environment variable reference

| Variable | Required | Source | Notes |
|----------|----------|--------|-------|
| `GITHUB_TOKEN` | Yes | Auto: `gh auth token` | All scorers use this for GitHub API calls |
| `OPENROUTER_API_KEY` | No | Manual export | Reserved for future AI-assisted checks |
| `OPENROUTER_MODEL` | No | Optional | Override the OpenRouter model (default: `anthropic/claude-sonnet-4.5`) |
| `LLM_MODEL` | No | Optional | Override model for either backend |
