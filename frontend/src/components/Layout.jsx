import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout({ children }) {
  const [menuAbierto, setMenuAbierto] = useState(false)
  const { pathname } = useLocation()

  // En móvil el menú es un cajón: se cierra al navegar.
  useEffect(() => { setMenuAbierto(false) }, [pathname])

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <header className="lg:hidden sticky top-0 z-20 flex items-center gap-3 px-4 py-3 bg-panel border-b border-hairline">
        <button
          type="button"
          onClick={() => setMenuAbierto(true)}
          aria-label="Abrir menú"
          aria-expanded={menuAbierto}
          className="p-2 -ml-2 rounded-lg text-fg-3 hover:text-fg hover:bg-panel2"
        >
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
        <p className="text-base font-display text-fg leading-none">Learnix</p>
      </header>

      {menuAbierto && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/40"
          onClick={() => setMenuAbierto(false)}
          aria-hidden="true"
        />
      )}

      <Sidebar abierto={menuAbierto} />
      <main className="lg:ml-64 min-h-screen p-4 sm:p-6 lg:p-8 xl:p-10">
        {children}
      </main>
    </div>
  )
}
