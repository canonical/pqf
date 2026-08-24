import type {
  DimensionEntry,
  MetricDefinition,
  Medal,
  Portfolio,
  Product,
  Result,
} from '../types'

export type MetricTierStatus = 'pass' | 'fail' | 'na'
export type MetricValue = string | number | boolean | null | undefined
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
  value: MetricValue
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

function coerceRight(raw: string, left: MetricValue): string | number | boolean {
  if (raw === 'true') return true
  if (raw === 'false') return false
  if (typeof left === 'number') {
    const parsed = Number(raw)
    return Number.isNaN(parsed) ? raw : parsed
  }
  const parsed = Number(raw)
  if (!Number.isNaN(parsed) && raw.trim() !== '') return parsed
  return raw
}

export function evaluateMetricAgainstTier(
  criteria: string[],
  metricKey: string,
  value: MetricValue,
): MetricTierStatus {
  const criterion = criteria.find((item) => item.startsWith(`${metricKey} `))
  if (!criterion) return 'na'
  if (value === undefined) return 'fail'

  const match = CONDITION_RE.exec(criterion)
  if (!match) return 'fail'

  const [, , operator, rightRaw] = match
  const right = coerceRight(rightRaw, value)

  switch (operator) {
    case '==':
      return value === right ? 'pass' : 'fail'
    case '!=':
      return value !== right ? 'pass' : 'fail'
    case '>=':
      return typeof value === 'number' && typeof right === 'number' && value >= right ? 'pass' : 'fail'
    case '<=':
      return typeof value === 'number' && typeof right === 'number' && value <= right ? 'pass' : 'fail'
    case '>':
      return typeof value === 'number' && typeof right === 'number' && value > right ? 'pass' : 'fail'
    case '<':
      return typeof value === 'number' && typeof right === 'number' && value < right ? 'pass' : 'fail'
    default:
      return 'fail'
  }
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
  result: MetricValue,
  targetMedal: Medal,
  metric: MetricDefinition,
  targetTierStatus?: MetricTierStatus,
): GapClass {
  if (targetTierStatus === 'na') return 'not_applicable'

  if (result === null || result === undefined) {
    return metric.type === 'boolean' ? 'below_target' : 'not_applicable'
  }

  if (metric.type === 'boolean') {
    return result === true ? 'at_target' : 'below_target'
  }

  const targetThreshold = metric.medals[targetMedal]?.min
  if (targetThreshold === undefined) return 'not_applicable'

  const numericResult = typeof result === 'number' ? result : Number(result)
  if (Number.isNaN(numericResult)) return 'not_applicable'

  if (isAtTarget(numericResult, targetThreshold)) return 'at_target'
  if (numericResult > targetThreshold) return 'exceeds_target'
  return 'below_target'
}

export function computeGapToTarget(
  result: MetricValue,
  targetMedal: Medal,
  metric: MetricDefinition,
  targetTierStatus?: MetricTierStatus,
): string | null {
  const gapClass = computeGapClass(result, targetMedal, metric, targetTierStatus)

  if (gapClass === 'not_applicable') return null
  if (gapClass === 'at_target') return 'At target'
  if (gapClass === 'exceeds_target') return 'Exceeds target'

  if (result === null || result === undefined) {
    return 'Below target (requires true)'
  }

  if (metric.type === 'boolean') {
    return 'Below target (requires true)'
  }

  const targetThreshold = metric.medals[targetMedal]?.min
  if (targetThreshold === undefined) return null

  const numericResult = typeof result === 'number' ? result : Number(result)
  if (Number.isNaN(numericResult)) return null
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

function getCompositionMetricValue(
  rootEntry: DimensionEntry,
  leafProductId: string,
  metricKey: string,
): MetricValue {
  const compositionEntry = (rootEntry.composition ?? []).find((leaf) => leaf.product_id === leafProductId)
  return compositionEntry?.metrics?.[metricKey]
}

function buildMetricRow(
  product: Product,
  entry: DimensionEntry,
  dimensionCriteria: { bronze: string[]; silver: string[]; gold: string[] },
  metricKey: string,
  value: MetricValue,
): MetricDistributionRow {
  return {
    product,
    entry,
    value,
    bronze: evaluateMetricAgainstTier(dimensionCriteria.bronze, metricKey, value),
    silver: evaluateMetricAgainstTier(dimensionCriteria.silver, metricKey, value),
    gold: evaluateMetricAgainstTier(dimensionCriteria.gold, metricKey, value),
  }
}

function metricResultFromValue(
  criteria: { bronze: string[]; silver: string[]; gold: string[] },
  metricKey: string,
  value: MetricValue,
): Result {
  if (value === undefined || value === null) return 'insufficient_data'
  const gold = evaluateMetricAgainstTier(criteria.gold, metricKey, value)
  const silver = evaluateMetricAgainstTier(criteria.silver, metricKey, value)
  const bronze = evaluateMetricAgainstTier(criteria.bronze, metricKey, value)
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

function deriveRootMetricValue(
  criteria: { bronze: string[]; silver: string[]; gold: string[] },
  metricKey: string,
  leafValues: MetricValue[],
): MetricValue {
  const candidates = leafValues.filter((value): value is Exclude<MetricValue, null | undefined> => value !== null && value !== undefined)
  if (candidates.length === 0) return undefined

  return candidates.reduce((worst, candidate) => (
    METRIC_RESULT_WORST_TO_BEST[metricResultFromValue(criteria, metricKey, candidate)]
      < METRIC_RESULT_WORST_TO_BEST[metricResultFromValue(criteria, metricKey, worst)]
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
  const criteria = {
    bronze: meta?.medals?.bronze?.criteria ?? [],
    silver: meta?.medals?.silver?.criteria ?? [],
    gold: meta?.medals?.gold?.criteria ?? [],
  }
  return groupedRows.map((group) => {
    const leafValues = group.leaves.map((leaf) => (
      getCompositionMetricValue(group.root.entry, leaf.product.id, metricKey)
      ?? leaf.entry.metrics[metricKey]
    ))
    const rootValue = group.root.entry.metrics[metricKey] ?? deriveRootMetricValue(criteria, metricKey, leafValues)
    return {
      root: buildMetricRow(group.root.product, group.root.entry, criteria, metricKey, rootValue),
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
