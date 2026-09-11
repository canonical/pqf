import { Link, type LinkProps } from 'react-router'
import { useVersionedPath } from '../hooks/useVersionedPath'

export interface VersionLinkProps extends Omit<LinkProps, 'to'> {
  /** An app-relative path *without* the framework version segment, e.g. `/products/matrix`. */
  to: string
}

/**
 * Drop-in replacement for react-router's `Link` that scopes `to` to the currently selected
 * framework version (via `useVersionedPath`). Use this — not a bare `Link` — for every internal
 * navigation target so the selected version survives clicking through the app.
 */
export default function VersionLink({ to, ...props }: VersionLinkProps) {
  const toVersionedPath = useVersionedPath()
  return <Link to={toVersionedPath(to)} {...props} />
}
