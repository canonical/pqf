import type {
  DimensionEntry,
  MetricDefinition,
  Medal,
  Portfolio,
  Product,
  Result,
  MetricOutcome,
} from '../types'
import { aggregateMetric, meetsThreshold, missingMetric, parseLiteral } from './metricOutcome'

export type MetricTierStatus = 'pass' | 'fail' | 'na'
export type GapClass = 'at_target' | 'exceeds_target' | 'below_target' | 'not_applicable'

export interface GroupedRootRow {
  root: Product
  leaves: Product[]
}

export interface GroupedDimensionProductRow {
  product: Product
  entry: DimensionEntry
}

export interface GroupedDimensionRow {
  root: GroupedDimensionProductRow
  leaves: GroupedDimensionProductRow[]
}

export interface MetricDistributionRow {
  product: Product
  entry: DimensionEntry
  outcome: MetricOutcome
  bronze: MetricTierStatus
  silver: MetricTierStatus
  gold: MetricTierStatus
}

export interface MetricDistributionGroup {
  root: MetricDistributionRow
  leaves: MetricDistributionRow[]
}

const CONDITION_RE = /^(\w+)\s*(>=|<=|!=|>|<|==)\s*(.+)$/

export function buildGroupedProducts(portfolio: Portfolio): GroupedRootRow[] {
  const byId = new Map(portfolio.products.map((product) => [product.id, product]))

  return portfolio.products
    .filter((product) => product.product_type === 'root')
    .map((root) => ({
      root,
      leaves: (root.composed_of ?? [])
        .map((ref) => byId.get(ref.product_id))
        .filter((product): product is Product => Boolean(product)),
    }))
}

export function buildDimensionGroupedRows(
  portfolio: Portfolio,
  dimensionId: string,
): GroupedDimensionRow[] {
  const rootGroups = buildGroupedProducts(portfolio)
  const grouped = rootGroups
    .filter((group) => Boolean(group.root.dimensions[dimensionId]))
    .map((group) => ({
      root: {
        product: group.root,
        entry: group.root.dimensions[dimensionId],
      },
      leaves: group.leaves
        .filter((leaf) => Boolean(leaf.dimensions[dimensionId]))
        .map((leaf) => ({
          product: leaf,
          entry: leaf.dimensions[dimensionId],
        })),
    }))

  const groupedLeafIds = new Set(grouped.flatMap((group) => group.leaves.map((leaf) => leaf.product.id)))
  const groupedRootIds = new Set(grouped.map((group) => group.root.product.id))

  const ungrouped = portfolio.products
    .filter((product) => Boolean(product.dimensions[dimensionId]))
    .filter((product) => !groupedLeafIds.has(product.id) && !groupedRootIds.has(product.id))
    .map((product) => ({
      root: { product, entry: product.dimensions[dimensionId] },
      leaves: [],
    }))

  return [...grouped, ...ungrouped]
}

export function evaluateMetricAgainstTier(
  criteria: string[],
  metricKey: string,
  outcome: MetricOutcome,
): MetricTierStatus {
  const criterion = criteria.find((item) => item.startsWith(`${metricKey} `))
  if (!criterion) return 'na'
  if (outcome.state !== 'measured') return 'na'

  const match = CONDITION_RE.exec(criterion)
  if (!match) return 'fail'

  const [, , operator, rightRaw] = match
  return meetsThreshold(outcome.value, { operator, value: parseLiteral(rightRaw.trim()) }) ? 'pass' : 'fail'
}

function formatGap(gap: number): string {
  const rounded = Math.round(gap * 10) / 10
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
}

const TARGET_EPSILON = 1e-9

function isAtTarget(result: number, target: number): boolean {
  return Math.abs(result - target) <= TARGET_EPSILON
}

export function computeGapClass(
  outcome: MetricOutcome,
  targetMedal: Medal,
  metric: MetricDefinition,
  targetTierStatus?: MetricTierStatus,
): GapClass {
  if (targetTierStatus === 'na') return 'not_applicable'

  if (outcome.state !== 'measured' || metric.type === 'string') return 'not_applicable'
  const result = outcome.value

  if (metric.type === 'boolean') {
    return result === true ? 'at_target' : 'below_target'
  }

  const targetThreshold = metric.medals[targetMedal]?.min
  if (targetThreshold === undefined) return 'not_applicable'

  if (typeof result !== 'number') return 'not_applicable'
  const numericResult = result

  if (isAtTarget(numericResult, targetThreshold)) return 'at_target'
  if (numericResult > targetThreshold) return 'exceeds_target'
  return 'below_target'
}

export function computeGapToTarget(
  outcome: MetricOutcome,
  targetMedal: Medal,
  metric: MetricDefinition,
  targetTierStatus?: MetricTierStatus,
): string | null {
  const gapClass = computeGapClass(outcome, targetMedal, metric, targetTierStatus)

  if (gapClass === 'not_applicable') return null
  if (gapClass === 'at_target') return 'At target'
  if (gapClass === 'exceeds_target') return 'Exceeds target'

  if (outcome.state !== 'measured' || metric.type === 'string') return null
  const result = outcome.value

  if (metric.type === 'boolean') {
    return 'Below target (requires true)'
  }

  const targetThreshold = metric.medals[targetMedal]?.min
  if (targetThreshold === undefined) return null

  if (typeof result !== 'number') return null
  const numericResult = result
  return `Below target (+${formatGap(targetThreshold - numericResult)}% to ${targetMedal})`
}

