"""
local_db.py — Almacenamiento local en JSON para clientes y proveedores.
Reemplaza las funciones de Supabase.
"""
from __future__ import annotations
import json
import uuid
import os

_BASE = os.path.join(os.path.dirname(__file__), "..", "data")
_CLIENTES_FILE    = os.path.join(_BASE, "clientes.json")
_PROVEEDORES_FILE = os.path.join(_BASE, "proveedores.json")


def _leer(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _escribir(path: str, data: dict) -> None:
    """Escritura atómica: escribe en .tmp y renombra para evitar corrupción."""
    dir_ = os.path.dirname(path)
    os.makedirs(dir_, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, path)


# ── Clientes ──────────────────────────────────────────────────────────────────

def cargar_clientes_db() -> list[dict]:
    raw = _leer(_CLIENTES_FILE)
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
            "nit":      nit,
            "nombre":   nombre.strip().upper(),
            "nrc":      nrc or "",
            "dui":      dui or "",
            "actividad": actividad.strip().upper(),
        }
        _escribir(_CLIENTES_FILE, data)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def eliminar_cliente_db(cliente_id: str) -> bool:
    try:
        data = _leer(_CLIENTES_FILE)
        # cliente_id puede ser NIT (key) o valor en campo "nit"
        if cliente_id in data:
            del data[cliente_id]
        else:
            key = next((k for k, v in data.items() if v.get("nit") == cliente_id), None)
            if key:
                del data[key]
        _escribir(_CLIENTES_FILE, data)
        return True
    except Exception:
        return False


# ── Proveedores ───────────────────────────────────────────────────────────────

def cargar_proveedores_db() -> list[dict]:
    raw = _leer(_PROVEEDORES_FILE)
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
    except Exception:
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
    except Exception:
        return False


def buscar_proveedor_por_nit(nit: str) -> dict | None:
    if not nit:
        return None
    data = _leer(_PROVEEDORES_FILE)
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
    existente = buscar_proveedor_por_nit(nit)
    if existente:
        return True
    return guardar_proveedor_db(nit=nit, nombre=nombre, nrc=nrc)


def cargar_proveedores_combinados() -> dict:
    raw = _leer(_PROVEEDORES_FILE)
    result = {}
    for nit, v in raw.items():
        result[nit] = {
            "nombre": v.get("nombre", v.get("nombre_comercial", "")),
            "nrc":    v.get("nrc", ""),
        }
    return result
