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
                    <Fragment key={root.id}>
                      <tr style={{ borderBottom: '1px solid #e5e5e5', background: '#fafafa' }}>
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
                    </Fragment>
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
