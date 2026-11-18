import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import MetricsList from './MetricsList'

describe('structured metric evidence', () => {
  it('shows measured failure reasons inline and accessibly', () => {
    const reason = 'terraform/versions.tf: ~> 0.20 permits Juju providers below 1.0.'
    render(<MetricsList
      metrics={{ uses_tf_v1_provider: { state: 'measured', value: false, reason } }}
      thresholds={{ uses_tf_v1_provider: { operator: '==', value: true } }}
    />)
    expect(screen.getByText(reason)).toBeVisible()
    expect(screen.getByLabelText('false')).toHaveAccessibleDescription(reason)
  })

  it('shows neutral unavailable evidence and its accessible reason', () => {
    render(<MetricsList metrics={{
      uses_jubilant: { state: 'not_applicable', value: null, reason: 'Snap product' },
      ci_passing: { state: 'insufficient_data', value: null, reason: 'No completed run' },
    }} />)
    expect(screen.getByText('N/A')).toHaveAccessibleDescription('Snap product')
    expect(screen.getByText('Insufficient data')).toHaveAccessibleDescription('No completed run')
  })

  it('compares string adoption without numeric coercion', () => {
    render(<MetricsList
      metrics={{ uses_sphinx_stack: { state: 'measured', value: '' } }}
      thresholds={{ uses_sphinx_stack: { operator: '!=', value: '' } }}
    />)
    expect(screen.getByText('Not adopted')).toHaveStyle({ color: '#c7162b' })
  })
})
