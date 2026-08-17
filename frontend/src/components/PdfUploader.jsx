import { useRef, useState } from 'react'
import { IconSubir } from './Icons'
import ImportCenter from './ImportCenter'

export default function PdfUploader({ onUpload, loading, multiple = false }) {
  const inputRef = useRef(null)
  const [files, setFiles] = useState([])
  const [declaranteId, setDeclaranteId] = useState('')
  const [nombreDeclarante, setNombreDeclarante] = useState('')
  const [dragging, setDragging] = useState(false)

  function handleFiles(selected) {
    const validos = Array.from(selected).filter(f => {
      const name = f.name.toLowerCase()
      return name.endsWith('.pdf') || name.endsWith('.json')
    })
    setFiles(validos)
  }

  /** Archivos traídos del Centro de importación (Drive/Gmail): se suman a los ya elegidos. */
  function handleImportados(nuevos) {
    setFiles(prev => {
      const combinados = multiple ? [...prev, ...nuevos] : nuevos.slice(-1)
      const vistos = new Set()
      return combinados.filter(f => {
        const clave = `${f.name}:${f.size}`
        if (vistos.has(clave)) return false
        vistos.add(clave)
        return true
      })
    })
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!files.length || !declaranteId.trim()) return
    onUpload(multiple ? files : files[0], declaranteId.trim(), nombreDeclarante.trim())
  }

  const canSubmit = files.length > 0 && declaranteId.trim() && !loading

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="form-label">NIT del declarante *</label>
          <input
            className="input"
            placeholder="06141503071023"
            value={declaranteId}
            onChange={e => setDeclaranteId(e.target.value)}
            maxLength={14}
            required
          />
        </div>
        <div>
          <label className="form-label">Nombre / Razón social</label>
          <input
            className="input"
            placeholder="EMPRESA S.A. DE C.V."
            value={nombreDeclarante}
            onChange={e => setNombreDeclarante(e.target.value)}
          />
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border border-dashed rounded-xl px-6 py-9 text-center cursor-pointer transition-colors duration-150
          ${dragging ? 'border-accent bg-accent/5' : 'border-hairline hover:border-fg-4 bg-panel2/40'}`}
      >
        <IconSubir className="w-7 h-7 mx-auto mb-3 text-fg-4" />
        <p className="text-sm text-fg-3">
          {files.length
            ? files.map(f => f.name).join(', ')
            : 'Arrastra el archivo aquí o haz clic para seleccionar'}
        </p>
        <p className="text-xs text-fg-4 mt-1">
          PDF o JSON firmado por Hacienda{multiple ? ' — múltiples permitidos' : ''}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.json"
          multiple={multiple}
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
        />
      </div>

      <ImportCenter onImportar={handleImportados} />

      <button type="submit" disabled={!canSubmit} className="btn-primary w-full py-2.5">
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
            Procesando…
          </span>
        ) : 'Extraer DTE'}
      </button>
    </form>
  )
}
