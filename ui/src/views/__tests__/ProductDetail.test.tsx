import { render, screen, within } from '@testing-library/react'
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
      context_refs: [
        { label: 'Synapse Operator', repo: 'canonical/synapse-operator' },
        { label: 'PostgreSQL', repo: 'canonical/postgresql-k8s-operator' },
      ],
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
        substrate_compat: {
          medal: 'unrated',
          target: 'gold',
          applicability: 'not_applicable',
          drift: null,
          metrics: { supports_juju_3: false, supports_juju_4: false, supports_ck8s: false },
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
    // multiple Bronze badges appear: product header + sub-product rows
    expect(screen.getAllByText('Bronze').length).toBeGreaterThan(0)
  })

  it('shows dimension row', () => {
    wrap('matrix')
    expect(screen.getAllByRole('link', { name: 'test verification' }).length).toBeGreaterThan(0)
  })

  it('renders not applicable dimensions as N/A', () => {
    wrap('synapse')
    const row = screen.getByRole('link', { name: 'substrate compat' }).closest('tr')
    expect(row).not.toBeNull()
    expect(row).toHaveTextContent('N/A')
  })

  it('renders scored unrated dimensions as below minimum', () => {
    const unratedPortfolio: Portfolio = {
      ...mockPortfolio,
      products: [
        {
          ...mockPortfolio.products[0],
          dimensions: {
            ...mockPortfolio.products[0].dimensions,
            documentation: {
              medal: 'unrated',
              target: 'silver',
              applicability: 'scored',
              drift: null,
              metrics: {
                readme_present: true,
                contributing_present: false,
                has_security: true,
              },
              composition: null,
            },
          },
        },
        mockPortfolio.products[1],
      ],
      dimensions_meta: {
        ...mockPortfolio.dimensions_meta,
        documentation: {
          outputs: {
            readme_present: { label: 'README', description: 'README present', type: 'boolean', range: 'true/false' },
            contributing_present: { label: 'CONTRIBUTING', description: 'Contribution guide present', type: 'boolean', range: 'true/false' },
            has_security: { label: 'SECURITY', description: 'Security policy present', type: 'boolean', range: 'true/false' },
          },
          medals: {
            bronze: { criteria: ['readme_present == true', 'contributing_present == true', 'has_security == true'] },
          },
        },
      },
    }
    mockWith(unratedPortfolio)
    wrap('matrix')

    const row = screen.getByRole('link', { name: 'documentation' }).closest('tr')
    expect(row).not.toBeNull()
    expect(row).toHaveTextContent('Below minimum')
  })

  it('renders root current medal as below minimum when a scored dimension fails bronze', () => {
    const aproxyLikePortfolio: Portfolio = {
      ...mockPortfolio,
      products: [
        {
          ...mockPortfolio.products[0],
          id: 'aproxy',
          name: 'Aproxy',
          current_medal: 'unrated',
          dimensions: {
            ...mockPortfolio.products[0].dimensions,
            documentation: {
              medal: 'unrated',
              target: 'silver',
              applicability: 'scored',
              drift: null,
              metrics: {
                readme_present: true,
                contributing_present: false,
                has_security: true,
              },
              composition: null,
            },
          },
        },
        mockPortfolio.products[1],
      ],
      dimensions_meta: {
        ...mockPortfolio.dimensions_meta,
        documentation: {
          outputs: {
            readme_present: { label: 'README', description: 'README present', type: 'boolean', range: 'true/false' },
            contributing_present: { label: 'CONTRIBUTING', description: 'Contribution guide present', type: 'boolean', range: 'true/false' },
            has_security: { label: 'SECURITY', description: 'Security policy present', type: 'boolean', range: 'true/false' },
          },
          medals: {
            bronze: { criteria: ['readme_present == true', 'contributing_present == true', 'has_security == true'] },
          },
        },
      },
    }
    mockWith(aproxyLikePortfolio)
    wrap('aproxy')

    const currentBlock = screen.getByText('CURRENT').closest('div')
    expect(currentBlock).not.toBeNull()
    expect(within(currentBlock as HTMLElement).getByText('Below minimum')).toBeInTheDocument()
  })

  it('N/A dimension evidence column shows dash instead of metric values', () => {
    wrap('synapse')
    const row = screen.getByRole('link', { name: 'substrate compat' }).closest('tr')!
    const cells = within(row).getAllByRole('cell')
    // Evidence column is the 4th cell (index 3)
    expect(cells[3]).toHaveTextContent('—')
    // Should NOT render the metric keys from the (non-empty) metrics dict
    expect(cells[3]).not.toHaveTextContent('Juju 3')
    expect(cells[3]).not.toHaveTextContent('Juju 4')
  })

  it('leaf product evidence column shows threshold-colored metrics', () => {
    wrap('synapse')
    const row = screen.getByRole('link', { name: 'test verification' }).closest('tr')!
    // coverage_pct=65, gold threshold=90 → shows "65 / 90"
    expect(row).toHaveTextContent('65 / 90')
  })

  it('renders squad as a linked GitHub team badge', () => {
    wrap('matrix')
    const squadLink = screen.getByRole('link', { name: 'AMER' })
    expect(squadLink).toHaveAttribute('href', 'https://github.com/orgs/canonical/teams/platform-engineering-amer')
    expect(squadLink).toHaveClass('p-chip')
  })

  it('removes the target column from the dimensions table and shows target thresholds in evidence', () => {
    wrap('matrix')

    const dimensionsCard = screen.getByRole('heading', { name: 'Dimensions' }).closest('.p-card') as HTMLElement
    const table = dimensionsCard.querySelector('table') as HTMLTableElement
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

  it('renders linked product from context refs', () => {
    wrap('matrix')
    expect(screen.getByRole('link', { name: 'Synapse Operator' })).toBeInTheDocument()
  })

  it('shows 404 message for unknown product', () => {
    wrap('unknown')
    expect(screen.getByText(/not found/i)).toBeInTheDocument()
  })

  it('root product shows linked chips for components in header', () => {
    wrap('matrix')
    expect(screen.getByText('COMPONENTS')).toBeInTheDocument()
    // component links navigate to leaf product pages
    const componentLinks = screen.getAllByRole('link').filter(link =>
      link.getAttribute('href')?.includes('synapse')
    )
    expect(componentLinks.length).toBeGreaterThan(0)
  })

  it('root product shows unified Dependencies card with context refs only', () => {
    wrap('matrix')
    expect(screen.getByRole('heading', { name: 'Dependencies' })).toBeInTheDocument()
    expect(screen.queryByText(/Sub-products/i)).not.toBeInTheDocument()
    // synapse-operator is a known PQF product → "Also scored by this team"
    expect(screen.getByText('Synapse Operator')).toBeInTheDocument()
    expect(screen.getByText(/Also scored by this team/i)).toBeInTheDocument()
    // postgresql is not in portfolio → "External dependencies"
    expect(screen.getByText(/PostgreSQL/i)).toBeInTheDocument()
    expect(screen.getByText(/External dependencies/i)).toBeInTheDocument()
  })

  it('renders dependency heatmap with dimension medal cells for sub-products', () => {
    wrap('matrix')
    expect(screen.getByRole('columnheader', { name: /sub-product/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /type/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /test verification/i })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Synapse Charm' }).length).toBeGreaterThan(0)
    expect(screen.getByText('charm')).toBeInTheDocument()
  })

  it('root product evidence shows metric values from composition', () => {
    mockWith(
      portfolioWithComposition({
        composition: [
          {
            product_id: 'synapse',
            repo: 'canonical/synapse-operator',
            medal: 'bronze',
            applicability: 'scored',
            metrics: { coverage_pct: 65, latest_build_passing: true },
            excluded_from_parent_medal: false,
          },
        ],
      }),
    )
    wrap('matrix')
    const row = screen.getByRole('link', { name: 'test verification' }).closest('tr')!
    // RootMetricsList should show coverage_pct 65 against gold threshold 90
    expect(row).toHaveTextContent('65')
    expect(row).toHaveTextContent('/ 90')
  })

  it('root product evidence shows per-leaf expand when leaves disagree', () => {
    mockWith(
      portfolioWithComposition({
        composition: [
          {
            product_id: 'synapse',
            repo: 'canonical/synapse-operator',
            medal: 'bronze',
            applicability: 'scored',
            metrics: { coverage_pct: 65, latest_build_passing: true },
            excluded_from_parent_medal: false,
          },
          {
            product_id: 'saml',
            repo: 'canonical/saml-operator',
            medal: 'gold',
            applicability: 'scored',
            metrics: { coverage_pct: 90, latest_build_passing: false },
            excluded_from_parent_medal: false,
          },
        ],
      }),
    )
    wrap('matrix')
    expect(screen.getAllByRole('button', { name: /2 components/i }).length).toBeGreaterThan(0)
  })

  it('excludes leaves with excluded_from_parent_medal=true from leaf count in evidence', () => {
    mockWith(
      portfolioWithComposition({
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
      }),
    )
    wrap('matrix')
    // 1 in-scope leaf → no expand button needed (no disagreement possible)
    expect(screen.queryByRole('button', { name: /components/i })).not.toBeInTheDocument()
  })

  it('leaf product shows GitHub repo link in header', () => {
    wrap('synapse')
    const link = screen.getByRole('link', { name: 'GitHub ↗' })
    expect(link).toHaveAttribute('href', 'https://github.com/canonical/synapse-operator')
  })

  it('leaf product with subpath links to subpath in GitHub', () => {
    const portfolioWithSubpath: Portfolio = {
      ...mockPortfolio,
      products: [
        mockPortfolio.products[0],
        { ...mockPortfolio.products[1], source: { repo: 'canonical/monorepo', subpath: 'my-charm' } },
      ],
    }
    mockWith(portfolioWithSubpath)
    wrap('synapse')
    const link = screen.getByRole('link', { name: 'GitHub ↗' })
    expect(link).toHaveAttribute('href', 'https://github.com/canonical/monorepo/tree/main/my-charm')
  })

  it('product without source does not show GitHub link', () => {
    wrap('matrix')
    expect(screen.queryByRole('link', { name: 'GitHub ↗' })).not.toBeInTheDocument()
  })

  it('leaf product shows Part of chip', () => {
    wrap('synapse')
    expect(screen.getByText('Part of:')).toBeInTheDocument()
    const partOfLink = screen.getAllByRole('link').find(link =>
      link.getAttribute('href')?.includes('matrix') && link.textContent?.includes('Matrix (Synapse)')
    )
    expect(partOfLink).toBeDefined()
  })

  it('leaf product shows direct metrics without composition layer', () => {
    wrap('synapse')
    expect(screen.queryByRole('button', { name: /component in scope/i })).not.toBeInTheDocument()
    expect(screen.getByText('Coverage')).toBeInTheDocument()
  })
})
