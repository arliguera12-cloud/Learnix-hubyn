import { useState } from 'react'
import PdfUploader from './PdfUploader'
import ResultadosTabla from './ResultadosTabla'
import { exportarExcel, guardarResultados } from '../services/api'
import {
  fmt, descargarBlob, fusionarSinDuplicados, avisoDuplicados,
  usePersistenciaExtractor, useProgresoSimulado, subirLoteEnTandas,
} from '../utils/dte'
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
  const { resultados, setResultados, declaranteId, setDeclaranteId } = usePersistenciaExtractor(tipo)
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState(null)
  const [exportando,   setExportando]   = useState(false)
  const [aviso,        setAviso]        = useState(null)
  const { progress, iniciar: iniciarProgreso, avanzarA, terminar: terminarProgreso, limpiar: limpiarProgreso } = useProgresoSimulado()

  // Cambiar de cliente en el selector vacía la tabla de inmediato — antes
  // quedaba la del cliente anterior en pantalla hasta la próxima extracción,
  // y esa extracción terminaba sumando los documentos de ambos clientes.
  function handleClienteChange(nuevoNit) {
    if (nuevoNit === declaranteId) return
    setResultados([]); setError(null); setAviso(null)
  }

  async function handleUpload(filesOrFile, dId, nombre) {
    setLoading(true)
    setError(null)
    setAviso(null)
    limpiarProgreso()
    setDeclaranteId(dId)

    const isMultiple = Array.isArray(filesOrFile)

    try {
      let nuevos = []

      if (isMultiple && loteApiFn) {
        // Se sube en tandas de a lo sumo TAMANO_TANDA (el backend las procesa
        // en paralelo internamente) — así un lote de cientos de PDFs no choca
        // con el límite por request ni con el timeout del proxy.
        iniciarProgreso(filesOrFile.length)
        const { resultados: res, errores } = await subirLoteEnTandas(
          filesOrFile, loteApiFn, dId, nombre,
          (procesados, total) => avanzarA(Math.round((procesados / total) * 92)),
        )
        nuevos = res
        if (errores.length) {
          setError(errores.map(e => `${e.filename}: ${e.error}`).join('\n'))
        }
        terminarProgreso()
      } else if (isMultiple) {
        // Secuencial como fallback, si el tipo no tiene endpoint de lote
        for (let i = 0; i < filesOrFile.length; i++) {
          iniciarProgreso(filesOrFile.length)
          const { data } = await apiFn(filesOrFile[i], dId, nombre)
          nuevos.push(data)
        }
        terminarProgreso()
      } else {
        const { data } = await apiFn(filesOrFile, dId, nombre)
        nuevos = [data]
      }

      // Descarta lo que ya estaba: subir el mismo DTE dos veces (su PDF y su
      // JSON, o lotes que se solapan) duplicaba la fila y el crédito fiscal.
      // Si el declarante cambió desde la última subida, arranca de cero en
      // vez de mezclar documentos de dos clientes distintos en una tabla.
      const base = dId === declaranteId ? resultados : []
      const { lista, agregados, duplicados } = fusionarSinDuplicados(base, nuevos)
      setResultados(lista)
      setAviso(avisoDuplicados(duplicados))

      // Guardar en Supabase en segundo plano (solo lo realmente agregado)
      guardarResultados(tipo, dId, agregados)

    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail ?? err.message))
      limpiarProgreso()
    } finally {
      setLoading(false)
      setTimeout(limpiarProgreso, 500)
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
    setAviso(null)
    limpiarProgreso()
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
        <p className="text-[0.65rem] uppercase tracking-[0.18em] text-fg-4 font-semibold mb-1">
          Extractor DTE
        </p>
        <h2 className="text-3xl text-fg leading-none flex items-center gap-3">
          {Icon && <Icon className="w-7 h-7 text-accent" />}
          {titulo.replace(/^Extractor DTE — /, '')}
        </h2>
        <p className="text-sm text-fg-4 mt-2">{descripcion}</p>
      </div>

      {/* Uploader */}
      <div className="card">
        <PdfUploader onUpload={handleUpload} onClienteChange={handleClienteChange} loading={loading} multiple={!!loteApiFn} />
      </div>

      {/* Barra de progreso */}
      {progress && (
        <div className="card space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-slate-300">
              Procesando {progress.total} PDF{progress.total !== 1 ? 's' : ''}…
            </span>
            <span className="text-slate-400 font-mono text-xs">
              {Math.round(progress.pct)}%
            </span>
          </div>
          <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 transition-all duration-300 ease-out"
              style={{ width: `${progress.pct}%` }}
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

      {/* Documentos repetidos omitidos */}
      {aviso && (
        <div className="card border-amber-800 bg-amber-900/15">
          <p className="text-amber-400 text-sm flex items-start gap-2">
            <IconAlerta className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{aviso}</span>
          </p>
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
