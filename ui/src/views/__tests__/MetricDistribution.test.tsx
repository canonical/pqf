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
      composed_of: [{ product_id: 'discourse-k8s', excluded_from_parent_medal: false }],
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: {
          result: 'bronze',
          drift: null,
          metrics: {},
          composition: [
            {
              product_id: 'discourse-k8s',
              repo: 'canonical/discourse-k8s-operator',
              result: 'silver',
              metrics: { coverage_pct: 83 },
              excluded_from_parent_medal: false,
            },
          ],
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
          metrics: { coverage_pct: 83 },
          composition: null,
        },
      },
    },
  ],
  dimensions_meta: {
    test_verification: {
      label: 'Test Verification',
      outputs: {
        coverage_pct: {
          label: 'Coverage',
          description: 'Coverage',
          type: 'number',
          range: '0-100',
          ai_assisted: true,
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

describe('MetricDistribution route', () => {
  it('renders the redesigned metric distribution header and table', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    expect(await screen.findByRole('heading', { name: /metric distribution/i })).toBeInTheDocument()
    expect(screen.getByText(/Coverage \(coverage_pct\)/i)).toBeInTheDocument()
    expect(screen.getByText('coverage_pct ≥ 70')).toBeInTheDocument()
    expect(screen.getByText('coverage_pct ≥ 80')).toBeInTheDocument()
    expect(screen.getByText('coverage_pct ≥ 90')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^product$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^value$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /threshold result/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /gap to target/i })).toBeInTheDocument()
  })

  it('shows the gap to target and ai-assisted badge for metric rows', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    const leafLink = await screen.findByRole('link', { name: /discourse k8s/i })
    expect(leafLink).toBeInTheDocument()
    expect(screen.getAllByText('Exceeds target')).toHaveLength(2)
    expect(screen.getByText('✦ AI')).toBeInTheDocument()
  })

  it('falls back to composition metrics for root rows when root metric is missing', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    await screen.findByRole('heading', { name: /metric distribution/i })
    const valueCells = screen.getAllByRole('cell', { name: '83' })
    expect(valueCells).toHaveLength(2)
  })
})
