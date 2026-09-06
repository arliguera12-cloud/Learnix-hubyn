"""
org_context.py — Resuelve la organización (tenant) del usuario autenticado.

El backend habla con Supabase usando la service key, que bypassa RLS: las
políticas de db/01_schema_saas.sql (`organizacion_id = get_mi_organizacion_id()`)
no se aplican a nada de lo que haga este proceso. Por eso el filtro por
organización tiene que hacerse acá, en Python, y no puede delegarse a la base.

El JWT de Supabase solo trae `sub` (el user_id de auth.users); la pertenencia
a una organización vive en `perfiles.organizacion_id`. Este módulo hace ese
salto y lo cachea por un rato corto — el mapeo usuario→organización cambia
muy rara vez, pero un lote de 15 PDFs no debería pagar 15 consultas por él.
"""
from __future__ import annotations

import logging
import threading
import time

from fastapi import Depends, HTTPException, status

from utils.auth_dependency import get_current_user
from utils.supabase_admin import get_supabase

log = logging.getLogger(__name__)

_TTL_SEGUNDOS = 300
_lock = threading.Lock()
_cache: dict[str, tuple[float, str]] = {}


def _consultar_organizacion(user_id: str) -> str | None:
    resp = (
        get_supabase()
        .table("perfiles")
        .select("organizacion_id")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    return resp.data[0].get("organizacion_id")


def resolver_organizacion_id(user_id: str) -> str:
    ahora = time.monotonic()
    with _lock:
        entrada = _cache.get(user_id)
        if entrada is not None and ahora - entrada[0] < _TTL_SEGUNDOS:
            return entrada[1]

    try:
        organizacion_id = _consultar_organizacion(user_id)
    except Exception as exc:
        log.error("No se pudo resolver la organización de %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo verificar la organización del usuario",
        )

    if not organizacion_id:
        # Sin organización no hay forma de aislar los datos de este usuario de
        # los de otro tenant, así que se rechaza en vez de caer a un directorio
        # compartido. Se repara desde la app con reparar_mi_perfil() (db/04).
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tu usuario no pertenece a ninguna organización. "
                "Vuelve a iniciar sesión o contacta al administrador."
            ),
        )

    with _lock:
        _cache[user_id] = (ahora, organizacion_id)
    return organizacion_id


def get_current_org(user: dict = Depends(get_current_user)) -> dict:
    """Dependencia: el usuario autenticado más su `organizacion_id`."""
    return {**user, "organizacion_id": resolver_organizacion_id(user["user_id"])}
