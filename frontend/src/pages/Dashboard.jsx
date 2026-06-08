import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../services/supabase'
import { useAuth } from '../services/auth'
import api from '../services/api'

const MODULOS = [
  { to: '/ventas',            icon: '📤', label: 'Ventas',
    desc: 'CCF, NC, ND',  anexo: 'Anexos 1 y 2', color: 'from-blue-500/10 to-transparent' },
  { to: '/compras',           icon: '📥', label: 'Compras',
    desc: 'CCF recibidos', anexo: 'Anexo 3',      color: 'from-purple-500/10 to-transparent' },
  { to: '/retenciones',       icon: '✂️',  label: 'Retenciones',
    desc: 'DTE-07',        anexo: 'Casilla 162',  color: 'from-amber-500/10 to-transparent' },
  { to: '/sujetos-excluidos', icon: '📋', label: 'Sujetos Excluidos',
    desc: 'DTE-14',        anexo: 'Casilla 66',   color: 'from-emerald-500/10 to-transparent' },
  { to: '/clientes',          icon: '👥', label: 'Clientes',
    desc: 'Directorio',    anexo: 'Receptores',   color: 'from-sky-500/10 to-transparent' },
  { to: '/proveedores',       icon: '🏢', label: 'Proveedores',
    desc: 'Directorio',    anexo: 'Emisores',     color: 'from-rose-500/10 to-transparent' },
]

const STATS_CONFIG = [
  { key: 'ventas',      tabla: 'db_ventas',      label: 'Ventas',           icon: '📤', color: 'text-blue-400',    bg: 'bg-blue-500/10' },
  { key: 'compras',     tabla: 'db_compras',     label: 'Compras',          icon: '📥', color: 'text-purple-400',  bg: 'bg-purple-500/10' },
  { key: 'retenciones', tabla: 'db_retenciones', label: 'Retenciones',      icon: '✂️',  color: 'text-amber-400',   bg: 'bg-amber-500/10' },
  { key: 'sujetos',     tabla: 'db_sujetos',     label: 'Sujetos Excluidos',icon: '📋', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
]

export default function Dashboard() {
  const { session } = useAuth()
  const [stats,    setStats]    = useState({ ventas: 0, compras: 0, retenciones: 0, sujetos: 0 })
  const [backend,  setBackend]  = useState(null) // null=cargando, true/false
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    async function cargar() {
      // Conteos desde Supabase
      try {
        const counts = {}
        await Promise.all(
          STATS_CONFIG.map(async ({ key, tabla }) => {
            const { count } = await supabase.from(tabla).select('*', { count: 'exact', head: true })
            counts[key] = count ?? 0
          })
        )
        setStats(counts)
      } catch {
        // tablas aún no creadas
      }

      // Health del backend
      try {
        await api.get('/health')
        setBackend(true)
      } catch {
        setBackend(false)
      }

      setLoading(false)
    }
    cargar()
  }, [])

  const email    = session?.user?.email ?? 'usuario'
  const totalDTE = Object.values(stats).reduce((s, v) => s + v, 0)

  return (
    <div className="max-w-5xl mx-auto space-y-7">

      {/* Bienvenida */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Dashboard</h2>
          <p className="text-sm text-slate-400 mt-0.5">
            {email} · {new Date().toLocaleDateString('es-SV', { day: '2-digit', month: 'long', year: 'numeric' })}
          </p>
        </div>
        <div className="text-right hidden sm:block">
          <p className="text-2xl font-bold text-white tabular-nums">
            {loading ? '—' : totalDTE.toLocaleString()}
          </p>
          <p className="text-xs text-slate-500">DTEs procesados</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {STATS_CONFIG.map(({ key, label, icon, color, bg }) => (
          <div key={key} className="card flex items-center gap-3">
            <div className={`${bg} rounded-xl h-10 w-10 flex items-center justify-center shrink-0`}>
              <span className="text-xl leading-none">{icon}</span>
            </div>
            <div>
              <p className={`text-2xl font-bold tabular-nums ${color}`}>
                {loading ? <span className="text-slate-600">—</span> : stats[key].toLocaleString()}
              </p>
              <p className="text-xs text-slate-500 leading-tight">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Estado del sistema */}
      <div className="card">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Estado del sistema
        </h3>
        <div className="flex flex-wrap gap-4">
          <StatusRow
            label="Backend API"
            status={backend}
            textOn="conectado"
            textOff="sin conexión"
          />
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-slate-600"/>
            <span className="text-xs text-slate-400">Groq llama-3.3-70b</span>
            <span className="badge-warn">configurable</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-slate-600"/>
            <span className="text-xs text-slate-400">Vertex AI Gemini</span>
            <span className="badge-warn">configurable</span>
          </div>
        </div>
      </div>

      {/* Módulos */}
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Módulos
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {MODULOS.map(({ to, icon, label, desc, anexo, color }) => (
            <Link
              key={to}
              to={to}
              className="card overflow-hidden relative hover:border-brand-500/40 hover:bg-surface-700 transition-all duration-150 group"
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${color} pointer-events-none`}/>
              <div className="relative">
                <span className="text-2xl block mb-2 leading-none">{icon}</span>
                <p className="font-semibold text-white group-hover:text-brand-400 transition-colors text-sm">
                  {label}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
                <span className="inline-block mt-2 text-xs text-slate-600 bg-surface-800 px-2 py-0.5 rounded-full">
                  {anexo}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>

    </div>
  )
}

function StatusRow({ label, status, textOn, textOff }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`h-2 w-2 rounded-full ${
          status === null ? 'bg-slate-500' :
          status ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
        }`}
      />
      <span className="text-xs text-slate-400">{label}</span>
      <span className={status === null ? 'badge-warn' : status ? 'badge-ok' : 'badge-err'}>
        {status === null ? 'verificando' : status ? textOn : textOff}
      </span>
    </div>
  )
}
