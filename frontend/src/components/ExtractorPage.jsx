import { useMemo, useState } from 'react'
import PdfUploader from './PdfUploader'
import ResultadosTabla from './ResultadosTabla'
import { exportarExcel, guardarResultados } from '../services/api'
import {
  fmt, descargarBlob, fusionarSinDuplicados, avisoDuplicados, nivelEstado,
  usePersistenciaExtractor, useProgresoLote, subirLoteEnTandas, TAMANO_TANDA,
  SearchBar, filtrarPorTexto, ErrorBox, AvisoBox,
} from '../utils/dte'
import { IconExportar } from './Icons'

const FILTROS = [
  ['todos',   'Todos'],
  ['ok',      'Conforme'],
  ['revisar', 'Revisar'],
  ['manual',  'Revisión manual'],
]

// Campos monetarios por tipo para el resumen financiero
const CAMPOS_FINANCIEROS = {
  ventas:            { gravadas: 'gravadas', iva: 'debito',  total: 'total' },
  compras:           { gravadas: 'gra',      iva: 'iva',     total: 'tot'   },
  retenciones:       { gravadas: 'base',     iva: 'ret',     total: 'base'  },
  sujetos_excluidos: { gravadas: 'base',     iva: 'ret',     total: 'base'  },
}

// Campos por los que se puede buscar texto libre, según el tipo de extractor.
const CAMPOS_BUSQUEDA = {
  ventas:            ['nom_cli',    'nit_cli',  'dui_cli',    'num_control', 'gen', 'sello'],
  compras:           ['nom_prov',   'nit_prov', 'dui_prov',   'num_control', 'gen', 'sello'],
  retenciones:       ['nit_prov',   'dui_agente', 'gen',      'sello'],
  sujetos_excluidos: ['nom_sujeto', 'id_sujeto', 'gen',       'sello'],
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
  const [filtro,       setFiltro]       = useState('todos')
  const [busqueda,     setBusqueda]     = useState('')
  const { progress, iniciar: iniciarProgreso, avanzar: avanzarProgreso, terminar: terminarProgreso, limpiar: limpiarProgreso } = useProgresoLote()

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
        iniciarProgreso(filesOrFile.length, Math.ceil(filesOrFile.length / TAMANO_TANDA))
        const { resultados: res, errores } = await subirLoteEnTandas(
          filesOrFile, loteApiFn, dId, nombre, avanzarProgreso,
        )
        nuevos = res
        if (errores.length) {
          setError(errores.map(e => `${e.filename}: ${e.error}`).join('\n'))
        }
        terminarProgreso()
      } else if (isMultiple) {
        // Secuencial como fallback, si el tipo no tiene endpoint de lote
        iniciarProgreso(filesOrFile.length, filesOrFile.length)
        for (let i = 0; i < filesOrFile.length; i++) {
          const { data } = await apiFn(filesOrFile[i], dId, nombre)
          nuevos.push(data)
          avanzarProgreso(i + 1, filesOrFile.length, i + 1, filesOrFile.length)
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

  // Con lotes grandes, encontrar a mano los documentos con alerta entre
  // cientos de tarjetas es tedioso — estos filtros dejan saltar directo a
  // los que necesitan revisión en vez de scrollear todo.
  const conteos = useMemo(() => {
    const c = { todos: resultados.length, ok: 0, revisar: 0, manual: 0 }
    for (const r of resultados) {
      const n = nivelEstado(r.registro?.estado)
      if (n === 'ok') c.ok++
      else if (n === 'revisar') c.revisar++
      else if (n === 'manual') c.manual++
    }
    return c
  }, [resultados])

  const resultadosBuscados = useMemo(
    () => filtrarPorTexto(resultados, CAMPOS_BUSQUEDA[tipo] || [], busqueda, r => r.registro || {}),
    [resultados, tipo, busqueda],
  )

  const resultadosFiltrados = useMemo(() => {
    const conIndice = resultadosBuscados.map(r => [r, resultados.indexOf(r)])
    if (filtro === 'todos') return conIndice
    return conIndice.filter(([r]) => nivelEstado(r.registro?.estado) === filtro)
  }, [resultadosBuscados, resultados, filtro])

  return (
    <div className="max-w-[90rem] mx-auto space-y-6">
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
              Procesando {progress.procesados} de {progress.total} documento{progress.total !== 1 ? 's' : ''}
              {progress.totalTandas > 1 && ` (tanda ${progress.tandaActual || 1} de ${progress.totalTandas})`}…
            </span>
            <span className="text-slate-400 font-mono text-xs">
              {Math.round(progress.pct)}%{progress.etaTexto && ` · ${progress.etaTexto}`}
            </span>
          </div>
          <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 transition-all duration-500 ease-out"
              style={{ width: `${progress.pct}%` }}
            />
          </div>
        </div>
      )}

      {/* Error */}
      <ErrorBox mensaje={error} />

      {/* Documentos repetidos omitidos */}
      <AvisoBox mensaje={aviso} />

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

      {/* Búsqueda + filtros por estado — clave para ubicar documentos en un lote grande */}
      {exitosos > 1 && (
        <div className="flex flex-wrap items-center gap-3">
          <SearchBar value={busqueda} onChange={setBusqueda} />
          {FILTROS.map(([valor, label]) => {
            const n = conteos[valor]
            if (valor !== 'todos' && n === 0) return null
            return (
              <button
                key={valor}
                onClick={() => setFiltro(valor)}
                className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                  filtro === valor
                    ? 'bg-brand-500/20 border-brand-500 text-brand-400'
                    : 'border-surface-600 text-slate-400 hover:border-slate-500 hover:text-slate-200'
                }`}
              >
                {label} ({n})
              </button>
            )
          })}
        </div>
      )}

      {/* Resultados individuales */}
      {resultadosFiltrados.length === 0 && filtro !== 'todos' ? (
        <p className="text-center text-slate-500 py-8 text-sm">
          Ningún documento en «{FILTROS.find(([v]) => v === filtro)?.[1]}».
        </p>
      ) : (
        resultadosFiltrados.map(([r, i]) => (
          <ResultadosTabla key={i} data={r} tipo={tipo} declaranteId={declaranteId} index={i + 1} />
        ))
      )}
    </div>
  )
}
