import React from 'react'
import { useParams, Link } from 'react-router'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import DriftChip from '../components/DriftChip'
import MetricsList from '../components/MetricsList'
import LoadingSpinner from '../components/LoadingSpinner'
import type { Medal, LeafDimensionResult } from '../types'

const MEDAL_ORDER: Record<Medal, number> = { gold: 3, silver: 2, bronze: 1, unrated: 0 }

function CompositionImpact({ composition }: { composition: LeafDimensionResult[] }) {
  const [expanded, setExpanded] = React.useState(false)
  const inScope = composition.filter(
    c => !c.excluded_from_parent_medal && c.applicability === 'scored'
  )
  const worst = inScope.length > 0
    ? inScope.reduce((a, b) => MEDAL_ORDER[a.medal] <= MEDAL_ORDER[b.medal] ? a : b)
    : null

  return (
    <div>
      <button
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
        style={{
          fontSize: '0.75rem', background: 'none', border: 'none',
          cursor: 'pointer', color: '#06c', padding: 0, textDecoration: 'underline',
        }}
      >
        {expanded ? '▾' : '▸'} {inScope.length} component{inScope.length !== 1 ? 's' : ''} in scope
      </button>
      {expanded && (
        <div style={{ marginTop: '0.5rem', paddingLeft: '1rem', borderLeft: '2px solid #e5e5e5' }}>
          {composition.map(c => (
            <div
              key={c.product_id}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.25rem 0', fontSize: '0.875rem' }}
            >
              <MedalBadge medal={c.medal} size="small" />
              <span style={{ fontWeight: c.product_id === worst?.product_id ? 600 : 400 }}>
                {c.product_id}
              </span>
              {c.product_id === worst?.product_id && (
                <span style={{ fontSize: '0.6875rem', color: '#C7162B' }}>← worst</span>
              )}
              {c.excluded_from_parent_medal && (
                <span style={{ fontSize: '0.6875rem', color: '#666' }}>excluded</span>
              )}
              {c.applicability === 'not_applicable' && (
                <span style={{ fontSize: '0.6875rem', color: '#666' }}>N/A</span>
              )}
              {c.repo && (
                <a href={`https://github.com/${c.repo}`} target="_blank" rel="noreferrer"
                   style={{ fontSize: '0.75rem', color: '#666' }}>
                  {c.repo} ↗
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

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
              {product.description && <p className="u-text--muted" style={{ margin: 0 }}>{product.description}</p>}
            </div>
            {product.documentation_url && (
              <a href={product.documentation_url} target="_blank" rel="noreferrer" className="p-button--neutral is-small">
                Docs ↗
              </a>
            )}
          </div>
          <hr style={{ margin: '1rem 0' }} />
          <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
            <div>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>CURRENT</span>
              <MedalBadge medal={product.current_medal} />
            </div>
            <div>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>TARGET</span>
              <MedalBadge medal={product.target_medal} />
            </div>
            <div>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>LIFECYCLE</span>
              <span className="p-label">{product.lifecycle}</span>
            </div>
            <div>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>SQUAD</span>
              {(() => {
                const team = SQUAD_TEAMS[product.squad?.toLowerCase()]
                if (!team) return <span>{product.squad}</span>

                return (
                  <a href={team.url} target="_blank" rel="noreferrer" className="p-chip" style={{ textDecoration: 'none', fontSize: '0.875rem', padding: '0.2rem 0.6rem' }}>
                    {team.label}
                  </a>
                )
              })()}
            </div>
          </div>
          {product.parent_product_ids.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
              <span className="u-text--muted" style={{ fontSize: '0.75rem' }}>Part of:</span>
              {product.parent_product_ids.map(parentId => {
                const parent = portfolio.products.find(p => p.id === parentId)
                return parent ? (
                  <Link key={parentId} to={`/products/${parentId}`}
                        className="p-chip" style={{ fontSize: '0.75rem', textDecoration: 'none', padding: '0.15rem 0.5rem' }}>
                    {parent.name}
                  </Link>
                ) : null
              })}
            </div>
          )}
          {product.product_type === 'root' && product.composed_of && (
            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
              <div>
                <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>COMPOSED OF</span>
                <span>{product.composed_of.length} product{product.composed_of.length !== 1 ? 's' : ''}</span>
              </div>
              {product.context_refs.length > 0 && (
                <div>
                  <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>CONTEXT DEPS</span>
                  <span>{product.context_refs.length}</span>
                </div>
              )}
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
                  const targetCriteria = targetTier === 'bronze' || targetTier === 'silver' || targetTier === 'gold'
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
                        <DriftChip drift={entry.drift} />
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        {entry.composition && entry.composition.length > 0 ? (
                          <CompositionImpact composition={entry.composition} />
                        ) : (
                          <MetricsList metrics={entry.metrics} thresholds={targetThresholds} metaOutputs={dimMeta?.outputs} />
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Dependencies (context only) card */}
        {product.context_refs.length > 0 && (
          <div className="p-card u-sv3">
            <h2 className="p-heading--4" style={{ marginBottom: '0.5rem' }}>Dependencies (context only)</h2>
            <p className="u-text--muted" style={{ fontSize: '0.875rem', marginBottom: '0.75rem' }}>
              These dependencies are shown for context. They are not owned by this squad and do not affect the medal score.
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
    </div>
  )
}
