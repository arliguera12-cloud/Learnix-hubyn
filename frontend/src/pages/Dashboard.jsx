import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../services/supabase'
import { useAuth } from '../services/auth'
import api from '../services/api'
import {
  IconVentas, IconCompras, IconRetenciones, IconSujetos,
  IconClientes, IconProveedores,
} from '../components/Icons'

const MODULOS = [
  { to: '/ventas',            Icon: IconVentas,      label: 'Ventas',
    desc: 'CCF, NC, ND',   anexo: 'Anexos 1 y 2' },
  { to: '/compras',           Icon: IconCompras,     label: 'Compras',
    desc: 'CCF recibidos', anexo: 'Anexo 3' },
  { to: '/retenciones',       Icon: IconRetenciones, label: 'Retenciones',
    desc: 'DTE-07',        anexo: 'Casilla 162' },
  { to: '/sujetos-excluidos', Icon: IconSujetos,     label: 'Sujetos Excluidos',
    desc: 'DTE-14',        anexo: 'Casilla 66' },
  { to: '/clientes',          Icon: IconClientes,    label: 'Clientes',
    desc: 'Directorio',    anexo: 'Receptores' },
  { to: '/proveedores',       Icon: IconProveedores, label: 'Proveedores',
    desc: 'Directorio',    anexo: 'Emisores' },
]

const STATS_CONFIG = [
  { key: 'ventas',      tabla: 'db_ventas',      label: 'Ventas',            Icon: IconVentas },
  { key: 'compras',     tabla: 'db_compras',     label: 'Compras',           Icon: IconCompras },
  { key: 'retenciones', tabla: 'db_retenciones', label: 'Retenciones',       Icon: IconRetenciones },
  { key: 'sujetos',     tabla: 'db_sujetos',     label: 'Sujetos Excluidos', Icon: IconSujetos },
]

export default function Dashboard() {
  const { session } = useAuth()
  const [stats,    setStats]    = useState({ ventas: 0, compras: 0, retenciones: 0, sujetos: 0 })
  const [backend,  setBackend]  = useState(null) // null=cargando, true/false
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    let cancelado = false

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
        if (!cancelado) setStats(counts)
      } catch {
        // tablas aún no creadas
      }

      // Health del backend
      try {
        await api.get('/health')
        if (!cancelado) setBackend(true)
      } catch {
        if (!cancelado) setBackend(false)
      }

      if (!cancelado) setLoading(false)
    }

    cargar()
    return () => { cancelado = true }
  }, [])

  const email    = session?.user?.email ?? 'usuario'
  const totalDTE = Object.values(stats).reduce((s, v) => s + v, 0)

  return (
    <div className="max-w-[90rem] mx-auto space-y-7">

      {/* Cabecera editorial */}
      <div className="flex items-end justify-between border-b border-hairline pb-4">
        <div>
          <p className="text-[0.65rem] uppercase tracking-[0.18em] text-fg-4 font-semibold mb-1">
            Libro mayor
          </p>
          <h2 className="text-3xl text-fg leading-none">Dashboard</h2>
          <p className="text-sm text-fg-4 mt-2">
            {email} · {new Date().toLocaleDateString('es-SV', { day: '2-digit', month: 'long', year: 'numeric' })}
          </p>
        </div>
        <div className="text-right hidden sm:block">
          <p className="text-4xl text-fg tabular-nums font-display leading-none">
            {loading ? '—' : totalDTE.toLocaleString('es-SV')}
          </p>
          <p className="text-[0.65rem] uppercase tracking-[0.14em] text-fg-4 mt-1.5">
            DTE procesados
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-hairline border border-hairline rounded-xl overflow-hidden">
        {STATS_CONFIG.map(({ key, label, Icon }) => (
          <div key={key} className="bg-panel p-4">
            <div className="flex items-center justify-between mb-3">
              <Icon className="w-5 h-5 text-fg-4" />
              <span className="font-mono text-[0.6rem] text-fg-5 uppercase tracking-wider">
                {loading ? '' : 'registros'}
              </span>
            </div>
            <p className="text-3xl tabular-nums font-display text-fg leading-none">
              {loading ? <span className="text-fg-5">—</span> : stats[key].toLocaleString('es-SV')}
            </p>
            <p className="text-xs text-fg-4 mt-1.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Estado del sistema */}
      <div className="card">
        <h3 className="text-[0.65rem] font-semibold text-fg-4 uppercase tracking-[0.16em] mb-3">
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
            <span className="h-1.5 w-1.5 rounded-full bg-fg-5" />
            <span className="text-xs text-fg-3">Groq llama-3.3-70b</span>
            <span className="badge-warn">configurable</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-fg-5" />
            <span className="text-xs text-fg-3">Vertex AI Gemini</span>
            <span className="badge-warn">configurable</span>
          </div>
        </div>
      </div>

      {/* Módulos */}
      <div>
        <h3 className="text-[0.65rem] font-semibold text-fg-4 uppercase tracking-[0.16em] mb-3">
          Módulos
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-px bg-hairline border border-hairline rounded-xl overflow-hidden">
          {MODULOS.map(({ to, Icon, label, desc, anexo }) => (
            <Link
              key={to}
              to={to}
              className="bg-panel p-5 hover:bg-panel2 transition-colors duration-150 group
                         border-l-2 border-transparent hover:border-accent"
            >
              <Icon className="w-6 h-6 text-fg-4 group-hover:text-accent transition-colors mb-3" />
              <p className="font-medium text-fg text-sm">{label}</p>
              <p className="text-xs text-fg-4 mt-0.5">{desc}</p>
              <span className="inline-block mt-3 text-[0.65rem] font-mono uppercase tracking-wider
                               text-fg-4 border border-hairline px-2 py-0.5 rounded-full">
                {anexo}
              </span>
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
        className={`h-1.5 w-1.5 rounded-full ${
          status === null ? 'bg-fg-5' :
          status ? 'bg-accent2 animate-pulse' : 'bg-accent'
        }`}
      />
      <span className="text-xs text-fg-3">{label}</span>
      <span className={status === null ? 'badge-warn' : status ? 'badge-ok' : 'badge-err'}>
        {status === null ? 'verificando' : status ? textOn : textOff}
      </span>
    </div>
  )
}
