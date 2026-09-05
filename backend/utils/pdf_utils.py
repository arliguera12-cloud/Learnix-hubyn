"""
Learnix DTE Hub — Utilidades compartidas de extracción PDF.
Centraliza: safe_str, safe_extract_text, normalizar_unicode,
limpiar_monto, extraer_y_formatear_fecha, extraer_texto_pdf,
limpiar_numero, limpiar_nit.
"""

import re
import logging
from io import BytesIO

import pdfplumber

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# PRIMITIVAS DE TEXTO
# ──────────────────────────────────────────────

def safe_str(val) -> str:
    return "" if val is None else str(val)


def limpiar_numero(num: str) -> str:
    """Elimina todo excepto dígitos. Uso: NIT, DUI, NRC."""
    return re.sub(r"[^0-9]", "", str(num))


# Alias semántico
limpiar_nit = limpiar_numero


def normalizar_unicode(texto: str) -> str:
    """Normaliza caracteres unicode problemáticos antes del matching de regex."""
    reemplazos = {
        '–': '-', '—': '-', '‒': '-',   # dashes → hyphen
        ' ': ' ', ' ': ' ', ' ': ' ',   # non-breaking spaces → space
        '’': "'", '‘': "'",                   # smart single quotes
        '“': '"', '”': '"',                   # smart double quotes
        'ﬁ': 'fi', 'ﬂ': 'fl',                # ligatures
    }
    for orig, repl in reemplazos.items():
        texto = texto.replace(orig, repl)
    return texto


# Un "palabrón" de 25+ letras seguidas sin espacio/dígito/puntuación en
# medio no ocurre en un DTE real (nombres, direcciones, giros — todo trae
# espacios) — es la firma de un PDF cuyo font/kerning hace que el
# x_tolerance por defecto de pdfplumber (3) fusione palabras adyacentes en
# una sola ("ESAUHERIBERTOESCOBARRAMOS OSCAREDUARDOVALDIZONAMAYA" en vez de
# "ESAU HERIBERTO ESCOBAR RAMOS OSCAR EDUARDO VALDIZON AMAYA") — sin
# separación entre nombres, ninguna regex de emisor/receptor puede
# distinguirlos.
_PALABRON_FUSIONADO = re.compile(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]{25,}")


def safe_extract_text(page, layout: bool = False) -> str:
    try:
        texto = safe_str(page.extract_text(layout=layout))
    except Exception:
        try:
            return safe_str(page.extract_text())
        except Exception:
            return ""
    if _PALABRON_FUSIONADO.search(texto):
        try:
            texto_ajustado = safe_str(page.extract_text(layout=layout, x_tolerance=1))
            if not _PALABRON_FUSIONADO.search(texto_ajustado):
                return texto_ajustado
        except Exception:
            pass
    return texto


# ──────────────────────────────────────────────
# EXTRACCIÓN DUAL DE PDF
# ──────────────────────────────────────────────

def extraer_texto_pdf(file_bytes: bytes) -> tuple:
    """
    Extrae texto de un PDF con dos estrategias: lineal (layout=False) y
    visual (layout=True). Intenta manejar PDFs protegidos con contraseña.

    Retorna (texto_lineal, texto_visual) ambos normalizados.
    Lanza pdfplumber.pdfminer.pdfparser.PDFSyntaxError si el PDF es inválido.
    """
    texto_lineal = ""
    texto_visual = ""

    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                return "", ""
            for page in pdf.pages:
                texto_lineal += safe_extract_text(page, layout=False) + "\n"
                try:
                    texto_visual += safe_extract_text(page, layout=True) + "\n"
                except Exception:
                    pass
    except Exception:
        # Intentar con contraseña vacía (PDFs con cifrado nominal)
        try:
            with pdfplumber.open(BytesIO(file_bytes), password="") as pdf:
                for page in pdf.pages:
                    texto_lineal += safe_extract_text(page, layout=False) + "\n"
                    try:
                        texto_visual += safe_extract_text(page, layout=True) + "\n"
                    except Exception:
                        pass
        except Exception:
            raise

    return normalizar_unicode(texto_lineal), normalizar_unicode(texto_visual)


