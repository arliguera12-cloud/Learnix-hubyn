"""
constants.py — Constantes centralizadas para Learnix DTE Hub.
"""
from __future__ import annotations

# ── Tipos DTE ─────────────────────────────────────────────────────────────────

TIPOS_CONTRIBUYENTES: frozenset[str] = frozenset({"03", "05", "06"})
TIPOS_CONSUMIDOR: frozenset[str] = frozenset({"01", "02", "10", "11"})
TODOS_TIPOS_VALIDOS: frozenset[str] = TIPOS_CONTRIBUYENTES | TIPOS_CONSUMIDOR
TIPOS_VALIDOS_COMPRAS: frozenset[str] = frozenset({"03", "05", "06", "11"})

# ── Claves de Session State ───────────────────────────────────────────────────

class SK:
    """Session State Keys — evita magic strings dispersos."""
    CLIENTE_ACTIVO    = "cliente_activo"
    DB_VENTAS         = "db_ventas"
    DB_COMPRAS        = "db_compras"
    DB_RET            = "db_ret"
    COLA_REVISION_V   = "cola_revision_v"
    COLA_REVISION_C   = "cola_revision_c"
    PDFS_PROCESADOS   = "_pdfs_procesados"
    CACHE_EXTRACCIONES = "_cache_extracciones"
    GROQ_API_KEY      = "groq_api_key_input"

# ── Extracción de texto ───────────────────────────────────────────────────────

MAX_VALORES_LOOP_VENTAS  = 30
MAX_VALORES_LOOP_COMPRAS = 40

# Ventana de contexto alrededor del NIT para buscar nombre
WINDOW_BEFORE = 600
WINDOW_AFTER  = 1500

# ── Procesamiento concurrente ─────────────────────────────────────────────────

CACHE_MAX_SIZE   = 200
CACHE_EVICT_SIZE = 50

# ── Validación de campos ──────────────────────────────────────────────────────

SELLO_LEN_MIN = 30
SELLO_LEN_MAX = 45
NIT_LENGTH    = 14
