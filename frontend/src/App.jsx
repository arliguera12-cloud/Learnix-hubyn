import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './services/auth'
import Layout from './components/Layout'

import Login            from './pages/Login'
import Dashboard        from './pages/Dashboard'
import Ventas           from './pages/Ventas'
import Compras          from './pages/Compras'
import Retenciones      from './pages/Retenciones'
import SujetosExcluidos from './pages/SujetosExcluidos'
import Clientes         from './pages/Clientes'
import Proveedores      from './pages/Proveedores'

function ProtectedRoute({ children }) {
  const { session, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-900 flex items-center justify-center">
        <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!session) return <Navigate to="/login" replace />

  return <Layout>{children}</Layout>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/ventas" element={<ProtectedRoute><Ventas /></ProtectedRoute>} />
        <Route path="/compras" element={<ProtectedRoute><Compras /></ProtectedRoute>} />
        <Route path="/retenciones" element={<ProtectedRoute><Retenciones /></ProtectedRoute>} />
        <Route path="/sujetos-excluidos" element={<ProtectedRoute><SujetosExcluidos /></ProtectedRoute>} />
        <Route path="/clientes" element={<ProtectedRoute><Clientes /></ProtectedRoute>} />
        <Route path="/proveedores" element={<ProtectedRoute><Proveedores /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
