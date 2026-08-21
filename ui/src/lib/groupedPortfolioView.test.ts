import { describe, expect, it } from 'vitest'
import type { Portfolio } from '../types'
import {
  buildGroupedProducts,
  buildMetricDistributionRows,
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
