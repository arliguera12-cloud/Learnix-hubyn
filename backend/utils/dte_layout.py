"""
dte_layout.py — Lectura de los bloques EMISOR / RECEPTOR de un DTE.

Los DTE que emite Hacienda imprimen al emisor y al receptor en dos columnas,
de modo que al extraer el texto ambos identificadores caen en la misma línea.
El caso simple es un solo campo repetido:

    NIT: 01697286-7                         NIT: 0502-160984-104-0
           └ emisor                                └ receptor

pero el caso real más común (cualquier CCF de un contribuyente formal, que
siempre imprime NIT y NRC) intercala los dos campos de cada columna en la
misma línea:

    NIT: 0614-110169-001-1   NRC: 1937        NIT: 0509-070465-0010   NRC: 1657547
      └────── emisor ──────┘                    └──────receptor──────┘

Buscar "todas las etiquetas NIT/NRC/DUI de la línea, en orden" y partir la
lista a la mitad reconoce ambos casos: la primera mitad es siempre el
emisor, la segunda el receptor — sin depender de posiciones en el layout
del PDF ni de que sea un único campo el que se repite. Eso es `ids_pareados`.

Hay además otros dos formatos reales, más difíciles de emparejar por columna
porque el receptor no imprime NIT/NRC como tal:

1. Receptor sin NRC (persona natural, "Factura" en vez de CCF): en vez de
   "NIT:"/"NRC:" imprime "Tipo de doc. de identificación: NIT" y, en la
   línea siguiente, "N° de doc. identificación: <valor>" — ver
   `_receptor_tipo_documento`.

2. DTE de un intermediario que vende "a cuenta de terceros" (p. ej. una
   pasarela de pago facturando su comisión): no usa columnas Emisor/
   Receptor en absoluto. El emisor va en el membrete ("N.I.T. ...", "NRC
   No. ..." — sin ":" tras la etiqueta, por eso `_CAMPO_ID` no lo toca) y
   el comprador se identifica con un bloque "NOMBRE / DIRECCION / ..."
   donde NIT y NRC quedan cada uno solo en su línea — ver
   `_receptor_bloque_nombre`.

`verificar_cliente_en_documento` prueba los tres, en ese orden, antes de
caer en la búsqueda permisiva (que no distingue de qué lado aparece).
"""
from __future__ import annotations

import re

# Espacio horizontal: evita que un campo cruce un salto de línea y empareje
# el valor de una fila con el de la siguiente.
_H = r"[^\S\r\n]"

# "ETIQUETA: valor" suelto, para juntar todos los que caen en una misma
# línea y así reconstruir cada columna — ver docstring del módulo.
_CAMPO_ID = re.compile(rf"(NIT|NRC|DUI){_H}*:{_H}*([0-9][0-9\-\s]*[0-9])")


def _solo_digitos(valor: str) -> str:
    return re.sub(r"[^0-9]", "", valor or "")


def ids_pareados(texto: str) -> dict[str, dict[str, str]]:
    """
    Devuelve los identificadores de cada columna cuando el documento usa el
    diseño a dos columnas:

        {"emisor": {"nit": ..., "nrc": ..., "dui": ...},
         "receptor": {...}}

    Devuelve ``{}`` si el documento no tiene ese formato, para que quien
    llame pueda recurrir a su lógica anterior.
    """
    emisor: dict[str, str] = {}
    receptor: dict[str, str] = {}

    for linea in (texto or "").splitlines():
        campos = list(_CAMPO_ID.finditer(linea))
        # Una cantidad impar, o un único campo, no alcanza para partir la
        # línea en "columna izquierda / columna derecha" — es una mención
        # suelta (p. ej. "VENTA POR CUENTA DE TERCEROS ... NIT: X"), no el
        # bloque emisor/receptor.
        if len(campos) < 2 or len(campos) % 2 != 0:
            continue

        mitad = len(campos) // 2
        izquierda, derecha = campos[:mitad], campos[mitad:]
        etiquetas = lambda grupo: [m.group(1).upper() for m in grupo]  # noqa: E731
        if etiquetas(izquierda) != etiquetas(derecha):
            # Las etiquetas de cada mitad no calzan en el mismo orden: no es
            # el mismo campo repetido para las dos columnas, es otra cosa.
            continue

        for m in izquierda:
            emisor.setdefault(m.group(1).lower(), _solo_digitos(m.group(2)))
        for m in derecha:
            receptor.setdefault(m.group(1).lower(), _solo_digitos(m.group(2)))

    if not receptor:
        return {}
    return {"emisor": emisor, "receptor": receptor}


