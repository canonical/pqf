import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import MedalBadge from '../components/MedalBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import { usePortfolio } from '../hooks/usePortfolio'
import {
  buildMetricDistributionRows,
  computeGapToTarget,
  RESULT_ORDER,
  type MetricDistributionGroup,
  type MetricDistributionRow,
  type MetricValue,
} from '../lib/groupedPortfolioView'
import type { DimensionMeta, Medal, MetricDefinition, ProductType, Result } from '../types'

interface DistributionCounts {
  gold: number
  silver: number
  bronze: number
  below_minimum: number
  no_data: number
}

function valueCell(value: MetricValue) {
  if (value === undefined || value === null) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

function metricStatus(row: MetricDistributionRow): Result {
  if (row.value === undefined || row.value === null) return 'insufficient_data'
  if (row.gold === 'pass') return 'gold'
  if (row.silver === 'pass') return 'silver'
  if (row.bronze === 'pass') return 'bronze'
  if (row.bronze === 'fail' || row.silver === 'fail' || row.gold === 'fail') return 'below_minimum'
  return 'insufficient_data'
}

function computeDistribution(groups: MetricDistributionGroup[]): DistributionCounts {
  const counts: DistributionCounts = {
    gold: 0,
    silver: 0,
    bronze: 0,
    below_minimum: 0,
    no_data: 0,
  }

  for (const group of groups) {
    for (const row of [group.root, ...group.leaves]) {
      const result = metricStatus(row)
      if (result === 'gold') {
        counts.gold += 1
      } else if (result === 'silver') {
        counts.silver += 1
      } else if (result === 'bronze') {
        counts.bronze += 1
      } else if (result === 'insufficient_data' || result === 'not_applicable') {
        counts.no_data += 1
      } else {
        counts.below_minimum += 1
      }
    }
  }

  return counts
}

function formatCriterion(criterion: string): string {
  return criterion
    .replace(/\s*>=\s*/g, ' ≥ ')
    .replace(/\s*<=\s*/g, ' ≤ ')
    .replace(/\s*==\s*/g, ' = ')
    .replace(/\s*>\s*/g, ' > ')
    .replace(/\s*<\s*/g, ' < ')
}

function thresholdSummary(criteria: string[]) {
  return criteria.length > 0 ? criteria.map(formatCriterion).join(' · ') : 'No criteria'
}

function parseMinThreshold(criteria: string[]) {
  const criterion = criteria[0]
  if (!criterion) return undefined
  const match = criterion.match(/^\w+\s*>=\s*([0-9]+(?:\.[0-9]+)?)$/)
  return match ? Number(match[1]) : undefined
}

function buildMetricDefinition(
  metricKey: string,
  metricType: string,
  medals: DimensionMeta['medals'],
): MetricDefinition {
  if (metricType === 'boolean') {
    return { name: metricKey, type: 'boolean', signal_name: metricKey }
  }

  const bronze = parseMinThreshold(medals.bronze?.criteria ?? [])
  const silver = parseMinThreshold(medals.silver?.criteria ?? [])
  const gold = parseMinThreshold(medals.gold?.criteria ?? [])

  return {
    name: metricKey,
    type: 'numeric',
    medals: {
      ...(bronze !== undefined ? { bronze: { min: bronze } } : {}),
      ...(silver !== undefined ? { silver: { min: silver } } : {}),
      ...(gold !== undefined ? { gold: { min: gold } } : {}),
    },
  }
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
    if (medalFilter !== 'all' && metricStatus(row) !== medalFilter) return false
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

function resultLabel(result: Result) {
  return <MedalBadge medal={result} size="small" />
}

function distributionBar({ gold, silver, bronze, below_minimum, no_data }: DistributionCounts) {
  const total = gold + silver + bronze + below_minimum + no_data
  if (total === 0) return null

  const segments: Array<{ key: keyof DistributionCounts; color: string; label: string }> = [
    { key: 'gold', color: '#C7962F', label: 'Gold' },
    { key: 'silver', color: '#8F8F8F', label: 'Silver' },
    { key: 'bronze', color: '#9E622A', label: 'Bronze' },
    { key: 'below_minimum', color: '#C7162B', label: 'Sub-min' },
    { key: 'no_data', color: '#666', label: 'No data' },
  ]

  return (
    <div>
      <div
        aria-label="Metric distribution"
        style={{
          display: 'flex',
          overflow: 'hidden',
          borderRadius: '999px',
          height: '16px',
          background: '#eee',
        }}
      >
        {segments.map((segment) => {
          const count = { gold, silver, bronze, below_minimum, no_data }[segment.key]
          if (count === 0) return null
          return (
            <div
              key={segment.key}
              title={`${segment.label}: ${count}`}
              style={{
                width: `${(count / total) * 100}%`,
                backgroundColor: segment.color,
              }}
            />
          )
        })}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginTop: '0.75rem' }}>
        <span><strong>Gold</strong>: {gold}</span>
        <span><strong>Silver</strong>: {silver}</span>
        <span><strong>Bronze</strong>: {bronze}</span>
        <span><strong>Sub-min</strong>: {below_minimum}</span>
        <span><strong>No data</strong>: {no_data}</span>
      </div>
    </div>
  )
}

