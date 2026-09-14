# PQF Architecture

---

## Data Flow

Every scoring result and generated artifact is scoped to exactly one **framework version**. One
production job for a top-level product may process several selected versions in a single batch;
each version's framework contract, not a mutable shared config file, decides which dimensions,
metrics, criteria, products, and targets apply to that version's results.

```
products/*.yaml          framework/versions/<version>/{framework,dimensions}.yaml
      │                          │
      │           ┌──────────────┘
      ▼           ▼
  engine/graph.py              (builds the version-filtered product graph; extracts inline leaves)
      │
      ▼
  evaluation units             (one per leaf product: repo + optional subpath)
      │
      ▼
  scorers/run.py               (resolves the implementation revisions the version selects,
      │                         via scorers/registry.py; outputs per-leaf metric dict)
      ▼
  computed/versions/<version>/{product}.json
      │                        (leaf_metrics envelope; GHA-written, never hand-edited)
      ▼
  engine/assemble.py           (worst-in-scope aggregation → results; product-set assembly)
      │
      ├─► public/versions/<version>/portfolio.json   (one self-describing artifact per version)
      └─► public/badges/
      │
      ▼
  engine/version_index.py  ──► public/framework-versions.json   (lifecycle/display index)
      │
      ▼
  ui/ (React 19 + Vite)        (loads the index first, then the selected version's portfolio.json)
      │
      ▼
  GitHub Pages
```

### How versioned scoring works

Version-aware scoring separates shared evidence acquisition from the contract-specific decisions
that turn evidence into results:

1. `engine/workflow_matrix.py` selects live framework versions from lifecycle metadata, relevant
   changes, the active/upcoming cadence, and bootstrap debt such as a missing, stale-contract, or
   overdue published `portfolio.json`.
2. For each selected version, `engine/graph.py` resolves that version's product set, component
   boundaries, composition edges, and effective targets.
3. The matrix groups every selected version for one top-level product into one workflow job. The
   job passes the ordered `framework_versions` list to `scorers/batch.py`.
4. The batch runner resolves each version's leaf `EvaluationUnit` objects and executes only the
   runner implementations selected by that version's contract.
5. Within that job, a `RunnerCache` may reuse raw runner output only when the complete cache
   identity below is equal.
6. After raw-output lookup, each contract filters the runner output to its selected outputs, then
   independently applies its required metrics, medal criteria, resolved target, and aggregation
   behavior.
7. The workflow merges per-dimension output into versioned computed envelopes and
   `engine/assemble.py` assembles each selected version's product set as
   `public/versions/<version>/portfolio.json`.

| Cache key input | Why it is required |
|-----------------|--------------------|
| Complete `EvaluationUnit` | Prevents reuse across different products, repositories, subpaths, URLs, types, or targets |
| `ScorerContext` | Prevents reuse across different credentials or model configuration |
| Runner key | Prevents reuse across dimensions or implementations backed by another runner |
| Complete runner-identity digest | Invalidates reuse when logic, shared helpers, prompts, the dispatched registry wrapper, or relevant metric-to-runner bindings change |

The cache stores only raw runner output. Each framework version still selects its own output
implementation IDs, required metrics, criteria, target, and aggregation behavior after lookup.

### Measurement failures

PQF distinguishes acquired evidence that measures low from evidence that could not be measured:

| Outcome | Meaning |
|---------|---------|
| `false`, `0`, low number | Evidence was acquired and measured low |
| `null` | A supported metric is genuinely unmeasurable |
| `below_minimum` | Required evidence was measured but baseline criteria failed |
| `insufficient_data` | A required metric is unavailable |
| Acquisition exception | GitHub evidence could not be fetched reliably; the scoring job fails and publishes nothing |

