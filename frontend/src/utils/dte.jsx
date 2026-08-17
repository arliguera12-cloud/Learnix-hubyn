/**
 * Utilidades compartidas por las páginas de extractores.
 *
 * Ventas.jsx y Compras.jsx tenían copias idénticas de `fmt`, `descargarBlob`
 * y `estadoBadge`; al vivir por duplicado, la corrección del vocabulario de
 * `estado` habría que hacerla dos veces (y ExtractorPage tenía una tercera
 * copia de `fmt`/`descargarBlob`).
 */
import { IconCheck, IconAlerta } from '../components/Icons'

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
