# Versioned Scoring Documentation Design

## Purpose

PQF's framework-version model now affects how users interpret results and how contributors change
products, metrics, criteria, scorers, and automation. The documentation should explain that model
consistently across every relevant entry point rather than treating versioning as an isolated
architecture detail.

This update will document:

- how active, upcoming, and archived framework versions differ;
- why the same product can have different results in different versions;
- how product, component, composition, target, metric, and criterion changes are version-scoped;
- how production scoring groups selected versions by product;
- when identical measurements may be reused safely across versions;
- how acquisition failures differ from measured-low results; and
- how contributors preview and validate version-aware changes locally.

## Terminology

Explanatory and user-facing content will use **product set** for the products included in a
framework version. It will not use **portfolio** as the conceptual term.

Existing compatibility identifiers remain unchanged:

- `public/versions/<version>/portfolio.json`
- Python and TypeScript types or functions whose established names include `Portfolio`
- existing command-line arguments and generated artifact paths

Documentation may mention those names when describing concrete implementation artifacts, but it
must distinguish the artifact filename from the user-facing concept of a product set.

Other preferred terms are:

| Term | Meaning |
|------|---------|
| Framework version | A complete scoring-contract snapshot plus lifecycle metadata |
| Scoring contract | The dimensions, outputs, implementation revisions, required metrics, and medal criteria selected by a framework version |
| Measurement | Raw evidence returned by a scorer implementation |
| Result | The evaluated outcome for a dimension or product |
| Target | The version-resolved result a product is expected to meet |
| Product set | The products and components included in a selected framework version |

Documentation should avoid hard-coding statements such as "V0 is active" or "V1 is upcoming"
unless the text is explicitly describing a historical example. Current lifecycle state must be
read from `public/framework-versions.json` or `framework/versions/*/framework.yaml`.

## Information Architecture

### Canonical technical explanation

`docs/architecture.md` will be the canonical description of version-aware scoring. It will cover:

1. Framework lifecycle and complete contract snapshots.
2. Version-scoped product sets, component membership, composition edges, and targets.
3. Measurement and result data flow.
4. Production job grouping: one job per product, containing all selected framework versions for
   that product.
5. Safe cross-version reuse:
   - the complete `EvaluationUnit` identity must match;
   - the immutable scorer context must match;
   - the runner identity must match; and
   - the digest of every registered runner source must match.
6. Version-specific contract filtering after cache lookup. Reusing a runner result does not reuse a
   version's criteria or bypass its selected output implementations.
7. Required evidence fails closed after authenticated and anonymous acquisition attempts are
   exhausted. API failure must not become `false`, zero, or empty measured evidence.
8. Generated artifact routing and the retained `portfolio.json` compatibility filename.

Other documents will link to this explanation instead of duplicating its implementation details.

### User-facing entry points

`README.md`, `docs/README.md`, and `ui/src/views/About.tsx` will provide concise explanations of:

- active as the official current view;
- upcoming as the readiness/planning view for the next contract and product set;
- archived as frozen historical evidence;
- why a product can differ across versions;
- how product results are evaluated from dimension results and version-specific targets; and
- the difference between below minimum and insufficient data.

The About page may state that PQF safely reuses an identical measurement when two versions ask the
same question of the same product. It will not expose cache-key implementation details. It will
link to current canonical documentation rather than an old design artifact.

### Task-oriented contributor guides

The following documents will receive scoped updates:

- `docs/local-scoring.md`
  - explicit version selection;
  - versioned raw, merged, and assembled artifacts;
  - local scoring is per requested version, while production may group versions safely;
  - what must be regenerated after contract, output, implementation, or product-set changes.
- `CONTRIBUTING.md`
  - version-aware change review expectations;
  - active versus upcoming change policy;
  - generated artifact ownership;
  - links to architecture and local scoring.
- `docs/adding-a-product.md`
  - framework lifecycle selection;
  - version-scoped product/component membership and targets;
  - readiness implications of onboarding into an upcoming version.
- `docs/adding-a-metric.md`
  - stable metric IDs versus immutable implementation revisions;
  - how contract selection controls which version adopts a measurement change;
  - complete source registration as part of safe reuse.
- `docs/adding-a-dimension.md`
  - scorer purity and IO boundaries;
  - output contracts and implementation bindings;
  - registering every source dependency used by a runner fingerprint;
  - required-evidence error semantics.
- `AGENTS.md`
  - concise mandatory guardrails for version-specific contracts, immutable implementation
    revisions, safe cache identity, fail-closed required acquisition, product-set terminology, and
    generated artifact ownership.

Historical specifications and implementation plans will not be rewritten. They describe decisions
at a point in time and are not current operating documentation.

## Scoring Explanation

The documentation will describe scoring as four distinct stages:

1. **Select a framework version.** Its lifecycle metadata determines whether it is official,
   previewed, or frozen.
2. **Resolve the product set and targets.** Product, component, and composition boundaries decide
   what exists in that version; sparse target declarations resolve by version sequence.
3. **Measure applicable leaf units.** Contracts select immutable metric implementation revisions.
   Production may reuse a raw runner result only under the complete cache identity described above.
4. **Evaluate and aggregate.** The selected version's criteria evaluate measurements into dimension
   results, and root products aggregate applicable leaf results. A cached measurement never carries
   another version's criteria or target with it.

The explanation will explicitly distinguish:

- `false`, zero, or a low percentage: successfully measured evidence;
- `null`: evidence could not be measured confidently;
- below minimum: measured but failed baseline criteria;
- insufficient data: a required metric is unavailable; and
- acquisition failure: scoring stops rather than publishing success-shaped data.

## Validation

The documentation update will include:

- React Testing Library assertions for the About-page versioning and scoring explanation;
- existing `make validate` coverage for framework and product examples;
- targeted searches for stale conceptual uses of "portfolio" in current user-facing and
  explanatory documentation;
- link/path checks for updated documentation references;
- `make test-ui` for About-page behavior;
- `make lint` and `make format-check`; and
- documentation review against the current framework contracts and workflow implementation.

No generated score or public data artifact will be edited by hand.

## Out of Scope

- Renaming `portfolio.json` or existing internal `Portfolio` identifiers.
- Changing scoring behavior, cache behavior, framework contracts, or workflow execution.
- Rewriting historical design specifications or implementation plans.
- Adding a second canonical scoring guide that would compete with `docs/architecture.md`.

