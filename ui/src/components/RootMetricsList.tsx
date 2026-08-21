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
    c => !c.excluded_from_parent_medal && c.result !== 'insufficient_data' && c.result !== 'not_applicable',
  )
  const metricKeys = metaOutputs ? Object.keys(metaOutputs) : []

  if (metricKeys.length === 0 || inScope.length === 0) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {metricKeys.map((key, idx) => {
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
        const isExpandable = !allAgree

        return (
          <div
            key={key}
            style={{
              borderTop: idx > 0 ? '1px solid #f0f0f0' : 'none',
              background: isExpanded ? '#f7f9ff' : 'transparent',
            }}
          >
            {/* Metric row: label | value | chevron */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.5rem',
                padding: '0.3rem 0',
                fontSize: '0.8125rem',
                cursor: isExpandable ? 'pointer' : 'default',
              }}
              onClick={isExpandable ? () => setExpanded(prev => ({ ...prev, [key]: !prev[key] })) : undefined}
              role={isExpandable ? 'button' : undefined}
              aria-expanded={isExpandable ? isExpanded : undefined}
              aria-label={isExpandable ? `${isExpanded ? 'Collapse' : 'Expand'} ${label}: ${inScope.length} components` : undefined}
              tabIndex={isExpandable ? 0 : undefined}
              onKeyDown={isExpandable ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(prev => ({ ...prev, [key]: !prev[key] })) } } : undefined}
            >
              {/* Left: label + info badge */}
              <span
                style={{ color: '#555', display: 'flex', alignItems: 'center', gap: '0.35rem', flexShrink: 0 }}
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
              </span>

              {/* Right: value + expand chevron */}
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                {formatValue(worst.value, threshold, unit)}
                {isExpandable && (
                  <span
                    style={{
                      fontSize: '0.625rem',
                      color: '#06c',
                      width: '1rem',
                      textAlign: 'center',
                      userSelect: 'none',
                    }}
                    aria-hidden="true"
                  >
                    {isExpanded ? '▾' : '▸'}
                  </span>
                )}
              </span>
            </div>

            {/* Expanded breakdown panel — full width of the cell */}
            {isExpandable && isExpanded && (
              <div
                style={{
                  margin: '0 0 0.35rem 0',
                  borderRadius: '4px',
                  border: '1px solid #e0e7ff',
                  overflow: 'hidden',
                  fontSize: '0.75rem',
                }}
              >
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '0.2rem 0.5rem',
                  background: '#e8eeff',
                  color: '#555',
                  fontWeight: 600,
                  fontSize: '0.6875rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}>
                  <span>Component</span>
                  <span>{label}</span>
                </div>
                {inScope.map((leaf, leafIdx) => {
                  const val = leaf.metrics[key]
                  const isWorst = leaf.product_id === worst.leafId
                  return (
                    <div
                      key={leaf.product_id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.25rem 0.5rem',
                        background: leafIdx % 2 === 0 ? '#fff' : '#fafbff',
                        borderTop: '1px solid #eef0f8',
                      }}
                    >
                      <Link
                        to={`/products/${leaf.product_id}`}
                        style={{
                          color: isWorst ? '#c7162b' : '#06c',
                          fontWeight: isWorst ? 600 : 400,
                          textDecoration: 'none',
                        }}
                      >
                        {leaf.product_id}
                      </Link>
                      <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                        {val !== undefined
                          ? formatValue(val, threshold, unit)
                          : <span style={{ color: '#999' }}>—</span>
                        }
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

