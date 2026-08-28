import { Fragment } from 'react'
import { useParams, Link } from 'react-router'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import { RESULT_ORDER } from '../lib/groupedPortfolioView'
import type { DriftInfo } from '../types'
import { buildDimensionGroupedRows } from '../lib/groupedPortfolioView'

const TIER_LABELS = ['gold', 'silver', 'bronze'] as const

function parseCriterionMetric(criterion: string): string {
  return criterion.split(/\s+/)[0]
}

function renderDriftDeadline(drift: DriftInfo | null) {
  if (drift === null) {
    return <span style={{ color: '#0e8420', fontWeight: 600 }}>✓</span>
  }

  const deadline = drift.deadline.slice(0, 10)

  if (drift.status === 'overdue') {
    return <span>🔴 Overdue · {deadline}</span>
  }

  return <span>🟡 Remediating · {deadline}</span>
}

export default function DimensionDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: portfolio, isLoading, isError, error } = usePortfolio()

  if (isLoading) return <LoadingSpinner />
  if (isError) return <div className="p-notification--negative"><p>{error?.message}</p></div>
  if (!portfolio) return null

  const meta = portfolio.dimensions_meta[id!]
  if (!meta) {
    return (
      <div className="row" style={{ paddingTop: '1.5rem' }}>
        <div className="col-12">
          <p>Dimension <strong>{id}</strong> not found. <Link to="/">Back to overview</Link></p>
        </div>
      </div>
    )
  }

  const groupedProductScores = buildDimensionGroupedRows(portfolio, id!)
    .sort((a, b) =>
      RESULT_ORDER[b.root.entry.result] - RESULT_ORDER[a.root.entry.result]
    )

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">

        {/* Back nav */}
        <p style={{ marginBottom: '1rem' }}><Link to="/">← Overview</Link></p>

        {/* Header card */}
        <div className="p-card u-sv3">
          <h1 className="p-heading--3" style={{ marginBottom: '0.25rem' }}>{meta.label ?? id!.replace(/_/g, ' ')}</h1>
          {meta.description && <p className="u-text--muted" style={{ margin: 0 }}>{meta.description}</p>}
        </div>

        {/* Metrics card — one row per output metric */}
        {meta.outputs && Object.keys(meta.outputs).length > 0 && (
          <div className="p-card u-sv3">
            <h2 className="p-heading--4" style={{ marginBottom: '1rem' }}>Metrics</h2>
            <table style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse' }}>
              <colgroup>
                <col style={{ width: '22%' }} />
                <col style={{ width: '48%' }} />
                <col style={{ width: '15%' }} />
                <col style={{ width: '15%' }} />
              </colgroup>
              <thead>
                <tr style={{ borderBottom: '1px solid #d9d9d9' }}>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Metric</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Description</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Type</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Scoring</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(meta.outputs).map(([key, out], idx) => (
                  <tr key={key} style={{ borderBottom: '1px solid #e5e5e5', background: idx % 2 === 0 ? '#fafafa' : '#fff' }}>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                      <Link to={`/dimensions/${id}/metrics/${key}`} style={{ fontWeight: 600, display: 'block' }}>
                        {out.label}
                      </Link>
                      <code style={{ fontSize: '0.75rem', color: '#666' }}>{key}</code>
                    </td>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top', fontSize: '0.875rem' }}>
                      {out.description}
                    </td>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                      <span style={{ fontSize: '0.75rem' }}>
                        <strong>{out.type}</strong>
                        {out.range && <span style={{ color: '#666', display: 'block' }}>{out.range}</span>}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                      {out.ai_assisted ? (
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
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Rubric card — criteria only, descriptions on hover */}
        <div className="p-card u-sv3">
          <h2 className="p-heading--4" style={{ marginBottom: '1rem' }}>Medal rubric</h2>
          <table style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse' }}>
            <colgroup>
              <col style={{ width: '14%' }} />
              <col style={{ width: '86%' }} />
            </colgroup>
            <thead>
              <tr style={{ borderBottom: '1px solid #d9d9d9' }}>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Tier</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Required criteria</th>
              </tr>
            </thead>
            <tbody>
              {TIER_LABELS.map((tier, idx) => {
                const crit = meta.medals[tier]
                if (!crit) return null
                return (
                  <tr key={tier} style={{ borderBottom: '1px solid #e5e5e5', background: idx % 2 === 0 ? '#fafafa' : '#fff' }}>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                      <MedalBadge medal={tier} size="small" />
                    </td>
                    <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                      <ul className="p-list" style={{ margin: 0 }}>
                        {crit.criteria.map((c: string, i: number) => {
                          const metricKey = parseCriterionMetric(c)
                          const outputMeta = meta.outputs?.[metricKey]
                          return (
                            <li
                              key={i}
                              className="p-list__item"
                              title={outputMeta?.description}
                              style={{ cursor: outputMeta?.description ? 'help' : undefined }}
                            >
                              <strong>{outputMeta?.label ?? metricKey}</strong>
                              {' '}
                              <code style={{ fontSize: '0.8125rem', color: '#666' }}>{c}</code>
                            </li>
                          )
                        })}
                      </ul>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Product scores card */}
        <div className="p-card u-sv3">
          <h2 className="p-heading--4" style={{ marginBottom: '1rem' }}>Product scores</h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse' }}>
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '25%' }} />
                <col style={{ width: '35%' }} />
              </colgroup>
              <thead>
                <tr style={{ borderBottom: '1px solid #d9d9d9' }}>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Product</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Dimension score</th>
                  <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>Drift / Deadline</th>
                </tr>
              </thead>
              <tbody>
                {groupedProductScores.map((group, groupIdx) => (
                  <Fragment key={group.root.product.id}>
                    <tr
                      style={{
                        borderBottom: '1px solid #e5e5e5',
                        background: groupIdx % 2 === 0 ? '#fafafa' : '#fff',
                      }}
                    >
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        <Link to={`/products/${group.root.product.id}`} style={{ fontWeight: 600 }}>
                          {group.root.product.name}
                        </Link>
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        <MedalBadge medal={group.root.entry.result} size="small" />
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        {renderDriftDeadline(group.root.entry.drift)}
                      </td>
                    </tr>
                    {group.leaves.map((leaf) => (
                      <tr key={leaf.product.id} style={{ borderBottom: '1px solid #e5e5e5', background: '#fff' }}>
                        <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                          <Link to={`/products/${leaf.product.id}`} style={{ fontWeight: 500 }}>
                            ↳ {leaf.product.name}
                          </Link>
                        </td>
                        <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                          <MedalBadge medal={leaf.entry.result} size="small" />
                        </td>
                        <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                          {leaf.entry.drift ? renderDriftDeadline(leaf.entry.drift) : <span style={{ color: '#999' }}>—</span>}
                        </td>
                      </tr>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <p className="u-sv2">
          <Link to="/about">Learn more about the framework →</Link>
        </p>

      </div>
    </div>
  )
}
