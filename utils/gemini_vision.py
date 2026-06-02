"""
gemini_vision.py — Stub: visión IA no disponible, extracción por pdfplumber + regex.
"""
from __future__ import annotations


def vision_disponible() -> bool:
    return False


def vision_ultimo_error() -> str:
    return ""


def extraer_dte_con_vision(
    pdf_bytes: bytes,
    tipo_dte: str = "compras",
    nombre_archivo: str = "",
) -> tuple[dict, list[str], dict]:
    return {}, [], {}
