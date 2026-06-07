import { useState } from 'react'
import { procesarVentas } from '../services/api'
import PdfUploader from '../components/PdfUploader'
import ResultadosTabla from '../components/ResultadosTabla'

export default function Ventas() {
  const [resultados, setResultados] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleUpload(file, declaranteId) {
    setLoading(true)
    setError(null)
    try {
      const { data } = await procesarVentas(file, declaranteId)
      setResultados(data)
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <h1>Extractor DTE — Ventas</h1>
      <PdfUploader onUpload={handleUpload} loading={loading} />
      {error && <p className="error">{error}</p>}
      {resultados && <ResultadosTabla data={resultados} />}
    </div>
  )
}
