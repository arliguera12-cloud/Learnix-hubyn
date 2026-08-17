import { useState, useMemo } from 'react'
import PdfUploader from '../components/PdfUploader'
import { procesarCompras, procesarComprasLote, exportarExcelCompras, guardarResultados } from '../services/api'
import { fmt, descargarBlob, EstadoBadge, esAlerta, nivelEstado, fusionarSinDuplicados, avisoDuplicados } from '../utils/dte'
import { IconCompras, IconExportar, IconCheck, IconAlerta } from '../components/Icons'

const TIPOS_PERCEPCION = new Set(['03', '05', '06', '12'])

// ── componente principal ───────────────────────────────────────────────────

export default function Compras() {
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
        const { data } = await procesarComprasLote(filesOrFile, dId)
        nuevos = data.resultados ?? []
        if (data.errores?.length) setError(data.errores.map(e => `${e.filename}: ${e.error}`).join('\n'))
        setProgress({ done: filesOrFile.length, total: filesOrFile.length, fase: 'listo' })
      } else {
        const { data } = await procesarCompras(filesOrFile, dId)
        nuevos = [data]
      }
      // Descarta lo que ya estaba: subir el mismo DTE dos veces (su PDF y su
      // JSON, o lotes que se solapan) duplicaba la fila y el crédito fiscal.
      const { lista, agregados, duplicados } = fusionarSinDuplicados(resultados, nuevos)
      setResultados(lista)
      setAviso(avisoDuplicados(duplicados))
      guardarResultados('compras', dId, agregados)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail ?? err.message))
    } finally {
      setLoading(false); setProgress(null)
    }
  }

  // ── datos derivados ───────────────────────────────────────────────────────

  const registros = useMemo(() => resultados.map(r => r.registro || {}), [resultados])

  const totales = useMemo(() => {
    let exe = 0, gra = 0, iva = 0, tot = 0
    for (const r of registros) {
      exe += parseFloat(r.exe || 0); gra += parseFloat(r.gra || 0)
      iva += parseFloat(r.iva || 0); tot += parseFloat(r.tot || 0)
    }
    return { exe, gra, iva, tot }
  }, [registros])

  const alertas = useMemo(
    () => resultados.filter(r => esAlerta(r.registro?.estado)),
    [resultados]
  )

  const percepciones = useMemo(() =>
    registros.filter(r => parseFloat(r.perc || 0) > 0 && TIPOS_PERCEPCION.has(String(r.tipo))),
    [registros])

  // Se agrupa por identificador fiscal, no por nombre: un mismo proveedor
  // aparece escrito de varias formas entre documentos ("GRUPO NSV, LTDA" y
  // "GRUPO NSV, LTDA DE C.V." comparten NIT) y agrupando por texto salía
  // repetido, repartiendo sus totales en varias filas.
  const resumenProv = useMemo(() => {
    const map = {}
    for (const r of registros) {
      const k = r.nit_prov || r.dui_prov || r.nom_prov || '(sin identificar)'
      if (!map[k]) {
        map[k] = {
          nom: r.nom_prov || '(sin nombre)',
          nit: r.nit_prov || '', dui: r.dui_prov || '',
          docs: 0, exe: 0, gra: 0, iva: 0, tot: 0,
        }
      }
      // Entre las variantes del nombre se conserva la más larga, que suele ser
      // la razón social completa en vez de la abreviada.
      if ((r.nom_prov || '').length > map[k].nom.length) map[k].nom = r.nom_prov
      map[k].docs += 1
      map[k].exe += parseFloat(r.exe || 0); map[k].gra += parseFloat(r.gra || 0)
      map[k].iva += parseFloat(r.iva || 0); map[k].tot += parseFloat(r.tot || 0)
    }
    return Object.values(map).sort((a, b) => b.tot - a.tot)
  }, [registros])

  // ── exportar ─────────────────────────────────────────────────────────────

  async function handleExportar() {
    if (!registros.length) return
    setExportando(true)
    try {
      const res = await exportarExcelCompras(declaranteId, registros)
      descargarBlob(res.data, `F07_Compras_${declaranteId}.xlsx`)
    } catch {
      setError('Error al exportar. Intenta de nuevo.')
    } finally {
      setExportando(false)
    }
  }

  // ── tabs ──────────────────────────────────────────────────────────────────

  const TABS = [
    `F-07 Compras (${registros.length})`,
    'Auditoría completa',
    'Resumen por proveedor',
    'Anexo 8 — Percepciones',
    alertas.length ? `Alertas (${alertas.length})` : 'Alertas',
  ]

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Cabecera */}
      <div>
        <h2 className="text-2xl text-fg flex items-center gap-2.5">
          <IconCompras className="w-6 h-6 text-accent" />
          Extractor DTE — Compras
        </h2>
        <p className="text-sm text-slate-400 mt-0.5">
          Extrae CCF recibidos de proveedores (DTE-03, 05, 06, 11). Genera Anexo 3 para F-07.
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

      {/* Tabs (solo si hay resultados) */}
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
            {/* Tab 0 — F-07 Compras */}
            {tab === 0 && (
              <div className="space-y-4">
                {/* Totales */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-slate-300 tabular-nums">${fmt(totales.exe)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Exentas / NS</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-emerald-400 tabular-nums">${fmt(totales.gra)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Gravadas</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-amber-400 tabular-nums">${fmt(totales.iva)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">IVA (Crédito)</p>
                  </div>
                  <div className="bg-surface-700 rounded-xl p-3 text-center">
                    <p className="text-sm font-bold text-white tabular-nums">${fmt(totales.tot)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Total General</p>
                  </div>
                </div>

                {/* Nota Q-T */}
                <div className="bg-amber-900/20 border border-amber-800/50 rounded-lg px-4 py-2.5 text-xs text-amber-300">
                  ℹ️ Columnas Q–T tienen valores por defecto (Tipo Op=1, Clasif=2, Sector=4, Tipo C/G=2).
                  Ajústalos según la naturaleza del gasto antes de subir a Hacienda.
                </div>

                {/* Tabla */}
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr>
                        {['Fecha','Tipo','Proveedor','NIT/NRC','Exentas','Gravadas','IVA','Total','Estatus'].map(h => (
                          <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {registros.map((r, i) => (
                        <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                          <td className="table-cell">{r.fecha || '—'}</td>
                          <td className="table-cell font-mono">{r.tipo || '—'}</td>
                          <td className="table-cell max-w-[160px] truncate" title={r.nom_prov}>{r.nom_prov || '—'}</td>
                          <td className="table-cell font-mono">{r.nit_prov || '—'}</td>
                          <td className="table-cell text-right font-mono text-slate-300">{r.exe != null ? `$${fmt(r.exe)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-emerald-400">{r.gra != null ? `$${fmt(r.gra)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-amber-400">{r.iva != null ? `$${fmt(r.iva)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-white">{r.tot != null ? `$${fmt(r.tot)}` : '—'}</td>
                          <td className="table-cell"><EstadoBadge estado={r.estado} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Botón exportar */}
                <div className="flex justify-end pt-1">
                  <button
                    onClick={handleExportar}
                    disabled={exportando}
                    className="btn-primary flex items-center gap-2 px-5 py-2"
                  >
                    {exportando ? (
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                      </svg>
                    ) : <IconExportar className="w-4 h-4" />}
                    Generar / Descargar Compras
                  </button>
                </div>
              </div>
            )}

            {/* Tab 1 — Auditoría Completa */}
            {tab === 1 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      {['Fecha','Tipo','Nombre Proveedor','NIT/NRC','DUI','Exentas','Gravadas','IVA','Ret.','Perc.','Total','FOVIAL','COTRANS','Sello','UUID','N° Control','Archivo'].map(h => (
                        <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resultados.map((r, i) => {
                      const d = r.registro || {}
                      return (
                        <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                          <td className="table-cell">{d.fecha || '—'}</td>
                          <td className="table-cell font-mono">{d.tipo || '—'}</td>
                          <td className="table-cell max-w-[140px] truncate" title={d.nom_prov}>{d.nom_prov || '—'}</td>
                          <td className="table-cell font-mono">{d.nit_prov || '—'}</td>
                          <td className="table-cell font-mono">{d.dui_prov || '—'}</td>
                          <td className="table-cell text-right font-mono">{d.exe != null ? `$${fmt(d.exe)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-emerald-400">{d.gra != null ? `$${fmt(d.gra)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-amber-400">{d.iva != null ? `$${fmt(d.iva)}` : '—'}</td>
                          <td className="table-cell text-right font-mono">{d.ret != null ? `$${fmt(d.ret)}` : '—'}</td>
                          <td className="table-cell text-right font-mono">{d.perc != null ? `$${fmt(d.perc)}` : '—'}</td>
                          <td className="table-cell text-right font-mono text-white">{d.tot != null ? `$${fmt(d.tot)}` : '—'}</td>
                          <td className="table-cell text-right font-mono">{d.fovial != null ? `$${fmt(d.fovial)}` : '—'}</td>
                          <td className="table-cell text-right font-mono">{d.cotrans != null ? `$${fmt(d.cotrans)}` : '—'}</td>
                          <td className="table-cell font-mono text-slate-500 max-w-[80px] truncate" title={d.sello}>{d.sello || '—'}</td>
                          <td className="table-cell font-mono text-slate-500 max-w-[80px] truncate" title={d.gen}>{d.gen || '—'}</td>
                          <td className="table-cell font-mono">{d.num_control_raw || d.num_control || '—'}</td>
                          <td className="table-cell text-slate-500">{r.filename || '—'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab 2 — Resumen por Proveedor */}
            {tab === 2 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      {['Proveedor','Docs','NIT','DUI','Exentas','Gravadas','IVA','Total'].map(h => (
                        <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resumenProv.map((p, i) => (
                      <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                        <td className="table-cell font-medium text-slate-200 max-w-[180px] truncate" title={p.nom}>{p.nom}</td>
                        <td className="table-cell text-center text-blue-400 font-bold">{p.docs}</td>
                        <td className="table-cell font-mono">{p.nit || '—'}</td>
                        <td className="table-cell font-mono">{p.dui || '—'}</td>
                        <td className="table-cell text-right font-mono">{`$${fmt(p.exe)}`}</td>
                        <td className="table-cell text-right font-mono text-emerald-400">{`$${fmt(p.gra)}`}</td>
                        <td className="table-cell text-right font-mono text-amber-400">{`$${fmt(p.iva)}`}</td>
                        <td className="table-cell text-right font-mono text-white">{`$${fmt(p.tot)}`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {resumenProv.length === 0 && (
                  <p className="text-center text-slate-500 py-8 text-sm">Sin datos</p>
                )}
              </div>
            )}

            {/* Tab 3 — Anexo 8 Percepciones */}
            {tab === 3 && (
              <div className="space-y-3">
                {percepciones.length === 0 ? (
                  <p className="text-center text-slate-500 py-8 text-sm">
                    No hay documentos con percepciones (perc &gt; 0 y tipo 03/05/06/12).
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr>
                          {['Fecha','Tipo','Proveedor','NIT/NRC','DUI','Exentas','Gravadas','IVA','Percepción'].map(h => (
                            <th key={h} className="table-head text-left whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {percepciones.map((r, i) => (
                          <tr key={i} className="hover:bg-surface-700/40 transition-colors">
                            <td className="table-cell">{r.fecha || '—'}</td>
                            <td className="table-cell font-mono">{r.tipo || '—'}</td>
                            <td className="table-cell max-w-[140px] truncate" title={r.nom_prov}>{r.nom_prov || '—'}</td>
                            <td className="table-cell font-mono">{r.nit_prov || '—'}</td>
                            <td className="table-cell font-mono">{r.dui_prov || '—'}</td>
                            <td className="table-cell text-right font-mono">{`$${fmt(r.exe)}`}</td>
                            <td className="table-cell text-right font-mono text-emerald-400">{`$${fmt(r.gra)}`}</td>
                            <td className="table-cell text-right font-mono text-amber-400">{`$${fmt(r.iva)}`}</td>
                            <td className="table-cell text-right font-mono text-sky-400 font-bold">{`$${fmt(r.perc)}`}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
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
                            {d.nom_prov || d.nit_prov || r.filename || `Doc #${i + 1}`}
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
                          <p className="text-xs font-mono text-amber-400">${fmt(d.tot)}</p>
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
