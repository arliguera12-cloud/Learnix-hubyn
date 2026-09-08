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

// Calendario tributario oficial de Hacienda (mh.gob.sv), "Calendario
// Tributario 2026". Los vencimientos mensuales de El Salvador son "los
// primeros diez/quince días hábiles siguientes" al período que se declara,
// así que la fecha exacta se recorre cada mes según fines de semana y
// asuetos — no es un día fijo del calendario. Estos son los días de cada
// mes de 2026 ya ajustados por Hacienda; cuando Hacienda publique el
// calendario del año siguiente, hay que reemplazar esta tabla.
const CALENDARIO_2026 = {
  0:  { f07f14: 16, f930: 23 }, // enero
  1:  { f07f14: 13, f930: 20 }, // febrero
  2:  { f07f14: 13, f930: 20 }, // marzo
  3:  { f07f14: 20, f930: 27 }, // abril
  4:  { f07f14: 15, f930: 22 }, // mayo
  5:  { f07f14: 12, f930: 22 }, // junio
  6:  { f07f14: 14, f930: 21 }, // julio
  7:  { f07f14: 20, f930: 27 }, // agosto
  8:  { f07f14: 14, f930: 22 }, // septiembre
  9:  { f07f14: 14, f930: 21 }, // octubre
  10: { f07f14: 16, f930: 23 }, // noviembre
  11: { f07f14: 14, f930: 21 }, // diciembre
}

// Respaldo para meses fuera de la tabla oficial (p. ej. cuando aún no se
// carga el calendario del año siguiente): aproximación por día fijo, igual
// que antes — siempre hay que confirmar la fecha real en mh.gob.sv.
const DIA_APROXIMADO = { f07f14: 10, f930: 15 }

function obtenerDia(anio, mesIndex, campo) {
  const mesCalendario = anio === 2026 ? CALENDARIO_2026[mesIndex] : null
  return mesCalendario ? mesCalendario[campo] : DIA_APROXIMADO[campo]
}

function proximaFecha(campo, nombre, formulario) {
  const hoy = new Date()
  let anio = hoy.getFullYear()
  let mes  = hoy.getMonth()
  let fecha = new Date(anio, mes, obtenerDia(anio, mes, campo), 23, 59, 59, 999)

  if (fecha < hoy) {
    mes += 1
    if (mes > 11) { mes = 0; anio += 1 }
    fecha = new Date(anio, mes, obtenerDia(anio, mes, campo), 23, 59, 59, 999)
  }

  return { formulario, nombre, fecha, aproximada: anio !== 2026 }
}

function calcularObligaciones() {
  const hoy = new Date()
  const obligaciones = [
    proximaFecha('f07f14', 'Declaración de IVA', 'F-07'),
    proximaFecha('f07f14', 'Pago a Cuenta / Retención Renta', 'F-14'),
    proximaFecha('f930',   'Informe mensual de retenciones/percepciones IVA', 'F-930'),
  ]

  // Declaración de Renta anual — 30 de abril (fecha fija, sin ajuste por Hacienda)
  const anioActual = hoy.getFullYear()
  let fechaRenta = new Date(anioActual, 3, 30, 23, 59, 59, 999)
  if (fechaRenta < hoy) fechaRenta = new Date(anioActual + 1, 3, 30, 23, 59, 59, 999)
  obligaciones.push({ formulario: 'Renta', nombre: 'Declaración de Renta anual', fecha: fechaRenta, aproximada: false })

  return obligaciones
    .map((o) => ({ ...o, diasRestantes: Math.ceil((o.fecha - hoy) / 86400000) }))
    .sort((a, b) => a.fecha - b.fecha)
}

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
  const obligaciones = calcularObligaciones()

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

      {/* Calendario tributario */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[0.65rem] font-semibold text-fg-4 uppercase tracking-[0.16em]">
            Próximas obligaciones fiscales
          </h3>
          <span className="text-[0.6rem] text-fg-5">
            {obligaciones.some(o => o.aproximada)
              ? 'algunas fechas son aproximadas · verificá en mh.gob.sv'
              : 'calendario oficial Hacienda 2026'}
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-hairline border border-hairline rounded-xl overflow-hidden">
          {obligaciones.map(({ formulario, nombre, fecha, diasRestantes, aproximada }) => (
            <div key={formulario} className="bg-panel p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-[0.65rem] uppercase tracking-wider text-fg-4">
                  {formulario}
                </span>
                <span className={
                  diasRestantes <= 3 ? 'badge-err' : diasRestantes <= 7 ? 'badge-warn' : 'badge-ok'
                }>
                  {diasRestantes === 0 ? 'hoy' : diasRestantes === 1 ? '1 día' : `${diasRestantes} días`}
                </span>
              </div>
              <p className="text-sm text-fg leading-snug">{nombre}</p>
              <p className="text-xs text-fg-4 mt-1.5">
                {fecha.toLocaleDateString('es-SV', { day: '2-digit', month: 'long', year: 'numeric' })}
                {aproximada && ' (aprox.)'}
              </p>
            </div>
          ))}
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
