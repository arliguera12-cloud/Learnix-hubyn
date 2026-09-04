"""
Extractor de DTEs de Compras (DTE-01/03/05/06/11).
Lógica portada de pages/2_Extractor_DTE_Compras.py sin dependencias de Streamlit.
"""
import re
import logging
from concurrent.futures import ThreadPoolExecutor

import pdfplumber

from utils.pdf_utils import (
    safe_str,
    limpiar_monto,
    extraer_y_formatear_fecha,
    extraer_texto_pdf,
)
from utils.ai_utils import (
    gemini_disponible,
    procesar_dte_con_gemini,
    es_nombre_sospechoso,
    verificar_compra_con_gemini,
    clasificar_gasto_con_ia,
)
from utils.gemini_vision import extraer_dte_con_vision, vision_disponible
from utils.qr_reader import extraer_datos_qr as _extraer_qr
from utils.mh_consulta import consultar_dte_publico, estado_doc_alerta
from utils.qa_utils import calcular_confianza
from utils.dte_layout import buscar_numero_control
from utils.constants import TIPOS_VALIDOS_COMPRAS, MAX_VALORES_LOOP_COMPRAS

MAX_VALORES_LOOP = MAX_VALORES_LOOP_COMPRAS



_log = logging.getLogger(__name__)

# Patrones que marcan dónde termina la sección EMISOR y empieza la del
# RECEPTOR/CLIENTE — usados para no confundir el nombre del proveedor con
# el del propio declarante. Algunas plantillas (p. ej. gasolineras emitidas
# por powercloud.com.sv) nunca imprimen literalmente "RECEPTOR" ni
# "CLIENTE": el emisor va sin etiqueta al inicio del documento y la única
# marca antes del bloque del receptor es el pie de verificación "Portal
# Hacienda / Código generación / Sello recibido / Número de control" — sin
# este patrón, el corte de sección no ocurría y el nombre del receptor
# (frecuentemente el propio declarante) se colaba como "sufijo legal"
# válido (S.A. DE C.V.) antes de llegar al del emisor real.
PATRONES_CORTE_RECEPTOR = [
    r'(?i)DATOS\s+DEL\s+RECEPTOR',
    r'(?i)DATOS\s+DEL\s+CLIENTE',
    r'(?i)Portal\s+Hacienda',
    r'(?i)\bRECEPTOR\b',
    r'(?i)\bCLIENTE\b',
]


def _cortar_antes_de_receptor(texto: str, estricto: bool = False) -> str | None:
    """
    Devuelve la porción de `texto` anterior a la sección RECEPTOR/CLIENTE
    según PATRONES_CORTE_RECEPTOR.

    Ignora un match de "RECEPTOR"/"CLIENTE" que sea en realidad la segunda
    palabra del encabezado de dos columnas "EMISOR RECEPTOR" en una sola
    línea, sin nada más entre medio (frecuente en la plantilla oficial de
    Hacienda) — ese encabezado antecede TODO el contenido de la tabla
    (tanto el del emisor como el del receptor), así que cortar ahí
    descartaba también los datos del propio emisor, dejando nit_prov/
    dui_prov vacíos en cualquier DTE con ese layout (encontrado con
    documentos reales de ECSA, CADELU y una factura de Baldizón).

    `estricto=True`: si no se encuentra un límite confiable, retorna None
    en vez del texto completo sin cortar. Lo usan las búsquedas "amplias"
    (p. ej. Estrategia -1, que acepta cualquier línea con sufijo legal)
    donde buscar en TODO el documento sin acotar es peligroso — en un
    layout de dos columnas por fila sin ningún límite textual real (ambas
    columnas comparten cada línea, como ECSA/CADELU/Baldizón), ese
    documento entero incluye tanto el bloque del emisor como el del
    receptor Y la sección de totales, así que una búsqueda amplia agarraba
    literalmente cualquier frase con forma de razón social ("Monto Global
    Desc., Rebajas y Otros a...", "Otros Documentos AS...") en vez de
    fallar limpio y dejar que una estrategia más conservadora (que valida
    línea por línea) lo resuelva.
    """
    for pat in PATRONES_CORTE_RECEPTOR:
        for m in re.finditer(pat, texto, re.I):
            inicio_linea = texto.rfind('\n', 0, m.start()) + 1
            antes = texto[inicio_linea:m.start()]
            # Dos falsos límites, ninguno marca el inicio real del bloque
            # receptor: el encabezado "EMISOR RECEPTOR" (ya explicado
            # arriba) y la línea de firma "Responsable por parte del
            # Receptor:" del pie del documento — sin excluir esta segunda,
            # "RECEPTOR" ahí era la ÚNICA ocurrencia no-header y quedaba
            # como límite "válido", pero tan al final que el corte incluía
            # igualmente toda la sección de totales de en medio.
            if re.search(r'(?:^\s*EMISOR|RESPONSABLE\s+POR\s+PARTE\s+DEL)\s*$', antes, re.I):
                continue
            return texto[:m.start()]
    return None if estricto else texto

PALABRAS_BASURA_NOMBRE = [
    "DOCUMENTO", "TRIBUTARIO", "ELECTRONICO", "ELECTRÓNICO",
    "REPRESENTACIÓN", "REPRESENTACION", "EMISOR", "FACTURA",
    "CONSUMIDOR", "COMPROBANTE", "CODIGO", "CÓDIGO", "SELLO",
    "VERSION", "VERSIÓN", "TRANSMISION", "TRANSMISIÓN",
    "MINISTERIO", "HACIENDA", "MUNICIPIO", "ACTIVIDAD",
    "ECONOMICA", "AGENCIA", "EFECTIVO", "HORA", "EMISIÓN",
    "EMISION", "GENERACIÓN", "GENERACION", "TELÉFONO",
    "TELEFONO", "TIPO ESTABLECIMIENTO", "ESTABLECIMIENTO",
    "CASA MATRIZ", "SUCURSAL:", "NIT:", "NRC:",
    "NUMERO DE CONTROL", "NÚMERO DE CONTROL",
    "MODELO DE FACTURACION", "TIPO DE TRANSMISION",
]

BASURA_ESTRICTA = {"@", "EMAIL", "CORREO", ".COM", "WWW.", "HTTP", "FACTURA.GOB"}

# Formas jurídicas que delatan una razón social. Se usan como pista para
# aceptar una línea corta del bloque emisor; una línea sin ellas necesita
# longitud suficiente para no confundirse con una etiqueta.
#
# Deliberadamente NO incluye palabras genéricas como "COMERCIAL" o "SERVICIOS":
# aparecen en las etiquetas del propio formulario ("Nombre comercial:",
# "Actividad económica: Servicios…") y harían pasar la etiqueta por un nombre.
# Las formas jurídicas con puntuación ya las cubre `_SUFIJO_LEGAL`; esta lista
# es solo un refuerzo para las escritas sin puntos.
PALABRAS_COMERCIALES = (
    "S.A.", "SA DE CV", "S.A. DE C.V.", "SA DE C.V.",
    "LTDA", "S. EN C.", "S.A.S.", "DE C.V.", "DE CV", "Y CIA", "CIA.",
    "ASOCIACION", "ASOCIACIÓN", "FUNDACION", "FUNDACIÓN", "COOPERATIVA",
)

PREFIJOS_DIRECCION = (
    "KM ", "KM.", "AV.", "AV ", "AVENIDA", "CALLE ", "PASAJE",
    "COLONIA", "COL.", "URB.", "URB ", "URBANIZACION", "URBANIZACIÓN",
    "RESIDENCIAL", "LOTIFICACION", "BARRIO", "CANTON", "CANTÓN",
    "CARRETERA", "CARR.", "BULEVAR", "BOULEVARD", "BLVD", "BLVD.",
    "POLIGONO", "LOCAL ", "NIVEL ", "PISO ", "EDIFICIO",
    "CENTRO COMERCIAL", "COMPLEJO", "PARQUE INDUSTRIAL",
    "FINAL ", "ENTRE ", "#", "NO.", "S/N",
)

NOMBRES_INVALIDOS = {
    "MATRIZ", "LOCAL", "SUCURSAL", "AGENCIA", "OFICINA",
    "ESTABLECIMIENTO", "PUNTO DE VENTA", "ALMACEN", "BODEGA",
}

CORTE_NOMBRE = re.compile(
    r"\s*(?:NIT|NRC|DUI|GIRO|ACTIVIDAD|DIRECCI[OÓ]N|CORREO|TEL[EÉ]F|"
    r"TIPO\s+ESTAB|MUNICIPIO|DEPARTAMENTO|DISTRITO|DEPTO|NUMERO\s+DE\s+CONTROL|"
    r"MODELO\s+(?:DE|FACTURACI)|TIPO\s+(?:DE\s+TRANS|TRANSMISI)|"
    r"CONDICI[OÓ]N|SUCURSAL|N\.?\s*I\.?\s*T\.?\s*[:\s]|"
    r"N\.?\s*R\.?\s*C\.?\s*[:\s]|N[UÚ]MERO\s+DE|REGISTRO|PROCESAMIENTO|"
    r"\d{4}[\s\-]\d{6})"
    r".*$",
    re.I | re.S,
)

