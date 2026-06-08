import { useState } from 'react'
import PdfUploader from './PdfUploader'
import ResultadosTabla from './ResultadosTabla'

export default function ExtractorPage({ titulo, icono, descripcion, tipo, apiFn, loteApiFn }) {
  const [resultados, setResultados] = useState([])
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState(null)
  const [progress,   setProgress]   = useState(null) // { done, total } during batch
  const [declaranteId, setDeclaranteId] = useState('')

  async function handleUpload(filesOrFile, dId, nombre) {
    setLoading(true)
    setError(null)
    setProgress(null)
    setDeclaranteId(dId)

    const isMultiple = Array.isArray(filesOrFile)

    try {
      if (isMultiple && loteApiFn) {
        // Batch call — single request, multiple files
        const { data } = await loteApiFn(filesOrFile, dId, nombre)
        const items = data.resultados ?? []
        if (data.errores?.length) {
          setError(data.errores.map(e => `${e.filename}: ${e.error}`).join('\n'))
        }
        setResultados(items)
      } else if (isMultiple) {
        // Sequential fallback when no loteApiFn
        const acc = []
        for (let i = 0; i < filesOrFile.length; i++) {
          setProgress({ done: i, total: filesOrFile.length })
          const { data } = await apiFn(filesOrFile[i], dId, nombre)
          acc.push(data)
        }
        setProgress({ done: filesOrFile.length, total: filesOrFile.length })
        setResultados(acc)
      } else {
        const { data } = await apiFn(filesOrFile, dId, nombre)
        setResultados([data])
      }
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail ?? err.message))
    } finally {
      setLoading(false)
      setProgress(null)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">
          <span className="mr-2">{icono}</span>{titulo}
        </h2>
        <p className="text-sm text-slate-400 mt-0.5">{descripcion}</p>
      </div>

      <div className="card">
        <PdfUploader onUpload={handleUpload} loading={loading} multiple={!!loteApiFn} />
      </div>

      {progress && (
        <div className="card">
          <p className="text-sm text-slate-300">
            Procesando {progress.done + 1} de {progress.total}…
          </p>
          <div className="mt-2 h-1.5 bg-surface-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 transition-all duration-300"
              style={{ width: `${((progress.done + 1) / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="card border-red-800 bg-red-900/20">
          <p className="text-red-400 font-semibold text-sm">⚠️ Error</p>
          <pre className="text-red-300 text-sm mt-1 whitespace-pre-wrap">{error}</pre>
        </div>
      )}

      {resultados.map((r, i) => (
        <ResultadosTabla key={i} data={r} tipo={tipo} declaranteId={declaranteId} />
      ))}
    </div>
  )
}
