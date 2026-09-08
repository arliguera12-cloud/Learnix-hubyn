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


def _patron_valor(valor_limpio: str) -> re.Pattern:
    """
    Regex que encuentra `valor_limpio` (solo dígitos) dentro de un texto,
    tolerando guiones o espacios entre dígitos — así lo imprime Hacienda
    (ej. NIT "0614-150307-102-3", NRC "228200-7") — y sin matchear como
    substring de un número más largo (límite de dígito a cada lado).
    """
    cuerpo = r"[\s\-]*".join(re.escape(d) for d in valor_limpio)
    return re.compile(rf"(?<!\d){cuerpo}(?!\d)")


_CONECTORES_NOMBRE = {"DE", "DEL", "LA", "LAS", "LOS", "Y"}


def _tokens_nombre(nombre: str) -> set[str]:
    palabras = re.findall(r"[A-ZÁÉÍÓÚÑÜ]+", (nombre or "").upper())
    return {p for p in palabras if p not in _CONECTORES_NOMBRE and len(p) > 1}


def verificar_cliente_en_documento(texto: str, cliente_activo: dict, rol_esperado: str) -> tuple[bool, str]:
    """
    ¿El cliente activo (declarante) aparece en este documento EN EL ROL que
    le corresponde? `rol_esperado` es "emisor" (ventas, retenciones, sujetos
    excluidos: el declarante emite el DTE) o "receptor" (compras: el
    declarante recibe el CCF que emitió su proveedor).

    No alcanza con comprobar que el cliente esté en algún lado del
    documento: una compra de Juan Pérez (Juan como receptor) subida al
    extractor de Ventas antes pasaba igual, porque Juan sí aparece en el
    documento — nomás que del lado equivocado, y el extractor terminaba
    armando una "venta" de Juan que en realidad es una compra suya.

    Devuelve (aparece, motivo). `motivo` empieza con "aparece como" cuando
    el cliente sí está, pero del otro lado — quien llama arma con eso un
    aviso específico ("esto es una compra, no una venta") en vez del
    genérico de "no encontrado". Prioridad de identificador: NRC primero
    (el más confiable para personas naturales, ya que NIT/DUI a veces
    aparecen intercambiados), después NIT, después DUI; el nombre solo
    como último recurso.
    """
    texto = texto or ""
    if len(texto.strip()) < 20:
        # Sin capa de texto extraíble (PDF de imagen que depende de Visión):
        # no hay sobre qué validar. Mejor no bloquear que dar un falso rechazo.
        return True, ""

    identificadores = {
        campo: re.sub(r"[^0-9]", "", str(cliente_activo.get(campo, "") or ""))
        for campo in ("nrc", "nit", "dui")
    }
    identificadores = {k: v for k, v in identificadores.items() if v}

    def _coincide(columna: dict) -> bool:
        return any(columna.get(campo) == valor for campo, valor in identificadores.items())

    pares = ids_pareados(texto)
    if pares:
        rol_contrario = "receptor" if rol_esperado == "emisor" else "emisor"
        if _coincide(pares.get(rol_esperado, {})):
            return True, ""
        if _coincide(pares.get(rol_contrario, {})):
            return False, f"aparece como {rol_contrario}, no como {rol_esperado}"
        # Ninguna columna calza por número — no se descarta todavía: el
        # directorio puede tener el identificador en otro formato que el
        # documento. Sigue con la búsqueda permisiva de abajo.

    for valor in identificadores.values():
        if _patron_valor(valor).search(texto):
            return True, ""

    tokens = _tokens_nombre(str(cliente_activo.get("nombre", "") or ""))
    if len(tokens) >= 2:
        texto_up = texto.upper()
        if all(re.search(rf"\b{re.escape(t)}\b", texto_up) for t in tokens):
            return True, ""

    return False, "ausente"


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
