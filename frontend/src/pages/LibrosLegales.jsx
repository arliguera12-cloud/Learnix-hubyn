import { useEffect, useMemo, useState } from 'react'
import { supabase } from '../services/supabase'
import ClienteSelector from '../components/ClienteSelector'
import { IconLibrosLegales, IconAlerta } from '../components/Icons'
import { fmt, descargarBlob } from '../utils/dte'

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

const LIBROS = [
  {
    key: 'compras',
    tabla: 'db_compras',
    titulo: 'Libro de Compras',
    filtro: null,
    columnas: [
      ['fecha', 'Fecha'], ['tipo', 'Tipo Doc'], ['num_control', 'N° Documento'],
      ['nit_prov', 'NIT/NRC Proveedor'], ['nom_prov', 'Nombre Proveedor'],
      ['exe', 'Exentas', 'money'], ['gra', 'Gravadas', 'money'],
      ['iva', 'IVA Crédito Fiscal', 'money'], ['tot', 'Total', 'money'],
    ],
    totalCampo: 'tot',
  },
  {
    key: 'ventas_contrib',
    tabla: 'db_ventas',
    titulo: 'Libro de Ventas — Contribuyentes',
    filtro: r => ['03', '05', '06'].includes(String(r.registro?.tipo)),
    columnas: [
      ['fecha', 'Fecha'], ['tipo', 'Tipo Doc'], ['num_control', 'N° Control'],
      ['nit_cli', 'NIT/NRC Cliente'], ['nom_cli', 'Nombre Cliente'],
      ['exentas', 'Exentas', 'money'], ['gravadas', 'Gravadas', 'money'],
      ['debito', 'IVA Débito Fiscal', 'money'], ['total', 'Total', 'money'],
    ],
    totalCampo: 'total',
  },
  {
    key: 'ventas_consumidor',
    tabla: 'db_ventas',
    titulo: 'Libro de Ventas — Consumidor Final',
    filtro: r => !['03', '05', '06'].includes(String(r.registro?.tipo)),
    columnas: [
      ['fecha', 'Fecha'], ['tipo', 'Tipo Doc'], ['num_control', 'N° Documento'],
      ['exentas', 'Exentas', 'money'], ['gravadas', 'Gravadas (c/IVA)', 'money'],
      ['total', 'Total', 'money'],
    ],
    totalCampo: 'total',
  },
]

function anioActual() { return new Date().getFullYear() }

