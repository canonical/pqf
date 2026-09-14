import { useFrameworkVersion } from '../providers/FrameworkVersionProvider'

/**
 * Returns a function that scopes an app-relative path (e.g. `/products/matrix`, `/about`, or the
 * bare root `/`) to the currently selected framework version, producing e.g.
 * `/v0/products/matrix`. Every internal navigation target must be built through this (directly,
 * or via `VersionLink`) so the selected version is preserved — switching versions, or simply
 * browsing an archived/upcoming version, must never bounce back to the active version or have an
 * unprefixed path segment misinterpreted as a framework version id by the router.
 */
export function useVersionedPath(): (path: string) => string {
  const { current } = useFrameworkVersion()
  return (path: string) => {
    if (!path || path === '/') return `/${current.id}`
    const suffix = path.startsWith('/') ? path : `/${path}`
    return `/${current.id}${suffix}`
  }
}
