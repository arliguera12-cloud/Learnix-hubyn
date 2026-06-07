import { useEffect, useState } from 'react'
import { supabase } from '../services/supabase'

export default function Clientes() {
  const [clientes, setClientes] = useState([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')

  useEffect(() => {
    async function cargar() {
      const { data, error } = await supabase
        .from('clientes')
        .select('*')
        .order('nombre')
      if (!error) setClientes(data ?? [])
      setLoading(false)
    }
    cargar()
  }, [])

  const filtrados = clientes.filter(
    (c) =>
      c.nombre?.toLowerCase().includes(busqueda.toLowerCase()) ||
      c.nit?.includes(busqueda),
  )

  return (
    <div className="page">
      <h1>Directorio de Clientes</h1>
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
            {filtrados.map((c) => (
              <tr key={c.nit}>
                <td>{c.nit}</td>
                <td>{c.nombre}</td>
                <td>{c.dui}</td>
                <td>{c.nrc}</td>
                <td>{c.actividad}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
