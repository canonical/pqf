import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { FrameworkVersionIndex, Portfolio } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

vi.mock('../../hooks/useFrameworkVersions')
import { useFrameworkVersions } from '../../hooks/useFrameworkVersions'

const mockFrameworkVersions: FrameworkVersionIndex = {
  versions: [
    {
      id: 'v0',
      sequence: 0,
      label: 'PQF V0',
      status: 'active',
      description: 'Current framework revision',
      portfolio_url: 'versions/v0/portfolio.json',
      generated_at: '2026-07-23T00:00:00Z',
      contract_digest: 'digest-v0',
    },
  ],
}

const mockPortfolio: Portfolio = {
  generated_at: '2026-07-23T00:00:00Z',
  products: [
    {
      id: 'discourse',
      product_type: 'root',
      name: 'Discourse',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'bronze',
      squad: 'americas',
      is_portfolio_entry: true,
      meets_target: false,
      composed_of: null,
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: {
          result: 'bronze',
          meets_target: false,
          metrics: {},
          composition: null,
        },
      },
    },
    {
      id: 'discourse-k8s',
      product_type: 'charm',
      name: 'Discourse K8s',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'silver',
      squad: '',
      is_portfolio_entry: false,
      meets_target: true,
      composed_of: null,
      context_refs: [],
      parent_product_ids: ['discourse'],
      source: { repo: 'canonical/discourse-k8s-operator', subpath: null },
      dimensions: {
        test_verification: {
          result: 'silver',
          meets_target: true,
          metrics: {},
          composition: null,
        },
      },
    },
  ],
  dimensions_meta: {
    test_verification: {
      label: 'Test Verification',
      description: 'Build and coverage quality signals.',
      outputs: {
        coverage_pct: {
          label: 'Coverage',
          description: 'Coverage',
          type: 'number',
          range: '0-100',
        },
        stability_pct: {
          label: 'Stability',
          description: 'Stability',
          type: 'number',
          range: '0-100',
        },
      },
      medals: {
        bronze: { criteria: ['coverage_pct >= 70'] },
        silver: { criteria: ['coverage_pct >= 80'] },
        gold: { criteria: ['coverage_pct >= 90'] },
      },
    },
  },
  framework: { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active', description: 'Current framework revision' },
  contract_digest: 'digest-v0',
  source_revision: 'abc123',
  implementation_fingerprints: {},
  compliance_summary: { total: 1, meeting_target: 0, below_target: 1, insufficient_data: 0 },
}

function wrap(path: string) {
  const queryClient = new QueryClient()
  vi.mocked(usePortfolio).mockReturnValue({
    data: mockPortfolio,
    isLoading: false,
    isError: false,
    error: null,
  } as ReturnType<typeof usePortfolio>)
  vi.mocked(useFrameworkVersions).mockReturnValue({
    data: mockFrameworkVersions,
    isLoading: false,
    isError: false,
    error: null,
  } as ReturnType<typeof useFrameworkVersions>)

  // Routes are version-scoped (Task 9); tests target the sole active version below.
  window.location.hash = `#/v0${path}`

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

describe('DimensionsOverview route', () => {
  it('renders a Products-style table shell for dimensions', async () => {
    wrap('/dimensions')

    expect(await screen.findByRole('heading', { name: /dimensions/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /dimension/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /description/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /products/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /metrics/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /test verification/i })).toBeInTheDocument()
    expect(screen.getByText('2 products')).toBeInTheDocument()
    expect(screen.getByText('2 metrics')).toBeInTheDocument()
    expect(screen.getByText('Bronze')).toBeInTheDocument()
    expect(screen.getByText('Silver')).toBeInTheDocument()
  })

  it('scopes the dimension link to the selected framework version', async () => {
    wrap('/dimensions')
    const link = await screen.findByRole('link', { name: /test verification/i })
    expect(link).toHaveAttribute('href', '#/v0/dimensions/test_verification')
  })
})
