"""
Extractor de DTEs de Sujetos Excluidos (casilla 66 / retención renta 10%).
Encapsula la lógica de pages/4_Extractor_DTE_Sujetos_Excluidos.py sin dependencias de Streamlit.
"""
from typing import Any

from utils.pdf_utils import extraer_texto_pdf
from utils.ai_utils import procesar_dte_con_gemini
from utils.qa_utils import validar_sujetos_excluidos


def extraer_sujetos_excluidos(pdf_bytes: bytes, declarante_id: str) -> dict[str, Any]:
    """Extrae registros de sujetos excluidos a partir de los bytes de un PDF."""
    texto = extraer_texto_pdf(pdf_bytes)

    registros_raw = procesar_dte_con_gemini(
        texto=texto,
        tipo_dte="sujetos_excluidos",
        declarante_id=declarante_id,
    )

    registros_validos, errores = validar_sujetos_excluidos(registros_raw)

    return {
        "tipo": "sujetos_excluidos",
        "registros": registros_validos,
        "errores": errores,
        "total_registros": len(registros_validos),
    }
