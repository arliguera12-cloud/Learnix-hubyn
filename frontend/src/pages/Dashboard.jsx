import { useEffect, useRef, useState } from 'react'
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

// Calendario tributario (aproximado): reglas generales de vencimiento de
// El Salvador (Ministerio de Hacienda) — declaraciones mensuales el día 10
// (IVA F-07, Pago a Cuenta/Retención Renta F-14) o 15 (Informe mensual de
// retenciones/percepciones/anticipos IVA, F-930) del mes siguiente al
// período que declaran, y Declaración de Renta anual el 30 de abril. Cuando
// esa fecha cae en fin de semana o feriado, Hacienda la corre al siguiente
// día hábil — ese ajuste exacto no se calcula acá (requeriría el calendario
// oficial de feriados), así que la fecha mostrada es una aproximación:
// siempre hay que confirmar la fecha límite real en mh.gob.sv antes de
// declarar.
const OBLIGACIONES_BASE = [
  { formulario: 'F-07',  nombre: 'Declaración de IVA',                                   dia: 10 },
  { formulario: 'F-14',  nombre: 'Pago a Cuenta / Retención Renta',                       dia: 10 },
  { formulario: 'F-930', nombre: 'Informe mensual de retenciones/percepciones IVA',       dia: 15 },
]

function proximaFecha(dia, mesOffset = 0) {
  const hoy = new Date()
  const fecha = new Date(hoy.getFullYear(), hoy.getMonth() + mesOffset, dia)
  fecha.setHours(23, 59, 59, 999)
  return fecha
}

function calcularObligaciones() {
  const hoy = new Date()
  const obligaciones = OBLIGACIONES_BASE.map(({ formulario, nombre, dia }) => {
    let fecha = proximaFecha(dia, 0)
    if (fecha < hoy) fecha = proximaFecha(dia, 1)
    return { formulario, nombre, fecha }
  })

  // Declaración de Renta anual — 30 de abril
  const anioActual = hoy.getFullYear()
  let fechaRenta = new Date(anioActual, 3, 30, 23, 59, 59, 999)
  if (fechaRenta < hoy) fechaRenta = new Date(anioActual + 1, 3, 30, 23, 59, 59, 999)
  obligaciones.push({ formulario: 'Renta', nombre: 'Declaración de Renta anual', fecha: fechaRenta })

  return obligaciones
    .map((o) => ({ ...o, diasRestantes: Math.ceil((o.fecha - hoy) / 86400000) }))
    .sort((a, b) => a.fecha - b.fecha)
}

/**
 * Cuenta desde el valor previo hasta `value` — el "libro mayor" tallándose
 * en pantalla en vez de aparecer ya sumado. Arranca solo cuando `enabled`
 * pasa a true (los datos reales ya llegaron), y respeta reduced-motion
 * mostrando el número final de una vez.
 */
function useCountUp(value, enabled, duration = 900) {
  const [display, setDisplay] = useState(value)
  const anterior = useRef(value)

  useEffect(() => {
    if (!enabled) { setDisplay(value); anterior.current = value; return }
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const desde = anterior.current
    const hasta = value
    if (reduceMotion || desde === hasta) { setDisplay(hasta); anterior.current = hasta; return }

    const inicio = performance.now()
    let raf
    function tick(ahora) {
      const t = Math.min(1, (ahora - inicio) / duration)
      const suavizado = 1 - Math.pow(1 - t, 3)
      setDisplay(Math.round(desde + (hasta - desde) * suavizado))
      if (t < 1) raf = requestAnimationFrame(tick)
      else anterior.current = hasta
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, enabled, duration])

  return display
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

  const cargado = !loading
  const totalAnimado = useCountUp(totalDTE, cargado)
  const statsAnimados = {
    ventas:      useCountUp(stats.ventas, cargado),
    compras:     useCountUp(stats.compras, cargado),
    retenciones: useCountUp(stats.retenciones, cargado),
    sujetos:     useCountUp(stats.sujetos, cargado),
  }

  return (
    <div className="max-w-[90rem] mx-auto space-y-7">

      {/* Cabecera */}
      <div className="flex items-end justify-between pb-1">
        <div>
          <p className="text-[0.65rem] uppercase tracking-[0.18em] text-fg-4 font-semibold mb-1">
            Resumen
          </p>
          <h2 className="text-2xl text-fg leading-none">Dashboard</h2>
          <p className="text-sm text-fg-4 mt-2">
            {email} · {new Date().toLocaleDateString('es-SV', { day: '2-digit', month: 'long', year: 'numeric' })}
          </p>
        </div>
        <div className="text-right hidden sm:block">
          <p className="text-4xl font-bold text-fg tabular-nums leading-none">
            {loading ? '—' : totalAnimado.toLocaleString('es-SV')}
          </p>
          <div className="flex items-center justify-end gap-1.5 mt-1.5">
            <span className="h-[2px] w-4 bg-accent rounded-full" />
            <p className="text-[0.65rem] uppercase tracking-[0.14em] text-fg-4">
              DTE procesados
            </p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STATS_CONFIG.map(({ key, label, Icon }, i) => (
          <div
            key={key}
            className="tile p-4 animate-rise"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
                <Icon className="w-4 h-4 text-accent" />
              </span>
              <span className="font-mono text-[0.6rem] text-fg-5 uppercase tracking-wider">
                {loading ? '' : 'registros'}
              </span>
            </div>
            <p className="text-3xl font-bold tabular-nums text-fg leading-none">
              {loading ? <span className="text-fg-5">—</span> : statsAnimados[key].toLocaleString('es-SV')}
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
            <span className="text-xs text-fg-3">Verificación con IA (principal)</span>
            <span className="badge-warn">configurable</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-fg-5" />
            <span className="text-xs text-fg-3">Verificación con IA (respaldo)</span>
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
          <span className="text-[0.6rem] text-fg-5">fechas aproximadas · verificá en mh.gob.sv</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {obligaciones.map(({ formulario, nombre, fecha, diasRestantes }, i) => (
            <div
              key={formulario}
              className="tile p-4 animate-rise"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-[0.65rem] uppercase tracking-wider text-accent bg-accent/10 rounded px-1.5 py-0.5">
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
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {MODULOS.map(({ to, Icon, label, desc, anexo }, i) => (
            <Link
              key={to}
              to={to}
              style={{ animationDelay: `${i * 50}ms` }}
              className="tile p-5 hover:shadow-card-lg transition-all duration-200 group animate-rise
                         motion-safe:hover:-translate-y-0.5"
            >
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-panel2
                               group-hover:bg-accent/10 transition-colors mb-3">
                <Icon className="w-5 h-5 text-fg-4 group-hover:text-accent group-hover:translate-x-0.5 transition-all" />
              </span>
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
          status ? 'bg-accent2 animate-pulse' : 'bg-danger'
        }`}
      />
      <span className="text-xs text-fg-3">{label}</span>
      <span className={status === null ? 'badge-warn' : status ? 'badge-ok' : 'badge-err'}>
        {status === null ? 'verificando' : status ? textOn : textOff}
      </span>
    </div>
  )
}
