"""
utils/pdf_cache.py — Caché SHA256 para resultados de Gemini Vision.

Almacena (campos, alertas, audit) por huella SHA256 del PDF + tipo_dte
en st.session_state. Evita re-llamar a la API si el mismo archivo ya fue
procesado en la sesión actual.

Límite: 200 entradas; al desbordarse se eliminan las 50 más antiguas.
"""
from __future__ import annotations
import hashlib
import streamlit as st

_CACHE_KEY  = "_vision_cache"
_MAX_ENTRIES = 200


def _key(pdf_bytes: bytes, tipo_dte: str) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()[:24] + ":" + tipo_dte


def cache_get(pdf_bytes: bytes, tipo_dte: str) -> tuple | None:
    """Returns cached (campos, alertas, audit) or None if not cached."""
    return st.session_state.get(_CACHE_KEY, {}).get(_key(pdf_bytes, tipo_dte))


def cache_set(pdf_bytes: bytes, tipo_dte: str, value: tuple) -> None:
    """Store Vision result in session cache."""
    if _CACHE_KEY not in st.session_state:
        st.session_state[_CACHE_KEY] = {}
    store = st.session_state[_CACHE_KEY]
    store[_key(pdf_bytes, tipo_dte)] = value
    if len(store) > _MAX_ENTRIES:
        for k in list(store)[:50]:
            del store[k]


def cache_clear() -> None:
    """Evict the entire Vision cache (e.g. after API key change)."""
    st.session_state.pop(_CACHE_KEY, None)


def cache_size() -> int:
    return len(st.session_state.get(_CACHE_KEY, {}))
