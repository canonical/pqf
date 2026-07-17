import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { HashRouter } from 'react-router'
import GlobalNav from './GlobalNav'

describe('GlobalNav', () => {
  it('renders PQF logo title', () => {
    render(
      <HashRouter>
        <GlobalNav />
      </HashRouter>
    )
    expect(screen.getByText('PQF')).toBeInTheDocument()
  })

  it('renders Portfolio, Products, and About nav links', () => {
    render(
      <HashRouter>
        <GlobalNav />
      </HashRouter>
    )
    expect(screen.getByRole('link', { name: 'Portfolio' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Products' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'About' })).toBeInTheDocument()
  })

  it('links Docs to the canonical repo docs tree', () => {
    render(
      <HashRouter>
        <GlobalNav />
      </HashRouter>
    )
    expect(screen.getByRole('link', { name: 'Docs ↗' })).toHaveAttribute(
      'href',
      'https://github.com/canonical/pqf/tree/main/docs',
    )
  })
})
