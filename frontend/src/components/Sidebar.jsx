import { NavLink, useNavigate } from 'react-router-dom'
import { signOut } from '../services/auth'

const NAV = [
  { to: '/',                  icon: '🏠', label: 'Dashboard',         group: null },
  { to: '/ventas',            icon: '📤', label: 'Ventas',            group: 'Extractores' },
  { to: '/compras',           icon: '📥', label: 'Compras',           group: 'Extractores' },
  { to: '/retenciones',       icon: '✂️',  label: 'Retenciones',      group: 'Extractores' },
  { to: '/sujetos-excluidos', icon: '📋', label: 'Sujetos Excluidos', group: 'Extractores' },
  { to: '/clientes',          icon: '👥', label: 'Clientes',          group: 'Directorios' },
  { to: '/proveedores',       icon: '🏢', label: 'Proveedores',       group: 'Directorios' },
]

export default function Sidebar() {
  const navigate = useNavigate()

  async function handleLogout() {
    await signOut()
    navigate('/login')
  }

  // Agrupar items de nav
  const grupos = []
  let grupoActual = undefined // sentinel distinto de null para forzar el primer push
  for (const item of NAV) {
    if (item.group !== grupoActual) {
      grupoActual = item.group
      grupos.push({ label: item.group, items: [item] })
    } else {
      grupos[grupos.length - 1].items.push(item)
    }
  }

  return (
    <aside className="fixed inset-y-0 left-0 w-56 bg-sb-bg border-r border-sb-hair flex flex-col z-30">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-sb-hair">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-lg bg-brand-500/20 flex items-center justify-center shrink-0">
            <span className="text-sm">📊</span>
          </div>
          <div>
            <p className="text-[10px] text-sb-txt-mute uppercase tracking-widest leading-none mb-0.5">
              Learnix
            </p>
            <h1 className="text-sm font-display text-sb-txt-hi leading-none">DTE Hub</h1>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {grupos.map(({ label, items }) => (
          <div key={label || '_root'}>
            {label && (
              <p className="px-3 mb-1 text-[10px] uppercase tracking-widest text-sb-txt-mute font-semibold">
                {label}
              </p>
            )}
            <div className="space-y-0.5">
              {items.map(({ to, icon, label: itemLabel }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors duration-100 ` +
                    (isActive
                      ? 'bg-gold/10 text-sb-txt-hi font-medium border-l-2 border-gold pl-[10px]'
                      : 'text-sb-txt hover:text-sb-txt-hi hover:bg-white/5')
                  }
                >
                  <span className="text-base leading-none w-5 text-center">{icon}</span>
                  <span className="truncate">{itemLabel}</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-2 py-3 border-t border-sb-hair">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-sb-txt-mute
                     hover:text-cinnabar hover:bg-cinnabar/10 transition-colors duration-100"
        >
          <span className="w-5 text-center text-base leading-none">🚪</span>
          <span>Cerrar sesión</span>
        </button>
      </div>
    </aside>
  )
}
