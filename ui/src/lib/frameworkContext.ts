import type { FrameworkVersionSummary } from '../types'

/**
 * Builds the short version-context label shown across every view (via `GlobalNav`) so users
 * always know which framework version they are looking at. `framework-versions.json` (via the
 * selected `FrameworkVersionSummary` from the provider) is the sole source for this — never the
 * embedded `framework` block in a portfolio payload.
 */
export function describeFrameworkContext(version: FrameworkVersionSummary): string {
  const timestamp = new Date(version.generated_at).toLocaleString()
  switch (version.status) {
    case 'upcoming':
      return `Planning against ${version.label} · refreshed ${timestamp}`
    case 'archived':
      return `Archived snapshot · generated ${timestamp}`
    case 'active':
    default:
      return `Current framework · ${version.label}`
  }
}
