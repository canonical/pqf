# CI: Artifact-Driven Production Deploy for Fresh PQF Data

**Date:** 2026-07-21  
**Status:** Draft  
**Branch:** main

---

## Problem Statement

PQF currently has two separate production concerns:

1. **Fresh metric generation**
   - `compute-metrics.yml` computes scorer outputs, assembles `public/portfolio.json`, and generates badges.
   - on `main`, it then tries to commit those generated artifacts back into the repository.

2. **Production site deployment**
   - `deploy-pages.yml` builds the UI from the checked-out repository state and deploys it to GitHub Pages.

This breaks down in two ways:

- **Verified-signature branch protection** now rejects the bot commit in `commit-artifacts`, so fresh generated data never lands on `main`.
- **Production deploy currently depends on committed generated files**, so the live site can stay stale even when compute succeeded.

The goal is to preserve the existing one-merge flow:

- PR previews continue showing fresh computed data.
- Merging a product/config/scorer/engine PR updates production automatically.
- Production deployment no longer depends on committing generated artifacts to `main`.

---

## Decisions Made

| Question | Decision |
|----------|----------|
| Source of production truth for fresh data | Workflow artifacts produced by `run-engine` |
| PR preview behavior | Keep current artifact-driven preview flow |
| Production deploy owner for data changes | `compute-metrics.yml` |
| Role of `commit-artifacts` | Remove from critical path for live-site freshness |
| Role of `deploy-pages.yml` | Restrict to UI-only deploys |
| Expected merge UX | Single merge should still update production |

---

## Approaches Considered

### 1. Use Canonical signed PR automation for generated artifacts

- Replace direct `git commit && git push` with `canonical/create-pull-request@main`.
- Generated files would land through a second automation PR.

**Pros**
- Aligns with a confirmed Canonical signed-commit pattern.
- Satisfies verified-signature rules.

**Cons**
- Breaks the current one-merge production flow.
- Production freshness would depend on a second PR merge or auto-merge path.
- Adds more workflow indirection than needed for the immediate problem.

### 2. Deploy production directly from workflow artifacts (**recommended**)

- Keep `run-engine` as the source of fresh generated data.
- Build and publish the production site directly from downloaded workflow artifacts.

**Pros**
- Preserves the current one-merge UX.
- Avoids verified-signature pressure on generated bot commits.
- Matches the already-working PR preview model.
- Keeps the freshness boundary explicit: compute output feeds deploy directly.

**Cons**
- Repository `computed/` and `public/portfolio.json` stop being the authoritative deployment source.
- Requires careful trigger ownership to avoid stale deploys from `deploy-pages.yml`.

### 3. Find a direct signed-push-to-main workflow

- Continue same-branch artifact commits, but add a signed push mechanism.

**Pros**
- Minimal conceptual change if available.

**Cons**
- No high-confidence Canonical reusable same-branch signed-push solution was confirmed.
- Keeps deployment coupled to repository-generated artifacts.
- Still makes live freshness depend on a secondary commit path.

---

## Recommended Design

### 1. Preserve the current PR preview architecture

The PR preview path remains unchanged in principle:

- PR changes trigger `compute-metrics.yml`
- scorer outputs are generated
- `run-engine` assembles fresh `public/portfolio.json` and badges
- preview build downloads `engine-artifacts`
- preview deploy publishes the site for the PR

This is already the correct model because preview freshness comes from the workflow outputs, not from committed generated files.

### 2. Make production deploy artifact-driven for data-affecting events

For these events:

- `push` to `main` that changes:
  - `products/**`
  - `config/**`
  - `scorers/**`
  - `engine/**`
- nightly `schedule`
- `workflow_dispatch`

`compute-metrics.yml` should own the full production data pipeline:

1. compute product metrics
2. assemble fresh portfolio + badges in `run-engine`
3. download `engine-artifacts`
4. build the UI against that fresh generated `public/`
5. deploy the built site to production using the existing `gh-pages` publishing path

This makes production freshness depend on the exact compute results from the same workflow run.

### 3. Remove `commit-artifacts` from the live-site path

`commit-artifacts` is the failing step today because verified-signature rules reject the generated commit.

Under this design:

- production no longer depends on `commit-artifacts`
- a failure to commit generated files can no longer block production freshness
- the live site continues to serve the last successful deploy if compute or deploy fails

