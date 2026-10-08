import { describe, expect, it } from 'vitest'
import type { MetricDefinition, Portfolio } from '../types'
import {
  buildGroupedProducts,
  buildMetricDistributionRows,
  computeGapClass,
  computeGapToTarget,
  evaluateMetricAgainstTier,
} from './groupedPortfolioView'

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
      meets_target: false,
      composed_of: [{ product_id: 'discourse-k8s', excluded_from_parent_medal: false }],
      context_refs: [],
      parent_product_ids: [],
      dimensions: {
        test_verification: {
          result: 'bronze',
          meets_target: false,
          metrics: {},
          composition: [
            {
              product_id: 'discourse-k8s',
              repo: 'canonical/discourse-k8s-operator',
              result: 'silver',
              metrics: { coverage_pct: { state: 'measured', value: 83 }, latest_build_passing: { state: 'measured', value: true } },
              excluded_from_parent_medal: false,
            },
          ],
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
      meets_target: true,
      composed_of: null,
      context_refs: [],
      parent_product_ids: ['discourse'],
      source: { repo: 'canonical/discourse-k8s-operator', subpath: null },
      dimensions: {
        test_verification: {
          result: 'silver',
          meets_target: true,
          metrics: { coverage_pct: { state: 'measured', value: 83 }, latest_build_passing: { state: 'measured', value: true } },
          composition: null,
        },
      },
    },
  ],
  dimensions_meta: {
    test_verification: {
      medals: {
        bronze: { criteria: ['coverage_pct >= 70'] },
        silver: { criteria: ['coverage_pct >= 80'] },
        gold: { criteria: ['coverage_pct >= 90'] },
      },
    },
  },
  framework: { id: 'v0', sequence: 0, label: 'PQF V0', status: 'active', description: 'Current framework revision' },
  contract_digest: 'digest-v0',
  source_revision: 'abc123',
  implementation_fingerprints: {},
  compliance_summary: { total: 1, meeting_target: 0, below_target: 1, insufficient_data: 0 },
}

describe('groupedPortfolioView', () => {
  it('compares quoted version strings as adoption, not numeric ordering', () => {
    expect(evaluateMetricAgainstTier(['uses_sphinx_stack != ""'], 'uses_sphinx_stack', { state: 'measured', value: '' })).toBe('fail')
    expect(evaluateMetricAgainstTier(['uses_sphinx_stack != ""'], 'uses_sphinx_stack', { state: 'measured', value: '2.3.0' })).toBe('pass')
    expect(computeGapToTarget({ state: 'measured', value: '2.3.0' }, 'gold', { name: 'uses_sphinx_stack', type: 'string' })).toBeNull()
  })

  it('keeps unavailable states out of tier failures and numeric gaps', () => {
    for (const state of ['not_applicable', 'insufficient_data'] as const) {
      const outcome = { state, value: null, reason: 'No relevant report' } as const
      expect(evaluateMetricAgainstTier(['coverage_pct >= 80'], 'coverage_pct', outcome)).toBe('na')
      expect(computeGapToTarget(outcome, 'gold', { name: 'coverage_pct', type: 'numeric', medals: { gold: { min: 90 } } })).toBeNull()
    }
  })

  it('does not hide an unknown component behind a measured root value', () => {
    const portfolio = structuredClone(mockPortfolio)
    const entry = portfolio.products[0].dimensions.test_verification
    entry.metrics.coverage_pct = { state: 'measured', value: 95 }
    entry.composition![0].metrics.coverage_pct = { state: 'insufficient_data', value: null, reason: 'Report missing' }
    const group = buildMetricDistributionRows(portfolio, 'test_verification', 'coverage_pct')[0]
    expect(group.root.outcome).toEqual({ state: 'insufficient_data', value: null, reason: 'Report missing' })
    expect(group.leaves[0].outcome.state).toBe('insufficient_data')
  })

  it('builds root -> leaf grouped rows', () => {
    const rows = buildGroupedProducts(mockPortfolio)
    expect(rows).toHaveLength(1)
    expect(rows[0].root.id).toBe('discourse')
    expect(rows[0].leaves.map((leaf) => leaf.id)).toEqual(['discourse-k8s'])
  })

  it('evaluates a numeric metric against tier condition', () => {
    const result = evaluateMetricAgainstTier(['coverage_pct >= 80'], 'coverage_pct', { state: 'measured', value: 83 })
    expect(result).toBe('pass')
  })

  it('returns na when tier does not reference metric', () => {
    const result = evaluateMetricAgainstTier(['latest_build_passing == true'], 'coverage_pct', { state: 'measured', value: 83 })
    expect(result).toBe('na')
  })

  it('builds grouped metric distribution rows', () => {
    const groups = buildMetricDistributionRows(mockPortfolio, 'test_verification', 'coverage_pct')
    expect(groups).toHaveLength(1)
    expect(groups[0].root.product.id).toBe('discourse')
    expect(groups[0].leaves[0].outcome).toEqual({ state: 'measured', value: 83 })
  })
})

