import type { FrameworkVersionSummary } from '../types'

/**
 * Resolves a version to send the user to when their requested version is unknown, or when no
 * version is currently marked `active` in `framework-versions.json`. Prefers the active version;
 * otherwise falls back to the most recently sequenced version so a no-active-version state is
 * always recoverable rather than a dead end.
 */
export function resolveRecoveryVersion(
  versions: FrameworkVersionSummary[],
): FrameworkVersionSummary | undefined {
  const active = versions.find(version => version.status === 'active')
  if (active) return active
  return [...versions].sort((a, b) => b.sequence - a.sequence)[0]
}
