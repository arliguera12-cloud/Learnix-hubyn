"""
Learnix Hub — Gemini 1.5 Flash utility (REST, no SDK).
Provides a universal DTE field verifier and backward-compatible helpers.
"""
import os
import re
import json
import logging
import requests
import streamlit as st

log = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)
_TIMEOUT = 20  # seconds

# Last error surfaced so the UI can display it
_ultimo_error: str = ""


# ─── API key & availability ───────────────────────────────────────────────────

def _get_api_key() -> str:
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


def gemini_ultimo_error() -> str:
    """Returns the last error message from a Gemini call (empty string = no error)."""
    return _ultimo_error


# ─── Shared name-quality helpers ─────────────────────────────────────────────

_SOSPECHOSO = re.compile(
    r"""^(?:
        FECHA\s+(?:Y\s+HORA|PROCESADO|DE\s+EMISION|EMISION)|
        M[OÓ]DULO\s+DE|
        MODELO\s+(?:DE\s+)?FACTURACI[OÓ]N|
        C[OÓ]DIGO\s+(?:DE\s+)?GENERACI[OÓ]N|
        NUMERO\s+DE\s+CONTROL|
        SELLO|TIPO\s+DE|
        RAZ[OÓ]N\s+SOCIAL\s*:|
        NIT\s*:|NRC\s*:|
        \d{2}[/\-]\d{2}[/\-]\d{4}
    )""",
    re.I | re.X,
)
_PAT_FECHA_STR = re.compile(r'\d{2}[/\-]\d{2}[/\-]\d{4}')
_PAT_HORA      = re.compile(r'\b\d{2}:\d{2}:\d{2}\b')
_PAT_META      = re.compile(r'\b(?:PROCESADO|MODELO\s+FACTURACI|GENERACI[OÓ]N\s*:)', re.I)
_PAT_DDMMYYYY  = re.compile(r'^\d{2}/\d{2}/20\d{2}$')


def es_nombre_sospechoso(nombre: str) -> bool:
    if not nombre:
        return False
    n = nombre.strip().upper()
    if _SOSPECHOSO.match(n):
        return True
    if _PAT_FECHA_STR.search(n) or _PAT_HORA.search(n) or _PAT_META.search(n):
        return True
    return False


# ─── Central HTTP call ────────────────────────────────────────────────────────

def _llamar_gemini(prompt: str, max_tokens: int = 350) -> dict | None:
    """
    Sends a single request to Gemini and returns the parsed JSON dict.
    Returns None on any failure and sets _ultimo_error with a human-readable
    description so the caller (and the UI) can display it.
    """
    global _ultimo_error
    api_key = _get_api_key()
    if not api_key:
        _ultimo_error = "API key de Gemini no configurada en secrets.toml."
        log.warning("Gemini: missing API key")
        return None

    try:
        resp = requests.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": max_tokens,
                },
            },
            timeout=_TIMEOUT,
        )

        if resp.status_code == 400:
            _ultimo_error = f"Gemini rechazó la solicitud (400): {resp.text[:200]}"
            log.error("Gemini 400: %s", resp.text[:500])
            return None
        if resp.status_code == 403:
            _ultimo_error = "API key inválida o sin permiso para usar Gemini (403)."
            log.error("Gemini 403")
            return None
        if resp.status_code == 429:
            _ultimo_error = "Cuota de Gemini agotada (429). Espera un momento e intenta de nuevo."
            log.warning("Gemini 429 quota")
            return None

        resp.raise_for_status()

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip markdown code fences if present
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
        raw = re.sub(r'\s*```$', '', raw)

        resultado = json.loads(raw)
        _ultimo_error = ""
        return resultado

    except requests.exceptions.Timeout:
        _ultimo_error = f"Timeout ({_TIMEOUT}s) al llamar a Gemini. Verifica tu conexión."
        log.warning("Gemini timeout")
        return None
    except requests.exceptions.ConnectionError:
        _ultimo_error = "Sin conexión a Internet para llamar a Gemini."
        log.warning("Gemini connection error")
        return None
    except json.JSONDecodeError as e:
        _ultimo_error = f"Gemini devolvió una respuesta no parseable: {e}"
        log.warning("Gemini JSON parse error: %s", e)
        return None
    except Exception as e:
        _ultimo_error = f"Error inesperado en Gemini: {e}"
        log.error("Gemini unexpected error", exc_info=True)
        return None


# ─── Type-specific prompt builders ───────────────────────────────────────────

