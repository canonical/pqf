import { describe, it, expect } from 'vitest'
import { describeFrameworkContext } from './frameworkContext'
import type { FrameworkVersionSummary } from '../types'

const base: FrameworkVersionSummary = {
  id: 'v0',
  sequence: 0,
  label: 'PQF V0',
  status: 'active',
  description: '',
  portfolio_url: 'versions/v0/portfolio.json',
  generated_at: '2026-06-01T12:00:00Z',
  contract_digest: 'digest-v0',
}

describe('describeFrameworkContext', () => {
  it('describes the active version as the current framework', () => {
    expect(describeFrameworkContext(base)).toBe('Current framework · PQF V0')
  })

  it('describes an upcoming version as planning with a stable, locale-independent refreshed date', () => {
    const upcoming: FrameworkVersionSummary = {
      ...base,
      id: 'v1',
      label: 'PQF V1',
      status: 'upcoming',
      generated_at: '2026-09-05T23:30:00Z',
    }
    // Date-only, UTC-derived — must not depend on the host's locale or timezone (unlike
    // `toLocaleString()`, which produced a different, non-deterministic string per environment).
    expect(describeFrameworkContext(upcoming)).toBe('Planning against PQF V1 · refreshed 2026-09-05')
  })

  it('describes an archived version as an archived snapshot with a stable, locale-independent generated date', () => {
    const archived: FrameworkVersionSummary = {
      ...base,
      id: 'v-1',
      label: 'PQF V-1',
      status: 'archived',
      generated_at: '2026-01-15T02:00:00Z',
    }
    expect(describeFrameworkContext(archived)).toBe('Archived snapshot · generated 2026-01-15')
  })

  it('renders the same date regardless of the time-of-day component, since the label is date-only', () => {
    const midnightUtc: FrameworkVersionSummary = { ...base, id: 'v2', label: 'PQF V2', status: 'upcoming', generated_at: '2026-03-10T00:00:00Z' }
    const lateUtc: FrameworkVersionSummary = { ...base, id: 'v2', label: 'PQF V2', status: 'upcoming', generated_at: '2026-03-10T23:59:59Z' }
    expect(describeFrameworkContext(midnightUtc)).toBe(describeFrameworkContext(lateUtc))
    expect(describeFrameworkContext(midnightUtc)).toBe('Planning against PQF V2 · refreshed 2026-03-10')
  })
})
