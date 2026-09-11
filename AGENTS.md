# AGENTS.md — PQF contributing guide for AI agents

## What this repo is

PQF (Product Quality Framework) tracks quality compliance across Canonical Platform Engineering's
tracked products via medal grades (bronze / silver / gold). It has two main parts:

1. **Python engine + scorers** (`engine/`, `scorers/`) — pure-Python result computation pipeline
2. **React dashboard** (`ui/`) — Canonical-branded SPA that reads `public/framework-versions.json`
   and the selected version's `public/versions/<version>/portfolio.json`

Everything is **framework-versioned**: `framework/versions/<version>/{framework,dimensions}.yaml`
is a full, self-contained snapshot of the scoring contract. V0 is **active** (today's official
view, scored nightly); V1 is **upcoming** (previewed weekly and on demand); archived versions are
frozen and never rescored. GitHub Actions runs the scorers per version, uploads the generated
artifacts, and publishes them through the GitHub Pages deployment workflow. The deploy step keeps
archived version directories intact, mirrors the active version at the root compatibility paths
(`public/portfolio.json` and `public/badges/`), and preserves the pre-versioning snapshot at
`/legacy/`.

**Full architecture:** [docs/architecture.md](docs/architecture.md)

---

## Key constraints

### Python engine

- **Pure/IO split is non-negotiable.** Every `logic.py` receives all external data as parameters
  (no `os.environ`, no file reads) and never branches on the framework version. `scorers/run.py`
  reads env vars, resolves the contract, and dispatches; `scorers/<name>/scorer.py` is a thin
  wrapper calling `scorers.run.main(fixed_dimension=...)`.
- **Framework snapshots are the scoring contract.** Adding a dimension = add an entry to a version's
  `framework/versions/<version>/dimensions.yaml` + bind implementation revisions in
  `scorers/registry.py` + create `scorers/<name>/`. Scorer outputs must match exactly what the
  contract declares. There is no unversioned `config/dimensions.yaml`.
- **Never edit an archived version to change scoring.** Archived measurements are frozen and never
  recomputed; only reviewed payload-format migrations that preserve measurements and scoring
  identity are allowed. Prefer landing changes in the **upcoming** version — changing the **active**
  version alters today's official compliance view.
- **Metric ID vs implementation revision.** The metric key is the stable user-facing concept; the
  `implementation:` ID selects an immutable measurement revision. Changing how a metric is measured
  = publish a new revision and point a contract at it, never edit a revision in place.
- `FRAMEWORK_VERSION` is always explicit in local commands — nothing defaults to a version.
- `framework-versions.json` is authoritative for lifecycle/display metadata. The contract digest
  covers scoring semantics only; it excludes framework, dimension, and output display metadata.
- Tests mock all HTTP with `responses` (`@responses.activate`); mock LLM clients with `pytest-mock`.
- `computed/versions/` files are GHA-written. Never hand-edit or commit them.
- `public/versions/<version>/portfolio.json` and `public/framework-versions.json` are GHA-written.
  Never hand-edit them — regenerate with `engine/assemble.py` / `engine/version_index.py`.

### React UI

- All UI components use `@canonical/react-components` (Vanilla Framework wrappers). No Tailwind,
  no shadcn, no custom CSS frameworks.
- `public/framework-versions.json` is loaded first and is the sole authority for lifecycle and
  display metadata; the portfolio's embedded `framework` block is provenance only. Routes are
  version-scoped (`#/<version>/...`). Never import Python engine code from JS/TS.
- TypeScript strict mode; no `any` except in test mocks.
- Vitest + React Testing Library for unit tests (co-located `.test.tsx`); Playwright for E2E.
- Vite base path is `./` (relative) for GH Pages compatibility.

#### Result grades & colours

Result values and their exact hex colours for the React UI (`ui/src/components/MedalBadge.tsx`):
- **gold**: `#C7962F`
- **silver**: `#8F8F8F`
- **bronze**: `#9E622A`
- **unrated** / **below_minimum** / **insufficient_data** / **not_applicable**: `#666`

Result scoring logic: "at or above target" means `MEDAL_ORDER[current] >= MEDAL_ORDER[target]` (comparison, not equality).

