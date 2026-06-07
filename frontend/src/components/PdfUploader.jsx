import { useState } from 'react'

export default function PdfUploader({ onUpload, loading }) {
  const [file, setFile] = useState(null)
  const [declaranteId, setDeclaranteId] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!file || !declaranteId) return
    onUpload(file, declaranteId)
  }

  return (
    <form onSubmit={handleSubmit} className="pdf-uploader">
      <label>
        ID del declarante
        <input
          type="text"
          value={declaranteId}
          onChange={(e) => setDeclaranteId(e.target.value)}
          placeholder="ej. 06141503071023"
          required
        />
      </label>
      <label>
        Archivo PDF
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files[0] ?? null)}
          required
        />
      </label>
      <button type="submit" disabled={loading || !file || !declaranteId}>
        {loading ? 'Procesando…' : 'Extraer DTE'}
      </button>
    </form>
  )
}
