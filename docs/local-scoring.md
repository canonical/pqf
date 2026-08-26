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

## Measurability gates (`required_metrics_for_scoring`)

Each dimension may declare `required_metrics_for_scoring` in `config/dimensions.yaml`.
This is a list of metric keys that must be present and non-null before PQF will score that
dimension.

- If every required metric is present, the normal medal rubric runs.
- If any required metric is missing or `null`, the dimension becomes
  `insufficient_data` and its medal is forced to `unrated`.
- Use this for **measurability** checks only — for example, a missing latest test result or
  a support sample that was too small to calculate averages.
- Do **not** use it for normal failing values. A measured `false`, `0`, or low percentage
  should still be scored by the rubric.

Current examples:

- `test_verification` requires `latest_build_passing`
- `documentation` requires README/CONTRIBUTING/SECURITY presence (informational metrics like diataxis_coverage_ai and uses_rtd_hosting stay informational)
- `substrate_compat` requires a declared Juju support signal plus substrate CI evidence
- `security_ssdlc` requires branch protection and renovate (dependency update measurability)
- `engagement` requires the sampled response metrics that can otherwise be `null` (informational metrics like repo_views_14d stay informational)

This means a rubric-only change still needs a full recompute when scorer outputs or nullability
semantics change, because regenerated `computed/*.json` data may now shift products from
`scored` to `insufficient_data`.

## Calibration guidance for contributors

When you change a scorer or rubric, keep these interpretation rules intact:

- **Measured-low is not the same as unmeasured.**
  - Example: `latest_build_passing = false` is a real low signal and should score low.
  - Example: `latest_build_passing = null` because no trustworthy source exists should force `unrated`, not bronze.
- **Support only sanctioned structural variants.** Expand detector logic for a real allowed variant (for example matrix vs non-matrix workflow encoding), not for every team-specific layout or naming habit in the fleet.
- **Keep gates conservative.** If a metric is not yet measurable with high confidence across the portfolio, keep it informational instead of letting it gate results.
- **Use PQF to drive alignment.** If a repository departs from the intended standard without an accepted reason, prefer leaving the detector prescriptive and treating the repo as needing alignment work.

A good rule of thumb: if explaining a metric now takes a paragraph of exceptions, the logic has probably become too complex and should be simplified before it grows further.

---

## Documentation scoring without LLM

`score-no-llm` and `score` currently produce different documentation outputs depending on LLM availability. The
documentation scorer emits:

- `readme_present` — Deterministic
- `contributing_present` — Deterministic
- `has_security` — Deterministic
- `documentation_workflows_passing` — Deterministic
- `diataxis_coverage_ai` — AI-assisted via OpenRouter (informational; requires `OPENROUTER_API_KEY`)
- `uses_rtd_hosting` — Deterministic (informational)
- `release_notes_process_implemented` — Deterministic

---

## SSDLC scoring

The security_ssdlc scorer is fully deterministic and emits:

- `renovate_enabled` — Detects Renovate configuration files
- `branch_protection_required_checks` — Requires status checks in default branch protection
- `signed_commits_required` — Requires GPG/SSH signatures in default branch protection
- `canonical_repo_automation_registered` — Checks `canonical/canonical-repo-automation` registration
- `sast_workflow_present` — Detects CodeQL or equivalent SAST workflows
- `cve_tracking_process_present` — Detects CVE tracking documentation or process markers

---

## Environment variable reference

| Variable | Required | Source | Notes |
|----------|----------|--------|-------|
| `GITHUB_TOKEN` | Yes | Auto: `gh auth token` | All scorers use this for GitHub API calls |
| `OPENROUTER_API_KEY` | Conditional | Manual export | Required for `documentation` scorer's AI-assisted diataxis_coverage_ai metric; deterministic scoring works without it |
| `OPENROUTER_MODEL` | No | Optional | Override the OpenRouter model (default: `anthropic/claude-sonnet-4.5`) |
| `LLM_MODEL` | No | Optional | Override model for either backend |
