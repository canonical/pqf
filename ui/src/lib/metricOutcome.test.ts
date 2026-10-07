import { describe, expect, it } from 'vitest'
import { aggregateMetric } from './metricOutcome'
import type { MetricOutcome } from '../types'

describe('structured component summaries', () => {
  it('keeps the largest number as worst for a maximum threshold regardless of component order', () => {
    const outcomes: MetricOutcome[] = [{ state: 'measured', value: 5 }, { state: 'measured', value: 2 }]
    expect(aggregateMetric(outcomes, { operator: '<=', value: 3 }).value).toBe(5)
    expect(aggregateMetric([...outcomes].reverse(), { operator: '<=', value: 3 }).value).toBe(5)
  })

  it('honors false-valued boolean criteria rather than assuming true always passes', () => {
    expect(aggregateMetric([
      { state: 'measured', value: true },
      { state: 'measured', value: false },
    ], { operator: '==', value: false }).value).toBe(true)
  })

  it('keeps a measured non-adoption as the bottleneck, not an unknown outcome', () => {
    expect(aggregateMetric([
      { state: 'measured', value: '2.3.0' },
      { state: 'measured', value: '' },
    ], { operator: '!=', value: '' })).toEqual({ state: 'measured', value: '' })
  })

  it('never orders measured version strings numerically', () => {
    expect(aggregateMetric([
      { state: 'measured', value: '2.3.0' },
      { state: 'measured', value: '1.0.0' },
    ], { operator: '!=', value: '' }).value).toBe('2.3.0')
  })

  it('does not turn N/A into a failed component or discard insufficient evidence', () => {
    const na: MetricOutcome = { state: 'not_applicable', value: null, reason: 'Snap product' }
    const unknown: MetricOutcome = { state: 'insufficient_data', value: null, reason: 'No evidence' }
    expect(aggregateMetric([na, { state: 'measured', value: true }])).toEqual({ state: 'measured', value: true })
    expect(aggregateMetric([na, { state: 'measured', value: true }, unknown])).toEqual(unknown)
    expect(aggregateMetric([na])).toEqual(na)
  })
})
