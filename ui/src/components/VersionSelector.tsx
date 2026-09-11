import type { ChangeEvent } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { useFrameworkVersion } from '../providers/FrameworkVersionProvider'
import type { FrameworkStatus, FrameworkVersionSummary } from '../types'

const STATUS_ORDER: FrameworkStatus[] = ['upcoming', 'active', 'archived']
const STATUS_LABELS: Record<FrameworkStatus, string> = {
  upcoming: 'Upcoming',
  active: 'Active',
  archived: 'Archived',
}

interface VersionGroup {
  status: FrameworkStatus
  label: string
  versions: FrameworkVersionSummary[]
}

function groupVersions(versions: FrameworkVersionSummary[]): VersionGroup[] {
  return STATUS_ORDER.map(status => ({
    status,
    label: STATUS_LABELS[status],
    versions: versions.filter(version => version.status === status).sort((a, b) => b.sequence - a.sequence),
  })).filter(group => group.versions.length > 0)
}

function formatRefreshTime(generatedAt: string): string {
  const timestamp = new Date(generatedAt)
  if (!Number.isFinite(timestamp.getTime())) {
    return 'Refresh time unavailable'
  }
  return `Refreshed ${timestamp.toLocaleString()}`
}

/**
 * Persistent top-right control for switching the selected framework version. Preserves the
 * current sub-route by replacing only the first path segment (the version id).
 */
export default function VersionSelector() {
  const { current, versions } = useFrameworkVersion()
  const navigate = useNavigate()
  const location = useLocation()
  const groups = groupVersions(versions)

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextId = event.target.value
    if (!nextId || nextId === current.id) return
    const segments = location.pathname.split('/')
    segments[1] = nextId
    navigate({ pathname: segments.join('/') || '/', search: location.search })
  }

  return (
    <div className="version-selector" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
      <div className="p-form__group p-form-validation">
        <label className="p-form__label u-off-screen" htmlFor="framework-version-select">
          Framework version
        </label>
        <div className="p-form__control u-clearfix">
          <div className="p-form-validation__select-wrapper">
            <select
              id="framework-version-select"
              className="p-form-validation__input version-selector__select"
              value={current.id}
              onChange={handleChange}
            >
              {groups.map(group => (
                <optgroup key={group.status} label={group.label}>
                  {group.versions.map(version => (
                    <option key={version.id} value={version.id}>
                      {version.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        </div>
      </div>
      <span className="version-selector__meta" style={{ fontSize: '0.75rem', color: '#f2f2f2', marginTop: '0.25rem' }}>
        {formatRefreshTime(current.generated_at)}
      </span>
    </div>
  )
}
