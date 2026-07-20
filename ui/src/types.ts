export type Medal = 'gold' | 'silver' | 'bronze' | 'unrated'
export type DriftStatus = 'remediating' | 'overdue'
export type Lifecycle = 'experimental' | 'beta' | 'stable' | 'legacy'
export type ProductType = 'root' | 'charm' | 'snap'
export type ApplicabilityOutcome = 'scored' | 'not_applicable' | 'insufficient_data'

export interface DriftInfo {
  status: DriftStatus
  first_seen_at: string
  deadline: string
}

export interface LeafDimensionResult {
  product_id: string
  repo: string
  medal: Medal
  applicability: ApplicabilityOutcome
  metrics: Record<string, string | number | boolean>
  excluded_from_parent_medal: boolean
}

export interface DimensionEntry {
  medal: Medal
  target: Medal
  applicability: ApplicabilityOutcome
  drift: DriftInfo | null
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
  target_medal: Medal
  current_medal: Medal
  squad: string
  is_portfolio_entry: boolean
  documentation_url?: string
  source?: SourceRef
  composed_of: ComposedRef[] | null
  context_refs: ContextRef[]
  parent_product_ids: string[]
  dimensions: Record<string, DimensionEntry>
}

export interface MedalCriteria {
  criteria: string[]
}

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
}
