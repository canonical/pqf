import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { Portfolio } from '../../types'

vi.mock('../../hooks/usePortfolio')
import { usePortfolio } from '../../hooks/usePortfolio'

const mockPortfolio: Portfolio = {
  generated_at: '2026-07-23T00:00:00Z',
  products: [
    {
      id: 'discourse',
      product_type: 'root',
      name: 'Discourse',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'bronze',
      squad: 'americas',
      is_portfolio_entry: true,
      composed_of: [{ product_id: 'discourse-k8s', excluded_from_parent_medal: false }],
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: {
          result: 'bronze',
          drift: null,
          metrics: {},
          composition: [
            {
              product_id: 'discourse-k8s',
              repo: 'canonical/discourse-k8s-operator',
              result: 'silver',
              metrics: { coverage_pct: 83, latest_build_passing: true },
              excluded_from_parent_medal: false,
            },
          ],
        },
      },
    },
    {
      id: 'aardvark',
      product_type: 'root',
      name: 'Aardvark',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'bronze',
      squad: 'americas',
      is_portfolio_entry: true,
      composed_of: [{ product_id: 'aardvark-agent', excluded_from_parent_medal: false }],
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: {
          result: 'bronze',
          drift: null,
          metrics: {},
          composition: [
            {
              product_id: 'aardvark-agent',
              repo: 'canonical/aardvark-agent',
              result: 'bronze',
              metrics: { coverage_pct: 75, latest_build_passing: false },
              excluded_from_parent_medal: false,
            },
          ],
        },
      },
    },
    {
      id: 'aardvark-agent',
      product_type: 'charm',
      name: 'Aardvark Agent',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'bronze',
      squad: '',
      is_portfolio_entry: false,
      composed_of: null,
      context_refs: [],
      parent_product_ids: ['aardvark'],
      source: { repo: 'canonical/aardvark-agent', subpath: null },
      dimensions: {
        test_verification: {
          result: 'bronze',
          drift: null,
          metrics: { coverage_pct: 75, latest_build_passing: false },
          composition: null,
        },
      },
    },
    {
      id: 'discourse-k8s',
      product_type: 'charm',
      name: 'Discourse K8s',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'silver',
      squad: '',
      is_portfolio_entry: false,
      composed_of: null,
      context_refs: [],
      parent_product_ids: ['discourse'],
      source: { repo: 'canonical/discourse-k8s-operator', subpath: null },
      dimensions: {
        test_verification: {
          result: 'silver',
          drift: null,
          metrics: { coverage_pct: 83, latest_build_passing: true },
          composition: null,
        },
      },
    },
    {
      id: 'landscape',
      product_type: 'root',
      name: 'Landscape',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'bronze',
      squad: 'emea',
      is_portfolio_entry: true,
      composed_of: [{ product_id: 'landscape-server', excluded_from_parent_medal: false }],
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: {
          result: 'bronze',
          drift: null,
          metrics: {},
          composition: [
            {
              product_id: 'landscape-server',
              repo: 'canonical/landscape-server',
              result: 'bronze',
              metrics: { coverage_pct: 75, latest_build_passing: false },
              excluded_from_parent_medal: false,
            },
          ],
        },
      },
    },
    {
      id: 'landscape-server',
      product_type: 'charm',
      name: 'Landscape Server',
      lifecycle: 'stable',
      target_result: 'silver',
      current_result: 'bronze',
      squad: '',
      is_portfolio_entry: false,
      composed_of: null,
      context_refs: [],
      parent_product_ids: ['landscape'],
      source: { repo: 'canonical/landscape-server', subpath: null },
      dimensions: {
        test_verification: {
          result: 'bronze',
          drift: null,
          metrics: { coverage_pct: 75, latest_build_passing: false },
          composition: null,
        },
      },
    },
    {
      id: 'zulu-test',
      product_type: 'charm',
      name: 'Zulu Test',
      lifecycle: 'stable',
      target_result: 'bronze',
      current_result: 'bronze',
      squad: '',
      is_portfolio_entry: false,
      composed_of: null,
      context_refs: [],
      parent_product_ids: [],
      source: { repo: 'canonical/zulu-test', subpath: null },
      dimensions: {
        test_verification: {
          result: 'silver',
          drift: null,
          metrics: { coverage_pct: 85, latest_build_passing: true, has_release_notes: true },
          composition: null,
        },
      },
    },
  ],
  dimensions_meta: {
    test_verification: {
      label: 'Test Verification',
      outputs: {
        coverage_pct: {
          label: 'Coverage',
          description: 'Coverage',
          type: 'number',
          range: '0-100',
          ai_assisted: true,
        },
        latest_build_passing: {
          label: 'Latest build passing',
          description: 'Latest build result',
          type: 'boolean',
          range: 'true/false',
          informational: true,
        },
        has_release_notes: {
          label: 'Release notes process',
          description: 'Release notes implemented',
          type: 'boolean',
          range: 'true/false',
        },
      },
      medals: {
        bronze: { criteria: ['coverage_pct >= 70', 'latest_build_passing == true'] },
        silver: { criteria: ['coverage_pct >= 80', 'has_release_notes == true'] },
        gold: { criteria: ['coverage_pct >= 90', 'has_release_notes == true'] },
      },
    },
  },
}