def _prompt_ventas(
    texto_pdf: str,
    campos: dict,
    nit_emisor: str,
    nom_emisor: str,
) -> str:
    return f"""Eres un verificador de Documentos Tributarios Electrónicos (DTE) de El Salvador.

EMISOR (vendedor, quien emite el documento):
  NIT: {nit_emisor}
  Nombre: {nom_emisor}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision : "{campos.get('fecha', '')}"
  nit_receptor  : "{campos.get('nit_cli', '')}"
  dui_receptor  : "{campos.get('dui_cli', '')}"
  nombre_receptor: "{campos.get('nom_cli', '')}"

TEXTO DEL PDF (primeras líneas relevantes):
{texto_pdf[:3000]}

INSTRUCCIONES:
1. FECHA: formato DD/MM/YYYY. Busca en el texto si el campo está vacío o mal.
2. NOMBRE RECEPTOR: nombre del COMPRADOR/ADQUIRIENTE. NO puede ser el mismo que el emisor ({nom_emisor}).
   Si dice "SIN NOMBRE" o está vacío, busca el nombre real en el texto.
3. NIT/DUI RECEPTOR: identificador del comprador. NO puede ser igual al del emisor ({nit_emisor}).
   Si está incorrecto o vacío, busca en el texto.

Devuelve ÚNICAMENTE JSON válido:
{{"fecha": "DD/MM/YYYY o null", "nom_cli": "NOMBRE MAYÚSCULAS o null", "nit_cli": "14 dígitos o null", "dui_cli": "9 dígitos o null", "correcciones": ["descripción 1"]}}

- null = el campo ya es correcto y no necesita cambio.
- "correcciones" lista solo los campos que cambiaste.
- Si todo está correcto devuelve correcciones como []."""


def _prompt_compras(
    texto_pdf: str,
    campos: dict,
    nit_receptor: str,
    nom_receptor: str,
) -> str:
    return f"""Eres un verificador de Documentos Tributarios Electrónicos (DTE) de El Salvador.

RECEPTOR (comprador, cliente activo):
  NIT: {nit_receptor}
  Nombre: {nom_receptor}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision: "{campos.get('fecha', '')}"
  nit_emisor   : "{campos.get('nit_prov', '')}"
  nombre_emisor: "{campos.get('nom_prov', '')}"

TEXTO DEL PDF (primeras líneas relevantes):
{texto_pdf[:3000]}

INSTRUCCIONES DE VERIFICACIÓN:
1. FECHA: formato DD/MM/YYYY. Busca en el texto si el campo está vacío o mal.
2. NOMBRE EMISOR: el proveedor/vendedor. NO puede ser el receptor ({nom_receptor}) ni metadata.
3. NIT EMISOR: NO puede ser igual al del receptor ({nit_receptor}).

Devuelve ÚNICAMENTE JSON válido:
{{"fecha": "DD/MM/YYYY o null", "nit_prov": "solo dígitos o null", "nom_prov": "NOMBRE MAYÚSCULAS o null", "correcciones": ["descripción 1"]}}

- null = el campo ya es correcto.
- Si todo está correcto devuelve correcciones como []."""


def _prompt_retenciones(
    texto_pdf: str,
    campos: dict,
    nit_cliente: str,
    nom_cliente: str,
) -> str:
    return f"""Eres un verificador de Documentos Tributarios Electrónicos (DTE) de El Salvador.

AGENTE RETENEDOR (cliente activo que emite la retención):
  NIT: {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision : "{campos.get('fecha', '')}"
  nit_proveedor : "{campos.get('nit_prov', '')}"

TEXTO DEL PDF (primeras líneas relevantes):
{texto_pdf[:3000]}

INSTRUCCIONES:
1. FECHA: formato DD/MM/YYYY. Busca en el texto si está vacío o mal.
2. NIT PROVEEDOR: NIT del sujeto retenido. NO puede ser igual al del agente retenedor ({nit_cliente}).
   Si está vacío o incorrecto, busca el NIT del sujeto retenido en el texto.

Devuelve ÚNICAMENTE JSON válido:
{{"fecha": "DD/MM/YYYY o null", "nit_prov": "14 dígitos o null", "correcciones": ["descripción 1"]}}

- null = el campo ya es correcto.
- Si todo está correcto devuelve correcciones como []."""


