import { useLocation, Link } from 'react-router'
import { useFrameworkVersion } from '../providers/FrameworkVersionProvider'
import { useVersionedPath } from '../hooks/useVersionedPath'
import { describeFrameworkContext } from '../lib/frameworkContext'
import VersionSelector from './VersionSelector'

export default function GlobalNav() {
  const location = useLocation()
  const { current } = useFrameworkVersion()
  const toVersionedPath = useVersionedPath()
  const base = toVersionedPath('/')

  const isActive = (path: string) => {
    const target = path === '' ? base : `${base}${path}`
    if (path === '') return location.pathname === base
    return location.pathname.startsWith(target)
  }

  return (
    <header className="p-navigation is-dark">
      <div className="p-navigation__row">
        <div className="p-navigation__banner">
          <div className="p-navigation__tagged-logo">
            <Link className="p-navigation__link" to={base}>
              <div className="p-navigation__logo-tag" style={{ background: '#E95420' }}>
                <img
                  className="p-navigation__logo-icon"
                  src="https://assets.ubuntu.com/v1/82818827-CoF_white.svg"
                  alt=""
                  width="32"
                  height="32"
                />
              </div>
              <span className="p-navigation__logo-title">PQF</span>
            </Link>
          </div>
        </div>
        <nav className="p-navigation__nav">
          <ul className="p-navigation__items">
            <li className="p-navigation__item">
              <Link 
                className={`p-navigation__link ${isActive('') ? 'is-selected' : ''}`}
                to={base}
              >
                Overview
              </Link>
            </li>
            <li className="p-navigation__item">
              <Link 
                className={`p-navigation__link ${isActive('/products') ? 'is-selected' : ''}`}
                to={toVersionedPath('/products')}
              >
                Products
              </Link>
            </li>
            <li className="p-navigation__item">
              <Link 
                className={`p-navigation__link ${isActive('/dimensions') ? 'is-selected' : ''}`}
                to={toVersionedPath('/dimensions')}
              >
                Dimensions
              </Link>
            </li>
            <li className="p-navigation__item">
              <Link 
                className={`p-navigation__link ${isActive('/about') ? 'is-selected' : ''}`}
                to={toVersionedPath('/about')}
              >
                About
              </Link>
            </li>
            <li className="p-navigation__item">
              <a
                className="p-navigation__link"
                href="https://github.com/canonical/pqf/tree/main/docs"
                target="_blank"
                rel="noopener noreferrer"
              >
                Docs ↗
              </a>
            </li>
          </ul>
        </nav>
        <div className="p-navigation__nav-selector-wrapper" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.5rem 1rem' }}>
          <span className="p-text--small" style={{ opacity: 0.8, whiteSpace: 'nowrap' }}>
            {describeFrameworkContext(current)}
          </span>
          <VersionSelector />
        </div>
      </div>
    </header>
  )
}
