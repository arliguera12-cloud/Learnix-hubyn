# core/extractores/__init__.py
"""
Módulo de extractores de DTE (PDF y JSON).
"""

from .gemini_validator import (
    necesita_gemini,
    validar_con_gemini,
    validar_retenciones_con_gemini
)

from .filtros import (
    render_panel_filtros,
    parsear_json_dte
)

from .utils import (
    limpiar_monto,
    extraer_y_formatear_fecha,
    formatear_uuid
)

__all__ = [
    "necesita_gemini",
    "validar_con_gemini",
    "validar_retenciones_con_gemini",
    "render_panel_filtros",
    "parsear_json_dte",
    "limpiar_monto",
    "extraer_y_formatear_fecha",
    "formatear_uuid",
]