function wrap(path: string) {
  const queryClient = new QueryClient()
  vi.mocked(usePortfolio).mockReturnValue({
    data: mockPortfolio,
    isLoading: false,
    isError: false,
    error: null,
  } as ReturnType<typeof usePortfolio>)

  window.location.hash = `#${path}`

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

describe('MetricDistribution route', () => {
  it('renders the redesigned metric distribution header and table', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    expect(await screen.findByRole('heading', { name: /Coverage \(coverage_pct\)/i })).toBeInTheDocument()
    expect(screen.getByText('coverage_pct ≥ 70')).toBeInTheDocument()
    expect(screen.getByText('coverage_pct ≥ 80')).toBeInTheDocument()
    expect(screen.getByText('coverage_pct ≥ 90')).toBeInTheDocument()
    expect(screen.queryByText('latest_build_passing = true')).not.toBeInTheDocument()
    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent?.trim())
    expect(headers).toEqual(['Product', 'Threshold result', 'Gap to target', 'Value'])
  })

  it('hides medal criteria wall for informational metrics', async () => {
    wrap('/dimensions/test_verification/metrics/latest_build_passing')
    await screen.findByRole('heading', { name: /Latest build passing/i })
    expect(screen.queryByText('coverage_pct ≥ 70')).not.toBeInTheDocument()
    expect(screen.queryByText('coverage_pct ≥ 80')).not.toBeInTheDocument()
    expect(screen.queryByText('coverage_pct ≥ 90')).not.toBeInTheDocument()
    expect(screen.getByText(/informational metric/i)).toBeInTheDocument()
  })

  it('keeps rows alphabetical by product name', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    await screen.findByRole('heading', { name: /Coverage/i })
    const table = screen.getByRole('table')
    const productLinks = table.querySelectorAll('tbody a')
    expect(Array.from(productLinks).map((link) => link.textContent?.trim())).toEqual([
      'Aardvark',
      'Aardvark Agent',
      'Discourse',
      'Discourse K8s',
      'Landscape',
      'Landscape Server',
      'Zulu Test',
    ])
  })

  it('shows the gap to target and ai-assisted badge for metric rows', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    const leafLink = await screen.findByRole('link', { name: /discourse k8s/i })
    expect(leafLink).toBeInTheDocument()
    expect(screen.getAllByRole('cell', { name: 'Exceeds target' })).toHaveLength(3)
    expect(screen.getByText('✦ AI')).toBeInTheDocument()
  })

  it('filters rows by gap class without depending on the displayed text', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    await screen.findByRole('heading', { name: /Coverage/i })

    const gapClassSelect = screen.getByRole('combobox', { name: /gap class/i })
    fireEvent.change(gapClassSelect, { target: { value: 'below_target' } })

    expect(screen.getAllByRole('cell', { name: 'Below target (+5% to silver)' })).toHaveLength(4)
    expect(screen.queryAllByRole('cell', { name: 'Exceeds target' })).toHaveLength(0)
  })

  it('falls back to composition metrics for root rows when root metric is missing', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    await screen.findByRole('heading', { name: /Coverage/i })
    const valueCells = screen.getAllByRole('cell', { name: '83' })
    expect(valueCells).toHaveLength(2)
  })

  it('does not crash when route transitions from loading to loaded state', async () => {
    const queryClient = new QueryClient()
    window.location.hash = '#/dimensions/test_verification/metrics/coverage_pct'

    vi.mocked(usePortfolio)
      .mockReturnValueOnce({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      } as ReturnType<typeof usePortfolio>)
      .mockReturnValue({
        data: mockPortfolio,
        isLoading: false,
        isError: false,
        error: null,
      } as ReturnType<typeof usePortfolio>)

    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    )

    rerender(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('heading', { name: /Coverage/i })).toBeInTheDocument()
  })

  it('shows N/A for threshold result when metric not in product target tier', async () => {
    wrap('/dimensions/test_verification/metrics/has_release_notes')
    await screen.findByRole('heading', { name: /Release notes/i })
    
    // Zulu Test has bronze target, but has_release_notes is only in silver/gold criteria
    // So it should show N/A in the threshold result column
    const zululink = screen.getByRole('link', { name: /Zulu Test/i })
    expect(zululink).toBeInTheDocument()
    
    // Find the row for Zulu Test
    const zuluRow = zululink.closest('tr')
    const cells = zuluRow?.querySelectorAll('td')
    
    // Second cell (index 1) is the "Threshold result" column
    // It should contain 'N/A' instead of a medal badge
    const thresholdCell = cells?.[1]
    expect(thresholdCell?.textContent).toContain('N/A')
  })

  it('shows actual threshold result when metric is in product target tier', async () => {
    wrap('/dimensions/test_verification/metrics/coverage_pct')
    await screen.findByRole('heading', { name: /Coverage/i })
    
    // Zulu Test has bronze target and coverage_pct is in bronze criteria
    // So it should show actual result (silver), not N/A
    const zululink = screen.getByRole('link', { name: /Zulu Test/i })
    expect(zululink).toBeInTheDocument()
    
    // Verify that Zulu Test's row doesn't show N/A in the threshold column
    // (when metric is applicable to target tier)
    const zuluRow = zululink.closest('tr')
    const cells = zuluRow?.querySelectorAll('td')
    const thresholdCell = cells?.[1]
    
    // The cell should NOT contain 'N/A' (it should contain a medal badge or result)
    // and should NOT be empty
    expect(thresholdCell?.textContent).not.toContain('N/A')
    expect(thresholdCell?.textContent?.trim().length).toBeGreaterThan(0)
  })
})
