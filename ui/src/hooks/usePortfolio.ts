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
  if (portfolio.contract_digest !== version.contract_digest) {
    throw new Error(
      `Portfolio at ${version.portfolio_url} has contract digest ${portfolio.contract_digest ?? 'unknown'}, ` +
        `expected ${version.contract_digest} from framework-versions.json`,
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
