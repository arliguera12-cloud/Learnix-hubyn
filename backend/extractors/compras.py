"""
Extractor de DTEs de Compras.
Encapsula la lógica de pages/2_Extractor_DTE_Compras.py sin dependencias de Streamlit.
"""
from typing import Any

from utils.pdf_utils import extraer_texto_pdf
from utils.ai_utils import procesar_dte_con_gemini
from utils.qa_utils import validar_compras
from utils.constants import TIPOS_VALIDOS_COMPRAS, MAX_VALORES_LOOP_COMPRAS


def extraer_compras(pdf_bytes: bytes, declarante_id: str) -> dict[str, Any]:
    """Extrae registros de compras a partir de los bytes de un PDF."""
    texto = extraer_texto_pdf(pdf_bytes)

    registros_raw = procesar_dte_con_gemini(
        texto=texto,
        tipo_dte="compras",
        max_registros=MAX_VALORES_LOOP_COMPRAS,
        declarante_id=declarante_id,
    )

    registros_validos, errores = validar_compras(registros_raw)

    return {
        "tipo": "compras",
        "registros": registros_validos,
        "errores": errores,
        "total_registros": len(registros_validos),
    }
