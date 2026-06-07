export default function ResultadosTabla({ data }) {
  const { registros = [], errores = [], total_registros, tipo } = data

  if (!registros.length && !errores.length) {
    return <p>No se encontraron registros en el PDF.</p>
  }

  const columnas = registros.length > 0 ? Object.keys(registros[0]) : []

  return (
    <div className="resultados">
      <p>
        Tipo: <strong>{tipo}</strong> — {total_registros} registro(s) extraídos
        {errores.length > 0 && `, ${errores.length} con errores de validación`}
      </p>

      {registros.length > 0 && (
        <div className="tabla-scroll">
          <table>
            <thead>
              <tr>
                {columnas.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {registros.map((row, i) => (
                <tr key={i}>
                  {columnas.map((col) => (
                    <td key={col}>{row[col] ?? ''}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {errores.length > 0 && (
        <details>
          <summary>Ver errores de validación ({errores.length})</summary>
          <ul>
            {errores.map((e, i) => (
              <li key={i}>{typeof e === 'string' ? e : JSON.stringify(e)}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
