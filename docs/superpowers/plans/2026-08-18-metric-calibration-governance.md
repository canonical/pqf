# Metric Calibration Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encode PQF's calibration philosophy and next calibration phases into contributor-facing repo docs and open a documentation PR.

**Architecture:** Update the high-level README with a concise philosophy statement, put the strict contributor contract in AGENTS.md, extend local-scoring semantics where contributors work on scoring, and add one dedicated roadmap document for the remaining phases. Keep the change set docs-only so the PR is easy to review and future calibration work can reference it cleanly.

**Tech Stack:** Markdown documentation, git, gh CLI

## Global Constraints

- Keep the philosophy simple, prescriptive, and high-confidence.
- Support only sanctioned structural variants, not arbitrary team-specific drift.
- Preserve the distinction between measured-low and unmeasurable.
- Prefer one roadmap document over duplicating the future phases in many places.
- Make no scorer, engine, or UI logic changes in this PR.

---

## File structure map

- Modify: `README.md` — add concise metric-calibration philosophy section and links.
- Modify: `AGENTS.md` — add strict scorer/rubric evolution rules for humans and AI contributors.
- Modify: `docs/local-scoring.md` — extend measurability semantics and contributor rules for gating.
- Modify: `docs/README.md` — link to the new roadmap document.
- Create: `docs/metric-calibration-roadmap.md` — record remaining phases of calibration work.
- Create: `docs/superpowers/specs/2026-08-18-metric-calibration-governance-design.md` — design record.

---

### Task 1: Document repo-wide philosophy and roadmap links

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`

**Interfaces:**
- Consumes: existing quick links and docs navigation.
- Produces: repo-wide entry points to the philosophy and roadmap docs.

- [ ] **Step 1: Write the failing review criterion**

Manual check:
- `README.md` does not currently explain the calibration philosophy.
- `docs/README.md` does not currently link a calibration roadmap.

- [ ] **Step 2: Add minimal documentation changes**

Add:
- a short README section with the philosophy bullets,
- one new docs index link to the roadmap.

- [ ] **Step 3: Review rendered markdown mentally**

Verify:
- the README section is concise,
- links point to the right files,
- the docs index placement is easy to discover.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/README.md
git commit -m "docs: codify metric calibration philosophy entry points"
```

### Task 2: Add strict contributor guardrails and scoring semantics

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/local-scoring.md`

**Interfaces:**
- Consumes: existing contributor guidance and measurability section.
- Produces: explicit rules for future scorer/rubric work.

- [ ] **Step 1: Write the failing review criterion**

Manual check:
- AGENTS.md does not yet explicitly enumerate the sanctioned-variance rule.
- local-scoring.md explains measurability behavior but not the broader contributor philosophy.

- [ ] **Step 2: Add the guidance**

Add:
- AGENTS.md section for scorer/rubric evolution rules,
- local-scoring.md examples of measured-low vs unmeasured and the gate-confidence rule.

- [ ] **Step 3: Review for duplication and contradiction**

Verify:
- README stays short,
- AGENTS carries the detailed rules,
- local-scoring stays operational and does not become a second policy manifesto.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md docs/local-scoring.md
git commit -m "docs: add calibration guardrails for future scorer work"
```

### Task 3: Record remaining phases and create PR

**Files:**
- Create: `docs/metric-calibration-roadmap.md`

**Interfaces:**
- Consumes: the already-agreed phase ordering from prior calibration work.
- Produces: a stable roadmap reference for future Phase 2+ work.

- [ ] **Step 1: Write the roadmap content**

Include:
- phase objective,
- why the phase exists,
- how it preserves the philosophy.

- [ ] **Step 2: Verify docs-only diff**

Run:
```bash
git diff --stat origin/main...HEAD
```
Expected:
- docs and guidance files only.

- [ ] **Step 3: Push and create PR**

Run:
```bash
git push origin docs/metric-calibration-philosophy
gh pr create --repo canonical/pqf --base main --head docs/metric-calibration-philosophy \
  --title "docs: codify metric calibration philosophy and roadmap" \
  --body "..."
```

- [ ] **Step 4: Validate PR summary**

Confirm the PR clearly states:
- philosophy encoded,
- sanctioned-variance rule documented,
- next phases recorded,
- no product logic changed.

---

## Self-review

### Spec coverage check
- Philosophy visibility → Task 1 + Task 2.
- Contributor guardrails → Task 2.
- Remaining phases reference → Task 1 + Task 3.
- Docs-only PR → Task 3.

### Placeholder scan
- No TBD/TODO placeholders.
- Every task has exact files and outcomes.

### Type/interface consistency
- All links and file paths are concrete and repo-relative.
