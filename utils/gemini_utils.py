"""
gemini_utils.py — Stub de compatibilidad.
Todo el código real vive en ai_utils.py (Groq / llama3-8b-8192).
"""
from utils.ai_utils import *  # noqa: F401, F403
from utils.ai_utils import (
    _get_api_key,
    _llamar_groq,
    _validar_fecha,
    _validar_nombre,
    _validar_nit,
    _extraer_campos_corregidos,
    _cb_state,
    _cb_is_open,
    _cb_on_success,
    _cb_on_failure,
)
