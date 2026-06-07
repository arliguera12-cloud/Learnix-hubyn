"""
supabase_client.py — versión FastAPI.
Usa variables de entorno en lugar de st.secrets / st.session_state.
Mantiene la misma interfaz pública que la versión Streamlit para que
los extractores no tengan que cambiar sus imports.
"""
from __future__ import annotations

import os

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

__all__ = [
    "login", "logout", "session_activa",
    "get_org_info", "get_organizacion_id",
    "cargar_clientes_db", "guardar_cliente_db", "eliminar_cliente_db",
    "cargar_proveedores_db", "guardar_proveedor_db", "eliminar_proveedor_db",
    "buscar_proveedor_por_nit", "auto_registrar_proveedor",
    "cargar_proveedores_combinados",
    "puede_procesar_mas_dtes", "guardar_dte_db",
]

_DEFAULT_PASSWORD = "learnix2024"


def _get_password() -> str:
    return os.environ.get("APP_PASSWORD", _DEFAULT_PASSWORD)


def login(email: str, password: str) -> dict:
    """Valida credenciales. Devuelve {"success": True} o {"success": False, "error": "..."}."""
    if password == _get_password():
        return {"success": True, "email": email or "usuario", "role": "admin"}
    return {"success": False, "error": "Contraseña incorrecta."}


def logout(access_token: str = "") -> dict:
    return {"success": True}


def session_activa() -> bool:
    return True


def get_org_info() -> dict:
    return {}


def get_organizacion_id() -> str | None:
    return None


def puede_procesar_mas_dtes() -> bool:
    return True


def guardar_dte_db(cliente_id: str, row: dict) -> bool:
    return True