def extraer_texto_fitz(file_bytes: bytes) -> str:
    """
    Extracción de respaldo con PyMuPDF (fitz), para cuando pdfplumber
    produce texto incompleto/desordenado en un PDF con layout inusual
    (texto superpuesto o posicionado de forma no estándar).

    Caso real: una factura de servicios (DELSUR) donde pdfplumber nunca
    llegaba a extraer la línea "Total del Mes" (el monto correcto,
    excluyendo saldo pendiente de meses anteriores) por más que el resto
    del documento sí se leyera — quedaba fuera del orden de lectura que
    pdfplumber reconstruye. fitz usa un algoritmo de extracción distinto y
    sí la capturaba.

    Nunca lanza excepción — si fitz no está instalado o falla con este
    PDF en particular, retorna "" y el llamador sigue solo con
    pdfplumber (comportamiento actual, sin regresión).
    """
    try:
        import fitz
    except Exception:
        return ""
    try:
        texto = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                texto += page.get_text() + "\n"
        return normalizar_unicode(texto)
    except Exception:
        return ""


# ──────────────────────────────────────────────
# NOMBRE DEL RECEPTOR POR COLUMNAS (anti-entrelazado)
# ──────────────────────────────────────────────

def extraer_nombre_receptor_columna(file_bytes: bytes) -> str:
    """
    Extrae el nombre / razón social del RECEPTOR usando coordenadas de columna.

    Los DTE del MH colocan EMISOR (columna izquierda) y RECEPTOR (columna
    derecha) en la misma fila. Cuando ambos nombres caen en la misma línea
    horizontal, pdfplumber entrelaza los caracteres de las dos columnas y el
    texto extraído queda ilegible (p. ej. "L A O N G Ó I N..." mezcla
    "LOGISTICA" + "ANÓNIMA"). Para evitarlo recortamos solo la columna derecha
    (el receptor) por coordenadas y extraemos su texto de forma aislada.

    Retorna el nombre en MAYÚSCULAS, o '' si no se pudo determinar con
    seguridad (en cuyo caso conviene caer al método textual heurístico).
    """
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                return ""
            page  = pdf.pages[0]
            W     = page.width
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                return ""

            # Encabezado RECEPTOR: sin él no es seguro recortar por columna
            recep = next(
                (w for w in words if w["text"].strip().upper() == "RECEPTOR"),
                None,
            )
            if not recep:
                return ""
            hdr_top   = recep["top"]
            emisor_x1 = next(
                (w["x1"] for w in words if w["text"].strip().upper() == "EMISOR"),
                None,
            )
            # Divisor entre columnas: punto medio EMISOR/RECEPTOR (tope en W/2)
            div = ((emisor_x1 + recep["x0"]) / 2) if emisor_x1 else (W / 2)
            div = min(div, W / 2)

            # Primera etiqueta NIT/DUI del receptor: delimita el bloque del
            # nombre. En Factura de Consumidor Final el receptor se
            # identifica por DUI, no por NIT — buscar solo "NIT" dejaba caer
            # el corte al valor por defecto (más abajo de la cuenta) e
            # incluía la línea "DUI: ... NRC" dentro del nombre capturado.
            nit_top = None
            for w in sorted(words, key=lambda x: x["top"]):
                if (w["top"] > hdr_top + 4 and w["x0"] >= div
                        and re.match(r"(?i)^(?:NIT|DUI)", w["text"])):
                    nit_top = w["top"]
                    break
            if nit_top is None:
                nit_top = hdr_top + 45

            top    = hdr_top + 6
            bottom = max(nit_top - 1, top + 1)
            crop   = page.crop((div, top, W, bottom))
            txt    = normalizar_unicode(crop.extract_text(x_tolerance=1.5) or "")

            # Quitar encabezado y etiquetas, dejando solo el nombre
            txt = re.sub(r"(?i)\bRECEPTOR\b", " ", txt)
            txt = re.sub(
                r"(?i)nombre(?:\s+comercial|"
                r"\s+o\s+raz[oó]n\s+social|"
                r"\s+del\s+(?:cliente|receptor|adquiriente))?\s*:?",
                " ", txt,
            )
            txt = re.sub(r"(?i)\braz[oó]n\s+social\s*:?", " ", txt)
            # Red de seguridad: si el recorte se pasó de largo e incluyó la
            # línea de identificación (NIT/DUI/NRC), cortar ahí en vez de
            # devolver el nombre pegado a esos datos.
            txt = re.split(r"(?i)\b(?:NIT|DUI|NRC)\s*:", txt, maxsplit=1)[0]
            txt = re.sub(r"\s+", " ", txt).strip(" :,-")
            return txt.upper()
    except Exception:
        log.debug("extraer_nombre_receptor_columna error", exc_info=True)
        return ""


