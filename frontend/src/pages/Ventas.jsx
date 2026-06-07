import ExtractorPage from '../components/ExtractorPage'
import { procesarVentas } from '../services/api'

export default function Ventas() {
  return (
    <ExtractorPage
      titulo="Extractor DTE — Ventas"
      icono="📤"
      descripcion="Extrae CCF, Notas de Crédito/Débito (DTE-03, 05, 06) y Facturas Consumidor Final (DTE-01). Genera Anexos 1 y 2 para F-07."
      tipo="ventas"
      apiFn={(file, dId, nombre) => procesarVentas(file, dId, nombre)}
    />
  )
}
