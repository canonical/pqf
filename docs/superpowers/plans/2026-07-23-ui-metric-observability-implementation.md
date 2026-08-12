# UI Metric Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver three UI improvements in one cycle: dependency heatmap on product pages, grouped product rows on dimension pages, and a dedicated metric distribution page with tier pass/fail + raw values.

**Architecture:** Add a shared pure transformation module in `ui/src/lib` that builds consistent root/leaf grouped models and metric-evaluation rows from `portfolio.json`. Reuse it in `ProductDetail`, `DimensionDetail`, and a new `MetricDistribution` view. Keep all logic client-side and deterministic, with no scorer/backend changes.

**Tech Stack:** React 19, TypeScript (strict), React Router, Vitest + React Testing Library, Canonical React Components.

## Global Constraints

- Use only `public/portfolio.json` data via `usePortfolio()`; no backend/API additions.
- Implement all three UI improvements in the same delivery cycle.
- Default grouping and distribution views must include both roots and sub-products grouped by root.
- Metric distribution must show raw metric values plus bronze/silver/gold pass/fail evaluation for the selected metric.
- Preserve existing navigation/error patterns and render `—`/`N/A` for missing or non-applicable data.
- Follow existing UI style patterns and avoid introducing a new CSS framework.

---

### Task 1: Build shared grouped and metric-evaluation primitives

**Files:**
- Create: `ui/src/lib/groupedPortfolioView.ts`
- Create: `ui/src/lib/groupedPortfolioView.test.ts`
- Modify: `ui/src/types.ts` (only if helper-specific typed aliases are needed and reusable)

**Interfaces:**
- Consumes:
  - `Portfolio`, `Product`, `DimensionEntry`, `Medal` from `ui/src/types.ts`
- Produces:
  - `buildGroupedProducts(portfolio: Portfolio): GroupedRootRow[]`
  - `buildDimensionGroupedRows(portfolio: Portfolio, dimensionId: string): GroupedDimensionRow[]`
  - `buildMetricDistributionRows(portfolio: Portfolio, dimensionId: string, metricKey: string): MetricDistributionRow[]`
  - `evaluateMetricAgainstTier(criteria: string[], metricKey: string, value: string | number | boolean | undefined): 'pass' | 'fail' | 'na'`

- [ ] **Step 1: Write failing utility tests**

```ts
import { describe, expect, it } from 'vitest'
import {
  buildGroupedProducts,
  buildMetricDistributionRows,
  evaluateMetricAgainstTier,
} from './groupedPortfolioView'

describe('groupedPortfolioView', () => {
  it('builds root -> leaf grouped rows', () => {
    const rows = buildGroupedProducts(mockPortfolio)
    expect(rows[0].root.id).toBe('discourse')
    expect(rows[0].leaves.length).toBeGreaterThan(0)
  })

  it('evaluates a numeric metric for a tier condition', () => {
    const result = evaluateMetricAgainstTier(['coverage_pct >= 80'], 'coverage_pct', 83)
    expect(result).toBe('pass')
  })

  it('returns na when tier does not reference metric', () => {
    const result = evaluateMetricAgainstTier(['latest_build_passing == true'], 'coverage_pct', 83)
    expect(result).toBe('na')
  })
})
```

- [ ] **Step 2: Run focused test to verify failure**

Run: `cd ui && npm test -- src/lib/groupedPortfolioView.test.ts`  
Expected: FAIL with module/function not found.

- [ ] **Step 3: Implement minimal pure functions**

```ts
export function buildGroupedProducts(portfolio: Portfolio): GroupedRootRow[] {
  const byId = new Map(portfolio.products.map(p => [p.id, p]))
  return portfolio.products
    .filter(p => p.product_type === 'root')
    .map(root => ({
      root,
      leaves: (root.composed_of ?? [])
        .map(ref => byId.get(ref.product_id))
        .filter((p): p is Product => Boolean(p)),
    }))
}
```

- [ ] **Step 4: Implement metric tier evaluation helper**

```ts
export function evaluateMetricAgainstTier(
  criteria: string[],
  metricKey: string,
  value: string | number | boolean | undefined,
): 'pass' | 'fail' | 'na' {
  const criterion = criteria.find(c => c.startsWith(`${metricKey} `))
  if (!criterion) return 'na'
  if (value === undefined) return 'fail'
  // parse operator and rhs, then evaluate deterministically
  return passes ? 'pass' : 'fail'
}
```

- [ ] **Step 5: Re-run utility tests**

