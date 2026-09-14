# Versioned Scoring Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain PQF's version-aware product sets, scoring pipeline, safe cross-version measurement reuse, and failure semantics consistently across user-facing and contributor documentation.

**Architecture:** `docs/architecture.md` remains the canonical technical source. The README, documentation index, and dashboard About page provide concise user-facing concepts and link inward; task-oriented contributor guides describe only the versioning implications relevant to their workflows. Existing `portfolio.json` and `Portfolio` compatibility identifiers remain unchanged while explanatory prose uses “product set.”

**Tech Stack:** Markdown, React 19, TypeScript, React Testing Library, Vitest, existing PQF validation and Makefile targets.

## Global Constraints

- Explanatory and user-facing content uses **product set**, not **portfolio**, as the conceptual term.
- Existing compatibility identifiers such as `portfolio.json`, `Portfolio`, command-line arguments, and generated artifact paths remain unchanged.
- `docs/architecture.md` is the canonical technical explanation; other pages link to it instead of duplicating implementation details.
- Current lifecycle IDs are read from metadata; documentation must not claim that a specific version ID is permanently active or upcoming.
- Cache reuse requires exact equality of evaluation-unit identity, scorer context, runner identity, and the digest of every registered runner source.
- Version-specific output selection and criteria are applied after cached runner lookup.
- Required evidence acquisition fails scoring after authenticated and anonymous attempts are exhausted; it never becomes false, zero, or empty measured evidence.
- Historical specifications and implementation plans remain unchanged.
- Generated files under `computed/versions/`, `public/versions/`, `public/framework-versions.json`, and `public/badges/` are never hand-edited.

---

### Task 1: Dashboard About Page

**Files:**
- Modify: `ui/src/views/About.tsx`
- Modify: `ui/src/views/__tests__/About.test.tsx`

**Interfaces:**
- Consumes: `useFrameworkVersion()` lifecycle metadata and `usePortfolio()` selected-version data.
- Produces: user-facing explanations of framework lifecycle, version-specific product sets, scoring stages, safe measurement reuse, and result semantics.

- [ ] **Step 1: Add failing About-page tests**

Add the framework-version hook import to the existing mock and replace the mock with a selected
active version plus active/upcoming/archived entries:

```tsx
vi.mock('../../providers/FrameworkVersionProvider', () => ({
  useFrameworkVersion: () => ({
    current: {
      id: 'v0',
      sequence: 0,
      label: 'PQF V0',
      status: 'active',
      description: '',
      portfolio_url: '',
      generated_at: '',
      contract_digest: 'digest-v0',
    },
    versions: [
      { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active' },
      { id: 'v1', sequence: 1, label: 'PQF V1', status: 'upcoming' },
      { id: 'legacy', sequence: -1, label: 'Legacy', status: 'archived' },
    ],
  }),
}))
```

Add focused assertions:

```tsx
it('explains framework lifecycle and version-specific product sets', () => {
  wrap()
  expect(screen.getByRole('heading', { name: /framework versions/i })).toBeInTheDocument()
  expect(screen.getByText(/official current view/i)).toBeInTheDocument()
  expect(screen.getByText(/readiness.*next scoring contract/i)).toBeInTheDocument()
  expect(screen.getByText(/frozen historical/i)).toBeInTheDocument()
  expect(screen.getByText(/product set/i)).toBeInTheDocument()
})

it('explains measurement, scoring, and unavailable evidence', () => {
  wrap()
  expect(screen.getByRole('heading', { name: /how scoring works/i })).toBeInTheDocument()
  expect(screen.getByText(/same measurement.*safely reused/i)).toBeInTheDocument()
  expect(screen.getByText(/version.*criteria.*target/i)).toBeInTheDocument()
  expect(screen.getByText(/required evidence.*cannot be acquired.*scoring fails/i)).toBeInTheDocument()
})

it('links to the current architecture documentation', () => {
  wrap()
  expect(screen.getByRole('link', { name: /scoring architecture on github/i })).toHaveAttribute(
    'href',
    'https://github.com/canonical/pqf/blob/main/docs/architecture.md',
  )
})
```

- [ ] **Step 2: Run the focused tests and observe failure**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/About.test.tsx
```

Expected: FAIL because the lifecycle/scoring sections and architecture link do not exist.

- [ ] **Step 3: Add concise user-facing sections**

In `About.tsx`, obtain the selected lifecycle metadata:

```tsx
import { useFrameworkVersion } from '../providers/FrameworkVersionProvider'

const { current } = useFrameworkVersion()
```

Add a **Framework versions** section that explains:

- active: official current compliance view;
- upcoming: readiness view for the next scoring contract and product set;
- archived: frozen historical evidence;
- each version can select different products, components, targets, metrics, and criteria;
- the selector shows `current.label` without hard-coding a version ID.

Add a **How scoring works** section with a short ordered list:

```tsx
<ol className="p-list--divided">
  <li className="p-list__item">Select a framework version and its product set.</li>
  <li className="p-list__item">Measure applicable product components.</li>
  <li className="p-list__item">Apply that version's criteria and targets.</li>
  <li className="p-list__item">Aggregate component results into each tracked product.</li>
