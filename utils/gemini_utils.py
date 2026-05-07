"""
Gemini 1.5 Flash utility via REST API (no SDK dependency).
Verifies and corrects DTE extracted fields: fecha, nombre emisor, NIT emisor.
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
_TIMEOUT = 15  # seconds

# ─── Patterns for suspicious (metadata) names ────────────────────────────────
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


# ─── Decides whether Gemini verification is needed ───────────────────────────
def necesita_verificacion(campos: dict, nit_receptor: str) -> tuple[bool, list[str]]:
    """
    Returns (needs_gemini, [reasons]).
    Called before making an API request so we skip Gemini when everything looks fine.
    """
    razones = []
    if campos.get("nit_prov") and nit_receptor and \
            campos["nit_prov"] == nit_receptor:
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


# ─── Single-call Gemini verifier ─────────────────────────────────────────────
def verificar_compra_con_gemini(
    texto_pdf: str,
    campos: dict,          # {fecha, nit_prov, nom_prov}
    nit_receptor: str,
    nom_receptor: str,
) -> tuple[dict, list[str]]:
    """
    Calls Gemini once to verify and correct extracted DTE fields.
    Returns (corrected_fields_dict, list_of_human_readable_corrections).
    corrected_fields_dict contains only keys whose values changed.
    """
    api_key = _get_api_key()
    if not api_key:
        return {}, []

    fecha_in   = campos.get("fecha", "")
    nit_prov   = campos.get("nit_prov", "")
    nom_prov   = campos.get("nom_prov", "")

    prompt = f"""Eres un verificador de documentos tributarios electrónicos (DTE) de El Salvador.

RECEPTOR (comprador, cliente activo):
  NIT: {nit_receptor}
  Nombre: {nom_receptor}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision: "{fecha_in}"
  nit_emisor: "{nit_prov}"
  nombre_emisor: "{nom_prov}"

TEXTO DEL PDF (primeras líneas relevantes):
{texto_pdf[:3000]}

INSTRUCCIONES DE VERIFICACIÓN:
1. FECHA: La fecha de emisión del DTE debe estar en formato DD/MM/YYYY.
   Puede estar en una tabla "DIA MES AÑO" seguida de números, o como dd/mm/yyyy, o YYYY-MM-DD.
   Si el campo extraído es incorrecto o vacío, busca la fecha correcta en el texto.
2. NOMBRE EMISOR: El nombre del proveedor/emisor NO puede ser:
   - El mismo que el receptor ({nom_receptor})
   - Texto de metadata: "FECHA PROCESADO:", "MÓDULO DE FACTURACIÓN:", fechas, horas
   Si el nombre extraído es incorrecto o vacío, encuentra el nombre real del emisor en el texto.
3. NIT EMISOR: El NIT del emisor NO puede ser igual al del receptor ({nit_receptor}).
   Si es igual o está vacío, busca el NIT real del emisor en el texto del PDF.

Devuelve ÚNICAMENTE un objeto JSON válido con este formato exacto:
{{"fecha": "DD/MM/YYYY o null", "nit_prov": "solo dígitos o null", "nom_prov": "NOMBRE EN MAYÚSCULAS o null", "correcciones": ["descripción 1", "descripción 2"]}}

- Usa null (sin comillas) si el campo está correcto y no necesita cambio.
- "correcciones" debe listar solo los campos que cambiaste, con brevedad.
- Si todo está correcto, devuelve correcciones como lista vacía []."""

    try:
        resp = requests.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 250,
                },
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Strip markdown code fences if present
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
        raw = re.sub(r'\s*```$', '', raw)

        resultado = json.loads(raw)
        correcciones = [str(c) for c in resultado.get("correcciones", []) if c]
        campos_corr  = {}

        # Only accept fecha in DD/MM/YYYY format
        nueva_fecha = resultado.get("fecha")
        if nueva_fecha and str(nueva_fecha).lower() != "null":
            nueva_fecha = str(nueva_fecha).strip()
            if _PAT_DDMMYYYY.match(nueva_fecha) and nueva_fecha != fecha_in:
                campos_corr["fecha"] = nueva_fecha

        nuevo_nom = resultado.get("nom_prov")
        if nuevo_nom and str(nuevo_nom).lower() != "null":
            nuevo_nom = str(nuevo_nom).strip().upper()
            if nuevo_nom and nuevo_nom != nom_prov and \
                    not es_nombre_sospechoso(nuevo_nom) and \
                    3 <= len(nuevo_nom) <= 120:
                campos_corr["nom_prov"] = nuevo_nom

        nuevo_nit = resultado.get("nit_prov")
        if nuevo_nit and str(nuevo_nit).lower() != "null":
            nuevo_nit = re.sub(r'[^0-9]', '', str(nuevo_nit))
            if nuevo_nit and nuevo_nit != nit_prov and \
                    nuevo_nit != nit_receptor and \
                    len(nuevo_nit) in (9, 14):
                campos_corr["nit_prov"] = nuevo_nit

        return campos_corr, correcciones

    except Exception:
        return {}, []


def limpiar_cache_gemini() -> None:
    pass  # No cache needed; Gemini is called per-document when needed
