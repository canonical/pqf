import { render, screen } from '@testing-library/react'
import { renderHook } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi } from 'vitest'
import { useVersionedPath } from './useVersionedPath'

const mockUseFrameworkVersion = vi.fn()
vi.mock('../providers/FrameworkVersionProvider', () => ({
  useFrameworkVersion: () => mockUseFrameworkVersion(),
}))

describe('useVersionedPath', () => {
  it('prefixes an app-relative path with the current framework version id', () => {
    mockUseFrameworkVersion.mockReturnValue({ current: { id: 'v0' }, versions: [] })
    const { result } = renderHook(() => useVersionedPath())

    expect(result.current('/products/matrix')).toBe('/v0/products/matrix')
    expect(result.current('/about')).toBe('/v0/about')
  })

  it('maps the bare root path to just the version root, not the framework id alone', () => {
    mockUseFrameworkVersion.mockReturnValue({ current: { id: 'v1' }, versions: [] })
    const { result } = renderHook(() => useVersionedPath())

    expect(result.current('/')).toBe('/v1')
    expect(result.current('')).toBe('/v1')
  })

  it('adds a leading slash when the given path omits one', () => {
    mockUseFrameworkVersion.mockReturnValue({ current: { id: 'v0' }, versions: [] })
    const { result } = renderHook(() => useVersionedPath())

    expect(result.current('about')).toBe('/v0/about')
  })
})

describe('VersionLink', () => {
  it('renders an anchor scoped to the current framework version', async () => {
    mockUseFrameworkVersion.mockReturnValue({ current: { id: 'v0' }, versions: [] })
    const { default: VersionLink } = await import('../components/VersionLink')

    render(
      <MemoryRouter>
        <VersionLink to="/products/matrix">Matrix</VersionLink>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Matrix' })).toHaveAttribute('href', '/v0/products/matrix')
  })
})