# ──────────────────────────────────────────────
# MONTOS
# ──────────────────────────────────────────────

def limpiar_monto(monto_str) -> float:
    """
    Parsea cadenas de montos con separadores ambiguos.
    Soporta: 1,234.56 | 1.234,56 | 1234.56 | 1234,56 | 1234
    """
    try:
        # Eliminar puntuación de cierre de oración antes de parsear
        s = re.sub(r'[^\d.,]', '', safe_str(monto_str).strip().rstrip('.,;:)'))
        if not s:
            return 0.0

        n_comas  = s.count(',')
        n_puntos = s.count('.')

        if n_comas == 0 and n_puntos == 0:
            return float(s)

        # Solo una coma
        if n_comas == 1 and n_puntos == 0:
            partes = s.split(',')
            # <= 2 dígitos después de la coma → decimal europeo: 1234,56
            if len(partes[1]) <= 2:
                return float(s.replace(',', '.'))
            # 3 dígitos → miles americano: 1,234
            return float(s.replace(',', ''))

        # Solo un punto
        if n_puntos == 1 and n_comas == 0:
            partes = s.split('.')
            # 3 dígitos después del punto → miles europeo: 1.234
            if len(partes[1]) == 3:
                return float(s.replace('.', ''))
            # decimal americano estándar: 1234.56
            return float(s)

        # Múltiples separadores: el último indica el decimal
        uc = s.rfind(',')
        up = s.rfind('.')
        if uc > up:
            s = s.replace('.', '').replace(',', '.')  # europeo: 1.234.567,89
        else:
            s = s.replace(',', '')                    # americano: 1,234,567.89
        return float(s)
    except Exception:
        return 0.0


# ──────────────────────────────────────────────
# FECHA
# ──────────────────────────────────────────────

