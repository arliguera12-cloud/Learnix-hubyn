"""
Gemini 1.5 Flash utility for DTE field extraction fallback.
Used when regex-based extraction produces suspicious or empty results.
"""
import os
import re
import streamlit as st

try:
    import google.generativeai as genai
    _GENAI_OK = True
except ImportError:
    _GENAI_OK = False

# ─── In-process cache: nit/uuid → nombre ─────────────────────────────────────
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
        \d{2}[/\-]\d{2}[/\-]\d{4}   # date as name
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
    """Return True if the extracted name looks like metadata, not a real company name."""
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
    """Read Gemini key from Streamlit secrets → env var → session state."""
    try:
        return st.secrets["gemini"]["api_key"]
    except Exception:
        pass
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        return env_key
    return st.session_state.get("gemini_api_key", "")


def gemini_disponible() -> bool:
    return _GENAI_OK and bool(_get_api_key())


def extraer_nombre_con_gemini(
    texto_pdf: str,
    nit: str = "",
    tipo_doc: str = "compra",
) -> str:
    """
    Use Gemini 1.5 Flash to extract the supplier name from DTE text.
    Returns uppercase name or "" on failure/unavailability.
    """
    if not _GENAI_OK:
        return ""
    api_key = _get_api_key()
    if not api_key:
        return ""

    cache_key = nit or texto_pdf[:80]
    if cache_key in _nombre_cache:
        return _nombre_cache[cache_key]

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    seccion = tipo_doc  # "compra" → emisor = proveedor
    texto_recortado = texto_pdf[:3500]

    prompt = f"""Eres un extractor de datos de documentos tributarios electrónicos (DTE) de El Salvador.

Del siguiente texto extraído de un PDF, encuentra el nombre o razón social del EMISOR (quien emite/vende el documento).

Reglas estrictas:
- Devuelve ÚNICAMENTE el nombre empresarial, sin explicaciones
- El EMISOR está en la sección "EMISOR" o "DATOS DEL EMISOR"
- El nombre termina antes de NIT, NRC, GIRO, dirección, correo, teléfono
- Ejemplos válidos: "GUARDADO S.A DE C.V", "ALMACENES VIDRI S.A. DE C.V.", "GRANJA SAN DIEGO S.A. DE C.V"
- Si no puedes identificarlo con certeza, devuelve exactamente: DESCONOCIDO

Texto del PDF:
{texto_recortado}

Responde solo con el nombre del emisor (sin comillas, sin explicaciones):"""

    try:
        resp = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                max_output_tokens=80,
            ),
        )
        nombre = resp.text.strip().strip('"').strip("'")
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
