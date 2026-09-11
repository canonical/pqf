import type { FrameworkVersionSummary } from '../types'

/**
 * Formats an ISO timestamp as a stable, locale- and timezone-independent `YYYY-MM-DD` date.
 * Deliberately date-only (not `toLocaleString()`) since the framework-context label is rendered
 * on every page and must produce identical, deterministic output regardless of the browser's
 * locale/timezone — a prior version compared this timestamp against a self-referential
 * `toLocaleString()` call in tests, which always agreed with itself but never verified an actual
 * stable format.
 */
function formatDate(iso: string): string {
  const date = new Date(iso)
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Builds the short version-context label shown across every view (via `GlobalNav`) so users
 * always know which framework version they are looking at. `framework-versions.json` (via the
 * selected `FrameworkVersionSummary` from the provider) is the sole source for this — never the
 * embedded `framework` block in a portfolio payload.
 */
export function describeFrameworkContext(version: FrameworkVersionSummary): string {
  const date = formatDate(version.generated_at)
  switch (version.status) {
    case 'upcoming':
      return `Planning against ${version.label} · refreshed ${date}`
    case 'archived':
      return `Archived snapshot · generated ${date}`
    case 'active':
    default:
      return `Current framework · ${version.label}`
  }
}
