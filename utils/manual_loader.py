"""
utils/manual_loader.py — Carga manuales Hacienda como contexto para Gemini.

Soporta dos modos automáticos (prioridad en orden):
  1. Files API  — URIs en st.secrets["manuales"] (se necesita re-subir cada 48h)
  2. Disco      — PDFs en data/manuales/<key>.pdf commiteados al repo (sin expiración)

Si ninguno está disponible, las funciones devuelven [] y la extracción funciona
exactamente como antes (degradación elegante).
"""
from __future__ import annotations

import base64
import logging
import os

import streamlit as st

log = logging.getLogger(__name__)

_DIR_MANUALES = os.path.join("data", "manuales")

# ─── Claves de los 7 manuales ─────────────────────────────────────────────────

MANUAL_KEYS: list[str] = [
    "ventas_contribuyentes",      # DTE 03, 05, 06 — ventas a contribuyentes
    "ventas_consumidor",          # DTE 01 — ventas a consumidor final
    "compras_contribuyentes",     # DTE 03, 05, 06 — módulo compras
    "retencion_1pct",             # DTE 07 — comprobante de retención 1%
    "percepcion_1pct",            # Anexo 8 — percepciones
    "compras_sujetos_excluidos",  # DTE 14 — sujetos excluidos (casilla 66)
    "f14_retenciones",            # F-14 retenciones
]

# ─── Mapeos tipo_dte → keys de manual por contexto ───────────────────────────

_VENTAS_MAP: dict[str, list[str]] = {
    "01": ["ventas_consumidor"],
    "03": ["ventas_contribuyentes"],
    "05": ["ventas_contribuyentes"],
    "06": ["ventas_contribuyentes"],
    "11": ["ventas_contribuyentes"],
}

_COMPRAS_MAP: dict[str, list[str]] = {
    "03": ["compras_contribuyentes"],
    "05": ["compras_contribuyentes"],
    "06": ["compras_contribuyentes"],
    "11": ["compras_contribuyentes"],
    "14": ["compras_sujetos_excluidos"],
}

_RETENCIONES_KEYS: list[str] = ["retencion_1pct", "f14_retenciones"]


# ─── Modo 1: Files API (URIs desde secrets) ───────────────────────────────────

def _cargar_uris() -> dict[str, str]:
    """Lee URIs desde st.secrets["manuales"], cacheado en session_state."""
    cache_key = "_manuales_uris"
    cached = st.session_state.get(cache_key)
    if cached is not None:
        return cached
    try:
        seccion = st.secrets.get("manuales", {})
        uris = {k: str(v) for k, v in seccion.items() if k in MANUAL_KEYS and v}
        st.session_state[cache_key] = uris
        if uris:
            log.debug("manual_loader (Files API): %d URIs cargadas", len(uris))
        return uris
    except Exception as exc:
        log.debug("manual_loader: sin secrets (%s)", exc)
        st.session_state[cache_key] = {}
        return {}


def _uris_a_parts(uris: dict[str, str], keys: list[str]) -> list[dict]:
    return [
        {"fileData": {"mimeType": "application/pdf", "fileUri": uris[k]}}
        for k in keys
        if k in uris
    ]


# ─── Modo 2: Inline desde disco ──────────────────────────────────────────────

def _cargar_bytes_disco() -> dict[str, bytes]:
    """
    Lee los PDFs de data/manuales/ y los cachea en session_state.
    Solo carga los archivos que existan — los faltantes se ignoran.
    """
    cache_key = "_manuales_bytes"
    cached = st.session_state.get(cache_key)
    if cached is not None:
        return cached

    result: dict[str, bytes] = {}
    for key in MANUAL_KEYS:
        path = os.path.join(_DIR_MANUALES, f"{key}.pdf")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    result[key] = f.read()
                log.debug("manual_loader (disco): %s cargado (%d KB)", key, len(result[key]) // 1024)
            except Exception as exc:
                log.warning("manual_loader: no se pudo leer %s: %s", path, exc)

    st.session_state[cache_key] = result
    if result:
        log.info("manual_loader (disco): %d manuales en memoria", len(result))
    return result


def _bytes_a_parts(manuales_bytes: dict[str, bytes], keys: list[str]) -> list[dict]:
    return [
        {
            "inlineData": {
                "mimeType": "application/pdf",
                "data"    : base64.b64encode(manuales_bytes[k]).decode(),
            }
        }
        for k in keys
        if k in manuales_bytes
    ]


# ─── Función unificada: elige modo automáticamente ───────────────────────────

def _obtener_parts(keys: list[str]) -> list[dict]:
    """
    Devuelve los parts de Gemini para las claves dadas.
    Intenta Files API primero; cae a disco si no hay URIs; devuelve [] si nada.
    """
    if not keys:
        return []

    # Modo 1 — Files API
    uris = _cargar_uris()
    parts_uri = _uris_a_parts(uris, keys)
    if parts_uri:
        return parts_uri

    # Modo 2 — Inline desde disco
    manuales_bytes = _cargar_bytes_disco()
    parts_inline = _bytes_a_parts(manuales_bytes, keys)
    if parts_inline:
        return parts_inline

    return []


# ─── API pública ──────────────────────────────────────────────────────────────

def obtener_file_parts_ventas(tipo_dte: str) -> list[dict]:
    """Parts del manual para extracción en módulo VENTAS."""
    return _obtener_parts(_VENTAS_MAP.get(tipo_dte, []))


def obtener_file_parts_compras(tipo_dte: str) -> list[dict]:
    """Parts del manual para extracción en módulo COMPRAS."""
    return _obtener_parts(_COMPRAS_MAP.get(tipo_dte, []))


def obtener_file_parts_retenciones() -> list[dict]:
    """Parts de manuales para módulo RETENCIONES (retencion_1pct + f14)."""
    return _obtener_parts(_RETENCIONES_KEYS)


def manuales_disponibles() -> dict[str, str]:
    """
    Retorna un dict con los manuales disponibles y su fuente.
    Útil para mostrar estado en la UI: {"ventas_contribuyentes": "disco", ...}
    """
    estado: dict[str, str] = {}
    uris = _cargar_uris()
    bytes_disco = _cargar_bytes_disco()
    for key in MANUAL_KEYS:
        if key in uris:
            estado[key] = "files_api"
        elif key in bytes_disco:
            estado[key] = "disco"
    return estado
