import { useState, useMemo } from 'react'
import PdfUploader from '../components/PdfUploader'
import { procesarVentas, procesarVentasLote, exportarExcelVentas, guardarResultados } from '../services/api'
import { fmt, descargarBlob, EstadoBadge, esAlerta, nivelEstado, fusionarSinDuplicados, avisoDuplicados } from '../utils/dte'
import { IconVentas, IconExportar, IconCheck, IconAlerta } from '../components/Icons'

// Tipos que van al Anexo 1 (Contribuyentes): CCF, NC, ND
const TIPOS_CONTRIB = new Set(['03', '05', '06'])

// Descripción por tipo DTE
const DESC_TIPO = {
  '01': 'Factura (CF)',
  '02': 'Recibo',
  '03': 'CCF',
  '05': 'Nota de Crédito',
  '06': 'Nota de Débito',
  '11': 'Fact. Exportación',
}

// ── componente principal ───────────────────────────────────────────────────

export default function Ventas() {
  const [resultados,   setResultados]   = useState([])
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState(null)
  const [progress,     setProgress]     = useState(null)
  const [declaranteId, setDeclaranteId] = useState('')
  const [exportando,   setExportando]   = useState(false)
  const [tab,          setTab]          = useState(0)
  const [aviso,        setAviso]        = useState(null)

  // ── upload ───────────────────────────────────────────────────────────────

  async function handleUpload(filesOrFile, dId) {
    setLoading(true); setError(null); setAviso(null); setProgress(null); setDeclaranteId(dId)
    const isMultiple = Array.isArray(filesOrFile)
    try {
      let nuevos = []
      if (isMultiple) {
        setProgress({ done: 0, total: filesOrFile.length, fase: 'enviando' })
        const { data } = await procesarVentasLote(filesOrFile, dId)
        nuevos = data.resultados ?? []
        if (data.errores?.length) setError(data.errores.map(e => `${e.filename}: ${e.error}`).join('\n'))
        setProgress({ done: filesOrFile.length, total: filesOrFile.length, fase: 'listo' })
      } else {
        const { data } = await procesarVentas(filesOrFile, dId)
        nuevos = [data]
      }
      // Descarta lo que ya estaba: subir el mismo DTE dos veces (su PDF y su
      // JSON, o lotes que se solapan) duplicaba la fila y el crédito fiscal.
      const { lista, agregados, duplicados } = fusionarSinDuplicados(resultados, nuevos)
      setResultados(lista)
      setAviso(avisoDuplicados(duplicados))
      guardarResultados('ventas', dId, agregados)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail ?? err.message))
    } finally {
      setLoading(false); setProgress(null)
    }
  }

  // ── datos derivados ───────────────────────────────────────────────────────

  const registros = useMemo(() => resultados.map(r => r.registro || {}), [resultados])

  const contrib = useMemo(() => registros.filter(r => TIPOS_CONTRIB.has(String(r.tipo))), [registros])
  const consumidor = useMemo(() => registros.filter(r => !TIPOS_CONTRIB.has(String(r.tipo))), [registros])

  const totalesContrib = useMemo(() => {
    let exentas = 0, no_sujetas = 0, gravadas = 0, debito = 0, total = 0
    for (const r of contrib) {
      exentas     += parseFloat(r.exentas     || 0)
      no_sujetas  += parseFloat(r.no_sujetas  || 0)
      gravadas    += parseFloat(r.gravadas    || 0)
      debito      += parseFloat(r.debito      || 0)
      total       += parseFloat(r.total       || 0)
    }
    return { exentas, no_sujetas, gravadas, debito, total }
  }, [contrib])

  const totalesConsumidor = useMemo(() => {
    let exentas = 0, gravadas = 0, total = 0
    for (const r of consumidor) {
      exentas  += parseFloat(r.exentas  || 0)
      gravadas += parseFloat(r.gravadas || 0)
      total    += parseFloat(r.total    || 0)
    }
    return { exentas, gravadas, total }
  }, [consumidor])

  // Agrupación diaria de consumidor
  const gruposDiarios = useMemo(() => {
    const map = {}
    for (const r of consumidor) {
      const fecha = r.fecha || 'Sin fecha'
      if (!map[fecha]) map[fecha] = { fecha, docs: 0, gravadas: 0, total: 0 }
      map[fecha].docs++
      map[fecha].gravadas += parseFloat(r.gravadas || 0)
      map[fecha].total    += parseFloat(r.total    || 0)
    }
    return Object.values(map).sort((a, b) => a.fecha.localeCompare(b.fecha))
  }, [consumidor])

  const alertas = useMemo(
    () => resultados.filter(r => esAlerta(r.registro?.estado)),
    [resultados]
  )

  const resumenTipo = useMemo(() => {
    const map = {}
    for (const r of registros) {
      const tipo = String(r.tipo || '?')
      if (!map[tipo]) map[tipo] = { tipo, desc: DESC_TIPO[tipo] || tipo, anexo: TIPOS_CONTRIB.has(tipo) ? 'Anexo 1' : 'Anexo 2', docs: 0, exentas: 0, gravadas: 0, debito: 0, total: 0 }
      map[tipo].docs++
      map[tipo].exentas  += parseFloat(r.exentas  || 0)
      map[tipo].gravadas += parseFloat(r.gravadas || 0)
      map[tipo].debito   += parseFloat(r.debito   || 0)
      map[tipo].total    += parseFloat(r.total    || 0)
    }
    return Object.values(map).sort((a, b) => a.tipo.localeCompare(b.tipo))
  }, [registros])

  // ── exportar ─────────────────────────────────────────────────────────────

  async function handleExportar() {
    if (!registros.length) return
    setExportando(true)
    try {
      const res = await exportarExcelVentas(declaranteId, registros)
      descargarBlob(res.data, `F07_Ventas_${declaranteId}.xlsx`)
    } catch {
      setError('Error al exportar. Intenta de nuevo.')
    } finally {
      setExportando(false)
    }
  }

  // ── tabs ──────────────────────────────────────────────────────────────────

  const TABS = [
    `Anexo 1 — Contribuyentes (${contrib.length})`,
    `Anexo 2 — Consumidor Final (${consumidor.length})`,
    'Auditoría completa',
    'Resumen por tipo',
    alertas.length ? `Alertas (${alertas.length})` : 'Alertas',
  ]

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Cabecera */}
      <div>
        <h2 className="text-2xl text-fg flex items-center gap-2.5">
          <IconVentas className="w-6 h-6 text-accent" />
          Extractor DTE — Ventas
        </h2>
        <p className="text-sm text-slate-400 mt-0.5">
          Extrae CCF, NC/ND y Facturas CF (DTE-01, 03, 05, 06). Genera Anexos 1 y 2 para F-07.
        </p>
      </div>

      {/* Uploader */}
      <div className="card">
        <PdfUploader onUpload={handleUpload} loading={loading} multiple />
      </div>

      {/* Progreso */}
      {progress && (
        <div className="card space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-slate-300">
              {progress.fase === 'enviando'
                ? `Enviando ${progress.total} PDF${progress.total !== 1 ? 's' : ''}…`
                : `Procesando ${progress.done + 1} de ${progress.total}…`}
            </span>
            <span className="text-slate-400 font-mono text-xs">
              {Math.round((progress.done / progress.total) * 100)}%
            </span>
          </div>
          <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
            <div className="h-full bg-brand-500 transition-all duration-300"
              style={{ width: `${(progress.done / progress.total) * 100}%` }} />
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

      {/* Tabs */}
      {registros.length > 0 && (
        <div className="card p-0 overflow-hidden">
          {/* Tab bar */}
          <div className="flex overflow-x-auto border-b border-surface-600 bg-surface-800">
            {TABS.map((label, i) => (
              <button
                key={i}
                onClick={() => setTab(i)}
                className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
                  tab === i
                    ? 'text-brand-400 border-b-2 border-brand-500 bg-surface-700'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-700/50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="p-4">
            {/* Tab 0 — Anexo 1 Contribuyentes */}
            {tab === 0 && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-slate-300 tabular-nums">${fmt(totalesContrib.exentas)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Exentas</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-slate-300 tabular-nums">${fmt(totalesContrib.no_sujetas)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">No Sujetas</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-emerald-400 tabular-nums">${fmt(totalesContrib.gravadas)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Gravadas</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-amber-400 tabular-nums">${fmt(totalesContrib.debito)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Débito Fiscal</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-white tabular-nums">${fmt(totalesContrib.total)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Total</p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr>
                        {['Fecha','Tipo','N° Control','Cliente','NIT/NRC','Exentas','No Suj.','Gravadas','Débito','Total','Estatus'].map(h => (
                          <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {contrib.map((r, i) => (
                        <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                          <td className="table-cell">{r.fecha || '—'}</td>
                          <td className="table-cell font-mono">{r.tipo || '—'}</td>
                          <td className="table-cell font-mono text-slate-400">{r.num_control || '—'}</td>
                          <td className="table-cell max-w-[140px] truncate" title={r.nom_cli}>{r.nom_cli || '—'}</td>
                          <td className="table-cell font-mono">{r.nit_cli || '—'}</td>
                          <td className="table-cell text-right font-mono">{r.exentas != null ? `$${fmt(r.exentas)}` : '—'}</td>
                          <td className="table-cell text-right font-mono">{r.no_sujetas != null ? `$${fmt(r.no_sujetas)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-emerald-400">{r.gravadas != null ? `$${fmt(r.gravadas)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-amber-400">{r.debito != null ? `$${fmt(r.debito)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-white">{r.total != null ? `$${fmt(r.total)}` : '—'}</td>
                          <td className="table-cell"><EstadoBadge estado={r.estado} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {contrib.length === 0 && (
                    <p className="text-center text-slate-500 py-8 text-sm">No hay documentos tipo CCF/NC/ND.</p>
                  )}
                </div>

                <div className="flex justify-end">
                  <button onClick={handleExportar} disabled={exportando} className="btn-primary flex items-center gap-2 px-5 py-2">
                    {exportando ? (
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                      </svg>
                    ) : <IconExportar className="w-4 h-4" />}
                    Generar / Descargar Ventas
                  </button>
                </div>
              </div>
            )}

            {/* Tab 1 — Anexo 2 Consumidor Final */}
            {tab === 1 && (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-slate-300 tabular-nums">${fmt(totalesConsumidor.exentas)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Exentas</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-emerald-400 tabular-nums">${fmt(totalesConsumidor.gravadas)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Gravadas (c/IVA)</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-white tabular-nums">${fmt(totalesConsumidor.total)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Total</p>
                  </div>
                </div>

                {/* Vista previa agrupación diaria */}
                {gruposDiarios.length > 0 && (
                  <div>
                    <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider mb-2">
                      Vista previa — Agrupación diaria para F-07
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr>
                            {['Fecha','N° Docs','Ventas Gravadas','Total'].map(h => (
                              <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {gruposDiarios.map((g, i) => (
                            <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                              <td className="table-cell font-medium">{g.fecha}</td>
                              <td className="table-cell text-center text-blue-400">{g.docs}</td>
                              <td className="table-cell text-right font-mono text-emerald-400">${fmt(g.gravadas)}</td>
                              <td className="table-cell text-right font-mono text-white">${fmt(g.total)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Detalle individual */}
                <div>
                  <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider mb-2">Detalle</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr>
                          {['Fecha','Tipo','N° Control','Sello','UUID','Exentas','Gravadas','Total','Estatus'].map(h => (
                            <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {consumidor.map((r, i) => (
                          <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                            <td className="table-cell">{r.fecha || '—'}</td>
                            <td className="table-cell font-mono">{r.tipo || '—'}</td>
                            <td className="table-cell font-mono text-slate-400">{r.num_control || '—'}</td>
                            <td className="table-cell font-mono text-slate-500 max-w-[60px] truncate" title={r.sello}>{r.sello || '—'}</td>
                            <td className="table-cell font-mono text-slate-500 max-w-[60px] truncate" title={r.gen}>{r.gen || '—'}</td>
                            <td className="table-cell text-right font-mono">{r.exentas != null ? `$${fmt(r.exentas)}` : '—'}</td>
                            <td className="table-cell text-right font-mono text-emerald-400">{r.gravadas != null ? `$${fmt(r.gravadas)}` : '—'}</td>
                            <td className="table-cell text-right font-mono text-white">{r.total != null ? `$${fmt(r.total)}` : '—'}</td>
                            <td className="table-cell"><EstadoBadge estado={r.estado} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {consumidor.length === 0 && (
                      <p className="text-center text-slate-500 py-8 text-sm">No hay Facturas de Consumidor Final.</p>
                    )}
                  </div>
                </div>

                <div className="flex justify-end">
                  <button onClick={handleExportar} disabled={exportando} className="btn-primary flex items-center gap-2 px-5 py-2">
                    {exportando ? (
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                      </svg>
                    ) : <IconExportar className="w-4 h-4" />}
                    Generar / Descargar Ventas
                  </button>
                </div>
              </div>
            )}

            {/* Tab 2 — Auditoría Completa */}
            {tab === 2 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      {['Fecha','Tipo','Anexo','Cliente/Nombre','NIT/NRC','DUI','N° Control','Exentas','No Suj.','Gravadas','Débito','Total','Estatus','Archivo'].map(h => (
                        <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resultados.map((r, i) => {
                      const d = r.registro || {}
                      const esContrib = TIPOS_CONTRIB.has(String(d.tipo))
                      return (
                        <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                          <td className="table-cell">{d.fecha || '—'}</td>
                          <td className="table-cell font-mono">{d.tipo || '—'}</td>
                          <td className="table-cell">
                            <span className={`text-xs font-semibold ${esContrib ? 'text-green-400' : 'text-blue-400'}`}>
                              {esContrib ? 'Anexo 1' : 'Anexo 2'}
                            </span>
                          </td>
                          <td className="table-cell max-w-[140px] truncate" title={d.nom_cli}>{d.nom_cli || '—'}</td>
                          <td className="table-cell font-mono">{d.nit_cli || '—'}</td>
                          <td className="table-cell font-mono">{d.dui_cli || '—'}</td>
                          <td className="table-cell font-mono text-slate-400">{d.num_control || '—'}</td>
                          <td className="table-cell text-right font-mono">{d.exentas != null ? `$${fmt(d.exentas)}` : '—'}</td>
                          <td className="table-cell text-right font-mono">{d.no_sujetas != null ? `$${fmt(d.no_sujetas)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-emerald-400">{d.gravadas != null ? `$${fmt(d.gravadas)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-amber-400">{d.debito != null ? `$${fmt(d.debito)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-white">{d.total != null ? `$${fmt(d.total)}` : '—'}</td>
                          <td className="table-cell"><EstadoBadge estado={d.estado} /></td>
                          <td className="table-cell text-slate-500">{r.filename || '—'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab 3 — Resumen por Tipo */}
            {tab === 3 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      {['Tipo','Descripción','Anexo','Docs','Exentas','Gravadas','Débito','Total'].map(h => (
                        <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resumenTipo.map((t, i) => (
                      <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                        <td className="table-cell font-mono font-bold">{t.tipo}</td>
                        <td className="table-cell text-slate-200">{t.desc}</td>
                        <td className="table-cell">
                          <span className={`text-xs font-semibold ${t.anexo === 'Anexo 1' ? 'text-green-400' : 'text-blue-400'}`}>
                            {t.anexo}
                          </span>
                        </td>
                        <td className="table-cell text-center text-blue-400 font-bold">{t.docs}</td>
                        <td className="table-cell text-right font-mono">${fmt(t.exentas)}</td>
                        <td className="table-cell text-right font-mono text-emerald-400">${fmt(t.gravadas)}</td>
                        <td className="table-cell text-right font-mono text-amber-400">${fmt(t.debito)}</td>
                        <td className="table-cell text-right font-mono text-white">${fmt(t.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {resumenTipo.length === 0 && (
                  <p className="text-center text-slate-500 py-8 text-sm">Sin datos</p>
                )}
              </div>
            )}

            {/* Tab 4 — Alertas */}
            {tab === 4 && (
              <div className="space-y-2">
                {alertas.length === 0 ? (
                  <p className="text-center text-emerald-400 py-8 text-sm flex items-center justify-center gap-2">
                    <IconCheck className="w-4 h-4" /> Sin alertas — todos los documentos están conformes.
                  </p>
                ) : (
                  alertas.map((r, i) => {
                    const d = r.registro || {}
                    return (
                      <div key={i} className="bg-surface-700 rounded-lg px-4 py-3 flex items-start gap-3">
                        <IconAlerta
                          className={`w-4 h-4 mt-0.5 shrink-0 ${
                            nivelEstado(d.estado) === 'manual' ? 'text-red-400' : 'text-amber-400'
                          }`}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-white truncate">
                            {d.nom_cli || d.nit_cli || r.filename || `Doc #${i + 1}`}
                          </p>
                          <p className="text-xs text-slate-400 mt-0.5">{d.estado}</p>
                          {d.motivos && (
                            <p className="text-xs text-slate-500 mt-1">{
                              Array.isArray(d.motivos) ? d.motivos.join(' · ') : d.motivos
                            }</p>
                          )}
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-xs text-slate-400">{d.fecha}</p>
                          <p className="text-xs font-mono text-amber-400">${fmt(d.total)}</p>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
