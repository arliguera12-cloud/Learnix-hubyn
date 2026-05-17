"""
database.py — Operaciones de base de datos de alto nivel para Learnix DTE Hub.

Complementa supabase_client.py exponiendo funciones que aceptan dicts completos
en lugar de parámetros individuales, útiles cuando los datos vienen de formularios
o de la extracción automática de DTEs.
"""
from __future__ import annotations
import logging
import streamlit as st
from utils.supabase_client import get_supabase, get_organizacion_id

logger = logging.getLogger(__name__)


def crear_cliente(datos_cliente: dict) -> bool:
    """
    Inserta o actualiza un cliente usando un dict de datos.

    Args:
        datos_cliente: Dict con cualquier combinación de claves:
                       nit, nombre_comercial, nrc, dui, actividad, organizacion_id.
                       Si 'organizacion_id' no está presente se toma de session_state.

    Returns:
        True si la operación fue exitosa, False en caso contrario.
    """
    datos_cliente = dict(datos_cliente)  # copia para no mutar el original

    # Usar organizacion_id del dict o caer en session_state
    org_id = datos_cliente.pop("organizacion_id", None) or get_organizacion_id()
    if not org_id:
        logger.error("crear_cliente: no hay organizacion_id disponible")
        return False

    datos_cliente["organizacion_id"] = org_id

    # user_id del usuario en sesión (requerido por la tabla)
    user = st.session_state.get("sb_user")
    if user and "user_id" not in datos_cliente:
        datos_cliente["user_id"] = user.id

    try:
        get_supabase().table("clientes").upsert(
            datos_cliente,
            on_conflict="organizacion_id,nit",
        ).execute()
        return True
    except Exception as exc:
        logger.error("crear_cliente: %s", exc)
        return False


def crear_proveedor(datos_proveedor: dict) -> bool:
    """
    Inserta o actualiza un proveedor privado usando un dict de datos.

    Args:
        datos_proveedor: Dict con claves: nit, nombre, rubro, organizacion_id (opcional).

    Returns:
        True si la operación fue exitosa, False en caso contrario.
    """
    datos_proveedor = dict(datos_proveedor)

    org_id = datos_proveedor.pop("organizacion_id", None) or get_organizacion_id()
    if not org_id:
        logger.error("crear_proveedor: no hay organizacion_id disponible")
        return False

    datos_proveedor["organizacion_id"] = org_id

    try:
        get_supabase().table("proveedores").upsert(
            datos_proveedor,
            on_conflict="organizacion_id,nit",
        ).execute()
        return True
    except Exception as exc:
        logger.error("crear_proveedor: %s", exc)
        return False
