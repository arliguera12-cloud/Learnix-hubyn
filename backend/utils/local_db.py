"""
local_db.py — Directorio de clientes y proveedores, persistido en Supabase
(tablas clientes_directorio / proveedores_directorio, ver db/06_local_data_tables.sql).

Reemplaza el almacenamiento anterior en JSON sobre el filesystem del backend
(backend/data/*.json), que se perdía en cada redeploy de Railway (filesystem
efímero).

Aislamiento entre organizaciones: `organizacion_id` es obligatorio en todas
las funciones. El backend habla con Supabase con la service key, que bypassa
RLS, así que las políticas por organización de db/06 no se aplican acá — el
filtro tiene que hacerlo este módulo. Antes el parámetro era opcional y todos
los llamadores lo omitían, con lo que las filas quedaban con
`organizacion_id IS NULL` y cualquier usuario autenticado leía, sobrescribía
y borraba el directorio de cualquier otro tenant. Las filas legadas sin
organización se reasignan con db/08_org_scope_directorio.sql.
"""
from __future__ import annotations

import logging
import threading
import time

from utils.supabase_admin import get_supabase

log = logging.getLogger(__name__)

_CLIENTES_TABLE = "clientes_directorio"
_PROVEEDORES_TABLE = "proveedores_directorio"

# Claves de caché — no son nombres de tabla: cargar_proveedores_db y
# cargar_proveedores_combinados leen la misma tabla pero devuelven formas
# distintas (lista de filas completas vs. dict indexado por nit con
# columnas recortadas), así que comparten tabla pero no pueden compartir
# entrada de caché.
_CACHE_CLIENTES = "clientes_db"
_CACHE_PROVEEDORES_COMBINADOS = "proveedores_combinados"

# Un lote de 40 PDFs corre las 40 extracciones en paralelo (ver
# routers/procesamiento.py: _process_lote), y cada una llamaba a
# cargar_proveedores_combinados/cargar_clientes_db directo — 40 consultas a
# Supabase en paralelo por lote, repitiendo exactamente la misma consulta
# (el directorio no cambia entre PDFs de un mismo lote), y si la tabla no
# existe o Supabase está lento, esas 40 esperas de red se pagan una por una.
# TTL corto porque solo busca evitar la repetición dentro del mismo lote, no
# servir datos desactualizados si alguien edita el directorio entre subidas.
_TTL_SEGUNDOS = 30
_cache_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, object]] = {}


def _cache_get_or_load(clave_cache: str, organizacion_id: str, cargar):
    clave = (clave_cache, organizacion_id)
    ahora = time.monotonic()
    with _cache_lock:
        entrada = _cache.get(clave)
        if entrada is not None and ahora - entrada[0] < _TTL_SEGUNDOS:
            return entrada[1]
    valor = cargar()
    with _cache_lock:
        _cache[clave] = (ahora, valor)
    return valor


def _org_eq(query, organizacion_id: str):
    """Restringe la consulta a una organización. Nunca acepta un scope vacío:
    sin `organizacion_id` la consulta abarcaría el directorio de todos los
    tenants, así que es un error de programación, no un caso a tolerar."""
    _exigir_org(organizacion_id)
    return query.eq("organizacion_id", organizacion_id)


def _exigir_org(organizacion_id: str) -> None:
    if not organizacion_id:
        raise ValueError("organizacion_id es obligatorio para operar sobre el directorio")


# ── Clientes ──────────────────────────────────────────────────────────────────

def _cargar_clientes_db_sin_cache(organizacion_id: str) -> list[dict]:
    try:
        query = get_supabase().table(_CLIENTES_TABLE).select("*")
        resp = _org_eq(query, organizacion_id).order("nombre_comercial").execute()
        return resp.data or []
    except Exception as exc:
        log.error("cargar_clientes_db: %s", exc)
        return []


def cargar_clientes_db(organizacion_id: str) -> list[dict]:
    _exigir_org(organizacion_id)
    return _cache_get_or_load(
        _CACHE_CLIENTES, organizacion_id, lambda: _cargar_clientes_db_sin_cache(organizacion_id)
    )


def guardar_cliente_db(
    nit: str,
    nombre: str,
    organizacion_id: str,
    nrc: str = "",
    dui: str = "",
    actividad: str = "",
) -> tuple[bool, str]:
    _exigir_org(organizacion_id)
    try:
        row = {
            "nit":              nit,
            "nombre_comercial": nombre.strip().upper(),
            "nrc":              nrc or "",
            "dui":              dui or "",
            "actividad":        actividad.strip().upper(),
            "organizacion_id":  organizacion_id,
        }
        sb = get_supabase()
        existing = _org_eq(
            sb.table(_CLIENTES_TABLE).select("id").eq("nit", nit), organizacion_id
        ).execute()
        if existing.data:
            sb.table(_CLIENTES_TABLE).update(row).eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table(_CLIENTES_TABLE).insert(row).execute()
        with _cache_lock:
            _cache.pop((_CACHE_CLIENTES, organizacion_id), None)
        return True, ""
    except Exception as exc:
        log.error("guardar_cliente_db(%s): %s", nit, exc)
        return False, str(exc)


