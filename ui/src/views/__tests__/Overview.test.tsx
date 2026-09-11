import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Overview from '../Overview'
import type { Portfolio, Product } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

vi.mock('../../providers/FrameworkVersionProvider', () => ({
  useFrameworkVersion: () => ({
    current: { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active', description: '', portfolio_url: '', generated_at: '', contract_digest: 'digest-v0' },
    versions: [],
  }),
}))

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
      meets_target: false,
      composed_of: null,
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: { result: 'silver', meets_target: false, metrics: {}, composition: null },
        documentation: {
          result: 'bronze',
          meets_target: false,
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
  framework: { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active', description: 'Current framework revision' },
  contract_digest: 'digest-v0',
  source_revision: 'abc123',
  implementation_fingerprints: {},
  compliance_summary: { total: 1, meeting_target: 0, below_target: 1, insufficient_data: 0 },
}

const rootProduct: Product = {
  id: 'matrix', product_type: 'root', name: 'Matrix', lifecycle: 'stable',
  target_result: 'gold', current_result: 'bronze', squad: 'americas',
  is_portfolio_entry: true, meets_target: false, context_refs: [], parent_product_ids: [],
  composed_of: [{ product_id: 'synapse', excluded_from_parent_medal: false }],
  dimensions: {},
}

const inlineLeaf: Product = {
  id: 'synapse', product_type: 'charm', name: 'Synapse', lifecycle: 'stable',
  target_result: 'gold', current_result: 'gold', squad: '',
  is_portfolio_entry: false, meets_target: true, context_refs: [], parent_product_ids: ['matrix'],
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
    expect(screen.getByRole('heading', { name: /products overview/i })).toBeInTheDocument()
  })

  it('renders product name as link', () => {
    wrap(<Overview />)
    const links = screen.getAllByRole('link', { name: 'Matrix (Synapse)' })
    expect(links.length).toBeGreaterThan(0)
  })

  it('scopes product and dimension links to the selected framework version', () => {
    wrap(<Overview />)
    const productLinks = screen.getAllByRole('link', { name: 'Matrix (Synapse)' })
    productLinks.forEach(link => expect(link).toHaveAttribute('href', '/v0/products/matrix'))
    expect(screen.getByRole('link', { name: /about this framework/i })).toHaveAttribute('href', '/v0/about')
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
              meets_target: false,
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

  it('shows the compliance summary as meeting_target / total from the payload', () => {
    wrap(<Overview />)
    expect(screen.getByText('0 / 1')).toBeInTheDocument()
  })

  it('guards the meeting-target summary colour for an empty portfolio instead of showing a false alarm colour', () => {
    // total: 0, meeting_target: 0 must not render the "0 met" alarm colour used when products
    // exist but none meet target — there is nothing to be below target on.
    vi.mocked(usePortfolio).mockReturnValue({
      data: {
        ...mockPortfolio,
        products: [] as Product[],
        compliance_summary: { total: 0, meeting_target: 0, below_target: 0, insufficient_data: 0 },
      },
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)

    wrap(<Overview />)
    const summary = screen.getByText('0 / 0')
    expect(summary).toHaveStyle({ color: '#333' })
  })

  it('does not recompute the summary from the products list when it disagrees with compliance_summary', () => {
    // compliance_summary intentionally disagrees with the products array below, to prove Overview
    // renders the payload field verbatim rather than recomputing it in TypeScript.
    vi.mocked(usePortfolio).mockReturnValue({
      data: {
        ...mockPortfolio,
        compliance_summary: { total: 5, meeting_target: 4, below_target: 1, insufficient_data: 0 },
      },
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)

    wrap(<Overview />)
    expect(screen.getByText('4 / 5')).toBeInTheDocument()
  })

  it('shows a compact squad indicator in the products table without a separate status column', () => {
    const { container } = wrap(<Overview />)

    expect(screen.getByRole('columnheader', { name: 'Squad' })).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Lifecycle' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Status' })).not.toBeInTheDocument()
    expect(screen.getByText('AMER')).toBeInTheDocument()
    // Result + target medal badges are the row semantics; no second "Meets/Below target" vocabulary
    // within the products table itself (the portfolio summary card above is allowed to say
    // "Below target" as an aggregate label).
    const productsTable = container.querySelectorAll('table')[0]
    expect(within(productsTable).queryByText('Meets target')).not.toBeInTheDocument()
    expect(within(productsTable).queryByText('Below target')).not.toBeInTheDocument()
    expect(screen.queryByText(/remediating/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/overdue/i)).not.toBeInTheDocument()
  })

  it('marks rows that do not meet target with a non-visible accessibility attribute, not a second badge', () => {
    const { container } = wrap(<Overview />)

    const productsTable = container.querySelectorAll('table')[0]
    const row = within(productsTable).getByRole('link', { name: 'Matrix (Synapse)' }).closest('tr')
    expect(row).not.toBeNull()
    // mockPortfolio's matrix product has meets_target: false
    expect(row).toHaveAttribute('data-meets-target', 'false')
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
})
