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
      target_medal: 'gold',
      current_medal: 'bronze',
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
      target_medal: 'gold',
      current_medal: 'unrated',
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
      target_medal: 'silver',
      current_medal: 'bronze',
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

  it('shows leaf product indented under its root', () => {
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
    // At least one Bronze badge should be visible
    expect(screen.getAllByText('Bronze').length).toBeGreaterThan(0)
  })
})
