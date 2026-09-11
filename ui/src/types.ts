export type Medal = 'gold' | 'silver' | 'bronze' | 'unrated'
export type Result = 'gold' | 'silver' | 'bronze' | 'below_minimum' | 'insufficient_data' | 'not_applicable'
export type Lifecycle = 'experimental' | 'beta' | 'stable' | 'legacy'
export type ProductType = 'root' | 'charm' | 'snap'
export type ApplicabilityOutcome = 'scored' | 'not_applicable' | 'insufficient_data'

/** Lifecycle status of a framework version. `framework-versions.json` is the sole authority for this. */
export type FrameworkStatus = 'upcoming' | 'active' | 'archived'

/** An entry in the public `framework-versions.json` index. Authoritative for lifecycle/display metadata. */
export interface FrameworkVersionSummary {
  id: string
  sequence: number
  label: string
  status: FrameworkStatus
  description: string
  portfolio_url: string
  generated_at: string
  contract_digest: string
}

export interface FrameworkVersionIndex {
  versions: FrameworkVersionSummary[]
}

/**
 * The `framework` block embedded in a portfolio. This is historical provenance recorded at
 * generation time — it must never be used to derive current lifecycle/display labels. Use the
 * matching `FrameworkVersionSummary` from `framework-versions.json` for that instead.
 */
export interface FrameworkMetadata {
  id: string
  sequence: number
  label: string
  status: FrameworkStatus
  description: string
}

export interface ComplianceSummary {
  total: number
  meeting_target: number
  below_target: number
  insufficient_data: number
}

export interface LeafDimensionResult {
  product_id: string
  repo: string
  result: Result
  metrics: Record<string, string | number | boolean>
  excluded_from_parent_medal: boolean
}

export interface DimensionEntry {
  result: Result
  /** Whether this dimension's result is at or above its target tier. Always present on version-scoped portfolios. */
  meets_target: boolean
  metrics: Record<string, string | number | boolean>
  composition: LeafDimensionResult[] | null
}

export interface ComposedRef {
  product_id: string
  excluded_from_parent_medal: boolean
}

export interface ContextRef {
  label: string
  repo: string | null
}

export interface SourceRef {
  repo: string
  subpath: string | null
}

export interface Product {
  id: string
  product_type: ProductType
  name: string
  description?: string
  lifecycle: Lifecycle
  current_result: Result
  target_result: Result
  squad: string
  is_portfolio_entry: boolean
  documentation_url?: string
  source?: SourceRef
  composed_of: ComposedRef[] | null
  context_refs: ContextRef[]
  parent_product_ids: string[]
  dimensions: Record<string, DimensionEntry>
  /** Whether the product's current result is at or above its target. Always present on version-scoped portfolios. */
  meets_target: boolean
}

export interface MedalCriteria {
  criteria: string[]
}

export interface NumericMetricDefinition {
  name: string
  type: 'numeric'
  medals: Partial<Record<Medal, { min: number }>>
  label?: string
  description?: string
}

export interface BooleanMetricDefinition {
  name: string
  type: 'boolean'
  signal_name?: string
  label?: string
  description?: string
}

export type MetricDefinition = NumericMetricDefinition | BooleanMetricDefinition

export interface OutputMeta {
  label: string
  description: string
  type: string
  range: string
  ai_assisted?: boolean
  informational?: boolean
}

export interface DimensionMeta {
  label?: string
  description?: string
  applies_to?: string[]
  aggregation?: string
  outputs?: Record<string, OutputMeta>
  medals: {
    bronze?: MedalCriteria
    silver?: MedalCriteria
    gold?: MedalCriteria
  }
}

export interface Portfolio {
  generated_at: string
  products: Product[]
  dimensions_meta: Record<string, DimensionMeta>
  /**
   * Historical provenance only — see `FrameworkMetadata`. Never use this for lifecycle/display
   * decisions; use the selected `FrameworkVersionSummary` from `FrameworkVersionProvider` instead.
   */
  framework: FrameworkMetadata
  contract_digest: string
  source_revision: string
  implementation_fingerprints: Record<string, string>
  compliance_summary: ComplianceSummary
}
