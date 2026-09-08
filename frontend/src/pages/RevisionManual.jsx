import { useEffect, useMemo, useState } from 'react'
import { supabase } from '../services/supabase'
import { IconRevision, IconAlerta, IconCheck } from '../components/Icons'
import { nivelEstado, esAlerta } from '../utils/dte'

const TABLAS = {
  ventas:            'db_ventas',
  compras:           'db_compras',
  retenciones:       'db_retenciones',
  sujetos_excluidos: 'db_sujetos',
}

const TITULO_TIPO = {
  ventas:            'Ventas',
  compras:           'Compras',
  retenciones:       'Retenciones',
  sujetos_excluidos: 'Sujetos Excluidos',
}

// Campos que tiene sentido corregir a mano por tipo de extractor — los
// mismos nombres que usan los extractores del backend (ver CAMPOS_FINANCIEROS
// y CAMPOS_BUSQUEDA en components/ExtractorPage.jsx).
const CAMPOS_EDITABLES = {
  ventas: [
    ['nom_cli', 'Cliente', 'text'], ['nit_cli', 'NIT cliente', 'text'], ['dui_cli', 'DUI cliente', 'text'],
    ['fecha', 'Fecha (DD/MM/AAAA)', 'text'],
    ['exentas', 'Exentas', 'number'], ['no_sujetas', 'No sujetas', 'number'],
    ['gravadas', 'Gravadas', 'number'], ['debito', 'Débito fiscal', 'number'], ['total', 'Total', 'number'],
  ],
  compras: [
    ['nom_prov', 'Proveedor', 'text'], ['nit_prov', 'NIT proveedor', 'text'], ['dui_prov', 'DUI proveedor', 'text'],
    ['fecha', 'Fecha (DD/MM/AAAA)', 'text'],
    ['gra', 'Gravadas', 'number'], ['iva', 'IVA', 'number'], ['tot', 'Total', 'number'],
  ],
  retenciones: [
    ['nit_prov', 'NIT sujeto retenido', 'text'], ['dui_agente', 'DUI agente', 'text'],
    ['fecha', 'Fecha (DD/MM/AAAA)', 'text'],
    ['base', 'Base imponible', 'number'], ['ret', 'Retención', 'number'],
  ],
  sujetos_excluidos: [
    ['nom_sujeto', 'Sujeto excluido', 'text'], ['id_sujeto', 'NIT/DUI sujeto', 'text'],
    ['fecha', 'Fecha (DD/MM/AAAA)', 'text'],
    ['base', 'Base imponible', 'number'], ['ret', 'Retención', 'number'],
  ],
}

const NOMBRE_CAMPO = {
  ventas: 'nom_cli', compras: 'nom_prov', retenciones: 'nit_prov', sujetos_excluidos: 'nom_sujeto',
}

const FILTROS = [['todos', 'Todos'], ...Object.entries(TITULO_TIPO)]

