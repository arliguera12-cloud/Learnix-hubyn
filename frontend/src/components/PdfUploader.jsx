import { useRef, useState } from 'react'
import { IconSubir } from './Icons'
import ImportCenter from './ImportCenter'
import ClienteSelector from './ClienteSelector'
import { useClienteActivo } from '../services/clienteActivo'

export default function PdfUploader({ onUpload, loading, multiple = false }) {
  const inputRef = useRef(null)
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)

  const { clienteActivo, setClienteActivo } = useClienteActivo()
  const [modoManual, setModoManual] = useState(false)
  const [manualNit, setManualNit] = useState('')
  const [manualNombre, setManualNombre] = useState('')

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

  const declaranteId = modoManual ? manualNit.trim() : (clienteActivo?.nit ?? '')
  const nombreDeclarante = modoManual ? manualNombre.trim() : (clienteActivo?.nombre_comercial ?? '')

  function handleSubmit(e) {
    e.preventDefault()
    if (!files.length || !declaranteId) return
    onUpload(multiple ? files : files[0], declaranteId, nombreDeclarante)
  }

  const canSubmit = files.length > 0 && !!declaranteId && !loading

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Cliente */}
      <div>
        <label className="form-label">Cliente *</label>

        {modoManual ? (
          <div className="space-y-2">
            <div className="grid sm:grid-cols-2 gap-3">
              <input
                className="input"
                placeholder="NIT — 06141503071023"
                value={manualNit}
                onChange={e => setManualNit(e.target.value)}
                maxLength={14}
              />
              <input
                className="input"
                placeholder="Nombre / Razón social"
                value={manualNombre}
                onChange={e => setManualNombre(e.target.value)}
              />
            </div>
            <button
              type="button"
              onClick={() => { setModoManual(false); setManualNit(''); setManualNombre('') }}
              className="text-xs text-fg-4 hover:text-fg-2 underline"
            >
              Elegir del directorio en vez de escribir
            </button>
          </div>
        ) : clienteActivo ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-hairline bg-panel2/40 px-3 py-2.5">
            <div className="min-w-0">
              <p className="text-sm text-fg truncate">{clienteActivo.nombre_comercial}</p>
              <p className="text-xs text-fg-4 font-mono">{clienteActivo.nit}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button type="button" onClick={() => setClienteActivo(null)} className="btn-ghost text-xs">
                Cambiar
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <ClienteSelector onSeleccionar={setClienteActivo} />
            <button type="button" onClick={() => setModoManual(true)} className="text-xs text-fg-4 hover:text-fg-2 underline">
              Cliente nuevo (no está en el directorio)
            </button>
          </div>
        )}
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
