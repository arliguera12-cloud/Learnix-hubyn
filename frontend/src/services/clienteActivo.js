/**
 * "Cliente activo" — el cliente sobre el que se están extrayendo DTEs.
 *
 * La app Streamlit original lo elegía una vez en el Dashboard y quedaba en
 * `st.session_state` para todos los extractores; acá no había equivalente y
 * cada extracción pedía tipear el NIT y el nombre a mano de nuevo. Se
 * persiste en localStorage: sobrevive a la navegación entre páginas igual
 * que el session_state de Streamlit sobrevivía entre sus páginas.
 */
import { useCallback, useState } from 'react'

const KEY = 'learnix_cliente_activo'

function leer() {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function useClienteActivo() {
  const [clienteActivo, setClienteActivoState] = useState(leer)

  const setClienteActivo = useCallback((cliente) => {
    setClienteActivoState(cliente)
    if (cliente) localStorage.setItem(KEY, JSON.stringify(cliente))
    else localStorage.removeItem(KEY)
  }, [])

  return { clienteActivo, setClienteActivo }
}
