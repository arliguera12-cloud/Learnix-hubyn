import { NavLink, useNavigate } from 'react-router-dom'
import { signOut } from '../services/auth'
import ThemeToggle from './ThemeToggle'
import {
  IconLibro, IconVentas, IconCompras, IconRetenciones,
  IconSujetos, IconClientes, IconProveedores, IconSalir, IconSeccion,
} from './Icons'

const NAV = [
  { to: '/dashboard',         Icon: IconLibro,       label: 'Dashboard',         group: null },
  { to: '/ventas',            Icon: IconVentas,      label: 'Ventas',            group: 'Extractores' },
  { to: '/compras',           Icon: IconCompras,     label: 'Compras',           group: 'Extractores' },
  { to: '/retenciones',       Icon: IconRetenciones, label: 'Retenciones',       group: 'Extractores' },
  { to: '/sujetos-excluidos', Icon: IconSujetos,     label: 'Sujetos Excluidos', group: 'Extractores' },
  { to: '/clientes',          Icon: IconClientes,    label: 'Clientes',          group: 'Directorios' },
  { to: '/proveedores',       Icon: IconProveedores, label: 'Proveedores',       group: 'Directorios' },
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
    <aside className="fixed inset-y-0 left-0 w-56 bg-panel border-r border-hairline flex flex-col z-30">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-hairline">
        <div className="flex items-baseline gap-2">
          <IconSeccion className="text-xl text-accent" />
          <div>
            <p className="text-sm font-display text-fg leading-none">Learnix</p>
            <p className="text-[9px] text-fg-4 uppercase tracking-[0.2em] leading-none mt-1">
              DTE Hub
            </p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {grupos.map(({ label, items }) => (
          <div key={label || '_root'}>
            {label && (
              <p className="px-3 mb-1.5 text-[10px] uppercase tracking-[0.16em] text-fg-4 font-semibold">
                {label}
              </p>
            )}
            <div className="space-y-0.5">
              {items.map(({ to, Icon, label: itemLabel }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors duration-100 ` +
                    (isActive
                      ? 'bg-accent/10 text-fg font-medium border-l-2 border-accent pl-[10px]'
                      : 'text-fg-3 hover:text-fg hover:bg-panel2')
                  }
                >
                  <Icon className="w-[18px] h-[18px] shrink-0" />
                  <span className="truncate">{itemLabel}</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-2 py-3 border-t border-hairline space-y-1">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-fg-4
                     hover:text-accent hover:bg-accent/10 transition-colors duration-100"
        >
          <IconSalir className="w-[18px] h-[18px] shrink-0" />
          <span>Cerrar sesión</span>
        </button>
        <div className="flex items-center justify-between px-3 py-1.5">
          <span className="text-xs text-fg-4">Tema</span>
          <ThemeToggle className="text-fg-4 hover:text-fg" />
        </div>
      </div>
    </aside>
  )
}