def eliminar_cliente_db(cliente_id: str, organizacion_id: str) -> bool:
    _exigir_org(organizacion_id)
    try:
        sb = get_supabase()
        # El borrado por `id` también se restringe a la organización: el id es
        # un UUID que llega del cliente y, sin este filtro, valía para borrar
        # la fila de cualquier otro tenant que lo conociera.
        resp = _org_eq(
            sb.table(_CLIENTES_TABLE).delete().eq("id", cliente_id), organizacion_id
        ).execute()
        if not resp.data:
            _org_eq(
                sb.table(_CLIENTES_TABLE).delete().eq("nit", cliente_id), organizacion_id
            ).execute()
        with _cache_lock:
            _cache.pop((_CACHE_CLIENTES, organizacion_id), None)
        return True
    except Exception as exc:
        log.error("eliminar_cliente_db(%s): %s", cliente_id, exc)
        return False


# ── Proveedores ───────────────────────────────────────────────────────────────

def cargar_proveedores_db(organizacion_id: str) -> list[dict]:
    _exigir_org(organizacion_id)
    try:
        query = get_supabase().table(_PROVEEDORES_TABLE).select("*")
        resp = _org_eq(query, organizacion_id).order("nombre_comercial").execute()
        return resp.data or []
    except Exception as exc:
        log.error("cargar_proveedores_db: %s", exc)
        return []


def guardar_proveedor_db(
    nit: str, nombre: str, organizacion_id: str, nrc: str = ""
) -> bool:
    _exigir_org(organizacion_id)
    try:
        row = {
            "nit":              nit,
            "nombre_comercial": nombre.strip().upper(),
            "nrc":              nrc or "",
            "organizacion_id":  organizacion_id,
        }
        sb = get_supabase()
        existing = _org_eq(
            sb.table(_PROVEEDORES_TABLE).select("id").eq("nit", nit), organizacion_id
        ).execute()
        if existing.data:
            sb.table(_PROVEEDORES_TABLE).update(row).eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table(_PROVEEDORES_TABLE).insert(row).execute()
        with _cache_lock:
            _cache.pop((_CACHE_PROVEEDORES_COMBINADOS, organizacion_id), None)
        return True
    except Exception as exc:
        log.error("guardar_proveedor_db(%s): %s", nit, exc)
        return False


def eliminar_proveedor_db(proveedor_id: str, organizacion_id: str) -> bool:
    _exigir_org(organizacion_id)
    try:
        sb = get_supabase()
        resp = _org_eq(
            sb.table(_PROVEEDORES_TABLE).delete().eq("id", proveedor_id), organizacion_id
        ).execute()
        if not resp.data:
            _org_eq(
                sb.table(_PROVEEDORES_TABLE).delete().eq("nit", proveedor_id), organizacion_id
            ).execute()
        with _cache_lock:
            _cache.pop((_CACHE_PROVEEDORES_COMBINADOS, organizacion_id), None)
        return True
    except Exception as exc:
        log.error("eliminar_proveedor_db(%s): %s", proveedor_id, exc)
        return False


def buscar_proveedor_por_nit(nit: str, organizacion_id: str) -> dict | None:
    _exigir_org(organizacion_id)
    if not nit:
        return None
    try:
        query = get_supabase().table(_PROVEEDORES_TABLE).select("nombre_comercial,nrc").eq("nit", nit)
        resp = _org_eq(query, organizacion_id).limit(1).execute()
        if resp.data:
            row = resp.data[0]
            return {"nombre": row.get("nombre_comercial", ""), "nrc": row.get("nrc", ""), "fuente": "privado"}
        return None
    except Exception as exc:
        log.error("buscar_proveedor_por_nit(%s): %s", nit, exc)
        return None


def auto_registrar_proveedor(
    nit: str, nombre: str, organizacion_id: str, nrc: str = ""
) -> bool:
    _exigir_org(organizacion_id)
    if not nit or not nombre.strip():
        return False
    if buscar_proveedor_por_nit(nit, organizacion_id):
        return True
    return guardar_proveedor_db(nit=nit, nombre=nombre, nrc=nrc, organizacion_id=organizacion_id)


def _cargar_proveedores_combinados_sin_cache(organizacion_id: str) -> dict:
    try:
        query = get_supabase().table(_PROVEEDORES_TABLE).select("nit,nombre_comercial,nrc")
        resp = _org_eq(query, organizacion_id).execute()
        return {
            row["nit"]: {"nombre": row.get("nombre_comercial", ""), "nrc": row.get("nrc", "")}
            for row in (resp.data or [])
        }
    except Exception as exc:
        log.error("cargar_proveedores_combinados: %s", exc)
        return {}


def cargar_proveedores_combinados(organizacion_id: str) -> dict:
    _exigir_org(organizacion_id)
    return _cache_get_or_load(
        _CACHE_PROVEEDORES_COMBINADOS,
        organizacion_id,
        lambda: _cargar_proveedores_combinados_sin_cache(organizacion_id),
    )
