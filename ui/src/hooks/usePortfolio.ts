import { useQuery } from '@tanstack/react-query'
import type { Portfolio } from '../types'

async function fetchPortfolio(): Promise<Portfolio> {
  // Use BASE_URL so the path resolves correctly on GH Pages subpath (/pqf/)
  const res = await fetch(`${import.meta.env.BASE_URL}portfolio.json`)
  if (!res.ok) throw new Error(`Failed to fetch product data: ${res.status}`)
  return res.json()
}

export function usePortfolio() {
  return useQuery<Portfolio, Error>({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
    staleTime: 5 * 60 * 1000,
  })
}
