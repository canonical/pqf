import { useQuery } from '@tanstack/react-query'
import type { FrameworkVersionIndex } from '../types'

async function fetchFrameworkVersions(): Promise<FrameworkVersionIndex> {
  // Use BASE_URL so the path resolves correctly on GH Pages subpath (/pqf/)
  const res = await fetch(`${import.meta.env.BASE_URL}framework-versions.json`)
  if (!res.ok) throw new Error(`Failed to fetch framework versions: ${res.status}`)
  return res.json()
}

export function useFrameworkVersions() {
  return useQuery<FrameworkVersionIndex, Error>({
    queryKey: ['framework-versions'],
    queryFn: fetchFrameworkVersions,
    staleTime: 5 * 60 * 1000,
  })
}
