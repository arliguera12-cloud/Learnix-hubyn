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


# Número de control completo en una sola pieza: DTE-03-M001P001-000000000000097
_CONTROL_COMPLETO = re.compile(r"(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})", re.I)

# Solo el prefijo, cuando el correlativo quedó en otra línea:
#   "Número de control: DTE-03-S001P005-"
#   "OD EL SALVADOR LTDA, DE C.V.  000000000008829"
_CONTROL_PREFIJO = re.compile(r"DTE-(\d{2})-([A-Z0-9]{1,20})-", re.I)

# Correlativo suelto: 12 a 18 dígitos como palabra completa.
_CORRELATIVO = re.compile(r"\b(\d{12,18})\b")

# Margen para buscar el correlativo tras el prefijo. Cubre el texto de la
# columna contigua que se cuela entre ambos al extraer un PDF a dos columnas,
# sin llegar tan lejos como para capturar un número de otra sección.
_VENTANA_CORRELATIVO = 240


def buscar_numero_control(texto: str) -> tuple[str, str]:
    """
    Devuelve ``(numero_control, tipo_dte)`` o ``("", "")`` si no aparece.

    Además del número completo reconoce el caso en que el salto de línea del
    PDF parte el número en dos: el prefijo termina en guion al final de una
    línea y el correlativo aparece más adelante, a menudo detrás del texto de
    la columna vecina. Buscar solo la forma contigua descartaba esos DTE con
    "No se detectó Número de Control válido".
    """
    texto = texto or ""

    m = _CONTROL_COMPLETO.search(texto)
    if m:
        return m.group(1).upper(), m.group(2)

    for m_pref in _CONTROL_PREFIJO.finditer(texto):
        cola = texto[m_pref.end():m_pref.end() + _VENTANA_CORRELATIVO]
        m_corr = _CORRELATIVO.search(cola)
        if m_corr:
            control = f"DTE-{m_pref.group(1)}-{m_pref.group(2).upper()}-{m_corr.group(1)}"
            return control, m_pref.group(1)

    return "", ""


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
