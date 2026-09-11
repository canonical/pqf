import { useState, useMemo } from 'react'
import VersionLink from '../components/VersionLink'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import ComplianceStatus from '../components/ComplianceStatus'
import LoadingSpinner from '../components/LoadingSpinner'
import { RESULT_ORDER } from '../lib/groupedPortfolioView'

const SQUAD_LABELS: Record<string, string> = {
  americas: 'AMER',
  emea: 'EMEA',
  apac: 'APAC',
}

type SortField = 'name' | 'current_result' | 'target_result'

function squadLabel(squad: string): string {
  return SQUAD_LABELS[squad?.toLowerCase()] ?? squad?.toUpperCase() ?? '—'
}

export default function Overview() {
  const { data: portfolio, isLoading, isError, error } = usePortfolio()
  const [search, setSearch] = useState('')
  const [sortField, setSortField] = useState<SortField>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const products = useMemo(() => {
    if (!portfolio) return []
    const filtered = portfolio.products
      .filter(p => p.is_portfolio_entry)
      .filter(p =>
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.squad.toLowerCase().includes(search.toLowerCase())
      )
    return [...filtered].sort((a, b) => {
      let cmp = 0
      if (sortField === 'name') cmp = a.name.localeCompare(b.name)
      else if (sortField === 'current_result')
        cmp = RESULT_ORDER[a.current_result] - RESULT_ORDER[b.current_result]
      else if (sortField === 'target_result')
        cmp = RESULT_ORDER[a.target_result] - RESULT_ORDER[b.target_result]
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [portfolio, search, sortField, sortDir])

  if (isLoading) return <LoadingSpinner />
  if (isError) return <div className="p-notification--negative"><p>{error?.message}</p></div>
  if (!portfolio) return null

  const compliance = portfolio.compliance_summary

  const dimensions = Object.keys(portfolio.dimensions_meta)

  function toggleSort(field: SortField) {
    if (sortField === field) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortField(field); setSortDir('asc') }
  }

  function getAriaSort(field: SortField): "none" | "ascending" | "descending" {
    if (sortField !== field) return 'none'
    return sortDir === 'asc' ? 'ascending' : 'descending'
  }

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">
        <h1 className="p-heading--2">Products overview</h1>

        {/* Summary stats */}
        <div className="row u-sv3">
          <div className="col-4">
            <div className="p-card">
              <p style={{ fontSize: '2.5rem', fontWeight: 700, margin: '0 0 0.25rem', lineHeight: 1,
                color: compliance.meeting_target === compliance.total && compliance.total > 0 ? '#2d9e46' : compliance.meeting_target === 0 ? '#c7162b' : '#1d7a1d' }}>
                {compliance.meeting_target} / {compliance.total}
              </p>
              <p className="u-text--muted" style={{ margin: 0 }}>Meeting target</p>
            </div>
          </div>
          <div className="col-4">
            <div className="p-card">
              <p style={{ fontSize: '2.5rem', fontWeight: 700, margin: '0 0 0.25rem', lineHeight: 1,
                color: compliance.below_target > 0 ? '#c7162b' : '#333' }}>
                {compliance.below_target}
              </p>
              <p className="u-text--muted" style={{ margin: 0 }}>Below target</p>
            </div>
          </div>
          <div className="col-4">
            <div className="p-card">
              <p style={{ fontSize: '2.5rem', fontWeight: 700, margin: '0 0 0.25rem', lineHeight: 1,
                color: compliance.insufficient_data > 0 ? '#E98B06' : '#333' }}>
                {compliance.insufficient_data}
              </p>
              <p className="u-text--muted" style={{ margin: 0 }}>Insufficient data</p>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="u-sv2">
          <input
            type="search"
            className="p-form__input"
            placeholder="Filter by product or squad…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search products"
          />
        </div>

        {/* Product table */}
        <div className="p-card u-sv3">
          <h2 className="p-heading--4">Products</h2>
          <table className="p-table--sortable">
            <thead>
              <tr>
                <th
                  aria-sort={getAriaSort('name')}
                  onClick={() => toggleSort('name')}
                  style={{ cursor: 'pointer', width: '30%' }}
                >
                  Product
                </th>
                <th style={{ width: '10%' }}>Squad</th>
                <th
                  aria-sort={getAriaSort('target_result')}
                  onClick={() => toggleSort('target_result')}
                  style={{ cursor: 'pointer', width: '15%' }}
                >
                  Target
                </th>
                <th
                  aria-sort={getAriaSort('current_result')}
                  onClick={() => toggleSort('current_result')}
                  style={{ cursor: 'pointer', width: '15%' }}
                >
                  Current
                </th>
                <th style={{ width: '20%' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {products.map(product => (
                <tr key={product.id}>
                  <td>
                    <VersionLink to={`/products/${product.id}`}>{product.name}</VersionLink>
                  </td>
                  <td>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: '#666',
                      }}
                    >
                      {squadLabel(product.squad)}
                    </span>
                  </td>
                  <td><MedalBadge medal={product.target_result} size="small" /></td>
                  <td><MedalBadge medal={product.current_result} size="small" /></td>
                  <td><ComplianceStatus meetsTarget={product.meets_target} size="small" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Heatmap */}
        <div className="p-card u-sv3">
          <h2 className="p-heading--4">Compliance heatmap</h2>
          <div style={{ overflowX: 'auto' }}>
            <table className="p-table--sortable" style={{ tableLayout: 'fixed', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ width: '20%' }}>Product</th>
                  {dimensions.map(dim => (
                    <th key={dim} style={{ width: `${80 / dimensions.length}%` }}>
                      <VersionLink to={`/dimensions/${dim}`}>
                        {portfolio.dimensions_meta[dim]?.label ?? dim.replace(/_/g, ' ')}
                      </VersionLink>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {products.map(product => (
                  <tr key={product.id}>
                    <td style={{ width: '20%' }}>
                      <VersionLink to={`/products/${product.id}`}>{product.name}</VersionLink>
                    </td>
                    {dimensions.map(dim => {
                      const d = product.dimensions[dim]
                      return (
                        <td key={dim}>
                          {d ? <MedalBadge medal={d.result as any} size="small" /> : <span>—</span>}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <p className="u-text--muted u-sv1">
          <small>Data generated at {new Date(portfolio.generated_at).toLocaleString()}</small>
        </p>
        <p>
          <VersionLink to="/about" className="p-button--neutral">
            About this framework
          </VersionLink>
        </p>
      </div>
    </div>
  )
}
