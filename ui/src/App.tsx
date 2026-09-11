import { HashRouter, Routes, Route, Navigate, useParams } from 'react-router'
import { lazy, Suspense } from 'react'
import GlobalNav from './components/GlobalNav'
import LoadingSpinner from './components/LoadingSpinner'
import FrameworkVersionProvider from './providers/FrameworkVersionProvider'
import { useFrameworkVersions } from './hooks/useFrameworkVersions'

const Overview = lazy(() => import('./views/Overview'))
const ProductsExplorer = lazy(() => import('./views/ProductsExplorer'))
const ProductDetail = lazy(() => import('./views/ProductDetail'))
const DimensionsOverview = lazy(() => import('./views/DimensionsOverview'))
const DimensionDetail = lazy(() => import('./views/DimensionDetail'))
const MetricDistribution = lazy(() => import('./views/MetricDistribution'))
const About = lazy(() => import('./views/About'))

/**
 * Bare `/` has no framework version yet. Once the index loads, redirect to the active version —
 * `framework-versions.json` is the sole source of truth for which version is active.
 */
function RootRedirect() {
  const { data, isLoading, isError, error } = useFrameworkVersions()

  if (isLoading) return <LoadingSpinner />

  if (isError || !data) {
    return (
      <div className="row" style={{ padding: '3rem 1rem', textAlign: 'center' }}>
        <p>Failed to load framework versions{error ? `: ${error.message}` : '.'}</p>
      </div>
    )
  }

  const active = data.versions.find(version => version.status === 'active')
  if (!active) {
    return (
      <div className="row" style={{ padding: '3rem 1rem', textAlign: 'center' }}>
        <p>No active framework version is currently published.</p>
      </div>
    )
  }

  return <Navigate to={`/${active.id}`} replace />
}

/** Redirects an unmatched sub-route back to the selected version's overview. */
function VersionRootRedirect() {
  const { frameworkVersion } = useParams<{ frameworkVersion: string }>()
  return <Navigate to={`/${frameworkVersion}`} replace />
}

function VersionedApp() {
  return (
    <FrameworkVersionProvider>
      <GlobalNav />
      <main className="l-main" style={{ padding: '2rem 0', minHeight: '80vh', background: '#f5f5f5' }}>
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            <Route index element={<Overview />} />
            <Route path="products" element={<ProductsExplorer />} />
            <Route path="products/:id" element={<ProductDetail />} />
            <Route path="dimensions" element={<DimensionsOverview />} />
            <Route path="dimensions/:id" element={<DimensionDetail />} />
            <Route path="dimensions/:dimensionId/metrics/:metricKey" element={<MetricDistribution />} />
            <Route path="about" element={<About />} />
            <Route path="*" element={<VersionRootRedirect />} />
          </Routes>
        </Suspense>
      </main>
    </FrameworkVersionProvider>
  )
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/:frameworkVersion/*" element={<VersionedApp />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  )
}
