import { useId } from 'react'
import type { MetricOutcome } from '../types'
import { meetsThreshold, type ThresholdInfo } from '../lib/metricOutcome'

export default function MetricEvidence({ outcome, threshold, unit, plain = false }: {
  outcome: MetricOutcome
  threshold?: ThresholdInfo
  unit?: string | null
  plain?: boolean
}) {
  const reasonId = useId()
  if (outcome.state !== 'measured') {
    return <span style={{ color: '#666' }}>
      <span aria-describedby={reasonId}>{outcome.state === 'not_applicable' ? 'N/A' : 'Insufficient data'}</span>
      <span id={reasonId} style={{ display: 'block', fontSize: '0.75rem', overflowWrap: 'anywhere' }}>{outcome.reason}</span>
    </span>
  }
  const value = outcome.value
  const passes = threshold ? meetsThreshold(value, threshold) : undefined
  const color = passes === undefined ? (value === true && !plain ? '#237a36' : undefined) : passes ? '#237a36' : '#c7162b'
  const label = typeof value === 'boolean' && !plain ? (value ? '✓' : '✗') : value === '' ? 'Not adopted' : String(value)
  return <span style={{ color, fontWeight: threshold ? 600 : undefined, overflowWrap: 'anywhere' }} title={outcome.reason}>
    <span aria-label={typeof value === 'boolean' && !plain ? String(value) : undefined}>{label}</span>
    {typeof value === 'number' && unit && <span style={{ color: '#666', fontWeight: 400, fontSize: '0.75rem' }}> {unit}</span>}
    {threshold && typeof value === 'number' && <span style={{ color: '#666', fontWeight: 400, fontSize: '0.75rem' }}> / {String(threshold.value)}{unit ? ` ${unit}` : ''}</span>}
  </span>
}
