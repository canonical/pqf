import { useLocation, Link } from 'react-router'

export default function GlobalNav() {
  const location = useLocation()
  
  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <header className="p-navigation is-dark">
      <div className="p-navigation__row">
        <div className="p-navigation__banner">
          <div className="p-navigation__tagged-logo">
            <Link className="p-navigation__link" to="/">
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
                className={`p-navigation__link ${isActive('/') ? 'is-selected' : ''}`}
                to="/"
              >
                Overview
              </Link>
            </li>
            <li className="p-navigation__item">
              <Link 
                className={`p-navigation__link ${isActive('/products') ? 'is-selected' : ''}`}
                to="/products"
              >
                Products
              </Link>
            </li>
            <li className="p-navigation__item">
              <Link 
                className={`p-navigation__link ${isActive('/dimensions') ? 'is-selected' : ''}`}
                to="/dimensions"
              >
                Dimensions
              </Link>
            </li>
            <li className="p-navigation__item">
              <Link 
                className={`p-navigation__link ${isActive('/about') ? 'is-selected' : ''}`}
                to="/about"
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
      </div>
    </header>
  )
}
