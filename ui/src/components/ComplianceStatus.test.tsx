import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ComplianceStatus from './ComplianceStatus'

describe('ComplianceStatus', () => {
  it('renders "Meets target" when meetsTarget is true', () => {
    render(<ComplianceStatus meetsTarget />)
    expect(screen.getByText('Meets target')).toBeInTheDocument()
  })

  it('renders "Below target" when meetsTarget is false', () => {
    render(<ComplianceStatus meetsTarget={false} />)
    expect(screen.getByText('Below target')).toBeInTheDocument()
  })

  it('applies a positive colour when meeting target', () => {
    const { container } = render(<ComplianceStatus meetsTarget />)
    expect(container.firstChild).toHaveStyle({ backgroundColor: '#0e8420' })
  })

  it('applies a negative colour when below target', () => {
    const { container } = render(<ComplianceStatus meetsTarget={false} />)
    expect(container.firstChild).toHaveStyle({ backgroundColor: '#C7162B' })
  })
})
