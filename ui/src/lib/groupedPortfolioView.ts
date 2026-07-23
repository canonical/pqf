import type {
  DimensionEntry,
  Medal,
  Portfolio,
  Product,
} from '../types'

export type MetricTierStatus = 'pass' | 'fail' | 'na'
export type MetricValue = string | number | boolean | undefined

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
    const rootValue = group.root.entry.metrics[metricKey]
    return {
      root: buildMetricRow(group.root.product, group.root.entry, criteria, metricKey, rootValue),
      leaves: group.leaves.map((leaf) => {
        const value =
          getCompositionMetricValue(group.root.entry, leaf.product.id, metricKey)
          ?? leaf.entry.metrics[metricKey]
        return buildMetricRow(leaf.product, leaf.entry, criteria, metricKey, value)
      }),
    }
  })
}

export const MEDAL_ORDER: Record<Medal, number> = {
  gold: 3,
  silver: 2,
  bronze: 1,
  unrated: 0,
}
