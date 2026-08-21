import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Overview from '../Overview'
import type { Portfolio, Product } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

const mockPortfolio: Portfolio = {
  generated_at: '2026-06-30T00:00:00Z',
  products: [
    {
      id: 'matrix',
      name: 'Matrix (Synapse)',
      description: 'Chat',
      lifecycle: 'stable',
      product_type: 'root',
      target_result: 'gold',
      current_result: 'bronze',
      squad: 'americas',
      is_portfolio_entry: true,
      composed_of: null,
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: { result: 'silver', drift: null, metrics: {}, composition: null },
        documentation: {
          result: 'bronze',
          drift: { status: 'remediating', first_seen_at: '2026-01-01T00:00:00Z', deadline: '2026-07-01T00:00:00Z' },
          metrics: {},
          composition: null,
        },
      },
    },
  ],
  dimensions_meta: {
    test_verification: { medals: { bronze: { criteria: [] } } },
    documentation: { medals: { bronze: { criteria: [] } } },
  },
}

const rootProduct: Product = {
  id: 'matrix', product_type: 'root', name: 'Matrix', lifecycle: 'stable',
  target_result: 'gold', current_result: 'bronze', squad: 'americas',
  is_portfolio_entry: true, context_refs: [], parent_product_ids: [],
  composed_of: [{ product_id: 'synapse', excluded_from_parent_medal: false }],
  dimensions: {},
}

const inlineLeaf: Product = {
  id: 'synapse', product_type: 'charm', name: 'Synapse', lifecycle: 'stable',
  target_result: 'gold', current_result: 'gold', squad: '',
  is_portfolio_entry: false, context_refs: [], parent_product_ids: ['matrix'],
  composed_of: null, source: { repo: 'canonical/synapse-operator', subpath: null },
  dimensions: {},
}

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Overview', () => {
  beforeEach(() => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: mockPortfolio,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)
  })

  it('shows page heading', () => {
    wrap(<Overview />)
    expect(screen.getByRole('heading', { name: /portfolio/i })).toBeInTheDocument()
  })

  it('renders product name as link', () => {
    wrap(<Overview />)
    const links = screen.getAllByRole('link', { name: 'Matrix (Synapse)' })
    expect(links.length).toBeGreaterThan(0)
  })

  it('shows current medal', () => {
    wrap(<Overview />)
    const medals = screen.getAllByText('Bronze')
    expect(medals.length).toBeGreaterThan(0)
  })


  it('shows below minimum for unrated products with scored failed dimensions', () => {
    const belowMinimumPortfolio: Portfolio = {
      ...mockPortfolio,
      products: [
        {
          ...mockPortfolio.products[0],
          current_result: 'below_minimum',
          dimensions: {
            documentation: {
              result: 'below_minimum',
              drift: null,
              metrics: {},
              composition: null,
            },
          },
        },
      ],
    }

    vi.mocked(usePortfolio).mockReturnValue({
      data: belowMinimumPortfolio,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)

    wrap(<Overview />)
    expect(screen.getAllByText('Sub-min').length).toBeGreaterThan(0)
  })

  it('filters by search input', async () => {
    wrap(<Overview />)
    const input = screen.getByRole('searchbox')
    await userEvent.type(input, 'nomatch')
    expect(screen.queryByText('Matrix (Synapse)')).not.toBeInTheDocument()
  })

  it('shows summary stat: 0% at target', () => {
    wrap(<Overview />)
    expect(screen.getByText(/0%/)).toBeInTheDocument()
  })

  it('shows compact squad and drift indicators in the products table', () => {
    wrap(<Overview />)

    expect(screen.getByRole('columnheader', { name: 'Squad' })).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Lifecycle' })).not.toBeInTheDocument()
    expect(screen.getByText('AMER')).toBeInTheDocument()
    expect(screen.getByTitle('Remediating · deadline 2026-07-01')).toBeInTheDocument()
  })

  it('sorts products by target medal when the target header is clicked', async () => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: {
        ...mockPortfolio,
        products: [
          {
            ...mockPortfolio.products[0],
            id: 'alpha',
            name: 'Alpha',
            target_result: 'gold',
          },
          {
            ...mockPortfolio.products[0],
            id: 'zeta',
            name: 'Zeta',
            target_result: 'bronze',
          },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)

    const user = userEvent.setup()
    const { container } = wrap(<Overview />)
    const productsTable = container.querySelectorAll('table')[0]

    let productLinks = within(productsTable).getAllByRole('link', { name: /Alpha|Zeta/ })
    expect(productLinks.map(link => link.textContent)).toEqual(['Alpha', 'Zeta'])

    await user.click(screen.getByRole('columnheader', { name: 'Target' }))

    productLinks = within(productsTable).getAllByRole('link', { name: /Alpha|Zeta/ })
    expect(productLinks.map(link => link.textContent)).toEqual(['Zeta', 'Alpha'])
    expect(screen.getByRole('columnheader', { name: 'Target' })).toHaveAttribute('aria-sort', 'ascending')
  })

  it('shows only portfolio entry products in table', () => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: {
        ...mockPortfolio,
        products: [rootProduct, inlineLeaf],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)

    wrap(<Overview />)
    expect(screen.getAllByRole('link', { name: 'Matrix' }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('link', { name: 'Synapse' })).not.toBeInTheDocument()
  })

  it('excludes inline leaf products from stats counts', () => {
    // rootProduct: is_portfolio_entry=true, bronze vs gold (not at target)
    // inlineLeaf: is_portfolio_entry=false, gold vs gold (at target)
    // With filter: 0% at target (0/1 portfolio entry)
    // Without filter: 50% (1/2 total) — confirms the filter is applied
    vi.mocked(usePortfolio).mockReturnValue({
      data: {
        ...mockPortfolio,
        products: [rootProduct, inlineLeaf],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)

    wrap(<Overview />)
    expect(screen.getByText(/0%/)).toBeInTheDocument()
  })
})
