import { lazy, Suspense, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import DashboardLayout from './layouts/DashboardLayout/DashboardLayout'

const CortezaPage = lazy(() => import('./pages/Corteza/CortezaPage'))
const ExplorarPage = lazy(() => import('./pages/Explorar/ExplorarPage'))
const SinapsisPage = lazy(() => import('./pages/Sinapsis/SinapsisPage'))
const ActividadPage = lazy(() => import('./pages/Actividad/ActividadPage'))
const DimensionesPage = lazy(() => import('./pages/Dimensiones/DimensionesPage'))
const SaludPage = lazy(() => import('./pages/Salud/SaludPage'))

const LazyRoute = ({ children }: { children: ReactNode }) => (
  <Suspense fallback={<div className="loading">Cargando...</div>}>{children}</Suspense>
)

const App = () => (
  <Routes>
    <Route element={<DashboardLayout />}>
      <Route index element={<Navigate to="/corteza" replace />} />
      <Route path="corteza" element={<LazyRoute><CortezaPage /></LazyRoute>} />
      <Route path="explorar" element={<LazyRoute><ExplorarPage /></LazyRoute>} />
      <Route path="explorar/:concepto" element={<LazyRoute><ExplorarPage /></LazyRoute>} />
      <Route path="sinapsis" element={<LazyRoute><SinapsisPage /></LazyRoute>} />
      <Route path="actividad" element={<LazyRoute><ActividadPage /></LazyRoute>} />
      <Route path="dimensiones" element={<LazyRoute><DimensionesPage /></LazyRoute>} />
      <Route path="salud" element={<LazyRoute><SaludPage /></LazyRoute>} />
    </Route>
  </Routes>
)

export default App
