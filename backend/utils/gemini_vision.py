"""
gemini_vision.py — Capa de visión IA para DTEs.

Delega en utils.ai_utils, que implementa la extracción por imagen con el modelo
de visión de Groq (Llama-4 Scout). Se mantiene este módulo como punto de entrada
estable para los extractores (firma histórica intacta).
"""
from __future__ import annotations

from utils.ai_utils import (
    extraer_dte_con_vision as _extraer_dte_con_vision,
    vision_disponible as _vision_disponible,
    vision_ultimo_error as _vision_ultimo_error,
)


def vision_disponible() -> bool:
    return _vision_disponible()


def vision_ultimo_error() -> str:
    return _vision_ultimo_error()


def extraer_dte_con_vision(
    pdf_bytes: bytes,
    tipo_dte: str = "compras",
    contexto_receptor: dict | None = None,
) -> tuple[dict, list[str], dict]:
    return _extraer_dte_con_vision(pdf_bytes, tipo_dte, contexto_receptor)
