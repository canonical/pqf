# Table Column Spacing Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebalance the Product detail dependency rows and the Products explorer table so Product and Repo get the most useful space while Type, Medal, Target, and Squad stay compact.

**Architecture:** Keep the existing structures: `ProductDetail` dependency rows remain CSS grid rows, and `ProductsExplorer` remains a semantic HTML table. Add explicit width allocation to both surfaces, preserve ellipsis/min-width safety on long text, and lock the behavior in with focused Vitest + React Testing Library assertions.

**Tech Stack:** React 19, TypeScript strict, `react-router`, `@tanstack/react-query`, Vitest, React Testing Library, Vite.

## Global Constraints

- Keep the current semantics: detail page dependency rows stay CSS grid; products page stays an HTML table.
- Priority columns: Product and Repo get the most width.
- Compact columns: Type, Target, Squad stay intentionally small and stable.
- Long Product/Repo content truncates with ellipsis instead of distorting layout.
- Do not redesign either surface or change which columns exist.
- Use explicit width allocation instead of mostly content-driven sizing.
- `@canonical/react-components` (Vanilla Framework) only — no Tailwind, no shadcn, no custom CSS frameworks.
- TypeScript strict mode. No `any` except in test mocks typed as `ReturnType<typeof usePortfolio>`.
- Tests live in `ui/src/views/__tests__/`.
- Validate with `make test-ui` and `make build`.

---

## File Map

| Path | Action | Responsibility |
|------|--------|----------------|
| `ui/src/views/ProductDetail.tsx` | Modify | Rebalance dependency-row grid so Product is primary but bounded and Repo gets a guaranteed useful width |
| `ui/src/views/__tests__/ProductDetail.test.tsx` | Modify | Lock the dependency-row width strategy and overflow-safe styles |
| `ui/src/views/ProductsExplorer.tsx` | Modify | Add explicit table column sizing plus overflow-safe Product/Repo cells for grouped and flat rows |
| `ui/src/views/__tests__/ProductsExplorer.test.tsx` | Modify | Assert the table width strategy and compact metadata columns |

---

## Task 1: Rebalance Product detail dependency rows

**Files:**
- Modify: `ui/src/views/ProductDetail.tsx`
- Modify: `ui/src/views/__tests__/ProductDetail.test.tsx`

**Interfaces:**
- Consumes: `product.composed_of`, `portfolio.products`, `leaf.source.repo`, existing dependency-row markup inside `ProductDetail`.
- Produces: dependency rows with grid template `auto minmax(0, 1.1fr) auto minmax(14rem, 0.9fr)` (or the exact agreed equivalent), Product and Repo cells that ellipsize safely, and a regression test proving those styles.

---

- [ ] **Step 1.1: Write the failing test**

Update `ui/src/views/__tests__/ProductDetail.test.tsx` by tightening the dependency-row expectations:

```tsx
  it('balances dependency row widths toward product and repo content', () => {
    wrap('matrix')

    const productLink = screen.getByRole('link', { name: 'Synapse Charm' })
    const repoLink = screen.getByRole('link', { name: /canonical\/synapse-operator/i })
    const row = productLink.parentElement?.parentElement

    expect(row).not.toBeNull()
    expect(row).toHaveStyle({
      display: 'grid',
      gridTemplateColumns: 'auto minmax(0, 1.1fr) auto minmax(14rem, 0.9fr)',
    })

    expect(productLink.parentElement).toHaveStyle({ minWidth: '0' })
    expect(repoLink.parentElement).toHaveStyle({ minWidth: '0' })
    expect(repoLink).toHaveStyle({
      display: 'block',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    })
  })
```