export default function RevisionManual() {
  const [pendientes, setPendientes] = useState([])
  const [loading,     setLoading]   = useState(true)
  const [error,       setError]     = useState(null)
  const [filtro,      setFiltro]    = useState('todos')
  const [clienteFiltro, setClienteFiltro] = useState('todos') // declarante_id, o 'todos'
  const [seleccion,   setSeleccion] = useState(null) // fila elegida para corregir
  const [form,        setForm]      = useState({})
  const [guardando,   setGuardando] = useState(false)
  const [aviso,       setAviso]     = useState(null)

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) { setPendientes([]); setLoading(false); return }

      const resultados = await Promise.all(
        Object.entries(TABLAS).map(async ([tipo, tabla]) => {
          const { data, error: err } = await supabase
            .from(tabla)
            .select('id, declarante_id, filename, periodo, fecha, registro, created_at')
            .eq('user_id', user.id)
            .order('created_at', { ascending: false })
            .limit(500)
          if (err) throw err
          return (data ?? [])
            .filter(row => esAlerta(row.registro?.estado))
            .map(row => ({ ...row, tipo, tabla }))
        })
      )

      const todos = resultados.flat().sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
      setPendientes(todos)
    } catch (err) {
      setError(err.message || 'No se pudo cargar la lista de revisión manual.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { cargar() }, [])

  // Clientes presentes en la lista actual, con un nombre representativo —
  // para no mostrar "de todos" mezclado cuando alguien solo quiere ver los
  // de un cliente puntual.
  const clientesEnLista = useMemo(() => {
    const mapa = new Map()
    for (const p of pendientes) {
      if (!mapa.has(p.declarante_id)) {
        mapa.set(p.declarante_id, p.registro?.[NOMBRE_CAMPO[p.tipo]] || p.declarante_id)
      }
    }
    return [...mapa.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [pendientes])

  const filtrados = useMemo(() => {
    let lista = filtro === 'todos' ? pendientes : pendientes.filter(p => p.tipo === filtro)
    if (clienteFiltro !== 'todos') lista = lista.filter(p => p.declarante_id === clienteFiltro)
    return lista
  }, [pendientes, filtro, clienteFiltro])

  function elegir(fila) {
    setSeleccion(fila)
    setForm({ ...fila.registro })
    setAviso(null)
  }

  function cerrarEdicion() {
    setSeleccion(null)
    setForm({})
  }

  async function guardar(soloMarcarConforme = false) {
    if (!seleccion) return
    setGuardando(true)
    setAviso(null)

    const registroNuevo = {
      ...seleccion.registro,
      ...(soloMarcarConforme ? {} : form),
      estado: 'OK (revisado manualmente)',
      revisado_manualmente: true,
      revisado_en: new Date().toISOString(),
    }

    const { error: err } = await supabase
      .from(seleccion.tabla)
      .update({ registro: registroNuevo })
      .eq('id', seleccion.id)

    setGuardando(false)

    if (err) {
      setAviso({ tipo: 'error', texto: err.message })
      return
    }

    setPendientes(prev => prev.filter(p => p.id !== seleccion.id))
    cerrarEdicion()
    setAviso({ tipo: 'ok', texto: 'Documento corregido y marcado como conforme.' })
  }

  const camposTipo = seleccion ? CAMPOS_EDITABLES[seleccion.tipo] : []

  return (
    <div className="max-w-[90rem] mx-auto space-y-5">
      <div>
        <h2 className="text-2xl text-fg flex items-center gap-2.5">
          <IconRevision className="w-6 h-6 text-accent" />
          Revisión manual
        </h2>
        <p className="text-sm text-fg-4 mt-0.5">
          Documentos que la extracción marcó como &ldquo;Revisar&rdquo; o &ldquo;Revisión manual&rdquo; —
          corregí los datos y quedan conformes para el anexo.
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

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="flex items-center gap-3 flex-wrap justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {FILTROS.map(([key, label]) => {
            const count = key === 'todos' ? pendientes.length : pendientes.filter(p => p.tipo === key).length
            return (
              <button
                key={key}
                type="button"
                onClick={() => setFiltro(key)}
                className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                  filtro === key
                    ? 'bg-accent/15 border-accent text-accent'
                    : 'border-hairline text-fg-4 hover:text-fg-2'
                }`}
              >
                {label} ({count})
              </button>
            )
          })}
        </div>

        {clientesEnLista.length > 1 && (
          <select
            className="input w-auto max-w-[16rem] text-xs py-1.5"
            value={clienteFiltro}
            onChange={e => setClienteFiltro(e.target.value)}
          >
            <option value="todos">Todos los clientes ({pendientes.length})</option>
            {clientesEnLista.map(([nit, nombre]) => (
              <option key={nit} value={nit}>{nombre}</option>
            ))}
          </select>
        )}
      </div>

      <div className="card p-0 overflow-hidden">
        {loading ? (
          <p className="p-6 text-center text-fg-4 text-sm">Cargando…</p>
        ) : filtrados.length === 0 ? (
          <p className="p-6 text-center text-fg-4 text-sm flex items-center justify-center gap-2">
            <IconCheck className="w-4 h-4 text-accent2" />
            Sin documentos pendientes de revisión.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  {['Tipo', 'Nombre/ID', 'Fecha', 'Motivo', 'Archivo', ''].map(h => (
                    <th key={h} className="table-head text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtrados.map(row => {
                  const d = row.registro || {}
                  const nivel = nivelEstado(d.estado)
                  const motivo = d.detalle_confianza
                    || (d.campos_faltantes?.length ? `Faltan: ${d.campos_faltantes.join(', ')}` : d.estado || '—')
                  return (
                    <tr
                      key={`${row.tabla}:${row.id}`}
                      className={`hover:bg-panel2/50 transition-colors cursor-pointer ${
                        seleccion?.id === row.id ? 'bg-panel2/60' : ''
                      }`}
                      onClick={() => elegir(row)}
                    >
                      <td className="table-cell text-xs">{TITULO_TIPO[row.tipo]}</td>
                      <td className="table-cell max-w-[180px] truncate" title={d[NOMBRE_CAMPO[row.tipo]]}>
                        {d[NOMBRE_CAMPO[row.tipo]] || 'SIN NOMBRE'}
                      </td>
                      <td className="table-cell text-xs font-mono">{d.fecha || row.fecha || '—'}</td>
                      <td className="table-cell text-xs text-fg-4 max-w-[260px] truncate" title={motivo}>
                        <span className={nivel === 'manual' ? 'text-red-400' : 'text-amber-400'}>●</span>{' '}
                        {motivo}
                      </td>
                      <td className="table-cell text-xs text-fg-5 max-w-[140px] truncate" title={row.filename}>
                        {row.filename || '—'}
                      </td>
                      <td className="table-cell text-right">
                        <button type="button" className="btn-ghost text-xs px-2 py-1" onClick={() => elegir(row)}>
                          Corregir
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Panel de corrección */}
      {seleccion && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="form-label mb-0.5">
                Corrigiendo — {TITULO_TIPO[seleccion.tipo]}
              </p>
              <p className="text-xs text-fg-4">
                {seleccion.filename || 'Sin archivo'} · Declarante {seleccion.declarante_id}
              </p>
            </div>
            <button type="button" onClick={cerrarEdicion} className="btn-ghost text-xs px-3 py-1.5 text-fg-4">
              Cerrar
            </button>
          </div>

          {seleccion.registro?.detalle_confianza && (
            <p className="text-xs text-amber-400 flex items-start gap-1.5">
              <IconAlerta className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              {seleccion.registro.detalle_confianza}
            </p>
          )}

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {camposTipo.map(([campo, label, tipoInput]) => (
              <div key={campo}>
                <label className="form-label" htmlFor={`campo-${campo}`}>{label}</label>
                <input
                  id={`campo-${campo}`}
                  className="input"
                  type={tipoInput === 'number' ? 'text' : 'text'}
                  inputMode={tipoInput === 'number' ? 'decimal' : 'text'}
                  value={form[campo] ?? ''}
                  onChange={e => setForm(f => ({ ...f, [campo]: e.target.value }))}
                />
              </div>
            ))}
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-hairline">
            <button
              type="button"
              onClick={() => guardar(true)}
              disabled={guardando}
              className="btn-ghost text-xs px-3 py-2 border border-hairline"
              title="Los datos extraídos están correctos tal como están, solo confirmar"
            >
              Marcar conforme sin cambios
            </button>
            <button
              type="button"
              onClick={() => guardar(false)}
              disabled={guardando}
              className="btn-primary px-5 py-2"
            >
              {guardando ? 'Guardando…' : 'Guardar corrección'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
