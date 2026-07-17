import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import RootMetricsList from './RootMetricsList'
import type { LeafDimensionResult, OutputMeta } from '../types'

const OUTPUTS: Record<string, OutputMeta> = {
  coverage_pct: { label: 'Coverage', description: 'Test coverage %', type: 'number', range: '0-100' },
  latest_build_passing: { label: 'Build passing', description: 'Latest build', type: 'boolean', range: 'true/false' },
}

const THRESHOLDS = {
  coverage_pct: { operator: '>=', value: 70 },
  latest_build_passing: { operator: '==', value: true },
}

function leaf(
  id: string,
  metrics: Record<string, string | number | boolean>,
  excluded = false,
): LeafDimensionResult {
  return {
    product_id: id,
    repo: `canonical/${id}`,
    medal: 'unrated' as const,
    applicability: 'scored' as const,
    metrics,
    excluded_from_parent_medal: excluded,
  }
}

const LOW_LEAF = leaf('synapse', { coverage_pct: 0, latest_build_passing: true })
const HIGH_LEAF = leaf('saml', { coverage_pct: 70, latest_build_passing: false })

describe('RootMetricsList', () => {
  it('renders metric labels from metaOutputs', () => {
    render(
      <RootMetricsList composition={[LOW_LEAF]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    expect(screen.getByText('Coverage')).toBeInTheDocument()
    expect(screen.getByText('Build passing')).toBeInTheDocument()
  })

  it('shows worst coverage value (low for >=) with threshold denominator', () => {
    render(
      <RootMetricsList composition={[LOW_LEAF, HIGH_LEAF]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    // worst coverage = 0 (synapse); threshold >=70 → shown as "0 / 70"
    const dl = screen.getByText('Coverage').closest('dl')!
    expect(dl).toHaveTextContent('0')
    expect(dl).toHaveTextContent('/ 70')
  })

  it('shows expand button when leaves disagree on a metric', () => {
    render(
      <RootMetricsList composition={[LOW_LEAF, HIGH_LEAF]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    const expandBtns = screen.getAllByRole('button', { name: /2 leaves/i })
    expect(expandBtns.length).toBeGreaterThan(0)
  })

  it('does not show expand button when all leaves agree on a metric', () => {
    const agreed = [
      leaf('a', { coverage_pct: 90, latest_build_passing: true }),
      leaf('b', { coverage_pct: 90, latest_build_passing: true }),
    ]
    render(
      <RootMetricsList composition={agreed} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    expect(screen.queryByRole('button', { name: /leaves/i })).not.toBeInTheDocument()
  })

  it('expands to show per-leaf values on button click', () => {
    render(
      <RootMetricsList composition={[LOW_LEAF, HIGH_LEAF]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    const btn = screen.getAllByRole('button', { name: /2 leaves/i })[0]
    fireEvent.click(btn)
    expect(screen.getByText('synapse')).toBeInTheDocument()
    expect(screen.getByText('saml')).toBeInTheDocument()
  })

  it('excludes leaves with excluded_from_parent_medal=true from in-scope count', () => {
    const excluded = leaf('saml', { coverage_pct: 70, latest_build_passing: false }, true)
    render(
      <RootMetricsList composition={[LOW_LEAF, excluded]} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    // only 1 leaf in scope → no expand button (all agree trivially)
    expect(screen.queryByRole('button', { name: /leaves/i })).not.toBeInTheDocument()
  })

  it('renders nothing when no in-scope leaves', () => {
    const allExcluded = [leaf('synapse', { coverage_pct: 0 }, true)]
    const { container } = render(
      <RootMetricsList composition={allExcluded} thresholds={THRESHOLDS} metaOutputs={OUTPUTS} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when metaOutputs is undefined', () => {
    const { container } = render(
      <RootMetricsList composition={[LOW_LEAF]} thresholds={THRESHOLDS} metaOutputs={undefined} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
