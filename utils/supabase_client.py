"""
supabase_client.py — Capa de compatibilidad sin Supabase.
Auth por contraseña simple; datos en JSON local.
"""
from __future__ import annotations
import streamlit as st
from utils.local_db import (
    cargar_clientes_db,
    guardar_cliente_db,
    eliminar_cliente_db,
    cargar_proveedores_db,
    guardar_proveedor_db,
    eliminar_proveedor_db,
    buscar_proveedor_por_nit,
    auto_registrar_proveedor,
    cargar_proveedores_combinados,
)

# Re-exportar para que otras páginas no tengan que cambiar sus imports
__all__ = [
    "login", "logout", "session_activa", "restaurar_sesion_desde_cookie",
    "get_org_info", "get_organizacion_id",
    "cargar_clientes_db", "guardar_cliente_db", "eliminar_cliente_db",
    "cargar_proveedores_db", "guardar_proveedor_db", "eliminar_proveedor_db",
    "buscar_proveedor_por_nit", "auto_registrar_proveedor",
    "cargar_proveedores_combinados",
    "puede_procesar_mas_dtes", "guardar_dte_db",
]

_DEFAULT_PASSWORD = "learnix2024"


def _get_password() -> str:
    try:
        return st.secrets.get("APP_PASSWORD", _DEFAULT_PASSWORD)
    except Exception:
        return _DEFAULT_PASSWORD


def login(email: str, password: str) -> tuple[bool, str]:
    if password == _get_password():
        st.session_state["autenticado"]     = True
        st.session_state["sb_user_email"]   = email or "usuario"
        st.session_state["sb_rol"]          = "admin"
        st.session_state["intentos_login"]  = 0
        st.session_state["bloqueado_hasta"] = 0
        return True, ""
    return False, "Contraseña incorrecta."


def logout() -> None:
    conservar = {"intentos_login", "bloqueado_hasta"}
    for k in [k for k in st.session_state if k not in conservar]:
        del st.session_state[k]


def session_activa() -> bool:
    return bool(st.session_state.get("autenticado"))


def restaurar_sesion_desde_cookie() -> bool:
    return False


def get_org_info() -> dict:
    return {}


def get_organizacion_id() -> str | None:
    return None


def puede_procesar_mas_dtes() -> bool:
    return True


def guardar_dte_db(cliente_id: str, row: dict) -> bool:
    return True