There are **no remediation deadlines and no drift clocks**. The UI shows a compliance summary
(at/above target, below target, insufficient data), not a remediation countdown. The Metric
Distribution view keeps numeric gap analysis; per-row binary compliance badges were removed.

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
| `make e2e` | `cd ui && npm run e2e` (Playwright; set `PW_PORT` to override the default dev-server port `5173` if it's already bound, e.g. `PW_PORT=5190 make e2e`) |
| `make validate` | Validate products and every framework version against the schemas |
| `make score PRODUCT=<id> FRAMEWORK_VERSION=<version>` | Run all scorers for one product against one framework version |
| `make score-no-llm PRODUCT=<id> FRAMEWORK_VERSION=<version>` | Same, deterministic (LLM checks skipped) |
| `make _merge PRODUCT=<id> FRAMEWORK_VERSION=<version>` | `.pqf-score/<version>/<id>/` → `computed/versions/<version>/<id>.json` |
| `make _assemble FRAMEWORK_VERSION=<version>` | → `public/versions/<version>/portfolio.json` |
| `make _version-index` | → `public/framework-versions.json` |

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes (scorers) | GitHub PAT for API calls in scorers |
| `OPENROUTER_API_KEY` | Yes (documentation scorer) | OpenRouter API key |
| `OPENROUTER_MODEL` | No | AI model (default: `anthropic/claude-sonnet-4.5`) |

---

## Current dimensions and key metrics

Dimensions are declared **per framework version** — always read the contract you are changing
(`framework/versions/<version>/dimensions.yaml`) rather than trusting a summary. Current state:

**V0 (active)** — four dimensions:

| Dimension | Result criteria |
|-----------|-----------------|
| `test_verification` | Bronze: `latest_build_passing`. Gold: + `uses_jubilant`. (No silver tier — intentional.) |
| `documentation` | Bronze: `readme_present`. Silver: + `contributing_present`. Gold: + `has_security`. |
| `security_ssdlc` | Bronze: `renovate_enabled`. Silver: + `branch_protection_required_checks`. Gold: + `signed_commits_required`. |
| `engagement` | Bronze: `ownership_signal`. Silver: + `response_coverage_rate >= 80`. Gold: + `response_coverage_rate >= 90`. |

**V1 (upcoming)** — adds `substrate_compat` and promotes further signals:

| Dimension | Result criteria |
|-----------|-----------------|
| `test_verification` | Bronze: `latest_build_passing`. Silver: + `integration_test_evidence_present`. Gold: + `uses_jubilant`. |
| `documentation` | Bronze: `readme_present`. Silver: + `contributing_present`. Gold: + `has_security` + `release_notes_process_implemented`. |
| `substrate_compat` | Bronze: `supports_juju_3`. Silver: + `substrate_test_evidence_present`. Gold: `supports_juju_4` + `substrate_test_evidence_present`. |
| `security_ssdlc` | Bronze: `renovate_enabled`. Silver: + `branch_protection_required_checks`. Gold: + `signed_commits_required` + `sast_workflow_present`. |
| `engagement` | Bronze: `ownership_signal`. Silver: + coverage ≥ 80, triage ≤ 3d, PR review ≤ 5d. Gold: + coverage ≥ 90, triage ≤ 2d, PR review ≤ 3d. |

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

# Score one product for one framework version (requires GITHUB_TOKEN + OPENROUTER_API_KEY)
make score PRODUCT=matrix FRAMEWORK_VERSION=v0

# Deterministic variant (no LLM key needed)
make score-no-llm PRODUCT=matrix FRAMEWORK_VERSION=v1
```

---

## Repo layout

```
products/                   # One YAML per product (manually maintained, PR-reviewed)
framework/versions/<version>/ # framework.yaml + dimensions.yaml — a full contract snapshot
config/schemas/             # JSON schemas for products and framework contracts
computed/versions/<version>/  # GHA-written raw metrics per product (never hand-edited)
engine/                     # Pure Python result computation + validation + version index
scorers/                    # registry.py + run.py + one logic.py per dimension (+ tests)
public/versions/<version>/  # GHA-generated portfolio.json per framework version
public/framework-versions.json # GHA-generated version index (lifecycle authority)
public/badges/              # GHA-generated badges
public/legacy/              # gh-pages-only frozen pre-versioning snapshot, served at /legacy/, not linked in the new UI
ui/                         # React 19 + Vite dashboard
.github/workflows/          # compute-metrics.yml, deploy-legacy.yml, preview, ci
docs/                       # Architecture, how-to guides, view documentation
docs/superpowers/           # Design specs and implementation plans (AI agent artifacts)
Makefile                    # Single source of truth for all dev commands
```

---

## GitHub Actions

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `compute-metrics.yml` | Nightly (active version), weekly (upcoming version), relevant push to `main`, manual (`framework_version` input) | Runs affected scorers, carries forward unchanged artifacts, builds `ui/`, and deploys the complete site. UI-only pushes skip scoring. Archived versions are never selected. |
| `deploy-legacy.yml` | Manual | Publishes the frozen pre-versioning snapshot under `/legacy/` |
| `ci.yml` | Push / PR | Validate, lint, tests, semantic change report, security audit |

---

## Further reading

- [docs/architecture.md](docs/architecture.md) — full data flow and design decisions
- [docs/adding-a-product.md](docs/adding-a-product.md) — product onboarding
- [docs/adding-a-metric.md](docs/adding-a-metric.md) — adding a metric to an existing dimension (worked example)
- [docs/adding-a-dimension.md](docs/adding-a-dimension.md) — creating a brand-new quality dimension
