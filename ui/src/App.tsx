import { HashRouter, Routes, Route, Navigate } from 'react-router'
import { lazy, Suspense } from 'react'
import GlobalNav from './components/GlobalNav'
import LoadingSpinner from './components/LoadingSpinner'

const Overview = lazy(() => import('./views/Overview'))
const ProductsExplorer = lazy(() => import('./views/ProductsExplorer'))
const ProductDetail = lazy(() => import('./views/ProductDetail'))
const DimensionsOverview = lazy(() => import('./views/DimensionsOverview'))
const DimensionDetail = lazy(() => import('./views/DimensionDetail'))
const MetricDistribution = lazy(() => import('./views/MetricDistribution'))
const About = lazy(() => import('./views/About'))

export default function App() {
  return (
    <HashRouter>
      <GlobalNav />
      <main className="l-main" style={{ padding: '2rem 0', minHeight: '80vh', background: '#f5f5f5' }}>
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/products" element={<ProductsExplorer />} />
            <Route path="/products/:id" element={<ProductDetail />} />
            <Route path="/dimensions" element={<DimensionsOverview />} />
            <Route path="/dimensions/:id" element={<DimensionDetail />} />
            <Route path="/dimensions/:dimensionId/metrics/:metricKey" element={<MetricDistribution />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
    </HashRouter>
  )
}
