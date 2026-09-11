import { useQuery } from '@tanstack/react-query'
import type { FrameworkVersionSummary, Portfolio } from '../types'
import { useFrameworkVersion } from '../providers/FrameworkVersionProvider'

async function fetchPortfolio(version: FrameworkVersionSummary): Promise<Portfolio> {
  // Use BASE_URL so the path resolves correctly on GH Pages subpath (/pqf/)
  const res = await fetch(`${import.meta.env.BASE_URL}${version.portfolio_url}`)
  if (!res.ok) throw new Error(`Failed to fetch product data: ${res.status}`)
  const portfolio: Portfolio = await res.json()

  // framework-versions.json is the source of truth; a portfolio that doesn't match the index
  // entry it was published under is a broken artifact, not a version we can silently accept.
  if (portfolio.framework?.id !== version.id) {
    throw new Error(
      `Portfolio at ${version.portfolio_url} reports framework id ` +
        `${portfolio.framework?.id ?? 'unknown'}, expected ${version.id}`,
    )
  }
  // Compare with `||` rather than only `!==` — if the runtime JSON payload is missing
  // `contract_digest` on either side (a malformed artifact, despite the TS types), an
  // `undefined !== undefined` check would silently pass. Require both sides to be present.
  if (!version.contract_digest || !portfolio.contract_digest || portfolio.contract_digest !== version.contract_digest) {
    throw new Error(
      `Portfolio at ${version.portfolio_url} has contract digest ${portfolio.contract_digest ?? 'missing'}, ` +
        `expected ${version.contract_digest ?? 'missing'} from framework-versions.json`,
    )
  }

  // Overview and other views read `compliance_summary` directly from the payload (never
  // recomputing it in TypeScript), so a missing or malformed field must fail fast here with a
  // friendly, actionable message rather than surfacing as a confusing runtime crash in a view.
  const summary = portfolio.compliance_summary
  const summaryFields = ['total', 'meeting_target', 'below_target', 'insufficient_data'] as const
  const isValidSummary =
    summary != null && summaryFields.every(field => typeof summary[field] === 'number')
  if (!isValidSummary) {
    throw new Error(
      `Portfolio at ${version.portfolio_url} is missing a valid compliance_summary ` +
        '(expected numeric total, meeting_target, below_target, and insufficient_data fields)',
    )
  }

  return portfolio
}

/**
 * Fetches the portfolio for a framework version. Pass an explicit `FrameworkVersionSummary` to
 * target a specific version (e.g. from the version selector); omit it to use the version
 * selected by the current route, via `FrameworkVersionProvider`.
 */
export function usePortfolio(version?: FrameworkVersionSummary) {
  const { current } = useFrameworkVersion()
  const selected = version ?? current

  return useQuery<Portfolio, Error>({
    queryKey: ['portfolio', selected.id],
    queryFn: () => fetchPortfolio(selected),
    staleTime: 5 * 60 * 1000,
  })
}
