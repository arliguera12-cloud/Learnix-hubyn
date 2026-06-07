import { exportarExcel } from '../services/api'

export default function ResultadosTabla({ data, tipo, declaranteId }) {
  if (!data) return null

  const { registro = {}, correcciones_ia = [], filename } = data

  // Limpiar campos internos para la tabla
  const SKIP = new Set(['gemini_correcciones', '_vision_campos', '_vision_alertas', '_vision_audit'])
  const campos = Object.entries(registro).filter(([k]) => !SKIP.has(k))

  async function handleExportar() {
    try {
      const res = await exportarExcel(tipo, declaranteId)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `${tipo}_${declaranteId}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Error al exportar. Verifica que haya registros guardados.')
    }
  }

  const tieneError = registro.error || registro.error_fatal || registro.error_tipo
  const errorMsg = registro.error_fatal || registro.error_tipo || registro.error

  if (tieneError) {
    return (
      <div className="card border-red-800 bg-red-900/20 mt-4">
        <p className="text-red-400 font-semibold">Error al procesar</p>
        <p className="text-sm text-red-300 mt-1">{errorMsg}</p>
      </div>
    )
  }

  return (
    <div className="mt-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-400">
            Archivo: <span className="text-slate-200">{filename}</span>
          </p>
          {correcciones_ia.length > 0 && (
            <p className="text-xs text-amber-400 mt-0.5">
              IA realizó {correcciones_ia.length} corrección(es)
            </p>
          )}
        </div>
        <button onClick={handleExportar} className="btn-ghost text-sm flex items-center gap-2">
          <span>📥</span> Exportar Excel
        </button>
      </div>

      {/* Tabla de campos extraídos */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-head text-left">Campo</th>
                <th className="table-head text-left">Valor</th>
              </tr>
            </thead>
            <tbody>
              {campos.map(([key, val]) => (
                <tr key={key} className="hover:bg-surface-700/50 transition-colors">
                  <td className="table-cell font-mono text-slate-400 text-xs">{key}</td>
                  <td className="table-cell">
                    {val === null || val === undefined || val === '' ? (
                      <span className="text-slate-600 italic text-xs">—</span>
                    ) : typeof val === 'number' ? (
                      <span className="font-mono text-emerald-400">{val.toLocaleString('es-SV', { minimumFractionDigits: 2 })}</span>
                    ) : (
                      <span className="text-slate-200">{String(val)}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Correcciones IA */}
      {correcciones_ia.length > 0 && (
        <details className="card text-sm">
          <summary className="cursor-pointer text-amber-400 font-medium">
            🤖 Correcciones aplicadas por IA ({correcciones_ia.length})
          </summary>
          <ul className="mt-3 space-y-1">
            {correcciones_ia.map((c, i) => (
              <li key={i} className="text-slate-300 text-xs pl-4 border-l-2 border-amber-800">{c}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
