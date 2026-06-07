"""
Extractor de DTEs de Ventas.
Encapsula la lógica de pages/1_Extractor_DTE_Ventas.py sin dependencias de Streamlit.
"""
from typing import Any

# Reutiliza utilidades existentes (sin cambios)
from utils.pdf_utils import extraer_texto_pdf
from utils.ai_utils import procesar_dte_con_gemini
from utils.qa_utils import validar_ventas
from utils.constants import TIPOS_CONTRIBUYENTES, TIPOS_CONSUMIDOR, MAX_VALORES_LOOP_VENTAS


def extraer_ventas(pdf_bytes: bytes, declarante_id: str) -> dict[str, Any]:
    """
    Extrae registros de ventas a partir de los bytes de un PDF.

    Returns:
        {
            "registros": [...],
            "errores": [...],
            "metricas": {...}
        }
    """
    texto = extraer_texto_pdf(pdf_bytes)

    # Determinar tipo: contribuyentes (CCF) o consumidor final (FC)
    tipo = "contribuyentes" if _es_contribuyentes(texto) else "consumidor_final"

    registros_raw = procesar_dte_con_gemini(
        texto=texto,
        tipo_dte=tipo,
        max_registros=MAX_VALORES_LOOP_VENTAS,
        declarante_id=declarante_id,
    )

    registros_validos, errores = validar_ventas(registros_raw)

    return {
        "tipo": tipo,
        "registros": registros_validos,
        "errores": errores,
        "total_registros": len(registros_validos),
    }


def _es_contribuyentes(texto: str) -> bool:
    """Detecta si el DTE corresponde a ventas a contribuyentes (contiene NRC)."""
    return "NRC" in texto or "N.R.C" in texto
