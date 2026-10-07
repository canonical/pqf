import type { MetricOutcome } from '../types'

export interface ThresholdInfo {
  operator: string
  value: string | number | boolean
}

export function parseLiteral(raw: string): string | number | boolean {
  if (raw.startsWith('"') && raw.endsWith('"')) return JSON.parse(raw) as string
  if (raw.startsWith("'") && raw.endsWith("'")) return raw.slice(1, -1)
  if (raw === 'true') return true
  if (raw === 'false') return false
  return Number(raw)
}

export function meetsThreshold(value: string | number | boolean, threshold: ThresholdInfo): boolean {
  const right = threshold.value
  switch (threshold.operator) {
    case '==': return value === right
    case '!=': return value !== right
    case '>=': return typeof value === 'number' && typeof right === 'number' && value >= right
    case '<=': return typeof value === 'number' && typeof right === 'number' && value <= right
    case '>': return typeof value === 'number' && typeof right === 'number' && value > right
    case '<': return typeof value === 'number' && typeof right === 'number' && value < right
    default: return false
  }
}

export function missingMetric(): MetricOutcome {
  return { state: 'insufficient_data', value: null, reason: 'Metric evidence is missing.' }
}

/** Unknown evidence must not disappear behind a measured component's success. */
export function aggregateMetric(outcomes: MetricOutcome[], threshold?: ThresholdInfo): MetricOutcome {
  const unknown = outcomes.find(outcome => outcome.state === 'insufficient_data')
  if (unknown) return unknown
  const measured = outcomes.filter(outcome => outcome.state === 'measured')
  if (measured.length === 0) return outcomes[0] ?? missingMetric()
  return measured.reduce((worst, current) => {
    if (threshold) {
      const currentPasses = meetsThreshold(current.value, threshold)
      const worstPasses = meetsThreshold(worst.value, threshold)
      if (currentPasses !== worstPasses) return currentPasses ? worst : current
      if (threshold.operator === '<=' || threshold.operator === '<') {
        return typeof current.value === 'number' && typeof worst.value === 'number' && current.value > worst.value ? current : worst
      }
      if (threshold.operator === '==' || threshold.operator === '!=') return worst
    }
    if (typeof current.value === 'number' && typeof worst.value === 'number') return current.value < worst.value ? current : worst
    if (typeof current.value === 'boolean' && typeof worst.value === 'boolean') return !current.value ? current : worst
    return worst
  })
}
