import { useState } from 'react'
import { IconExportar, IconAlerta } from './Icons'
import { exportarExcel } from '../services/api'
import { EstadoBadge, esAlerta, nivelEstado } from '../utils/dte'

// Campos a mostrar por tipo, con etiquetas amigables
const CAMPOS_DISPLAY = {
  ventas: [
    ['fecha',      'Fecha emisión'],
    ['tipo',       'Tipo DTE'],
    ['num_control','N° Control'],
    ['gen',        'Cód. Generación'],
    ['sello',      'Sello recepción'],
    ['nit_cli',    'NIT/NRC cliente'],
    ['dui_cli',    'DUI cliente'],
    ['nom_cli',    'Nombre cliente'],
    ['exentas',    'Ventas exentas'],
    ['no_sujetas', 'No sujetas'],
    ['gravadas',   'Ventas gravadas'],
    ['debito',     'Débito fiscal'],
    ['terceros',   'Ventas terceros'],
    ['deb_terc',   'Déb. terceros'],
    ['total',      'Total'],
  ],
  compras: [
    ['fecha',    'Fecha emisión'],
    ['tipo',     'Tipo DTE'],
    ['gen',      'Cód. Generación'],
    ['sello',    'Sello recepción'],
    ['nit_prov', 'NIT/NRC proveedor'],
    ['dui_prov', 'DUI proveedor'],
    ['nom_prov', 'Nombre proveedor'],
    ['exe',      'Compras exentas'],
    ['gra',      'Compras gravadas'],
    ['iva',      'Crédito fiscal'],
    ['ret',      'Retención'],
    ['perc',     'Percepción'],
    ['tot',      'Total compras'],
    ['fovial',   'FOVIAL'],
    ['cotrans',  'COTRANS'],
  ],
  retenciones: [
    ['nit_prov', 'NIT agente retención'],
    ['fecha',    'Fecha emisión'],
    ['tipo',     'Tipo DTE'],
    ['sello',    'Sello recepción'],
    ['gen',      'Cód. Generación'],
    ['base',     'Monto sujeto'],
    ['ret',      'Retención 1%'],
  ],
  sujetos_excluidos: [
    ['id_sujeto',  'Identificación'],
    ['nom_sujeto', 'Nombre sujeto excluido'],
    ['fecha',      'Fecha emisión'],
    ['tipo',       'Tipo DTE'],
    ['sello',      'Sello recepción'],
    ['gen',        'Cód. Generación'],
    ['base',       'Monto operación'],
    ['ret',        'Retención IVA 13%'],
  ],
}

const CAMPOS_NUMERICOS = new Set([
  'exentas','no_sujetas','gravadas','debito','terceros','deb_terc','total',
  'exe','gra','iva','ret','perc','tot','fovial','cotrans','base',
])

