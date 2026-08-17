import { useEffect, useMemo, useRef, useState } from 'react'
import { supabase } from '../services/supabase'

/** Combobox con búsqueda para elegir un cliente del directorio (nombre o NIT). */
export default function ClienteSelector({ onSeleccionar, autoFocus = false }) {
  const [clientes,  setClientes]  = useState([])
  const [cargando,  setCargando]  = useState(true)
  const [busqueda,  setBusqueda]  = useState('')
  const [abierto,   setAbierto]   = useState(false)
  const cajaRef = useRef(null)

  useEffect(() => {
    supabase.from('clientes').select('id,nit,nombre_comercial,nrc,dui').order('nombre_comercial')
      .then(({ data }) => { setClientes(data ?? []); setCargando(false) })
  }, [])

  useEffect(() => {
    function alHacerClicFuera(e) {
      if (cajaRef.current && !cajaRef.current.contains(e.target)) setAbierto(false)
    }
    document.addEventListener('mousedown', alHacerClicFuera)
    return () => document.removeEventListener('mousedown', alHacerClicFuera)
  }, [])

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase()
    if (!q) return clientes
    return clientes.filter(c =>
      c.nombre_comercial?.toLowerCase().includes(q) || c.nit?.includes(q)
    )
  }, [clientes, busqueda])

  function elegir(cliente) {
    onSeleccionar({ nit: cliente.nit, nombre_comercial: cliente.nombre_comercial })
    setBusqueda('')
    setAbierto(false)
  }

  return (
    <div ref={cajaRef} className="relative">
      <input
        className="input text-sm"
        autoFocus={autoFocus}
        placeholder={cargando ? 'Cargando clientes…' : 'Buscar cliente por nombre o NIT…'}
        value={busqueda}
        onFocus={() => setAbierto(true)}
        onChange={e => { setBusqueda(e.target.value); setAbierto(true) }}
        onKeyDown={e => { if (e.key === 'Escape') setAbierto(false) }}
      />

      {abierto && !cargando && (
        <div className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto rounded-lg border border-hairline bg-panel shadow-lg">
          {filtrados.length === 0 ? (
            <p className="px-3 py-2.5 text-sm text-fg-4">
              {clientes.length === 0 ? 'No tenés clientes en el directorio todavía.' : 'Sin resultados.'}
            </p>
          ) : (
            filtrados.map(c => (
              <button
                key={c.id}
                type="button"
                onClick={() => elegir(c)}
                className="w-full text-left px-3 py-2 text-sm hover:bg-panel2 transition-colors flex items-center justify-between gap-2"
              >
                <span className="truncate text-fg">{c.nombre_comercial}</span>
                <span className="text-xs text-fg-4 font-mono shrink-0">{c.nit}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
