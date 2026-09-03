/**
 * Utilidades compartidas por las páginas de extractores.
 *
 * Ventas.jsx y Compras.jsx tenían copias idénticas de `fmt`, `descargarBlob`
 * y `estadoBadge`; al vivir por duplicado, la corrección del vocabulario de
 * `estado` habría que hacerla dos veces (y ExtractorPage tenía una tercera
 * copia de `fmt`/`descargarBlob`).
 */
import { useRef, useState } from 'react'
import { IconCheck, IconAlerta, IconBuscar } from '../components/Icons'
import { obtenerEstadoLote } from '../services/api'

/**
 * Caja de error para lotes con fallos por documento.
 *
 * Antes era un `<pre>` monoespaciado con `filename: mensaje\n` por línea —
 * en lotes grandes (50+ archivos) se volvía un bloque de texto ilegible,
 * todo del mismo color, sin separar visualmente un archivo de otro. Ahora
 * cada línea es una fila con el nombre del archivo destacado y el motivo
 * aparte, con un límite de filas visibles (colapsa el resto detrás de un
 * "ver N más") para que un lote con muchos errores no tape el resto de la
 * pantalla.
 */
const _MAX_ERRORES_VISIBLES = 6

export function ErrorBox({ mensaje }) {
  const [expandido, setExpandido] = useState(false)
  if (!mensaje) return null

  const lineas = mensaje.split('\n').filter(Boolean)
  const visibles = expandido ? lineas : lineas.slice(0, _MAX_ERRORES_VISIBLES)
  const ocultos = lineas.length - visibles.length

  return (
    <div className="card border-l-2 border-l-red-500 border-y-0 border-r-0 bg-panel">
      <p className="text-red-400 font-semibold text-sm flex items-center gap-1.5 mb-2">
        <IconAlerta className="w-4 h-4 shrink-0" />
        {lineas.length > 1 ? `${lineas.length} documentos con error` : 'Error'}
      </p>
      <ul className="space-y-1.5">
        {visibles.map((linea, i) => {
          const idx = linea.indexOf(':')
          const archivo = idx > -1 ? linea.slice(0, idx) : null
          const detalle = idx > -1 ? linea.slice(idx + 1).trim() : linea
          return (
            <li key={i} className="text-sm flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
              {archivo && (
                <span className="font-mono text-xs text-fg-3 bg-panel2 px-1.5 py-0.5 rounded truncate max-w-[280px]">
                  {archivo}
                </span>
              )}
              <span className="text-red-400/90">{detalle}</span>
            </li>
          )
        })}
      </ul>
      {ocultos > 0 && (
        <button
          type="button"
          onClick={() => setExpandido(true)}
          className="text-xs text-fg-4 hover:text-fg-2 underline mt-2"
        >
          Ver {ocultos} más
        </button>
      )}
    </div>
  )
}

/** Caja de aviso (documentos repetidos omitidos, notas informativas) — mismo lenguaje visual que ErrorBox pero en tono ámbar. */
export function AvisoBox({ mensaje }) {
  const [expandido, setExpandido] = useState(false)
  if (!mensaje) return null

  const [resumen, ...detalle] = mensaje.split('\n').filter(Boolean)

  // Sin detalle (caso de un solo duplicado): un párrafo simple alcanza.
  if (!detalle.length) {
    return (
      <div className="card border-l-2 border-l-amber-500 border-y-0 border-r-0 bg-panel">
        <p className="text-amber-400 text-sm flex items-start gap-2">
          <IconAlerta className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{resumen}</span>
        </p>
      </div>
    )
  }

  // Con detalle (varios duplicados): resumen siempre visible, la lista de
  // nombres colapsa detrás de "Ver N más" en vez de volcarse toda de una.
  const visibles = expandido ? detalle : detalle.slice(0, _MAX_ERRORES_VISIBLES)
  const ocultos = detalle.length - visibles.length

  return (
    <div className="card border-l-2 border-l-amber-500 border-y-0 border-r-0 bg-panel">
      <p className="text-amber-400 text-sm flex items-start gap-2 mb-2">
        <IconAlerta className="w-4 h-4 shrink-0 mt-0.5" />
        <span>{resumen}</span>
      </p>
      <ul className="space-y-1 pl-6">
        {visibles.map((nombre, i) => (
          <li key={i} className="text-xs font-mono text-fg-4 truncate">{nombre}</li>
        ))}
      </ul>
      {ocultos > 0 && (
        <button
          type="button"
          onClick={() => setExpandido(true)}
          className="text-xs text-fg-4 hover:text-fg-2 underline mt-2 ml-6"
        >
          Ver {ocultos} más
        </button>
      )}
    </div>
  )
}

