"""
local_db.py — Almacenamiento local en JSON para clientes y proveedores.
"""
from __future__ import annotations
import json
import logging
import os
import time

log = logging.getLogger(__name__)

_BASE = os.environ.get(
    "LOCAL_DB_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data"),
)
_CLIENTES_FILE    = os.path.join(_BASE, "clientes.json")
_PROVEEDORES_FILE = os.path.join(_BASE, "proveedores.json")

_MAX_RETRIES = 3
_RETRY_DELAY = 0.05  # segundos


def _leer(path: str) -> dict:
    for attempt in range(_MAX_RETRIES):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                log.warning("_leer(%s): contenido inesperado, retornando {}", path)
                return {}
            return data
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            log.warning("_leer(%s): JSON inválido (intento %d): %s", path, attempt + 1, exc)
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY * (2 ** attempt))
        except OSError as exc:
            log.warning("_leer(%s): error de I/O (intento %d): %s", path, attempt + 1, exc)
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY * (2 ** attempt))
    return {}


def _escribir(path: str, data: dict) -> None:
    """Escritura atómica: escribe en .tmp y renombra para evitar corrupción."""
    dir_ = os.path.dirname(path)
    os.makedirs(dir_, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, path)
    _invalidar_cache(path)


# ── Cache en memoria (módulo-level, vive por proceso) ────────────────────────

_cache: dict[str, dict] = {}
_cache_mtime: dict[str, float] = {}


def _invalidar_cache(path: str) -> None:
    _cache.pop(path, None)
    _cache_mtime.pop(path, None)


def _leer_con_cache(path: str) -> dict:
    try:
        mtime = os.path.getmtime(path)
        if _cache_mtime.get(path) == mtime and path in _cache:
            return _cache[path]
    except OSError:
        pass
    data = _leer(path)
    try:
        _cache[path] = data
        _cache_mtime[path] = os.path.getmtime(path)
    except OSError:
        pass
    return data


# ── Clientes ──────────────────────────────────────────────────────────────────

def cargar_clientes_db() -> list[dict]:
    raw = _leer_con_cache(_CLIENTES_FILE)
    result = []
    for nit, v in raw.items():
        row = dict(v)
        row.setdefault("id", nit)
        row.setdefault("nit", nit)
        row.setdefault("nombre_comercial", row.pop("nombre", ""))
        result.append(row)
    return sorted(result, key=lambda x: x.get("nombre_comercial", ""))


def guardar_cliente_db(
    nit: str,
    nombre: str,
    nrc: str = "",
    dui: str = "",
    actividad: str = "",
) -> tuple[bool, str]:
    try:
        data = _leer(_CLIENTES_FILE)
        data[nit] = {
            "nit":       nit,
            "nombre":    nombre.strip().upper(),
            "nrc":       nrc or "",
            "dui":       dui or "",
            "actividad": actividad.strip().upper(),
        }
        _escribir(_CLIENTES_FILE, data)
        return True, ""
    except Exception as exc:
        log.error("guardar_cliente_db(%s): %s", nit, exc)
        return False, str(exc)


def eliminar_cliente_db(cliente_id: str) -> bool:
    try:
        data = _leer(_CLIENTES_FILE)
        if cliente_id in data:
            del data[cliente_id]
        else:
            key = next((k for k, v in data.items() if v.get("nit") == cliente_id), None)
            if key:
                del data[key]
        _escribir(_CLIENTES_FILE, data)
        return True
    except Exception as exc:
        log.error("eliminar_cliente_db(%s): %s", cliente_id, exc)
        return False


# ── Proveedores ───────────────────────────────────────────────────────────────

def cargar_proveedores_db() -> list[dict]:
    raw = _leer_con_cache(_PROVEEDORES_FILE)
    result = []
    for nit, v in raw.items():
        row = dict(v)
        row.setdefault("id", nit)
        row.setdefault("nit", nit)
        row.setdefault("nombre_comercial", row.pop("nombre", ""))
        result.append(row)
    return sorted(result, key=lambda x: x.get("nombre_comercial", ""))


def guardar_proveedor_db(nit: str, nombre: str, nrc: str = "") -> bool:
    try:
        data = _leer(_PROVEEDORES_FILE)
        data[nit] = {
            "nombre": nombre.strip().upper(),
            "nrc":    nrc or "",
        }
        _escribir(_PROVEEDORES_FILE, data)
        return True
    except Exception as exc:
        log.error("guardar_proveedor_db(%s): %s", nit, exc)
        return False


def eliminar_proveedor_db(proveedor_id: str) -> bool:
    try:
        data = _leer(_PROVEEDORES_FILE)
        if proveedor_id in data:
            del data[proveedor_id]
        else:
            key = next((k for k, v in data.items() if v.get("nit") == proveedor_id), None)
            if key:
                del data[key]
        _escribir(_PROVEEDORES_FILE, data)
        return True
    except Exception as exc:
        log.error("eliminar_proveedor_db(%s): %s", proveedor_id, exc)
        return False


def buscar_proveedor_por_nit(nit: str) -> dict | None:
    if not nit:
        return None
    data = _leer_con_cache(_PROVEEDORES_FILE)
    row = data.get(nit)
    if row:
        return {
            "nombre": row.get("nombre", row.get("nombre_comercial", "")),
            "nrc":    row.get("nrc", ""),
            "fuente": "privado",
        }
    return None


def auto_registrar_proveedor(nit: str, nombre: str, nrc: str = "") -> bool:
    if not nit or not nombre.strip():
        return False
    if buscar_proveedor_por_nit(nit):
        return True
    return guardar_proveedor_db(nit=nit, nombre=nombre, nrc=nrc)


def cargar_proveedores_combinados() -> dict:
    raw = _leer_con_cache(_PROVEEDORES_FILE)
    return {
        nit: {
            "nombre": v.get("nombre", v.get("nombre_comercial", "")),
            "nrc":    v.get("nrc", ""),
        }
        for nit, v in raw.items()
    }
