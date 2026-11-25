import { useId } from 'react'
import type { MetricOutcome } from '../types'
import { meetsThreshold, type ThresholdInfo } from '../lib/metricOutcome'

export default function MetricEvidence({ outcome, threshold, unit, plain = false, showReason = true }: {
  outcome: MetricOutcome
  threshold?: ThresholdInfo
  unit?: string | null
  plain?: boolean
  showReason?: boolean
}) {
  const reasonId = useId()
  if (outcome.state !== 'measured') {
    return <span style={{ color: '#666' }}>
      <span aria-describedby={showReason ? reasonId : undefined}>{outcome.state === 'not_applicable' ? 'N/A' : 'Insufficient data'}</span>
      {showReason && <span id={reasonId} style={{ display: 'block', fontSize: '0.75rem', overflowWrap: 'anywhere' }}>{outcome.reason}</span>}
    </span>
  }
  const value = outcome.value
  const passes = threshold ? meetsThreshold(value, threshold) : undefined
  const color = passes === undefined ? (value === true && !plain ? '#237a36' : undefined) : passes ? '#237a36' : '#c7162b'
  const label = typeof value === 'boolean' && !plain ? (value ? '✓' : '✗') : value === '' ? 'Not adopted' : String(value)
  const reasonVisible = showReason && Boolean(outcome.reason) && (passes === false || (passes === undefined && value === false))
  return <span style={{ color, fontWeight: threshold ? 600 : undefined, overflowWrap: 'anywhere' }} title={showReason ? outcome.reason : undefined}>
    <span aria-label={typeof value === 'boolean' && !plain ? String(value) : undefined} aria-describedby={reasonVisible ? reasonId : undefined}>{label}</span>
    {typeof value === 'number' && unit && <span style={{ color: '#666', fontWeight: 400, fontSize: '0.75rem' }}> {unit}</span>}
    {threshold && typeof value === 'number' && <span style={{ color: '#666', fontWeight: 400, fontSize: '0.75rem' }}> / {String(threshold.value)}{unit ? ` ${unit}` : ''}</span>}
    {reasonVisible && <span id={reasonId} style={{ display: 'block', color: '#666', fontWeight: 400, fontSize: '0.75rem', whiteSpace: 'pre-line', overflowWrap: 'anywhere' }}>{outcome.reason}</span>}
  </span>
}
