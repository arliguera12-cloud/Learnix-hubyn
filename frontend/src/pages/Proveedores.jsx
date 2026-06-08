import { useEffect, useState } from 'react'
import { supabase } from '../services/supabase'

export default function Proveedores() {
  const [todos,    setTodos]    = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    supabase.from('proveedores').select('*').order('nombre_comercial')
      .then(({ data, error }) => {
        if (error) setError(error.message)
        else setTodos(data ?? [])
        setLoading(false)
      })
  }, [])

  const filtrados = todos.filter(p =>
    p.nombre_comercial?.toLowerCase().includes(busqueda.toLowerCase()) ||
    p.nit?.includes(busqueda) ||
    p.dui?.includes(busqueda)
  )

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">🏢 Directorio de Proveedores</h2>
          <p className="text-sm text-slate-400 mt-0.5">{todos.length} proveedor(es) registrados</p>
        </div>
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
                  {['NIT', 'Nombre', 'NRC', 'Actividad'].map(h => (
                    <th key={h} className="table-head text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtrados.map((p, i) => (
                  <tr key={p.nit ?? i} className="hover:bg-surface-700/50 transition-colors">
                    <td className="table-cell font-mono text-xs text-slate-300">{p.nit}</td>
                    <td className="table-cell font-medium text-slate-100">{p.nombre_comercial}</td>
                    <td className="table-cell font-mono text-xs">{p.nrc || '—'}</td>
                    <td className="table-cell text-slate-400">{p.actividad || '—'}</td>
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
