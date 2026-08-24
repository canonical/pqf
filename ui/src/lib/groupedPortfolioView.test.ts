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
}

describe('groupedPortfolioView', () => {
  it('builds root -> leaf grouped rows', () => {
    const rows = buildGroupedProducts(mockPortfolio)
    expect(rows).toHaveLength(1)
    expect(rows[0].root.id).toBe('discourse')
    expect(rows[0].leaves.map((leaf) => leaf.id)).toEqual(['discourse-k8s'])
  })

  it('evaluates a numeric metric against tier condition', () => {
    const result = evaluateMetricAgainstTier(['coverage_pct >= 80'], 'coverage_pct', 83)
    expect(result).toBe('pass')
  })

  it('returns na when tier does not reference metric', () => {
    const result = evaluateMetricAgainstTier(['latest_build_passing == true'], 'coverage_pct', 83)
    expect(result).toBe('na')
  })

  it('builds grouped metric distribution rows', () => {
    const groups = buildMetricDistributionRows(mockPortfolio, 'test_verification', 'coverage_pct')
    expect(groups).toHaveLength(1)
    expect(groups[0].root.product.id).toBe('discourse')
    expect(groups[0].leaves[0].value).toBe(83)
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

    expect(computeGapToTarget(80, 'silver', metric)).toBe('At target')
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

    expect(computeGapToTarget(0.1 + 0.2, 'bronze', { ...metric, medals: { bronze: { min: 0.3 } } })).toBe(
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

    expect(computeGapToTarget(75, 'silver', metric)).toBe('Below target (+5% to silver)')
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

    expect(computeGapToTarget(95, 'gold', metric)).toBe('Exceeds target')
  })

  it('returns "At target" for a boolean metric with value true', () => {
    const metric = {
      name: 'has_security_md',
      type: 'boolean',
      signal_name: 'SECURITY.md',
    } satisfies MetricDefinition

    expect(computeGapToTarget(true, 'bronze', metric)).toBe('At target')
  })

  it('returns "Below target (requires true)" for a boolean metric with value false', () => {
    const metric = {
      name: 'has_security_md',
      type: 'boolean',
      signal_name: 'SECURITY.md',
    } satisfies MetricDefinition

    expect(computeGapToTarget(false, 'bronze', metric)).toBe('Below target (requires true)')
  })

  it('returns "Below target (requires true)" when boolean metric has no data', () => {
    const metric = {
      name: 'has_security_md',
      type: 'boolean',
      signal_name: 'SECURITY.md',
    } satisfies MetricDefinition

    expect(computeGapToTarget(null, 'bronze', metric)).toBe('Below target (requires true)')
  })

  it('returns null when target medal does not include this boolean metric', () => {
    const metric = {
      name: 'has_security_md',
      type: 'boolean',
    } satisfies MetricDefinition

    expect(computeGapToTarget(true, 'bronze', metric, 'na')).toBeNull()
  })

  it('returns null when a numeric metric has no target threshold', () => {
    const metric = {
      name: 'coverage_pct',
      type: 'numeric',
      medals: {},
    } satisfies MetricDefinition

    expect(computeGapToTarget(50, 'silver', metric)).toBeNull()
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

    expect(computeGapToTarget(76.3, 'silver', metric)).toBe('Below target (+3.7% to silver)')
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
    expect(computeGapClass(75, 'silver', metric)).toBe('below_target')
  })

  it('returns not_applicable when the metric is not part of the target criteria', () => {
    expect(computeGapClass(75, 'silver', metric, 'na')).toBe('not_applicable')
  })
})
