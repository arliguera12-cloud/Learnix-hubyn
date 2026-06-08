import ExtractorPage from '../components/ExtractorPage'
import { procesarCompras, procesarComprasLote } from '../services/api'

export default function Compras() {
  return (
    <ExtractorPage
      titulo="Extractor DTE — Compras"
      icono="📥"
      descripcion="Extrae CCF recibidos de proveedores (DTE-03, 05, 06, 11). Genera Anexo 3 para F-07."
      tipo="compras"
      apiFn={procesarCompras}
      loteApiFn={procesarComprasLote}
    />
  )
}