Required GitHub acquisition fails closed. For public evidence, an authenticated request is retried
anonymously when authentication fails or the authenticated client is rate-limited; if the required
request still fails, `GitHubAcquisitionError` stops the compute job. A response is treated as
absence only where the scorer defines that response as valid evidence of absence—for example, a
`404` for an optional Jira sync file or for the `.github/workflows` directory. Optional signals
that an API cannot expose reliably, such as repository traffic, may explicitly return `null`
instead. These cases do not expose credentials, response bodies, or operational secrets in the
published product set.

---

## Component Responsibilities

| Directory | Owner | Responsibility |
|-----------|-------|---------------|
| `products/` | PE team (PR-reviewed) | One YAML per product — manually maintained source of truth, with version membership boundaries and version-scoped targets |
| `framework/versions/<id>/` | Framework owners (PR-reviewed) | `framework.yaml` (lifecycle/display metadata) + `dimensions.yaml` (complete scoring contract snapshot) |
| `config/schemas/` | Contributors | JSON Schemas used by `make validate` |
| `scorers/{dim}/` | Contributors | `logic.py` (pure, testable) + `scorer.py` (thin wrapper over `scorers/run.py`) |
| `scorers/registry.py` | Contributors | Maps metric implementation revision IDs to the pure functions that produce them |
| `computed/versions/<id>/` | GHA only | `leaf_metrics` envelope keyed by leaf product ID — **never hand-edited** |
| `engine/` | Contributors | Framework discovery/validation, result computation, product-set assembly, version index |
| `public/versions/<id>/` | GHA only | Versioned source-of-truth `portfolio.json` per framework version — **never hand-edited** |
| `public/portfolio.json` | GHA only | Active-version compatibility mirror for legacy consumers; regenerated from the active version's `portfolio.json` |
| `public/badges/` | GHA only | Stable active-only badge contract consumed by external links |
| `public/framework-versions.json` | GHA only | Authoritative lifecycle/display index consumed by the UI |
| `public/legacy/` | gh-pages only | Frozen pre-versioning snapshot published at `/legacy/` and kept outside the versioned artifact model |
| `ui/` | Contributors | React SPA reading `framework-versions.json` + the selected version's `portfolio.json` |
| `.github/workflows/` | Contributors | Compute, deploy, preview, and legacy-snapshot workflows (see below) |

---

## Framework Versions

### Directory layout and lifecycle

```text
framework/
  versions/
    v0/
      framework.yaml      # id, sequence, label, status, description
      dimensions.yaml     # complete scoring contract snapshot
    v1/
      framework.yaml
      dimensions.yaml
```

Each `dimensions.yaml` is a **full snapshot**. It never inherits from another version at runtime,
so a contract can be read and reviewed without traversing an inheritance chain. A new version is
created by copying the active contract into a new directory and editing the copy.

`status` is one of:

| Status | Meaning |
|--------|---------|
| `active` | The single official framework used for current compliance. Recomputed nightly. |
| `upcoming` | The single next framework under preparation. A planning/readiness view, recomputed weekly and on manual dispatch. |
| `archived` | A former active framework. Its published measurements are frozen and its scorers never run again. |

`make validate` enforces the lifecycle invariants: exactly one active version, at most one upcoming
version, unique IDs and sequence numbers, and lifecycle order consistent with sequence order.
Lifecycle behavior always derives from this metadata; no version ID permanently means active or
upcoming.

Activation is a single reviewed source change that marks the old active version `archived` and the
upcoming version `active`.

### Contract digest and archives

`contract_digest` hashes only what determines **how a version scores**: the semantic parts of the
dimensions contract plus the identity fields that scope it (`id` and `sequence`, which resolves
catalog membership boundaries). Lifecycle and display metadata is deliberately excluded:
framework `status`, `label`, and `description`, dimension `label` and `description`, and output
`label`, `description`, `range`, and `ai_assisted`. Activating a version or clarifying UI copy
therefore does not invalidate artifacts that were already published.

Archived versions follow four rules:

1. **Frozen measurements.** No cadence, manual dispatch, or bootstrap path may schedule an archived
   version for scoring, so archived measured values can never change.
