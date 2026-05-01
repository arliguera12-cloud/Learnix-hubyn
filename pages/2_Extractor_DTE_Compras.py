# =============================================================
#  EXTRACTOR V10 - MOTOR PRINCIPAL DE EXTRACCION DE PDFs
#  Vinculado con: validador_tributario.py, generador_f07.py
# =============================================================

import re
import pdfplumber
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ExtractorV10")

# ─────────────────────────────────────────────────────────────
#  DATACLASS: Resultado de Extraccion
# ─────────────────────────────────────────────────────────────
@dataclass
class ResultadoExtraccion:
    # Identificacion del documento
    archivo:        str   = ""
    codgen:         str   = ""
    num_control:    str   = ""
    tipo_dte:       str   = ""

    # Datos del emisor (proveedor)
    fecha:          str   = ""
    nit_emisor:     str   = ""
    nrc_emisor:     str   = ""
    nombre_emisor:  str   = ""
    dui_emisor:     str   = ""

    # Datos del receptor
    nit_receptor:   str   = ""
    nrc_receptor:   str   = ""
    nombre_receptor:str   = ""

    # Montos tributarios
    gravado:        float = 0.0
    exento:         float = 0.0
    iva:            float = 0.0
    fovial:         float = 0.0
    cotrans:        float = 0.0
    total:          float = 0.0

    # Control de calidad
    iva_recalculado:    bool  = False
    total_recalculado:  bool  = False
    tiene_fovial:       bool  = False
    tiene_retenciones:  bool  = False
    retencion_renta:    float = 0.0
    iva_percibido:      float = 0.0
    iva_retenido:       float = 0.0
    errores:            list  = field(default_factory=list)
    advertencias:       list  = field(default_factory=list)
    metodo_extraccion:  str   = ""
    texto_crudo:        str   = ""


# ─────────────────────────────────────────────────────────────
#  PATRONES REGEX UNIFICADOS (Basados en analisis de 10 PDFs)
# ─────────────────────────────────────────────────────────────
class PatronesRegex:

    # ── IDENTIFICACION ──────────────────────────────────────
    CODGEN = re.compile(
        r'\b([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}'
        r'-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})\b'
    )

    NUM_CONTROL = re.compile(
        r'(DTE-(?:03|05|06|07|08|09|11|14|15)-[A-Z0-9]+-\d+)',
        re.IGNORECASE
    )

    TIPO_DTE = re.compile(
        r'DTE-(0[3-9]|1[0-9])-',
        re.IGNORECASE
    )

    # ── FECHA ────────────────────────────────────────────────
    FECHA = re.compile(
        r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b'
    )

    # ── NIT / NRC ─────────────────────────────────────────────
    NIT = re.compile(
        r'\b(\d{4}-\d{6}-\d{3}-\d)\b'
    )

    NRC = re.compile(
        r'NRC[:\s]*([0-9\-]+)',
        re.IGNORECASE
    )

    DUI = re.compile(
        r'\b(\d{8}-\d)\b'
    )

    # ── MONTOS TRIBUTARIOS ───────────────────────────────────
    MONTO = r'\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})'

    GRAVADO = re.compile(
        r'(?:'
        r'Suma\s+[Tt]otal\s+de\s+[Oo]peraciones'     # Docs FREUND, ECSA, Serv.Fin.
        r'|Total\s+Gravada?'                           # Doc VIDRI
        r'|Subtotal\s+Gravado'                         # Variante anterior
        r'|Compras?\s+Gravadas?'                       # Variante F-07
        r'|Venta\s+Gravada?'                           # Otra variante
        r')' +
        r'[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    EXENTO = re.compile(
        r'(?:'
        r'Ventas?\s+[Ee]xentas?'                       # Variante 1
        r'|Ventas?\s+no\s+[Ss]ujetas?'                 # Doc VIDRI
        r'|Compras?\s+[Ee]xentas?'                     # Variante F-07
        r'|[Ee]xentas?\s+o\s+[Nn]o\s+[Ss]ujetas?'    # Variante formal
        r'|[Mm]onto\s+[Ee]xento'                       # Otra variante
        r')' +
        r'[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    IVA = re.compile(
        r'(?:'
        r'Impuesto\s+al?\s+[Vv]alor\s+[Aa]gregado'   # Docs FREUND, ECSA, VIDRI
        r'|IVA\s+13\s*%'                               # Docs Serv.Fin. (IVA 13%)
        r'|D[eé]bito\s+[Ff]iscal'                      # Docs TROPIGAS
        r'|Cr[eé]dito\s+[Ff]iscal'                     # Variante CCF
        r'|Impuesto\s+IVA'                             # Variante genérica
        r')' +
        r'(?:[^\d\n]*(?:13\s*%?|\(13%\)))?' +
        r'[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    FOVIAL = re.compile(
        r'FOVIAL[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    COTRANS = re.compile(
        r'COTRANS[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    TOTAL = re.compile(
        r'(?:'
        r'TOTAL\s+A\s+PAGAR'                           # Docs anteriores
        r'|Total\s+a\s+[Pp]agar'                       # Variante mayúsculas
        r'|Monto\s+[Tt]otal\s+de\s+la\s+[Oo]peraci[oó]n'  # Docs ECSA, VIDRI
        r'|TOTAL\s+(?!otros|Otros|al\s+Valor)'        # Solo "TOTAL" (Doc VIDRI)
        r')' +
        r'[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    RETENCION_RENTA = re.compile(
        r'Retenci[oó]n\s+[Rr]enta[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    IVA_PERCIBIDO = re.compile(
        r'IVA\s+[Pp]ercib(?:ido|ido)[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    IVA_RETENIDO = re.compile(
        r'IVA\s+[Rr]eten(?:ido|ido)[^\d\n]*' + MONTO,
        re.IGNORECASE
    )