/**
 * Mantiene `resultados` y `declaranteId` de un extractor en sessionStorage.
 *
 * Cada página de extractor guardaba estos dos en `useState` local: al
 * navegar de Ventas a Compras y volver, React desmontaba Ventas y todo lo
 * ya extraído desaparecía de la pantalla, aunque siguiera guardado en
 * Supabase — obligaba a resubir los mismos PDF para volver a verlos. Se usa
 * sessionStorage (no localStorage) porque son resultados de trabajo en
 * curso: tiene sentido que sobrevivan a navegar entre módulos, no que
 * persistan para siempre entre sesiones distintas del navegador.
 */
export function usePersistenciaExtractor(tipo) {
  const key = `learnix_extractor_${tipo}`

  const [resultados, setResultadosState] = useState(() => {
    try {
      const raw = sessionStorage.getItem(key)
      return raw ? JSON.parse(raw).resultados ?? [] : []
    } catch {
      return []
    }
  })
  const [declaranteId, setDeclaranteIdState] = useState(() => {
    try {
      const raw = sessionStorage.getItem(key)
      return raw ? JSON.parse(raw).declaranteId ?? '' : ''
    } catch {
      return ''
    }
  })

  function guardar(nuevosResultados, nuevoDeclaranteId) {
    try {
      sessionStorage.setItem(key, JSON.stringify({ resultados: nuevosResultados, declaranteId: nuevoDeclaranteId }))
    } catch {
      // Lote muy grande para la cuota de sessionStorage: se sigue viendo en
      // pantalla, solo no sobrevive a cambiar de módulo. No es crítico.
    }
  }

  function setResultados(actualizarOArray) {
    setResultadosState(prev => {
      const next = typeof actualizarOArray === 'function' ? actualizarOArray(prev) : actualizarOArray
      guardar(next, declaranteId)
      return next
    })
  }

  function setDeclaranteId(nuevo) {
    setDeclaranteIdState(nuevo)
    guardar(resultados, nuevo)
  }

  return { resultados, setResultados, declaranteId, setDeclaranteId }
}

/**
 * Progreso REAL de una subida por lote troceada en tandas (ver
 * subirLoteEnTandas). El backend procesa cada tanda como un job en
 * background y el frontend hace polling de su avance, así que el progreso
 * es granular incluso dentro de una tanda (no solo al terminarla) — con eso
 * alcanza para un porcentaje real y una estimación de tiempo restante.
 */
function _formatearDuracion(seg) {
  if (seg < 60) return `${seg}s`
  const min = Math.floor(seg / 60)
  const rest = seg % 60
  return rest > 0 ? `${min}m ${rest}s` : `${min}m`
}