Initial direction:

- remove the job entirely, or
- disable it for now while the artifact-driven deploy path becomes primary

Either choice is acceptable as long as deployment no longer depends on it.

### 4. Narrow `deploy-pages.yml` to UI-only changes

The existing production deploy workflow must not continue deploying stale repository `public/` for data-changing merges.

So `deploy-pages.yml` should be repurposed to handle only UI-oriented changes, such as:

- `ui/**`
- UI dependency lockfile changes
- other build-only inputs that do not require fresh recomputation

It must also explicitly skip commits that include any data-affecting paths (`products/**`, `config/**`, `scorers/**`, `engine/**`) so mixed UI+data merges are still deployed only by the artifact-driven compute workflow.

Because trigger path filters alone are not sufficient for "UI changes, but not when data changes also occurred," this exclusion should be enforced with a workflow or job-level changed-files guard rather than relying only on `on.push.paths`.

### 5. Workflow ownership model

After this change, deployment responsibility is:

#### `compute-metrics.yml`
- owns fresh data generation
- owns PR preview deploys
- owns production deploys for data-affecting changes and scheduled/manual refreshes

#### `deploy-pages.yml`
- owns UI-only production deploys
- never owns production deploys that require newly generated portfolio/badge artifacts

This removes the ambiguity that currently allows stale repository state to overwrite fresh computed output.

---

## Data Flow

### PR preview path

1. PR changes trigger `compute-metrics.yml`
2. compute jobs produce per-product JSON artifacts
3. `run-engine` produces:
   - `computed/`
   - `public/portfolio.json`
   - `public/badges/`
   - `drift-history.json`
4. preview build downloads those artifacts
5. UI build consumes fresh generated `public/`
6. preview is published

### Production data-change path

1. merge to `main` (or nightly/manual run) triggers `compute-metrics.yml`
2. compute jobs produce fresh artifacts
3. `run-engine` assembles fresh portfolio + badges
4. production build job downloads `engine-artifacts`
5. UI build consumes fresh generated `public/`
6. production deploy publishes the built site

### Production UI-only path

1. UI-only push to `main` triggers `deploy-pages.yml`
2. workflow builds the UI from repository state
3. workflow deploys site without recomputing metrics

This is valid because no data inputs changed.

---

## Error Handling and Failure Modes

### Compute fails

- No production deploy occurs from `compute-metrics.yml`
- existing live site remains on the last successful deployment
- failure is explicit in the compute workflow instead of surfacing later as stale production confusion

### Production deploy fails after successful compute

- fresh artifacts remain available in that workflow run for inspection or redeploy
- live site remains on the last successful deployment
- failure is isolated to deployment rather than hidden inside commit rejection

### UI-only deploy runs on a mixed commit by mistake

- stale repository `public/` could overwrite a fresh compute deployment
- therefore mixed commits must be explicitly excluded from `deploy-pages.yml`

Preventing that overlap is a required part of this design.

---

## Testing Strategy

### Workflow behavior validation

Verify these cases:

1. **PR touching `products/**`**
   - preview build uses fresh `engine-artifacts`
   - preview site reflects recomputed data

2. **Merge touching `products/**`**
   - `compute-metrics.yml` runs on `main`
   - production build/deploy uses fresh `engine-artifacts`
   - live site updates without any generated-file commit to `main`

3. **Merge touching only `ui/**`**
   - `deploy-pages.yml` runs
   - site updates without recomputing portfolio data

4. **Merge touching both `ui/**` and `products/**`**
   - artifact-driven production deploy path wins
   - UI-only deploy path is skipped

### Repository verification

After implementation:

- inspect workflow trigger conditions
- verify no stale deploy workflow can run on data-changing commits
- verify production deploy consumes downloaded `engine-artifacts`, not checked-in generated files

---

## Out of Scope

- redesigning scorer behavior
- redesigning PR preview UX
- introducing a second artifacts PR flow for generated files
- solving GitHub Pages platform rate limits unrelated to repository-state freshness
- preserving committed `computed/` and `public/` as canonical long-term deployment inputs

---

## Open Follow-Up

If the team still wants generated artifacts versioned in git for traceability, that should be designed separately as a non-critical archival workflow. It should not be part of the production freshness path.
