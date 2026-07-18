import React from 'react'
import { Link } from 'react-router'
import type { LeafDimensionResult, OutputMeta } from '../types'

interface ThresholdInfo {
  operator: string
  value: number | boolean
}

interface Props {
  composition: LeafDimensionResult[]
  thresholds: Record<string, ThresholdInfo>
  metaOutputs: Record<string, OutputMeta> | undefined
}

function extractUnit(range: string | undefined): string | null {
  if (!range) return null
  const m = range.match(/([a-zA-Z%]+)$/)
  return m ? m[1] : null
}

function meetsThreshold(
  val: string | number | boolean,
  op: string,
  threshold: number | boolean,
): boolean {
  const n = Number(val)
  const t = Number(threshold)
  switch (op) {
    case '>=': return n >= t
    case '<=': return n <= t
    case '>': return n > t
    case '<': return n < t
    case '==': return String(val) === String(threshold)
    default: return false
  }
}

function formatValue(
  val: string | number | boolean,
  threshold?: ThresholdInfo,
  unit?: string | null,
): React.ReactNode {
  const unitSuffix = unit ? <span style={{ color: '#999', fontWeight: 400, fontSize: '0.75rem' }}> {unit}</span> : null

  if (typeof val === 'boolean') {
    if (threshold === undefined) {
      return val
        ? <span style={{ color: '#2d9e46' }}>✓</span>
        : <span style={{ color: '#666' }}>✗</span>
    }
    const passes = meetsThreshold(val, threshold.operator, threshold.value)
    return passes
      ? <span style={{ color: '#2d9e46', fontWeight: 600 }}>✓</span>
      : <span style={{ color: '#c7162b', fontWeight: 600 }}>✗</span>
  }

  const label = String(val)
  if (threshold === undefined) {
    return <span>{label}{unitSuffix}</span>
  }
  const passes = meetsThreshold(val, threshold.operator, threshold.value)
  const color = passes ? '#2d9e46' : '#c7162b'
  return (
    <span style={{ color, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
      {label}{unitSuffix}
      <span style={{ color: '#999', fontWeight: 400, fontSize: '0.75rem' }}> / {String(threshold.value)}{unit ? ` ${unit}` : ''}</span>
    </span>
  )
}

function getWorstEntry(
  metricKey: string,
  inScope: LeafDimensionResult[],
  threshold: ThresholdInfo | undefined,
): { value: string | number | boolean; leafId: string } | null {
  const entries = inScope
    .map(leaf => ({ value: leaf.metrics[metricKey], leafId: leaf.product_id }))
    .filter((e): e is { value: string | number | boolean; leafId: string } => e.value !== undefined)

  if (entries.length === 0) return null

  return entries.reduce((worst, current) => {
    const w = worst.value
    const c = current.value
    if (!threshold) {
      if (typeof c === 'boolean') return !c && !!w ? current : worst
      return Number(c) < Number(w) ? current : worst
    }
    const op = threshold.operator
    if (op === '>=' || op === '>') return Number(c) < Number(w) ? current : worst
    if (op === '<=' || op === '<') return Number(c) > Number(w) ? current : worst
    if (op === '==') {
      if (typeof c === 'boolean') return !c && !!w ? current : worst
      const cMisses = String(c) !== String(threshold.value)
      const wMisses = String(w) !== String(threshold.value)
      return cMisses && !wMisses ? current : worst
    }
    return worst
  })
}

export default function RootMetricsList({ composition, thresholds, metaOutputs }: Props) {
  const [expanded, setExpanded] = React.useState<Record<string, boolean>>({})

  const inScope = composition.filter(
    c => !c.excluded_from_parent_medal && c.applicability === 'scored',
  )
  const metricKeys = metaOutputs ? Object.keys(metaOutputs) : []

  if (metricKeys.length === 0 || inScope.length === 0) return null

  return (
    <dl
      className="u-no-margin"
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: '0.1rem 0.75rem',
        fontSize: '0.8125rem',
      }}
    >
      {metricKeys.map(key => {
        const meta = metaOutputs![key]
        const label = meta.label
        const desc = meta.description
        const isInformational = meta.informational === true
        const unit = extractUnit(meta.range)
        const threshold = isInformational ? undefined : thresholds[key]
        const worst = getWorstEntry(key, inScope, threshold)
        if (worst === null) return null

        const allAgree = inScope.every(
          l => l.metrics[key] !== undefined && String(l.metrics[key]) === String(worst.value),
        )
        const isExpanded = expanded[key] ?? false

        return (
          <React.Fragment key={key}>
            <dt
              style={{ color: '#666', margin: 0, display: 'flex', alignItems: 'center', gap: '0.35rem' }}
              title={desc}
            >
              {label}
              {isInformational && (
                <span style={{
                  fontSize: '0.625rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: '#888',
                  border: '1px solid #ccc',
                  borderRadius: '2px',
                  padding: '0 3px',
                  lineHeight: 1.4,
                }}>
                  info
                </span>
              )}
            </dt>
            <dd style={{ margin: 0, textAlign: 'right' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem' }}>
                {formatValue(worst.value, threshold, unit)}
                {!allAgree && (
                  <button
                    onClick={() => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))}
                    aria-expanded={isExpanded}
                    aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${label}: ${inScope.length} components`}
                    style={{
                      fontSize: '0.6875rem',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#06c',
                      padding: 0,
                    }}
                  >
                    {isExpanded ? '▾' : '▸'} {inScope.length} components
                  </button>
                )}
              </span>
              {isExpanded && (
                <div
                  style={{
                    marginTop: '0.25rem',
                    paddingLeft: '0.5rem',
                    borderLeft: '2px solid #e5e5e5',
                  }}
                >
                  {inScope.map(leaf => (
                    <div
                      key={leaf.product_id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        gap: '0.5rem',
                        padding: '0.1rem 0',
                        fontSize: '0.75rem',
                      }}
                    >
                      <Link
                        to={`/products/${leaf.product_id}`}
                        style={{
                          color: leaf.product_id === worst.leafId ? '#c7162b' : '#555',
                          fontWeight: leaf.product_id === worst.leafId ? 600 : 400,
                          textDecoration: 'none',
                        }}
                      >
                        {leaf.product_id}
                      </Link>
                      <span>
                        {leaf.metrics[key] !== undefined
                          ? formatValue(leaf.metrics[key], undefined, unit)
                          : <span style={{ color: '#999' }}>—</span>
                        }
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </dd>
          </React.Fragment>
        )
      })}
    </dl>
  )
}
