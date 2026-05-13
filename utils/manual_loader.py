"""
utils/manual_loader.py — Carga URIs de manuales Hacienda desde st.secrets.

Cada URI apunta a un archivo subido a Gemini Files API (válido 48h).
El mapeo tipo_dte → [uri, ...] se usa en gemini_vision.py para incluir
el manual como contexto en cada llamada de extracción.
"""
import logging

import streamlit as st

log = logging.getLogger(__name__)

# ─── Claves de los 7 manuales ─────────────────────────────────────────────────

MANUAL_KEYS: list[str] = [
    "ventas_contribuyentes",     # DTE 03, 05, 06 — ventas a contribuyentes
    "ventas_consumidor",         # DTE 01 — ventas a consumidor final
    "compras_contribuyentes",    # DTE 03, 05, 06 — módulo compras
    "retencion_1pct",            # DTE 07 — comprobante de retención 1%
    "percepcion_1pct",           # Anexo 8 — percepciones
    "compras_sujetos_excluidos", # DTE 14 — sujetos excluidos (casilla 66)
    "f14_retenciones",           # F-14 retenciones
]

# ─── Mapeo tipo_dte (string de 2 dígitos) → lista de claves de manual ─────────
#
# Tipos 03/05/06 aparecen tanto en ventas como en compras;
# las funciones obtener_file_parts_ventas / obtener_file_parts_compras
# usan subconjuntos distintos de este mapeo según el contexto.

_TIPO_A_MANUALES: dict[str, list[str]] = {
    "01": ["ventas_consumidor"],
    "03": ["ventas_contribuyentes", "compras_contribuyentes"],
    "05": ["ventas_contribuyentes", "compras_contribuyentes"],
    "06": ["ventas_contribuyentes", "compras_contribuyentes"],
    "07": ["retencion_1pct"],
    "11": ["ventas_contribuyentes"],
    "14": ["compras_sujetos_excluidos"],
}


# ─── Carga y caché de URIs ────────────────────────────────────────────────────

def cargar_uris_manuales() -> dict[str, str]:
    """
    Lee las URIs de manuales desde st.secrets["manuales"].

    Cachea el resultado en st.session_state._manuales_uris para evitar
    lecturas repetidas de secrets en cada llamada.

    Returns:
        {key: uri_string} — dict vacío si no hay sección [manuales] en secrets.
    """
    _CACHE_KEY = "_manuales_uris"

    # Devolver caché si ya fue cargado en esta sesión
    cached = st.session_state.get(_CACHE_KEY)
    if cached is not None:
        return cached  # type: ignore[return-value]

    try:
        seccion = st.secrets.get("manuales", {})
        uris: dict[str, str] = {
            k: str(v)
            for k, v in seccion.items()
            if k in MANUAL_KEYS and v
        }
        st.session_state[_CACHE_KEY] = uris
        if uris:
            log.debug("manual_loader: %d URIs cargadas: %s", len(uris), list(uris.keys()))
        return uris
    except Exception as exc:
        # Degradación elegante: si secrets no está disponible (tests, scripts), devuelve {}
        log.debug("manual_loader: no se pudieron cargar manuales (%s)", exc)
        st.session_state[_CACHE_KEY] = {}
        return {}


# ─── Construcción de parts fileData ──────────────────────────────────────────

def _uris_a_parts(uris: dict[str, str], keys: list[str]) -> list[dict]:
    """
    Convierte una lista de claves de manual en parts fileData de Gemini.

    Solo incluye las claves que tengan URI configurada.
    """
    parts = []
    for key in keys:
        uri = uris.get(key)
        if uri:
            parts.append({
                "fileData": {
                    "mimeType": "application/pdf",
                    "fileUri" : uri,
                }
            })
    return parts


def obtener_file_parts_ventas(tipo_dte: str) -> list[dict]:
    """
    Devuelve los fileData parts del manual relevante para extracción en VENTAS.

    Para tipos 03/05/06 usa ventas_contribuyentes.
    Para tipo 01 usa ventas_consumidor.
    Para tipo 11 usa ventas_contribuyentes.

    Args:
        tipo_dte: código de 2 dígitos, ej. "03", "01".

    Returns:
        Lista de dicts con formato {"fileData": {"mimeType": ..., "fileUri": ...}}.
        Lista vacía si no hay URIs configuradas o el tipo no está mapeado.
    """
    uris = cargar_uris_manuales()
    if not uris:
        return []

    ventas_keys_map: dict[str, list[str]] = {
        "01": ["ventas_consumidor"],
        "03": ["ventas_contribuyentes"],
        "05": ["ventas_contribuyentes"],
        "06": ["ventas_contribuyentes"],
        "11": ["ventas_contribuyentes"],
    }
    keys = ventas_keys_map.get(tipo_dte, [])
    return _uris_a_parts(uris, keys)


def obtener_file_parts_compras(tipo_dte: str) -> list[dict]:
    """
    Devuelve los fileData parts del manual relevante para extracción en COMPRAS.

    Para tipos 03/05/06 usa compras_contribuyentes.
    Para tipo 14 usa compras_sujetos_excluidos.

    Args:
        tipo_dte: código de 2 dígitos, ej. "03", "14".

    Returns:
        Lista de dicts con formato {"fileData": {"mimeType": ..., "fileUri": ...}}.
        Lista vacía si no hay URIs configuradas o el tipo no está mapeado.
    """
    uris = cargar_uris_manuales()
    if not uris:
        return []

    compras_keys_map: dict[str, list[str]] = {
        "03": ["compras_contribuyentes"],
        "05": ["compras_contribuyentes"],
        "06": ["compras_contribuyentes"],
        "11": ["compras_contribuyentes"],
        "14": ["compras_sujetos_excluidos"],
    }
    keys = compras_keys_map.get(tipo_dte, [])
    return _uris_a_parts(uris, keys)


def obtener_file_parts_retenciones() -> list[dict]:
    """
    Devuelve los fileData parts para el módulo de retenciones.

    Incluye retencion_1pct y f14_retenciones cuando estén disponibles.

    Returns:
        Lista de dicts con formato {"fileData": {"mimeType": ..., "fileUri": ...}}.
        Lista vacía si no hay URIs configuradas.
    """
    uris = cargar_uris_manuales()
    if not uris:
        return []

    keys = ["retencion_1pct", "f14_retenciones"]
    return _uris_a_parts(uris, keys)
