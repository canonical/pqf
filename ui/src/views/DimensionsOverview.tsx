import { Link } from 'react-router'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import type { Result } from '../types'

const RESULT_ORDER_ARRAY: Result[] = ['gold', 'silver', 'bronze', 'below_minimum', 'insufficient_data', 'not_applicable']
const RESULT_COLOURS: Record<Result, string> = {
  gold: '#c9a227',
  silver: '#757575',
  bronze: '#a0522d',
  below_minimum: '#cc7700',
  insufficient_data: '#999999',
  not_applicable: '#cccccc',
}

export default function DimensionsOverview() {
  const { data: portfolio, isLoading, isError, error } = usePortfolio()

  if (isLoading) return <LoadingSpinner />
  if (isError) return <div className="p-notification--negative"><p>{error?.message}</p></div>
  if (!portfolio) return null

  const dimensions = Object.entries(portfolio.dimensions_meta)

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">

        <div className="p-card u-sv3">
          <h1 className="p-heading--3" style={{ marginBottom: '0.25rem' }}>Dimensions</h1>
          <p className="u-text--muted" style={{ margin: 0 }}>
            Each dimension measures a distinct aspect of product quality. Products are rated bronze, silver, or gold based on meeting the criteria defined in each dimension's rubric.
          </p>
        </div>

        <div className="p-card u-sv3">
          <table style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse' }}>
            <colgroup>
              <col style={{ width: '22%' }} />
              <col style={{ width: '38%' }} />
              <col style={{ width: '28%' }} />
              <col style={{ width: '12%' }} />
            </colgroup>
            <thead>
              <tr style={{ borderBottom: '1px solid #d9d9d9' }}>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Dimension</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Description</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Products</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Metrics</th>
              </tr>
            </thead>
            <tbody>
              {dimensions.map(([id, meta], idx) => {
               const medalCounts = RESULT_ORDER_ARRAY.reduce((acc, m) => {
                   acc[m] = portfolio.products.filter(p => p.dimensions[id]?.result === m).length
                   return acc
                 }, {} as Record<Result, number>)
                const totalProducts = portfolio.products.filter(p => p.dimensions[id]).length
                const metricCount = meta.outputs ? Object.keys(meta.outputs).length : 0

                return (
                  <tr key={id} style={{ borderBottom: '1px solid #e5e5e5', background: idx % 2 === 0 ? '#fafafa' : '#fff' }}>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                      <Link to={`/dimensions/${id}`} style={{ fontWeight: 600, display: 'block' }}>
                        {meta.label ?? id.replace(/_/g, ' ')}
                      </Link>
                      <code style={{ fontSize: '0.75rem', color: '#888' }}>{id}</code>
                    </td>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top', fontSize: '0.875rem', color: '#333' }}>
                      {meta.description ?? '—'}
                    </td>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                      {totalProducts > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                            {RESULT_ORDER_ARRAY.filter(m => medalCounts[m] > 0).map(m => (
                              <span key={m} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                                <MedalBadge medal={m} size="small" />
                                <span style={{ fontSize: '0.8125rem', color: RESULT_COLOURS[m], fontWeight: 600 }}>
                                  {medalCounts[m]}
                                </span>
                              </span>
                            ))}
                          </div>
                          <span style={{ fontSize: '0.75rem', color: '#888' }}>{totalProducts} product{totalProducts !== 1 ? 's' : ''}</span>
                        </div>
                      ) : (
                        <span style={{ fontSize: '0.875rem', color: '#aaa' }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                      {metricCount > 0 ? (
                        <span style={{ fontSize: '0.875rem', color: '#333' }}>
                          {metricCount} metric{metricCount !== 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.875rem', color: '#aaa' }}>—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <p className="u-sv2">
          <Link to="/about">Learn more about the framework →</Link>
        </p>

      </div>
    </div>
  )
}
