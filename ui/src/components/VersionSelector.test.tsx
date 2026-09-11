import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import VersionSelector from './VersionSelector'
import FrameworkVersionProvider from '../providers/FrameworkVersionProvider'

const indexPayload = {
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

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}</div>
}

function renderSelector(initialPath: string) {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route
            path="/:frameworkVersion/*"
            element={
              <FrameworkVersionProvider>
                <VersionSelector />
                <LocationDisplay />
              </FrameworkVersionProvider>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('VersionSelector', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => indexPayload,
      }),
    )
  })

  it('marks the active version as selected by default', async () => {
    renderSelector('/v0/products/matrix')
    const select = await screen.findByRole('combobox', { name: /framework version/i })
    expect(select).toHaveValue('v0')
  })

  it('groups versions by upcoming, active, and archived status', async () => {
    renderSelector('/v0/products/matrix')
    const select = await screen.findByRole('combobox', { name: /framework version/i })
    const upcomingGroup = select.querySelector('optgroup[label="Upcoming"]')
    const activeGroup = select.querySelector('optgroup[label="Active"]')
    expect(upcomingGroup).not.toBeNull()
    expect(activeGroup).not.toBeNull()
    expect(within(upcomingGroup as HTMLElement).getByText('PQF V1')).toBeInTheDocument()
    expect(within(activeGroup as HTMLElement).getByText('PQF V0')).toBeInTheDocument()
  })

  it('navigates to the same sub-route when switching to another version', async () => {
    const user = userEvent.setup()
    renderSelector('/v0/products/matrix')
    const select = await screen.findByRole('combobox', { name: /framework version/i })

    await user.selectOptions(select, 'v1')

    expect(screen.getByTestId('location')).toHaveTextContent('/v1/products/matrix')
  })

  it('shows the refreshed timestamp when the selected version is active', async () => {
    renderSelector('/v0/products/matrix')
    await screen.findByRole('combobox', { name: /framework version/i })
    expect(screen.getByText(/Refreshed/)).toBeInTheDocument()
  })

  it('wraps the select in Canonical/Vanilla form-validation markup with a labelled control', async () => {
    renderSelector('/v0/products/matrix')
    const select = await screen.findByRole('combobox', { name: /framework version/i })

    const selectWrapper = select.closest('.p-form-validation__select-wrapper')
    expect(selectWrapper).not.toBeNull()

    const formControl = selectWrapper?.closest('.p-form__control')
    expect(formControl).not.toBeNull()

    const formGroup = formControl?.closest('.p-form-validation')
    expect(formGroup).not.toBeNull()

    expect(screen.getByText('Framework version', { selector: 'label' })).toBeInTheDocument()
  })
})
