import { render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DimensionDetail from '../DimensionDetail'
import type { Portfolio } from '../../types'

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
      product_type: 'root',
      name: 'Matrix (Synapse)',
      description: 'Chat',
      lifecycle: 'stable',
      target_result: 'gold',
      current_result: 'bronze',
      squad: 'americas',
      is_portfolio_entry: true,
      meets_target: true,
      composed_of: [{ product_id: 'synapse', excluded_from_parent_medal: false }],
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        documentation: { result: 'bronze', meets_target: true, metrics: {}, composition: [] },
      },
    },
    {
      id: 'synapse',
      product_type: 'charm',
      name: 'Synapse Charm',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'silver',
      squad: '',
      is_portfolio_entry: false,
      meets_target: true,
      composed_of: null,
      context_refs: [],
      parent_product_ids: ['matrix'],
      source: { repo: 'canonical/synapse-operator', subpath: null },
      dimensions: {
        documentation: {
          result: 'silver',
          meets_target: true,
          metrics: {},
          composition: null,
        },
      },
    },
    {
      id: 'landscape',
      product_type: 'root',
      name: 'Landscape',
      description: 'Management',
      lifecycle: 'stable',
      target_result: 'gold',
      current_result: 'silver',
      squad: 'emea',
      is_portfolio_entry: true,
      meets_target: false,
      composed_of: [],
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        documentation: {
          result: 'silver',
          meets_target: false,
          metrics: {},
          composition: [],
        },
      },
    },
    {
      id: 'anbox',
      product_type: 'root',
      name: 'Anbox Cloud',
      description: 'Streaming',
      lifecycle: 'stable',
      target_result: 'gold',
      current_result: 'below_minimum',
      squad: 'apac',
      is_portfolio_entry: true,
      meets_target: false,
      composed_of: [],
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        documentation: {
          result: 'below_minimum',
          meets_target: false,
          metrics: {},
          composition: [],
        },
      },
    },
  ],
  dimensions_meta: {
    documentation: {
      label: 'Documentation',
      description: 'README, contributing guide, and docs quality',
      outputs: {
        has_readme: {
          label: 'README present',
          description: 'A README.md exists in the primary component repository.',
          type: 'boolean',
          range: '',
          ai_assisted: false,
        },
        diataxis_coverage: {
          label: 'Diátaxis coverage',
          description: 'Number of Diátaxis doc types present.',
          type: 'number',
          range: '0–4',
          ai_assisted: true,
        },
        style_linter_passing: {
          label: 'Style linter passing',
          description: 'Documentation passes the Canonical Vale style linter with no errors.',
          type: 'boolean',
          range: '',
          ai_assisted: true,
        },
      },
      medals: {
        bronze: { criteria: ['has_readme == true'] },
        silver: { criteria: ['diataxis_coverage >= 4'] },
        gold: { criteria: ['style_linter_passing == true'] },
      },
    },
  },
  framework: { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active', description: 'Current framework revision' },
  contract_digest: 'digest-v0',
  source_revision: 'abc123',
  implementation_fingerprints: {},
  compliance_summary: { total: 3, meeting_target: 1, below_target: 2, insufficient_data: 0 },
}

function wrap(id: string) {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/dimensions/${id}`]}>
        <Routes>
          <Route path="/dimensions/:id" element={<DimensionDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DimensionDetail', () => {
  beforeEach(() => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: mockPortfolio,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)
  })

  it('renders dimension label as heading', () => {
    wrap('documentation')
    expect(screen.getByRole('heading', { name: 'Documentation' })).toBeInTheDocument()
  })

  it('renders metrics card with scoring badges', () => {
    wrap('documentation')
    const metricsCard = screen.getByRole('heading', { name: 'Metrics' }).closest('.p-card') as HTMLElement
    expect(metricsCard).not.toBeNull()
    expect(within(metricsCard).getByText('Diátaxis coverage')).toBeInTheDocument()
    expect(within(metricsCard).getByText('0–4')).toBeInTheDocument()
    expect(within(metricsCard).getByText('Deterministic')).toBeInTheDocument()
    expect(within(metricsCard).getAllByText('✦ AI')).toHaveLength(2)
  })

  it('renders rubric criterion labels and keeps descriptions on hover only', () => {
    wrap('documentation')
    const rubricCard = screen.getByRole('heading', { name: 'Medal rubric' }).closest('.p-card') as HTMLElement
    expect(rubricCard).not.toBeNull()
    expect(within(rubricCard).getByText('README present')).toBeInTheDocument()
    const criterion = within(rubricCard).getByText('has_readme == true').closest('li')
    expect(criterion).toHaveAttribute('title', 'A README.md exists in the primary component repository.')
    expect(screen.getAllByText('A README.md exists in the primary component repository.')).toHaveLength(1)
  })

  it('renders a target column with medal badges for each product row', () => {
    wrap('documentation')
    expect(screen.getByRole('columnheader', { name: 'Target' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
    const rootRow = screen.getByRole('link', { name: 'Matrix (Synapse)' }).closest('tr')
    expect(rootRow).toHaveTextContent('Gold')
    expect(rootRow).toHaveTextContent('Bronze')

    const leafRow = screen.getByRole('link', { name: '↳ Synapse Charm' }).closest('tr')
    expect(within(leafRow as HTMLElement).getAllByText('Silver')).toHaveLength(2)
  })

  it('does not render data-meets-target attributes anywhere in the dimension detail view', () => {
    const { container } = wrap('documentation')
    expect(container.querySelectorAll('[data-meets-target]')).toHaveLength(0)
  })

  it('renders product scores grouped by root with nested leaf rows', () => {
    wrap('documentation')
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toBeInTheDocument()
    expect(screen.getByText('↳ Synapse Charm')).toBeInTheDocument()
  })

  it('scopes product links and the back-to-overview link to the selected framework version', () => {
    wrap('documentation')
    expect(screen.getByRole('link', { name: '← Overview' })).toHaveAttribute('href', '/v0')
    expect(screen.getByRole('link', { name: 'Matrix (Synapse)' })).toHaveAttribute('href', '/v0/products/matrix')
  })

  it('shows not found for unknown dimension', () => {
    wrap('unknown')
    expect(screen.getByText(/not found/i)).toBeInTheDocument()
  })

  it('scopes the not-found recovery link to the selected framework version', () => {
    wrap('unknown')
    expect(screen.getByRole('link', { name: /back to overview/i })).toHaveAttribute('href', '/v0')
  })
})
