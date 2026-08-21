import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ProductsExplorer from '../ProductsExplorer'
import type { Portfolio } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

const mockPortfolio: Portfolio = {
  generated_at: '2026-06-30T00:00:00Z',
  dimensions_meta: {},
  products: [
    {
      id: 'matrix',
      name: 'Matrix (Synapse)',
      product_type: 'root',
      lifecycle: 'stable',
      target_result: 'gold',
      current_result: 'bronze',
      squad: 'americas',
      is_portfolio_entry: true,
      context_refs: [],
      parent_product_ids: [],
      composed_of: [{ product_id: 'synapse', excluded_from_parent_medal: false }],
      dimensions: {},
    },
    {
      id: 'synapse',
      name: 'Synapse Charm',
      product_type: 'charm',
      lifecycle: 'stable',
      target_result: 'gold',
      current_result: 'below_minimum',
      squad: '',
      is_portfolio_entry: false,
      context_refs: [],
      parent_product_ids: ['matrix'],
      composed_of: null,
      source: { repo: 'canonical/synapse-operator', subpath: null },
      dimensions: {},
    },
    {
      id: 'wazuh',
      name: 'Wazuh Indexer',
      product_type: 'root',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'bronze',
      squad: 'emea',
      is_portfolio_entry: true,
      context_refs: [],
      parent_product_ids: [],
      composed_of: null,
      dimensions: {},
    },
  ],
}

function wrap() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/products']}>
        <ProductsExplorer />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProductsExplorer', () => {
  beforeEach(() => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: mockPortfolio,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)
  })

  it('renders the Products heading', () => {
    wrap()
    expect(screen.getByRole('heading', { name: 'Products' })).toBeInTheDocument()
  })

  it('shows root product with a link', () => {
    wrap()
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
  })

  it('shows leaf product under its root', () => {
    wrap()
    expect(screen.getByRole('link', { name: 'Synapse Charm' })).toBeInTheDocument()
  })

  it('shows squad filter dropdown', () => {
    wrap()
    expect(screen.getByRole('combobox', { name: /filter by squad/i })).toBeInTheDocument()
  })

  it('filters root products by squad', () => {
    wrap()
    const select = screen.getByRole('combobox', { name: /filter by squad/i })
    fireEvent.change(select, { target: { value: 'emea' } })
    expect(screen.queryByRole('link', { name: 'Matrix (Synapse)' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Wazuh Indexer' })).toBeInTheDocument()
  })

  it('shows medal for root product', () => {
    wrap()
    expect(screen.getAllByText('Bronze').length).toBeGreaterThan(0)
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
        mockPortfolio.products[1],
        mockPortfolio.products[2],
      ],
    }

    vi.mocked(usePortfolio).mockReturnValue({
      data: belowMinimumPortfolio,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)

    wrap()
    expect(screen.getAllByText('Sub-min').length).toBeGreaterThan(0)
  })

  it('shows search input', () => {
    wrap()
    expect(screen.getByRole('searchbox', { name: /search products/i })).toBeInTheDocument()
  })

  it('search filters products by name', () => {
    wrap()
    const searchInput = screen.getByRole('searchbox', { name: /search products/i })
    fireEvent.change(searchInput, { target: { value: 'synapse' } })
    // Synapse Charm (leaf) matches → Matrix (Synapse) root should still be shown as context
    expect(screen.getByRole('link', { name: 'Synapse Charm' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
    // Wazuh has no match → hidden
    expect(screen.queryByRole('link', { name: 'Wazuh Indexer' })).not.toBeInTheDocument()
  })

  it('shows root as context when only a child matches search', () => {
    wrap()
    const searchInput = screen.getByRole('searchbox', { name: /search products/i })
    fireEvent.change(searchInput, { target: { value: 'synapse charm' } })
    // leaf matches exactly, root shown as context header
    expect(screen.getByRole('link', { name: 'Synapse Charm' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
  })

  it('shows "Group by parent" checkbox checked by default', () => {
    wrap()
    const cb = screen.getByRole('checkbox', { name: /group by.*parent/i })
    expect(cb).toBeChecked()
  })

  it('uncheck group by parent shows flat list', () => {
    wrap()
    const cb = screen.getByRole('checkbox', { name: /group by.*parent/i })
    fireEvent.click(cb)
    // All products still visible in flat list
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Synapse Charm' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Wazuh Indexer' })).toBeInTheDocument()
  })

  it('shows empty state message when no results match', () => {
    wrap()
    const searchInput = screen.getByRole('searchbox', { name: /search products/i })
    fireEvent.change(searchInput, { target: { value: 'zzznomatch' } })
    expect(screen.getByText(/no products match/i)).toBeInTheDocument()
  })

  it('shows result count when filters are active', () => {
    wrap()
    const searchInput = screen.getByRole('searchbox', { name: /search products/i })
    fireEvent.change(searchInput, { target: { value: 'wazuh' } })
    expect(screen.getByText(/1\s+result/i)).toBeInTheDocument()
  })

  it('uses explicit column sizing to prioritize product and repo columns', () => {
    const { container } = wrap()

    const cols = container.querySelectorAll('col')
    expect(cols).toHaveLength(6)
    expect(cols[0]).toHaveStyle({ width: '36%' })
    expect(cols[1]).toHaveStyle({ width: '7rem' })
    expect(cols[2]).toHaveStyle({ width: '7rem' })
    expect(cols[3]).toHaveStyle({ width: '7rem' })
    expect(cols[4]).toHaveStyle({ width: '6rem' })
    expect(cols[5]).toHaveStyle({ width: '26%' })
  })

  it('keeps product and repo cells overflow-safe in grouped rows', () => {
    wrap()

    const rootLink = screen.getByRole('link', { name: 'Matrix (Synapse)' })
    const leafRepoLink = screen.getByRole('link', { name: /canonical\/synapse-operator/i })

    expect(rootLink.parentElement).toHaveStyle({ minWidth: '0' })
    expect(rootLink).toHaveStyle({
      display: 'block',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    })

    expect(leafRepoLink.parentElement).toHaveStyle({ minWidth: '0' })
    expect(leafRepoLink).toHaveStyle({
      display: 'block',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    })
  })
})
