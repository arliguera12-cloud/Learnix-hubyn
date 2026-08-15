#!/usr/bin/env python3
"""
migrate_local_json.py — Migración one-time de backend/data/*.json a las tablas
clientes_directorio / proveedores_directorio en Supabase.

Uso:
    cd backend && python ../scripts/migrate_local_json.py [--dry-run]

Requiere las mismas variables de entorno que el backend (SUPABASE_URL,
SUPABASE_KEY o SUPABASE_SERVICE_KEY) — cárgalas con `source .env` o
exportándolas antes de correr el script.

Este script es idempotente respecto al esquema (usa upsert por NIT dentro de
organizacion_id=NULL, igual que local_db.py cuando no se pasa organización),
pero está pensado para correrse una sola vez, antes de eliminar
backend/data/*.json del repo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from utils.supabase_admin import get_supabase  # noqa: E402

_DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"
_CLIENTES_FILE = _DATA_DIR / "clientes.json"
_PROVEEDORES_FILE = _DATA_DIR / "proveedores.json"


def _cargar_json(path: Path) -> dict:
    if not path.exists():
        print(f"  (no existe {path}, se omite)")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def migrar_clientes(dry_run: bool) -> int:
    data = _cargar_json(_CLIENTES_FILE)
    if not data:
        return 0
    rows = [
        {
            "nit": nit,
            "nombre_comercial": v.get("nombre", "").strip().upper(),
            "dui": v.get("dui", "") or "",
            "nrc": v.get("nrc", "") or "",
            "actividad": (v.get("actividad", "") or "").strip().upper(),
            "organizacion_id": None,
        }
        for nit, v in data.items()
    ]
    print(f"  {len(rows)} clientes a migrar")
    if dry_run:
        return len(rows)
    sb = get_supabase()
    sb.table("clientes_directorio").upsert(
        rows, on_conflict="nit", ignore_duplicates=False
    ).execute()
    return len(rows)


def migrar_proveedores(dry_run: bool) -> int:
    data = _cargar_json(_PROVEEDORES_FILE)
    if not data:
        return 0
    rows = [
        {
            "nit": nit,
            "nombre_comercial": v.get("nombre", v.get("nombre_comercial", "")).strip().upper(),
            "nrc": v.get("nrc", "") or "",
            "organizacion_id": None,
        }
        for nit, v in data.items()
    ]
    print(f"  {len(rows)} proveedores a migrar")
    if dry_run:
        return len(rows)
    sb = get_supabase()
    sb.table("proveedores_directorio").upsert(
        rows, on_conflict="nit", ignore_duplicates=False
    ).execute()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo cuenta cuántos registros se migrarían, sin escribir en Supabase.",
    )
    args = parser.parse_args()

    if not os.environ.get("SUPABASE_URL"):
        print("ERROR: falta SUPABASE_URL en el entorno.", file=sys.stderr)
        sys.exit(1)

    print(f"Migrando desde {_DATA_DIR} ({'dry-run' if args.dry_run else 'real'})")
    n_clientes = migrar_clientes(args.dry_run)
    n_proveedores = migrar_proveedores(args.dry_run)
    print(f"\nListo: {n_clientes} clientes, {n_proveedores} proveedores"
          + (" (dry-run, nada escrito)" if args.dry_run else " migrados a Supabase"))


if __name__ == "__main__":
    main()
