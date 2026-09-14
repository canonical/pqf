import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import App from '../App'
import type { FrameworkVersionIndex, Portfolio } from '../types'

vi.mock('../hooks/usePortfolio')
import { usePortfolio } from '../hooks/usePortfolio'

vi.mock('../hooks/useFrameworkVersions')
import { useFrameworkVersions } from '../hooks/useFrameworkVersions'

const mockFrameworkVersions: FrameworkVersionIndex = {
  versions: [
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
  ],
}

const mockPortfolio: Portfolio = {
  generated_at: '2026-06-01T00:00:00Z',
  products: [],
  dimensions_meta: {},
  framework: { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active', description: 'Current framework revision' },
  contract_digest: 'digest-v0',
  source_revision: 'abc123',
  implementation_fingerprints: {},
  compliance_summary: { total: 0, meeting_target: 0, below_target: 0, insufficient_data: 0 },
}

function renderApp(hash: string) {
  const queryClient = new QueryClient()
  window.location.hash = hash

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

describe('App routing', () => {
  beforeEach(() => {
    vi.mocked(usePortfolio).mockReturnValue({
      data: mockPortfolio,
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof usePortfolio>)
  })

  it('redirects bare root to the active framework version', async () => {
    vi.mocked(useFrameworkVersions).mockReturnValue({
      data: mockFrameworkVersions,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useFrameworkVersions>)

    renderApp('#/')

    await waitFor(() => expect(window.location.hash).toBe('#/v0'))
    expect(await screen.findByRole('heading', { name: /overview/i })).toBeInTheDocument()
  })

  it('shows an explicit not-found state with recovery navigation to the active version for an unknown framework version', async () => {
    vi.mocked(useFrameworkVersions).mockReturnValue({
      data: mockFrameworkVersions,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useFrameworkVersions>)

    renderApp('#/does-not-exist/products')

    expect(await screen.findByText(/framework version not found/i)).toBeInTheDocument()
    const recoveryLink = screen.getByRole('link', { name: /go to the active framework version/i })
    expect(recoveryLink).toHaveAttribute('href', '#/v0')
  })

  it('offers a recovery link to the most recent version when no version is active at the bare root', async () => {
    vi.mocked(useFrameworkVersions).mockReturnValue({
      data: {
        versions: mockFrameworkVersions.versions.map(version => ({ ...version, status: 'archived' })),
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useFrameworkVersions>)

    renderApp('#/')

    expect(await screen.findByText(/no active framework version is currently published/i)).toBeInTheDocument()
    const recoveryLink = screen.getByRole('link', { name: /go to the most recent framework version/i })
    expect(recoveryLink).toHaveAttribute('href', '#/v1')
  })

  it('offers a recovery link to the most recent version when no version is active for an unknown framework version', async () => {
    vi.mocked(useFrameworkVersions).mockReturnValue({
      data: {
        versions: mockFrameworkVersions.versions.map(version => ({ ...version, status: 'archived' })),
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useFrameworkVersions>)

    renderApp('#/does-not-exist/products')

    expect(await screen.findByText(/framework version not found/i)).toBeInTheDocument()
    const recoveryLink = screen.getByRole('link', { name: /go to the most recent framework version/i })
    expect(recoveryLink).toHaveAttribute('href', '#/v1')
  })

  it('offers a retry affordance when the framework version index fails to load at the bare root', async () => {
    const refetch = vi.fn()
    vi.mocked(useFrameworkVersions).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('network down'),
      refetch,
    } as unknown as ReturnType<typeof useFrameworkVersions>)

    renderApp('#/')

    expect(await screen.findByText(/failed to load framework versions/i)).toBeInTheDocument()
    const retryButton = screen.getByRole('button', { name: /retry/i })

    const user = userEvent.setup()
    await user.click(retryButton)

    expect(refetch).toHaveBeenCalled()
  })

  it('offers a retry affordance from within a versioned route when the version index fetch errors', async () => {
    const refetch = vi.fn()
    vi.mocked(useFrameworkVersions).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('network down'),
      refetch,
    } as unknown as ReturnType<typeof useFrameworkVersions>)

    renderApp('#/v0/products')

    expect(await screen.findByText(/failed to load framework versions/i)).toBeInTheDocument()
    const retryButton = screen.getByRole('button', { name: /retry/i })

    const user = userEvent.setup()
    await user.click(retryButton)

    expect(refetch).toHaveBeenCalled()
  })
})
