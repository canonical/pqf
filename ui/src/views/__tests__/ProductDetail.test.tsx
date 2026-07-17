import { render, screen, within, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ProductDetail from '../ProductDetail'
import type { Portfolio, LeafDimensionResult } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

const mockPortfolio: Portfolio = {
  generated_at: '2026-06-30T00:00:00Z',
  products: [
    {
      id: 'matrix',
      product_type: 'root',
      name: 'Matrix (Synapse)',
      description: 'Chat platform',
      lifecycle: 'stable',
      target_medal: 'gold',
      current_medal: 'bronze',
      squad: 'americas',
      is_portfolio_entry: true,
      documentation_url: 'https://charmhub.io/synapse',
      context_refs: [{ label: 'Synapse Operator', repo: 'canonical/synapse-operator' }],
      parent_product_ids: [],
      composed_of: [{ product_id: 'synapse', excluded_from_parent_medal: false }],
      dimensions: {
        test_verification: {
          medal: 'silver',
          target: 'gold',
          applicability: 'scored',
          drift: null,
          metrics: { coverage_pct: 87, stability_pct: 94, latest_build_passing: true },
          composition: null,
        },
      },
    },
    {
      id: 'synapse',
      product_type: 'charm',
      name: 'Synapse Charm',
      lifecycle: 'stable',
      target_medal: 'gold',
      current_medal: 'bronze',
      squad: '',
      is_portfolio_entry: false,
      context_refs: [],
      parent_product_ids: ['matrix'],
      composed_of: null,
      source: { repo: 'canonical/synapse-operator', subpath: null },
      dimensions: {
        test_verification: {
          medal: 'bronze',
          target: 'gold',
          applicability: 'scored',
          drift: null,
          metrics: { coverage_pct: 65, latest_build_passing: true },
          composition: null,
        },
      },
    },
  ],
  dimensions_meta: {
    test_verification: {
      outputs: {
        coverage_pct: { label: 'Coverage', description: 'Unit test coverage', type: 'number', range: '0-100' },
        latest_build_passing: { label: 'Build passing', description: 'Latest build status', type: 'boolean', range: 'true/false' },
      },
      medals: {
        bronze: { criteria: ['coverage_pct >= 70'] },
        silver: { criteria: ['coverage_pct >= 80'] },
        gold: { criteria: ['coverage_pct >= 90', 'latest_build_passing == true'] },
      },
    },
  },
}

function mockWith(portfolio: Portfolio) {
  vi.mocked(usePortfolio).mockReturnValue({
    data: portfolio,
    isLoading: false,
    isError: false,
    error: null,
  } as ReturnType<typeof usePortfolio>)
}

function portfolioWithComposition(overrides?: { composition: LeafDimensionResult[] }): Portfolio {
  return {
    ...mockPortfolio,
    products: [
      {
        ...mockPortfolio.products[0],
        dimensions: {
          test_verification: {
            medal: 'silver',
            target: 'gold',
            applicability: 'scored',
            drift: null,
            metrics: { coverage_pct: 87, stability_pct: 94, latest_build_passing: true },
            composition: overrides?.composition ?? [
              {
                product_id: 'synapse',
                repo: 'canonical/synapse-operator',
                medal: 'bronze',
                applicability: 'scored',
                metrics: { coverage_pct: 65, latest_build_passing: true },
                excluded_from_parent_medal: false,
              },
            ],
          },
        },
      },
      mockPortfolio.products[1],
    ],
  }
}

function wrap(id: string) {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/products/${id}`]}>
        <Routes>
          <Route path="/products/:id" element={<ProductDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ProductDetail', () => {
  beforeEach(() => {
    mockWith(mockPortfolio)
  })

  it('renders product name as heading', () => {
    wrap('matrix')
    expect(screen.getByRole('heading', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
  })

  it('shows current medal', () => {
    wrap('matrix')
    expect(screen.getByText('Bronze')).toBeInTheDocument()
  })

  it('shows dimension row', () => {
    wrap('matrix')
    expect(screen.getByText('test verification')).toBeInTheDocument()
  })

  it('renders squad as a linked GitHub team badge', () => {
    wrap('matrix')
    const squadLink = screen.getByRole('link', { name: 'AMER' })
    expect(squadLink).toHaveAttribute('href', 'https://github.com/orgs/canonical/teams/platform-engineering-amer')
    expect(squadLink).toHaveClass('p-chip')
  })

  it('removes the target column from the dimensions table and shows target thresholds in evidence', () => {
    wrap('matrix')

    const table = screen.getByRole('table')
    expect(within(table).queryByRole('columnheader', { name: 'Target' })).not.toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'Current' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'Drift' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'Evidence' })).toBeInTheDocument()

    const row = screen.getByRole('link', { name: 'test verification' }).closest('tr')
    expect(row).not.toBeNull()
    expect(row).toHaveTextContent('Coverage')
    expect(row).toHaveTextContent('87 / 90')
    expect(row).toHaveTextContent('Build passing')
  })

  it('renders GitHub repo link for context ref', () => {
    wrap('matrix')
    expect(screen.getByRole('link', { name: /synapse-operator/i })).toBeInTheDocument()
  })

  it('shows 404 message for unknown product', () => {
    wrap('unknown')
    expect(screen.getByText(/not found/i)).toBeInTheDocument()
  })

  it('root product shows composition count in header', () => {
    wrap('matrix')
    expect(screen.getByText('COMPOSED OF')).toBeInTheDocument()
    expect(screen.getByText('1 product')).toBeInTheDocument()
  })

  it('root product shows context refs card', () => {
    wrap('matrix')
    expect(screen.getByText('Dependencies (context only)')).toBeInTheDocument()
    expect(screen.getByText('Synapse Operator')).toBeInTheDocument()
  })

  it('root product dimension row shows composition expand button', () => {
    mockWith(portfolioWithComposition())
    wrap('matrix')
    expect(screen.getByRole('button', { name: /component in scope/i })).toBeInTheDocument()
  })

  it('clicking composition expands to show leaf breakdown', () => {
    mockWith(portfolioWithComposition())
    wrap('matrix')
    const expandButton = screen.getByRole('button', { name: /component in scope/i })
    fireEvent.click(expandButton)
    expect(screen.getByText('synapse')).toBeInTheDocument()
  })

  it('leaf product shows Part of chip', () => {
    wrap('synapse')
    expect(screen.getByText('Part of:')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
  })

  it('leaf product shows direct metrics without composition layer', () => {
    wrap('synapse')
    expect(screen.queryByRole('button', { name: /component in scope/i })).not.toBeInTheDocument()
    expect(screen.getByText('Coverage')).toBeInTheDocument()
  })

  it('shows in-scope count excluding excluded leaves in button label', () => {
    const portfolioWithExcluded = portfolioWithComposition({
      composition: [
        {
          product_id: 'synapse',
          repo: 'canonical/synapse-operator',
          medal: 'bronze',
          applicability: 'scored',
          metrics: { coverage_pct: 65 },
          excluded_from_parent_medal: false,
        },
        {
          product_id: 'saml',
          repo: 'canonical/saml-operator',
          medal: 'gold',
          applicability: 'scored',
          metrics: {},
          excluded_from_parent_medal: true,
        },
      ] as LeafDimensionResult[],
    })
    mockWith(portfolioWithExcluded)
    wrap('matrix')
    // 2 total leaves, 1 excluded → only 1 in scope
    expect(screen.getByText(/1 component in scope/i)).toBeInTheDocument()
  })
})