2. **Migratable payload format.** A reviewed format migration may transform an archived
   `portfolio.json` artifact so a newer UI schema can read it, provided it preserves the recorded
   metric values, results, product membership, generation time, and scoring-contract identity
   (framework ID and contract digest).
   PR review is the governance gate; the engine does not hard-lock archived files.
3. **No archived rescoring.** Digest validation applies to archived artifacts exactly as to live
   ones. A mismatch means archived scoring rules were changed after the fact — that is an error,
   never a trigger to recompute.
4. **Index authority.** `public/framework-versions.json` is authoritative for lifecycle and display
   metadata. The versioned `public/versions/<id>/portfolio.json` files are the source of truth for
   each framework version, while the root `public/portfolio.json` and `public/badges/` are the
   active-version compatibility surfaces. A `portfolio.json` artifact's embedded `framework` block
   is historical provenance only and must never drive selector labels or version badges.

### Metric identity vs implementation revision

Metric IDs name stable, user-facing concepts. Implementation IDs name concrete measurement logic
revisions:

```yaml
outputs:
  integration_test_evidence_present:
    implementation: "integration-test-evidence-present/v1"
    type: boolean
    label: "Integration test evidence"
```

`scorers/registry.py` binds each implementation ID and output key to a runner wrapper around pure
metric logic. Metric functions never receive a framework version and never branch on version IDs.
A changed detector becomes a **new** implementation revision (`.../v2`), and a contract opts into
it explicitly — which keeps the semantic change visible in review instead of silently changing
every version that references the existing ID. Its fingerprint covers the binding metadata, runner
wrapper, runner logic, scoring-relevant shared helpers, and prompt assets. Implementation revision
IDs are immutable, and unknown IDs are validation errors.

Archived versions do not require their implementations to stay executable, because archived
artifacts are never recomputed. Implementations must remain available while the active or upcoming
contract references them.

### Version-scoped catalog boundaries

Product definitions stay in `products/*.yaml` — they are not duplicated per version. Membership is
expressed with `introduced_in` and optional `retired_in` on top-level products, inline components,
standalone components, and composition edges. Inclusion is start-inclusive and
retirement-exclusive:

```text
introduced_in <= selected version < retired_in
```

Targets are sparse, version-scoped declarations; the target for a selected version is the
declaration with the greatest sequence not exceeding it:

```yaml
targets:
  v0: bronze
  v1: silver
```

See [Adding a product](adding-a-product.md) for the authoring rules and validation errors.

### Local scoring

Local runtime commands take an explicit `FRAMEWORK_VERSION` and never fall back to a default:

```bash
make score-no-llm PRODUCT=matrix FRAMEWORK_VERSION=v0
```

Archived versions are rejected for recomputation. See [Run PQF locally](local-scoring.md).

### `/legacy/`

The final pre-versioning site is deployed once at `/legacy/` by `deploy-legacy.yml`. It keeps its
own unversioned `portfolio.json`, is never recomputed, is not part of
`public/framework-versions.json`, and is **not linked from the new UI**. It exists purely as a
historical and visual regression reference for the previous major iteration.

---

## Product Graph Model

### `product_type` enum

Every node in the product graph has a `product_type`:

| Value | Meaning |
|-------|---------|
| `root` | Top-level tracked product entry. Has no source repo of its own. Composed of one or more leaf products. Its result is the worst across all scored leaves. |
| `charm` | A Juju charm — the primary unit of quality scoring. Has a `source.repo` (and optionally `source.subpath` for mono-repos). |
| `snap` | A snap package. Same scoring contract as `charm`. |

### Inline leaf vs standalone leaf

A leaf product (charm or snap) that appears inside a root's `composed_of` list can be:

| Kind | When to use | How declared |
|------|-------------|--------------|
| **Inline** | Your squad owns it; it belongs to exactly one root product | Embed the full leaf definition in `composed_of` |
| **Standalone** | Shared across multiple roots *or* independently tracked in PQF | Own `products/<id>.yaml` file + a `ref: <id>` entry in `composed_of` |