# "Tipo de doc. de identificación: NIT" + "N° de doc. identificación: valor"
# — formato del receptor sin NRC (persona natural). Ver docstring del módulo.
_TIPO_DOC = re.compile(
    rf"Tipo{_H}+de{_H}+doc(?:umento)?\.?{_H}+de{_H}+identificaci[oó]n{_H}*:{_H}*(NIT|NRC|DUI)",
    re.I,
)
_NUM_DOC = re.compile(
    rf"N[°ºo]\.?{_H}+de{_H}+doc(?:umento)?\.?{_H}*identificaci[oó]n{_H}*:{_H}*([0-9][0-9\-\s]*[0-9])",
    re.I,
)


def _receptor_tipo_documento(texto: str) -> dict[str, str]:
    """Ver formato 1 en el docstring del módulo."""
    lineas = (texto or "").splitlines()
    receptor: dict[str, str] = {}
    for i, linea in enumerate(lineas):
        m_tipo = _TIPO_DOC.search(linea)
        if not m_tipo:
            continue
        tipo = m_tipo.group(1).upper()
        for candidata in lineas[i:i + 3]:
            m_num = _NUM_DOC.search(candidata)
            if m_num:
                receptor[tipo.lower()] = _solo_digitos(m_num.group(1))
                break
    return receptor


# Arranca el bloque "NOMBRE / DIRECCION / ..." del formato "venta a cuenta
# de terceros" — la etiqueta corta "NOMBRE" (no "Nombre o razón social",
# que es del formato de columnas Emisor/Receptor y no trae el ID aquí).
_LINEA_NOMBRE_SIMPLE = re.compile(rf"^{_H}*NOMBRE{_H}*:{_H}*\S")

# Encabezados que cierran el bloque de identificación del comprador: de aquí
# en adelante ya no hay más campos del receptor, aunque aparezcan NIT/NRC
# sueltos más adelante (p. ej. el del tercero por cuenta de quien se vende).
_FIN_BLOQUE_NOMBRE = re.compile(
    r"OTROS DOCUMENTOS ASOCIADOS|VENTA A CUENTA DE TERCEROS|DOCUMENTOS RELACIONADOS|^\s*No{1,2}\s+CANTIDAD",
    re.I | re.M,
)


def _receptor_bloque_nombre(texto: str) -> dict[str, str]:
    """Ver formato 2 en el docstring del módulo."""
    lineas = (texto or "").splitlines()
    inicio = next((i for i, l in enumerate(lineas) if _LINEA_NOMBRE_SIMPLE.match(l)), None)
    if inicio is None:
        return {}

    receptor: dict[str, str] = {}
    for linea in lineas[inicio:inicio + 12]:
        if _FIN_BLOQUE_NOMBRE.search(linea):
            break
        campos = list(_CAMPO_ID.finditer(linea))
        if len(campos) == 1:
            m = campos[0]
            receptor.setdefault(m.group(1).lower(), _solo_digitos(m.group(2)))
    return receptor


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

    rol_contrario = "receptor" if rol_esperado == "emisor" else "emisor"

    pares = ids_pareados(texto)
    if pares:
        if _coincide(pares.get(rol_esperado, {})):
            return True, ""
        if _coincide(pares.get(rol_contrario, {})):
            return False, f"aparece como {rol_contrario}, no como {rol_esperado}"
        # Ninguna columna calza por número — no se descarta todavía: el
        # directorio puede tener el identificador en otro formato que el
        # documento. Sigue con los otros formatos y, al final, la búsqueda
        # permisiva de abajo.

    # Formatos donde solo se puede identificar al receptor (ver docstring
    # del módulo) — si el cliente aparece ahí, ya sabemos su rol real,
    # aunque no se haya podido leer el del emisor.
    for receptor_parcial in (_receptor_tipo_documento(texto), _receptor_bloque_nombre(texto)):
        if not receptor_parcial:
            continue
        if _coincide(receptor_parcial):
            if rol_esperado == "receptor":
                return True, ""
            return False, "aparece como receptor, no como emisor"

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
