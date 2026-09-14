import VersionLink from '../components/VersionLink'
import { usePortfolio } from '../hooks/usePortfolio'
import MedalBadge from '../components/MedalBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import { useFrameworkVersion } from '../providers/FrameworkVersionProvider'

export default function About() {
  const { data: portfolio, isLoading } = usePortfolio()
  const { current } = useFrameworkVersion()
  if (isLoading) return <LoadingSpinner />

  const dimensions = portfolio ? Object.entries(portfolio.dimensions_meta) : []

  return (
    <div className="row" style={{ paddingTop: '1.5rem' }}>
      <div className="col-12">
        <h1 className="p-heading--2">About PQF</h1>
        <p>
          The Product Quality Framework (PQF) gives Platform Engineering a data-driven,
          auditable view of quality and compliance across tracked products. Each product is
          scored across five dimensions and awarded a medal — Bronze, Silver, or Gold — based on
          objective, automatically-computed criteria.
        </p>

        <h2 className="p-heading--4">Framework versions</h2>
        <p>
          Each framework version defines its own product set and can select different products,
          components, targets, metrics, and criteria. You are viewing {current.label}.
        </p>
        <ul className="p-list--divided">
          <li className="p-list__item">
            <strong>Active</strong> is the official current view of compliance.
          </li>
          <li className="p-list__item">
            <strong>Upcoming</strong> is a readiness view for the next scoring contract and
            product set.
          </li>
          <li className="p-list__item">
            <strong>Archived</strong> preserves frozen historical evidence.
          </li>
        </ul>

        <h2 className="p-heading--4">How scoring works</h2>
        <ol className="p-list--divided">
          <li className="p-list__item">Select a framework version and its product set.</li>
          <li className="p-list__item">Measure applicable product components.</li>
          <li className="p-list__item">Apply that version's criteria and targets.</li>
          <li className="p-list__item">
            Aggregate component results into each tracked product.
          </li>
        </ol>
        <p>
          The same measurement may be safely reused when versions ask the identical question of
          the identical product, but each version always applies its own outputs, criteria, and
          target.
        </p>
        <p>
          If required evidence cannot be acquired, scoring fails rather than producing a low
          result.
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
              <td><MedalBadge medal="below_minimum" /></td>
              <td>Below minimum. Dimension was measured but failed to meet minimum criteria.</td>
            </tr>
            <tr>
              <td><MedalBadge medal="insufficient_data" /></td>
              <td>Insufficient data. Dimension could not be measured.</td>
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
                    <VersionLink to={`/dimensions/${key}`}>{meta.label ?? key.replace(/_/g, ' ')}</VersionLink>
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
              href="https://github.com/canonical/pqf/blob/main/docs/architecture.md"
              target="_blank"
              rel="noreferrer"
            >
              Scoring architecture on GitHub ↗
            </a>
          </li>
          <li className="p-list__item">
            <VersionLink to="/">Overview</VersionLink>
          </li>
        </ul>
      </div>
    </div>
  )
}
