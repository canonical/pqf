# Portfolio Terminology Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove user-facing uses of "Portfolio" from the current PQF UI and current documentation, replacing them with clearer terms such as "Products" or "tracked products" while keeping internal artifact names unchanged.

**Architecture:** Treat this as a copy-only rename across current shipped surfaces. Keep technical identifiers such as `public/portfolio.json`, `Portfolio`, `usePortfolio`, and assembler function names stable so the change stays low-risk and focused on visible terminology.

**Tech Stack:** React 19, TypeScript, Vitest, Markdown docs, Playwright screenshots

## Global Constraints

- Keep internal artifact names such as `portfolio.json`, `Portfolio`, and `usePortfolio` unchanged in this pass.
- Rename visible UI labels to `Products` where they refer to navigation or page names.
- Use prose alternatives such as `tracked products` or `cross-product` where `Products` reads awkwardly.
- Update any tests that assert the renamed UI copy.
- Refresh screenshots that visibly include the renamed copy.

---

### Task 1: Update UI copy and current documentation

**Files:**
- Modify: `ui/src/views/Overview.tsx`
- Modify: `ui/src/views/ProductDetail.tsx`
- Modify: `ui/src/views/DimensionDetail.tsx`
- Modify: `ui/src/views/About.tsx`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/views/overview.md`
- Modify: `docs/architecture.md`
- Modify: `docs/adding-a-dimension.md`
- Modify: `docs/local-scoring.md`
- Modify: `docs/metric-calibration-roadmap.md`

**Interfaces:**
- Consumes: Existing routed UI views and current docs prose
- Produces: Updated visible terminology with no routing or data-shape changes

- [ ] **Step 1: Update visible UI labels**

```tsx
<h1 className="p-heading--2">Products overview</h1>
<Link to="/">← Products</Link>
<Link to="/">Back to products</Link>
```

- [ ] **Step 2: Update prose documentation**

```md
PQF tracks the quality and compliance state of Canonical Platform Engineering's tracked products.
This rule set exists to keep PQF useful for cross-product reasoning.
```

- [ ] **Step 3: Keep internal artifact names unchanged**

```ts
const { data: portfolio } = usePortfolio()
const res = await fetch(`${import.meta.env.BASE_URL}portfolio.json`)
```

- [ ] **Step 4: Verify only copy changed**

Run: `git --no-pager diff -- ui/src/views README.md AGENTS.md docs`
Expected: only user-facing strings and prose wording change; no route, file path, or type renames

### Task 2: Update tests, screenshots, and validation

**Files:**
- Modify: `ui/src/views/__tests__/Overview.test.tsx`
- Modify: `ui/src/views/__tests__/About.test.tsx`
- Modify: `docs/screenshots/overview.png`
- Modify: `docs/screenshots/dimension-detail-documentation-after.png`

**Interfaces:**
- Consumes: Updated UI copy from Task 1
- Produces: Passing tests and screenshots that match the renamed terminology

- [ ] **Step 1: Update test expectations**

```tsx
expect(screen.getByRole('heading', { name: /products overview/i })).toBeInTheDocument()
expect(screen.getByRole('link', { name: /products overview/i })).toBeInTheDocument()
```

- [ ] **Step 2: Run targeted UI tests**

Run: `cd ui && npm test -- --run src/views/__tests__/Overview.test.tsx src/views/__tests__/About.test.tsx src/views/__tests__/ProductDetail.test.tsx src/views/__tests__/DimensionDetail.test.tsx`
Expected: PASS

- [ ] **Step 3: Refresh screenshots**

```bash
make dev
# Capture:
# - docs/screenshots/overview.png
# - docs/screenshots/dimension-detail-documentation-after.png
```

- [ ] **Step 4: Run build-level verification**

Run: `cd ui && npm test -- --run src/views/__tests__/Overview.test.tsx src/views/__tests__/About.test.tsx src/views/__tests__/ProductDetail.test.tsx src/views/__tests__/DimensionDetail.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add ui/src/views ui/src/views/__tests__ README.md AGENTS.md docs
git commit -m "docs: rename portfolio UI copy to products"
git push
```
