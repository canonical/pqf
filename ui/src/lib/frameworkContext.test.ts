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

  it('describes an upcoming version as planning with a refreshed timestamp', () => {
    const upcoming: FrameworkVersionSummary = { ...base, id: 'v1', label: 'PQF V1', status: 'upcoming' }
    expect(describeFrameworkContext(upcoming)).toBe(
      `Planning against PQF V1 · refreshed ${new Date(upcoming.generated_at).toLocaleString()}`,
    )
  })

  it('describes an archived version as an archived snapshot with a generated timestamp', () => {
    const archived: FrameworkVersionSummary = { ...base, id: 'v-1', label: 'PQF V-1', status: 'archived' }
    expect(describeFrameworkContext(archived)).toBe(
      `Archived snapshot · generated ${new Date(archived.generated_at).toLocaleString()}`,
    )
  })
})
