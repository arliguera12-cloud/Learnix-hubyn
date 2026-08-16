import ExtractorPage from '../components/ExtractorPage'
import { procesarRetenciones, procesarRetencionesLote } from '../services/api'
import { IconRetenciones } from '../components/Icons'

export default function Retenciones() {
  return (
    <ExtractorPage
      titulo="Extractor DTE — Retenciones"
      Icon={IconRetenciones}
      descripcion="Extrae comprobantes de retención IVA 1% (DTE-07). Genera Anexo 7 — Casilla 162 para F-07."
      tipo="retenciones"
      apiFn={procesarRetenciones}
      loteApiFn={procesarRetencionesLote}
    />
  )
}
