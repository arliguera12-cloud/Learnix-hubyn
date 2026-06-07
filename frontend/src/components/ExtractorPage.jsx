import { useState } from 'react'
import PdfUploader from './PdfUploader'
import ResultadosTabla from './ResultadosTabla'

export default function ExtractorPage({ titulo, icono, descripcion, tipo, apiFn }) {
  const [resultado, setResultado] = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [declaranteId, setDeclaranteId] = useState('')

  async function handleUpload(file, dId, nombre) {
    setLoading(true)
    setError(null)
    setDeclaranteId(dId)
    try {
      const { data } = await apiFn(file, dId, nombre)
      setResultado(data)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail ?? err.message))
    } finally {
      setLoading(false)
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
        <PdfUploader onUpload={handleUpload} loading={loading} />
      </div>

      {error && (
        <div className="card border-red-800 bg-red-900/20">
          <p className="text-red-400 font-semibold text-sm">⚠️ Error</p>
          <p className="text-red-300 text-sm mt-1">{error}</p>
        </div>
      )}

      {resultado && (
        <ResultadosTabla data={resultado} tipo={tipo} declaranteId={declaranteId} />
      )}
    </div>
  )
}
