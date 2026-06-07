import { useEffect, useState } from 'react'
import { supabase } from '../services/supabase'

export default function Proveedores() {
  const [proveedores, setProveedores] = useState([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')

  useEffect(() => {
    async function cargar() {
      const { data, error } = await supabase
        .from('proveedores')
        .select('*')
        .order('nombre')
      if (!error) setProveedores(data ?? [])
      setLoading(false)
    }
    cargar()
  }, [])

  const filtrados = proveedores.filter(
    (p) =>
      p.nombre?.toLowerCase().includes(busqueda.toLowerCase()) ||
      p.nit?.includes(busqueda),
  )

  return (
    <div className="page">
      <h1>Directorio de Proveedores</h1>
      <input
        type="search"
        placeholder="Buscar por nombre o NIT…"
        value={busqueda}
        onChange={(e) => setBusqueda(e.target.value)}
      />
      {loading ? (
        <p>Cargando…</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>NIT</th>
              <th>Nombre</th>
              <th>DUI</th>
              <th>NRC</th>
              <th>Actividad</th>
            </tr>
          </thead>
          <tbody>
            {filtrados.map((p) => (
              <tr key={p.nit}>
                <td>{p.nit}</td>
                <td>{p.nombre}</td>
                <td>{p.dui}</td>
                <td>{p.nrc}</td>
                <td>{p.actividad}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
