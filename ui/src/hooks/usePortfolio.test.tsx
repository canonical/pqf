import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ReactNode } from 'react'
import type { FrameworkVersionSummary, Portfolio } from '../types'

const mockUseFrameworkVersion = vi.fn()
vi.mock('../providers/FrameworkVersionProvider', () => ({
  useFrameworkVersion: () => mockUseFrameworkVersion(),
}))

import { usePortfolio } from './usePortfolio'

const version: FrameworkVersionSummary = {
  id: 'v0',
  sequence: 0,
  label: 'PQF V0',
  status: 'active',
  description: '',
  portfolio_url: 'v0/portfolio.json',
  generated_at: '2026-01-01T00:00:00Z',
  contract_digest: 'digest-abc',
}

const basePortfolio: Portfolio = {
  generated_at: '2026-01-01T00:00:00Z',
  products: [],
  dimensions_meta: {},
  framework: { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active', description: 'Current framework revision' },
  contract_digest: 'digest-abc',
  source_revision: 'abc123',
  implementation_fingerprints: {},
  compliance_summary: { total: 0, meeting_target: 0, below_target: 0, insufficient_data: 0 },
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('usePortfolio', () => {
  beforeEach(() => {
    mockUseFrameworkVersion.mockReturnValue({ current: version, versions: [version] })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => basePortfolio,
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('resolves with the portfolio when the framework id and contract digest both match', async () => {
    const { result } = renderHook(() => usePortfolio(version), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(basePortfolio)
  })

  it('errors when the portfolio framework id does not match the route version', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...basePortfolio,
          framework: { id: 'v1', sequence: 1, label: 'PQF V1', status: 'active', description: 'Next revision' },
        }),
      }),
    )

    const { result } = renderHook(() => usePortfolio(version), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toMatch(/framework id v1, expected v0/)
  })

  it('errors when the contract digest is missing from the portfolio', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...basePortfolio, contract_digest: undefined }),
      }),
    )

    const { result } = renderHook(() => usePortfolio(version), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toMatch(/contract digest missing/)
  })

  it('errors when the contract digest mismatches the route version', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...basePortfolio, contract_digest: 'digest-other' }),
      }),
    )

    const { result } = renderHook(() => usePortfolio(version), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toMatch(/contract digest digest-other, expected digest-abc/)
  })

  it('errors rather than silently passing when both the version and portfolio digest are missing', async () => {
    // A malformed framework-versions.json entry could omit contract_digest at runtime even
    // though the TS type declares it required. Both sides being `undefined` must not compare
    // as equal and silently validate.
    const versionWithoutDigest = { ...version, contract_digest: undefined } as unknown as FrameworkVersionSummary
    mockUseFrameworkVersion.mockReturnValue({ current: versionWithoutDigest, versions: [versionWithoutDigest] })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...basePortfolio, contract_digest: undefined }),
      }),
    )

    const { result } = renderHook(() => usePortfolio(versionWithoutDigest), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toMatch(/contract digest missing, expected missing/)
  })

  it('errors with a friendly message when compliance_summary is missing from the portfolio', async () => {
    // A malformed artifact (e.g. engine/assemble.py regression) could omit compliance_summary
    // even though the TS type declares it required. Overview reads this field directly without
    // ever recomputing it, so a missing/malformed value must fail fast here instead of surfacing
    // as a confusing runtime crash inside the view.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...basePortfolio, compliance_summary: undefined }),
      }),
    )

    const { result } = renderHook(() => usePortfolio(version), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toMatch(/compliance_summary/i)
  })

  it('errors with a friendly message when compliance_summary has non-numeric fields', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...basePortfolio,
          compliance_summary: { total: 1, meeting_target: 'oops', below_target: 0, insufficient_data: 0 },
        }),
      }),
    )

    const { result } = renderHook(() => usePortfolio(version), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toMatch(/compliance_summary/i)
  })
})
