import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
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
  const location = useLocation()
  const navRef = useRef(null)
  const [indicador, setIndicador] = useState(null)

  async function handleLogout() {
    await signOut()
    navigate('/login')
  }

  // Barra que se desliza hacia el item activo en vez de aparecer/desaparecer
  // de golpe — la navegación se lee como un mismo espacio que se mueve, no
  // como recargas de estado independientes entre sí.
  useEffect(() => {
    const activo = navRef.current?.querySelector('a[aria-current="page"]')
    setIndicador(activo ? { top: activo.offsetTop, height: activo.offsetHeight } : null)
  }, [location.pathname])

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
    <aside className="fixed inset-y-0 left-0 w-64 bg-panel border-r border-hairline flex flex-col z-30">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-hairline">
        <div className="flex items-center gap-3">
          <IconSeccion className="w-9 h-9 text-lg" />
          <div>
            <p className="text-[15px] font-semibold text-fg leading-none">Learnix</p>
            <p className="text-[10px] text-fg-4 uppercase tracking-[0.2em] leading-none mt-1.5">
              DTE Hub
            </p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav ref={navRef} className="relative flex-1 overflow-y-auto py-4 px-3 space-y-5">
        {indicador && (
          <div
            aria-hidden="true"
            className="absolute inset-x-3 rounded-lg bg-accent/10
                       transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]
                       motion-reduce:transition-none pointer-events-none"
            style={{ transform: `translateY(${indicador.top}px)`, height: indicador.height }}
          />
        )}
        {grupos.map(({ label, items }) => (
          <div key={label || '_root'}>
            {label && (
              <p className="px-3 mb-2 text-[11px] uppercase tracking-[0.16em] text-fg-4 font-semibold">
                {label}
              </p>
            )}
            <div className="space-y-1">
              {items.map(({ to, Icon, label: itemLabel }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `relative z-10 flex items-center gap-3 px-3 py-2.5 rounded-lg text-[15px] transition-colors duration-100 ` +
                    (isActive
                      ? 'text-accent font-medium'
                      : 'text-fg-3 hover:text-fg hover:bg-panel2')
                  }
                >
                  <Icon className="w-5 h-5 shrink-0" />
                  <span className="truncate">{itemLabel}</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-hairline space-y-1.5">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-[15px] text-fg-4
                     hover:text-accent hover:bg-accent/10 transition-colors duration-100"
        >
          <IconSalir className="w-5 h-5 shrink-0" />
          <span>Cerrar sesión</span>
        </button>
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-sm text-fg-4">Tema</span>
          <ThemeToggle className="text-fg-4 hover:text-fg" />
        </div>
      </div>
    </aside>
  )
}