# ─────────────────────────────────────────────────────────────
#  CLASE PRINCIPAL: ExtractorV10
# ─────────────────────────────────────────────────────────────
class ExtractorV10:

    def __init__(self):
        self.px = PatronesRegex()

    # ── METODO PUBLICO PRINCIPAL ─────────────────────────────
    def extraer(self, ruta_pdf: str) -> ResultadoExtraccion:
        resultado = ResultadoExtraccion()
        resultado.archivo = Path(ruta_pdf).name

        try:
            texto = self._extraer_texto(ruta_pdf)
            if not texto or len(texto.strip()) < 50:
                resultado.errores.append("PDF sin texto extraible o muy corto")
                return resultado

            resultado.texto_crudo = texto
            self._extraer_identificacion(texto, resultado)
            self._extraer_datos_entidades(texto, resultado)
            self._extraer_montos(texto, resultado)

        except Exception as e:
            resultado.errores.append(f"Error general: {str(e)}")
            logger.error(f"Error extrayendo {ruta_pdf}: {e}")

        return resultado

    # ── EXTRACCION DE TEXTO ──────────────────────────────────
    def _extraer_texto(self, ruta_pdf: str) -> str:
        """
        Intenta extraer texto con pdfplumber primero,
        luego con PyMuPDF como fallback.
        """
        texto = ""

        # METODO 1: pdfplumber (mejor para tablas)
        try:
            with pdfplumber.open(ruta_pdf) as pdf:
                partes = []
                for pagina in pdf.pages:
                    t = pagina.extract_text()
                    if t:
                        partes.append(t)
                texto = "\n".join(partes)
            if texto.strip():
                return texto
        except Exception as e:
            logger.warning(f"pdfplumber fallo: {e}")

        # METODO 2: PyMuPDF (fallback)
        try:
            doc = fitz.open(ruta_pdf)
            partes = []
            for pagina in doc:
                partes.append(pagina.get_text("text"))
            doc.close()
            texto = "\n".join(partes)
        except Exception as e:
            logger.warning(f"PyMuPDF fallo: {e}")

        return texto

    # ── EXTRACCION: IDENTIFICACION ───────────────────────────
    def _extraer_identificacion(self, texto: str,
                                 resultado: ResultadoExtraccion):
        # CODGEN (UUID)
        m = self.px.CODGEN.search(texto)
        if m:
            resultado.codgen = m.group(1).upper()

        # Número de Control
        m = self.px.NUM_CONTROL.search(texto)
        if m:
            resultado.num_control = m.group(1).upper()

        # Tipo DTE (extrae del número de control)
        m = self.px.TIPO_DTE.search(resultado.num_control or texto)
        if m:
            resultado.tipo_dte = m.group(1)

        # Fecha (toma la PRIMERA fecha que aparece)
        for m in self.px.FECHA.finditer(texto):
            dia, mes, anio = m.group(1), m.group(2), m.group(3)
            if 1 <= int(dia) <= 31 and 1 <= int(mes) <= 12:
                resultado.fecha = f"{dia.zfill(2)}/{mes.zfill(2)}/{anio}"
                break

    # ── EXTRACCION: ENTIDADES (NIT, NRC, Nombre) ─────────────
    def _extraer_datos_entidades(self, texto: str,
                                  resultado: ResultadoExtraccion):
        nits = self.px.NIT.findall(texto)

        # Primera NIT = emisor, segunda NIT = receptor
        if len(nits) >= 1:
            resultado.nit_emisor = nits[0]
        if len(nits) >= 2:
            resultado.nit_receptor = nits[1]

        # NRC
        nrcs = self.px.NRC.findall(texto)
        if len(nrcs) >= 1:
            resultado.nrc_emisor = nrcs[0].strip()
        if len(nrcs) >= 2:
            resultado.nrc_receptor = nrcs[1].strip()

        # DUI (si existe)
        m = self.px.DUI.search(texto)
        if m:
            resultado.dui_emisor = m.group(1)

        # Nombre del emisor: busca patrón después de "Nombre:" o similar
        resultado.nombre_emisor = self._extraer_nombre_emisor(texto)
        resultado.nombre_receptor = self._extraer_nombre_receptor(texto)

    def _extraer_nombre_emisor(self, texto: str) -> str:
        patrones = [
            r'(?:Emisor|Proveedor|Razón\s+Social|Nombre\s+Comercial)'
            r'[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑA-Za-z0-9,\.\s]+(?:S\.A\.|LTDA\.|S\.A\.'
            r'\s+DE\s+C\.V\.|DE\s+C\.V\.|SOCIEDAD\s+ANONIMA)?)',
            r'^([A-ZÁÉÍÓÚÑ]{3,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,8})\s*\n',
        ]
        for patron in patrones:
            m = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
            if m:
                nombre = m.group(1).strip()
                if 4 < len(nombre) < 120:
                    return nombre
        return ""

    def _extraer_nombre_receptor(self, texto: str) -> str:
        patrones = [
            r'(?:Receptor|Cliente|Comprador)[:\s]+([A-ZÁÉÍÓÚÑA-Za-záéíóúñ]'
            r'[A-ZÁÉÍÓÚÑA-Za-záéíóúñ0-9,\.\s]+)',
        ]
        for patron in patrones:
            m = re.search(patron, texto, re.IGNORECASE)
            if m:
                nombre = m.group(1).strip().split('\n')[0]
                if 4 < len(nombre) < 120:
                    return nombre
        return ""

    # ── EXTRACCION: MONTOS TRIBUTARIOS ───────────────────────
    def _extraer_montos(self, texto: str, resultado: ResultadoExtraccion):

        def parse_monto(valor_str: str) -> float:
            """Convierte string de monto a float."""
            limpio = valor_str.replace(',', '').replace('$', '').strip()
            try:
                return round(float(limpio), 2)
            except ValueError:
                return 0.0

        # GRAVADO
        m = self.px.GRAVADO.search(texto)
        if m:
            resultado.gravado = parse_monto(m.group(1))
        else:
            resultado.advertencias.append(
                "No se encontro campo 'Gravado'. Verificar manualmente."
            )

        # EXENTO (asumir $0.00 si no existe)
        m = self.px.EXENTO.search(texto)
        if m:
            resultado.exento = parse_monto(m.group(1))
        else:
            resultado.exento = 0.0
            resultado.advertencias.append(
                "Campo 'Exento' no encontrado. Se asume $0.00"
            )

        # IVA
        m = self.px.IVA.search(texto)
        if m:
            resultado.iva = parse_monto(m.group(1))
        else:
            resultado.advertencias.append(
                "No se encontro campo 'IVA'. Se calculara automaticamente."
            )

        # FOVIAL (opcional, solo combustibles)
        m = self.px.FOVIAL.search(texto)
        if m:
            resultado.fovial = parse_monto(m.group(1))
            resultado.tiene_fovial = resultado.fovial > 0

        # COTRANS (opcional, solo combustibles)
        m = self.px.COTRANS.search(texto)
        if m:
            resultado.cotrans = parse_monto(m.group(1))

        # RETENCIONES
        m = self.px.RETENCION_RENTA.search(texto)
        if m:
            resultado.retencion_renta = parse_monto(m.group(1))
            if resultado.retencion_renta > 0:
                resultado.tiene_retenciones = True

        m = self.px.IVA_PERCIBIDO.search(texto)
        if m:
            resultado.iva_percibido = parse_monto(m.group(1))

        m = self.px.IVA_RETENIDO.search(texto)
        if m:
            resultado.iva_retenido = parse_monto(m.group(1))

        # TOTAL
        m = self.px.TOTAL.search(texto)
        if m:
            resultado.total = parse_monto(m.group(1))
        else:
            resultado.advertencias.append(
                "No se encontro campo 'Total'. Se calculara automaticamente."
            )

        # Metodo de extraccion
        resultado.metodo_extraccion = "REGEX_V10"