Inline leaves are the common case. Use standalone leaves only when the same charm needs to appear under multiple root products or when the team wants to track it independently on the dashboard.

### `context_refs` — context-only dependencies

`context_refs` lists repos that provide context (e.g., a shared database charm owned by another squad) without being scored as part of this product:

- They appear in the UI for context
- They are **never** included in result computation
- They do not require a `products/` YAML file

### Scoring deduplication by `(repo, subpath)`

Within one version's product graph, `engine/graph.py` returns one `EvaluationUnit` per unique
`(repo, subpath)` pair. Within one product job, the runner cache can also reuse identical raw
runner output across the selected versions.

`compute-metrics.yml` runs one job per root product, with all selected versions for that product
grouped into the job. True `(repo, subpath)` deduplication across different root-product jobs
remains a planned improvement.

---

## GitHub Actions Pipelines

### `compute-metrics.yml` — versioned scorer

**Triggers:**
- `0 2 * * *` — nightly, every **active** framework version
- `0 3 * * 1` — weekly Monday, every **upcoming** framework version
- `workflow_dispatch` with a `framework_version` input (must be active or upcoming)
- push to `main` and pull requests touching `products/**`, `framework/**`, `config/**`,
  `scorers/**`, `engine/**`, `ui/**`, or the workflow itself

**Steps:**
1. On pull requests, publish a semantic change report classifying framework/catalog changes as
   metadata-only, additive informational, scoring-semantic, or catalog membership/target
2. Build the product-grouped selected-version matrix with `engine/workflow_matrix.py`
3. Run each product job across its ordered selected versions and write each version's outputs →
   `computed/versions/<id>/{product}.json`
4. Merge scorer outputs and run `engine/assemble.py` per version → `public/versions/<id>/portfolio.json`
5. Carry forward archived version directories from the published site, regenerate the active root
   compatibility mirror at `public/portfolio.json`, rebuild `public/badges/`, and run
   `engine/version_index.py` → `public/framework-versions.json`
6. Upload the `public/` artifact, build the UI from it, and deploy the complete site to Pages;
   nothing is committed to `main`

Archived versions are never selected: their measurements are frozen. Whatever the cadence selects
is unioned with a bootstrap set — every live version whose published `portfolio.json` is missing
or was built from a different scoring contract — so the version index can always be rebuilt
completely.
For a UI-only push with current live artifacts, the selected matrix is empty, current versioned
artifacts are carried forward, and the latest UI is deployed without invoking repository scorers.
Keeping production publication in this single workflow also ensures a newer main-branch run cancels
an older pending run while the active run completes. Main-branch runs are serialized so a newer
UI-only commit cannot discard unpublished scoring changes; after the active run publishes, the
newest pending checkout compares itself with the last successfully published `source_revision`.
That range includes scoring changes from failed or superseded runs before it carries artifacts
forward and deploys the latest UI. Immediately before production publication, the workflow also
checks that its source SHA is still the current `main` tip. Older scheduled runs are skipped, and
manual runs from non-main refs can compute but cannot publish to the production root. Main pushes
and main manual runs share the main publication queue. Scheduled runs remain independent
so a pending cadence refresh cannot be evicted; they select their lifecycle cadence plus any live
versions affected since the last successful publication. Manual runs select the requested version
plus those unpublished changes. Under the shared Pages deployment lock, each run refreshes only
the versions it selected and replaces every unselected version with the latest deployed copy before
regenerating the active root mirror, badges, and version index. Concurrent cadence and push runs
therefore cannot overwrite one another's newer version snapshots. If both runs selected the same
version at the same source revision and contract digest, the copy with the later `generated_at`
wins. The matrix also treats the active version's `portfolio.json` as due when it was not generated
on the current UTC date, and the upcoming version's `portfolio.json` as due when it was not
generated in the current ISO week. A later run therefore inherits a cadence refresh if GitHub
replaces a pending scheduled deployment.

### `deploy-legacy.yml` — one-off legacy snapshot

