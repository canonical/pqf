import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import MetricsList from './MetricsList'

describe('MetricsList', () => {
  it('renders each metric key and value', () => {
    render(<MetricsList metrics={{ coverage_pct: { state: 'measured', value: 87 }, latest_build_passing: { state: 'measured', value: true } }} />)
    expect(screen.getByText('Coverage')).toBeInTheDocument()
    expect(screen.getByText('87')).toBeInTheDocument()
    expect(screen.getByText('Build passing')).toBeInTheDocument()
    expect(screen.getByText('✓')).toBeInTheDocument()
  })

  it('renders boolean false as text', () => {
    render(<MetricsList metrics={{ enabled: { state: 'measured', value: false } }} />)
    expect(screen.getByText('✗')).toBeInTheDocument()
  })

  it('renders null as missing data without applying a threshold', () => {
    render(
      <MetricsList
        metrics={{ avg_triage_days: { state: 'insufficient_data', value: null, reason: 'No issues' } }}
        thresholds={{ avg_triage_days: { operator: '<=', value: 3 } }}
      />,
    )

    expect(screen.getByText('Avg. triage')).toBeInTheDocument()
    expect(screen.getByText('Insufficient data')).toHaveAccessibleDescription('No issues')
    expect(screen.queryByText(/\/ 3/)).not.toBeInTheDocument()
  })

  it('shows threshold comparisons for numeric metrics', () => {
    render(
      <MetricsList
        metrics={{ coverage_pct: { state: 'measured', value: 87 } }}
        thresholds={{ coverage_pct: { operator: '>=', value: 90 } }}
      />
    )

    expect(screen.getByText('Coverage')).toBeInTheDocument()
    const thresholdValue = screen.getByText('87').parentElement
    expect(thresholdValue).toHaveTextContent('87 / 90')
    expect(thresholdValue).toHaveStyle({ color: '#c7162b', fontWeight: '600' })
  })

  it('uses metadata labels and colors booleans by threshold result', () => {
    render(
      <MetricsList
        metrics={{ latest_build_passing: { state: 'measured', value: true }, has_security: { state: 'measured', value: false } }}
        thresholds={{
          latest_build_passing: { operator: '==', value: true },
          has_security: { operator: '==', value: true },
        }}
        metaOutputs={{
          latest_build_passing: { label: 'CI build', description: 'Main build status', type: 'boolean', range: 'true/false' },
          has_security: { label: 'Security policy', description: 'SECURITY file present', type: 'boolean', range: 'true/false' },
        }}
      />
    )

    expect(screen.getByText('CI build')).toBeInTheDocument()
    expect(screen.getByText('Security policy')).toBeInTheDocument()
    expect(screen.getByText('✓').parentElement).toHaveStyle({ color: '#237a36', fontWeight: '600' })
    expect(screen.getByText('✗').parentElement).toHaveStyle({ color: '#c7162b', fontWeight: '600' })
  })
})