def _prompt_sujetos_excluidos(
    texto_pdf: str,
    campos: dict,
    nit_cliente: str,
    nom_cliente: str,
) -> str:
    return f"""Eres un verificador de Documentos Tributarios Electrónicos (DTE) de El Salvador.

COMPRADOR (cliente activo que paga al sujeto excluido):
  NIT: {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision : "{campos.get('fecha', '')}"
  nit_sujeto    : "{campos.get('nit_sujeto', '')}"
  dui_sujeto    : "{campos.get('dui_sujeto', '')}"
  nombre_sujeto : "{campos.get('nom_sujeto', '')}"

TEXTO DEL PDF (primeras líneas relevantes):
{texto_pdf[:3000]}

INSTRUCCIONES:
1. FECHA: formato DD/MM/YYYY. Busca en el texto si está vacío o mal.
2. NOMBRE SUJETO EXCLUIDO: persona natural o jurídica que presta el servicio/vende.
   NO puede ser el mismo que el comprador ({nom_cliente}).
3. NIT/DUI SUJETO: identificador del sujeto excluido. NO puede ser igual a {nit_cliente}.

Devuelve ÚNICAMENTE JSON válido:
{{"fecha": "DD/MM/YYYY o null", "nom_sujeto": "NOMBRE MAYÚSCULAS o null", "nit_sujeto": "14 dígitos o null", "dui_sujeto": "9 dígitos o null", "correcciones": ["descripción 1"]}}

- null = el campo ya es correcto.
- Si todo está correcto devuelve correcciones como []."""


# ─── Field validator/extractor after Gemini response ─────────────────────────

def _validar_fecha(nueva: str | None, actual: str) -> str | None:
    if not nueva or str(nueva).lower() == "null":
        return None
    nueva = str(nueva).strip()
    if _PAT_DDMMYYYY.match(nueva) and nueva != actual:
        return nueva
    return None


def _validar_nombre(nuevo: str | None, actual: str, excluir_prefijo: str = "") -> str | None:
    if not nuevo or str(nuevo).lower() == "null":
        return None
    nuevo = str(nuevo).strip().upper()
    if (
        nuevo
        and nuevo != actual.upper()
        and not es_nombre_sospechoso(nuevo)
        and 3 <= len(nuevo) <= 120
        and (not excluir_prefijo or not nuevo.startswith(excluir_prefijo[:12]))
    ):
        return nuevo
    return None


def _validar_nit(nuevo: str | None, actual: str, excluir: set | None = None) -> str | None:
    if not nuevo or str(nuevo).lower() == "null":
        return None
    nuevo = re.sub(r'[^0-9]', '', str(nuevo))
    excluir = excluir or set()
    if nuevo and nuevo != actual and nuevo not in excluir and len(nuevo) in (9, 14):
        return nuevo
    return None


def _extraer_campos_corregidos(
    resultado: dict,
    campos_actuales: dict,
    tipo_dte: str,
    nit_contexto: str,
) -> dict:
    """Validates Gemini's response and returns only fields that actually changed."""
    campos_corr: dict = {}
    excluir = {nit_contexto} if nit_contexto else set()

    fecha_ok = _validar_fecha(resultado.get("fecha"), campos_actuales.get("fecha", ""))
    if fecha_ok:
        campos_corr["fecha"] = fecha_ok

    if tipo_dte == "ventas":
        nom = _validar_nombre(
            resultado.get("nom_cli"), campos_actuales.get("nom_cli", ""),
            excluir_prefijo=nit_contexto,
        )
        if nom:
            campos_corr["nom_cli"] = nom
        nit = _validar_nit(resultado.get("nit_cli"), campos_actuales.get("nit_cli", ""), excluir)
        if nit and len(nit) == 14:
            campos_corr["nit_cli"] = nit
        dui = _validar_nit(resultado.get("dui_cli"), campos_actuales.get("dui_cli", ""), excluir)
        if dui and len(dui) == 9:
            campos_corr["dui_cli"] = dui

    elif tipo_dte == "compras":
        nom = _validar_nombre(resultado.get("nom_prov"), campos_actuales.get("nom_prov", ""))
        if nom:
            campos_corr["nom_prov"] = nom
        nit = _validar_nit(resultado.get("nit_prov"), campos_actuales.get("nit_prov", ""), excluir)
        if nit and len(nit) == 14:
            campos_corr["nit_prov"] = nit

    elif tipo_dte == "retenciones":
        nit = _validar_nit(resultado.get("nit_prov"), campos_actuales.get("nit_prov", ""), excluir)
        if nit and len(nit) == 14:
            campos_corr["nit_prov"] = nit

    elif tipo_dte == "sujetos_excluidos":
        nom = _validar_nombre(resultado.get("nom_sujeto"), campos_actuales.get("nom_sujeto", ""))
        if nom:
            campos_corr["nom_sujeto"] = nom
        nit = _validar_nit(resultado.get("nit_sujeto"), campos_actuales.get("nit_sujeto", ""), excluir)
        if nit and len(nit) == 14:
            campos_corr["nit_sujeto"] = nit
        dui = _validar_nit(resultado.get("dui_sujeto"), campos_actuales.get("dui_sujeto", ""), excluir)
        if dui and len(dui) == 9:
            campos_corr["dui_sujeto"] = dui

    return campos_corr


