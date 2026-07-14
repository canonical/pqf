import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import About from '../About'
import type { Portfolio } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

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

  it('links to portfolio overview', () => {
    wrap()
    expect(screen.getByRole('link', { name: /portfolio overview/i })).toBeInTheDocument()
  })

  it('links framework specification to the canonical repo', () => {
    wrap()
    expect(screen.getByRole('link', { name: /full framework specification on github/i })).toHaveAttribute(
      'href',
      'https://github.com/canonical/pqf/blob/main/docs/superpowers/specs/2026-06-29-pqf-tool-design.md',
    )
  })
})