</ol>
```

State that the same measurement may be safely reused when versions ask the identical question of
the identical product, but each version always applies its own outputs, criteria, and target.
State that required evidence acquisition failure stops scoring rather than producing a low result.

Replace the old design-spec link with:

```tsx
<a
  href="https://github.com/canonical/pqf/blob/main/docs/architecture.md"
  target="_blank"
  rel="noreferrer"
>
  Scoring architecture on GitHub ↗
</a>
```

- [ ] **Step 4: Run the focused tests**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/About.test.tsx
```

Expected: all About tests pass.

- [ ] **Step 5: Commit**

```bash
git add ui/src/views/About.tsx ui/src/views/__tests__/About.test.tsx
git commit -m "docs(ui): explain versioned scoring"
```

### Task 2: Canonical Architecture Explanation

**Files:**
- Modify: `docs/architecture.md`
- Modify: `README.md`
- Modify: `docs/README.md`

**Interfaces:**
- Consumes: current `engine/workflow_matrix.py`, `scorers/batch.py`, `scorers/registry.py`, and `.github/workflows/compute-metrics.yml` behavior.
- Produces: the canonical scoring explanation and concise entry-point summaries that link to it.

- [ ] **Step 1: Verify current implementation terms before editing**

Run:

```bash
rg -n "RunnerCache|framework_versions|raise_for_required_github_evidence|portfolio.json" \
  scorers engine .github/workflows/compute-metrics.yml
```

Expected: matches identify the current cache, grouped matrix, fail-closed helper, and compatibility
artifact paths that the documentation must describe accurately.

- [ ] **Step 2: Add the canonical scoring data flow**

In `docs/architecture.md`, add a **How versioned scoring works** subsection with these stages:

1. select live framework versions from lifecycle, changes, cadence, and bootstrap debt;
2. resolve each version's product set, component boundaries, composition edges, and targets;
3. group all selected versions for one product into one workflow job;
4. resolve leaf `EvaluationUnit` objects and execute contract-selected runner implementations;
5. reuse raw runner output only under the complete cache identity;
6. filter outputs and apply each version's required metrics and medal criteria independently;
7. merge and assemble versioned artifacts.

Include this cache identity table:

| Cache key input | Why it is required |
|-----------------|--------------------|
| Complete `EvaluationUnit` | Prevents reuse across different products, repositories, subpaths, URLs, types, or targets |
| `ScorerContext` | Prevents reuse across different credentials or model configuration |
| Runner key | Prevents reuse across dimensions or implementations backed by another runner |
| Complete runner-source digest | Invalidates reuse when logic, shared helpers, prompts, or other registered source dependencies change |

State explicitly:

> The cache stores only raw runner output. Each framework version still selects its own output
> implementation IDs, required metrics, criteria, target, and aggregation behavior after lookup.

- [ ] **Step 3: Document required-evidence failure semantics**

Add a **Measurement failures** subsection that distinguishes:

| Outcome | Meaning |
|---------|---------|
| `false`, `0`, low number | Evidence was acquired and measured low |
| `null` | A supported metric is genuinely unmeasurable |
| `below_minimum` | Required evidence was measured but baseline criteria failed |
| `insufficient_data` | A required metric is unavailable |
| Acquisition exception | GitHub evidence could not be fetched reliably; the scoring job fails and publishes nothing |

Describe authenticated-to-anonymous retry for public GitHub evidence and the explicit valid absence
cases. Do not document tokens, response bodies, or operational secrets.

- [ ] **Step 4: Update entry-point summaries**

In `README.md`:

- replace conceptual uses of “portfolio” with “product set”;
- add a short **How versions affect results** paragraph;
- link to `docs/architecture.md#how-versioned-scoring-works`;
- explain that active/upcoming/archived lifecycle metadata, not fixed IDs, controls behavior.

In `docs/README.md`:

- add **Scoring contract**, **Measurement**, and **Product set** vocabulary entries;
- describe `portfolio.json` only as the generated artifact filename;
- link Architecture as the canonical versioned-scoring explanation.

- [ ] **Step 5: Check terminology and links**

Run:

```bash
rg -n '\bportfolio\b' README.md docs/README.md docs/architecture.md
rg -n 'V0 is active|V1 is upcoming|currently active version is v[0-9]+' \
  README.md docs/README.md docs/architecture.md
```

Expected:

- `portfolio` appears only in concrete identifiers such as `portfolio.json` or explicit
  compatibility explanations;
- no current lifecycle role is permanently assigned to a version ID.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/README.md docs/architecture.md
git commit -m "docs: explain versioned scoring architecture"
```

### Task 3: Contributor and Agent Guidance

**Files:**
- Modify: `docs/local-scoring.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/adding-a-product.md`
- Modify: `docs/adding-a-metric.md`
- Modify: `docs/adding-a-dimension.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: the canonical architecture terminology and invariants from Task 2.
- Produces: task-specific instructions for maintainers, contributors, product owners, and agents.

