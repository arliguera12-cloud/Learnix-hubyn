"""
Extractor de DTEs de Retenciones (casilla 162 / 1%).
Encapsula la lógica de pages/3_Extractor_DTE_retenciones.py sin dependencias de Streamlit.
"""
from typing import Any

from utils.pdf_utils import extraer_texto_pdf
from utils.ai_utils import procesar_dte_con_gemini
from utils.qa_utils import validar_retenciones


def extraer_retenciones(pdf_bytes: bytes, declarante_id: str) -> dict[str, Any]:
    """Extrae registros de retenciones a partir de los bytes de un PDF."""
    texto = extraer_texto_pdf(pdf_bytes)

    registros_raw = procesar_dte_con_gemini(
        texto=texto,
        tipo_dte="retenciones",
        declarante_id=declarante_id,
    )

    registros_validos, errores = validar_retenciones(registros_raw)

    return {
        "tipo": "retenciones",
        "registros": registros_validos,
        "errores": errores,
        "total_registros": len(registros_validos),
    }
