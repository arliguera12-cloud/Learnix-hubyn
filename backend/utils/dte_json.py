"""
dte_json.py — Lectura del JSON firmado por Hacienda.

Centraliza la decodificación porque no todos los emisores entregan UTF-8: se
han recibido archivos válidos en Latin-1, donde la "Ñ" de un nombre viaja como
el byte 0xD1. `json.loads` sobre bytes asume UTF-8 y los rechazaba con "El
archivo no es un JSON válido", descartando compras reales.
"""
from __future__ import annotations

import json


def decodificar_texto(file_bytes: bytes) -> str:
    """
    Devuelve el contenido como texto.

    Intenta UTF-8 (tolerando BOM) y recurre a Latin-1, que nunca falla y cubre
    los acentos y la Ñ del castellano. El orden importa: probar Latin-1 primero
    convertiría silenciosamente UTF-8 legítimo en mojibake.
    """
    for codificacion in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(codificacion)
        except UnicodeDecodeError:
            continue
    # latin-1 no lanza UnicodeDecodeError, así que este punto es inalcanzable;
    # se deja el reemplazo por si cambia la lista de codificaciones.
    return file_bytes.decode("utf-8", errors="replace")


def cargar_json(file_bytes: bytes):
    """Parsea el JSON del DTE. Lanza `json.JSONDecodeError` si no es JSON."""
    return json.loads(decodificar_texto(file_bytes))