describe('computeGapToTarget', () => {
  it('returns "At target" when numeric result equals the target threshold', () => {
    const metric = {
      name: 'coverage_pct',
      type: 'numeric',
      medals: {
        bronze: { min: 70 },
        silver: { min: 80 },
        gold: { min: 90 },
      },
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: 80 }, 'silver', metric)).toBe('At target')
  })

  it('returns "At target" when numeric result is equal within floating point epsilon', () => {
    const metric = {
      name: 'coverage_pct',
      type: 'numeric',
      medals: {
        bronze: { min: 70 },
        silver: { min: 80 },
        gold: { min: 90 },
      },
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: 0.1 + 0.2 }, 'bronze', { ...metric, medals: { bronze: { min: 0.3 } } })).toBe(
      'At target',
    )
  })

  it('returns "Below target (+5% to silver)" when numeric result is below the target threshold', () => {
    const metric = {
      name: 'coverage_pct',
      type: 'numeric',
      medals: {
        bronze: { min: 70 },
        silver: { min: 80 },
        gold: { min: 90 },
      },
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: 75 }, 'silver', metric)).toBe('Below target (+5% to silver)')
  })

  it('returns "Exceeds target" when numeric result exceeds the target threshold', () => {
    const metric = {
      name: 'coverage_pct',
      type: 'numeric',
      medals: {
        bronze: { min: 70 },
        silver: { min: 80 },
        gold: { min: 90 },
      },
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: 95 }, 'gold', metric)).toBe('Exceeds target')
  })

  it('returns "At target" for a boolean metric with value true', () => {
    const metric = {
      name: 'has_security_md',
      type: 'boolean',
      signal_name: 'SECURITY.md',
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: true }, 'bronze', metric)).toBe('At target')
  })

  it('returns "Below target (requires true)" for a boolean metric with value false', () => {
    const metric = {
      name: 'has_security_md',
      type: 'boolean',
      signal_name: 'SECURITY.md',
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: false }, 'bronze', metric)).toBe('Below target (requires true)')
  })

  it('does not label unknown boolean evidence as a measured failure', () => {
    const metric = {
      name: 'has_security_md',
      type: 'boolean',
      signal_name: 'SECURITY.md',
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'insufficient_data', value: null, reason: 'No evidence' }, 'bronze', metric)).toBeNull()
  })

  it('returns null when target medal does not include this boolean metric', () => {
    const metric = {
      name: 'has_security_md',
      type: 'boolean',
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: true }, 'bronze', metric, 'na')).toBeNull()
  })

  it('returns null when a numeric metric has no target threshold', () => {
    const metric = {
      name: 'coverage_pct',
      type: 'numeric',
      medals: {},
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: 50 }, 'silver', metric)).toBeNull()
  })

  it('rounds numeric gaps to one decimal place for below-target messages', () => {
    const metric = {
      name: 'coverage_pct',
      type: 'numeric',
      medals: {
        bronze: { min: 70 },
        silver: { min: 80 },
        gold: { min: 90 },
      },
    } satisfies MetricDefinition

    expect(computeGapToTarget({ state: 'measured', value: 76.3 }, 'silver', metric)).toBe('Below target (+3.7% to silver)')
  })
})

describe('computeGapClass', () => {
  const metric = {
    name: 'coverage_pct',
    type: 'numeric',
    medals: {
      bronze: { min: 70 },
      silver: { min: 80 },
      gold: { min: 90 },
    },
  } satisfies MetricDefinition

  it('returns below_target when a numeric result is below the target threshold', () => {
    expect(computeGapClass({ state: 'measured', value: 75 }, 'silver', metric)).toBe('below_target')
  })

  it('returns not_applicable when the metric is not part of the target criteria', () => {
    expect(computeGapClass({ state: 'measured', value: 75 }, 'silver', metric, 'na')).toBe('not_applicable')
  })
})