# ─── Universal public function ────────────────────────────────────────────────

def procesar_dte_con_gemini(
    texto_pdf: str,
    tipo_dte: str,
    campos_actuales: dict,
    contexto_receptor: dict,
) -> tuple[dict, list[str]]:
    """
    Universal Gemini verifier for any DTE type.

    Args:
        texto_pdf       : Raw text extracted from the PDF.
        tipo_dte        : "ventas" | "compras" | "retenciones" | "sujetos_excluidos"
        campos_actuales : Fields already extracted by regex (may have errors).
                          Keys vary by tipo_dte — see prompt builders above.
        contexto_receptor: {"nit": "...", "nombre": "..."} — the active client.

    Returns:
        (corrected_fields_dict, corrections_list)
        corrected_fields_dict contains only the keys whose values changed.
        corrections_list contains human-readable descriptions of changes.
    """
    if not gemini_disponible():
        return {}, []

    nit_ctx = re.sub(r'[^0-9]', '', str(contexto_receptor.get("nit", "")))
    nom_ctx = str(contexto_receptor.get("nombre", "")).strip().upper()

    _prompt_builders = {
        "ventas"           : _prompt_ventas,
        "compras"          : _prompt_compras,
        "retenciones"      : _prompt_retenciones,
        "sujetos_excluidos": _prompt_sujetos_excluidos,
    }

    build_prompt = _prompt_builders.get(tipo_dte)
    if not build_prompt:
        log.warning("procesar_dte_con_gemini: tipo_dte desconocido '%s'", tipo_dte)
        return {}, []

    prompt    = build_prompt(texto_pdf, campos_actuales, nit_ctx, nom_ctx)
    resultado = _llamar_gemini(prompt)

    if resultado is None:
        return {}, []

    correcciones  = [str(c) for c in resultado.get("correcciones", []) if c]
    campos_corr   = _extraer_campos_corregidos(resultado, campos_actuales, tipo_dte, nit_ctx)
    return campos_corr, correcciones


# ─── Backward-compatible helpers (used by 2_Extractor_DTE_Compras.py) ────────

def necesita_verificacion(campos: dict, nit_receptor: str) -> tuple[bool, list[str]]:
    """
    Returns (needs_gemini, [reasons]).
    Skips Gemini when all extracted fields look correct.
    """
    razones = []
    if campos.get("nit_prov") and nit_receptor and campos["nit_prov"] == nit_receptor:
        razones.append("NIT del emisor coincide con el del receptor")
    if not campos.get("nom_prov", "").strip():
        razones.append("Nombre del emisor vacío")
    elif es_nombre_sospechoso(campos.get("nom_prov", "")):
        razones.append(f"Nombre extraído parece metadata: {campos['nom_prov'][:40]}")
    if not campos.get("fecha", "").strip():
        razones.append("Fecha de emisión no encontrada")
    if not campos.get("nit_prov", "").strip():
        razones.append("NIT del emisor no encontrado")
    return bool(razones), razones


def verificar_compra_con_gemini(
    texto_pdf: str,
    campos: dict,
    nit_receptor: str,
    nom_receptor: str,
) -> tuple[dict, list[str]]:
    """
    Backward-compatible wrapper — delegates to procesar_dte_con_gemini.
    Kept so 2_Extractor_DTE_Compras.py needs zero changes.
    """
    return procesar_dte_con_gemini(
        texto_pdf  = texto_pdf,
        tipo_dte   = "compras",
        campos_actuales   = campos,
        contexto_receptor = {"nit": nit_receptor, "nombre": nom_receptor},
    )


def limpiar_cache_gemini() -> None:
    pass  # No cache needed; Gemini is called per-document when needed