function fmt(v) {
  return Number(v).toLocaleString('es-SV', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function descargarBlob(blobData, nombre) {
  const url = URL.createObjectURL(new Blob([blobData]))
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  a.click()
  URL.revokeObjectURL(url)
}

export default function ResultadosTabla({ data, tipo, declaranteId, index }) {
  const [exportando, setExportando] = useState(false)
  const [expandido,  setExpandido]  = useState(false)

  if (!data) return null

  const { registro = {}, correcciones_ia = [], filename } = data
  const tieneError  = registro.error || registro.error_fatal || registro.error_tipo
  const errorMsg    = registro.error_fatal || registro.error_tipo || registro.error

  async function handleExportar() {
    setExportando(true)
    try {
      const res = await exportarExcel(tipo, declaranteId, [registro])
      descargarBlob(res.data, `F07_${tipo}_${declaranteId}_${index || 1}.xlsx`)
    } catch {
      alert('Error al exportar.')
    } finally {
      setExportando(false)
    }
  }

  if (tieneError) {
    return (
      <div className="card border-red-800 bg-red-900/20">
        <div className="flex items-start gap-3">
          <IconAlerta className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-red-400 font-semibold text-sm">
              {filename && <span className="text-red-300 font-mono text-xs mr-2">{filename}</span>}
              Error al procesar
            </p>
            <p className="text-red-300 text-sm mt-1">{errorMsg}</p>
          </div>
        </div>
      </div>
    )
  }

  const campos      = CAMPOS_DISPLAY[tipo] || []
  const tieneIa     = correcciones_ia.length > 0
  const numDocLabel = registro.tipo ? `DTE-${registro.tipo}` : 'DTE'

  return (
    <div className="card space-y-0 p-0 overflow-hidden">
      {/* Cabecera del documento */}
      <div className="px-4 py-3 bg-surface-700 flex items-center justify-between gap-3 border-b border-surface-600">
        <div className="flex items-center gap-3 min-w-0">
          {index && (
            <span className="shrink-0 h-6 w-6 rounded-full bg-brand-500/20 text-brand-400 text-xs font-bold flex items-center justify-center">
              {index}
            </span>
          )}
          <div className="min-w-0">
            <p className="text-sm font-medium text-white truncate">
              {filename || 'Sin nombre'}
            </p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="badge-ok text-xs">{numDocLabel}</span>
              {registro.fecha && (
                <span className="text-xs text-slate-500">{registro.fecha}</span>
              )}
              <EstadoBadge estado={registro.estado} />
              {tieneIa && (
                <span className="text-xs text-amber-400">
                  IA · {correcciones_ia.length} corrección{correcciones_ia.length > 1 ? 'es' : ''}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setExpandido(v => !v)}
            className="btn-ghost text-xs px-2 py-1 text-slate-400"
          >
            {expandido ? 'Ocultar campos' : 'Ver campos'}
          </button>
          <button
            onClick={handleExportar}
            disabled={exportando}
            className="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1.5"
          >
            {exportando ? (
              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
              </svg>
            ) : <IconExportar className="w-3.5 h-3.5" />}
            Excel
          </button>
        </div>
      </div>

      {/* Por qué necesita revisión (siempre visible, no solo al expandir) */}
      {esAlerta(registro.estado) && (registro.detalle_confianza || registro.campos_faltantes?.length > 0) && (
        <div className="px-4 py-2.5 border-b border-surface-600/50 flex items-start gap-2">
          <IconAlerta
            className={`w-4 h-4 mt-0.5 shrink-0 ${nivelEstado(registro.estado) === 'manual' ? 'text-red-400' : 'text-amber-400'}`}
          />
          <p className="text-xs text-slate-400">
            {registro.detalle_confianza || `Campos faltantes: ${registro.campos_faltantes.join(', ')}`}
            {registro.confianza != null && <span className="text-slate-500"> · confianza {registro.confianza}%</span>}
          </p>
        </div>
      )}

      {/* Resumen de montos (siempre visible) */}
      {campos.some(([k]) => CAMPOS_NUMERICOS.has(k) && registro[k]) && (
        <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1 border-b border-surface-600/50">
          {campos
            .filter(([k]) => CAMPOS_NUMERICOS.has(k) && (registro[k] !== undefined && registro[k] !== null && registro[k] !== ''))
            .map(([key, label]) => (
              <div key={key} className="flex justify-between items-baseline text-xs py-0.5">
                <span className="text-slate-500 truncate pr-2">{label}</span>
                <span className="font-mono text-emerald-400 tabular-nums shrink-0">
                  ${fmt(registro[key])}
                </span>
              </div>
            ))
          }
        </div>
      )}

      {/* Tabla de campos (expandible) */}
      {expandido && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-head text-left w-40">Campo</th>
                <th className="table-head text-left">Valor</th>
              </tr>
            </thead>
            <tbody>
              {campos.map(([key, label]) => {
                const val = registro[key]
                if (val === undefined || val === null) return null
                const esNum = CAMPOS_NUMERICOS.has(key)
                return (
                  <tr key={key} className="hover:bg-surface-700/40 transition-colors">
                    <td className="table-cell text-slate-500 text-xs font-medium w-40">{label}</td>
                    <td className="table-cell">
                      {val === '' ? (
                        <span className="text-slate-600 italic text-xs">—</span>
                      ) : esNum ? (
                        <span className="font-mono text-emerald-400 text-sm tabular-nums">
                          ${fmt(val)}
                        </span>
                      ) : (
                        <span className="text-slate-200 text-sm break-all">{String(val)}</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Correcciones IA */}
      {tieneIa && expandido && (
        <div className="px-4 py-3 border-t border-surface-600/50 bg-amber-900/10">
          <p className="text-xs text-amber-400 font-semibold mb-2">
            Correcciones aplicadas por IA
          </p>
          <ul className="space-y-1">
            {correcciones_ia.map((c, i) => (
              <li key={i} className="text-xs text-slate-300 pl-3 border-l-2 border-amber-700">
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