function toGapTarget(target: Result): Medal {
  if (target === 'gold' || target === 'silver' || target === 'bronze') return target
  return 'unrated'
}

const TABLE_TH: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  textAlign: 'left',
  fontSize: '0.75rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  color: '#666',
  borderBottom: '2px solid #d9d9d9',
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

  const metricMeta = meta.outputs[metricKey]
  const metricDefinition = buildMetricDefinition(metricKey, metricMeta.type, meta.medals)
  const thresholdPills = [
    ['Bronze', meta.medals.bronze?.criteria ?? []],
    ['Silver', meta.medals.silver?.criteria ?? []],
    ['Gold', meta.medals.gold?.criteria ?? []],
  ] as const
  const flattenedCount = filteredGroups.reduce((count, group) => count + (group.rootVisible ? 1 : 0) + group.leaves.length, 0)
  const distribution = computeDistribution(filteredGroups)

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">
        <p style={{ marginBottom: '1rem' }}><Link to={`/dimensions/${dimensionId}`}>← {meta.label ?? dimensionId}</Link></p>

        <div className="p-card u-sv3">
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 320px', gap: '1.5rem', alignItems: 'start' }}>
            <div>
              <h1 className="p-heading--3" style={{ marginBottom: '0.25rem' }}>Metric distribution</h1>
              <p className="u-text--muted" style={{ margin: 0 }}>
                {metricMeta.label} ({metricKey})
              </p>
              {metricMeta.description && <p style={{ marginBottom: '0.75rem' }}>{metricMeta.description}</p>}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                {metricMeta.ai_assisted ? (
                  <span
                    title="Scored by AI (LLM via OpenRouter)"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: '#7764d8',
                      background: '#f0eeff',
                      border: '1px solid #c5bcf5',
                      borderRadius: '3px',
                      padding: '0.15rem 0.4rem',
                      cursor: 'default',
                    }}
                  >
                    ✦ AI
                  </span>
                ) : (
                  <span style={{ fontSize: '0.75rem', color: '#666' }}>Deterministic</span>
                )}
              </div>
            </div>

            <div>
              <h2 className="p-heading--4" style={{ marginBottom: '0.75rem' }}>Fleet distribution</h2>
              {distributionBar(distribution)}
            </div>
          </div>
        </div>

        <div className="p-card u-sv3">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '1rem' }}>
            {thresholdPills.map(([label, criteria]) => (
              <span
                key={label}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  borderRadius: '999px',
                  border: '1px solid #d9d9d9',
                  background: '#fafafa',
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.875rem',
                }}
                title={criteria.join(' · ')}
              >
                <strong>{label}</strong>
                <span>{thresholdSummary(criteria)}</span>
              </span>
            ))}
            <span style={{ marginLeft: 'auto', fontSize: '0.8125rem', color: '#777' }}>
              {flattenedCount} row{flattenedCount === 1 ? '' : 's'}
            </span>
          </div>

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
              <option value="below_minimum">Sub-min</option>
              <option value="insufficient_data">No data</option>
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
          </div>

          <p style={{ margin: '0 0 1rem', fontSize: '0.8125rem', color: '#666' }}>
            Threshold result shows how this metric value rates against the dimension&apos;s rubric (gold/silver/bronze/sub-min/no data).
            {' '}
            Gap to target compares the metric value to the threshold for this product&apos;s target medal.
          </p>

          <div style={{ overflowX: 'auto' }}>
            <table className="p-table" style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse' }}>
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '24%' }} />
              </colgroup>
              <thead>
                <tr style={{ background: '#f5f5f5' }}>
                  <th style={TABLE_TH}>Product</th>
                  <th style={TABLE_TH}>Value</th>
                  <th style={TABLE_TH}>Threshold result</th>
                  <th style={TABLE_TH}>Gap to target</th>
                </tr>
              </thead>
              <tbody>
                {filteredGroups
                  .sort((a, b) => RESULT_ORDER[metricStatus(b.root)] - RESULT_ORDER[metricStatus(a.root)])
                  .flatMap(group => {
                    const rows = []
                    if (group.rootVisible) {
                      rows.push(
                        <tr key={group.root.product.id} style={{ borderBottom: '1px solid #e5e5e5', background: '#fafafa' }}>
                          <td style={{ padding: '0.65rem 0.75rem', minWidth: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                              <Link
                                to={`/products/${group.root.product.id}`}
                                style={{ display: 'block', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                              >
                                {group.root.product.name}
                              </Link>
                            </div>
                          </td>
                          <td style={{ padding: '0.65rem 0.75rem', verticalAlign: 'top' }}>{valueCell(group.root.value)}</td>
                          <td style={{ padding: '0.65rem 0.75rem', verticalAlign: 'top' }}>{resultLabel(metricStatus(group.root))}</td>
                          <td style={{ padding: '0.65rem 0.75rem', verticalAlign: 'top' }}>{computeGapToTarget(group.root.value, toGapTarget(group.root.product.target_result), metricDefinition) ?? '—'}</td>
                        </tr>,
                      )
                    }
                    for (const leaf of group.leaves) {
                      rows.push(
                        <tr key={leaf.product.id} style={{ borderBottom: '1px solid #e5e5e5', background: '#fff' }}>
                          <td style={{ padding: '0.65rem 0.75rem', minWidth: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
                              <div style={{ width: '1.25rem', flexShrink: 0, alignSelf: 'stretch', position: 'relative', marginRight: '0.35rem' }}>
                                <span
                                  style={{
                                    position: 'absolute',
                                    left: '0.5rem',
                                    top: 0,
                                    bottom: 0,
                                    width: '1px',
                                    background: '#c8d3e0',
                                    pointerEvents: 'none',
                                  }}
                                />
                                <span
                                  style={{
                                    position: 'absolute',
                                    left: '0.5rem',
                                    top: '50%',
                                    width: '0.6rem',
                                    height: '1px',
                                    background: '#c8d3e0',
                                    pointerEvents: 'none',
                                  }}
                                />
                              </div>
                              <Link
                                to={`/products/${leaf.product.id}`}
                                style={{ display: 'block', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.875rem' }}
                              >
                                {leaf.product.name}
                              </Link>
                            </div>
                          </td>
                          <td style={{ padding: '0.65rem 0.75rem', verticalAlign: 'top' }}>{valueCell(leaf.value)}</td>
                          <td style={{ padding: '0.65rem 0.75rem', verticalAlign: 'top' }}>{resultLabel(metricStatus(leaf))}</td>
                          <td style={{ padding: '0.65rem 0.75rem', verticalAlign: 'top' }}>{computeGapToTarget(leaf.value, toGapTarget(leaf.product.target_result), metricDefinition) ?? '—'}</td>
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