- [ ] **Step 1.2: Run the test to verify it fails**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/ProductDetail.test.tsx -t "balances dependency row widths toward product and repo content"
```

Expected: FAIL because `gridTemplateColumns` still uses the old dependency-row sizing.

- [ ] **Step 1.3: Update the dependency row implementation**

Modify the dependency row block in `ui/src/views/ProductDetail.tsx`:

```tsx
                      <div
                        key={c.product_id}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'auto minmax(0, 1.1fr) auto minmax(14rem, 0.9fr)',
                          alignItems: 'center',
                          gap: '0.75rem',
                        }}
                      >
                        {leaf?.current_medal ? (
                          <MedalBadge medal={leaf.current_medal} size="small" />
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: '#999', textAlign: 'center', width: '24px' }}>—</span>
                        )}
                        <div style={{ minWidth: 0 }}>
                          <Link
                            to={`/products/${c.product_id}`}
                            style={{
                              fontWeight: 500,
                              display: 'block',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {leaf?.name ?? c.product_id}
                          </Link>
                        </div>
                        {leaf?.product_type ? (
                          <div style={{ minWidth: 0 }}>
                            <span className="p-label--information" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                              {leaf.product_type}
                            </span>
                          </div>
                        ) : <span />}
                        {leaf?.source?.repo ? (
                          <div style={{ minWidth: 0 }}>
                            <a
                              href={`https://github.com/${leaf.source.repo}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                display: 'block',
                                fontSize: '0.8rem',
                                color: '#666',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {leaf.source.repo} ↗
                            </a>
                          </div>
                        ) : <span />}
                      </div>
```

- [ ] **Step 1.4: Run the targeted test to verify it passes**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/ProductDetail.test.tsx -t "balances dependency row widths toward product and repo content"
```

Expected: PASS.

- [ ] **Step 1.5: Run the full ProductDetail test file**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/ProductDetail.test.tsx
```

Expected: PASS with all `ProductDetail` tests green.

- [ ] **Step 1.6: Commit**

```bash
git add ui/src/views/ProductDetail.tsx ui/src/views/__tests__/ProductDetail.test.tsx
git commit -m "fix: rebalance dependency row column widths"
```

---

## Task 2: Rebalance the Products explorer table columns

**Files:**
- Modify: `ui/src/views/ProductsExplorer.tsx`
- Modify: `ui/src/views/__tests__/ProductsExplorer.test.tsx`

**Interfaces:**
- Consumes: existing grouped and flat table rendering in `ProductsExplorer`, `Product` data shape, `SQUAD_LABELS`, existing tree-connector markup for leaf rows.
- Produces: a semantic table with explicit `<colgroup>` sizing, compact metadata columns, wider Product/Repo columns, ellipsized Product/Repo cell content, and tests that assert the sizing hooks.

---

- [ ] **Step 2.1: Write the failing tests**

Add to `ui/src/views/__tests__/ProductsExplorer.test.tsx`:

```tsx
  it('uses explicit column sizing to prioritize product and repo columns', () => {
    const { container } = wrap()

    const cols = container.querySelectorAll('col')
    expect(cols).toHaveLength(6)
    expect(cols[0]).toHaveStyle({ width: '36%' })
    expect(cols[1]).toHaveStyle({ width: '7rem' })
    expect(cols[2]).toHaveStyle({ width: '7rem' })
    expect(cols[3]).toHaveStyle({ width: '7rem' })
    expect(cols[4]).toHaveStyle({ width: '6rem' })
    expect(cols[5]).toHaveStyle({ width: '26%' })
  })

  it('keeps product and repo cells overflow-safe in grouped rows', () => {
    wrap()

    const rootLink = screen.getByRole('link', { name: 'Matrix (Synapse)' })
    const leafRepoLink = screen.getByRole('link', { name: /canonical\/synapse-operator/i })

    expect(rootLink.parentElement).toHaveStyle({ minWidth: '0' })
    expect(rootLink).toHaveStyle({
      display: 'block',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    })

    expect(leafRepoLink.parentElement).toHaveStyle({ minWidth: '0' })
    expect(leafRepoLink).toHaveStyle({
      display: 'block',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    })
  })
```

- [ ] **Step 2.2: Run the tests to verify they fail**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/ProductsExplorer.test.tsx -t "uses explicit column sizing|keeps product and repo cells overflow-safe in grouped rows"
```

Expected: FAIL because the table does not yet render a `<colgroup>` or overflow-safe Product/Repo wrappers.

- [ ] **Step 2.3: Add explicit column sizing to the table**

Modify the table in `ui/src/views/ProductsExplorer.tsx`:

```tsx
            <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
              <colgroup>
                <col style={{ width: '36%' }} />
                <col style={{ width: '7rem' }} />
                <col style={{ width: '7rem' }} />
                <col style={{ width: '7rem' }} />
                <col style={{ width: '6rem' }} />
                <col style={{ width: '26%' }} />
              </colgroup>
              <thead>
```

Keep the remaining width for table padding and browser rounding. Do not add or remove any columns.

- [ ] **Step 2.4: Make grouped-row Product and Repo cells shrink-safe**

Update the grouped root/leaf row cells in `ui/src/views/ProductsExplorer.tsx`:

```tsx
                        <td style={{ padding: '0.65rem 0.75rem', minWidth: 0 }}>
                          <Link
                            to={`/products/${root.id}`}
                            style={{
                              display: 'block',
                              fontWeight: 600,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {root.name}
                          </Link>
                        </td>
```

```tsx
                            <td style={{ padding: '0.45rem 0.75rem', minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
                                <div
                                  style={{
                                    width: '1.25rem',
                                    flexShrink: 0,
                                    alignSelf: 'stretch',
                                    position: 'relative',
                                    marginRight: '0.35rem',
                                  }}
                                >
                                  {/* existing connector spans unchanged */}
                                </div>
                                <Link
                                  to={`/products/${leaf.id}`}
                                  style={{
                                    display: 'block',
                                    minWidth: 0,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    fontSize: '0.875rem',
                                  }}
                                >
                                  {leaf.name}
                                </Link>
                              </div>
                            </td>
```

```tsx
                            <td style={{ padding: '0.45rem 0.75rem', minWidth: 0 }}>
                              {leaf.source?.repo ? (
                                <a
                                  href={`https://github.com/${leaf.source.repo}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{
                                    display: 'block',
                                    fontSize: '0.8125rem',
                                    color: '#555',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {leaf.source.repo} ↗
                                </a>
                              ) : (
                                <span style={{ color: '#ccc', fontSize: '0.875rem' }}>—</span>
                              )}
                            </td>
```

Keep Type, Medal, Target, and Squad cells as compact nowrap metadata cells. If needed, add `whiteSpace: 'nowrap'` to those compact cells rather than widening them.

- [ ] **Step 2.5: Make flat-row Product and Repo cells shrink-safe**

Update the flat rows in `ui/src/views/ProductsExplorer.tsx`:

```tsx
                    <td style={{ padding: '0.6rem 0.75rem', minWidth: 0 }}>
                      <Link
                        to={`/products/${p.id}`}
                        style={{
                          display: 'block',
                          fontWeight: p.product_type === 'root' ? 600 : 400,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {p.name}
                      </Link>
                    </td>
```

```tsx
                    <td style={{ padding: '0.6rem 0.75rem', minWidth: 0 }}>
                      {p.source?.repo ? (
                        <a
                          href={`https://github.com/${p.source.repo}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            display: 'block',
                            fontSize: '0.8125rem',
                            color: '#555',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {p.source.repo} ↗
                        </a>
                      ) : (
                        <span style={{ color: '#ccc', fontSize: '0.875rem' }}>—</span>
                      )}
                    </td>
```

- [ ] **Step 2.6: Run the targeted tests to verify they pass**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/ProductsExplorer.test.tsx -t "uses explicit column sizing|keeps product and repo cells overflow-safe in grouped rows"
```

Expected: PASS.

- [ ] **Step 2.7: Run the full ProductsExplorer test file**

Run:

```bash
cd ui && npm test -- --run src/views/__tests__/ProductsExplorer.test.tsx
```

Expected: PASS with all `ProductsExplorer` tests green.

- [ ] **Step 2.8: Run full UI verification**

Run:

```bash
make test-ui
make build
```

Expected:

- `make test-ui` passes all Vitest suites
- `make build` completes successfully with the usual existing Sass deprecation warnings only

- [ ] **Step 2.9: Commit**

```bash
git add ui/src/views/ProductsExplorer.tsx ui/src/views/__tests__/ProductsExplorer.test.tsx
git commit -m "fix: rebalance products table column widths"
```

---

## Self-Review

- **Spec coverage:** Task 1 covers the dependency-row rebalance and overflow rules. Task 2 covers the Products page explicit column sizing, compact metadata columns, wider Product/Repo allocation, and validation.
- **Placeholder scan:** No `TODO`, `TBD`, “appropriate handling”, or “similar to Task N” references remain.
- **Type consistency:** All referenced files and symbols already exist in the codebase; the plan only modifies view/test files and does not invent new shared types or APIs.

