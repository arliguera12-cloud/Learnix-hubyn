import { useEffect, useState } from 'react'
import { supabase } from '../services/supabase'
import { IconProveedores, IconAlerta, IconCheck } from '../components/Icons'

function limpiarNumero(v) {
  return String(v || '').replace(/[^0-9]/g, '')
}

export default function Proveedores() {
  const [todos,          setTodos]          = useState([])
  const [busqueda,       setBusqueda]       = useState('')
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  const [organizacionId, setOrganizacionId] = useState(null)
  const [guardando,      setGuardando]      = useState(false)
  const [aviso,          setAviso]          = useState(null)
  const [seleccion,      setSeleccion]      = useState(new Set())
  const [eliminando,     setEliminando]     = useState(false)
  const [soloDuplicados, setSoloDuplicados] = useState(false)

  const [form, setForm] = useState({ nit: '', nombre: '', nrc: '' })

  async function cargar() {
    setLoading(true)
    const { data, error } = await supabase.from('proveedores').select('*').order('nombre_comercial')
    if (error) setError(error.message)
    else { setTodos(data ?? []); setError(null) }
    setLoading(false)
  }

  useEffect(() => {
    cargar()
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) return
      const { data } = await supabase.from('perfiles').select('organizacion_id').eq('id', user.id).single()
      setOrganizacionId(data?.organizacion_id ?? null)
    })
  }, [])

  // Posibles duplicados: mismo nombre comercial normalizado. El NIT ya es
  // único a nivel de base de datos, así que un duplicado real solo puede
  // darse por el nombre — dos registros para el mismo proveedor con NIT
  // distinto (typo, sucursal cargada aparte, etc.).
  const nombreNormalizado = p => (p.nombre_comercial || '').trim().toUpperCase().replace(/\s+/g, ' ')
  const conteoPorNombre = todos.reduce((acc, p) => {
    const k = nombreNormalizado(p)
    if (k) acc[k] = (acc[k] || 0) + 1
    return acc
  }, {})
  const idsDuplicados = new Set(todos.filter(p => conteoPorNombre[nombreNormalizado(p)] > 1).map(p => p.id))
  const gruposDuplicados = new Set(Object.entries(conteoPorNombre).filter(([, n]) => n > 1).map(([k]) => k)).size

  const filtrados = todos.filter(p =>
    (p.nombre_comercial?.toLowerCase().includes(busqueda.toLowerCase()) ||
     p.nit?.includes(busqueda)) &&
    (!soloDuplicados || idsDuplicados.has(p.id))
  )

  function alternarSeleccion(id) {
    setSeleccion(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function alternarSeleccionTodos() {
    setSeleccion(prev =>
      prev.size === filtrados.length ? new Set() : new Set(filtrados.map(p => p.id))
    )
  }

  async function agregar(e) {
    e.preventDefault()
    setAviso(null)
    const nit = limpiarNumero(form.nit)
    const nombre = form.nombre.trim()

    if (!nit || !nombre) {
      setAviso({ tipo: 'error', texto: 'El NIT y la razón social son obligatorios.' })
      return
    }
    if (nit.length !== 9 && nit.length !== 14) {
      setAviso({ tipo: 'error', texto: 'El NIT debe tener 9 o 14 dígitos.' })
      return
    }
    if (!organizacionId) {
      setAviso({ tipo: 'error', texto: 'No se pudo determinar tu organización. Recarga la página.' })
      return
    }

    setGuardando(true)
    const { error } = await supabase.from('proveedores').insert({
      organizacion_id: organizacionId,
      nit,
      nombre_comercial: nombre.toUpperCase(),
      nrc: limpiarNumero(form.nrc),
    })
    setGuardando(false)

    if (error) {
      setAviso({
        tipo: 'error',
        texto: error.code === '23505' ? 'Ya existe un proveedor con ese NIT.' : error.message,
      })
      return
    }

    setAviso({ tipo: 'ok', texto: `${nombre.toUpperCase()} guardado correctamente.` })
    setForm({ nit: '', nombre: '', nrc: '' })
    cargar()
  }

  async function eliminar(proveedor) {
    if (!window.confirm(`¿Eliminar a ${proveedor.nombre_comercial}? Esta acción no se puede deshacer.`)) return
    const { error, count } = await supabase.from('proveedores').delete({ count: 'exact' }).eq('id', proveedor.id)
    if (error) {
      setAviso({ tipo: 'error', texto: error.message })
    } else if (!count) {
      setAviso({ tipo: 'error', texto: 'Solo un administrador de la organización puede eliminar proveedores.' })
    } else {
      setTodos(prev => prev.filter(p => p.id !== proveedor.id))
      setSeleccion(prev => { const n = new Set(prev); n.delete(proveedor.id); return n })
    }
  }

  async function eliminarSeleccionados() {
    const ids = [...seleccion]
    if (!ids.length) return
    if (!window.confirm(
      `¿Eliminar ${ids.length} proveedor${ids.length > 1 ? 'es' : ''} seleccionado${ids.length > 1 ? 's' : ''}? Esta acción no se puede deshacer.`
    )) return

    setEliminando(true)
    const { error, count } = await supabase.from('proveedores').delete({ count: 'exact' }).in('id', ids)
    setEliminando(false)

    if (error) {
      setAviso({ tipo: 'error', texto: error.message })
      return
    }
    setTodos(prev => prev.filter(p => !seleccion.has(p.id)))
    setSeleccion(new Set())
    setAviso({
      tipo: 'ok',
      texto: count === ids.length
        ? `${count} proveedor${count > 1 ? 'es' : ''} eliminado${count > 1 ? 's' : ''}.`
        : `${count} de ${ids.length} eliminados — los demás requieren permisos de administrador.`,
    })
  }

  return (
    <div className="max-w-[90rem] mx-auto space-y-5">
      <div>
        <h2 className="text-2xl text-fg flex items-center gap-2.5">
          <IconProveedores className="w-6 h-6 text-accent" />
          Directorio de Proveedores
        </h2>
        <p className="text-sm text-slate-400 mt-0.5">
          {todos.length} proveedor{todos.length === 1 ? '' : 'es'} registrado{todos.length === 1 ? '' : 's'}
        </p>
      </div>

      {aviso && (
        <div className={`card ${aviso.tipo === 'error' ? 'border-red-800 bg-red-900/20' : 'border-emerald-800 bg-emerald-900/15'}`}>
          <p className={`text-sm flex items-start gap-2 ${aviso.tipo === 'error' ? 'text-red-400' : 'text-emerald-400'}`}>
            {aviso.tipo === 'error' ? <IconAlerta className="w-4 h-4 shrink-0 mt-0.5" /> : <IconCheck className="w-4 h-4 shrink-0 mt-0.5" />}
            <span>{aviso.texto}</span>
          </p>
        </div>
      )}

      <div className="card">
        <p className="form-label mb-3">Agregar proveedor</p>
        <form onSubmit={agregar} className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <input className="input" placeholder="NIT *" maxLength={14}
            value={form.nit} onChange={e => setForm(f => ({ ...f, nit: e.target.value }))} />
          <input className="input lg:col-span-2" placeholder="Razón social *"
            value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} />
          <input className="input" placeholder="NRC"
            value={form.nrc} onChange={e => setForm(f => ({ ...f, nrc: e.target.value }))} />
          <button type="submit" disabled={guardando} className="btn-primary py-2 sm:col-span-2 lg:col-span-4">
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
        </form>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <input
          className="input max-w-xs"
          placeholder="Buscar por nombre o NIT…"
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
        {gruposDuplicados > 0 && (
          <button
            type="button"
            onClick={() => setSoloDuplicados(v => !v)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              soloDuplicados
                ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                : 'border-hairline text-fg-4 hover:text-fg-2'
            }`}
          >
            {soloDuplicados ? 'Viendo' : 'Ver'} posibles duplicados ({gruposDuplicados})
          </button>
        )}
      </div>

      {seleccion.size > 0 && (
        <div className="card border-l-2 border-l-accent border-y-0 border-r-0 bg-panel flex items-center justify-between gap-3 py-3">
          <p className="text-sm text-fg-2">
            {seleccion.size} proveedor{seleccion.size > 1 ? 'es' : ''} seleccionado{seleccion.size > 1 ? 's' : ''}
          </p>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setSeleccion(new Set())} className="btn-ghost text-xs px-3 py-1.5 text-fg-4">
              Cancelar
            </button>
            <button
              type="button"
              onClick={eliminarSeleccionados}
              disabled={eliminando}
              className="btn-ghost text-xs px-3 py-1.5 text-red-400 hover:text-red-300 border border-red-800/50"
            >
              {eliminando ? 'Eliminando…' : `Eliminar seleccionados`}
            </button>
          </div>
        </div>
      )}

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="card p-0 overflow-hidden">
        {loading ? (
          <p className="p-6 text-center text-slate-400 text-sm">Cargando…</p>
        ) : filtrados.length === 0 ? (
          <p className="p-6 text-center text-slate-500 text-sm">
            {busqueda ? 'Sin resultados para la búsqueda.' : 'Sin proveedores registrados.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="table-head text-left w-8">
                    <input
                      type="checkbox"
                      checked={filtrados.length > 0 && seleccion.size === filtrados.length}
                      onChange={alternarSeleccionTodos}
                      aria-label="Seleccionar todos"
                    />
                  </th>
                  {['NIT', 'Nombre', 'NRC', ''].map(h => (
                    <th key={h} className="table-head text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtrados.map(p => (
                  <tr
                    key={p.id}
                    className={`hover:bg-surface-700/50 transition-colors ${
                      idsDuplicados.has(p.id) ? 'bg-amber-500/5' : ''
                    }`}
                  >
                    <td className="table-cell">
                      <input
                        type="checkbox"
                        checked={seleccion.has(p.id)}
                        onChange={() => alternarSeleccion(p.id)}
                        aria-label={`Seleccionar ${p.nombre_comercial}`}
                      />
                    </td>
                    <td className="table-cell font-mono text-xs text-slate-300">{p.nit}</td>
                    <td className="table-cell font-medium text-slate-100">
                      {p.nombre_comercial}
                      {idsDuplicados.has(p.id) && (
                        <span className="ml-2 text-[0.65rem] text-amber-400 font-semibold uppercase tracking-wide">
                          posible duplicado
                        </span>
                      )}
                    </td>
                    <td className="table-cell font-mono text-xs">{p.nrc || '—'}</td>
                    <td className="table-cell text-right">
                      <button onClick={() => eliminar(p)} className="btn-ghost text-xs text-red-400 hover:text-red-300 px-2 py-1">
                        Eliminar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
