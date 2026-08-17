/**
 * Centro de importación — trae PDF/JSON desde una carpeta de Google Drive o
 * desde adjuntos de Gmail, sin pasar primero por el explorador de archivos.
 *
 * Existía en la versión Streamlit (components/drive_import.py,
 * components/gmail_import.py) pero se perdió al reescribir a FastAPI/React —
 * utils/drive_utils.py y utils/gmail_utils.py quedaron completos en el
 * backend, solo sin un endpoint ni una pantalla que los usara. Este panel es
 * la reconexión, embebido dentro de PdfUploader para que los cuatro
 * extractores lo hereden sin duplicar código.
 */
import { useState } from 'react'
import { IconNube, IconCorreo } from './Icons'
import { importarDriveListar, importarDriveDescargar, importarGmailBuscar } from '../services/api'

function base64AFile(base64, nombre) {
  const binario = atob(base64)
  const bytes = new Uint8Array(binario.length)
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i)
  const tipo = nombre.toLowerCase().endsWith('.json') ? 'application/json' : 'application/pdf'
  return new File([bytes], nombre, { type: tipo })
}

function PanelDrive({ onImportar }) {
  const [apiKey, setApiKey] = useState('')
  const [url, setUrl] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [archivos, setArchivos] = useState([])
  const [seleccion, setSeleccion] = useState(new Set())

  async function listar() {
    if (!apiKey.trim() || !url.trim()) {
      setError('Ingresa la API Key y el enlace de la carpeta.')
      return
    }
    setCargando(true)
    setError('')
    try {
      const { data } = await importarDriveListar(apiKey.trim(), url.trim())
      setArchivos(data.archivos)
      setSeleccion(new Set(data.archivos.map((_, i) => i)))
      if (!data.archivos.length) setError('No se encontraron PDF/JSON en esa carpeta.')
    } catch (e) {
      setArchivos([])
      setError(e.response?.data?.detail || 'No se pudo leer la carpeta de Drive.')
    } finally {
      setCargando(false)
    }
  }

  async function importarSeleccion() {
    const elegidos = archivos.filter((_, i) => seleccion.has(i))
    if (!elegidos.length) return
    setCargando(true)
    setError('')
    try {
      const { data } = await importarDriveDescargar(
        apiKey.trim(),
        elegidos.map(a => ({ id: a.id, name: a.name, resourceKey: a.resourceKey, carpeta: a.carpeta })),
      )
      const files = data.archivos.map(a => base64AFile(a.contenido_base64, a.name))
      onImportar(files)
      if (data.errores?.length) {
        setError(`${data.errores.length} archivo(s) no se pudieron descargar: ${data.errores.map(e => e.name).join(', ')}`)
      }
      setArchivos([])
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudieron descargar los archivos.')
    } finally {
      setCargando(false)
    }
  }

  function alternar(i) {
    setSeleccion(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-fg-4">
        La carpeta debe estar compartida como «Cualquiera con el enlace → Lector».
        Necesitas una API Key de Google con la API de Drive habilitada.
      </p>
      <input
        className="input text-sm"
        type="password"
        placeholder="API Key de Google (AIza...)"
        value={apiKey}
        onChange={e => setApiKey(e.target.value)}
      />
      <input
        className="input text-sm"
        placeholder="https://drive.google.com/drive/folders/..."
        value={url}
        onChange={e => setUrl(e.target.value)}
      />
      <button type="button" className="btn-ghost border border-hairline text-sm w-full" onClick={listar} disabled={cargando}>
        {cargando ? 'Buscando…' : 'Listar carpeta'}
      </button>

      {error && <p className="text-xs text-red-500">{error}</p>}

      {archivos.length > 0 && (
        <div className="space-y-2">
          <div className="max-h-48 overflow-y-auto border border-hairline rounded-lg divide-y divide-hairline">
            {archivos.map((a, i) => (
              <label key={a.id} className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer">
                <input type="checkbox" checked={seleccion.has(i)} onChange={() => alternar(i)} />
                <span className="truncate flex-1">{a.name}</span>
                <span className="text-xs text-fg-4 shrink-0">{a.carpeta}</span>
              </label>
            ))}
          </div>
          <button type="button" className="btn-primary text-sm w-full py-2" onClick={importarSeleccion} disabled={cargando || !seleccion.size}>
            {cargando ? 'Descargando…' : `Importar ${seleccion.size} archivo(s)`}
          </button>
        </div>
      )}
    </div>
  )
}

function PanelGmail({ onImportar }) {
  const [email, setEmail] = useState('')
  const [appPassword, setAppPassword] = useState('')
  const [remitente, setRemitente] = useState('')
  const [texto, setTexto] = useState('')
  const [dias, setDias] = useState(30)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [adjuntos, setAdjuntos] = useState([])
  const [seleccion, setSeleccion] = useState(new Set())

  async function buscar() {
    if (!email.trim() || !appPassword.trim()) {
      setError('Ingresa el correo y la contraseña de aplicación.')
      return
    }
    setCargando(true)
    setError('')
    try {
      const { data } = await importarGmailBuscar(email.trim(), appPassword.trim(), {
        remitente: remitente.trim(),
        texto: texto.trim(),
        dias: Number(dias) || 30,
      })
      setAdjuntos(data.adjuntos)
      setSeleccion(new Set(data.adjuntos.map((_, i) => i)))
      if (!data.adjuntos.length) setError('No se encontraron adjuntos con esos filtros.')
    } catch (e) {
      setAdjuntos([])
      setError(e.response?.data?.detail || 'No se pudo conectar con Gmail.')
    } finally {
      setCargando(false)
    }
  }

  function importarSeleccion() {
    const elegidos = adjuntos.filter((_, i) => seleccion.has(i))
    if (!elegidos.length) return
    const files = elegidos.map(a => base64AFile(a.contenido_base64, a.filename))
    onImportar(files)
    setAdjuntos([])
  }

  function alternar(i) {
    setSeleccion(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-fg-4">
        Activa la verificación en 2 pasos y genera una contraseña de aplicación en{' '}
        myaccount.google.com/apppasswords — no uses tu contraseña normal.
      </p>
      <input
        className="input text-sm"
        placeholder="tucorreo@gmail.com"
        value={email}
        onChange={e => setEmail(e.target.value)}
      />
      <input
        className="input text-sm"
        type="password"
        placeholder="Contraseña de aplicación"
        value={appPassword}
        onChange={e => setAppPassword(e.target.value)}
      />
      <div className="grid grid-cols-2 gap-2">
        <input
          className="input text-sm"
          placeholder="Remitente (opcional)"
          value={remitente}
          onChange={e => setRemitente(e.target.value)}
        />
        <input
          className="input text-sm"
          placeholder="Texto a buscar (opcional)"
          value={texto}
          onChange={e => setTexto(e.target.value)}
        />
      </div>
      <div className="flex items-center gap-2">
        <label className="text-xs text-fg-4 shrink-0">Últimos días</label>
        <input
          type="number"
          min={1}
          max={365}
          className="input text-sm w-24"
          value={dias}
          onChange={e => setDias(e.target.value)}
        />
      </div>
      <button type="button" className="btn-ghost border border-hairline text-sm w-full" onClick={buscar} disabled={cargando}>
        {cargando ? 'Buscando…' : 'Buscar en Gmail'}
      </button>

      {error && <p className="text-xs text-red-500">{error}</p>}

      {adjuntos.length > 0 && (
        <div className="space-y-2">
          <div className="max-h-48 overflow-y-auto border border-hairline rounded-lg divide-y divide-hairline">
            {adjuntos.map((a, i) => (
              <label key={`${a.filename}-${i}`} className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer">
                <input type="checkbox" checked={seleccion.has(i)} onChange={() => alternar(i)} />
                <span className="truncate flex-1">{a.filename}</span>
                <span className="text-xs text-fg-4 shrink-0">{a.fecha}</span>
              </label>
            ))}
          </div>
          <button type="button" className="btn-primary text-sm w-full py-2" onClick={importarSeleccion} disabled={!seleccion.size}>
            {`Importar ${seleccion.size} adjunto(s)`}
          </button>
        </div>
      )}
    </div>
  )
}

export default function ImportCenter({ onImportar }) {
  const [abierto, setAbierto] = useState(false)
  const [tab, setTab] = useState('drive')

  return (
    <div className="border border-hairline rounded-lg">
      <button
        type="button"
        onClick={() => setAbierto(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-fg-3 hover:text-fg-1 transition-colors"
      >
        <IconNube className="w-4 h-4 shrink-0" />
        Importar desde Drive o Gmail
        <span className="ml-auto text-xs text-fg-4">{abierto ? '−' : '+'}</span>
      </button>

      {abierto && (
        <div className="border-t border-hairline p-3 space-y-3">
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setTab('drive')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${tab === 'drive' ? 'bg-panel2 text-fg-1' : 'text-fg-4 hover:text-fg-2'}`}
            >
              <IconNube className="w-3.5 h-3.5" /> Drive
            </button>
            <button
              type="button"
              onClick={() => setTab('gmail')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${tab === 'gmail' ? 'bg-panel2 text-fg-1' : 'text-fg-4 hover:text-fg-2'}`}
            >
              <IconCorreo className="w-3.5 h-3.5" /> Gmail
            </button>
          </div>

          {tab === 'drive' ? <PanelDrive onImportar={onImportar} /> : <PanelGmail onImportar={onImportar} />}
        </div>
      )}
    </div>
  )
}
