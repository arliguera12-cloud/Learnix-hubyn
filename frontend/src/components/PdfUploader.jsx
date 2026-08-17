import { useRef, useState } from 'react'
import { IconSubir, IconCerrar, IconArchivo } from './Icons'
import ImportCenter from './ImportCenter'
import ClienteSelector from './ClienteSelector'
import { useClienteActivo } from '../services/clienteActivo'

function tamano(bytes) {
  if (!bytes) return ''
  const kb = bytes / 1024
  return kb < 1024 ? `${kb.toFixed(0)} KB` : `${(kb / 1024).toFixed(1)} MB`
}

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

  function quitarArchivo(i) {
    setFiles(prev => prev.filter((_, idx) => idx !== i))
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

      {/* Zona de subida */}
      <div>
        <label className="form-label">Documentos *</label>
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`flex items-center gap-3.5 rounded-lg border border-dashed px-4 py-3.5 cursor-pointer transition-colors duration-150
            ${dragging ? 'border-accent bg-accent/5' : 'border-hairline hover:border-fg-4 bg-panel2/40'}`}
        >
          <div className="shrink-0 h-10 w-10 rounded-lg border border-hairline bg-panel flex items-center justify-center">
            <IconSubir className="w-5 h-5 text-fg-4" />
          </div>
          <div className="min-w-0">
            <p className="text-sm text-fg-2 font-medium">
              Arrastrá el archivo aquí o hacé clic para elegirlo
            </p>
            <p className="text-xs text-fg-4 mt-0.5">
              PDF o JSON firmado por Hacienda{multiple ? ' — se pueden elegir varios' : ''}
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.json"
            multiple={multiple}
            className="hidden"
            onChange={e => handleFiles(e.target.files)}
          />
        </div>

        {files.length > 0 && (
          <ul className="mt-2 rounded-lg border border-hairline divide-y divide-hairline overflow-hidden">
            {files.map((f, i) => (
              <li key={`${f.name}:${f.size}:${i}`} className="flex items-center gap-2.5 px-3 py-2 bg-panel/60">
                <IconArchivo className="w-4 h-4 text-fg-4 shrink-0" />
                <span className="text-sm text-fg-2 truncate flex-1">{f.name}</span>
                <span className="text-xs text-fg-5 font-mono shrink-0">{tamano(f.size)}</span>
                <button
                  type="button"
                  onClick={() => quitarArchivo(i)}
                  className="shrink-0 text-fg-4 hover:text-red-400 transition-colors"
                  aria-label={`Quitar ${f.name}`}
                >
                  <IconCerrar className="w-3.5 h-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
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
