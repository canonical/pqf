import { createContext, useContext, type ReactNode } from 'react'
import { useParams, Link } from 'react-router'
import { useFrameworkVersions } from '../hooks/useFrameworkVersions'
import LoadingSpinner from '../components/LoadingSpinner'
import type { FrameworkVersionSummary } from '../types'

export interface FrameworkVersionContextValue {
  /** The framework version selected by the `:frameworkVersion` route segment. */
  current: FrameworkVersionSummary
  /** The full published index, for building the version selector and resolving links. */
  versions: FrameworkVersionSummary[]
}

const FrameworkVersionContext = createContext<FrameworkVersionContextValue | null>(null)

/**
 * Returns the framework version selected by the current route and the full published index.
 * Must be used within a `FrameworkVersionProvider`.
 */
export function useFrameworkVersion(): FrameworkVersionContextValue {
  const context = useContext(FrameworkVersionContext)
  if (!context) {
    throw new Error('useFrameworkVersion must be used within a FrameworkVersionProvider')
  }
  return context
}

interface FrameworkVersionProviderProps {
  children: ReactNode
}

/**
 * Loads `framework-versions.json` and validates the `:frameworkVersion` route parameter against
 * it. `framework-versions.json` is the sole source of truth for lifecycle/display metadata
 * (status, label, description) — a portfolio's embedded `framework` block is historical
 * provenance only and must never be used here. Unknown version ids render an explicit not-found
 * state rather than silently falling back to another version.
 */
export function FrameworkVersionProvider({ children }: FrameworkVersionProviderProps) {
  const { frameworkVersion } = useParams<{ frameworkVersion: string }>()
  const { data, isLoading, isError, error, refetch } = useFrameworkVersions()

  if (isLoading) {
    return <LoadingSpinner />
  }

  if (isError || !data) {
    return (
      <div className="row" style={{ padding: '3rem 1rem', textAlign: 'center' }}>
        <p>Failed to load framework versions{error ? `: ${error.message}` : '.'}</p>
        <button type="button" className="p-button" onClick={() => refetch()}>
          Retry
        </button>
      </div>
    )
  }

  const current = data.versions.find(version => version.id === frameworkVersion)

  if (!current) {
    const active = data.versions.find(version => version.status === 'active')
    return (
      <div className="row" style={{ padding: '3rem 1rem', textAlign: 'center' }}>
        <h1 className="p-heading--2">Framework version not found</h1>
        <p>&ldquo;{frameworkVersion}&rdquo; is not a published PQF framework version.</p>
        {active && (
          <p>
            <Link to={`/${active.id}`}>Go to the active framework version ({active.label})</Link>
          </p>
        )}
      </div>
    )
  }

  return (
    <FrameworkVersionContext.Provider value={{ current, versions: data.versions }}>
      {children}
    </FrameworkVersionContext.Provider>
  )
}

export default FrameworkVersionProvider
