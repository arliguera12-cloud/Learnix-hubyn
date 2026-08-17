"""
dte_layout.py — Lectura de los bloques EMISOR / RECEPTOR de un DTE.

Los DTE que emite Hacienda imprimen al emisor y al receptor en dos columnas,
de modo que al extraer el texto ambos identificadores caen en la misma línea:

    EMISOR                                  RECEPTOR
    Nombre: JORGE ARTURO MAGAÑA EGUIZABAL   Nombre: VICTOR ALEJANDRO RIVAS
    NIT: 01697286-7                         NIT: 0502-160984-104-0
    NRC: 228200-7                           NRC: 217691-4

    → "NIT: 01697286-7 NIT: 0502-160984-104-0"
           └ emisor          └ receptor

Buscar "el primer NIT del documento" devuelve entonces el del emisor. Este
módulo reconoce ese formato pareado y separa cada columna sin depender de
posiciones ni de encabezados con dos puntos.
"""
from __future__ import annotations

import re

# Espacio horizontal: evita que el par cruce un salto de línea y empareje
# el valor del emisor de una fila con el del receptor de la siguiente.
_H = r"[^\S\r\n]"

# "ETIQUETA: valor   ETIQUETA: valor" en una sola línea, con la misma etiqueta
# repetida — la firma inequívoca del diseño a dos columnas.
_PAREADO = re.compile(
    rf"(?im)^{_H}*(NIT|NRC|DUI){_H}*:{_H}*([0-9][0-9\-\s]*[0-9]){_H}+"
    rf"\1{_H}*:{_H}*([0-9][0-9\-\s]*[0-9]){_H}*$"
)


def _solo_digitos(valor: str) -> str:
    return re.sub(r"[^0-9]", "", valor or "")


def ids_pareados(texto: str) -> dict[str, dict[str, str]]:
    """
    Devuelve los identificadores de cada columna cuando el documento usa el
    diseño a dos columnas:

        {"emisor": {"nit": ..., "nrc": ..., "dui": ...},
         "receptor": {...}}

    Devuelve ``{}`` si el documento no tiene ese formato, para que quien llame
    pueda recurrir a su lógica anterior.
    """
    emisor: dict[str, str] = {}
    receptor: dict[str, str] = {}

    for etiqueta, izquierda, derecha in _PAREADO.findall(texto or ""):
        clave = etiqueta.lower()
        # Solo la primera aparición de cada etiqueta: las secciones de más
        # abajo del DTE ("VENTA POR CUENTA DE TERCEROS") repiten "NIT:".
        emisor.setdefault(clave, _solo_digitos(izquierda))
        receptor.setdefault(clave, _solo_digitos(derecha))

    if not receptor:
        return {}
    return {"emisor": emisor, "receptor": receptor}


def identificadores_emisor(texto: str) -> set[str]:
    """
    Identificadores del emisor tal como aparecen en el documento.

    Se usan como lista de exclusión: sirven aunque el registro del declarante
    en el directorio no los tenga todos. Es justo el caso que hacía fallar la
    extracción — el declarante estaba dado de alta con su NIT de 14 dígitos,
    pero el DTE imprime su DUI en el campo NIT, así que la exclusión por
    directorio no lo reconocía.
    """
    pares = ids_pareados(texto)
    if not pares:
        return set()
    return {v for v in pares["emisor"].values() if v}
