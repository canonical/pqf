# AGENTS.md — PQF contributing guide for AI agents

## What this repo is

PQF (Product Quality Framework) tracks quality compliance across Canonical Platform Engineering's
tracked products via medal grades (bronze / silver / gold). It has two main parts:

1. **Python engine + scorers** (`engine/`, `scorers/`) — pure-Python medal computation pipeline
2. **React dashboard** (`ui/`) — Canonical-branded SPA that reads `public/portfolio.json`

A nightly GitHub Actions workflow runs the scorers, computes medals, and commits artifacts
(`computed/`, `public/portfolio.json`, `public/badges/`) to `main`. A second workflow builds
the UI and deploys it to GitHub Pages.

**Full architecture:** [docs/architecture.md](docs/architecture.md)

---

## Key constraints

### Python engine

- **Pure/IO split is non-negotiable.** Every `logic.py` receives all external data as parameters
  (no `os.environ`, no file reads). The `scorer.py` wrapper reads env vars and passes them in.
- `config/dimensions.yaml` is the single config knob. Adding a dimension = add entry here +
  create `scorers/<name>/scorer.py`. Scorer outputs must match exactly what dimensions.yaml declares.
- Tests mock all HTTP with `responses` (`@responses.activate`); mock LLM clients with `pytest-mock`.
- `computed/` files are GHA-written. Never hand-edit them.
- `public/portfolio.json` is GHA-written. Never hand-edit it — regenerate with `engine/assemble.py`.

### React UI

- All UI components use `@canonical/react-components` (Vanilla Framework wrappers). No Tailwind,
  no shadcn, no custom CSS frameworks.
- `public/portfolio.json` is the single data source. Never import Python engine code from JS/TS.
- TypeScript strict mode; no `any` except in test mocks.
- Vitest + React Testing Library for unit tests (co-located `.test.tsx`); Playwright for E2E.
- Vite base path is `./` (relative) for GH Pages compatibility.

#### Medal grades & colours

Medal grades and their exact hex colours for the React UI:
- **gold**: `#C7962F`
- **silver**: `#8F8F8F`
- **bronze**: `#9E622A`
- **unrated**: `#666`
- **remediating**: `#E98B06`
- **overdue**: `#C7162B`

Medal scoring logic: "at or above target" means `MEDAL_ORDER[current] >= MEDAL_ORDER[target]` (comparison, not equality).

---

## Metric calibration philosophy

When changing scorers, rubrics, or scoring semantics, preserve these rules:

- **Keep metrics simple and deterministic.** A metric should stay easy to explain in one sentence.
- **Separate measured-low from unmeasurable.** `bronze` means the repo was measured and performed poorly. `unrated` / `insufficient_data` means the signal could not be measured confidently.
- **Support only sanctioned variants.** The allowed variance classes are:
  - monorepo vs non-monorepo,
  - charm vs snap,
  - root/meta product vs leaf aggregation context,
  - equivalent YAML/workflow encodings of the same canonical signal.
- **Do not normalize arbitrary team-specific drift.** If a repository differs from the intended standard for no sanctioned reason, prefer flagging that misalignment over adding detector complexity.
- **Keep gating metrics high-confidence.** Only use `required_metrics_for_scoring` and medal gates for signals we can measure reliably across the fleet.
- **Prefer tightening standards over broadening heuristics.** If a detector keeps needing special cases, treat that as a design smell and revisit the standard before expanding the logic.

This rule set exists to keep PQF useful for cross-product reasoning: as simple as possible, as high-confidence as possible, and aligned with the standards we want teams to follow.

See also [docs/local-scoring.md](docs/local-scoring.md) for local scoring semantics and [docs/metric-calibration-roadmap.md](docs/metric-calibration-roadmap.md) for the next calibration phases.

## Makefile — the single source of truth for dev commands

Always use `make` targets. CI uses the same targets.

| Target | What it runs |
|--------|-------------|
| `make install` | `pip install -e ".[dev]"` |
| `make install-ui` | `cd ui && npm install` |
| `make lint` | `ruff check .` |
| `make format` | `ruff format .` |
| `make format-check` | `ruff format --check .` |
| `make test` | `pytest --tb=short` |
| `make test-ui` | `cd ui && npm test` |
| `make test-all` | `make test` + `make test-ui` |
| `make build` | `cd ui && npm run build` |
| `make dev` | `cd ui && npm run dev` |
| `make score PRODUCT=<id>` | Run all scorers for one product |

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes (scorers) | GitHub PAT for API calls in scorers |
| `OPENROUTER_API_KEY` | Yes (documentation scorer) | OpenRouter API key |
| `OPENROUTER_MODEL` | No | AI model (default: `anthropic/claude-sonnet-4.5`) |