def extraer_y_formatear_fecha(texto: str) -> str:
    """
    Extrae la fecha de EMISIÓN del DTE y retorna DD/MM/YYYY.
    Ignora fechas de vencimiento (VENCE, LOTE, EXPIRA, CADUCIDAD).
    Elimina componentes de hora antes de parsear.
    """
    try:
        texto_clean = re.sub(
            r'[-\s]\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?', ' ', safe_str(texto), flags=re.I
        )
        candidatas = []

        # Paso 0: tabla DIA / MES / AÑO (formato PriceSmart y similares)
        # Acepta AÑO con o sin tilde según como lo extraiga el PDF
        for m in re.finditer(
            r'[Dd][Ii][Aa]\s+[Mm][Ee][Ss]\s+[Aa][ÑñNn][Oo]\s+'
            r'(\d{1,2})\s+(\d{1,2})\s+(20[2-3]\d)',
            texto_clean,
        ):
            dia, mes, anio = m.group(1), m.group(2), m.group(3)
            if 1 <= int(dia) <= 31 and 1 <= int(mes) <= 12:
                candidatas.append((m.start(), f"{int(dia):02d}/{int(mes):02d}/{anio}"))

        # Paso 1: etiqueta explícita de emisión (mayor prioridad)
        for m in re.finditer(
            r'(?:[Ff]echa\s+y\s+[Hh]ora\s+de\s+(?:[Gg]eneraci[oó]n|[Ee]misi[oó]n)|'
            r'[Ff]echa\s+(?:de\s+)?[Ee]misi[oó]n|[Ff]echa\s+[Gg]eneraci[oó]n|'
            r'[Ff]echa\s+[Hh]ora\s+[Ee]misi[oó]n|[Ff]echa\s+[Dd]ocumento|'
            r'(?<!\w)[Ff]echa(?!\s+[Vv]enc))'
            r'\s*:?\s*'
            r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]20[2-3]\d|20[2-3]\d[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})',
            texto_clean, re.I,
        ):
            candidatas.append((m.start(), m.group(1)))

        # Paso 1b: fecha escrita con mes en texto (ej: "02 de junio de 2024")
        _MESES = {
            'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,
            'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12,
        }
        for m in re.finditer(
            r'\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|'
            r'septiembre|octubre|noviembre|diciembre)\s+de\s+(20[2-3]\d)\b',
            texto_clean, re.I,
        ):
            ctx = texto_clean[max(0, m.start() - 30):m.start()].upper()
            if not any(w in ctx for w in ['VENCE', 'LOTE', 'EXPIRA', 'CADUCIDAD']):
                mes_num = _MESES.get(m.group(2).lower(), 0)
                if mes_num:
                    candidatas.append((m.start() - 5,
                        f"{int(m.group(1)):02d}/{mes_num:02d}/{m.group(3)}"))


        # Paso 2: ISO YYYY-MM-DD
        for m in re.finditer(
            r'\b(20[2-3]\d)[-\/](0[1-9]|1[0-2])[-\/]([0-2]\d|3[01])\b', texto_clean
        ):
            ctx = texto_clean[max(0, m.start() - 30):m.start()].upper()
            if not any(w in ctx for w in ['VENCE', 'LOTE', 'V:', 'EXPIRA', 'CADUCIDAD']):
                candidatas.append((m.start(), f"{m.group(3)}/{m.group(2)}/{m.group(1)}"))

        # Paso 3: DD/MM/YYYY genérico (permite espacios opcionales alrededor del separador)
        for m in re.finditer(
            r'\b(\d{1,2})\s*[\/\-\.]\s*(\d{1,2})\s*[\/\-\.]\s*(20[2-3]\d)\b', texto_clean
        ):
            ctx = texto_clean[max(0, m.start() - 30):m.start()].upper()
            if any(w in ctx for w in ['VENCE', 'LOTE', 'V:', 'EXPIRA', 'CADUCIDAD']):
                continue
            p1, p2, y = int(m.group(1)), int(m.group(2)), m.group(3)
            if p1 > 31 or p2 > 12:
                continue
            candidatas.append((m.start(), f"{p1:02d}/{p2:02d}/{y}"))

        candidatas.sort(key=lambda x: x[0])

        for _, fecha_str in candidatas:
            m_iso = re.match(r'(20[2-3]\d)[-\/](\d{1,2})[-\/](\d{1,2})', fecha_str)
            if m_iso:
                return f"{int(m_iso.group(3)):02d}/{int(m_iso.group(2)):02d}/{m_iso.group(1)}"
            m_dmy = re.match(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20[2-3]\d)', fecha_str)
            if m_dmy:
                return f"{int(m_dmy.group(1)):02d}/{int(m_dmy.group(2)):02d}/{m_dmy.group(3)}"
            if re.match(r'\d{2}\/\d{2}\/20\d{2}', fecha_str):
                return fecha_str
    except Exception:
        log.debug("extraer_y_formatear_fecha error", exc_info=True)
    return ""
