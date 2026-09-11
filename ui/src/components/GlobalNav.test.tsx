import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import GlobalNav from './GlobalNav'
import type { FrameworkVersionSummary } from '../types'

vi.mock('../providers/FrameworkVersionProvider', () => {
  const versions: FrameworkVersionSummary[] = [
    {
      id: 'v1',
      sequence: 1,
      label: 'PQF V1',
      status: 'upcoming',
      description: 'Next framework revision',
      portfolio_url: 'versions/v1/portfolio.json',
      generated_at: '2026-09-05T12:00:00Z',
      contract_digest: 'digest-v1',
    },
    {
      id: 'v0',
      sequence: 0,
      label: 'PQF V0',
      status: 'active',
      description: 'Current framework revision',
      portfolio_url: 'versions/v0/portfolio.json',
      generated_at: '2026-06-01T00:00:00Z',
      contract_digest: 'digest-v0',
    },
  ]
  return {
    useFrameworkVersion: () => ({ current: versions[1], versions }),
  }
})

function wrap(ui: React.ReactElement, initialEntries: string[] = ['/v0']) {
  return render(<MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>)
}

describe('GlobalNav', () => {
  it('renders PQF logo title', () => {
    wrap(<GlobalNav />)
    expect(screen.getByText('PQF')).toBeInTheDocument()
  })

  it('renders Overview, Products, and About nav links scoped to the selected version', () => {
    wrap(<GlobalNav />)
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/v0')
    expect(screen.getByRole('link', { name: 'Products' })).toHaveAttribute('href', '/v0/products')
    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('href', '/v0/about')
  })

  it('links Docs to the canonical repo docs tree', () => {
    wrap(<GlobalNav />)
    expect(screen.getByRole('link', { name: 'Docs ↗' })).toHaveAttribute(
      'href',
      'https://github.com/canonical/pqf/tree/main/docs',
    )
  })

  it('renders the version selector', () => {
    wrap(<GlobalNav />)
    expect(screen.getByRole('combobox', { name: /framework version/i })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /framework version/i })).toHaveValue('v0')
  })
})