def es_linea_direccion(texto: str) -> bool:
    L = safe_str(texto).upper().strip()
    return any(L.startswith(p) or (f" {p}" in L[:60]) for p in PREFIJOS_DIRECCION)

SKIP_LINEAS = re.compile(
    r'^(?:DOCUMENTO|TRIBUTARIO|ELECTR[OÓ]NICO|ELECTRONICO|COMPROBANTE|'
    r'CR[EÉ]DITO|CREDITO|FISCAL|C[OÓ]DIGO|CODIGO|SELLO|N[UÚ]MERO|NUMERO|'
    r'MODELO\s+(?:DE|FACTURACI)|M[OÓ]DULO\s+DE|TIPO\s+(?:DE|TRANSMISI)|'
    r'TRANSMISI[OÓ]N|MONEDA|VERSI[OÓ]N\s+JSON|HORA\s+EMISI|'
    r'ACTIVIDAD|CONDICI[OÓ]N|DISTRITO|DEPTO|DEPARTAMENTO|MUNICIPIO|'
    r'SUCURSAL|DIRECCI[OÓ]N|TEL[EÉ]FONO|TELEFONO|'
    r'FECHA\s*[:\s]|FECHA\s+Y\s+HORA|FECHA\s+PROCESADO|FECHA\s+EMISI|'
    r'RECEPTOR|EMISOR|CLIENTE|DTE-|VENTA\s+A\s+CUENTA|DOCUMENTOS\s+RELAC|'
    r'P[AÁ]GINA|PAGINA|VER\.|VERSI[OÓ]N|VERSION|[A-F0-9]{8}-|'
    r'\d{2}[/\-]\d{2}[/\-]\d{4}|\d{2}:\d{2}:\d{2})',
    re.I
)



def cargar_proveedores_json() -> dict:
    """
    Retorna dict combinado {nit: {nombre, nrc}} para el motor de extracción:
      - Catálogo global (proveedores_globales) como base
      - Catálogo privado de la org encima con prioridad máxima
    Compatible con el formato interno dict{nit:{nombre,nrc}} del extractor.
    """
    try:
        from utils.local_db import cargar_proveedores_combinados
        return cargar_proveedores_combinados()
    except Exception:
        return {}


def _mismo_nombre(a: str, b: str) -> bool:
    """
    ¿`a` y `b` son el mismo nombre, sin importar el orden de las palabras?

    Los DTE no siempre imprimen el nombre en el mismo orden en cada
    documento ("JONATHAN RUIZ" vs "RUIZ JONATHAN") — una comparación
    literal (`a == b` / `a.startswith(b)`) no detecta esa variante y deja
    colarse el nombre del receptor (tu cliente) como si fuera el proveedor.
    Comparar como conjunto de palabras es invariante al orden.
    """
    palabras_a = set(safe_str(a).upper().split())
    palabras_b = set(safe_str(b).upper().split())
    if not palabras_a or not palabras_b:
        return False
    return palabras_a == palabras_b


