import axios from 'axios'
import { supabase } from './supabase'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
})

// Adjunta el token de Supabase en cada petición
api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

// ─── Helper ────────────────────────────────────────────────────────────────

function buildForm(file, declaranteId, nombre = '') {
  const form = new FormData()
  form.append('file', file)
  form.append('declarante_id', declaranteId)
  if (nombre) form.append('nombre_declarante', nombre)
  return form
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

function buildLoteForm(files, declaranteId, nombre = '') {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  form.append('declarante_id', declaranteId)
  if (nombre) form.append('nombre_declarante', nombre)
  return form
}

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

// ─── Declarantes ───────────────────────────────────────────────────────────

export function getDeclarantes() {
  return api.get('/procesar/declarantes')
}

// ─── Exportación ───────────────────────────────────────────────────────────

export function exportarExcel(tipo, declaranteId, periodo) {
  const params = { tipo, declarante_id: declaranteId, ...(periodo && { periodo }) }
  return api.get('/exportar/excel', { params, responseType: 'blob' })
}

export default api
