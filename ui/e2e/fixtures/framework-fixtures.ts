import type { Page } from '@playwright/test'
import type { DimensionMeta, FrameworkVersionIndex, FrameworkVersionSummary, Portfolio, Product } from '../../src/types'

/**
 * Deterministic fixture data for the versioned-UI E2E suite. `public/framework-versions.json`
 * and `public/versions/<id>/portfolio.json` are GHA-written artifacts and are never committed to
 * the repo (see AGENTS.md), so these tests must not depend on them existing on disk. Instead,
 * every test installs Playwright route interception (`installFrameworkFixtures`) that serves this
 * fixture data for the exact fetch URLs the app requests, keeping the suite fully self-contained.
 *
 * Three versions cover every lifecycle status exercised by the spec:
 * - `v0` — active (the redirect target for bare `/` and the "current" nav context label).
 * - `v1` — upcoming (has an extra product, `orbit`, absent from `v0`, and is the deep-link target).
 * - `v-archived` — archived (only needs to be reachable via the selector/labels, not deep-linked).
 *   Deliberately not named with the substring "legacy" — that word is reserved for the retired,
 *   immutable pre-versioning `/legacy/` Pages snapshot, which must never be linked from the
 *   versioned app (see the "no legacy link" test) and is a distinct concept from an archived
 *   *framework version*.
 */

const DIMENSIONS_META: Record<string, DimensionMeta> = {
  documentation: {
    label: 'Documentation',
    description: 'Docs coverage and structure.',
    outputs: {
      diataxis_coverage: {
        label: 'Diataxis coverage',
        description: 'How many of the four Diataxis quadrants are covered.',
        type: 'numeric',
        range: '0–4',
        ai_assisted: true,
      },
    },
    medals: {
      bronze: { criteria: ['has_readme == true'] },
      silver: { criteria: ['diataxis_coverage >= 4'] },
    },
  },
  test_verification: {
    label: 'Test verification',
    description: 'Automated test coverage and stability.',
    outputs: {
      coverage_pct: {
        label: 'Coverage %',
        description: 'Line coverage percentage from the latest test run.',
        type: 'numeric',
        range: '0–100',
      },
    },
    medals: {
      bronze: { criteria: ['coverage_pct >= 70'] },
      silver: { criteria: ['coverage_pct >= 80'] },
    },
  },
}

function matrixProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 'matrix',
    product_type: 'root',
    name: 'Matrix (Synapse)',
    description: 'Chat platform',
    lifecycle: 'stable',
    current_result: 'bronze',
    target_result: 'silver',
    squad: 'americas',
    is_portfolio_entry: true,
    composed_of: null,
    context_refs: [],
    parent_product_ids: [],
    meets_target: false,
    dimensions: {
      documentation: { result: 'bronze', meets_target: false, metrics: { diataxis_coverage: 2 }, composition: null },
      test_verification: { result: 'silver', meets_target: true, metrics: { coverage_pct: 82 }, composition: null },
    },
    ...overrides,
  }
}

/** `orbit` exists only in the `v1` fixture portfolio — it must never appear under `v0`. */
function orbitProduct(): Product {
  return {
    id: 'orbit',
    product_type: 'root',
    name: 'Orbit',
    description: 'V1-only product',
    lifecycle: 'experimental',
    current_result: 'insufficient_data',
    target_result: 'bronze',
    squad: 'emea',
    is_portfolio_entry: true,
    composed_of: null,
    context_refs: [],
    parent_product_ids: [],
    meets_target: false,
    dimensions: {
      documentation: { result: 'insufficient_data', meets_target: false, metrics: {}, composition: null },
      test_verification: { result: 'insufficient_data', meets_target: false, metrics: {}, composition: null },
    },
  }
}

function buildPortfolio(version: FrameworkVersionSummary, products: Product[]): Portfolio {
  const metTarget = products.filter(p => p.meets_target).length
  return {
    generated_at: version.generated_at,
    products,
    dimensions_meta: DIMENSIONS_META,
    framework: {
      id: version.id,
      sequence: version.sequence,
      label: version.label,
      status: version.status,
      description: version.description,
    },
    contract_digest: version.contract_digest,
    source_revision: 'fixture-revision',
    implementation_fingerprints: {},
    compliance_summary: {
      total: products.length,
      meeting_target: metTarget,
      below_target: products.length - metTarget,
      insufficient_data: 0,
    },
  }
}

export const V0: FrameworkVersionSummary = {
  id: 'v0',
  sequence: 0,
  label: 'PQF V0',
  status: 'active',
  description: 'Current framework revision.',
  portfolio_url: 'versions/v0/portfolio.json',
  generated_at: '2026-01-15T00:00:00Z',
  contract_digest: 'digest-v0',
}

export const V1: FrameworkVersionSummary = {
  id: 'v1',
  sequence: 1,
  label: 'PQF V1',
  status: 'upcoming',
  description: 'Next framework revision, in planning.',
  portfolio_url: 'versions/v1/portfolio.json',
  generated_at: '2026-02-20T00:00:00Z',
  contract_digest: 'digest-v1',
}

export const V_ARCHIVED: FrameworkVersionSummary = {
  id: 'v-archived',
  sequence: -1,
  label: 'PQF Archived 2025',
  status: 'archived',
  description: 'Archived framework revision, frozen for historical reference.',
  portfolio_url: 'versions/v-archived/portfolio.json',
  generated_at: '2025-01-01T00:00:00Z',
  contract_digest: 'digest-archived',
}

export const FRAMEWORK_VERSION_INDEX: FrameworkVersionIndex = {
  versions: [V0, V1, V_ARCHIVED],
}

export const PORTFOLIO_V0: Portfolio = buildPortfolio(V0, [matrixProduct()])
export const PORTFOLIO_V1: Portfolio = buildPortfolio(V1, [matrixProduct(), orbitProduct()])
export const PORTFOLIO_ARCHIVED: Portfolio = buildPortfolio(V_ARCHIVED, [matrixProduct({ current_result: 'gold', meets_target: true })])

/**
 * Installs Playwright route interception for the framework-version index and every version's
 * portfolio, so the app renders deterministic fixture data with no dependency on committed
 * `public/` artifacts. Call before `page.goto`.
 */
export async function installFrameworkFixtures(page: Page): Promise<void> {
  await page.route('**/framework-versions.json', route =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(FRAMEWORK_VERSION_INDEX) }),
  )
  await page.route('**/versions/v0/portfolio.json', route =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(PORTFOLIO_V0) }),
  )
  await page.route('**/versions/v1/portfolio.json', route =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(PORTFOLIO_V1) }),
  )
  await page.route('**/versions/v-archived/portfolio.json', route =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(PORTFOLIO_ARCHIVED) }),
  )
}