export function isMetricApplicableToTier(
  metricKey: string,
  criteria: (string[] | Record<string, boolean> | undefined),
): boolean {
  /**
   * Check if a metric is introduced (has criteria) in a specific tier.
   * A metric is applicable if at least one criterion key/string starts with "{metricKey} ".
   */
  if (!criteria) return false
  
  if (Array.isArray(criteria)) {
    return criteria.some((criterion) => criterion.startsWith(`${metricKey} `))
  }
  
  return Object.keys(criteria).some((criterion) => criterion.startsWith(`${metricKey} `))
}

function getCompositionMetricOutcome(
  rootEntry: DimensionEntry,
  leafProductId: string,
  metricKey: string,
): MetricOutcome | undefined {
  const compositionEntry = (rootEntry.composition ?? []).find((leaf) => leaf.product_id === leafProductId)
  return compositionEntry?.metrics?.[metricKey]
}

function buildMetricRow(
  product: Product,
  entry: DimensionEntry,
  dimensionCriteria: { bronze: string[]; silver: string[]; gold: string[] },
  metricKey: string,
  outcome: MetricOutcome,
): MetricDistributionRow {
  return {
    product,
    entry,
    outcome,
    bronze: evaluateMetricAgainstTier(dimensionCriteria.bronze, metricKey, outcome),
    silver: evaluateMetricAgainstTier(dimensionCriteria.silver, metricKey, outcome),
    gold: evaluateMetricAgainstTier(dimensionCriteria.gold, metricKey, outcome),
  }
}

function metricResultFromOutcome(
  criteria: { bronze: string[]; silver: string[]; gold: string[] },
  metricKey: string,
  outcome: MetricOutcome,
): Result {
  if (outcome.state !== 'measured') return outcome.state
  const gold = evaluateMetricAgainstTier(criteria.gold, metricKey, outcome)
  const silver = evaluateMetricAgainstTier(criteria.silver, metricKey, outcome)
  const bronze = evaluateMetricAgainstTier(criteria.bronze, metricKey, outcome)
  if (gold === 'pass') return 'gold'
  if (silver === 'pass') return 'silver'
  if (bronze === 'pass') return 'bronze'
  if (gold === 'fail' || silver === 'fail' || bronze === 'fail') return 'below_minimum'
  return 'insufficient_data'
}

const METRIC_RESULT_WORST_TO_BEST: Record<Result, number> = {
  insufficient_data: 0,
  below_minimum: 1,
  bronze: 2,
  silver: 3,
  gold: 4,
  not_applicable: 5,
}

function deriveRootMetricOutcome(
  criteria: { bronze: string[]; silver: string[]; gold: string[] },
  metricKey: string,
  leafValues: MetricOutcome[],
): MetricOutcome {
  if (![...criteria.bronze, ...criteria.silver, ...criteria.gold].some(criterion => criterion.startsWith(`${metricKey} `))) {
    return aggregateMetric(leafValues)
  }
  const unknown = leafValues.find(value => value.state === 'insufficient_data')
  if (unknown) return unknown
  const candidates = leafValues.filter(value => value.state === 'measured')
  if (candidates.length === 0) return aggregateMetric(leafValues)
  return candidates.reduce((worst, candidate) => (
    METRIC_RESULT_WORST_TO_BEST[metricResultFromOutcome(criteria, metricKey, candidate)]
      < METRIC_RESULT_WORST_TO_BEST[metricResultFromOutcome(criteria, metricKey, worst)]
      ? candidate
      : worst
  ))
}

export function buildMetricDistributionRows(
  portfolio: Portfolio,
  dimensionId: string,
  metricKey: string,
): MetricDistributionGroup[] {
  const groupedRows = buildDimensionGroupedRows(portfolio, dimensionId)
  const meta = portfolio.dimensions_meta[dimensionId]
  const informational = meta?.outputs?.[metricKey]?.informational === true
  const criteria = {
    bronze: informational ? [] : meta?.medals?.bronze?.criteria ?? [],
    silver: informational ? [] : meta?.medals?.silver?.criteria ?? [],
    gold: informational ? [] : meta?.medals?.gold?.criteria ?? [],
  }
  return groupedRows.map((group) => {
    const leafValues = group.leaves.map((leaf) => (
      getCompositionMetricOutcome(group.root.entry, leaf.product.id, metricKey)
      ?? leaf.entry.metrics[metricKey] ?? missingMetric()
    ))
    const composition = group.root.entry.composition
    const inScopeValues = composition && composition.length > 0
      ? composition.filter(leaf => !leaf.excluded_from_parent_medal).map(leaf => leaf.metrics[metricKey] ?? missingMetric())
      : leafValues.filter((_, index) => {
        const leafId = group.leaves[index].product.id
        return !(group.root.product.composed_of ?? []).find(leaf => leaf.product_id === leafId)?.excluded_from_parent_medal
      })
    const unknown = inScopeValues.find(outcome => outcome.state === 'insufficient_data')
    const noScope = group.root.entry.result === 'not_applicable' && inScopeValues.length === 0
      ? { state: 'not_applicable', value: null, reason: 'No applicable component evidence for this dimension.' } as const
      : undefined
    const rootOutcome = unknown ?? group.root.entry.metrics[metricKey] ?? noScope ?? deriveRootMetricOutcome(criteria, metricKey, inScopeValues)
    return {
      root: buildMetricRow(group.root.product, group.root.entry, criteria, metricKey, rootOutcome),
      leaves: group.leaves.map((leaf, index) => buildMetricRow(leaf.product, leaf.entry, criteria, metricKey, leafValues[index])),
    }
  })
}

export const MEDAL_ORDER: Record<Medal, number> = {
  gold: 3,
  silver: 2,
  bronze: 1,
  unrated: 0,
}

export const RESULT_ORDER: Record<Result, number> = {
  gold: 6,
  silver: 5,
  bronze: 4,
  below_minimum: 3,
  insufficient_data: 2,
  not_applicable: 1,
}
