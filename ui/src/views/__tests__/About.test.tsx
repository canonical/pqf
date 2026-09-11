import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import About from '../About'
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
  products: [],
  dimensions_meta: {
    documentation: {
      label: 'Documentation',
      description: 'README, contributing guide, and docs quality',
      medals: { bronze: { criteria: [] } },
    },
  },
  framework: { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active', description: 'Current framework revision' },
  contract_digest: 'digest-v0',
  source_revision: 'abc123',
  implementation_fingerprints: {},
  compliance_summary: { total: 0, meeting_target: 0, below_target: 0, insufficient_data: 0 },
}

function wrap() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <About />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('About', () => {
  beforeEach(() => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: mockPortfolio,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)
  })

  it('renders page heading', () => {
    wrap()
    expect(screen.getByRole('heading', { name: /about/i })).toBeInTheDocument()
  })

  it('explains medal levels', () => {
    wrap()
    expect(screen.getByText(/fully compliant/i)).toBeInTheDocument()
    expect(screen.getByText(/strong quality posture/i)).toBeInTheDocument()
    expect(screen.getByText(/baseline quality/i)).toBeInTheDocument()
  })

  it('lists dimensions from portfolio metadata', () => {
    wrap()
    expect(screen.getByText('Documentation')).toBeInTheDocument()
  })

  it('links to overview', () => {
    wrap()
    expect(screen.getByRole('link', { name: /overview/i })).toBeInTheDocument()
  })

  it('scopes internal links to the selected framework version', () => {
    wrap()
    expect(screen.getByRole('link', { name: /overview/i })).toHaveAttribute('href', '/v0')
    expect(screen.getByRole('link', { name: 'Documentation' })).toHaveAttribute('href', '/v0/dimensions/documentation')
  })

  it('links framework specification to the canonical repo', () => {
    wrap()
    expect(screen.getByRole('link', { name: /full framework specification on github/i })).toHaveAttribute(
      'href',
      'https://github.com/canonical/pqf/blob/main/docs/superpowers/specs/2026-06-29-pqf-tool-design.md',
    )
  })

  it('includes sub-minimum in medal levels table', () => {
    wrap()
    // The medal levels table should include a row for "sub-minimum" or similar terminology
    // showing when a dimension was measured but failed to meet minimum criteria
    const medalTable = screen.getByRole('heading', { name: /medal levels/i }).closest('div')
    expect(medalTable?.textContent).toMatch(/sub.?min|below.?minimum/i)
  })
})
