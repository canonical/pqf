import { describe, expect, it } from 'vitest'
import { validatePortfolio } from './portfolioValidation'

function artifact(metrics: unknown, composition: unknown = null) {
  return {
    framework: { id: 'v0' },
    dimensions_meta: {},
    products: [{
      id: 'sample', name: 'Sample', squad: '', lifecycle: 'stable', product_type: 'charm',
      current_result: 'gold', target_result: 'gold', meets_target: true, is_portfolio_entry: true,
      composed_of: null, context_refs: [], parent_product_ids: [],
      dimensions: { documentation: { result: 'gold', meets_target: true, metrics, composition } },
    }],
  }
}

describe('portfolio metric artifact validation', () => {
  it('accepts source-less N/A composition entries published by assembly', () => {
    expect(() => validatePortfolio(artifact({}, [{
      product_id: 'source-less', repo: null, result: 'not_applicable',
      excluded_from_parent_medal: false, metrics: {},
    }]))).not.toThrow()
  })
  it('accepts only structured states including measured empty string, zero and false', () => {
    expect(() => validatePortfolio(artifact({
      version: { state: 'measured', value: '' },
      score: { state: 'measured', value: 0 },
      enabled: { state: 'measured', value: false },
      unknown: { state: 'insufficient_data', value: null, reason: 'Missing report' },
      na: { state: 'not_applicable', value: null, reason: 'Snap product' },
    }))).not.toThrow()
  })

  it.each([null, true, 4, '', {}, { state: 'measured', value: null },
    { state: 'measured', value: [] }, { state: 'other', value: true },
    { state: 'not_applicable', value: null }, { state: 'insufficient_data', value: null, reason: '' },
    { state: 'not_applicable', value: false, reason: 'Snap product' },
  ])('rejects malformed or scalar evidence %j', outcome => {
    expect(() => validatePortfolio(artifact({ signal: outcome }))).toThrow(/Invalid portfolio/)
  })

  it('rejects scalar evidence in a composition even with valid leaf metrics', () => {
    expect(() => validatePortfolio(artifact({ signal: { state: 'measured', value: true } }, [{
      product_id: 'component', repo: 'canonical/component', result: 'gold', excluded_from_parent_medal: false,
      metrics: { signal: true },
    }]))).toThrow(/composition\[0\].metrics.signal/)
  })

  it('rejects measured values that disagree with the declared output type', () => {
    const portfolio = artifact({ uses_sphinx_stack: { state: 'measured', value: true } })
    portfolio.dimensions_meta = { documentation: {
      outputs: { uses_sphinx_stack: { label: 'Sphinx', description: 'Version', type: 'string', range: '' } },
      medals: {},
    } }
    expect(() => validatePortfolio(portfolio)).toThrow(/uses_sphinx_stack.*string/)
  })

  it.each([null, { medals: null }, { medals: { gold: { criteria: 'uses_sphinx_stack != ""' } } },
    { medals: {}, outputs: { metric: null } }])('rejects malformed dimension metadata %j', metadata => {
    const portfolio = artifact({})
    portfolio.dimensions_meta = { documentation: metadata }
    expect(() => validatePortfolio(portfolio)).toThrow(/Invalid portfolio/)
  })
})