export function useProgresoLote() {
  const [progress, setProgress] = useState(null)
  const inicioRef = useRef(0)

  function iniciar(total, totalTandas) {
    inicioRef.current = Date.now()
    setProgress({
      procesados: 0, total, tandaActual: 0, totalTandas,
      pct: 1, etaTexto: null, transcurridoTexto: null, fase: 'procesando',
    })
  }

  /**
   * Se llama en cada poll (cada 2s dentro de una tanda, y al terminarla) con
   * el conteo real hasta ese momento. La ETA usa el ritmo por-documento
   * (transcurrido / procesados) en vez de por-tanda: antes solo se
   * recalculaba al cerrar una tanda completa, así que durante los ~2-20s de
   * una tanda en curso (con lotes de 100+ PDFs, varias tandas de 10) el
   * texto de tiempo restante quedaba congelado aunque la barra sí avanzara.
   */
  function avanzar(procesados, total, tandaActual, totalTandas) {
    const transcurridoMs  = Date.now() - inicioRef.current
    const transcurridoSeg = Math.round(transcurridoMs / 1000)
    const pct = Math.min(99, Math.round((procesados / total) * 100))

    let etaTexto = null
    if (procesados > 0 && procesados < total) {
      const msPorDoc     = transcurridoMs / procesados
      const restanteSeg   = Math.round((msPorDoc * (total - procesados)) / 1000)
      etaTexto = `~${_formatearDuracion(restanteSeg)} restantes`
    }

    setProgress(p => (p ? {
      ...p, procesados, total, tandaActual, totalTandas, pct, etaTexto,
      transcurridoTexto: transcurridoSeg > 0 ? _formatearDuracion(transcurridoSeg) : null,
    } : p))
  }

  function terminar() {
    const transcurridoSeg = Math.round((Date.now() - inicioRef.current) / 1000)
    setProgress(p => (p ? {
      ...p, pct: 100, etaTexto: null,
      transcurridoTexto: _formatearDuracion(transcurridoSeg),
      fase: 'listo',
    } : p))
  }

  function limpiar() {
    setProgress(null)
  }

  return { progress, iniciar, avanzar, terminar, limpiar }
}

// Mismo tope que el backend (routers/procesamiento.py: _MAX_LOTE_ARCHIVOS).
// Con 40 por tanda, cada request dispara hasta 40 llamadas a Visión en
// paralelo (cada una renderiza el PDF a imagen) — confirmado en producción
// que eso puede agotar la memoria del contenedor y tumbarlo a mitad de
// tanda (net::ERR_FAILED casi inmediato, distinto del timeout del proxy
// que corta tandas más largas recién a los 1-3 min). Tandas más chicas
// bajan el pico de memoria simultánea y además terminan bien dentro de
// cualquier timeout de proxy.
export const TAMANO_TANDA = 10

/**
 * Sube `files` en tandas de `TAMANO_TANDA`, una tras otra, y junta los
 * resultados y errores de todas. Así el usuario puede soltar 200+ PDF de una
 * sola vez sin toparse con el límite por request — el troceo pasa
 * desapercibido, solo se nota en que la barra de progreso avanza por tandas.
 *
 * `onProgreso(procesados, total, tandaActual, totalTandas)` se llama al
 * terminar cada tanda, con el conteo real hasta ese momento.
 */
const POLL_INTERVALO_MS = 2000

/**
 * Espera a que un job de lote termine, consultando su progreso cada
 * `POLL_INTERVALO_MS`. Cada consulta es un GET corto — nada que un timeout
 * intermedio (navegador, proxy, Vercel) pueda cortar a mitad de camino,
 * a diferencia de esperar la respuesta directa del POST original (que
 * podía tardar varios minutos y mostraba "Network Error" aunque el
 * servidor terminara bien).
 */
async function _esperarJob(jobId, onProgresoTanda) {
  for (;;) {
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVALO_MS))
    const { data: job } = await obtenerEstadoLote(jobId)
    onProgresoTanda?.(job.procesados, job.total)
    if (job.status === 'done') return job
    if (job.status === 'error') {
      throw new Error(job.error_fatal || 'El procesamiento del lote falló.')
    }
  }
}

export async function subirLoteEnTandas(files, loteApiFn, declaranteId, nombre, onProgreso) {
  const resultados = []
  const errores = []
  let procesados = 0
  let tandaActual = 0
  const totalTandas = Math.ceil(files.length / TAMANO_TANDA)

  for (let i = 0; i < files.length; i += TAMANO_TANDA) {
    const tanda = files.slice(i, i + TAMANO_TANDA)
    const { data: inicio } = await loteApiFn(tanda, declaranteId, nombre)
    const job = await _esperarJob(inicio.job_id, (procesadosTanda) => {
      onProgreso?.(procesados + procesadosTanda, files.length, tandaActual + 1, totalTandas)
    })
    resultados.push(...(job.resultados ?? []))
    errores.push(...(job.errores ?? []))
    procesados += tanda.length
    tandaActual += 1
    onProgreso?.(procesados, files.length, tandaActual, totalTandas)
  }

  return { resultados, errores }
}