export default function LibrosLegales() {
  const [libroKey,   setLibroKey]   = useState('compras')
  const [cliente,    setCliente]    = useState(null)
  const [anio,       setAnio]       = useState(anioActual())
  const [filas,      setFilas]      = useState([])
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState(null)

  const libro = LIBROS.find(l => l.key === libroKey)
  const anios = [anioActual(), anioActual() - 1, anioActual() - 2]

  useEffect(() => {
    if (!cliente) { setFilas([]); return }
    let cancelado = false

    async function cargar() {
      setLoading(true)
      setError(null)
      try {
        const { data: { user } } = await supabase.auth.getUser()
        if (!user) { setFilas([]); return }

        const { data, error: err } = await supabase
          .from(libro.tabla)
          .select('id, correlativo, fecha, periodo, registro')
          .eq('user_id', user.id)
          .eq('declarante_id', cliente.nit)
          .like('periodo', `${anio}-%`)
          .order('correlativo', { ascending: true })
          .limit(2000)

        if (err) throw err
        const filtradas = (data ?? []).filter(r => !libro.filtro || libro.filtro(r))
        if (!cancelado) setFilas(filtradas)
      } catch (err) {
        if (!cancelado) setError(err.message || 'No se pudo cargar el libro.')
      } finally {
        if (!cancelado) setLoading(false)
      }
    }

    cargar()
    return () => { cancelado = true }
  }, [cliente, anio, libroKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // Agrupa por mes (a partir de `periodo`, YYYY-MM) — un libro físico se
  // organiza en secciones mensuales con suma del mes y suma acumulada.
  const grupos = useMemo(() => {
    const porMes = {}
    for (const fila of filas) {
      const mes = fila.periodo?.split('-')[1] || '00'
      if (!porMes[mes]) porMes[mes] = []
      porMes[mes].push(fila)
    }
    let acumulado = 0
    return Object.entries(porMes)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([mes, items]) => {
        const suma = items.reduce((s, f) => s + parseFloat(f.registro?.[libro.totalCampo] || 0), 0)
        acumulado += suma
        return { mes: MESES[parseInt(mes, 10) - 1] || mes, items, suma, acumulado }
      })
  }, [filas, libro.totalCampo])

  const totalAnio = grupos.reduce((s, g) => s + g.suma, 0)

  function exportarCsv() {
    const cabecera = ['Correlativo', ...libro.columnas.map(([, label]) => label)]
    const lineas = [cabecera.join(';')]
    for (const grupo of grupos) {
      for (const fila of grupo.items) {
        const valores = [
          fila.correlativo ?? '',
          ...libro.columnas.map(([campo, , tipo]) => {
            const v = fila.registro?.[campo] ?? ''
            return tipo === 'money' ? fmt(v) : String(v).replace(/;/g, ',')
          }),
        ]
        lineas.push(valores.join(';'))
      }
    }
    descargarBlob(lineas.join('\n'), `${libro.titulo.replace(/\s+/g, '_')}_${cliente?.nit || 'cliente'}_${anio}.csv`)
  }

  return (
    <div className="max-w-[95rem] mx-auto space-y-5">
      <div>
        <h2 className="text-2xl text-fg flex items-center gap-2.5">
          <IconLibrosLegales className="w-6 h-6 text-accent" />
          Libros legales
        </h2>
        <p className="text-sm text-fg-4 mt-0.5">
          Registro correlativo y permanente por cliente y año — distinto del Anexo del F-07,
          que es el archivo de una sola subida para el portal de Hacienda.
        </p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {LIBROS.map(l => (
          <button
            key={l.key}
            type="button"
            onClick={() => setLibroKey(l.key)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              libroKey === l.key
                ? 'bg-accent/15 border-accent text-accent'
                : 'border-hairline text-fg-4 hover:text-fg-2'
            }`}
          >
            {l.titulo}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 items-end">
          <div>
            <label className="form-label">Cliente</label>
            {cliente ? (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-hairline bg-panel2/40 px-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-sm text-fg truncate">{cliente.nombre_comercial}</p>
                  <p className="text-xs text-fg-4 font-mono">{cliente.nit}</p>
                </div>
                <button type="button" onClick={() => setCliente(null)} className="btn-ghost text-xs shrink-0">
                  Cambiar
                </button>
              </div>
            ) : (
              <ClienteSelector onSeleccionar={setCliente} />
            )}
          </div>
          <div>
            <label className="form-label" htmlFor="libro-anio">Año</label>
            <select
              id="libro-anio"
              className="input"
              value={anio}
              onChange={e => setAnio(Number(e.target.value))}
            >
              {anios.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={exportarCsv}
              disabled={!cliente || !filas.length}
              className="btn-primary px-4 py-2 disabled:opacity-40"
            >
              Exportar CSV
            </button>
          </div>
        </div>
      </div>

      {error && (
        <p className="text-red-400 text-sm flex items-center gap-2">
          <IconAlerta className="w-4 h-4 shrink-0" /> {error}
        </p>
      )}

      {!cliente ? (
        <div className="card">
          <p className="text-center text-fg-4 text-sm py-6">
            Elegí un cliente para ver su {libro.titulo.toLowerCase()}.
          </p>
        </div>
      ) : loading ? (
        <div className="card">
          <p className="text-center text-fg-4 text-sm py-6">Cargando…</p>
        </div>
      ) : filas.length === 0 ? (
        <div className="card">
          <p className="text-center text-fg-4 text-sm py-6">
            Sin movimientos en {anio} para {cliente.nombre_comercial}.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {grupos.map(grupo => (
            <div key={grupo.mes} className="card p-0 overflow-hidden">
              <div className="px-4 py-2.5 bg-panel2/60 border-b border-hairline flex items-center justify-between">
                <p className="text-sm font-medium text-fg">{grupo.mes} {anio}</p>
                <p className="text-xs text-fg-4 font-mono">
                  {grupo.items.length} documento{grupo.items.length === 1 ? '' : 's'} ·
                  folios {grupo.items[0]?.correlativo ?? '—'}–{grupo.items[grupo.items.length - 1]?.correlativo ?? '—'}
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      <th className="table-head text-left">Folio</th>
                      {libro.columnas.map(([campo, label]) => (
                        <th key={campo} className="table-head text-left whitespace-nowrap">{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {grupo.items.map(fila => (
                      <tr key={fila.id} className="hover:bg-panel2/40 transition-colors">
                        <td className="table-cell font-mono text-fg-4">{fila.correlativo ?? '—'}</td>
                        {libro.columnas.map(([campo, , tipo]) => (
                          <td key={campo} className={`table-cell ${tipo === 'money' ? 'text-right font-mono' : ''}`}>
                            {tipo === 'money'
                              ? `$${fmt(fila.registro?.[campo])}`
                              : (fila.registro?.[campo] || '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-panel2/40 font-medium">
                      <td className="table-cell" colSpan={libro.columnas.length}>Suma del mes</td>
                      <td className="table-cell text-right font-mono">${fmt(grupo.suma)}</td>
                    </tr>
                    <tr className="text-fg-4">
                      <td className="table-cell" colSpan={libro.columnas.length}>Suma acumulada {anio}</td>
                      <td className="table-cell text-right font-mono">${fmt(grupo.acumulado)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          ))}

          <div className="card flex items-center justify-between">
            <p className="text-sm text-fg-2">Total {anio} — {filas.length} documentos</p>
            <p className="text-lg font-display text-fg tabular-nums">${fmt(totalAnio)}</p>
          </div>
        </div>
      )}
    </div>
  )
}
