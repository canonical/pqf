import { useState, useMemo, Fragment } from 'react'
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

const MEDAL_OPTIONS = ['all', 'bronze', 'silver', 'gold', 'below_minimum', 'insufficient_data', 'not_applicable']
const MEDAL_LABELS: Record<string, string> = {
  all: 'All results',
  bronze: 'Bronze',
  silver: 'Silver',
  gold: 'Gold',
  below_minimum: 'Below Minimum',
  insufficient_data: 'Insufficient Data',
  not_applicable: 'Not Applicable',
}

export default function ProductsExplorer() {
  const { data: portfolio, isLoading, isError, error } = usePortfolio()

  const [search, setSearch] = useState('')
  const [squadFilter, setSquadFilter] = useState('all')
  const [medalFilter, setMedalFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [groupByParent, setGroupByParent] = useState(true)

  const { rootProducts, allProducts, squads, productTypes } = useMemo(() => {
    if (!portfolio) return { rootProducts: [], allProducts: [], squads: [] as string[], productTypes: [] as string[] }

    const roots = portfolio.products.filter(p => p.product_type === 'root')
    const squads = [...new Set(roots.map(p => p.squad).filter(Boolean))]
    const productTypes = [...new Set(portfolio.products.map(p => p.product_type).filter(Boolean))]

    return { rootProducts: roots, allProducts: portfolio.products, squads, productTypes }
  }, [portfolio])

  const filteredData = useMemo(() => {
    if (!portfolio) return { type: 'grouped' as const, groups: [] }

    const q = search.trim().toLowerCase()
    const matchesSearch = (p: Product) =>
      !q || p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)
    const matchesMedal = (p: Product) =>
      medalFilter === 'all' || p.current_result === medalFilter
    const matchesType = (p: Product) =>
      typeFilter === 'all' || p.product_type === typeFilter
    const matchesSquad = (p: Product) =>
      squadFilter === 'all' || p.squad === squadFilter

    if (!groupByParent) {
      const flat = allProducts
        .filter(p => matchesSearch(p) && matchesMedal(p) && matchesType(p))
        .sort((a, b) => a.name.localeCompare(b.name))
      return { type: 'flat' as const, products: flat }
    }

    const groups = rootProducts
      .filter(root => matchesSquad(root))
      .flatMap(root => {
        const leafProducts = (root.composed_of ?? [])
          .map(c => portfolio.products.find(p => p.id === c.product_id))
          .filter((p): p is Product => p !== undefined)

        const rootMatches = matchesSearch(root) && matchesMedal(root) && matchesType(root)
        const matchingLeaves = leafProducts.filter(
          l => matchesSearch(l) && matchesMedal(l) && matchesType(l),
        )

        if (rootMatches) return [{ root, leaves: leafProducts }]
        if (matchingLeaves.length > 0) return [{ root, leaves: matchingLeaves }]
        return []
      })

    return { type: 'grouped' as const, groups }
  }, [search, squadFilter, medalFilter, typeFilter, groupByParent, rootProducts, allProducts, portfolio])

  if (isLoading) return <LoadingSpinner />
  if (isError) return <div className="p-notification--negative"><p>{error?.message}</p></div>
  if (!portfolio) return null

  const TH: React.CSSProperties = {
    padding: '0.5rem 0.75rem',
    textAlign: 'left',
    fontSize: '0.75rem',
    fontWeight: 600,
    textTransform: 'uppercase',
    color: '#666',
    borderBottom: '2px solid #d9d9d9',
  }

  const hasActiveFilter = search || squadFilter !== 'all' || medalFilter !== 'all' || typeFilter !== 'all'
  const resultCount = filteredData.type === 'flat'
    ? filteredData.products.length
    : filteredData.groups.reduce((n, g) => n + 1 + g.leaves.length, 0)

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">
        <h1 className="p-heading--3" style={{ marginBottom: '1rem' }}>Products</h1>

        {/* Filter bar */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center' }}>
          {/* Search — grid overlay: SVG and input share the same cell */}
          <div style={{ display: 'grid', alignItems: 'center', flexGrow: 1, minWidth: '200px', maxWidth: '360px' }}>
            <svg
              style={{ gridArea: '1 / 1', justifySelf: 'start', marginLeft: '0.6rem', zIndex: 1, pointerEvents: 'none' }}
              xmlns="http://www.w3.org/2000/svg"
              width="14" height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#999"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search products…"
              aria-label="Search products"
              className="p-form__control"
              style={{ gridArea: '1 / 1', paddingLeft: '2rem', width: '100%', marginBottom: 0 }}
            />
          </div>

          {/* Medal filter */}
          <select
            value={medalFilter}
            onChange={e => setMedalFilter(e.target.value)}
            className="p-form__control"
            style={{ width: 'auto', marginBottom: 0 }}
            aria-label="Filter by medal"
          >
            {MEDAL_OPTIONS.map(m => (
              <option key={m} value={m}>{MEDAL_LABELS[m]}</option>
            ))}
          </select>

          {/* Type filter */}
          {productTypes.length > 1 && (
            <select
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
              className="p-form__control"
              style={{ width: 'auto', marginBottom: 0 }}
              aria-label="Filter by type"
            >
              <option value="all">All types</option>
              {productTypes.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          )}

          {/* Squad filter */}
          <select
            value={squadFilter}
            onChange={e => setSquadFilter(e.target.value)}
            className="p-form__control"
            style={{ width: 'auto', marginBottom: 0 }}
            aria-label="Filter by squad"
          >
            <option value="all">All squads</option>
            {squads.map(s => (
              <option key={s} value={s}>
                {SQUAD_LABELS[s.toLowerCase()] ?? s}
              </option>
            ))}
          </select>

          {/* Group by parent toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.875rem', color: '#555', userSelect: 'none', marginLeft: '0.25rem' }}>
            <input
              type="checkbox"
              checked={groupByParent}
              onChange={e => setGroupByParent(e.target.checked)}
              style={{ cursor: 'pointer' }}
            />
            Group by parent
          </label>

          {/* Result count hint when filtered */}
          {hasActiveFilter && (
            <span style={{ fontSize: '0.8125rem', color: '#888', marginLeft: 'auto' }}>
              {resultCount} result{resultCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Products table */}
        <div className="p-card u-sv3" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
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
                <tr style={{ background: '#f5f5f5' }}>
                  <th style={TH}>Product</th>
                  <th style={TH}>Type</th>
                  <th style={TH}>Medal</th>
                  <th style={TH}>Target</th>
                  <th style={TH}>Squad</th>
                  <th style={TH}>Repo</th>
                </tr>
              </thead>
              <tbody>
                {filteredData.type === 'grouped' && filteredData.groups.map((group, groupIdx) => {
                  const { root, leaves } = group
                  const isLastGroup = groupIdx === filteredData.groups.length - 1
                  return (
                    <Fragment key={root.id}>
                      {/* Root row */}
                      <tr style={{
                        borderTop: groupIdx > 0 ? '2px solid #e5e5e5' : undefined,
                        borderBottom: leaves.length === 0 ? '1px solid #e5e5e5' : 'none',
                        background: '#fafafa',
                      }}>
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
                        <td style={{ padding: '0.65rem 0.75rem', whiteSpace: 'nowrap' }}>
                          <span className="p-label" style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                            {root.product_type}
                          </span>
                        </td>
                        <td style={{ padding: '0.65rem 0.75rem', whiteSpace: 'nowrap' }}>
                          <MedalBadge medal={root.current_result as any} size="small" />
                        </td>
                        <td style={{ padding: '0.65rem 0.75rem', whiteSpace: 'nowrap' }}>
                          <MedalBadge medal={root.target_result} size="small" />
                        </td>
                        <td style={{ padding: '0.65rem 0.75rem', whiteSpace: 'nowrap', fontSize: '0.875rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#555' }}>
                          {SQUAD_LABELS[root.squad?.toLowerCase()] ?? root.squad}
                        </td>
                        <td style={{ padding: '0.65rem 0.75rem', minWidth: 0, fontSize: '0.875rem', color: '#aaa' }}>—</td>
                      </tr>

                      {/* Leaf rows with tree connector */}
                      {leaves.map((leaf, leafIdx) => {
                        const isLast = leafIdx === leaves.length - 1
                        return (
                          <tr
                            key={leaf.id}
                            style={{
                              borderBottom: isLast && !isLastGroup ? '1px solid #e5e5e5' : '1px solid #f0f0f0',
                              background: '#fff',
                            }}
                          >
                            {/* Product name cell with tree connector — flex layout avoids absolute-positioning coordinate issues */}
                            <td style={{ padding: '0.45rem 0.75rem', minWidth: 0 }}>
                             <div style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
                               {/* Tree connector: fixed-width column, stretches full cell height */}
                               <div style={{
                                 width: '1.25rem',
                                 flexShrink: 0,
                                 alignSelf: 'stretch',
                                 position: 'relative',
                                 marginRight: '0.35rem',
                               }}>
                                 {/* Vertical line: runs from top to midpoint (last child) or full height (others) */}
                                 <span style={{
                                   position: 'absolute',
                                   left: '0.5rem',
                                   top: 0,
                                   bottom: isLast ? '50%' : 0,
                                   width: '1px',
                                   background: '#c8d3e0',
                                   pointerEvents: 'none',
                                 }} />
                                 {/* Horizontal tick */}
                                 <span style={{
                                   position: 'absolute',
                                   left: '0.5rem',
                                   top: '50%',
                                   width: '0.6rem',
                                   height: '1px',
                                   background: '#c8d3e0',
                                   pointerEvents: 'none',
                                 }} />
                               </div>
                               <Link
                                 to={`/products/${leaf.id}`}
                                 style={{ display: 'block', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.875rem' }}
                               >
                                 {leaf.name}
                               </Link>
                             </div>
                            </td>
                            <td style={{ padding: '0.45rem 0.75rem', whiteSpace: 'nowrap' }}>
                             <span className="p-label--information" style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                                {leaf.product_type}
                              </span>
                            </td>
                            <td style={{ padding: '0.45rem 0.75rem', whiteSpace: 'nowrap' }}>
                              <MedalBadge medal={leaf.current_result as any} size="small" />
                            </td>
                            <td style={{ padding: '0.45rem 0.75rem', whiteSpace: 'nowrap', color: '#ccc', fontSize: '0.875rem' }}>—</td>
                            <td style={{ padding: '0.45rem 0.75rem', whiteSpace: 'nowrap', color: '#ccc', fontSize: '0.875rem' }}>—</td>
                            <td style={{ padding: '0.45rem 0.75rem', minWidth: 0 }}>
                              {leaf.source?.repo ? (
                                <a
                                  href={`https://github.com/${leaf.source.repo}`}
                                  target="_blank"
                                  rel="noreferrer"
                                 style={{ display: 'block', fontSize: '0.8125rem', color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                >
                                  {leaf.source.repo} ↗
                                </a>
                              ) : (
                                <span style={{ color: '#ccc', fontSize: '0.875rem' }}>—</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </Fragment>
                  )
                })}

                {filteredData.type === 'flat' && filteredData.products.map(p => (
                  <tr key={p.id} style={{ borderBottom: '1px solid #e5e5e5' }}>
                    <td style={{ padding: '0.6rem 0.75rem', minWidth: 0 }}>
                      <Link
                        to={`/products/${p.id}`}
                        style={{ display: 'block', fontWeight: p.product_type === 'root' ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      >
                        {p.name}
                      </Link>
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', whiteSpace: 'nowrap' }}>
                      <span
                        className={p.product_type === 'root' ? 'p-label' : 'p-label--information'}
                        style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}
                      >
                        {p.product_type}
                      </span>
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', whiteSpace: 'nowrap' }}>
                      <MedalBadge medal={p.current_result as any} size="small" />
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', whiteSpace: 'nowrap' }}>
                      {p.target_result ? <MedalBadge medal={p.target_result} size="small" /> : <span style={{ color: '#ccc' }}>—</span>}
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', whiteSpace: 'nowrap', fontSize: '0.875rem', fontWeight: p.squad ? 600 : 400, textTransform: p.squad ? 'uppercase' : undefined, letterSpacing: p.squad ? '0.04em' : undefined, color: p.squad ? '#555' : '#ccc' }}>
                      {p.squad ? (SQUAD_LABELS[p.squad.toLowerCase()] ?? p.squad) : '—'}
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', minWidth: 0 }}>
                      {p.source?.repo ? (
                        <a
                          href={`https://github.com/${p.source.repo}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ display: 'block', fontSize: '0.8125rem', color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                          {p.source.repo} ↗
                        </a>
                      ) : (
                        <span style={{ color: '#ccc', fontSize: '0.875rem' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}

                {/* Empty state */}
                {((filteredData.type === 'grouped' && filteredData.groups.length === 0) ||
                  (filteredData.type === 'flat' && filteredData.products.length === 0)) && (
                  <tr>
                    <td colSpan={6} style={{ padding: '2rem', textAlign: 'center', color: '#888', fontSize: '0.875rem' }}>
                      No products match your filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
