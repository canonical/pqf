import type { Portfolio } from '../types'
import { parseLiteral } from './metricOutcome'

function object(value: unknown, path: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Invalid portfolio: ${path} must be an object`)
  return value as Record<string, unknown>
}

function validateDimensionMetadata(value: unknown): Record<string, Record<string, string>> {
  const outputTypes: Record<string, Record<string, string>> = {}
  for (const [dimensionId, rawMetadata] of Object.entries(object(value, 'dimensions_meta'))) {
    const path = `dimensions_meta.${dimensionId}`
    const metadata = object(rawMetadata, path)
    const medals = object(metadata.medals, `${path}.medals`)
    for (const [tier, rawCriteria] of Object.entries(medals)) {
      const criteria = object(rawCriteria, `${path}.medals.${tier}`).criteria
      if (!Array.isArray(criteria) || !criteria.every(criterion => typeof criterion === 'string')) {
        throw new Error(`Invalid portfolio: ${path}.medals.${tier}.criteria must be an array of strings`)
      }
      for (const criterion of criteria) {
        const match = criterion.match(/^\w+\s*(>=|<=|!=|==|>|<)\s*(.+)$/)
        if (!match) throw new Error(`Invalid portfolio: ${path} has an invalid criterion`)
        let literal: string | number | boolean
        try {
          literal = parseLiteral(match[2].trim())
        } catch {
          throw new Error(`Invalid portfolio: ${path} has an invalid quoted criterion`)
        }
        if ((typeof literal === 'number' && !Number.isFinite(literal)) ||
            (!['==', '!='].includes(match[1]) && typeof literal !== 'number')) {
          throw new Error(`Invalid portfolio: ${path} has an invalid criterion literal`)
        }
      }
    }
    const types: Record<string, string> = {}
    for (const [key, rawOutput] of Object.entries(metadata.outputs === undefined ? {} : object(metadata.outputs, `${path}.outputs`))) {
      const outputPath = `${path}.outputs.${key}`
      const output = object(rawOutput, outputPath)
      for (const field of ['label', 'description', 'type', 'range']) {
        if (typeof output[field] !== 'string') throw new Error(`Invalid portfolio: ${outputPath}.${field} must be a string`)
      }
      const type = output.type as string
      if (!['boolean', 'number', 'numeric', 'integer', 'string'].includes(type)) {
        throw new Error(`Invalid portfolio: ${outputPath} has an unsupported metric type`)
      }
      for (const field of ['informational', 'ai_assisted']) {
        if (output[field] !== undefined && typeof output[field] !== 'boolean') {
          throw new Error(`Invalid portfolio: ${outputPath}.${field} must be a boolean`)
        }
      }
      types[key] = type === 'numeric' || type === 'integer' ? 'number' : type
    }
    outputTypes[dimensionId] = types
  }
  return outputTypes
}

function validateMetrics(value: unknown, path: string, outputTypes: Record<string, string> = {}) {
  for (const [key, raw] of Object.entries(object(value, path))) {
    const location = `${path}.${key}`
    const outcome = object(raw, location)
    const validReason = typeof outcome.reason === 'string' && outcome.reason.trim().length > 0
    if (outcome.state === 'measured') {
      if (!['string', 'number', 'boolean'].includes(typeof outcome.value) ||
          (typeof outcome.value === 'number' && !Number.isFinite(outcome.value)) ||
          (outcome.reason !== undefined && !validReason)) {
        throw new Error(`Invalid portfolio: ${location} has invalid measured evidence`)
      }
      if (outputTypes[key] && typeof outcome.value !== outputTypes[key]) {
        throw new Error(`Invalid portfolio: ${location} must carry a measured ${outputTypes[key]} value`)
      }
    } else if (outcome.state === 'not_applicable' || outcome.state === 'insufficient_data') {
      if (outcome.value !== null || !validReason) throw new Error(`Invalid portfolio: ${location} requires null value and a reason`)
    } else {
      throw new Error(`Invalid portfolio: ${location} has an unknown metric state`)
    }
  }
}

/** Validate the artifact boundary, never convert legacy scalar evidence. */
export function validatePortfolio(value: unknown): asserts value is Portfolio {
  const portfolio = object(value, 'root')
  object(portfolio.framework, 'framework')
  const outputTypes = validateDimensionMetadata(portfolio.dimensions_meta)
  if (!Array.isArray(portfolio.products)) throw new Error('Invalid portfolio: products must be an array')
  portfolio.products.forEach((rawProduct, index) => {
    const path = `products[${index}]`
    const product = object(rawProduct, path)
    for (const key of ['id', 'name', 'squad', 'lifecycle', 'product_type', 'current_result', 'target_result']) {
      if (typeof product[key] !== 'string') throw new Error(`Invalid portfolio: ${path}.${key} must be a string`)
    }
    if (typeof product.meets_target !== 'boolean' || typeof product.is_portfolio_entry !== 'boolean' ||
        !Array.isArray(product.context_refs) || !Array.isArray(product.parent_product_ids) ||
        !(product.composed_of === null || Array.isArray(product.composed_of))) {
      throw new Error(`Invalid portfolio: ${path} has malformed product metadata`)
    }
    for (const [dimensionId, rawEntry] of Object.entries(object(product.dimensions, `${path}.dimensions`))) {
      const location = `${path}.dimensions.${dimensionId}`
      const entry = object(rawEntry, location)
      if (typeof entry.result !== 'string' || typeof entry.meets_target !== 'boolean') throw new Error(`Invalid portfolio: ${location} has invalid result metadata`)
      validateMetrics(entry.metrics, `${location}.metrics`, outputTypes[dimensionId])
      if (entry.composition === null) continue
      if (!Array.isArray(entry.composition)) throw new Error(`Invalid portfolio: ${location}.composition must be an array or null`)
      entry.composition.forEach((rawLeaf, leafIndex) => {
        const leafPath = `${location}.composition[${leafIndex}]`
        const leaf = object(rawLeaf, leafPath)
        if (typeof leaf.product_id !== 'string' || !(leaf.repo === null || typeof leaf.repo === 'string') ||
            typeof leaf.result !== 'string' || typeof leaf.excluded_from_parent_medal !== 'boolean') {
          throw new Error(`Invalid portfolio: ${leafPath} has malformed component metadata`)
        }
        validateMetrics(leaf.metrics, `${leafPath}.metrics`, outputTypes[dimensionId])
      })
    }
  })
}