def extraer_nombre_emisor(texto: str, nit_prov: str, receptor_nombre: str) -> str:
    """
    Extrae el nombre del EMISOR (proveedor) del DTE.

    Bugs corregidos vs. versión original:
    - limpiar(): re.sub usaba `s` como patrón en lugar de "" como reemplazo.
    - Estrategia 1: el split cortaba el nombre antes de retornarlo.
    - Se agrega Estrategia 0: buscar entre sección [EMISOR] … [RECEPTOR].
    """
    texto       = safe_str(texto)
    receptor_up = safe_str(receptor_nombre).strip().upper()

    # ── Función interna de limpieza (CORREGIDA) ──────────────────────────────
    def limpiar(s: str) -> str:
        s = safe_str(s)
        # Quitar nombre del receptor si se coló. Tolerante a variantes de
        # puntuación en las siglas legales ("S.A." vs "S.A", frecuente
        # cuando el PDF real omite un punto que sí trae el nombre guardado
        # en la base del declarante) — sin esto, un layout donde emisor y
        # receptor caen en la misma línea (misma altura de fila, p. ej.
        # "CADELU, S.A. DE C.V. INDUSTRIAS FULLCHEM, S.A DE C.V") dejaba el
        # nombre del receptor pegado al del proveedor porque la comparación
        # exacta nunca encontraba ese ".", literal en un lado y ausente en
        # el otro.
        if receptor_up and len(receptor_up) > 3:
            # Se escapa palabra por palabra (no la cadena completa) y se
            # unen con "\s+": re.escape ya escapa el espacio como "\ ", y
            # reemplazar espacios sueltos por "\s+" DESPUÉS de escapar
            # corrompe ese "\ " en "\\s+" (escapa el propio backslash), que
            # ya no matchea nada — de ahí que un simple re.escape+replace
            # nunca lograra quitar el nombre del receptor de la línea.
            _tokens_receptor = [
                re.escape(tok).replace(r'\.', r'\.?') for tok in receptor_up.split()
            ]
            _patron_receptor = re.compile(r'\s+'.join(_tokens_receptor), re.I)
            s = _patron_receptor.sub("", s)
        # Cortar en segunda ocurrencia de una etiqueta de nombre (layout
        # columnar): cubre tanto "Nombre o Razón Social" como el "Nombre:"
        # corto que usan varios DTE reales (caso PIPSA — "Nombre: EMISOR
        # ... Nombre: RECEPTOR" en una sola línea porque pdfplumber no
        # detectó separación de columna) — sin este segundo patrón, el
        # nombre del receptor quedaba pegado al del emisor con la etiqueta
        # "NOMBRE:" en medio, sin cortar.
        # "RAZ[OÓ]N\s*SOCIAL" cubre el caso "NOMBRE: EMISOR RAZÓN SOCIAL:
        # RECEPTOR" (misma fila, cada parte con su propia etiqueta corta
        # distinta — no "Nombre o Razón Social" combinado) — sin él, la
        # etiqueta del receptor quedaba colgando tras quitarle su nombre y
        # el candidato entero se rechazaba en validación por parecer
        # metadata. re.I agregado: sin él, "NOMBRE"/"RECEPTOR" en
        # mayúsculas (el caso real más común) no coincidían con los
        # patrones en minúscula/con `[Nn]` inicial únicamente.
        # (?<![Oo]\s) evita que "RAZ[OÓ]N SOCIAL" dispare DENTRO de la
        # propia etiqueta compuesta "Nombre o Razón Social" (el espacio
        # entre "o" y "Razón" también satisface el `\s+` compartido) —
        # sin esta exclusión, un documento que SÍ usa la etiqueta larga
        # para ambas partes se cortaba a la mitad de su propia etiqueta,
        # antes de llegar al nombre real (caso FERRUSAL).
        partes = re.split(
            r'\s+(?:[Nn]ombre\s+[Oo]\s+[Rr]az|[Nn]ombre\s*:|(?<![Oo]\s)RAZ[OÓ]N\s*SOCIAL|RECEPTOR\b|CLIENTE\b)',
            s, maxsplit=1, flags=re.I,
        )
        s = partes[0]
        # Quitar etiquetas de campo al inicio
        # El orden importa: la alternancia se resuelve con la primera que encaja,
        # así que las etiquetas largas van antes que las cortas. Con "NOMBRE"
        # delante, "Nombre comercial: CLIDENTE" perdía solo "Nombre" y el nombre
        # del proveedor quedaba como "COMERCIAL: CLIDENTE".
        s = re.sub(
            r'^[\s\-:]*(?:DATOS\s+DEL\s+EMISOR|NOMBRE\s+O\s+RAZ[OÓ]N\s+SOCIAL|'
            r'NOMBRE\s+COMERCIAL|RAZ[OÓ]N\s*SOCIAL|NOMBRE|EMISOR)[\s:]*',
            "", s, flags=re.I,
        ).strip()
        # CORTE_NOMBRE: quitar todo desde keywords contables en adelante
        s = CORTE_NOMBRE.sub("", s).strip()   # ← CORREGIDO: .sub("", s)
        s = re.sub(r'^[-_.,;:\s]+|[-_.,;:\s]+$', "", s)
        # Quitar NIT/NRC inline
        s = re.sub(r'\b(?:NIT|NRC)\s*:?\s*[\d\-]+', '', s, flags=re.I).strip()
        s = re.sub(r'\s{2,}', ' ', s)
        return s.upper()

    # ── Validador ─────────────────────────────────────────────────────────────
    def valido(s: str) -> bool:
        T = safe_str(s).strip().upper()
        if len(T) < 4 or len(T) > 90:
            return False
        if receptor_up and (T == receptor_up or T.startswith(receptor_up[:12]) or _mismo_nombre(T, receptor_up)):
            return False
        if any(b in T for b in BASURA_ESTRICTA):
            return False
        if es_linea_direccion(T):
            return False
        if T in NOMBRES_INVALIDOS:
            return False
        digitos = sum(c.isdigit() for c in T)
        if len(T) > 0 and digitos / len(T) > 0.40:
            return False
        if re.fullmatch(r'[\d\s\-\.\/\(\)]+', T):
            return False
        if not re.search(r'[A-ZÁÉÍÓÚÑÜ]', T):
            return False
        if SKIP_LINEAS.match(T):
            return False
        # Red de seguridad: rechazar metadata fiscal (MODELO FACTURACIÓN, etc.)
        if es_nombre_sospechoso(T):
            return False
        return True

    # ── Estrategia -2 (MÁXIMA PRIORIDAD): columna izquierda por posición ──────
    # En el DTE estándar de Hacienda, emisor y receptor van en DOS columnas:
    #   Nombre o razon social:            Nombre o razon social:
    #   JULIO CÉSAR JOVEL SÁNCHEZ         JONATHAN GUILLERMO RUIZ HERNANDEZ
    #   NIT:08193003731016 NRC:965596     # NIT: 05020905931015 NRC:2774784
    # El EMISOR (proveedor) SIEMPRE es la columna IZQUIERDA. Esto funciona
    # también para personas naturales (sin sufijo legal) y evita confundir el
    # nombre del cliente (columna derecha) o truncar la razón social.
    #
    # GUARD: se busca solo antes del receptor. Sin este corte, un layout de
    # UNA sola columna (emisor primero, receptor después, cada uno con su
    # propia etiqueta "Nombre o Razón social:") encontraba la etiqueta del
    # RECEPTOR (la única con ese texto exacto) y tomaba como "nombre" la
    # línea siguiente — que en un nombre de receptor envuelto en dos líneas
    # podía ser solo el segundo apellido ("AMAYA" en vez de "OSCAR EDUARDO
    # VALDIZON AMAYA"), mientras el nombre real del emisor (sin esa
    # etiqueta, justo debajo de "DATOS DEL EMISOR") se ignoraba por completo.
    _lineas_vis = _cortar_antes_de_receptor(texto).split('\n')
    for _i, _ln in enumerate(_lineas_vis):
        # "Nombre/Razón Social" (con slash, sin espacios) es una variante
        # real tan común como "Nombre o Razón Social" — sin cubrirla, este
        # layout de dos columnas caía a estrategias más débiles que no
        # distinguen emisor de receptor (caso ESAU HERIBERTO ESCOBAR RAMOS).
        _labels = [m.start() for m in re.finditer(
            r'[Nn]ombre\s*(?:[Oo]|/)\s*[Rr]az[oó]n\s+[Ss]ocial', _ln)]
        if not _labels:
            continue
        # Línea de nombres = siguiente línea no vacía
        _nom_line = ""
        for _j in range(_i + 1, min(_i + 4, len(_lineas_vis))):
            if _lineas_vis[_j].strip():
                _nom_line = _lineas_vis[_j]
                break
        if not _nom_line:
            continue
        # Estrategia de corte (de más a menos confiable):
        # 1) Gap de 3+ espacios en la línea de nombres  →  columna izquierda
        # 2) Receptor conocido aparece en la línea      →  cortar antes de él
        # 3) Posición de la 2ª etiqueta como referencia →  si cae en espacio
        # 4) Tomar la línea completa (1 sola columna)
        _izq = _nom_line  # default: una sola columna
        if len(_labels) >= 2:
            _gap = re.search(r'\S(\s{3,})\S', _nom_line)
            if _gap:
                _izq = _nom_line[:_gap.start() + 1]
            elif receptor_up and len(receptor_up) >= 5:
                # Buscar las primeras 12 letras del receptor en la línea
                _m_rec = re.search(re.escape(receptor_up[:12]), _nom_line, re.I)
                if _m_rec:
                    _izq = _nom_line[:_m_rec.start()]
                else:
                    # Cortar en el punto medio entre las dos etiquetas
                    _mid = (_labels[0] + _labels[1]) // 2
                    if _mid < len(_nom_line):
                        _izq = _nom_line[:_mid]
            else:
                _split = _labels[1]
                if _split <= len(_nom_line) and not _nom_line[_split:_split+1].strip():
                    _izq = _nom_line[:_split]
        else:
            # Una sola etiqueta: puede haber columnas separadas con gap
            _gap = re.search(r'\S(\s{3,})\S', _nom_line)
            if _gap:
                _izq = _nom_line[:_gap.start() + 1]
        _cand = limpiar(_izq)
        if valido(_cand) and len(_cand) >= 4:
            _log.debug("extraer_nombre_emisor: estrategia=-2 (columna izq) → %s", _cand)
            return _cand

    # ── Estrategia -1 (ALTA PRIORIDAD): nombre por sufijo legal ─────────────
    # Las razones sociales salvadoreñas casi siempre terminan en una forma
    # jurídica (S.A. DE C.V., S.A., LTDA, etc.). La metadata del DTE nunca.
    # GUARD: solo busca en la sección EMISOR (antes de RECEPTOR/CLIENTE).
    _texto_emisor_sl = _cortar_antes_de_receptor(texto)
    _SUFIJO_LEGAL = re.compile(
        r'([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9&.,\- ]{2,70}?,?\s*'
        r'(?:SOCIEDAD\s+AN[OÓ]NIMA\s+DE\s+CAPITAL\s+VARIABLE|'  # SOCIEDAD ANONIMA DE CAPITAL VARIABLE
        r'S\.?\s*A\.?\s+DE\s+C\.?\s*V\.?|'          # S.A. DE C.V.
        # S.A.S.: se exige el punto tras la primera S (S\. en vez de S\.?)
        # — sin él, cualquier "s a s" suelto en prosa normal (p. ej. "...
        # documentos asociados...", donde "s aso" calza con S-A-S) también
        # matcheaba, igual que el caso "S.A." bare de abajo.
        r'S\.\s*A\.?\s*S\.?|'                           # S.A.S.
        # "S.A." con al menos un punto de los dos (ambos opcionales a la vez
        # — "S\.?\s*A\.?" sin punto alguno — hacía que CUALQUIER "s a"
        # suelto en prosa normal ("...otros a ventas...", "...menos a
        # cubrir...") calzara como razón social, agarrando fragmentos de
        # la sección de totales en vez de fallar limpio).
        r'(?:S\.A\.?|S\.?A\.)(?![A-Za-z])|'             # S.A. / S.A / SA.
        r'S\.?\s+DE\s+R\.?\s*L\.?(?:\s+DE\s+C\.?\s*V\.?)?|'  # S. DE R.L. (DE C.V.)
        r'LTDA\.?|'                                     # LTDA
        r'S\.?\s+EN\s+C\.?))',                          # S. EN C.
        re.I,
    )
    # Muchas plantillas repiten la etiqueta "Nombre:"/"Nombre Comercial:"
    # una vez por parte, en líneas separadas y SIN ningún separador de
    # RECEPTOR entre medio (p. ej. "Nombre: EMISOR" ... más abajo,
    # "Nombre Comercial: EMISOR" ... "Nombre Comercial: RECEPTOR") — la
    # 2ª aparición de esa etiqueta ya es del receptor. Sin cortar ahí, la
    # búsqueda de sufijo legal seguía de largo y alcanzaba el nombre (o su
    # línea de envoltura) del receptor.
    _NOMBRE_LABEL = re.compile(
        r'^\s*Nombre(?:\s+Comercial|\s+[Oo]\s+Raz[oó]n\s+[Ss]ocial)?\s*:', re.I,
    )
    if _texto_emisor_sl is not None:
        _lineas_sl = []
        _vistas = 0
        for _ln in _texto_emisor_sl.split('\n'):
            if _NOMBRE_LABEL.match(_ln):
                _vistas += 1
                if _vistas > 2:
                    break
            _lineas_sl.append(_ln)
        _texto_emisor_sl = '\n'.join(_lineas_sl)

    if _texto_emisor_sl is not None:
        for _ln in _texto_emisor_sl.split('\n'):
            m_sl = _SUFIJO_LEGAL.search(_ln)
            if not m_sl:
                continue
            # Un salto de 3+ espacios dentro de lo capturado es un gap de
            # columna (EMISOR|RECEPTOR lado a lado), no parte real de una
            # razón social — sin este guard, cuando el nombre del emisor
            # se envuelve a una 2ª línea que además comparte fila con la
            # 2ª línea del receptor, el prefijo no-codicioso terminaba
            # cruzando el gap para alcanzar el sufijo legal del RECEPTOR,
            # devolviendo un texto mitad-emisor mitad-receptor.
            if re.search(r'\s{3,}', m_sl.group(1)):
                continue
            # Cuando el gap de columna no sobrevive a la normalización de
            # texto_lineal (queda un solo espacio, no 3+), el guard de
            # arriba no alcanza — pero el fragmento que cruza igual
            # arranca con la cola de una forma jurídica ("Sociedad
            # Anónima de Capital Variable", "Sociedad de Responsabilidad
            # Limitada") que nunca es la PRIMERA palabra real de un
            # nombre de empresa. Si el candidato empieza así, es la
            # continuación envuelta de la línea anterior fusionada con la
            # fila del receptor, no un nombre válido.
            if re.match(
                r'\s*(?:AN[OÓ]NIMA|VARIABLE|LIMITADA|RESPONSABILIDAD|CAPITAL)\b',
                m_sl.group(1), re.I,
            ):
                continue
            candidato = limpiar(m_sl.group(1))
            if valido(candidato) and len(candidato) >= 6:
                _log.debug("extraer_nombre_emisor: estrategia=-1 (sufijo legal) → %s", candidato)
                return candidato

    # ── Estrategia 0: sección explícita [EMISOR] … [RECEPTOR] ────────────────
    # Busca un bloque etiquetado "EMISOR" y extrae el nombre dentro de él
    m_bloque = re.search(
        r'(?:DATOS\s+DEL\s+)?EMISOR\s*\n([\s\S]{10,400}?)(?:DATOS\s+DEL\s+)?(?:RECEPTOR|CLIENTE)',
        texto, re.I,
    )
    if m_bloque:
        bloque = m_bloque.group(1)
        for linea in bloque.split('\n'):
            l = safe_str(linea).strip()
            if not l or len(l) < 4:
                continue
            if SKIP_LINEAS.match(l):
                continue
            if any(b in l.upper() for b in BASURA_ESTRICTA):
                continue
            candidato = limpiar(l)
            if valido(candidato):
                _log.debug("extraer_nombre_emisor: estrategia=0 (bloque EMISOR) → %s", candidato)
                return candidato

    # ── Estrategia 1: etiqueta "Nombre o Razón Social:" (primer match = emisor)
    # CORREGIDO: tomamos group(1) directamente sin re-split innecesario
    for m_nom in re.finditer(
        r'[Nn]ombre\s*(?:[Oo]|/)\s*[Rr]az[oó]n\s+[Ss]ocial\s*:\s*([^\n]{4,120})',
        texto,
    ):
        # Ignorar si el contexto anterior indica que es sección RECEPTOR
        ctx_prev = texto[max(0, m_nom.start() - 120):m_nom.start()].upper()
        if any(w in ctx_prev for w in ['RECEPTOR', 'CLIENTE', 'DATOS DEL RECEPTOR']):
            continue
        candidato = limpiar(m_nom.group(1))
        if valido(candidato):
            _log.debug("extraer_nombre_emisor: estrategia=1 (etiqueta NRS) → %s", candidato)
            return candidato

    # ── Estrategia 2: texto antes del receptor ───────────────────────────────
    parte_emisor = _cortar_antes_de_receptor(texto)

    # ── Estrategia 3: palabras comerciales en bloque emisor ──────────────────
    for linea in parte_emisor.split('\n'):
        l = safe_str(linea).strip()
        if not l or len(l) < 4:
            continue
        if SKIP_LINEAS.match(l):
            continue
        if any(b in l.upper() for b in BASURA_ESTRICTA):
            continue
        tiene_comercial = any(w in l.upper() for w in PALABRAS_COMERCIALES)
        candidato = limpiar(l)
        if valido(candidato) and (tiene_comercial or len(candidato) >= 8):
            _log.debug("extraer_nombre_emisor: estrategia=3 (palabras comerciales) → %s", candidato)
            return candidato

    # ── Estrategia 4: primera línea no-metadata del documento ────────────────
    for linea in texto.split('\n')[:20]:
        l = safe_str(linea).strip()
        if not l or len(l) < 4:
            continue
        if SKIP_LINEAS.match(l):
            continue
        if any(b in l.upper() for b in BASURA_ESTRICTA):
            continue
        candidato = limpiar(l)
        if valido(candidato):
            _log.debug("extraer_nombre_emisor: estrategia=4 (primeras líneas) → %s", candidato)
            return candidato

    # ── Estrategia 5: líneas anteriores al NIT del proveedor ─────────────────
    if nit_prov and len(nit_prov) >= 9:
        lineas = texto.split('\n')
        for i, linea in enumerate(lineas):
            if nit_prov in re.sub(r'[^0-9]', '', linea):
                for offset in [1, 2, 3]:
                    if i - offset >= 0:
                        candidato = limpiar(lineas[i - offset].strip())
                        if valido(candidato):
                            _log.debug("extraer_nombre_emisor: estrategia=5 (cerca NIT) → %s", candidato)
                            return candidato

    _log.debug("extraer_nombre_emisor: todas las estrategias fallaron")
    return ""


