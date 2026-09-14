import { describe, it, expect } from 'vitest'
import { resolveRecoveryVersion } from './frameworkVersions'
import type { FrameworkVersionSummary } from '../types'

function version(overrides: Partial<FrameworkVersionSummary>): FrameworkVersionSummary {
  return {
    id: 'v0',
    sequence: 0,
    label: 'PQF V0',
    status: 'active',
    description: '',
    portfolio_url: 'versions/v0/portfolio.json',
    generated_at: '2026-06-01T00:00:00Z',
    contract_digest: 'digest-v0',
    ...overrides,
  }
}

describe('resolveRecoveryVersion', () => {
  it('prefers the active version when one exists', () => {
    const upcoming = version({ id: 'v1', sequence: 1, status: 'upcoming' })
    const active = version({ id: 'v0', sequence: 0, status: 'active' })
    expect(resolveRecoveryVersion([upcoming, active])).toBe(active)
  })

  it('falls back to the highest-sequence version when no version is active', () => {
    const archived = version({ id: 'v-1', sequence: -1, status: 'archived' })
    const upcoming = version({ id: 'v1', sequence: 1, status: 'upcoming' })
    expect(resolveRecoveryVersion([archived, upcoming])).toBe(upcoming)
  })

  it('returns undefined when there are no versions at all', () => {
    expect(resolveRecoveryVersion([])).toBeUndefined()
  })
})
