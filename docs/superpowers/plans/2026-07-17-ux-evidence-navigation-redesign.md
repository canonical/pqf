# UX Evidence and Navigation Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore per-metric evidence display for root products using worst-leaf-value logic, add linked component chips in product headers, unify the Dependencies card, remove target/drift from leaf product pages, add a Products explorer page, and add a Products nav link.

**Architecture:** New `RootMetricsList` component handles worst-leaf-value display with per-metric expand. `ProductDetail` is updated to branch on `product.product_type === 'root'` to choose between `RootMetricsList` (for root products with composition) and `MetricsList` (for leaf products or root products with no composition). A new `ProductsExplorer` view at `/products` shows all products grouped by root. Navigation is extended with a "Products" link.

**Tech Stack:** React 19, TypeScript strict, `@canonical/react-components` (Vanilla Framework classes), Vitest + React Testing Library.

## Global Constraints

- `@canonical/react-components` (Vanilla Framework) only — no Tailwind, no shadcn, no custom CSS frameworks.
- TypeScript strict mode. No `any` except in test mocks typed as `ReturnType<typeof usePortfolio>`.
- Tests: Vitest + React Testing Library, co-located with components (`*.test.tsx` next to `*.tsx`); views tests in `ui/src/views/__tests__/`.
- Run tests with: `cd ui && npm test -- --run` (exits after one pass; or `npm test` for watch mode).
- Lint with: `make lint` (ruff for Python only — TypeScript has no separate lint target).
- Medal grade colours: gold `#C7962F`, silver `#8F8F8F`, bronze `#9E622A`, unrated `#666`, remediating `#E98B06`, overdue `#C7162B`.
- All `<Link>` components use `react-router`'s `Link` (not `<a>` for internal routes).
- `HashRouter` is used in `App.tsx` — internal routes are hash-based (`#/products/:id` etc).

---

## File Map

| Path | Action | Responsibility |
|------|--------|----------------|
| `ui/src/components/RootMetricsList.tsx` | Create | Worst-leaf-value display with per-metric expand |
| `ui/src/components/RootMetricsList.test.tsx` | Create | Unit tests for RootMetricsList |
| `ui/src/views/ProductDetail.tsx` | Modify | Branch root/leaf rendering; new header chips; unified deps card |
| `ui/src/views/__tests__/ProductDetail.test.tsx` | Modify | Update stale tests; add new tests for new behaviours |
| `ui/src/views/ProductsExplorer.tsx` | Create | All-products page grouped by root with squad filter |
| `ui/src/views/__tests__/ProductsExplorer.test.tsx` | Create | Unit tests for ProductsExplorer |
| `ui/src/App.tsx` | Modify | Add `/products` route |
| `ui/src/components/GlobalNav.tsx` | Modify | Add "Products" nav link between Portfolio and Dimensions |
| `ui/src/components/GlobalNav.test.tsx` | Modify | Add assertion for Products link |

---

## Task 1: RootMetricsList component

**Files:**
- Create: `ui/src/components/RootMetricsList.tsx`
- Create: `ui/src/components/RootMetricsList.test.tsx`

**Interfaces:**
- Consumes: `LeafDimensionResult[]`, `Record<string, { operator: string; value: number | boolean }>` (pre-parsed thresholds from `parseCriteria` in ProductDetail), `Record<string, OutputMeta> | undefined` (from `dimensions_meta[dim].outputs`).
- Produces: exported default function `RootMetricsList({ composition, thresholds, metaOutputs })` — renders a `<dl>` grid identical in layout to `MetricsList`.

---

- [ ] **Step 1.1: Write failing tests**

