import { useState } from 'react'
import VersionLink from './VersionLink'
import MetricEvidence from './MetricEvidence'
import { aggregateMetric, missingMetric, type ThresholdInfo } from '../lib/metricOutcome'
import type { LeafDimensionResult, OutputMeta } from '../types'

interface Props {
  composition: LeafDimensionResult[]
  thresholds: Record<string, ThresholdInfo>
  metaOutputs: Record<string, OutputMeta> | undefined
}

export default function RootMetricsList({ composition, thresholds, metaOutputs }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const inScope = composition.filter(leaf => !leaf.excluded_from_parent_medal)
  if (!metaOutputs || inScope.length === 0) return null

  return <div style={{ display: 'flex', flexDirection: 'column' }}>
    {Object.entries(metaOutputs).map(([key, meta], index) => {
      const threshold = meta.informational ? undefined : thresholds[key]
      const outcomes = inScope.map(leaf => leaf.metrics[key] ?? missingMetric())
      const outcome = aggregateMetric(outcomes, threshold)
      const allAgree = outcomes.every(item => JSON.stringify(item) === JSON.stringify(outcome))
      const isExpanded = expanded[key] ?? false
      const toggle = () => setExpanded(previous => ({ ...previous, [key]: !previous[key] }))
      const unit = meta.range?.match(/([a-zA-Z%]+)$/)?.[1]
      return <div key={key} style={{ borderTop: index > 0 ? '1px solid #f0f0f0' : 'none' }}>
        <div
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', padding: '0.3rem 0', fontSize: '0.8125rem', cursor: allAgree ? 'default' : 'pointer' }}
          role={allAgree ? undefined : 'button'}
          tabIndex={allAgree ? undefined : 0}
          aria-expanded={allAgree ? undefined : isExpanded}
          aria-label={allAgree ? undefined : `${isExpanded ? 'Collapse' : 'Expand'} ${meta.label}: ${inScope.length} components`}
          onClick={allAgree ? undefined : toggle}
          onKeyDown={allAgree ? undefined : event => {
            if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle() }
          }}
        >
          <span title={meta.description} style={{ color: '#555' }}>
            {meta.label} {meta.informational && <span className="p-label">info</span>}
          </span>
          <span style={{ textAlign: 'right' }}>
            <MetricEvidence outcome={outcome} threshold={threshold} unit={unit} />
            {!allAgree && <span aria-hidden="true"> {isExpanded ? '▾' : '▸'}</span>}
          </span>
        </div>
        {!allAgree && isExpanded && <div style={{ border: '1px solid #d9d9d9', padding: '0.5rem', fontSize: '0.8125rem' }}>
          {inScope.map((leaf, leafIndex) => <div key={leaf.product_id} style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', padding: '0.25rem 0' }}>
            <VersionLink to={`/products/${leaf.product_id}`}>{leaf.product_id}</VersionLink>
            <span style={{ textAlign: 'right' }}><MetricEvidence outcome={outcomes[leafIndex]} threshold={threshold} unit={unit} /></span>
          </div>)}
        </div>}
      </div>
    })}
  </div>
}