---

## Current dimensions and key metrics

| Dimension | Key outputs | Medal criteria |
|-----------|-------------|---------------|
| `test_verification` | `coverage_pct`, `stability_pct`, `latest_build_passing`, `uses_ops_testing`, `uses_jubilant` | Bronze: coverage ≥ 70, build passing. Silver: coverage ≥ 80, stability ≥ 85. Gold: coverage ≥ 90, stability ≥ 98. |
| `documentation` | `has_readme`, `has_contributing`, `has_security`, `diataxis_coverage` (AI), `style_linter_passing` (AI), `links_passing` | Bronze: readme+contributing+security+links. Silver: diataxis ≥ 4. Gold: style linter + diataxis == 4. |
| `substrate_compat` | `supports_juju_3`, `supports_juju_4`, `supports_ck8s` | Silver: juju3. Gold: juju4 + ck8s. |
| `security_ssdlc` | `dependabot_enabled`, `codeql_enabled`, `branch_protection_required_checks` | Silver: dependabot. Gold: dependabot + codeql. |
| `engagement` | `avg_triage_days`, `avg_pr_review_days`, `response_coverage_rate`, `ownership_signal`, `has_jira_sync`, `repo_views_14d` (informational) | Silver: triage ≤ 3d, PR ≤ 5d, coverage ≥ 80%, ownership. Gold: triage ≤ 2d, PR ≤ 3d, coverage ≥ 90%, ownership. |

---

## Allure report URL pattern

Test coverage comes from Allure reports published to GitHub Pages. The stable URL pattern is:

```
https://canonical.github.io/{repo-name}/_latest
```

Set `allure_report_url` in the product YAML to this URL. The `_latest` symlink always points to the most recent run — no need to update the YAML when new reports are published.

The `test_verification` scorer fetches `{allure_report_url}/widgets/summary.json` to extract pass/fail counts.

---

## Tools

### Required for UI work: playwright-cli

The `playwright-cli` tool (`@playwright/cli`) is purpose-built for AI coding agents. Install it
globally:

```bash
npm install -g @playwright/cli
playwright-cli install chromium
```

Typical verification workflow after implementing a view:
```bash
# Terminal 1
cd ui && npm run dev

# Agent uses playwright-cli:
playwright-cli open
playwright-cli goto http://localhost:5173/
playwright-cli snapshot
playwright-cli screenshot
playwright-cli close
```

---

## Running things locally

```bash
# Python
make install
make test

# UI
make install-ui
make dev          # → http://localhost:5173

# Score one product (requires GITHUB_TOKEN + OPENROUTER_API_KEY)
make score PRODUCT=matrix
```

---

## Repo layout

```
products/           # One YAML per product (manually maintained, PR-reviewed)
config/             # dimensions.yaml — medal rubrics and scorer contracts
computed/           # GHA-written raw metrics per product (never hand-edited)
engine/             # Pure Python medal computation
scorers/            # One scorer per dimension (logic.py + scorer.py + tests)
public/             # GHA-generated: portfolio.json + badges/
ui/                 # React 19 + Vite dashboard
drift-history.json  # GHA-maintained drift start dates
.github/workflows/  # compute-metrics.yml + deploy-pages.yml
docs/               # Architecture, how-to guides, view documentation
docs/superpowers/   # Design specs and implementation plans (AI agent artifacts)
Makefile            # Single source of truth for all dev commands
```

---

## GitHub Actions

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `compute-metrics.yml` | Nightly, push to `products/**` or `config/**`, manual | Runs scorers → engine → badges → commits artifacts |
| `deploy-pages.yml` | Push to `main` | Builds `ui/` → deploys to GitHub Pages |
| `ci.yml` | Push / PR | Lint, tests, security audit |

---

## Further reading

- [docs/architecture.md](docs/architecture.md) — full data flow and design decisions
- [docs/adding-a-product.md](docs/adding-a-product.md) — product onboarding
- [docs/adding-a-metric.md](docs/adding-a-metric.md) — adding a metric to an existing dimension (worked example)
- [docs/adding-a-dimension.md](docs/adding-a-dimension.md) — creating a brand-new quality dimension
