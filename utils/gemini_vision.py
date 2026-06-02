"""
gemini_vision.py — Stub de compatibilidad.

El módulo de visión multimodal (PDF → imagen → IA) requería Gemini Vision,
que no está disponible en Groq/llama3-8b-8192 (modelo de texto únicamente).

La ruta de extracción principal sigue siendo pdfplumber + regex.
Groq se usa como corrector de campos vía gemini_utils.py.
"""
from __future__ import annotations


def vision_disponible() -> bool:
    """Siempre False — llama3-8b-8192 no soporta visión multimodal."""
    return False


def vision_ultimo_error() -> str:
    return ""


def extraer_dte_con_vision(
    pdf_bytes: bytes,
    tipo_dte: str = "compras",
    nombre_archivo: str = "",
) -> tuple[dict, list[str], dict]:
    """
    Stub — devuelve vacío para que la ruta de visión se omita
    y el extractor continúe con pdfplumber + regex + Groq.
    """
    return {}, [], {}
