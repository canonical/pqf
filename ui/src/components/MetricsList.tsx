import React from 'react'
import type { MetricOutcome } from '../types'
import MetricEvidence from './MetricEvidence'

interface ThresholdInfo {
  operator: string
  value: string | number | boolean
  metricLabel?: string
  metricDescription?: string
}

interface OutputMetaLocal {
  label: string
  description: string
  type: string
  range: string
  ai_assisted?: boolean
  informational?: boolean
}

interface Props {
  metrics: Record<string, MetricOutcome>
  thresholds?: Record<string, ThresholdInfo>
  metaOutputs?: Record<string, OutputMetaLocal>
}

const METRIC_LABELS: Record<string, string> = {
  coverage_pct: 'Coverage',
  stability_pct: 'Stability',
  latest_build_passing: 'Build passing',
  has_readme: 'README',
  has_contributing: 'CONTRIBUTING',
  has_security: 'SECURITY',
  diataxis_coverage: 'Diátaxis docs',
  style_linter_passing: 'Style linter',
  links_passing: 'Links',
  supports_juju_3: 'Juju 3',
  supports_juju_4: 'Juju 4',
  supports_ck8s: 'CK8s',
  dependabot_enabled: 'Dependabot',
  codeql_enabled: 'CodeQL',
  avg_triage_days: 'Avg. triage',
  avg_pr_review_days: 'Avg. PR review',
}

/** Extract a short unit string from a range descriptor, e.g. "≥ 0 days" → "days" */
function extractUnit(range: string | undefined): string | null {
  if (!range) return null
  const m = range.match(/([a-zA-Z%]+)$/)
  return m ? m[1] : null
}

export default function MetricsList({ metrics, thresholds, metaOutputs }: Props) {
  return (
    <dl className="u-no-margin" style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '0.1rem 0.75rem', fontSize: '0.8125rem' }}>
      {Object.entries(metrics).map(([key, val]) => {
        const meta = metaOutputs?.[key]
        const label = meta?.label ?? METRIC_LABELS[key] ?? key
        const desc = meta?.description
        const threshold = thresholds?.[key]
        const unit = extractUnit(meta?.range)
        const isInformational = meta?.informational === true

        return (
          <React.Fragment key={key}>
            <dt
              style={{ color: '#666', margin: 0, display: 'flex', alignItems: 'center', gap: '0.35rem' }}
              title={desc}
            >
              {label}
              {isInformational && (
                <span style={{
                  fontSize: '0.625rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: '#888',
                  border: '1px solid #ccc',
                  borderRadius: '2px',
                  padding: '0 3px',
                  lineHeight: 1.4,
                }}>
                  info
                </span>
              )}
            </dt>
            <dd style={{ margin: 0, textAlign: 'right' }}>
              <MetricEvidence outcome={val} threshold={isInformational ? undefined : threshold} unit={unit} />
            </dd>
          </React.Fragment>
        )
      })}
    </dl>
  )
}