Create `ui/src/components/RootMetricsList.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import RootMetricsList from './RootMetricsList'
import type { LeafDimensionResult, OutputMeta } from '../types'

const OUTPUTS: Record<string, OutputMeta> = {
  coverage_pct: { label: 'Coverage', description: 'Test coverage %', type: 'number', range: '0-100' },
  latest_build_passing: { label: 'Build passing', description: 'Latest build', type: 'boolean', range: 'true/false' },
}

const THRESHOLDS = {
  coverage_pct: { operator: '>=', value: 70 },
  latest_build_passing: { operator: '==', value: true },
}

function leaf(
  id: string,
  metrics: Record<string, string | number | boolean>,
  excluded = false,
): LeafDimensionResult {
  return {
    product_id: id,
    repo: `canonical/${id}`,
    medal: 'unrated' as const,
    applicability: 'scored' as const,
    metrics,
    excluded_from_parent_medal: excluded,
  }
}

const LOW_LEAF = leaf('synapse', { coverage_pct: 0, latest_build_passing: true })
const HIGH_LEAF = leaf('saml', { coverage_pct: 70, latest_build_passing: false })

describe('RootMetricsList', () => {
  it('renders metric labels from metaOutputs', () => {
    render(
      <RootMetricsList composition={[LOW_LEAF]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    expect(screen.getByText('Coverage')).toBeInTheDocument()
    expect(screen.getByText('Build passing')).toBeInTheDocument()
  })

  it('shows worst coverage value (low for >=) with threshold denominator', () => {
    render(
      <RootMetricsList composition={[LOW_LEAF, HIGH_LEAF]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    // worst coverage = 0 (synapse); threshold >=70 → shown as "0 / 70"
    const dl = screen.getByText('Coverage').closest('dl')!
    expect(dl).toHaveTextContent('0')
    expect(dl).toHaveTextContent('/ 70')
  })

  it('shows expand button when leaves disagree on a metric', () => {
    render(
      <RootMetricsList composition={[LOW_LEAF, HIGH_LEAF]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    const expandBtns = screen.getAllByRole('button', { name: /2 leaves/i })
    expect(expandBtns.length).toBeGreaterThan(0)
  })

  it('does not show expand button when all leaves agree on a metric', () => {
    const agreed = [
      leaf('a', { coverage_pct: 90, latest_build_passing: true }),
      leaf('b', { coverage_pct: 90, latest_build_passing: true }),
    ]
    render(
      <RootMetricsList composition={agreed} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    expect(screen.queryByRole('button', { name: /leaves/i })).not.toBeInTheDocument()
  })

  it('expands to show per-leaf values on button click', () => {
    render(
      <RootMetricsList composition={[LOW_LEAF, HIGH_LEAF]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    const btn = screen.getAllByRole('button', { name: /2 leaves/i })[0]
    fireEvent.click(btn)
    expect(screen.getByText('synapse')).toBeInTheDocument()
    expect(screen.getByText('saml')).toBeInTheDocument()
  })

  it('excludes leaves with excluded_from_parent_medal=true from in-scope count', () => {
    const excluded = leaf('saml', { coverage_pct: 70, latest_build_passing: false }, true)
    render(
      <RootMetricsList composition={[LOW_LEAF, excluded]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    // only 1 leaf in scope → no expand button (all agree trivially)
    expect(screen.queryByRole('button', { name: /leaves/i })).not.toBeInTheDocument()
  })

  it('renders nothing when no in-scope leaves', () => {
    const allExcluded = [leaf('synapse', { coverage_pct: 0 }, true)]
    const { container } = render(
      <RootMetricsList composition={allExcluded} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when metaOutputs is undefined', () => {
    const { container } = render(
      <RootMetricsList composition={[LOW_LEAF]} thresholds={THRESHOLDS} metaOutputs={undefined} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```bash
cd ui && npm test -- --run RootMetricsList
```

Expected: `Cannot find module './RootMetricsList'` or similar import error.

- [ ] **Step 1.3: Create the component**

Create `ui/src/components/RootMetricsList.tsx`:

```tsx
import React from 'react'
import type { LeafDimensionResult, OutputMeta } from '../types'

interface ThresholdInfo {
  operator: string
  value: number | boolean
}

interface Props {
  composition: LeafDimensionResult[]
  thresholds: Record<string, ThresholdInfo>
  metaOutputs: Record<string, OutputMeta> | undefined
}

function meetsThreshold(
  val: string | number | boolean,
  op: string,
  threshold: number | boolean,
): boolean {
  const n = Number(val)
  const t = Number(threshold)
  switch (op) {
    case '>=': return n >= t
    case '<=': return n <= t
    case '>': return n > t
    case '<': return n < t
    case '==': return String(val) === String(threshold)
    default: return false
  }
}

