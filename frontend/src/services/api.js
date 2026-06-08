import axios from 'axios'
import { supabase } from './supabase'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
})

api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

// ─── Helpers ───────────────────────────────────────────────────────────────

function buildForm(file, declaranteId, nombre = '') {
  const form = new FormData()
  form.append('file', file)
  form.append('declarante_id', declaranteId)
  if (nombre) form.append('nombre_declarante', nombre)
  return form
}

function buildLoteForm(files, declaranteId, nombre = '') {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  form.append('declarante_id', declaranteId)
  if (nombre) form.append('nombre_declarante', nombre)
  return form
}

/** Deriva YYYY-MM del string de fecha DD/MM/YYYY o similar */
function _periodoDesde(fecha) {
  if (!fecha) return null
  const m = String(fecha).match(/(\d{2})\/(\d{2})\/(\d{4})/)
  if (m) return `${m[3]}-${m[2]}`
  const m2 = String(fecha).match(/(\d{4})-(\d{2})/)
  if (m2) return `${m2[1]}-${m2[2]}`
  return null
}

// ─── DTEs (single) ─────────────────────────────────────────────────────────

export function procesarVentas(file, declaranteId, nombre) {
  return api.post('/procesar/ventas', buildForm(file, declaranteId, nombre))
}
export function procesarCompras(file, declaranteId, nombre) {
  return api.post('/procesar/compras', buildForm(file, declaranteId, nombre))
}
export function procesarRetenciones(file, declaranteId, nombre) {
  return api.post('/procesar/retenciones', buildForm(file, declaranteId, nombre))
}
export function procesarSujetosExcluidos(file, declaranteId, nombre) {
  return api.post('/procesar/sujetos-excluidos', buildForm(file, declaranteId, nombre))
}

// ─── DTEs (lote / multi-PDF) ───────────────────────────────────────────────

export function procesarVentasLote(files, declaranteId, nombre) {
  return api.post('/procesar/ventas/lote', buildLoteForm(files, declaranteId, nombre))
}
export function procesarComprasLote(files, declaranteId, nombre) {
  return api.post('/procesar/compras/lote', buildLoteForm(files, declaranteId, nombre))
}
export function procesarRetencionesLote(files, declaranteId, nombre) {
  return api.post('/procesar/retenciones/lote', buildLoteForm(files, declaranteId, nombre))
}
export function procesarSujetosExcluidosLote(files, declaranteId, nombre) {
  return api.post('/procesar/sujetos-excluidos/lote', buildLoteForm(files, declaranteId, nombre))
}

// ─── Guardar en Supabase ───────────────────────────────────────────────────

const _TABLA = {
  ventas:           'db_ventas',
  compras:          'db_compras',
  retenciones:      'db_retenciones',
  sujetos_excluidos:'db_sujetos',
}

/**
 * Guarda un array de resultados en la tabla Supabase correspondiente.
 * Silencia errores (tablas pueden no existir aún en entornos de desarrollo).
 */
export async function guardarResultados(tipo, declaranteId, resultados) {
  const tabla = _TABLA[tipo]
  if (!tabla || !resultados?.length) return

  try {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return

    const rows = resultados.map(({ registro = {}, filename }) => ({
      user_id:       user.id,
      declarante_id: declaranteId,
      filename:      filename || null,
      periodo:       _periodoDesde(registro.fecha),
      fecha:         registro.fecha || null,
      tipo_dte:      registro.tipo || null,
      registro,
    }))

    await supabase.from(tabla).insert(rows)
  } catch {
    // Ignorar — tablas pueden no existir aún
  }
}

// ─── Exportar Excel (formato F-07 Hacienda) ────────────────────────────────

export function exportarExcel(tipo, declaranteId, registros, periodo) {
  return api.post('/exportar/excel', {
    tipo,
    declarante_id: declaranteId,
    registros,
    ...(periodo && { periodo }),
  }, { responseType: 'blob' })
}

// ─── Declarantes ───────────────────────────────────────────────────────────

export function getDeclarantes() {
  return api.get('/procesar/declarantes')
}

export default api