/** Formato monetario salvadoreño, sin el símbolo (lo pone quien llama). */
export function fmt(n) {
  return Number(n || 0).toLocaleString('es-SV', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

// Colores por método real que resolvió un campo (registro.fuentes[campo] —
// ver backend/extractors/*.py). Compartido entre las tablas "Auditoría
// completa" de Ventas.jsx/Compras.jsx y el detalle expandible de
// ResultadosTabla.jsx.
export const FUENTE_CAMPO_ESTILO = {
  regex:        { label: 'Regex',        clase: 'text-slate-400 bg-slate-700/40' },
  qr:           { label: 'QR',           clase: 'text-violet-400 bg-violet-900/30' },
  hacienda:     { label: 'Hacienda',     clase: 'text-emerald-400 bg-emerald-900/30' },
  vision:       { label: 'Visión',       clase: 'text-sky-400 bg-sky-900/30' },
  ia:           { label: 'IA',           clase: 'text-amber-400 bg-amber-900/30' },
  json_oficial: { label: 'JSON oficial', clase: 'text-emerald-400 bg-emerald-900/30' },
}

/**
 * Resumen compacto de fuentes para una fila de tabla: dedupea los métodos
 * que tocaron algún campo del registro y los muestra como badges chiquitos.
 * "necesito saber con qué método se sacó la información" — antes solo se
 * podía ver expandiendo cada documento uno por uno; esto lo pone a simple
 * vista en la tabla completa.
 */
export function FuenteResumen({ fuentes }) {
  if (!fuentes) return <span className="text-slate-600">—</span>
  const distintas = [...new Set(Object.values(fuentes))]
  if (distintas.length === 0) return <span className="text-slate-600">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {distintas.map(f => {
        const info = FUENTE_CAMPO_ESTILO[f] || { label: f, clase: 'text-slate-400 bg-slate-700/40' }
        return (
          <span key={f} className={`text-[0.65rem] font-semibold px-1.5 py-0.5 rounded whitespace-nowrap ${info.clase}`}>
            {info.label}
          </span>
        )
      })}
    </div>
  )
}

/**
 * Filtra una lista de registros por texto libre sobre un conjunto de campos
 * (nombre/razón social, NIT/NRC, DUI, N° control, código de generación…).
 * Búsqueda simple por substring, sin distinguir mayúsculas/acentos exactos —
 * alcanza para ubicar un documento entre cientos sin scrollear la tabla.
 */
export function filtrarPorTexto(lista, campos, query, accessor = (x) => x) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return lista
  return lista.filter(item => {
    const r = accessor(item)
    return campos.some(c => String(r?.[c] ?? '').toLowerCase().includes(q))
  })
}

/** Barra de búsqueda compartida por los módulos (Ventas/Compras/Retenciones/Sujetos Excluidos). */
export function SearchBar({ value, onChange, placeholder = 'Buscar por nombre, NIT o N° de control…' }) {
  return (
    <div className="relative w-full sm:w-80">
      <IconBuscar className="w-4 h-4 text-fg-4 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="input pl-9 w-full"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-fg-4 hover:text-red-400 transition-colors"
          aria-label="Limpiar búsqueda"
        >
          ×
        </button>
      )}
    </div>
  )
}

