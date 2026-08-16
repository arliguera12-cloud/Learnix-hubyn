import { useState } from 'react'
import PdfUploader from './PdfUploader'
import ResultadosTabla from './ResultadosTabla'
import { exportarExcel, guardarResultados } from '../services/api'
import { fmt, descargarBlob } from '../utils/dte'
import { IconExportar, IconAlerta } from './Icons'

// Campos monetarios por tipo para el resumen financiero
const CAMPOS_FINANCIEROS = {
  ventas:            { gravadas: 'gravadas', iva: 'debito',  total: 'total' },
  compras:           { gravadas: 'gra',      iva: 'iva',     total: 'tot'   },
  retenciones:       { gravadas: 'base',     iva: 'ret',     total: 'base'  },
  sujetos_excluidos: { gravadas: 'base',     iva: 'ret',     total: 'base'  },
}

function calcularTotales(tipo, resultados) {
  const campos = CAMPOS_FINANCIEROS[tipo] || {}
  let gravadas = 0, iva = 0, total = 0
  for (const r of resultados) {
    const reg = r.registro || {}
    gravadas += parseFloat(reg[campos.gravadas] || 0)
    iva      += parseFloat(reg[campos.iva]      || 0)
    total    += parseFloat(reg[campos.total]    || 0)
  }
  return { gravadas, iva, total }
}

export default function ExtractorPage({ titulo, Icon, descripcion, tipo, apiFn, loteApiFn }) {
  const [resultados,   setResultados]   = useState([])
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState(null)
  const [progress,     setProgress]     = useState(null) // { done, total }
  const [declaranteId, setDeclaranteId] = useState('')
  const [exportando,   setExportando]   = useState(false)

  async function handleUpload(filesOrFile, dId, nombre) {
    setLoading(true)
    setError(null)
    setProgress(null)
    setDeclaranteId(dId)

    const isMultiple = Array.isArray(filesOrFile)

    try {
      let nuevos = []

      if (isMultiple && loteApiFn) {
        // Un solo request con todos los PDFs
        setProgress({ done: 0, total: filesOrFile.length, fase: 'enviando' })
        const { data } = await loteApiFn(filesOrFile, dId, nombre)
        nuevos = data.resultados ?? []
        if (data.errores?.length) {
          setError(data.errores.map(e => `${e.filename}: ${e.error}`).join('\n'))
        }
        setProgress({ done: filesOrFile.length, total: filesOrFile.length, fase: 'listo' })
      } else if (isMultiple) {
        // Secuencial como fallback
        for (let i = 0; i < filesOrFile.length; i++) {
          setProgress({ done: i, total: filesOrFile.length, fase: 'procesando' })
          const { data } = await apiFn(filesOrFile[i], dId, nombre)
          nuevos.push(data)
        }
        setProgress({ done: filesOrFile.length, total: filesOrFile.length, fase: 'listo' })
      } else {
        const { data } = await apiFn(filesOrFile, dId, nombre)
        nuevos = [data]
      }

      setResultados(prev => [...prev, ...nuevos])

      // Guardar en Supabase en segundo plano
      guardarResultados(tipo, dId, nuevos)

    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail ?? err.message))
    } finally {
      setLoading(false)
      setProgress(null)
    }
  }

  async function handleExportarTodo() {
    if (!resultados.length) return
    setExportando(true)
    try {
      const registros = resultados.map(r => r.registro || {})
      const res = await exportarExcel(tipo, declaranteId, registros)
      descargarBlob(res.data, `F07_${tipo}_${declaranteId}.xlsx`)
    } catch {
      setError('Error al exportar. Intenta de nuevo.')
    } finally {
      setExportando(false)
    }
  }

  function handleLimpiar() {
    setResultados([])
    setError(null)
    setProgress(null)
  }

  const exitosos   = resultados.length
  const totales    = exitosos > 0 ? calcularTotales(tipo, resultados) : null
  const labelIva   = tipo === 'ventas' ? 'Débito Fiscal' : 'IVA / Retención'
  const labelGrav  = tipo === 'ventas' ? 'Ventas Gravadas' : 'Monto Gravado'
  const labelTotal = 'Total'

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Cabecera */}
      <div>
        <h2 className="text-2xl text-fg flex items-center gap-2.5">
          {Icon && <Icon className="w-6 h-6 text-accent" />}
          {titulo}
        </h2>
        <p className="text-sm text-slate-400 mt-1">{descripcion}</p>
      </div>

      {/* Uploader */}
      <div className="card">
        <PdfUploader onUpload={handleUpload} loading={loading} multiple={!!loteApiFn} />
      </div>

      {/* Barra de progreso */}
      {progress && (
        <div className="card space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-slate-300">
              {progress.fase === 'enviando'
                ? `Enviando ${progress.total} PDF${progress.total !== 1 ? 's' : ''}…`
                : `Procesando ${progress.done + 1} de ${progress.total}…`}
            </span>
            <span className="text-slate-400 font-mono text-xs">
              {Math.round(((progress.done) / progress.total) * 100)}%
            </span>
          </div>
          <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 transition-all duration-300"
              style={{ width: `${(progress.done / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card border-red-800 bg-red-900/20">
          <p className="text-red-400 font-semibold text-sm flex items-center gap-1.5">
            <IconAlerta className="w-4 h-4" /> Error
          </p>
          <pre className="text-red-300 text-sm mt-1 whitespace-pre-wrap font-sans">{error}</pre>
        </div>
      )}

      {/* Resumen del lote */}
      {exitosos > 0 && totales && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200">
              Resumen del lote
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={handleExportarTodo}
                disabled={exportando}
                className="btn-primary text-sm px-4 py-1.5 flex items-center gap-2"
              >
                {exportando ? (
                  <>
                    <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                    </svg>
                    Exportando…
                  </>
                ) : (
                  <><IconExportar className="w-4 h-4" /> Exportar todo ({exitosos})</>
                )}
              </button>
              <button
                onClick={handleLimpiar}
                className="btn-ghost text-sm px-3 py-1.5 text-slate-400 hover:text-red-400"
              >
                Limpiar
              </button>
            </div>
          </div>

          {/* Cards de totales */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-surface-700 rounded-xl p-3 text-center">
              <p className="text-2xl font-bold text-blue-400">{exitosos}</p>
              <p className="text-xs text-slate-500 mt-0.5">Documentos</p>
            </div>
            <div className="bg-surface-700 rounded-xl p-3 text-center">
              <p className="text-lg font-bold text-emerald-400 tabular-nums">
                ${fmt(totales.gravadas)}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">{labelGrav}</p>
            </div>
            <div className="bg-surface-700 rounded-xl p-3 text-center">
              <p className="text-lg font-bold text-amber-400 tabular-nums">
                ${fmt(totales.iva)}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">{labelIva}</p>
            </div>
            <div className="bg-surface-700 rounded-xl p-3 text-center">
              <p className="text-lg font-bold text-white tabular-nums">
                ${fmt(totales.total)}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">{labelTotal}</p>
            </div>
          </div>
        </div>
      )}

      {/* Resultados individuales */}
      {resultados.map((r, i) => (
        <ResultadosTabla key={i} data={r} tipo={tipo} declaranteId={declaranteId} index={i + 1} />
      ))}
    </div>
  )
}