Run: `cd ui && npm test -- src/lib/groupedPortfolioView.test.ts`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/src/lib/groupedPortfolioView.ts ui/src/lib/groupedPortfolioView.test.ts ui/src/types.ts
git commit -m "feat(ui): add shared grouped metric view primitives"
```

---

### Task 2: Convert Product Detail dependencies panel to dimension heatmap

**Files:**
- Modify: `ui/src/views/ProductDetail.tsx`
- Modify: `ui/src/views/__tests__/ProductDetail.test.tsx`
- (Optional) Create: `ui/src/components/DependencyDimensionHeatmap.tsx`
- (Optional) Create: `ui/src/components/DependencyDimensionHeatmap.test.tsx`

**Interfaces:**
- Consumes:
  - `buildGroupedProducts(portfolio)` from Task 1
  - dimension keys from `portfolio.dimensions_meta`
- Produces:
  - Dependencies section with sub-product rows and per-dimension medal cells
  - Existing dependency links preserved

- [ ] **Step 1: Add failing ProductDetail test for heatmap rendering**

```ts
it('renders dependency heatmap with dimension medal cells for sub-products', async () => {
  renderWithRouter(<ProductDetail />, { route: '/products/discourse' })
  expect(await screen.findByText('Dependencies')).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /test verification/i })).toBeInTheDocument()
  expect(screen.getByText(/discourse-k8s/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd ui && npm test -- src/views/__tests__/ProductDetail.test.tsx`  
Expected: FAIL because heatmap headers/cells do not exist yet.

- [ ] **Step 3: Implement dependency heatmap table**

```tsx
const dimensionIds = Object.keys(portfolio.dimensions_meta)

<table>
  <thead>
    <tr>
      <th>Sub-product</th>
      {dimensionIds.map(dim => <th key={dim}>{portfolio.dimensions_meta[dim]?.label ?? dim}</th>)}
    </tr>
  </thead>
  <tbody>
    {leafProducts.map(leaf => (
      <tr key={leaf.id}>
        <td><Link to={`/products/${leaf.id}`}>{leaf.name}</Link></td>
        {dimensionIds.map(dim => <td key={dim}><MedalBadge medal={leaf.dimensions[dim]?.medal ?? 'unrated'} size="small" /></td>)}
      </tr>
    ))}
  </tbody>
</table>
```

- [ ] **Step 4: Preserve existing dependency navigation sections**

Run a quick code check that sub-products links, “Also scored by this team”, and “External dependencies” sections remain present after insertion/restructure.

- [ ] **Step 5: Run ProductDetail tests**

Run: `cd ui && npm test -- src/views/__tests__/ProductDetail.test.tsx`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/src/views/ProductDetail.tsx ui/src/views/__tests__/ProductDetail.test.tsx ui/src/components/DependencyDimensionHeatmap.tsx ui/src/components/DependencyDimensionHeatmap.test.tsx
git commit -m "feat(ui): add dependency dimension heatmap to product detail"
```

---

### Task 3: Group Dimension Detail product scores as root + leaves

**Files:**
- Modify: `ui/src/views/DimensionDetail.tsx`
- Modify: `ui/src/views/__tests__/DimensionDetail.test.tsx`

**Interfaces:**
- Consumes:
  - `buildDimensionGroupedRows(portfolio, dimensionId)` from Task 1
- Produces:
  - Grouped Product Scores table with root row + tree-indented leaf rows
  - Existing drift rendering retained for rows where it applies

- [ ] **Step 1: Add failing DimensionDetail grouped-layout test**

```ts
it('renders product scores grouped by root with nested leaf rows', async () => {
  renderWithRouter(<DimensionDetail />, { route: '/dimensions/test_verification' })
  expect(await screen.findByText('Product scores')).toBeInTheDocument()
  expect(screen.getByText('Discourse')).toBeInTheDocument()
  expect(screen.getByText('discourse-k8s')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd ui && npm test -- src/views/__tests__/DimensionDetail.test.tsx`  
Expected: FAIL because current table is flat.

- [ ] **Step 3: Replace flat map with grouped rows**

```tsx
{groupedRows.map(group => (
  <Fragment key={group.root.id}>
    <tr>{/* root row */}</tr>
    {group.leaves.map(leaf => (
      <tr key={leaf.id}>{/* indented/tree leaf row */}</tr>
    ))}
  </Fragment>
))}
```

- [ ] **Step 4: Keep link behavior and medal rendering consistent**

Ensure root/leaf product names still link to `/products/:id` and use `MedalBadge` sizing already used in table views.

- [ ] **Step 5: Run DimensionDetail tests**

Run: `cd ui && npm test -- src/views/__tests__/DimensionDetail.test.tsx`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/src/views/DimensionDetail.tsx ui/src/views/__tests__/DimensionDetail.test.tsx
git commit -m "feat(ui): group dimension scores by root and sub-products"
```

---

### Task 4: Add dedicated Metric Distribution page and route

**Files:**
- Create: `ui/src/views/MetricDistribution.tsx`
- Create: `ui/src/views/__tests__/MetricDistribution.test.tsx`
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/views/DimensionDetail.tsx` (metric links to new route)
- Modify: `ui/src/components/GlobalNav.tsx` (only if navigation discoverability is needed)

**Interfaces:**
- Consumes:
  - `buildMetricDistributionRows(portfolio, dimensionId, metricKey)` from Task 1
  - route params `dimensionId`, `metricKey`
- Produces:
  - `/dimensions/:dimensionId/metrics/:metricKey` page
  - grouped rows, raw metric value, bronze/silver/gold pass/fail indicators
  - filters: squad, medal, product type, show-only-failures

- [ ] **Step 1: Add failing route + page test**

```ts
it('renders metric distribution with tier pass/fail columns', async () => {
  renderWithRouter(<App />, { route: '/dimensions/test_verification/metrics/coverage_pct' })
  expect(await screen.findByRole('heading', { name: /metric distribution/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /bronze/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /silver/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /gold/i })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd ui && npm test -- src/views/__tests__/MetricDistribution.test.tsx`  
Expected: FAIL because route/page do not exist.

- [ ] **Step 3: Add lazy import and route**

```tsx
const MetricDistribution = lazy(() => import('./views/MetricDistribution'))
// ...
<Route path="/dimensions/:dimensionId/metrics/:metricKey" element={<MetricDistribution />} />
```

- [ ] **Step 4: Implement MetricDistribution view with filters**

```tsx
const rows = buildMetricDistributionRows(portfolio, dimensionId, metricKey)
const filtered = rows.filter(/* squad, medal, type, failure toggle */)

<table>
  <thead>
    <tr>
      <th>Product</th><th>Value</th><th>Bronze</th><th>Silver</th><th>Gold</th>
    </tr>
  </thead>
  <tbody>{/* grouped root + leaves */}</tbody>
</table>
```

- [ ] **Step 5: Link metrics from DimensionDetail**

```tsx
<Link to={`/dimensions/${id}/metrics/${key}`}>
  <strong>{out.label}</strong>
</Link>
```

- [ ] **Step 6: Run view tests**

Run: `cd ui && npm test -- src/views/__tests__/MetricDistribution.test.tsx src/views/__tests__/DimensionDetail.test.tsx`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ui/src/App.tsx ui/src/views/MetricDistribution.tsx ui/src/views/__tests__/MetricDistribution.test.tsx ui/src/views/DimensionDetail.tsx
git commit -m "feat(ui): add metric distribution view with tier evaluation"
```

---

### Task 5: End-to-end UI verification and CI parity

**Files:**
- Modify: `ui/src/views/__tests__/ProductsExplorer.test.tsx` (only if shared grouping behavior changes affect expectations)
- Modify: `ui/src/views/__tests__/Overview.test.tsx` (only if indirect assumptions need updates)
- No new production files expected unless test findings require small fixes

**Interfaces:**
- Consumes:
  - all interfaces produced by Tasks 1–4
- Produces:
  - verified green UI test suite and full repo CI check

- [ ] **Step 1: Run full UI tests**

Run: `make test-ui`  
Expected: PASS (all Vitest suites green).

- [ ] **Step 2: Run full CI parity checks**

Run: `make ci-check`  
Expected: PASS for lint, format-check, Python tests, and UI tests.

- [ ] **Step 3: Manual sanity pass in dev mode**

Run:

```bash
make dev
```

Validate in browser:
- Product page shows dependency heatmap with dimension columns.
- Dimension page shows grouped root/sub-product score rows.
- Metric distribution route loads and filters work.

- [ ] **Step 4: Commit any final test/alignment fixes**

```bash
git add ui/src/views/__tests__ ui/src/views ui/src/lib
git commit -m "test(ui): align coverage for grouped metric observability views"
```

## Self-review checklist (completed)

- Spec coverage: all three requested UI improvements are mapped to Tasks 2–4; shared primitives are Task 1; validation is Task 5.
- Placeholder scan: no TODO/TBD placeholders in tasks; commands and target files are concrete.
- Type/interface consistency: all task interfaces use existing `Portfolio/Product/DimensionEntry/Medal` and consistent helper signatures from Task 1.

