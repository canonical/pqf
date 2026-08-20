import React from 'react'
import { useParams, Link } from 'react-router'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import DriftChip from '../components/DriftChip'
import MetricsList from '../components/MetricsList'
import RootMetricsList from '../components/RootMetricsList'
import LoadingSpinner from '../components/LoadingSpinner'
import type { ApplicabilityOutcome, Medal } from '../types'
import { buildGroupedProducts } from '../lib/groupedPortfolioView'

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

function renderDimensionBadge(entry?: { medal: Medal; applicability: ApplicabilityOutcome }) {
  if (!entry) return <MedalBadge medal="unrated" size="small" />
  if (entry.applicability === 'not_applicable') {
    return (
      <span
        style={{
          backgroundColor: '#666',
          color: '#fff',
          borderRadius: '0.25rem',
          padding: '0.1rem 0.4rem',
          fontSize: '0.75rem',
          fontWeight: 600,
          minWidth: '5.5rem',
          display: 'inline-flex',
          justifyContent: 'center',
          alignItems: 'center',
          whiteSpace: 'nowrap',
        }}
      >
        N/A
      </span>
    )
  }
  if (entry.applicability === 'insufficient_data') {
    return (
      <span
        style={{
          backgroundColor: '#666',
          color: '#fff',
          borderRadius: '0.25rem',
          padding: '0.1rem 0.4rem',
          fontSize: '0.75rem',
          fontWeight: 600,
          minWidth: '5.5rem',
          display: 'inline-flex',
          justifyContent: 'center',
          alignItems: 'center',
          whiteSpace: 'nowrap',
        }}
      >
        Insufficient data
      </span>
    )
  }
  if (entry.medal === 'unrated') {
    return (
      <span
        style={{
          backgroundColor: '#666',
          color: '#fff',
          borderRadius: '0.25rem',
          padding: '0.1rem 0.4rem',
          fontSize: '0.75rem',
          fontWeight: 600,
          minWidth: '5.5rem',
          display: 'inline-flex',
          justifyContent: 'center',
          alignItems: 'center',
          whiteSpace: 'nowrap',
        }}
      >
        Below minimum
      </span>
    )
  }
  return <MedalBadge medal={entry.medal} size="small" />
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
  const groupedProducts = buildGroupedProducts(portfolio)
  const productGroup = groupedProducts.find(group => group.root.id === product.id)
  const dependencyDimensions = Object.keys(portfolio.dimensions_meta)

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">

        {/* Back nav */}
        {product.parent_product_ids.length > 0 ? (
          <p style={{ marginBottom: '1rem' }}>
            {product.parent_product_ids.map(parentId => {
              const parent = portfolio.products.find(p => p.id === parentId)
              return parent ? (
                <Link key={parentId} to={`/products/${parentId}`}>
                  ← {parent.name}
                </Link>
              ) : null
            })}
          </p>
        ) : (
          <p style={{ marginBottom: '1rem' }}><Link to="/">← Portfolio</Link></p>
        )}

        {/* Header card */}
        <div className="p-card u-sv3">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 className="p-heading--3" style={{ marginBottom: '0.25rem' }}>{product.name}</h1>
              {product.description && (
                <p className="u-text--muted" style={{ margin: 0 }}>{product.description}</p>
              )}
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {product.source?.repo && (
                <a
                  href={`https://github.com/${product.source.repo}${product.source.subpath ? `/tree/main/${product.source.subpath}` : ''}`}
                  target="_blank" rel="noreferrer"
                  className="p-button--neutral is-small"
                >
                  GitHub ↗
                </a>
              )}
              {product.documentation_url && (
                <a href={product.documentation_url} target="_blank" rel="noreferrer" className="p-button--neutral is-small">
                  Docs ↗
                </a>
              )}
            </div>
          </div>
          <hr style={{ margin: '1rem 0' }} />

          {/* Medal / lifecycle / squad row */}
          <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
            <div>
              <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>
                {isRoot ? 'CURRENT' : 'MEDAL'}
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
            {product.squad && (() => {
              const team = SQUAD_TEAMS[product.squad?.toLowerCase()]
              if (team) return (
                <div>
                  <span className="u-text--muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>SQUAD</span>
                  <a href={team.url} target="_blank" rel="noreferrer"
                    className="p-chip"
                    style={{ textDecoration: 'none', fontSize: '0.875rem', padding: '0.2rem 0.6rem' }}>
                    {team.label}
                  </a>
                </div>
              )
              return null
            })()}
          </div>

          {/* Part of: (leaf pages) — shown inline with Components for consistency */}
          {product.parent_product_ids.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
              <span className="u-text--muted" style={{ fontSize: '0.75rem' }}>Part of:</span>
              {product.parent_product_ids.map(parentId => {
                const parent = portfolio.products.find(p => p.id === parentId)
                return parent ? (
                  <Link key={parentId} to={`/products/${parentId}`}
                    className="p-chip"
                    style={{ fontSize: '0.75rem', textDecoration: 'none', padding: '0.15rem 0.5rem' }}>
                    {parent.name} →
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
                      style={{
                        fontSize: '0.8125rem',
                        textDecoration: 'none',
                        padding: '0.2rem 0.6rem',
                        borderRadius: '2rem',
                        border: '1px solid #06c',
                        color: '#06c',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                      }}>
                      {leafProduct?.name ?? c.product_id} ↗
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
                  // Bronze criteria establish the minimum bar (rated vs unrated);
                  // target-tier criteria are overlaid so failing metrics show against the actual target.
                  const bronzeCriteria = dimMeta?.medals?.bronze?.criteria ?? []
                  const targetCriteria = dimMeta?.medals?.[entry.target]?.criteria ?? []
                  const thresholds = parseCriteria([...bronzeCriteria, ...targetCriteria])

                  return (
                    <tr key={dim} style={{ borderBottom: '1px solid #e5e5e5', background: idx % 2 === 0 ? '#fafafa' : '#fff' }}>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        <Link to={`/dimensions/${dim}`} style={{ fontWeight: 500 }}>{dim.replace(/_/g, ' ')}</Link>
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        {renderDimensionBadge(entry)}
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        {isRoot && <DriftChip drift={entry.drift} />}
                      </td>
                      <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                        {entry.applicability === 'not_applicable' ? (
                          <span style={{ color: '#999' }}>—</span>
                        ) : isRoot && entry.composition && entry.composition.length > 0 ? (
                          <RootMetricsList
                            composition={entry.composition}
                            thresholds={thresholds}
                            metaOutputs={dimMeta?.outputs}
                          />
                        ) : (
                          <MetricsList
                            metrics={entry.metrics}
                            thresholds={thresholds}
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
            <h2 className="p-heading--4" style={{ marginBottom: '1rem' }}>Dependencies</h2>

            {isRoot && productGroup && productGroup.leaves.length > 0 && (
              <div style={{ marginBottom: '1rem', overflowX: 'auto' }}>
                <table style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #d9d9d9' }}>
                      <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}>
                        Sub-product
                      </th>
                      <th
                        style={{ width: '7rem', padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}
                      >
                        Type
                      </th>
                      {dependencyDimensions.map(dim => (
                        <th
                          key={dim}
                          style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: '#666' }}
                        >
                          {portfolio.dimensions_meta[dim]?.label ?? dim.replace(/_/g, ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {productGroup.leaves.map((leaf, idx) => (
                      <tr key={leaf.id} style={{ borderBottom: '1px solid #e5e5e5', background: idx % 2 === 0 ? '#fafafa' : '#fff' }}>
                        <td style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                          <Link to={`/products/${leaf.id}`} style={{ fontWeight: 500 }}>
                            {leaf.name}
                          </Link>
                        </td>
                        <td style={{ width: '7rem', padding: '0.75rem', verticalAlign: 'top' }}>
                          <span className="p-label--information" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                            {leaf.product_type}
                          </span>
                        </td>
                        {dependencyDimensions.map(dim => (
                          <td key={dim} style={{ padding: '0.75rem', verticalAlign: 'top' }}>
                            {renderDimensionBadge(leaf.dimensions[dim])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Also scored / External context — compact inline sections */}
            {product.context_refs.length > 0 && (() => {
              const findLinkedProduct = (cr: typeof product.context_refs[0]) =>
                cr.repo ? portfolio.products.find(p =>
                  p.source?.repo === cr.repo ||
                  p.composed_of?.some(c => {
                    const leaf = portfolio.products.find(lp => lp.id === c.product_id)
                    return leaf?.source?.repo === cr.repo
                  })
                ) : undefined

              const peOwned = product.context_refs.filter(cr => findLinkedProduct(cr) !== undefined)
              const external = product.context_refs.filter(cr => findLinkedProduct(cr) === undefined)

              const sectionStyle: React.CSSProperties = {
                borderTop: '1px solid #e5e5e5',
                marginTop: '1rem',
                paddingTop: '0.75rem',
              }
              const labelStyle: React.CSSProperties = {
                fontSize: '0.7rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                margin: '0 0 0.4rem',
              }
              const inlineListStyle: React.CSSProperties = {
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: '0.25rem 0',
              }

              return (
                <>
                  {peOwned.length > 0 && (
                    <div style={sectionStyle}>
                      <p style={{ ...labelStyle, color: '#555' }}>Also scored by this team</p>
                      <div style={inlineListStyle}>
                        {peOwned.map((cr, i) => {
                          const linked = findLinkedProduct(cr)
                          return (
                            <React.Fragment key={i}>
                              {i > 0 && <span style={{ color: '#ccc', margin: '0 0.4rem' }}>·</span>}
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                                {linked?.current_medal && <MedalBadge medal={linked.current_medal} size="small" />}
                                <Link to={`/products/${linked!.id}`}>{cr.label}</Link>
                              </span>
                            </React.Fragment>
                          )
                        })}
                      </div>
                    </div>
                  )}
                  {external.length > 0 && (
                    <div style={sectionStyle}>
                      <p style={{ ...labelStyle, color: '#888' }}>External dependencies</p>
                      <div style={inlineListStyle}>
                        {external.map((cr, i) => (
                          <React.Fragment key={i}>
                            {i > 0 && <span style={{ color: '#ccc', margin: '0 0.4rem' }}>·</span>}
                            <span>
                              {cr.repo ? (
                                <a href={`https://github.com/${cr.repo}`} target="_blank" rel="noreferrer"
                                  style={{ color: '#666' }}>
                                  {cr.label} ↗
                                </a>
                              ) : (
                                <span style={{ color: '#666' }}>{cr.label}</span>
                              )}
                            </span>
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )
            })()}
          </div>
        )}

      </div>
    </div>
  )
}
