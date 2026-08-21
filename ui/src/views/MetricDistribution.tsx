import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import MedalBadge from '../components/MedalBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import { usePortfolio } from '../hooks/usePortfolio'
import {
  buildMetricDistributionRows,
  RESULT_ORDER,
  type MetricDistributionGroup,
  type MetricDistributionRow,
} from '../lib/groupedPortfolioView'
import type { Result, ProductType } from '../types'

function statusCell(status: 'pass' | 'fail' | 'na') {
  if (status === 'pass') return <span style={{ color: '#1d7a1d', fontWeight: 600 }}>✓</span>
  if (status === 'fail') return <span style={{ color: '#c7162b', fontWeight: 600 }}>✕</span>
  return <span style={{ color: '#888' }}>N/A</span>
}

function valueCell(value: string | number | boolean | undefined) {
  if (value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

function rowHasFailure(row: MetricDistributionRow) {
  return row.bronze === 'fail' || row.silver === 'fail' || row.gold === 'fail'
}

function groupByFilters(
  groups: MetricDistributionGroup[],
  squadFilter: string,
  medalFilter: 'all' | Result,
  typeFilter: 'all' | ProductType,
  failuresOnly: boolean,
) {
  const rowMatches = (row: MetricDistributionRow) => {
    if (squadFilter !== 'all' && row.product.squad !== squadFilter) return false
    if (medalFilter !== 'all' && row.entry.result !== medalFilter) return false
    if (typeFilter !== 'all' && row.product.product_type !== typeFilter) return false
    if (failuresOnly && !rowHasFailure(row)) return false
    return true
  }

  return groups.flatMap((group) => {
    const filteredLeaves = group.leaves.filter(rowMatches)
    const rootMatches = rowMatches(group.root)
    if (!rootMatches && filteredLeaves.length === 0) return []
    return [{
      root: group.root,
      leaves: filteredLeaves,
      rootVisible: rootMatches || filteredLeaves.length > 0,
    }]
  })
}

export default function MetricDistribution() {
  const { dimensionId, metricKey } = useParams<{ dimensionId: string; metricKey: string }>()
  const { data: portfolio, isLoading, isError, error } = usePortfolio()
  const [squadFilter, setSquadFilter] = useState('all')
  const [medalFilter, setMedalFilter] = useState<'all' | Result>('all')
  const [typeFilter, setTypeFilter] = useState<'all' | ProductType>('all')
  const [showFailuresOnly, setShowFailuresOnly] = useState(false)

  const groups = useMemo(
    () => (portfolio && dimensionId && metricKey
      ? buildMetricDistributionRows(portfolio, dimensionId, metricKey)
      : []),
    [portfolio, dimensionId, metricKey],
  )

  const squads = useMemo(() => {
    const items = new Set<string>()
    for (const group of groups) {
      if (group.root.product.squad) items.add(group.root.product.squad)
      for (const leaf of group.leaves) {
        if (leaf.product.squad) items.add(leaf.product.squad)
      }
    }
    return Array.from(items).sort()
  }, [groups])

  const filteredGroups = useMemo(
    () => groupByFilters(groups, squadFilter, medalFilter, typeFilter, showFailuresOnly),
    [groups, squadFilter, medalFilter, typeFilter, showFailuresOnly],
  )

  if (isLoading) return <LoadingSpinner />
  if (isError) return <div className="p-notification--negative"><p>{error?.message}</p></div>
  if (!portfolio || !dimensionId || !metricKey) return null

  const meta = portfolio.dimensions_meta[dimensionId]
  if (!meta || !meta.outputs || !meta.outputs[metricKey]) {
    return (
      <div className="row" style={{ paddingTop: '1.5rem' }}>
        <div className="col-12">
          <p>
            Metric <strong>{metricKey}</strong> in dimension <strong>{dimensionId}</strong> not found.
            {' '}
            <Link to={`/dimensions/${dimensionId}`}>Back to dimension</Link>
          </p>
        </div>
      </div>
    )
  }

  const flattenedCount = filteredGroups.reduce((count, group) => count + (group.rootVisible ? 1 : 0) + group.leaves.length, 0)
  const metricLabel = meta.outputs[metricKey].label ?? metricKey

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">
        <p style={{ marginBottom: '1rem' }}><Link to={`/dimensions/${dimensionId}`}>← {meta.label ?? dimensionId}</Link></p>
        <div className="p-card u-sv3">
          <h1 className="p-heading--3" style={{ marginBottom: '0.25rem' }}>Metric distribution</h1>
          <p className="u-text--muted" style={{ margin: 0 }}>
            {metricLabel} ({metricKey})
          </p>
        </div>

        <div className="p-card u-sv3">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '1rem' }}>
            <select value={squadFilter} onChange={e => setSquadFilter(e.target.value)} className="p-form__control" style={{ width: 'auto', marginBottom: 0 }}>
              <option value="all">All squads</option>
              {squads.map(squad => <option key={squad} value={squad}>{squad}</option>)}
            </select>
            <select value={medalFilter} onChange={e => setMedalFilter(e.target.value as 'all' | Result)} className="p-form__control" style={{ width: 'auto', marginBottom: 0 }}>
              <option value="all">All results</option>
              <option value="gold">Gold</option>
              <option value="silver">Silver</option>
              <option value="bronze">Bronze</option>
              <option value="below_minimum">Below min</option>
              <option value="insufficient_data">Insuff. data</option>
              <option value="not_applicable">N/A</option>
            </select>
            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value as 'all' | ProductType)} className="p-form__control" style={{ width: 'auto', marginBottom: 0 }}>
              <option value="all">All types</option>
              <option value="root">Root</option>
              <option value="charm">Charm</option>
              <option value="snap">Snap</option>
            </select>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', color: '#555' }}>
              <input type="checkbox" checked={showFailuresOnly} onChange={e => setShowFailuresOnly(e.target.checked)} />
              Show failures only
            </label>
            <span style={{ marginLeft: 'auto', fontSize: '0.8125rem', color: '#777' }}>
              {flattenedCount} row{flattenedCount === 1 ? '' : 's'}
            </span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #d9d9d9' }}>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Product</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Type</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Dimension medal</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Value</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Bronze</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Silver</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Gold</th>
                </tr>
              </thead>
              <tbody>
                {filteredGroups
                  .sort((a, b) => RESULT_ORDER[b.root.entry.result] - RESULT_ORDER[a.root.entry.result])
                  .flatMap(group => {
                    const rows = []
                    if (group.rootVisible) {
                      rows.push(
                        <tr key={group.root.product.id} style={{ borderBottom: '1px solid #e5e5e5', background: '#fafafa' }}>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                            <Link to={`/products/${group.root.product.id}`} style={{ fontWeight: 600 }}>{group.root.product.name}</Link>
                          </td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{group.root.product.product_type}</td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}><MedalBadge medal={group.root.entry.result} size="small" /></td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{valueCell(group.root.value)}</td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{statusCell(group.root.bronze)}</td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{statusCell(group.root.silver)}</td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{statusCell(group.root.gold)}</td>
                        </tr>,
                      )
                    }
                    for (const leaf of group.leaves) {
                      rows.push(
                        <tr key={leaf.product.id} style={{ borderBottom: '1px solid #e5e5e5', background: '#fff' }}>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                            <Link to={`/products/${leaf.product.id}`} style={{ fontWeight: 500 }}>
                              ↳ {leaf.product.name}
                            </Link>
                          </td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{leaf.product.product_type}</td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}><MedalBadge medal={leaf.entry.result} size="small" /></td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{valueCell(leaf.value)}</td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{statusCell(leaf.bronze)}</td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{statusCell(leaf.silver)}</td>
                          <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>{statusCell(leaf.gold)}</td>
                        </tr>,
                      )
                    }
                    return rows
                  })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
