import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../services/supabase'
import { useAuth } from '../services/auth'
import api from '../services/api'

const MODULOS = [
  { to: '/ventas',            icon: '📤', label: 'Ventas',           desc: 'CCF, NC, ND — Anexos 1 y 2' },
  { to: '/compras',           icon: '📥', label: 'Compras',          desc: 'CCF recibidos — Anexo 3' },
  { to: '/retenciones',       icon: '✂️',  label: 'Retenciones',     desc: 'DTE-07 — Casilla 162 / 1%' },
  { to: '/sujetos-excluidos', icon: '📋', label: 'Sujetos Excluidos',desc: 'DTE-14 — Casilla 66 / 10%' },
  { to: '/clientes',          icon: '👥', label: 'Clientes',         desc: 'Directorio de receptores' },
  { to: '/proveedores',       icon: '🏢', label: 'Proveedores',      desc: 'Directorio de emisores' },
]

export default function Dashboard() {
  const { session } = useAuth()
  const [stats,   setStats]   = useState({ ventas: 0, compras: 0, retenciones: 0, sujetos: 0 })
  const [iaStatus, setIaStatus] = useState({ groq: null, vertex: null })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function cargar() {
      try {
        // Conteos desde Supabase
        const tablas = [
          ['ventas',       'db_ventas'],
          ['compras',      'db_compras'],
          ['retenciones',  'db_retenciones'],
          ['sujetos',      'db_sujetos'],
        ]
        const counts = {}
        await Promise.all(
          tablas.map(async ([key, tabla]) => {
            const { count } = await supabase.from(tabla).select('*', { count: 'exact', head: true })
            counts[key] = count ?? 0
          })
        )
        setStats(counts)
      } catch {
        // Si las tablas no existen aún, ignorar
      }

      // Estado del health del backend
      try {
        await api.get('/health')
        setIaStatus({ groq: true, vertex: null })
      } catch {
        setIaStatus({ groq: false, vertex: false })
      }

      setLoading(false)
    }
    cargar()
  }, [])

  const email = session?.user?.email ?? 'usuario'

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Welcome */}
      <div>
        <h2 className="text-xl font-bold text-white">Dashboard</h2>
        <p className="text-sm text-slate-400 mt-0.5">Bienvenido, {email}</p>
      </div>

      {/* Estadísticas */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Ventas',           value: stats.ventas,      icon: '📤', color: 'text-blue-400' },
          { label: 'Compras',          value: stats.compras,     icon: '📥', color: 'text-purple-400' },
          { label: 'Retenciones',      value: stats.retenciones, icon: '✂️',  color: 'text-amber-400' },
          { label: 'Sujetos Excluidos',value: stats.sujetos,     icon: '📋', color: 'text-emerald-400' },
        ].map(({ label, value, icon, color }) => (
          <div key={label} className="card flex items-center gap-3">
            <span className="text-2xl">{icon}</span>
            <div>
              <p className={`text-2xl font-bold ${color}`}>{loading ? '—' : value.toLocaleString()}</p>
              <p className="text-xs text-slate-500">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Estado de IA */}
      <div className="card space-y-2">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Estado del sistema</h3>
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${iaStatus.groq === null ? 'bg-slate-500' : iaStatus.groq ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}/>
            <span className="text-xs text-slate-300">Backend API</span>
            <span className={iaStatus.groq === null ? 'badge-warn' : iaStatus.groq ? 'badge-ok' : 'badge-err'}>
              {iaStatus.groq === null ? 'verificando' : iaStatus.groq ? 'conectado' : 'sin conexión'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-slate-500"/>
            <span className="text-xs text-slate-300">Groq (llama-3.3-70b)</span>
            <span className="badge-warn">configurable</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-slate-500"/>
            <span className="text-xs text-slate-300">Vertex AI (Gemini)</span>
            <span className="badge-warn">configurable</span>
          </div>
        </div>
      </div>

      {/* Módulos */}
      <div>
        <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">Módulos</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {MODULOS.map(({ to, icon, label, desc }) => (
            <Link
              key={to}
              to={to}
              className="card hover:border-brand-500/50 hover:bg-surface-700 transition-all duration-150 group"
            >
              <span className="text-2xl block mb-2">{icon}</span>
              <p className="font-semibold text-white group-hover:text-brand-400 transition-colors">{label}</p>
              <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
