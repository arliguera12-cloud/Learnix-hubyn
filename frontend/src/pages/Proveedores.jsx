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

  const filtrados = todos.filter(p =>
    p.nombre_comercial?.toLowerCase().includes(busqueda.toLowerCase()) ||
    p.nit?.includes(busqueda)
  )

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
    }
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

      <div>
        <input
          className="input max-w-xs"
          placeholder="Buscar por nombre o NIT…"
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
      </div>

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
                  {['NIT', 'Nombre', 'NRC', ''].map(h => (
                    <th key={h} className="table-head text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtrados.map(p => (
                  <tr key={p.id} className="hover:bg-surface-700/50 transition-colors">
                    <td className="table-cell font-mono text-xs text-slate-300">{p.nit}</td>
                    <td className="table-cell font-medium text-slate-100">{p.nombre_comercial}</td>
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
