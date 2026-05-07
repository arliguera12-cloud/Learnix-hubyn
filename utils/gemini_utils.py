"""
Gemini 1.5 Flash utility via REST API (no SDK dependency).
Used as fallback when regex-based name extraction produces suspicious results.
"""
import os
import re
import json
import requests
import streamlit as st

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)
_TIMEOUT = 12  # seconds

# ─── In-process cache: nit → nombre ──────────────────────────────────────────
_nombre_cache: dict[str, str] = {}

# ─── Patterns that indicate a bad supplier name ───────────────────────────────
_SOSPECHOSO = re.compile(
    r"""^(?:
        FECHA\s+(?:Y\s+HORA|PROCESADO|DE\s+EMISION|EMISION)|
        M[OÓ]DULO\s+DE|
        MODELO\s+(?:DE\s+)?FACTURACI[OÓ]N|
        C[OÓ]DIGO\s+(?:DE\s+)?GENERACI[OÓ]N|
        NUMERO\s+DE\s+CONTROL|
        SELLO|
        TIPO\s+DE|
        RAZ[OÓ]N\s+SOCIAL\s*:|
        NIT\s*:|
        NRC\s*:|
        \d{2}[/\-]\d{2}[/\-]\d{4}
    )""",
    re.I | re.X,
)
_PATRON_FECHA = re.compile(r'\d{2}[/\-]\d{2}[/\-]\d{4}')
_PATRON_HORA  = re.compile(r'\b\d{2}:\d{2}:\d{2}\b')
_PATRON_META  = re.compile(
    r'\b(?:PROCESADO|MODELO\s+FACTURACI|GENERACI[OÓ]N\s*:)',
    re.I,
)


def es_nombre_sospechoso(nombre: str) -> bool:
    """Return True if the extracted name looks like metadata, not a company name."""
    if not nombre:
        return False
    n = nombre.strip().upper()
    if _SOSPECHOSO.match(n):
        return True
    if _PATRON_FECHA.search(n):
        return True
    if _PATRON_HORA.search(n):
        return True
    if _PATRON_META.search(n):
        return True
    return False


def _get_api_key() -> str:
    """Read Gemini key: Streamlit secrets → env var → session state."""
    try:
        return st.secrets["gemini"]["api_key"]
    except Exception:
        pass
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        return env_key
    return st.session_state.get("gemini_api_key", "")


def gemini_disponible() -> bool:
    return bool(_get_api_key())


def extraer_nombre_con_gemini(
    texto_pdf: str,
    nit: str = "",
) -> str:
    """
    Call Gemini 1.5 Flash REST API to extract the supplier (emisor) name.
    Returns uppercase name or "" on failure/unavailability.
    """
    api_key = _get_api_key()
    if not api_key:
        return ""

    cache_key = nit or texto_pdf[:80]
    if cache_key in _nombre_cache:
        return _nombre_cache[cache_key]

    texto_recortado = texto_pdf[:3500]

    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "Eres un extractor de datos de documentos tributarios electrónicos "
                    "(DTE) de El Salvador.\n\n"
                    "Del siguiente texto extraído de un PDF, encuentra el nombre o razón "
                    "social del EMISOR (quien emite/vende el documento).\n\n"
                    "Reglas estrictas:\n"
                    "- Devuelve ÚNICAMENTE el nombre empresarial, sin explicaciones\n"
                    "- El EMISOR está en la sección 'EMISOR' o 'DATOS DEL EMISOR'\n"
                    "- El nombre termina antes de NIT, NRC, GIRO, dirección, correo, teléfono\n"
                    "- Ejemplos válidos: 'GUARDADO S.A DE C.V', 'PRICESMART EL SALVADOR S.A. DE C.V.'\n"
                    "- Si no puedes identificarlo con certeza, responde: DESCONOCIDO\n\n"
                    f"Texto del PDF:\n{texto_recortado}\n\n"
                    "Responde solo con el nombre del emisor (sin comillas, sin explicaciones):"
                )
            }]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 80,
        },
    }

    try:
        resp = requests.post(
            _GEMINI_URL,
            params={"key": api_key},
            json=payload,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        nombre = (
            data["candidates"][0]["content"]["parts"][0]["text"]
            .strip().strip('"').strip("'")
        )
        if nombre.upper() in ("DESCONOCIDO", "NO ENCONTRADO", "N/A", ""):
            nombre = ""
        if nombre and (len(nombre) < 3 or len(nombre) > 120):
            nombre = ""
        nombre = nombre.upper() if nombre else ""
        if nombre:
            _nombre_cache[cache_key] = nombre
        return nombre
    except Exception:
        return ""


def limpiar_cache_gemini() -> None:
    _nombre_cache.clear()