**Triggers:** Manual dispatch with the pre-versioning git ref. Builds that commit's site and
publishes it at `/legacy/`.

### `preview.yml` / `cleanup-preview.yml` — PR previews

Build and tear down per-PR preview deployments.

### `ci.yml` — lint, validation, tests

Runs `make lint`, `make format-check`, `make validate`, `make test`, `make test-ui`, `make e2e`,
and the security audit.

---

## Key Design Decisions

### Pure/IO split in scorers

Every scorer is split into two layers:

- `logic.py` — a pure function `compute_metrics(unit: EvaluationUnit, ...) -> dict[str, Any]`. No `os.environ`, no file I/O. Receives all external data as parameters. This makes it fully unit-testable with mocks.
- `scorers/run.py` — the version-aware IO wrapper. It resolves the framework version, rejects archived versions, builds the version-filtered product graph, resolves leaf `EvaluationUnit` objects, reads env vars (`GITHUB_TOKEN`, `OPENROUTER_API_KEY`), dispatches the implementation revisions the contract selects via `scorers/registry.py`, and prints JSON to stdout. Each `scorers/{dim}/scorer.py` is a thin compatibility wrapper that calls it with a fixed dimension.

This split means the core scoring logic can be tested exhaustively without network access.

### AI-assisted scoring

Today, production result-gating metrics are deterministic. We still keep an OpenRouter
integration path available for future informational checks, but current contracts do not
require LLM responses to compute results.

**How it works:**

1. `scorers/run.py` reads `OPENROUTER_API_KEY` from the environment and passes it to `logic.py`.
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

### Framework snapshots as the scoring contract

There is no repository-wide mutable dimension config. Each framework version owns a complete
`framework/versions/<id>/dimensions.yaml` snapshot, and adding a quality dimension to a version
requires exactly three changes:

1. A new entry in that version's `dimensions.yaml` — label, description, outputs (each selecting a
   metric implementation revision), and result criteria.
2. Metric implementation bindings in `scorers/registry.py`.
3. A `scorers/<name>/logic.py` that produces exactly the outputs those implementations declare.

No scorer hard-codes thresholds. Thresholds live only in the versioned contract, so raising a bar
is a YAML change in one framework version — and by convention that change lands in the upcoming
version rather than the active one.

### Version-addressed `portfolio.json` (no backend)

The React dashboard has no server-side API. It fetches `framework-versions.json`, then the selected
version's `portfolio.json`, and renders from that. Each versioned `portfolio.json` embeds its framework
identity, contract digest, implementation fingerprints, generation timestamp, source revision,
resolved dimension/metric metadata, the version-filtered product graph, resolved targets, results,
and the compliance summary counts. That makes every versioned artifact self-describing, so current
source configuration can never change the interpretation of an older view. The root
`public/portfolio.json` is a compatibility mirror of the active version for older consumers, and
`public/badges/` is the active-only external badge contract. This means:
- Zero infrastructure to maintain
- Instant GitHub Pages deployment
- Active data is at most 24 hours stale; upcoming data is at most a week stale

### Allure `_latest` symlink

Allure reports are published to `https://canonical.github.io/{repo}/_latest/` via a `_latest` symlink that always points to the most recent dated run. We use `_latest` rather than the dated path so the product YAML never needs to be updated when a new report is published.

---

## Result Computation

The `engine/` package computes results in three steps:

1. **Rubric evaluation** (`engine/rubric.py`): Parses criterion strings like `"coverage_pct >= 80"` and evaluates them against the product's computed metrics.
2. **Result assignment** (`engine/medal_engine.py`): Finds the highest tier where all criteria pass.
3. **Compliance summary** (`engine/assemble.py`): Compares each product's result to its
   version-resolved target and counts products meeting target, below target, or lacking sufficient
   data.

There are no remediation deadlines and no drift clocks. A framework version is the unit of change:
raising a bar happens in a new version, and the selected version plus its lifecycle status makes
every result's meaning explicit. The upcoming view is the planning/readiness view; the active view
is the official live compliance view.
