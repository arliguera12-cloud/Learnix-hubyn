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

// ─── DTEs ──────────────────────────────────────────────────────────────────

export function procesarVentas(file, declaranteId) {
  const form = new FormData()
  form.append('file', file)
  form.append('declarante_id', declaranteId)
  return api.post('/procesar/ventas', form)
}

export function procesarCompras(file, declaranteId) {
  const form = new FormData()
  form.append('file', file)
  form.append('declarante_id', declaranteId)
  return api.post('/procesar/compras', form)
}

export function procesarRetenciones(file, declaranteId) {
  const form = new FormData()
  form.append('file', file)
  form.append('declarante_id', declaranteId)
  return api.post('/procesar/retenciones', form)
}

export function procesarSujetosExcluidos(file, declaranteId) {
  const form = new FormData()
  form.append('file', file)
  form.append('declarante_id', declaranteId)
  return api.post('/procesar/sujetos-excluidos', form)
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
