import { Link } from 'react-router'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import LoadingSpinner from '../components/LoadingSpinner'

export default function About() {
  const { data: portfolio, isLoading } = usePortfolio()
  if (isLoading) return <LoadingSpinner />

  const dimensions = portfolio ? Object.entries(portfolio.dimensions_meta) : []

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">
        <h1 className="p-heading--2">About PQF</h1>
        <p>
          The Product Quality Framework (PQF) gives Platform Engineering a data-driven,
          auditable view of quality and compliance across the product portfolio. Each product is
          scored across five dimensions and awarded a medal — Bronze, Silver, or Gold — based on
          objective, automatically-computed criteria.
        </p>

        <h2 className="p-heading--4">Medal levels</h2>
        <table className="p-table">
          <thead>
            <tr><th>Medal</th><th>Meaning</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><MedalBadge medal="gold" /></td>
              <td>Fully compliant. All criteria met at the highest tier.</td>
            </tr>
            <tr>
              <td><MedalBadge medal="silver" /></td>
              <td>Strong quality posture. Meeting intermediate-tier criteria.</td>
            </tr>
            <tr>
              <td><MedalBadge medal="bronze" /></td>
              <td>Baseline quality. Meeting minimum-tier criteria.</td>
            </tr>
            <tr>
              <td><MedalBadge medal="unrated" /></td>
              <td>Not yet scored, or insufficient data.</td>
            </tr>
          </tbody>
        </table>

        <h2 className="p-heading--4">Dimensions</h2>
        {dimensions.length > 0 ? (
          <table className="p-table">
            <thead>
              <tr><th>Dimension</th><th>Description</th></tr>
            </thead>
            <tbody>
              {dimensions.map(([key, meta]) => (
                <tr key={key}>
                  <td>
                    <Link to={`/dimensions/${key}`}>{meta.label ?? key.replace(/_/g, ' ')}</Link>
                  </td>
                  <td>{meta.description ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="u-text--muted">No dimension data available.</p>
        )}

        <h2 className="p-heading--4">Further reading</h2>
        <ul className="p-list">
          <li className="p-list__item">
            <a
              href="https://github.com/canonical/pqf/blob/main/docs/superpowers/specs/2026-06-29-pqf-tool-design.md"
              target="_blank"
              rel="noreferrer"
            >
              Full framework specification on GitHub ↗
            </a>
          </li>
          <li className="p-list__item">
            <Link to="/">Portfolio overview</Link>
          </li>
        </ul>
      </div>
    </div>
  )
}
