import { NavLink, useNavigate } from 'react-router-dom'
import { signOut } from '../services/auth'

const NAV = [
  { to: '/',                 icon: '🏠', label: 'Dashboard' },
  { to: '/ventas',           icon: '📤', label: 'Ventas' },
  { to: '/compras',          icon: '📥', label: 'Compras' },
  { to: '/retenciones',      icon: '✂️',  label: 'Retenciones' },
  { to: '/sujetos-excluidos',icon: '📋', label: 'Sujetos Excluidos' },
  { to: '/clientes',         icon: '👥', label: 'Clientes' },
  { to: '/proveedores',      icon: '🏢', label: 'Proveedores' },
]

export default function Sidebar() {
  const navigate = useNavigate()

  async function handleLogout() {
    await signOut()
    navigate('/login')
  }

  return (
    <aside className="fixed inset-y-0 left-0 w-56 bg-surface-800 border-r border-surface-600 flex flex-col z-30">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-surface-600">
        <p className="text-xs text-slate-500 uppercase tracking-widest mb-0.5">Learnix</p>
        <h1 className="text-base font-bold text-white leading-tight">DTE Hub</h1>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {NAV.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors duration-100 ` +
              (isActive
                ? 'bg-brand-500/20 text-brand-400 font-medium'
                : 'text-slate-400 hover:text-slate-100 hover:bg-surface-600')
            }
          >
            <span className="text-base leading-none">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-surface-600">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-400
                     hover:text-red-400 hover:bg-red-900/20 transition-colors duration-100"
        >
          <span>🚪</span> Cerrar sesión
        </button>
      </div>
    </aside>
  )
}