- [ ] **Step 1: Update local scoring and contribution guidance**

In `docs/local-scoring.md`:

- explain that local commands intentionally score one explicit framework version;
- contrast that with production grouping selected versions for a product in one process;
- explain that grouped production execution is an optimization, not shared criteria;
- preserve concrete `portfolio.json` paths as compatibility artifact names;
- replace other conceptual “portfolio” wording with “product set.”

In `CONTRIBUTING.md`:

- link to the canonical architecture section;
- add a review checklist covering selected version, product-set boundary, target resolution,
  immutable implementation revision, registered runner sources, and measured-low versus acquisition
  failure;
- remove stale hard-coded test counts.

- [ ] **Step 2: Update product onboarding**

In `docs/adding-a-product.md`:

- remove statements that permanently assign lifecycle roles to V0 or V1;
- instruct contributors to inspect lifecycle metadata;
- explain active onboarding as an immediate official-view change and upcoming onboarding as
  readiness work;
- use “product set” for conceptual membership;
- retain exact field names `introduced_in`, `retired_in`, `targets`, `composed_of`, and
  `context_refs`.

- [ ] **Step 3: Update metric and dimension authoring**

In `docs/adding-a-metric.md`, state:

- a changed detector requires a new immutable implementation ID;
- versions may select different implementation revisions;
- runner reuse is safe only when the complete cache identity matches;
- shared helpers and prompts used by a runner must be registered in `RUNNER_SOURCE_FILES`.

In `docs/adding-a-dimension.md`, state:

- `logic.py` remains pure with external data passed as parameters;
- required external evidence failures raise and fail the job;
- `false`, zero, and empty collections are valid only after successful acquisition;
- every source dependency that can change runner output belongs in its fingerprint source tuple.

- [ ] **Step 4: Update `AGENTS.md` guardrails**

Add concise rules under the Python-engine and calibration sections:

```markdown
- Production groups selected framework versions by product, but a cached runner result is reusable
  only when the complete evaluation unit, scorer context, runner key, and every registered runner
  source fingerprint match. Contracts still filter outputs and evaluate criteria per version.
- Required external evidence acquisition fails the scoring job after supported retries; never turn
  API/auth/rate-limit/server failures into `false`, `0`, or empty evidence.
- In explanatory prose, call version membership the **product set**. Keep `portfolio.json` and
  existing `Portfolio` identifiers only as compatibility implementation names.
```

- [ ] **Step 5: Check current documentation for stale wording**

Run:

```bash
rg -n '\bportfolio\b|V0 is active|V1 is upcoming|110 tests' \
  AGENTS.md CONTRIBUTING.md docs/local-scoring.md docs/adding-a-product.md \
  docs/adding-a-metric.md docs/adding-a-dimension.md
```

Expected: conceptual language uses “product set”; concrete compatibility artifact names remain;
permanent lifecycle assignments and stale test counts are absent.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md CONTRIBUTING.md docs/local-scoring.md docs/adding-a-product.md \
  docs/adding-a-metric.md docs/adding-a-dimension.md
git commit -m "docs: update version-aware contributor guidance"
```

### Task 4: Cross-Documentation Validation

**Files:**
- Verify: all files changed in Tasks 1–3.

**Interfaces:**
- Consumes: completed user-facing and contributor documentation.
- Produces: a consistent, tested documentation set ready for PR review.

- [ ] **Step 1: Run About-page tests**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/About.test.tsx
```

Expected: all About-page tests pass.

- [ ] **Step 2: Run UI tests**

Run:

```bash
make test-ui
```

Expected: all Vitest tests pass.

- [ ] **Step 3: Validate contracts and examples**

Run:

```bash
make validate
```

Expected: `All files valid.`

- [ ] **Step 4: Run style checks**

Run:

```bash
make lint
make format-check
```

Expected: both commands exit 0.

- [ ] **Step 5: Run final terminology audit**

Run:

```bash
rg -n '\bportfolio\b' \
  README.md AGENTS.md CONTRIBUTING.md docs/README.md docs/architecture.md \
  docs/local-scoring.md docs/adding-a-product.md docs/adding-a-metric.md \
  docs/adding-a-dimension.md ui/src/views/About.tsx
```

Review every match. Accept only:

- `portfolio.json` paths;
- existing `Portfolio` code identifiers;
- explicit compatibility notes explaining those names.

- [ ] **Step 6: Review changed links**

Run:

```bash
rg -n 'docs/architecture.md|github.com/canonical/pqf/blob/main/docs/' \
  README.md AGENTS.md CONTRIBUTING.md docs ui/src/views/About.tsx
```

Expected: local Markdown links resolve within the repository and About-page GitHub links use the
canonical `canonical/pqf` repository.

- [ ] **Step 7: Commit final consistency fixes if needed**

If validation required edits:

```bash
git add README.md AGENTS.md CONTRIBUTING.md docs ui/src/views/About.tsx \
  ui/src/views/__tests__/About.test.tsx
git commit -m "docs: align versioned scoring terminology"
```

If no edits were required, do not create an empty commit.

