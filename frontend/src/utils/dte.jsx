/**
 * Utilidades compartidas por las páginas de extractores.
 *
 * Ventas.jsx y Compras.jsx tenían copias idénticas de `fmt`, `descargarBlob`
 * y `estadoBadge`; al vivir por duplicado, la corrección del vocabulario de
 * `estado` habría que hacerla dos veces (y ExtractorPage tenía una tercera
 * copia de `fmt`/`descargarBlob`).
 */
import { useRef, useState } from 'react'
import { IconCheck, IconAlerta } from '../components/Icons'

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
 * subirLoteEnTandas). Cada tanda es un request que termina de una sola vez
 * (el backend la procesa en paralelo y responde al final), así que dentro de
 * una tanda no hay forma de medir avance — pero entre tandas sí: se sabe
 * exactamente cuántos documentos van procesados sobre el total, y con eso
 * alcanza para un porcentaje real y una estimación de tiempo restante
 * (a partir de cuánto tardaron las tandas ya completadas).
 */
export function useProgresoLote() {
  const [progress, setProgress] = useState(null)
  const inicioRef = useRef(0)

  function iniciar(total, totalTandas) {
    inicioRef.current = Date.now()
    setProgress({
      procesados: 0, total, tandaActual: 0, totalTandas,
      pct: 1, etaTexto: null, fase: 'procesando',
    })
  }

  /** Se llama al terminar cada tanda, con el conteo real hasta ese momento. */
  function avanzar(procesados, total, tandaActual, totalTandas) {
    const transcurridoMs = Date.now() - inicioRef.current
    const pct = Math.min(99, Math.round((procesados / total) * 100))

    let etaTexto = null
    if (tandaActual > 0 && tandaActual < totalTandas) {
      const msPorTanda   = transcurridoMs / tandaActual
      const restanteSeg  = Math.round((msPorTanda * (totalTandas - tandaActual)) / 1000)
      etaTexto = restanteSeg < 60
        ? `~${restanteSeg}s restantes`
        : `~${Math.round(restanteSeg / 60)} min restantes`
    }

    setProgress(p => (p ? { ...p, procesados, total, tandaActual, totalTandas, pct, etaTexto } : p))
  }

  function terminar() {
    setProgress(p => (p ? { ...p, pct: 100, etaTexto: null, fase: 'listo' } : p))
  }

  function limpiar() {
    setProgress(null)
  }

  return { progress, iniciar, avanzar, terminar, limpiar }
}

// Mismo tope que el backend (routers/procesamiento.py: _MAX_LOTE_ARCHIVOS) —
// con más archivos por request el proxy corta la conexión antes de terminar.
export const TAMANO_TANDA = 40

/**
 * Sube `files` en tandas de `TAMANO_TANDA`, una tras otra, y junta los
 * resultados y errores de todas. Así el usuario puede soltar 200+ PDF de una
 * sola vez sin toparse con el límite por request — el troceo pasa
 * desapercibido, solo se nota en que la barra de progreso avanza por tandas.
 *
 * `onProgreso(procesados, total, tandaActual, totalTandas)` se llama al
 * terminar cada tanda, con el conteo real hasta ese momento.
 */
export async function subirLoteEnTandas(files, loteApiFn, declaranteId, nombre, onProgreso) {
  const resultados = []
  const errores = []
  let procesados = 0
  let tandaActual = 0
  const totalTandas = Math.ceil(files.length / TAMANO_TANDA)

  for (let i = 0; i < files.length; i += TAMANO_TANDA) {
    const tanda = files.slice(i, i + TAMANO_TANDA)
    const { data } = await loteApiFn(tanda, declaranteId, nombre)
    resultados.push(...(data.resultados ?? []))
    errores.push(...(data.errores ?? []))
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
  return n === 1
    ? `«${duplicados[0]}» ya estaba en la lista: es el mismo DTE y no se agregó.`
    : `${n} documentos ya estaban en la lista y no se agregaron: ${duplicados.join(', ')}`
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
