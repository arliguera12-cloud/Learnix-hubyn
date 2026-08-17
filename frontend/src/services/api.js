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

export function exportarExcelCompras(declaranteId, registros, opts = {}) {
  return api.post('/exportar/excel', {
    tipo: 'compras',
    declarante_id: declaranteId,
    registros,
    tipo_op:  opts.tipo_op  ?? '1',
    clasif:   opts.clasif   ?? '2',
    sector:   opts.sector   ?? '4',
    tipo_cg:  opts.tipo_cg  ?? '2',
    periodo_feb2024: opts.periodo_feb2024 ?? true,
    ...(opts.periodo && { periodo: opts.periodo }),
  }, { responseType: 'blob' })
}

export function exportarExcelVentas(declaranteId, registros, opts = {}) {
  return api.post('/exportar/excel', {
    tipo: 'ventas',
    declarante_id: declaranteId,
    registros,
    tipo_op_renta:      opts.tipo_op_renta      ?? '1',
    tipo_ingreso_renta: opts.tipo_ingreso_renta ?? '3',
    periodo_ene2025:    opts.periodo_ene2025    ?? true,
    ...(opts.periodo && { periodo: opts.periodo }),
  }, { responseType: 'blob' })
}

// ─── Declarantes ───────────────────────────────────────────────────────────

export function getDeclarantes() {
  return api.get('/procesar/declarantes')
}

// ─── Centro de importación (Drive / Gmail) ─────────────────────────────────
// Las credenciales solo viajan en el cuerpo del request; el backend no las
// guarda, se usan una vez para hablar con Google y se descartan.

export function importarDriveListar(apiKey, url, opts = {}) {
  return api.post('/importar/drive/listar', {
    api_key: apiKey,
    url,
    recursivo: opts.recursivo ?? true,
    max_archivos: opts.maxArchivos ?? 200,
  })
}

export function importarDriveDescargar(apiKey, archivos) {
  return api.post('/importar/drive/descargar', { api_key: apiKey, archivos })
}

export function importarGmailBuscar(email, appPassword, opts = {}) {
  return api.post('/importar/gmail/buscar', {
    email,
    app_password: appPassword,
    remitente: opts.remitente ?? '',
    texto: opts.texto ?? '',
    dias: opts.dias ?? 30,
    max_correos: opts.maxCorreos ?? 50,
  })
}

export default api
