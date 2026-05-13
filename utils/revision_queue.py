"""
utils/revision_queue.py — Cola de revisión persistente por cliente activo.

Serializa los ítems de cola_revision a data/cola_revision_{nit}.json.
Los bytes del PDF NO se persisten (son muy pesados y no son JSON-serializable).
Al recargar la app, los datos extraídos pre-llenados se restauran pero
el usuario debe re-subir el PDF si quiere re-procesar con Vision.
"""
from __future__ import annotations

import json
import logging
import os
import re

log = logging.getLogger(__name__)

_DIR      = "data"
_OMITIR   = {"bytes", "_vision_campos", "_vision_alertas", "_vision_audit"}


def _ruta(nit: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z]", "", str(nit)) or "sandbox"
    return os.path.join(_DIR, f"cola_revision_{safe}.json")


def cola_cargar(nit: str) -> list[dict]:
    """Load persisted queue for the given NIT. Returns [] if none."""
    path = _ruta(nit)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
        # Mark loaded items as missing bytes (PDF was not persisted)
        for item in items:
            item.setdefault("bytes", None)
            item.setdefault("_sin_bytes", True)
        log.info("Cola cargada: %d ítems (NIT=%s)", len(items), nit[:6])
        return items
    except Exception as exc:
        log.warning("cola_cargar: %s", exc)
        return []


def cola_guardar(nit: str, items: list[dict]) -> None:
    """Persist current queue to disk (bytes fields stripped)."""
    os.makedirs(_DIR, exist_ok=True)
    serializable = []
    for item in items:
        clean = {k: v for k, v in item.items() if k not in _OMITIR}
        # Convert non-serializable values gracefully
        serializable.append(clean)
    try:
        with open(_ruta(nit), "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        log.warning("cola_guardar: %s", exc)


def cola_agregar(nit: str, item: dict, lista_actual: list[dict]) -> None:
    """Append item to the in-memory list AND persist immediately."""
    lista_actual.append(item)
    cola_guardar(nit, lista_actual)


def cola_limpiar(nit: str) -> None:
    """Delete persisted queue file for this NIT."""
    path = _ruta(nit)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as exc:
            log.warning("cola_limpiar: %s", exc)
