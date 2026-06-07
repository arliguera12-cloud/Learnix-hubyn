import { Link } from 'react-router-dom'
import { signOut } from '../services/auth'

const MODULOS = [
  { path: '/ventas', label: 'Extractor Ventas', icon: '📤' },
  { path: '/compras', label: 'Extractor Compras', icon: '📥' },
  { path: '/retenciones', label: 'Extractor Retenciones', icon: '🔒' },
  { path: '/sujetos-excluidos', label: 'Sujetos Excluidos', icon: '📋' },
  { path: '/clientes', label: 'Directorio Clientes', icon: '👥' },
  { path: '/proveedores', label: 'Directorio Proveedores', icon: '🏢' },
]

export default function Dashboard() {
  return (
    <div className="dashboard">
      <header>
        <h1>Learnix DTE Hub</h1>
        <button onClick={signOut}>Cerrar sesión</button>
      </header>

      <main>
        <h2>Módulos disponibles</h2>
        <div className="modulos-grid">
          {MODULOS.map(({ path, label, icon }) => (
            <Link key={path} to={path} className="modulo-card">
              <span className="modulo-icon">{icon}</span>
              <span className="modulo-label">{label}</span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  )
}