export function descargarBlob(blobData, nombre) {
  const url = URL.createObjectURL(new Blob([blobData]))
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Clave que identifica un DTE de forma única.
 *
 * El código de generación (UUID que asigna Hacienda) es único por documento:
 * el mismo DTE subido como PDF y como JSON trae el mismo código. Si falta, se
 * recurre al número de control, que también es irrepetible por emisor.
 */
function claveDocumento(registro) {
  const r = registro || {}
  const gen = String(r.gen || r.gen_sin_guiones || '').replace(/-/g, '').toUpperCase()
  if (gen) return `gen:${gen}`
  const ctrl = String(r.num_control || r.num_control_raw || '').replace(/-/g, '').toUpperCase()
  if (ctrl) return `ctrl:${ctrl}`
  return '' // Sin identificador no se puede afirmar que sea repetido.
}

/**
 * Añade `nuevos` a `previos` descartando los que ya estaban.
 *
 * Es habitual subir el mismo DTE dos veces —el PDF y el JSON del mismo
 * documento, o un lote que se solapa con otro anterior— y cada copia sumaba
 * otra fila: los totales del anexo salían inflados y el crédito fiscal se
 * contaba doble. Un documento sin código de generación ni número de control no
 * se descarta, porque ahí no hay forma de afirmar que sea el mismo.
 *
 * Devuelve `{ lista, agregados, duplicados }`: la lista fusionada, los
 * documentos realmente incorporados —que son los que deben persistirse— y los
 * nombres de archivo omitidos, para avisar en vez de descartar en silencio.
 */
export function fusionarSinDuplicados(previos, nuevos) {
  const vistos = new Set(previos.map(r => claveDocumento(r.registro)).filter(Boolean))
  const agregados = []
  const duplicados = []

  for (const doc of nuevos) {
    const clave = claveDocumento(doc.registro)
    if (clave && vistos.has(clave)) {
      duplicados.push(doc.filename || 'documento sin nombre')
      continue
    }
    if (clave) vistos.add(clave)
    agregados.push(doc)
  }

  return { lista: [...previos, ...agregados], agregados, duplicados }
}

/** Redacta el aviso de documentos repetidos, o null si no hubo ninguno. */
export function avisoDuplicados(duplicados) {
  if (!duplicados.length) return null
  const n = duplicados.length
  if (n === 1) return `«${duplicados[0]}» ya estaba en la lista: es el mismo DTE y no se agregó.`
  // Primera línea = resumen, el resto = un nombre de archivo por línea — así
  // AvisoBox puede mostrar el resumen y colapsar la lista larga en vez de
  // volcar todos los nombres en un solo párrafo (que es lo que hacía ruido
  // en lotes de 20+ duplicados).
  return [`${n} documentos ya estaban en la lista y no se agregaron:`, ...duplicados].join('\n')
}

/**
 * Normaliza el `estado` que devuelve el backend a 'ok' | 'revisar' | 'manual'.
 *
 * Los extractores emiten "OK" / "REVISAR" / "REVISION_MANUAL" según el score
 * de confianza. Antes emitían cadenas con prefijo emoji ("🔴 Revisar"), y la
 * UI seguía detectando solo ese formato: con el vocabulario actual todo caía
 * en el caso por defecto y los documentos por revisar se pintaban como
 * conformes. Se aceptan ambos formatos para no romper registros históricos
 * ya guardados en Supabase.
 */
export function nivelEstado(estado) {
  if (!estado) return null
  const e = String(estado).trim().toUpperCase()

  if (e.startsWith('🔴') || e.includes('REVISION_MANUAL') || e.includes('REVISIÓN MANUAL')) {
    return 'manual'
  }
  if (e.startsWith('🟡') || e.includes('REVISAR')) return 'revisar'
  if (e.startsWith('🟢') || e.includes('OK')) return 'ok'
  return 'revisar' // Desconocido: se muestra como pendiente, nunca como conforme.
}

const ETIQUETA = {
  ok:      'Conforme',
  revisar: 'Revisar',
  manual:  'Revisión manual',
}

/** ¿Este registro necesita atención del usuario? */
export function esAlerta(estado) {
  const nivel = nivelEstado(estado)
  return nivel === 'revisar' || nivel === 'manual'
}

/** Insignia de estado para las tablas de resultados. */
export function EstadoBadge({ estado }) {
  const nivel = nivelEstado(estado)
  if (!nivel) return null

  const clase = nivel === 'ok' ? 'badge-ok' : nivel === 'revisar' ? 'badge-warn' : 'badge-err'
  const Icon = nivel === 'ok' ? IconCheck : IconAlerta

  return (
    <span className={`${clase} text-xs`}>
      <Icon className="w-3 h-3 shrink-0" />
      {ETIQUETA[nivel]}
    </span>
  )
}
