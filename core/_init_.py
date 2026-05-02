# core/__init__.py
"""
Módulo central de Learnix Hub
Exporta todas las funciones y constantes compartidas
"""

from .constantes import (
    TIPOS_DTE,
    FORMATOS_FECHA,
    CAMPOS_VENTAS,
    CAMPOS_COMPRAS,
    CAMPOS_RETENCIONES,
    CAMPOS_SUJETOS_EXCLUIDOS,
    GEMINI_MODEL,
    CONFIANZA_UMBRALES,
    MENSAJES,
    PATRON_NIT,
    PATRON_DUI,
)

from .extractores import (
    limpiar_monto,
    formatear_uuid,
    extraer_y_formatear_fecha,
    parsear_json_dte,
)

from .gemini_validator import (
    necesita_gemini,
    validar_con_gemini,
    validar_retenciones_con_gemini,
)

from .filtros import render_panel_filtros

__all__ = [
    # Constantes
    "TIPOS_DTE",
    "FORMATOS_FECHA",
    "CAMPOS_VENTAS",
    "CAMPOS_COMPRAS",
    "CAMPOS_RETENCIONES",
    "CAMPOS_SUJETOS_EXCLUIDOS",
    "GEMINI_MODEL",
    "CONFIANZA_UMBRALES",
    "MENSAJES",
    "PATRON_NIT",
    "PATRON_DUI",
    # Extractores
    "limpiar_monto",
    "formatear_uuid",
    "extraer_y_formatear_fecha",
    "parsear_json_dte",
    # Gemini
    "necesita_gemini",
    "validar_con_gemini",
    "validar_retenciones_con_gemini",
    # Filtros
    "render_panel_filtros",
]
