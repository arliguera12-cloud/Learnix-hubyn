"""
Learnix DTE Hub — Utilidades compartidas de extracción PDF.
Centraliza: safe_str, safe_extract_text, normalizar_unicode,
limpiar_monto, extraer_y_formatear_fecha, extraer_texto_pdf.
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


def safe_extract_text(page, layout: bool = False) -> str:
    try:
        return safe_str(page.extract_text(layout=layout))
    except Exception:
        try:
            return safe_str(page.extract_text())
        except Exception:
            return ""


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


# ──────────────────────────────────────────────
# MONTOS
# ──────────────────────────────────────────────

def limpiar_monto(monto_str) -> float:
    """
    Parsea cadenas de montos con separadores ambiguos.
    Soporta: 1,234.56 | 1.234,56 | 1234.56 | 1234,56 | 1234
    """
    try:
        s = re.sub(r'[^\d.,]', '', safe_str(monto_str).strip())
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
            r'(?<!\w)[Ff]echa(?!\s+[Vv]enc))'
            r'\s*:?\s*'
            r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]20[2-3]\d|20[2-3]\d[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})',
            texto_clean, re.I,
        ):
            candidatas.append((m.start(), m.group(1)))

        # Paso 2: ISO YYYY-MM-DD
        for m in re.finditer(
            r'\b(20[2-3]\d)[-\/](0[1-9]|1[0-2])[-\/]([0-2]\d|3[01])\b', texto_clean
        ):
            ctx = texto_clean[max(0, m.start() - 30):m.start()].upper()
            if not any(w in ctx for w in ['VENCE', 'LOTE', 'V:', 'EXPIRA', 'CADUCIDAD']):
                candidatas.append((m.start(), f"{m.group(3)}/{m.group(2)}/{m.group(1)}"))

        # Paso 3: DD/MM/YYYY genérico
        for m in re.finditer(
            r'\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20[2-3]\d)\b', texto_clean
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