def _leer_qr_y_consultar_mh(file_bytes: bytes) -> tuple[dict, dict | None]:
    """
    Lee el QR y, si trae código de generación, consulta el DTE completo en
    Hacienda — en un hilo aparte, en paralelo con Visión. Mismo patrón que
    retenciones.py/ventas.py. A diferencia de ventas.py, acá NO se usa
    `numeIdenRecep` (es el NIT del receptor/comprador — o sea, del propio
    declarante en una compra, no del proveedor) — Hacienda no expone el
    NIT del emisor/proveedor en la consulta pública, así que ese campo
    sigue dependiendo de regex/Visión/IA.
    """
    try:
        qr = _extraer_qr(file_bytes)
    except Exception:
        qr = {}
    gen = str(qr.get("codigo_generacion") or "").upper()
    fecha_qr_iso = str(qr.get("fecha_qr") or "").strip()
    consulta_mh = consultar_dte_publico(gen, fecha_qr_iso) if gen and fecha_qr_iso else None
    return qr, consulta_mh


def extraer_compra_nativo_pro(file_bytes: bytes, cliente_activo: dict, proveedores_db: dict = None) -> dict:
    """
    Extrae datos de un DTE de compra.
    Correcciones aplicadas:
    - Sello: regex sin \\b en t_no_sp (no funciona en strings sin espacios).
    - UUID fallback: separado del sello para no mezclar hex puro con alfanumérico.
    - Montos: loop de reconciliación O(n²) con índice de IVA, más rápido y preciso.
    - Sub-Total: patrón más restrictivo para no capturar subtotales de línea.
    - DTE-01 de compra: exentas = tot (sin IVA).
    """
    if not file_bytes or len(file_bytes) < 512:
        return {"error_fatal": "Archivo vacio o demasiado pequeño."}

    # ── Vision-First: extraer con IA antes de pdfplumber ─────────────────────
    _nit_rec_ctx = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nit', '')))
    _nom_rec_ctx = safe_str(cliente_activo.get('nombre', '')).strip().upper()

    gemini_correcciones: list[str] = []
    _vision_campos: dict  = {}
    _vision_alertas: list = []
    _vision_audit: dict   = {}

    # QR+Hacienda no depende del texto/regex del PDF — se lanza en un hilo
    # aparte para correr en paralelo con el parseo de texto de abajo. Visión
    # YA NO se lanza aquí sin condición: antes se disparaba para TODOS los
    # documentos de un lote, saturando el rate limit de Groq; ahora solo se
    # llama si, tras regex + QR + Hacienda, el documento sigue incompleto
    # (ver "Visión solo si Hacienda + regex no alcanzan" más abajo).
    with ThreadPoolExecutor(max_workers=1) as _pool:
        _qr_future = _pool.submit(_leer_qr_y_consultar_mh, file_bytes)
        _vision_ejecutada = False

        def _llamar_vision():
            # Único punto que invoca Visión — idempotente (si ya se llamó,
            # p. ej. en el fallback de número de control, no la repite).
            nonlocal _vision_campos, _vision_alertas, _vision_audit
            nonlocal gemini_correcciones, _vision_ejecutada
            if _vision_ejecutada or not vision_disponible():
                return
            _vision_campos, _vision_alertas, _vision_audit = extraer_dte_con_vision(
                file_bytes, "compras",
                {"nit": _nit_rec_ctx, "nombre": _nom_rec_ctx},
            )
            gemini_correcciones = [
                f"Visión: {a}" for a in _vision_alertas
            ] if _vision_alertas else (
                [f"Visión: extrajo {len(_vision_campos)} campo(s)"]
                if _vision_campos else []
            )
            _vision_ejecutada = True

        try:
            try:
                texto_lineal, texto_visual = extraer_texto_pdf(file_bytes)
            except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
                _llamar_vision()
                if not _vision_campos.get("num_control"):
                    return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
                texto_lineal = texto_visual = ""
            except Exception as e:
                if "password" in str(e).lower() or "encrypt" in str(e).lower():
                    return {"error_fatal": "PDF protegido con contraseña. Desbloquéalo antes de subir."}
                raise

            texto_completo = texto_lineal + "\n" + texto_visual

            t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
            t_no_sp = re.sub(r'\s+', '', t_clean).upper()

            # ── Número de Control DTE ─────────────────────────────────────────────
            tipo        = ""
            ctrl        = ""
            num_control = ""

            # Reconoce también el número partido por un salto de línea del PDF
            # (prefijo al final de una línea, correlativo más adelante).
            ctrl, tipo = buscar_numero_control(t_clean)
            if not ctrl:
                ctrl, tipo = buscar_numero_control(t_no_sp)

            if ctrl:
                num_control = ctrl.replace("-", "")

            if not ctrl:
                # Fallback: antes de gastar una llamada a Visión, el QR y la
                # consulta a Hacienda (ya corriendo en paralelo) también traen
                # el número de control — más barato y tan confiable como Visión.
                _qr_ctrl, _consulta_mh_ctrl = _qr_future.result()
                _ctrl_candidato = ""
                if _consulta_mh_ctrl:
                    _ctrl_candidato = safe_str(
                        ((_consulta_mh_ctrl.get("documento") or {}).get("identificacion") or {})
                        .get("numeroControl")
                    )
                if not _ctrl_candidato and _qr_ctrl.get("num_control"):
                    _ctrl_candidato = safe_str(_qr_ctrl["num_control"])
                _m_vc = re.search(r'(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})', _ctrl_candidato, re.I)
                if not _m_vc:
                    _llamar_vision()
                    _vc_ctrl = safe_str(_vision_campos.get("num_control", ""))
                    _m_vc = re.search(r'(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})', _vc_ctrl, re.I)
                if _m_vc:
                    ctrl        = _m_vc.group(1).upper()
                    tipo        = _m_vc.group(2)
                    num_control = ctrl.replace("-", "")
                else:
                    return {"error_tipo": "No se detecto Numero de Control DTE valido."}
            if tipo not in TIPOS_VALIDOS_COMPRAS:
                return {
                    "error_tipo": (
                        f"DTE-{tipo} no admitido en compras. "
                        f"Validos: {', '.join(sorted(TIPOS_VALIDOS_COMPRAS))}."
                    )
                }

            # ── Sello de Recepción ─────────────────────────────────────────────────
            # CORREGIDO: no usar \b en t_no_sp (cadena sin espacios).
            # Los sellos son ~40 chars alfanuméricos (pueden incluir Q,T,I,K…).
            sello = ""

            # Intento 1: etiqueta explícita en texto con espacios
            m_sello1 = re.search(
                r'[Ss]ello\s+(?:[Dd][Gg][Ii]|de\s+[Rr]ecepci[oó]n)\s*:?\s*([A-Z0-9]{30,50})',
                t_clean, re.I,
            )
            if m_sello1:
                sello = m_sello1.group(1)[:40]

            # Intento 2: año + 36 alfanuméricos en texto sin espacios
            # Usamos lookahead/lookbehind en lugar de \b (que no funciona correctamente en strings sin espacios)
            if not sello:
                m_sello2 = re.search(r'(?<![A-Z0-9])(20[2-3]\d[A-Z0-9]{36})(?![A-Z0-9])', t_no_sp)
                if not m_sello2:
                    m_sello2 = re.search(r'(20[2-3]\d[A-Z0-9]{36})', t_no_sp)
                if m_sello2:
                    sello = m_sello2.group(1)

            # Intento 3: buscar "SELLO" en t_no_sp y capturar lo que sigue
            if not sello:
                m_sello3 = re.search(r'SELLO[A-Z]*:?([A-Z0-9]{30,50})', t_no_sp)
                if m_sello3:
                    sello = m_sello3.group(1)[:40]

            # ── Código de Generación (UUID) ────────────────────────────────────────
            # CORREGIDO: separado completamente del sello. UUID = hex puro 8-4-4-4-12.
            gen           = ""
            UUID_PATTERN  = (
                r'([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}'
                r'-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})'
            )

            # Con etiqueta
            m_gen1 = re.search(
                r'[Cc][oó]digo\s+(?:de\s+)?[Gg]eneraci[oó]n\s*:?\s*' + UUID_PATTERN,
                t_clean,
            )
            if m_gen1:
                gen = m_gen1.group(1).upper()

            # Sin etiqueta en texto con espacios
            if not gen:
                m_gen2 = re.search(UUID_PATTERN, t_clean)
                if m_gen2:
                    gen = m_gen2.group(1).upper()

            # Fallback: buscar 32 hex puros en t_no_sp y formatear como UUID
            if not gen:
                m_gen3 = re.search(r'(?<![A-Z0-9])([0-9A-F]{32})(?![A-Z0-9])', t_no_sp)
                if m_gen3:
                    raw = m_gen3.group(1)
                    gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}".upper()

            gen_sin_guiones = gen.replace("-", "")

            # ── Fecha de emisión ────────────────────────────────────────────────────
            fecha = extraer_y_formatear_fecha(texto_lineal)
            if not fecha:
                fecha = extraer_y_formatear_fecha(texto_completo)

            # ── Datos del Receptor ─────────────────────────────────────────────────
            nit_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nit', '')))
            dui_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('dui', '')))
            nrc_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nrc', '')))
            nom_receptor = safe_str(cliente_activo.get('nombre', '')).strip().upper()
            excluir_nits = {nit_receptor, dui_receptor, nrc_receptor} - {""}

            # ── NIT del Proveedor/Emisor ───────────────────────────────────────────
            nit_prov     = ""
            dui_prov     = ""
            nom_prov     = ""
            es_nuevo     = True
            if proveedores_db is None:
                proveedores_db = cargar_proveedores_json()

            # Separar sección EMISOR del texto
            parte_emisor = _cortar_antes_de_receptor(texto_lineal)

            PATRON_NIT = re.compile(
                r'N\.?\s*I\.?\s*T\.?\s*[:\s]\s*'
                r'((?:\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d)|\d{14})',
                re.I,
            )

            # Buscar NIT con etiqueta en sección emisor
            m_nit = PATRON_NIT.search(parte_emisor)
            if m_nit:
                nit_cand = re.sub(r'[^0-9]', '', m_nit.group(1))
                if nit_cand not in excluir_nits and len(nit_cand) == 14:
                    nit_prov = nit_cand

            # Si no, buscar en todo el texto
            if not nit_prov:
                for m in PATRON_NIT.finditer(texto_completo):
                    nit_cand = re.sub(r'[^0-9]', '', m.group(1))
                    if nit_cand not in excluir_nits and len(nit_cand) == 14:
                        nit_prov = nit_cand
                        break

            # Fallback: formato DGII explícito (XXXX-XXXXXX-XXX-X) — evita capturar
            # fechas concatenadas o códigos de barras de 14 dígitos sin guiones.
            if not nit_prov:
                for m in re.finditer(
                    r'\b(\d{4}[\s\-]\d{6}[\s\-]\d{3}[\s\-]\d)\b', texto_completo
                ):
                    nit_cand = re.sub(r'[^0-9]', '', m.group(1))
                    if nit_cand not in excluir_nits and len(nit_cand) == 14:
                        nit_prov = nit_cand
                        break

            # Fallback: NIT "huérfano" (sin etiqueta "NIT:" adyacente) seguido
            # de un NRC de 6-7 dígitos en la misma línea. Ocurre en plantillas
            # de dos columnas EMISOR|RECEPTOR cuando una sección tiene más
            # líneas que la otra (p. ej. el emisor con dirección de 2 líneas):
            # las filas de pdfplumber quedan desalineadas entre columnas, la
            # etiqueta "NIT: NRC:" del emisor termina fusionada con la fila de
            # VALORES del receptor, y los valores del emisor quedan huérfanos
            # — sin su propia etiqueta — en la línea siguiente. También cubre
            # el caso "NIT: NRC: NIT: NRC:" (ambas etiquetas en una sola línea,
            # sin dígitos) seguido de los 4 valores en la línea de abajo.
            _PATRON_NIT_HUERFANO = re.compile(
                r'(?m)^\s*(\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d|\d{14})\s+(\d{6,7})\b'
            )
            if not nit_prov:
                for m in _PATRON_NIT_HUERFANO.finditer(parte_emisor):
                    nit_cand = re.sub(r'[^0-9]', '', m.group(1))
                    if nit_cand not in excluir_nits and len(nit_cand) == 14:
                        nit_prov = nit_cand
                        break

            # Mismo fallback pero sobre texto_visual (preserva la posición
            # horizontal con espacios — layout=True de pdfplumber). Cubre el
            # caso en que "EMISOR" y "RECEPTOR" comparten una sola línea de
            # encabezado ("EMISOR          RECEPTOR"): ahí no hay forma de
            # cortar texto_lineal en una sección solo-emisor porque cada fila
            # trae ambas columnas concatenadas en una sola línea de texto, y
            # el patrón huérfano de arriba (sobre parte_emisor/texto_lineal)
            # no tiene forma de distinguir la columna izquierda de la
            # derecha. En texto_visual sí — el ancla "^\s*" solo coincide si
            # los dígitos arrancan la línea, que es siempre la columna
            # izquierda (el emisor, por convención del DTE salvadoreño).
            if not nit_prov:
                for m in _PATRON_NIT_HUERFANO.finditer(texto_visual):
                    nit_cand = re.sub(r'[^0-9]', '', m.group(1))
                    if nit_cand not in excluir_nits and len(nit_cand) == 14:
                        nit_prov = nit_cand
                        break

            # DUI del proveedor (solo si no hay NIT)
            if not nit_prov:
                for m in re.finditer(r'\b(\d{8}[\s\-]?\d|\d{9})\b', parte_emisor):
                    nit_cand = re.sub(r'[^0-9]', '', m.group(0))
                    if nit_cand not in excluir_nits and len(nit_cand) == 9:
                        dui_prov = nit_cand
                        break

            # ── Nombre del Proveedor ───────────────────────────────────────────────
            id_lookup = nit_prov or dui_prov
            if id_lookup and id_lookup in proveedores_db:
                entrada = proveedores_db[id_lookup]
                nom_prov = safe_str(
                    entrada.get("nombre", "") if isinstance(entrada, dict) else entrada
                )
                es_nuevo = False

            if es_nuevo:
                nombre_encontrado = extraer_nombre_emisor(texto_lineal, nit_prov, nom_receptor)
                if not nombre_encontrado:
                    nombre_encontrado = extraer_nombre_emisor(texto_visual, nit_prov, nom_receptor)
                nom_prov = nombre_encontrado if nombre_encontrado else ""

            # ── Guard: emisor no puede ser el mismo que el receptor ──────────────
            if nit_prov and nit_prov == nit_receptor:
                nit_prov = ""
                nom_prov = ""

            # ── Aplicar Vision con prioridad sobre regex ──────────────────────────
            if _vision_campos.get("fecha"):
                fecha    = _vision_campos["fecha"]
            if _vision_campos.get("nom_prov"):
                nom_prov = _vision_campos["nom_prov"]
            if _vision_campos.get("nit_prov"):
                nit_prov = _vision_campos["nit_prov"]

            # ── FOVIAL y COTRANS ───────────────────────────────────────────────────
            # CORREGIDO: en facturas de combustible la etiqueta viene seguida de la
            # TARIFA entre paréntesis y luego el monto real, p. ej.
            #   "FOVIAL ($0.20 Ctvs. por galón) $ 0.86"
            # El patrón anterior ($? inmediato a la etiqueta) capturaba la tarifa
            # ($0.20) o nada. Ahora tomamos el ÚLTIMO monto en $ de la línea.
            fovial  = 0.0
            cotrans = 0.0
            m_fov = (
                re.search(r'[Ff][Oo][Vv][Ii][Aa][Ll][^\n]*\$\s*(\d[\d,.]*)', t_clean)
                or re.search(r'[Ff][Oo][Vv][Ii][Aa][Ll]\s*:?\s*(\d[\d,.]*)', t_clean)
            )
            m_cot = (
                re.search(r'[Cc][Oo][Tt][Rr][Aa][Nn][Ss][^\n]*\$\s*(\d[\d,.]*)', t_clean)
                or re.search(r'[Cc][Oo][Tt][Rr][Aa][Nn][Ss]\s*:?\s*(\d[\d,.]*)', t_clean)
            )
            if m_fov:
                fovial = limpiar_monto(m_fov.group(1))
            if m_cot:
                cotrans = limpiar_monto(m_cot.group(1))
            fovial_cotrans = round(fovial + cotrans, 2)

            # ── Exentas / No Sujetas ───────────────────────────────────────────────
            # "Otros montos no afectos" es la misma columna combinada
            # Exentas/No Sujetas del Anexo 3, con otro rótulo — no está
            # EXENTA (exoneración puntual de la ley) sino NO SUJETA (fuera
            # del ámbito del IVA desde el inicio, típico en un flete/gestión
            # que el proveedor solo traslada) — mismo ajuste que en
            # ventas.py, y acá cae igual en `exe` porque el Anexo 3 no
            # separa ambas columnas.
            exe = 0.0
            for pat in [
                r'[Vv]tas?\.?\s+[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Vv]entas?\s+[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Tt]otal\s+[Ee]xento\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'\b[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Oo]tros?\s+[Mm]ontos?\s+[Nn]o\s+[Aa]fectos?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'\b[Mm]ontos?\s+[Nn]o\s+[Aa]fectos?\s*:?\s*\$?\s*(\d[\d,.]+)',
            ]:
                m_exe = re.search(pat, t_clean)
                if m_exe:
                    val = limpiar_monto(m_exe.group(1))
                    if val > 0:
                        exe = val
                        break
            exe = max(exe, fovial_cotrans)

            # ── IVA Retenido ───────────────────────────────────────────────────────
            ret = 0.0
            for pat in [
                r'[Ii][Vv][Aa]\s+[Rr]etenido\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Rr]etenci[oó]n\s+[Ii][Vv][Aa]\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Rr]etenci[oó]n\s*:?\s*\$?\s*(\d[\d,.]+)',
            ]:
                m_ret = re.search(pat, t_clean)
                if m_ret:
                    ret = limpiar_monto(m_ret.group(1))
                    if ret > 0:
                        break

            # ── IVA Percibido ──────────────────────────────────────────────────────
            perc   = 0.0
            m_perc = re.search(
                r'[Ii][Vv][Aa]\s+[Pp]ercibido\s*:?\s*\$?\s*(\d[\d,.]+)', t_clean
            )
            if m_perc:
                perc = limpiar_monto(m_perc.group(1))

            # ── Total a Pagar ──────────────────────────────────────────────────────
            # Facturas de servicios (energía, agua, telecom) con mora: el
            # "Total a Pagar" incluye el saldo pendiente de PERÍODOS
            # ANTERIORES, ajeno a la base imponible de ESTE documento — el
            # crédito fiscal declarable es el de "Total del Mes" (o
            # equivalente), no el monto combinado con la deuda vieja. Si el
            # documento trae ambos rótulos, se prioriza el del mes.
            tot = 0.0
            _patrones_tot = [
                r'[Tt]otal\s+a\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Tt]otal\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Mm]onto\s+[Tt]otal\s+de\s+la\s+[Oo]peraci[oó]n\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Vv]alor\s+[Tt]otal\s+a\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Tt]OTAL\s*:?\s*\$?\s*(\d[\d,.]+)',
            ]
            if re.search(r'[Tt]otal\s+del\s+[Mm]es', t_clean):
                _patrones_tot = [
                    r'[Tt]otal\s+del\s+[Mm]es\s*:?\s*\$?\s*(\d[\d,.]+)',
                ] + _patrones_tot
            for pat in _patrones_tot:
                m_tot = re.search(pat, t_clean)
                if m_tot:
                    tot = limpiar_monto(m_tot.group(1))
                    if tot > 0:
                        break

            # ── IVA / Crédito Fiscal ───────────────────────────────────────────────
            iva = 0.0
            for pat in [
                r'[Ii]mpuesto\s+al\s+[Vv]alor\s+[Aa]gregado\s*13\s*%?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Ii]mpuesto\s+al\s+[Vv]alor\s+[Aa]gregado\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Ii][Vv][Aa]\s*13\s*%?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'13\s*%\s*[Ii][Vv][Aa]\s*:?\s*\$?\s*(\d[\d,.]+)',
                # Tolera texto intermedio entre "Débito Fiscal" y el monto, p. ej.
                # "Iva Débito Fiscal PST $1.62" (combustible / PowerCloud).
                r'[Ii][Vv][Aa]\s+[Dd][eé]bito\s+[Ff]iscal[^\d\n]*(\d[\d,.]+)',
                r'[Cc]r[eé]dito\s+[Ff]iscal\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Dd][eé]bito\s+[Ff]iscal[^\d\n]*(\d[\d,.]+)',
            ]:
                m_iva = re.search(pat, t_clean)
                if m_iva:
                    iva = limpiar_monto(m_iva.group(1))
                    if iva > 0:
                        break

            # ── Gravadas ───────────────────────────────────────────────────────────
            gra = 0.0
            for pat in [
                r'[Vv]ta\.?\s+[Gg]ravada\s+[Nn]eta\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Vv]entas?\s+[Gg]ravadas?\s+[Ll]ocales?\s*:?\s*\$?\s*(\d[\d,.]+)',
                # "Total ventas gravadas: $ 16.55" — base imponible real del CCF
                # (no confundir con "Monto total gravado", que en combustible suma
                #  FOVIAL/COTRANS/IVA e infla la base).
                r'[Tt]otal\s+[Vv]entas?\s+[Gg]ravad[ao]s?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Tt]otal\s+[Gg]ravad[ao]\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'\b[Gg]ravado\s*:?\s*(\d[\d,.]+)',
                r'[Ss]umatoria\s+de\s+[Vv]entas\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Ss]ub[\s\-]?[Tt]otal\s+(?:[Gg]ravad[ao]|[Vv]entas?)\s*:?\s*\$?\s*(\d[\d,.]+)',
                # Layouts DTE comunes
                r'[Mm]onto\s+[Ss]ujeto\s+a\s+(?:[Ii][Vv][Aa]|[Gg]ravar)\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Vv]entas\s+[Nn]etas?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Tt]otal\s+[Oo]peracion(?:es)?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Vv]alor\s+(?:de\s+)?[Vv]entas?\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Bb]ase\s+[Ii]mponible\s*:?\s*\$?\s*(\d[\d,.]+)',
                r'[Mm]onto\s+[Gg]ravado\s*:?\s*\$?\s*(\d[\d,.]+)',
            ]:
                m_grav = re.search(pat, t_clean)
                if m_grav:
                    gra = limpiar_monto(m_grav.group(1))
                    if gra > 0:
                        break

            # ── Lógica de Reconciliación ───────────────────────────────────────────
            iva_calculado = False
            encontrado    = tot > 0 and iva > 0 and gra > 0

            # DTE-01 de compra: factura de sujeto excluido, sin crédito fiscal
            if not encontrado and tipo == "01":
                iva       = 0.0
                gra       = max(round(tot - exe, 2), 0.0)
                encontrado = tot > 0

            # DTE-14: sujeto excluido (igual, sin IVA)
            if not encontrado and tipo == "14":
                iva       = 0.0
                gra       = max(round(tot - exe, 2), 0.0)
                encontrado = tot > 0

            # ── Búsqueda por consistencia matemática (O(n²) con índice IVA) ────────
            # CORREGIDO: en lugar de triple loop O(n³), construir índice de IVA
            # para buscar pares (gravadas, iva) que cumplan la relación 13%.
            if not encontrado:
                montos_raw = re.findall(
                    r'(?<![A-Z\-])(\d{1,3}(?:[,\.]\d{3})*[,\.]\d{2}|\d+\.\d{2}|\d+,\d{2})',
                    t_clean,
                )
                set_montos: set[float] = set()
                for rv in montos_raw:
                    v = limpiar_monto(rv)
                    if 0.01 < v < 1_000_000:
                        set_montos.add(round(v, 2))

                valores = sorted(list(set_montos), reverse=True)[:MAX_VALORES_LOOP]
                # Construir set para búsqueda O(1)
                set_valores = set(valores)

                for vg in valores:
                    vi_esperado = round(vg * 0.13, 2)
                    # Tolerancia ±1 centavo
                    for delta in [0, 0.01, -0.01, 0.02, -0.02]:
                        vi_cand = round(vi_esperado + delta, 2)
                        if vi_cand not in set_valores:
                            continue
                        vt_cand = round(vg + vi_cand + exe - ret + perc, 2)
                        # Buscar total dentro de ±0.10
                        for vt in valores:
                            if abs(vt - vt_cand) <= 0.10 and vt > vg:
                                gra       = vg
                                iva       = vi_cand
                                tot       = vt
                                encontrado = True
                                break
                        if encontrado:
                            break
                    if encontrado:
                        break

            # ── Ajustes finales ───────────────────────────────────────────────────
            if not encontrado:
                if tot > 0 and iva > 0 and gra == 0.0:
                    gra       = max(round(tot - iva - exe + ret - perc, 2), 0.0)
                    encontrado = True
                elif tot > 0 and iva == 0.0 and gra == 0.0 and tipo == "03":
                    gra           = round((tot - exe + ret - perc) / 1.13, 2)
                    iva           = round(tot - exe + ret - perc - gra, 2)
                    iva_calculado = True
                    encontrado    = True
                elif tot == 0.0 and gra > 0 and iva > 0:
                    tot = round(gra + iva + exe - ret + perc, 2)

            # ── Guard de consistencia fiscal (combustible / CCF) ──────────────────
            # En facturas de combustible varios totales ("Sub-Total", "Monto total
            # gravado", total - iva) incluyen FOVIAL/COTRANS y/o el propio IVA, lo
            # que infla la base gravada y produce falsos "IVA ≠ gravadas×13%".
            # El IVA al 13% es el ancla legal más confiable: si la base no cuadra
            # con él y el exceso se explica por FOVIAL/COTRANS (±IVA), derivamos la
            # base imponible real desde el IVA y movemos FOVIAL/COTRANS a exentas.
            if tipo in ("03", "05", "06") and iva > 0 and gra > 0:
                if abs(iva - round(gra * 0.13, 2)) > 0.05:
                    base_real = round(iva / 0.13, 2)
                    exceso    = round(gra - base_real, 2)
                    if (
                        fovial_cotrans > 0
                        or abs(exceso - fovial_cotrans) <= 0.05
                        or abs(exceso - (fovial_cotrans + iva)) <= 0.05
                    ):
                        gra = base_real
                        exe = max(exe, fovial_cotrans)

            gra = max(gra, 0.0)
            iva = max(iva, 0.0)
            tot = max(tot, 0.0)

            # A este punto el parseo de texto+regex ya terminó.
            if len(texto_completo.strip()) < 50 and not ctrl:
                return {"error_fatal": "PDF de imagen sin texto extraible. Usa OCR."}

            # ── Auditoría: qué método sacó cada campo ─────────────────────────────
            # Se inicializa en "regex" para todo lo que el parseo de texto ya haya
            # resuelto (aunque sea vacío/0 — de ahí "sistema" en el frontend cuando
            # ningún mecanismo posterior lo tocó); QR/Hacienda/Visión/IA pisan la
            # entrada correspondiente solo cuando de verdad cambian el valor.
            fuentes: dict[str, str] = {
                k: "regex" for k in ("fecha", "nit_prov", "nom_prov", "gra", "iva", "exe", "tot", "sello", "num_control")
            }

            # ── QR ES EL REY: sobreescribe campos con datos confiables del QR ────────
            # (leído en paralelo con Visión más arriba — aquí solo se recoge el
            # resultado, ya listo, sin volver a leer el QR ni consultar Hacienda).
            _qr, _consulta_mh = _qr_future.result()
            _fecha_qr_iso = ""
            try:
                if _qr.get("codigo_generacion"):
                    gen = _qr["codigo_generacion"].upper()
                    gen_sin_guiones = gen.replace("-", "")
                if _qr.get("num_control") and not ctrl:
                    _qc = _qr["num_control"].upper()
                    _mq = re.search(r'DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18}', _qc, re.I)
                    if _mq:
                        ctrl        = _qc
                        tipo        = _mq.group(1)
                        num_control = ctrl.replace("-", "")
                        fuentes["num_control"] = "qr"
                # NIT del emisor del QR como respaldo si regex no lo encontró
                if not nit_prov and _qr.get("nit_emisor_qr"):
                    _nq = re.sub(r'[^0-9]', '', str(_qr["nit_emisor_qr"]))
                    if len(_nq) == 14 and _nq not in excluir_nits:
                        nit_prov = _nq
                        fuentes["nit_prov"] = "qr"
                # Fecha del QR como respaldo si regex no la encontró
                if _qr.get("fecha_qr"):
                    _fecha_qr_iso = str(_qr["fecha_qr"]).strip()
                    if not fecha:
                        _mf = re.match(r'(\d{4})-(\d{2})-(\d{2})', _fecha_qr_iso)
                        if _mf:
                            fecha = f"{_mf.group(3)}/{_mf.group(2)}/{_mf.group(1)}"
                            fuentes["fecha"] = "qr"
            except Exception:
                pass

            # ── Consulta pública de Hacienda: corre ANTES que la IA a propósito —
            # es gratis y más confiable que cualquier inferencia sobre el PDF.
            # Verificado con un CCF real: resumen.totalGravada/totalExenta/
            # totalNoSuj/totalPagar. NO se usa numeIdenRecep acá — en una compra
            # ese campo es el NIT del receptor (el propio declarante), no el
            # del proveedor, así que nit_prov sigue dependiendo de regex/Visión/
            # IA/QR. La columna "Compras Exentas/No Sujetas" del Anexo 3 es una
            # sola (no separa exentas de no sujetas como sí hace ventas), así
            # que se suman ambas en `exe`.
            _mh_alerta = estado_doc_alerta(_consulta_mh)
            if _mh_alerta:
                gemini_correcciones.append(f"Hacienda: {_mh_alerta}")

            if _consulta_mh:
                _resumen_mh = (_consulta_mh.get("documento") or {}).get("resumen") or {}
                _grav_mh    = _resumen_mh.get("totalGravada")
                _exe_mh     = _resumen_mh.get("totalExenta")
                _nosuj_mh   = _resumen_mh.get("totalNoSuj")
                _tot_mh     = _resumen_mh.get("totalPagar")
                _iva_mh     = _resumen_mh.get("totalIva")
                _fovial_mh  = None
                _cotrans_mh = None
                for _trib in (_resumen_mh.get("tributos") or []):
                    _cod_trib = str(_trib.get("codigo"))
                    if _iva_mh is None and _cod_trib == "20":
                        _iva_mh = _trib.get("valor")
                    elif _cod_trib == "C3":
                        _fovial_mh = _trib.get("valor")
                    elif _cod_trib == "59":
                        _cotrans_mh = _trib.get("valor")
                if _grav_mh is not None:
                    gra = float(_grav_mh)
                    fuentes["gra"] = "hacienda"
                if _exe_mh is not None or _nosuj_mh is not None:
                    exe = float(_exe_mh or 0) + float(_nosuj_mh or 0)
                    fuentes["exe"] = "hacienda"
                # FOVIAL/COTRANS son tributos aparte en el resumen oficial de
                # Hacienda (código C3/59) — NO forman parte de totalExenta ni
                # totalNoSuj, pero SÍ están incluidos en totalPagar. Sin
                # sumarlos acá, la validación gra+exe+iva=tot queda corta por
                # exactamente el monto de FOVIAL+COTRANS y dispara "Total no
                # cuadra" en TODA factura de combustible (confirmado con
                # documentos reales de FERRUSAL: 14 alertas, todas por este
                # motivo). Se usa el valor de la propia consulta si vino en
                # tributos; si no, el ya extraído por regex del PDF más arriba.
                if _fovial_mh is not None:
                    fovial = float(_fovial_mh)
                if _cotrans_mh is not None:
                    cotrans = float(_cotrans_mh)
                exe = round(exe + fovial + cotrans, 2)
                if _tot_mh is not None:
                    tot = float(_tot_mh)
                    fuentes["tot"] = "hacienda"
                if _iva_mh is not None:
                    iva = float(_iva_mh)
                    fuentes["iva"] = "hacienda"
                if _consulta_mh.get("selloVal"):
                    sello = str(_consulta_mh["selloVal"]).upper()
                    fuentes["sello"] = "hacienda"
                gemini_correcciones.append("Hacienda: montos verificados con la consulta pública")

            # ── Visión SOLO si Hacienda + regex no alcanzan ───────────────────────
            # Antes Visión se lanzaba SIEMPRE en paralelo para cada documento del
            # lote, sin importar si ya había datos suficientes — eso saturaba el
            # rate limit de Groq cuando el lote tenía 10-20 PDFs. Ahora se calcula
            # la confianza con lo que ya se tiene (regex + QR + Hacienda) y solo
            # se gasta una llamada a Visión si el documento sigue incompleto.
            _campos_pre_vision = {
                "tipo": tipo,
                "num_control": num_control, "gen": gen, "sello": sello, "fecha": fecha,
                "nom_prov": nom_prov, "gra": gra, "tot": tot,
                # iva/exe/ret/perc no cuentan para el % de completitud, pero hacen
                # falta para que validar_montos_ventas concilie el total — sin
                # ellos "total ≠ gravadas" dispara una alerta falsa y tapa el
                # score en 60, forzando Visión aunque el documento ya esté completo.
                "iva": iva, "exe": exe, "ret": ret, "perc": perc,
            }
            _confianza_pre_vision = calcular_confianza(_campos_pre_vision, "compras")
            if _confianza_pre_vision["score"] < 85:
                _llamar_vision()
                if _vision_campos:
                    if _vision_campos.get("fecha") and not fecha:
                        fecha = _vision_campos["fecha"]
                        fuentes["fecha"] = "vision"
                    if _vision_campos.get("nom_prov") and not nom_prov:
                        nom_prov = _vision_campos["nom_prov"]
                        fuentes["nom_prov"] = "vision"
                    if _vision_campos.get("nit_prov") and not nit_prov:
                        nit_prov = _vision_campos["nit_prov"]
                        fuentes["nit_prov"] = "vision"
                    if _vision_campos.get("gravadas") and gra == 0.0:
                        gra = round(float(_vision_campos["gravadas"]), 2)
                        fuentes["gra"] = "vision"
                    if _vision_campos.get("iva") and iva == 0.0:
                        iva = round(float(_vision_campos["iva"]), 2)
                        fuentes["iva"] = "vision"
                    if _vision_campos.get("total") and tot == 0.0:
                        tot = round(float(_vision_campos["total"]), 2)
                        fuentes["tot"] = "vision"
                    if _vision_campos.get("exentas") and exe == 0.0:
                        exe = round(float(_vision_campos["exentas"]), 2)
                        fuentes["exe"] = "vision"
                    # Sello: Vision es la fuente primaria (~40 chars); regex como respaldo
                    v_sello = str(_vision_campos.get("sello_recepcion") or "").strip()
                    if len(v_sello) >= 30 and len(v_sello) <= 45 and "-" not in v_sello:
                        sello = v_sello
                        fuentes["sello"] = "vision"

            # ── Escalar a IA textual solo si la confianza está en zona gris ───────
            _campos_pre_ia = {
                "tipo": tipo,
                "num_control": num_control, "gen": gen, "sello": sello, "fecha": fecha,
                "nom_prov": nom_prov, "gra": gra, "tot": tot,
                "iva": iva, "exe": exe, "ret": ret, "perc": perc,
            }
            _confianza_pre = calcular_confianza(_campos_pre_ia, "compras")
            if 50 <= _confianza_pre["score"] < 85 and gemini_disponible():
                _campos_act = {"fecha": fecha, "nit_prov": nit_prov, "nom_prov": nom_prov}
                # texto_visual preserva columnas EMISOR|RECEPTOR — mejor para el modelo.
                # Evitar concatenar lineal+visual (duplica contenido y gasta contexto).
                _texto_ia = texto_visual if texto_visual.strip() else texto_lineal
                _corr_dict, _correcciones_ia = verificar_compra_con_gemini(
                    _texto_ia,
                    _campos_act,
                    nit_receptor,
                    nom_receptor,
                )
                gemini_correcciones += [f"IA: {c}" for c in _correcciones_ia]
                # Solo aplicar corrección si el campo estaba vacío o Groq da uno mejor
                if _corr_dict.get("fecha") and not fecha:
                    fecha    = _corr_dict["fecha"]
                    fuentes["fecha"] = "ia"
                if _corr_dict.get("nom_prov") and (not nom_prov or nom_prov == nom_receptor):
                    nom_prov = _corr_dict["nom_prov"]
                    fuentes["nom_prov"] = "ia"
                if _corr_dict.get("nit_prov") and not nit_prov:
                    nit_prov = _corr_dict["nit_prov"]
                    fuentes["nit_prov"] = "ia"
                # Montos: Groq extrae cuando regex devolvió 0
                if _corr_dict.get("gra") and gra == 0.0:
                    gra = float(_corr_dict["gra"])
                    fuentes["gra"] = "ia"
                if _corr_dict.get("iva") and iva == 0.0:
                    iva = float(_corr_dict["iva"])
                    fuentes["iva"] = "ia"
                if _corr_dict.get("exe") and exe == 0.0:
                    exe = float(_corr_dict["exe"])
                    fuentes["exe"] = "ia"
                if _corr_dict.get("tot") and tot == 0.0:
                    tot = float(_corr_dict["tot"])
                    fuentes["tot"] = "ia"

            _campos_finales = {
                "tipo": tipo,
                "num_control": num_control, "gen": gen, "sello": sello, "fecha": fecha,
                "nom_prov": nom_prov, "gra": round(gra, 2), "iva": round(iva, 2),
                "tot": round(tot, 2), "exe": round(exe, 2),
                "ret": round(ret, 2), "perc": round(perc, 2),
            }
            _confianza = calcular_confianza(_campos_finales, "compras")
            if _confianza["score"] >= 85:
                estado = "OK"
            elif _confianza["score"] >= 50:
                estado = "REVISAR"
            else:
                estado = "REVISION_MANUAL"
            _detalle_confianza = _confianza["detalle"]
            if _mh_alerta:
                # Un documento rechazado/invalidado por Hacienda nunca puede
                # quedar "OK" solo porque los campos vinieron completos.
                estado = "REVISION_MANUAL"
                _detalle_confianza = f"Hacienda: {_mh_alerta}. " + _detalle_confianza

            # Clasificación fiscal (Anexo 3, columnas Q-T) sugerida por IA a
            # partir del proveedor y el detalle del documento — reemplaza el
            # valor fijo único que antes se aplicaba a todo el lote al
            # exportar (ver routers/exportar.py). Si Groq no está disponible
            # o la clasificación no valida, se deja sin valor y el exportador
            # sigue usando el default fijo — mismo comportamiento de antes.
            _clasificacion_ia = clasificar_gasto_con_ia(nom_prov, texto_completo, tot)
            tipo_operacion = clasificacion = sector = tipo_costo_gasto = ""
            if _clasificacion_ia:
                tipo_operacion   = _clasificacion_ia["tipo_operacion"]
                clasificacion    = _clasificacion_ia["clasificacion"]
                sector           = _clasificacion_ia["sector"]
                tipo_costo_gasto = _clasificacion_ia["tipo_costo_gasto"]
                fuentes["clasificacion_gasto"] = "ia"

            return {
                "fecha"          : fecha,
                "tipo"           : tipo,
                "num_control"    : num_control,
                "num_control_raw": ctrl,
                "sello"          : sello,
                "gen"            : gen,
                "gen_sin_guiones": gen_sin_guiones,
                "nit_prov"       : nit_prov,
                "dui_prov"       : dui_prov,
                "nom_prov"       : nom_prov,
                "fuentes"        : fuentes,
                "exe"            : round(exe,  2),
                "gra"            : round(gra,  2),
                "iva"            : round(iva,  2),
                "ret"            : round(ret,  2),
                "perc"           : round(perc, 2),
                "tot"            : round(tot,  2),
                "fovial"         : round(fovial,  2),
                "cotrans"        : round(cotrans, 2),
                "tipo_operacion"  : tipo_operacion,
                "clasificacion"   : clasificacion,
                "sector"          : sector,
                "tipo_costo_gasto": tipo_costo_gasto,
                "estado"              : estado,
                "confianza"           : _confianza["score"],
                "campos_faltantes"    : _confianza["campos_faltantes"],
                "validacion_montos"   : _confianza["validacion_montos"],
                "detalle_confianza"   : _detalle_confianza,
                "iva_calc"            : iva_calculado,
                "es_nuevo"            : es_nuevo,
                "gemini_correcciones" : gemini_correcciones,
                "_vision_campos"      : _vision_campos,
                "_vision_alertas"     : _vision_alertas,
                "_vision_audit"       : _vision_audit,
            }

        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
            return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
        except Exception as err:
            return {"error_extraccion": safe_str(err)}