function formatValue(
  val: string | number | boolean,
  threshold?: ThresholdInfo,
): React.ReactNode {
  const label = typeof val === 'boolean' ? (val ? '✓' : '✗') : String(val)
  if (threshold === undefined) return <span>{label}</span>
  const passes = meetsThreshold(val, threshold.operator, threshold.value)
  const color = passes ? '#2d9e46' : '#c7162b'
  if (typeof val === 'boolean') {
    return <span style={{ color, fontWeight: 600 }}>{label}</span>
  }
  return (
    <span style={{ color, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
      {label}
      <span style={{ color: '#999', fontWeight: 400, fontSize: '0.75rem' }}> / {String(threshold.value)}</span>
    </span>
  )
}

function getWorstEntry(
  metricKey: string,
  inScope: LeafDimensionResult[],
  threshold: ThresholdInfo | undefined,
): { value: string | number | boolean; leafId: string } | null {
  const entries = inScope
    .map(leaf => ({ value: leaf.metrics[metricKey], leafId: leaf.product_id }))
    .filter((e): e is { value: string | number | boolean; leafId: string } => e.value !== undefined)

  if (entries.length === 0) return null

  return entries.reduce((worst, current) => {
    const w = worst.value
    const c = current.value
    if (!threshold) {
      if (typeof c === 'boolean') return !c && !!w ? current : worst
      return Number(c) < Number(w) ? current : worst
    }
    const op = threshold.operator
    if (op === '>=' || op === '>') return Number(c) < Number(w) ? current : worst
    if (op === '<=' || op === '<') return Number(c) > Number(w) ? current : worst
    if (op === '==') {
      if (typeof c === 'boolean') return !c && !!w ? current : worst
      const cMisses = String(c) !== String(threshold.value)
      const wMisses = String(w) !== String(threshold.value)
      return cMisses && !wMisses ? current : worst
    }
    return worst
  })
}

export default function RootMetricsList({ composition, thresholds, metaOutputs }: Props) {
  const [expanded, setExpanded] = React.useState<Record<string, boolean>>({})

  const inScope = composition.filter(
    c => !c.excluded_from_parent_medal && c.applicability === 'scored',
  )
  const metricKeys = metaOutputs ? Object.keys(metaOutputs) : []

  if (metricKeys.length === 0 || inScope.length === 0) return null

  return (
    <dl
      className="u-no-margin"
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: '0.1rem 0.75rem',
        fontSize: '0.8125rem',
      }}
    >
      {metricKeys.map(key => {
        const label = metaOutputs![key].label
        const desc = metaOutputs![key].description
        const threshold = thresholds[key]
        const worst = getWorstEntry(key, inScope, threshold)
        if (worst === null) return null

        const allAgree = inScope.every(
          l => l.metrics[key] !== undefined && String(l.metrics[key]) === String(worst.value),
        )
        const isExpanded = expanded[key] ?? false

        return (
          <React.Fragment key={key}>
            <dt style={{ color: '#666', margin: 0 }} title={desc}>
              {label}
            </dt>
            <dd style={{ margin: 0, textAlign: 'right' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem' }}>
                {formatValue(worst.value, threshold)}
                {!allAgree && (
                  <button
                    onClick={() => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))}
                    aria-expanded={isExpanded}
                    aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${label} per-leaf breakdown`}
                    style={{
                      fontSize: '0.6875rem',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#06c',
                      padding: 0,
                    }}
                  >
                    {isExpanded ? '▾' : '▸'} {inScope.length} leaves
                  </button>
                )}
              </span>
              {isExpanded && (
                <div
                  style={{
                    marginTop: '0.25rem',
                    paddingLeft: '0.5rem',
                    borderLeft: '2px solid #e5e5e5',
                  }}
                >
                  {inScope.map(leaf => (
                    <div
                      key={leaf.product_id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        gap: '0.5rem',
                        padding: '0.1rem 0',
                        fontSize: '0.75rem',
                      }}
                    >
                      <span
                        style={{
                          color: '#555',
                          fontWeight: leaf.product_id === worst.leafId ? 600 : 400,
                        }}
                      >
                        {leaf.product_id}
                      </span>
                      <span>
                        {leaf.metrics[key] !== undefined
                          ? formatValue(leaf.metrics[key], undefined)
                          : <span style={{ color: '#999' }}>—</span>
                        }
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </dd>
          </React.Fragment>
        )
      })}
    </dl>
  )
}
```

- [ ] **Step 1.4: Run tests to confirm they pass**

```bash
cd ui && npm test -- --run RootMetricsList
```

Expected: all 8 tests in `RootMetricsList.test.tsx` pass.

- [ ] **Step 1.5: Commit**

```bash
cd ui && npm test -- --run
git add ui/src/components/RootMetricsList.tsx ui/src/components/RootMetricsList.test.tsx
git commit -m "feat(ui): add RootMetricsList component with worst-leaf-value display"
```

---

## Task 2: ProductDetail — root view (evidence + header + dependencies)

**Prereq:** Task 1 must be complete (uses `RootMetricsList`).

**Files:**
- Modify: `ui/src/views/ProductDetail.tsx`
- Modify: `ui/src/views/__tests__/ProductDetail.test.tsx`

**Interfaces:**
- Consumes: `RootMetricsList` from Task 1 (signature: `{ composition, thresholds, metaOutputs }`).
- The `parseCriteria` function stays local in `ProductDetail.tsx` — its output (`Record<string, { operator, value }>`) is passed to `RootMetricsList` as `thresholds`.

---

- [ ] **Step 2.1: Update stale tests and add new tests for root view**

Replace the three stale tests and add two new ones in `ui/src/views/__tests__/ProductDetail.test.tsx`. The tests to replace are:
- `'root product shows composition count in header'` — now tests linked chips, not count
- `'root product shows context refs card'` — now tests unified "Dependencies" card title
- `'root product dimension row shows composition expand button'` — now tests metric values visible, not expand button
- `'clicking composition expands to show leaf breakdown'` — now tests per-metric expand
- `'shows in-scope count excluding excluded leaves in button label'` — button text changed from "N component in scope" to "N leaves"

Replace the entire block starting at line 185 (`'root product shows composition count in header'`) through the end of the `describe` block with the updated tests below.

> The file currently ends at line 249. Replace lines 185–249 (the last 5 tests) with:

```tsx
  it('root product shows linked chips for components in header', () => {
    wrap('matrix')
    expect(screen.getByText('COMPONENTS')).toBeInTheDocument()
    // chip links to /products/synapse and shows the leaf's name
    const chip = screen.getByRole('link', { name: 'Synapse Charm' })
    expect(chip.getAttribute('href')).toContain('synapse')
  })

  it('root product shows unified Dependencies card with sub-products and context refs', () => {
    wrap('matrix')
    expect(screen.getByRole('heading', { name: 'Dependencies' })).toBeInTheDocument()
    // sub-products section present
    expect(screen.getByText(/Sub-products/i)).toBeInTheDocument()
    // context refs present
    expect(screen.getByText('Synapse Operator')).toBeInTheDocument()
    expect(screen.getByText(/Context only/i)).toBeInTheDocument()
  })

  it('root product evidence shows metric values from composition', () => {
    mockWith(
      portfolioWithComposition({
        composition: [
          {
            product_id: 'synapse',
            repo: 'canonical/synapse-operator',
            medal: 'bronze',
            applicability: 'scored',
            metrics: { coverage_pct: 65, latest_build_passing: true },
            excluded_from_parent_medal: false,
          },
        ],
      }),
    )
    wrap('matrix')
    const row = screen.getByRole('link', { name: 'test verification' }).closest('tr')!
    // RootMetricsList should show coverage_pct 65 against gold threshold 90
    expect(row).toHaveTextContent('65')
    expect(row).toHaveTextContent('/ 90')
  })

  it('root product evidence shows per-leaf expand when leaves disagree', () => {
    mockWith(
      portfolioWithComposition({
        composition: [
          {
            product_id: 'synapse',
            repo: 'canonical/synapse-operator',
            medal: 'bronze',
            applicability: 'scored',
            metrics: { coverage_pct: 65, latest_build_passing: true },
            excluded_from_parent_medal: false,
          },
          {
            product_id: 'saml',
            repo: 'canonical/saml-operator',
            medal: 'gold',
            applicability: 'scored',
            metrics: { coverage_pct: 90, latest_build_passing: false },
            excluded_from_parent_medal: false,
          },
        ],
      }),
    )
    wrap('matrix')
    expect(screen.getAllByRole('button', { name: /2 leaves/i }).length).toBeGreaterThan(0)
  })

  it('excludes leaves with excluded_from_parent_medal=true from leaf count in evidence', () => {
    mockWith(
      portfolioWithComposition({
        composition: [
          {
            product_id: 'synapse',
            repo: 'canonical/synapse-operator',
            medal: 'bronze',
            applicability: 'scored',
            metrics: { coverage_pct: 65 },
            excluded_from_parent_medal: false,
          },
          {
            product_id: 'saml',
            repo: 'canonical/saml-operator',
            medal: 'gold',
            applicability: 'scored',
            metrics: {},
            excluded_from_parent_medal: true,
          },
        ] as LeafDimensionResult[],
      }),
    )
    wrap('matrix')
    // 1 in-scope leaf → no expand button needed (no disagreement possible)
    expect(screen.queryByRole('button', { name: /leaves/i })).not.toBeInTheDocument()
  })
```

Also add this import at the top of the file if not already present (it already is from the existing file):
```tsx
import type { Portfolio, LeafDimensionResult } from '../../types'
```

- [ ] **Step 2.2: Run tests to confirm the new tests fail**

```bash
cd ui && npm test -- --run ProductDetail
```

Expected: several tests fail. The three we replaced will fail because the DOM still has old text ("COMPOSED OF", "Dependencies (context only)", expand button with "component in scope"). That's expected at this stage.

- [ ] **Step 2.3: Rewrite ProductDetail.tsx**

Replace the entire contents of `ui/src/views/ProductDetail.tsx` with:

```tsx
import React from 'react'
import { useParams, Link } from 'react-router'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import DriftChip from '../components/DriftChip'
import MetricsList from '../components/MetricsList'
import RootMetricsList from '../components/RootMetricsList'
import LoadingSpinner from '../components/LoadingSpinner'

const SQUAD_TEAMS: Record<string, { label: string; url: string }> = {
  americas: { label: 'AMER', url: 'https://github.com/orgs/canonical/teams/platform-engineering-amer' },
  emea: { label: 'EMEA', url: 'https://github.com/orgs/canonical/teams/platform-engineering-emea' },
  apac: { label: 'APAC', url: 'https://github.com/orgs/canonical/teams/platform-engineering-apac' },
}

function parseCriteria(criteria: string[]): Record<string, { operator: string; value: number | boolean }> {
  const result: Record<string, { operator: string; value: number | boolean }> = {}
  for (const criterion of criteria) {
    const match = criterion.match(/^(\w+)\s*(>=|<=|==|>|<)\s*(.+)$/)
    if (!match) continue
    const [, metric, operator, rawValue] = match
    let value: number | boolean
    if (rawValue === 'true') value = true
    else if (rawValue === 'false') value = false
    else value = parseFloat(rawValue)
    result[metric] = { operator, value }
  }
  return result
}

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: portfolio, isLoading, isError, error } = usePortfolio()

  if (isLoading) return <LoadingSpinner />
  if (isError) return <div className="p-notification--negative"><p>{error?.message}</p></div>
  if (!portfolio) return null

  const product = portfolio.products.find(p => p.id === id)
  if (!product) {
    return (
      <div className="row" style={{ paddingTop: '1.5rem' }}>
        <div className="col-12">
          <p>Product <strong>{id}</strong> not found. <Link to="/">Back to portfolio</Link></p>
        </div>
      </div>
    )
  }

  const isRoot = product.product_type === 'root'
  const hasComposedOf = isRoot && product.composed_of && product.composed_of.length > 0
  const hasDependencies =
    (product.composed_of && product.composed_of.length > 0) ||
    product.context_refs.length > 0

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">

        {/* Back nav */}
        <p style={{ marginBottom: '1rem' }}><Link to="/">← Portfolio</Link></p>

        {/* Header card */}
        <div className="p-card u-sv3">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 className="p-heading--3" style={{ marginBottom: '0.25rem' }}>{product.name}</h1>
              {product.description && (
                <p className="u-text--muted" style={{ margin: 0 }}>{product.description}</p>
              )}
            </div>
            {product.documentation_url && (
              <a href={product.documentation_url} target="_blank" rel="noreferrer" className="p-button--neutral is-small">
                Docs ↗
              </a>
            )}
          </div>
          <hr style={{ margin: '1rem 0' }} />

          {/* Medal / lifecycle / squad row */}
          <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
            <div>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>
                {isRoot ? 'CURRENT' : 'COMPUTED MEDAL'}
              </span>
              <MedalBadge medal={product.current_medal} />
            </div>
            {isRoot && (
              <div>
                <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>TARGET</span>
                <MedalBadge medal={product.target_medal} />
              </div>
            )}
            <div>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>LIFECYCLE</span>
              <span className="p-label">{product.lifecycle}</span>
            </div>
            <div>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>SQUAD</span>
              {(() => {
                const team = SQUAD_TEAMS[product.squad?.toLowerCase()]
                if (!team) return <span>{product.squad || '—'}</span>
                return (
                  <a href={team.url} target="_blank" rel="noreferrer"
                    className="p-chip"
                    style={{ textDecoration: 'none', fontSize: '0.875rem', padding: '0.2rem 0.6rem' }}>
                    {team.label}
                  </a>
                )
              })()}
            </div>
          </div>

          {/* Part of: (leaf pages) */}
          {product.parent_product_ids.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
              <span className="u-text--muted" style={{ fontSize: '0.75rem' }}>Part of:</span>
              {product.parent_product_ids.map(parentId => {
                const parent = portfolio.products.find(p => p.id === parentId)
                return parent ? (
                  <Link key={parentId} to={`/products/${parentId}`}
                    className="p-chip"
                    style={{ fontSize: '0.75rem', textDecoration: 'none', padding: '0.15rem 0.5rem' }}>
                    {parent.name}
                  </Link>
                ) : null
              })}
            </div>
          )}

          {/* Components chips (root products only) */}
          {hasComposedOf && (
            <div style={{ marginTop: '1rem' }}>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>COMPONENTS</span>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {product.composed_of!.map(c => {
                  const leafProduct = portfolio.products.find(p => p.id === c.product_id)
                  return (
                    <Link key={c.product_id} to={`/products/${c.product_id}`}
                      className="p-chip"
                      style={{ fontSize: '0.75rem', textDecoration: 'none', padding: '0.15rem 0.5rem' }}>
                      {leafProduct?.name ?? c.product_id}
                    </Link>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Dimensions card */}
        <div className="p-card u-sv3">
          <h2 className="p-heading--4" style={{ marginBottom: '1rem' }}>Dimensions</h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse' }}>
              <colgroup>
                <col style={{ width: '22%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '48%' }} />
              </colgroup>
              <thead>
                <tr style={{ borderBottom: '1px solid #d9d9d9' }}>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Dimension</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Current</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Drift</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(product.dimensions).map(([dim, entry], idx) => {
                  const dimMeta = portfolio.dimensions_meta[dim]
                  const targetTier = product.target_medal
                  const targetCriteria =
                    targetTier === 'bronze' || targetTier === 'silver' || targetTier === 'gold'
                      ? dimMeta?.medals?.[targetTier]?.criteria ?? []
                      : []
                  const targetThresholds = parseCriteria(targetCriteria)

                  return (
                    <tr key={dim} style={{ borderBottom: '1px solid #e5e5e5', background: idx % 2 === 0 ? '#fafafa' : '#fff' }}>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        <Link to={`/dimensions/${dim}`} style={{ fontWeight: 500 }}>{dim.replace(/_/g, ' ')}</Link>
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        <MedalBadge medal={entry.medal} size="small" />
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        {isRoot && <DriftChip drift={entry.drift} />}
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        {isRoot && entry.composition && entry.composition.length > 0 ? (
                          <RootMetricsList
                            composition={entry.composition}
                            thresholds={targetThresholds}
                            metaOutputs={dimMeta?.outputs}
                          />
                        ) : (
                          <MetricsList
                            metrics={entry.metrics}
                            thresholds={isRoot ? targetThresholds : undefined}
                            metaOutputs={dimMeta?.outputs}
                          />
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Unified Dependencies card */}
        {hasDependencies && (
          <div className="p-card u-sv3">
            <h2 className="p-heading--4" style={{ marginBottom: '0.5rem' }}>Dependencies</h2>

            {product.composed_of && product.composed_of.length > 0 && (
              <div style={{ marginBottom: product.context_refs.length > 0 ? '1rem' : 0 }}>
                <p className="u-text--muted" style={{ fontSize: '0.875rem', margin: '0 0 0.5rem' }}>
                  Sub-products — scored and included in medal calculation
                </p>
                <ul className="p-list" style={{ marginBottom: 0 }}>
                  {product.composed_of.map(c => {
                    const leafProduct = portfolio.products.find(p => p.id === c.product_id)
                    return (
                      <li key={c.product_id} className="p-list__item"
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0' }}>
                        <Link to={`/products/${c.product_id}`}>
                          {leafProduct?.name ?? c.product_id}
                        </Link>
                        {leafProduct?.product_type && (
                          <span className="p-label--information" style={{ fontSize: '0.75rem' }}>
                            {leafProduct.product_type}
                          </span>
                        )}
                        {leafProduct?.source?.repo && (
                          <a href={`https://github.com/${leafProduct.source.repo}`}
                            target="_blank" rel="noreferrer"
                            style={{ fontSize: '0.875rem', color: '#666' }}>
                            {leafProduct.source.repo} ↗
                          </a>
                        )}
                        {c.excluded_from_parent_medal && (
                          <span style={{ fontSize: '0.75rem', color: '#666' }}>(excluded from medal)</span>
                        )}
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}

            {product.context_refs.length > 0 && (
              <div>
                <p className="u-text--muted" style={{ fontSize: '0.875rem', margin: '0 0 0.5rem' }}>
                  Context only — not scored by this team
                </p>
                <ul className="p-list" style={{ marginBottom: 0 }}>
                  {product.context_refs.map((cr, i) => (
                    <li key={i} className="p-list__item"
                      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0' }}>
                      <span>{cr.label}</span>
                      {cr.repo && (
                        <a href={`https://github.com/${cr.repo}`} target="_blank" rel="noreferrer"
                          style={{ fontSize: '0.875rem', color: '#666' }}>
                          {cr.repo} ↗
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
```

- [ ] **Step 2.4: Run tests to confirm all pass**

```bash
cd ui && npm test -- --run ProductDetail
```

Expected: all tests pass. If `'leaf product shows direct metrics without composition layer'` fails because of the old `queryByRole('button', { name: /component in scope/i })`, that test should still pass since the new code doesn't render that button — the leaf case now uses `MetricsList` directly.

- [ ] **Step 2.5: Run full test suite to confirm no regressions**

```bash
cd ui && npm test -- --run
```

Expected: all tests pass.

- [ ] **Step 2.6: Commit**

```bash
git add ui/src/views/ProductDetail.tsx ui/src/views/__tests__/ProductDetail.test.tsx
git commit -m "feat(ui): restore evidence metrics for root products, fix header chips and deps card"
```

---

## Task 3: ProductsExplorer page

**Files:**
- Create: `ui/src/views/ProductsExplorer.tsx`
- Create: `ui/src/views/__tests__/ProductsExplorer.test.tsx`

**Interfaces:**
- Consumes: `usePortfolio()` hook; `Product` type from types.ts.
- Produces: default export `ProductsExplorer` — React component rendered at `/products`.

---

- [ ] **Step 3.1: Write failing tests**

Create `ui/src/views/__tests__/ProductsExplorer.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ProductsExplorer from '../ProductsExplorer'
import type { Portfolio } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

const mockPortfolio: Portfolio = {
  generated_at: '2026-06-30T00:00:00Z',
  dimensions_meta: {},
  products: [
    {
      id: 'matrix',
      name: 'Matrix (Synapse)',
      product_type: 'root',
      lifecycle: 'stable',
      target_medal: 'gold',
      current_medal: 'bronze',
      squad: 'americas',
      is_portfolio_entry: true,
      context_refs: [],
      parent_product_ids: [],
      composed_of: [{ product_id: 'synapse', excluded_from_parent_medal: false }],
      dimensions: {},
    },
    {
      id: 'synapse',
      name: 'Synapse Charm',
      product_type: 'charm',
      lifecycle: 'stable',
      target_medal: 'gold',
      current_medal: 'unrated',
      squad: '',
      is_portfolio_entry: false,
      context_refs: [],
      parent_product_ids: ['matrix'],
      composed_of: null,
      source: { repo: 'canonical/synapse-operator', subpath: null },
      dimensions: {},
    },
    {
      id: 'wazuh',
      name: 'Wazuh Indexer',
      product_type: 'root',
      lifecycle: 'stable',
      target_medal: 'silver',
      current_medal: 'bronze',
      squad: 'emea',
      is_portfolio_entry: true,
      context_refs: [],
      parent_product_ids: [],
      composed_of: null,
      dimensions: {},
    },
  ],
}

function wrap() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/products']}>
        <ProductsExplorer />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProductsExplorer', () => {
  beforeEach(() => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: mockPortfolio,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)
  })

  it('renders the Products heading', () => {
    wrap()
    expect(screen.getByRole('heading', { name: 'Products' })).toBeInTheDocument()
  })

  it('shows root product with a link', () => {
    wrap()
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
  })

  it('shows leaf product indented under its root', () => {
    wrap()
    expect(screen.getByRole('link', { name: 'Synapse Charm' })).toBeInTheDocument()
  })

  it('shows squad filter dropdown', () => {
    wrap()
    expect(screen.getByRole('combobox', { name: /filter by squad/i })).toBeInTheDocument()
  })

  it('filters root products by squad', () => {
    wrap()
    const select = screen.getByRole('combobox', { name: /filter by squad/i })
    fireEvent.change(select, { target: { value: 'emea' } })
    expect(screen.queryByRole('link', { name: 'Matrix (Synapse)' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Wazuh Indexer' })).toBeInTheDocument()
  })

  it('shows medal for root product', () => {
    wrap()
    // At least one Bronze badge should be visible
    expect(screen.getAllByText('Bronze').length).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 3.2: Run tests to confirm they fail**

```bash
cd ui && npm test -- --run ProductsExplorer
```

Expected: `Cannot find module '../ProductsExplorer'`.

- [ ] **Step 3.3: Create the ProductsExplorer view**

Create `ui/src/views/ProductsExplorer.tsx`:

```tsx
import { useState, useMemo } from 'react'
import { Link } from 'react-router'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import type { Product } from '../types'

const SQUAD_LABELS: Record<string, string> = {
  americas: 'AMER',
  emea: 'EMEA',
  apac: 'APAC',
}

export default function ProductsExplorer() {
  const { data: portfolio, isLoading, isError, error } = usePortfolio()
  const [squadFilter, setSquadFilter] = useState('all')

  const { rootProducts, standaloneLeaves, squads } = useMemo(() => {
    if (!portfolio) return { rootProducts: [], standaloneLeaves: [], squads: [] as string[] }

    const roots = portfolio.products.filter(p => p.product_type === 'root')
    const leafIds = new Set(
      roots.flatMap(r => (r.composed_of ?? []).map(c => c.product_id)),
    )
    const standalone = portfolio.products.filter(
      p => p.product_type !== 'root' && !leafIds.has(p.id),
    )
    const squads = [...new Set(roots.map(p => p.squad).filter(Boolean))]

    return { rootProducts: roots, standaloneLeaves: standalone, squads }
  }, [portfolio])

  const filteredRoots = useMemo(
    () =>
      rootProducts.filter(p => squadFilter === 'all' || p.squad === squadFilter),
    [rootProducts, squadFilter],
  )

  if (isLoading) return <LoadingSpinner />
  if (isError) return <div className="p-notification--negative"><p>{error?.message}</p></div>
  if (!portfolio) return null

  const TH_STYLE: React.CSSProperties = {
    padding: '0.5rem 0.75rem',
    textAlign: 'left',
    fontSize: '0.75rem',
    fontWeight: 600,
    textTransform: 'uppercase',
    color: '#666',
  }

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">
        <h1 className="p-heading--3" style={{ marginBottom: '1rem' }}>Products</h1>

        {/* Squad filter */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center' }}>
          <select
            value={squadFilter}
            onChange={e => setSquadFilter(e.target.value)}
            className="p-form__control"
            style={{ width: 'auto' }}
            aria-label="Filter by squad"
          >
            <option value="all">All squads</option>
            {squads.map(s => (
              <option key={s} value={s}>
                {SQUAD_LABELS[s.toLowerCase()] ?? s}
              </option>
            ))}
          </select>
        </div>

        {/* Products table */}
        <div className="p-card u-sv3">
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #d9d9d9' }}>
                  <th style={TH_STYLE}>Product</th>
                  <th style={TH_STYLE}>Type</th>
                  <th style={TH_STYLE}>Medal</th>
                  <th style={TH_STYLE}>Squad / Repo</th>
                </tr>
              </thead>
              <tbody>
                {filteredRoots.map(root => {
                  const leafProducts = (root.composed_of ?? [])
                    .map(c => portfolio.products.find(p => p.id === c.product_id))
                    .filter((p): p is Product => p !== undefined)

                  return (
                    <>
                      <tr key={root.id} style={{ borderBottom: '1px solid #e5e5e5', background: '#fafafa' }}>
                        <td style={{ padding: '0.75rem' }}>
                          <Link to={`/products/${root.id}`} style={{ fontWeight: 600 }}>
                            {root.name}
                          </Link>
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          <span className="p-label" style={{ fontSize: '0.75rem' }}>
                            {root.product_type}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          <MedalBadge medal={root.current_medal} size="small" />
                        </td>
                        <td style={{ padding: '0.75rem', fontSize: '0.875rem' }}>
                          {SQUAD_LABELS[root.squad?.toLowerCase()] ?? root.squad}
                        </td>
                      </tr>
                      {leafProducts.map(leaf => (
                        <tr key={leaf.id} style={{ borderBottom: '1px solid #e5e5e5', background: '#fff' }}>
                          <td style={{ padding: '0.5rem 0.75rem 0.5rem 2rem' }}>
                            <Link to={`/products/${leaf.id}`} style={{ color: '#555' }}>
                              {leaf.name}
                            </Link>
                          </td>
                          <td style={{ padding: '0.5rem 0.75rem' }}>
                            <span className="p-label--information" style={{ fontSize: '0.75rem' }}>
                              {leaf.product_type}
                            </span>
                          </td>
                          <td style={{ padding: '0.5rem 0.75rem' }}>
                            <MedalBadge medal={leaf.current_medal} size="small" />
                          </td>
                          <td style={{ padding: '0.5rem 0.75rem' }}>
                            {leaf.source?.repo && (
                              <a
                                href={`https://github.com/${leaf.source.repo}`}
                                target="_blank"
                                rel="noreferrer"
                                style={{ fontSize: '0.875rem', color: '#666' }}
                              >
                                {leaf.source.repo} ↗
                              </a>
                            )}
                          </td>
                        </tr>
                      ))}
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Standalone products section */}
        {standaloneLeaves.length > 0 && (
          <div className="p-card u-sv3">
            <h2 className="p-heading--4" style={{ marginBottom: '1rem' }}>Standalone Products</h2>
            <ul className="p-list" style={{ marginBottom: 0 }}>
              {standaloneLeaves.map(p => (
                <li key={p.id} className="p-list__item"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.4rem 0' }}>
                  <Link to={`/products/${p.id}`}>{p.name}</Link>
                  <span className="p-label--information" style={{ fontSize: '0.75rem' }}>
                    {p.product_type}
                  </span>
                  <MedalBadge medal={p.current_medal} size="small" />
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3.4: Run tests to confirm they pass**

```bash
cd ui && npm test -- --run ProductsExplorer
```

Expected: all 6 tests pass.

- [ ] **Step 3.5: Run full suite**

```bash
cd ui && npm test -- --run
```

Expected: all tests pass.

- [ ] **Step 3.6: Commit**

```bash
git add ui/src/views/ProductsExplorer.tsx ui/src/views/__tests__/ProductsExplorer.test.tsx
git commit -m "feat(ui): add ProductsExplorer page at /products"
```

---

## Task 4: Navigation and routing

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/components/GlobalNav.tsx`
- Modify: `ui/src/components/GlobalNav.test.tsx`

---

- [ ] **Step 4.1: Update GlobalNav test to assert Products link exists**

In `ui/src/components/GlobalNav.test.tsx`, update the test `'renders Portfolio and About nav links'` to also assert the Products link:

```tsx
  it('renders Portfolio, Products, and About nav links', () => {
    render(
      <HashRouter>
        <GlobalNav />
      </HashRouter>
    )
    expect(screen.getByRole('link', { name: 'Portfolio' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Products' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'About' })).toBeInTheDocument()
  })
```

(Replace the existing test of the same name — just rename it and add the `Products` assertion.)

- [ ] **Step 4.2: Run test to confirm it fails**

```bash
cd ui && npm test -- --run GlobalNav
```

Expected: `'renders Portfolio, Products, and About nav links'` fails because "Products" link doesn't exist yet.

- [ ] **Step 4.3: Add Products link to GlobalNav**

In `ui/src/components/GlobalNav.tsx`, add the Products nav item between the Portfolio and Dimensions items. The nav currently has: Portfolio → Dimensions → About → Docs ↗. Change it to: Portfolio → Products → Dimensions → About → Docs ↗.

Insert after the Portfolio `<li>` and before the Dimensions `<li>`:

```tsx
            <li className="p-navigation__item">
              <a 
                className={`p-navigation__link ${isActive('/products') ? 'is-selected' : ''}`}
                href="#/products"
              >
                Products
              </a>
            </li>
```

The `isActive('/products')` function already handles prefix matching correctly (returns true when `location.pathname.startsWith('/products')`).

- [ ] **Step 4.4: Add /products route to App.tsx**

In `ui/src/App.tsx`, add the lazy import and route for `ProductsExplorer`. Add the import after the existing lazy imports:

```tsx
const ProductsExplorer = lazy(() => import('./views/ProductsExplorer'))
```

Add the route after `<Route path="/" element={<Overview />} />`:

```tsx
<Route path="/products" element={<ProductsExplorer />} />
```

The existing `<Route path="/products/:id" element={<ProductDetail />} />` stays unchanged — React Router matches more-specific routes first.

- [ ] **Step 4.5: Run all tests**

```bash
cd ui && npm test -- --run
```

Expected: all tests pass including the updated GlobalNav test.

- [ ] **Step 4.6: Commit**

```bash
git add ui/src/App.tsx ui/src/components/GlobalNav.tsx ui/src/components/GlobalNav.test.tsx
git commit -m "feat(ui): add Products nav link and /products route"
```

---

## Task 5: Playwright visual verification

**Prereq:** Tasks 1–4 complete. The local dev server must be running.

- [ ] **Step 5.1: Start the dev server**

```bash
cd ui && npm run dev
```

Leave running. Open a new shell for the remaining steps.

- [ ] **Step 5.2: Open browser and verify root product page**

```bash
playwright-cli open
playwright-cli goto "http://localhost:5173/#/products/matrix"
playwright-cli snapshot
```

Check the snapshot for:
- "CURRENT" medal badge visible (not "COMPUTED MEDAL")
- "TARGET" medal badge visible
- "COMPONENTS" section with linked chips (e.g. "synapse-operator-charm" or similar)
- Dimensions table Evidence column shows metric names and values (e.g. "Coverage", "87 / 90")
- "Dependencies" card (not "Dependencies (context only)")

- [ ] **Step 5.3: Verify a leaf product page**

```bash
playwright-cli goto "http://localhost:5173/#/products/synapse-operator-charm"
playwright-cli snapshot
```

(Use an actual leaf product ID from the portfolio — check `public/portfolio.json` for `is_portfolio_entry: false` products.)

Check:
- "COMPUTED MEDAL" label shown (not "CURRENT")
- No "TARGET" medal visible
- "Part of:" chips visible linking to parent
- Evidence column shows metric values without `/ N` threshold denominators (no threshold coloring)

- [ ] **Step 5.4: Verify the Products explorer page**

```bash
playwright-cli goto "http://localhost:5173/#/products"
playwright-cli snapshot
```

Check:
- "Products" heading visible
- Root products listed with leaf rows indented below them
- Squad filter dropdown visible
- "Products" nav link is highlighted as active

- [ ] **Step 5.5: Take screenshots for the record**

```bash
playwright-cli screenshot --path /tmp/pqf-products-root-detail.png
playwright-cli goto "http://localhost:5173/#/products"
playwright-cli screenshot --path /tmp/pqf-products-explorer.png
playwright-cli close
```

- [ ] **Step 5.6: Commit final state**

```bash
git add -A
git commit -m "chore: verify UX evidence redesign via Playwright"
```

If there are no new files to add (previous commits covered everything), just push:

```bash
git push
```

---

## Self-Review

### Spec Coverage

| Spec section | Plan task |
|---|---|
| §1 RootMetricsList worst-value evidence display | Task 1 + Task 2 (Step 2.3 evidence column) |
| §2 Composed-of chips in header | Task 2 (Step 2.3 header section) |
| §3 Unified Dependencies card | Task 2 (Step 2.3 dependencies card) |
| §4 Leaf product pages (no target/drift) | Task 2 (Step 2.3: `isRoot` conditional on TARGET + DriftChip + `isRoot ? targetThresholds : undefined`) |
| §5 Products explorer page `/products` | Task 3 |
| §6 Navigation Products link | Task 4 |

### Type Consistency

- `RootMetricsList` accepts `thresholds: Record<string, { operator: string; value: number | boolean }>` — same shape as output of `parseCriteria` in `ProductDetail.tsx`. ✓
- `metaOutputs: Record<string, OutputMeta> | undefined` — matches `dimMeta?.outputs` call site. ✓
- `leaf.source?.repo` — `source` is `SourceRef | undefined` in `types.ts`; optional chaining used throughout. ✓
- `product.composed_of` is `ComposedRef[] | null` — all usages check for non-null before mapping. ✓

### No Placeholders

No TBD, TODO, or incomplete sections found.
