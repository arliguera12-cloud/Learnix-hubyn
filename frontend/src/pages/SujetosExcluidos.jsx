import ExtractorPage from '../components/ExtractorPage'
import { procesarSujetosExcluidos, procesarSujetosExcluidosLote } from '../services/api'

export default function SujetosExcluidos() {
  return (
    <ExtractorPage
      titulo="Extractor DTE — Sujetos Excluidos"
      icono="📋"
      descripcion="Extrae comprobantes de sujetos excluidos con retención renta 10% (DTE-14). Genera Anexo 5 — Casilla 66 para F-07."
      tipo="sujetos_excluidos"
      apiFn={procesarSujetosExcluidos}
      loteApiFn={procesarSujetosExcluidosLote}
    />
  )
}
