import ExtractorPage from '../components/ExtractorPage'
import { procesarRetenciones } from '../services/api'

export default function Retenciones() {
  return (
    <ExtractorPage
      titulo="Extractor DTE — Retenciones"
      icono="✂️"
      descripcion="Extrae comprobantes de retención IVA 1% (DTE-07). Genera Anexo 7 — Casilla 162 para F-07."
      tipo="retenciones"
      apiFn={(file, dId, nombre) => procesarRetenciones(file, dId, nombre)}
    />
  )
}
