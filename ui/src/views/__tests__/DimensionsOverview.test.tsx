import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { Portfolio } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

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
      composed_of: null,
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: {
          result: 'bronze',
          drift: null,
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
      composed_of: null,
      context_refs: [],
      parent_product_ids: ['discourse'],
      source: { repo: 'canonical/discourse-k8s-operator', subpath: null },
      dimensions: {
        test_verification: {
          result: 'silver',
          drift: null,
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
}

function wrap(path: string) {
  const queryClient = new QueryClient()
  vi.mocked(usePortfolio).mockReturnValue({
    data: mockPortfolio,
    isLoading: false,
    isError: false,
    error: null,
  } as ReturnType<typeof usePortfolio>)

  window.location.hash = `#${path}`

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
})
