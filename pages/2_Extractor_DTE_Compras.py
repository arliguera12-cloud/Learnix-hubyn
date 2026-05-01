# =============================================================
#  EXTRACTOR DTE COMPRAS V10 - INTEGRADO EN STREAMLIT
#  Formato F-07 Ministerio de Hacienda El Salvador
#  Última actualización: 2026-05-01
# =============================================================

import streamlit as st
import pandas as pd
import pdfplumber
import fitz  # PyMuPDF
import tempfile
import os
import re
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict

# ─────────────────────────────────────────────────────────────
#  CONFIGURACION STREAMLIT
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Extractor DTE Compras V10",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ExtractorV10Compras")

# ─────────────────────────────────────────────────────────────
#  CSS PERSONALIZADO
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1F3864 0%, #2E5EAA 100%);
        color: white;
        padding: 20px 30px;
        border-radius: 12px;
        margin-bottom: 24px;
        text-align: center;
    }
    .main-header h1 {
        font-size: 2rem;
        margin: 0;
        font-weight: 700;
    }
    .main-header p {
        font-size: 0.9rem;
        margin: 6px 0 0;
        opacity: 0.85;
    }
    .metric-card {
        background: #ffffff;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .badge-ok {
        background: #D1FAE5;
        color: #065F46;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-error {
        background: #FEE2E2;
        color: #991B1B;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .result-section {
        background: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 20px;
        margin-top: 16px;
    }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  DATACLASSES
# ─────────────────────────────────────────────────────────────
@dataclass
class ResultadoExtraccion:
    archivo:        str   = ""
    codgen:         str   = ""
    num_control:    str   = ""
    tipo_dte:       str   = ""
    fecha:          str   = ""
    nit_emisor:     str   = ""
    nrc_emisor:     str   = ""
    nombre_emisor:  str   = ""
    dui_emisor:     str   = ""
    nit_receptor:   str   = ""
    nrc_receptor:   str   = ""
    nombre_receptor:str   = ""
    gravado:        float = 0.0
    exento:         float = 0.0
    iva:            float = 0.0
    fovial:         float = 0.0
    cotrans:        float = 0.0
    total:          float = 0.0
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

@dataclass
class ResultadoValidacion:
    es_valido:           bool = True
    iva_corregido:       float = 0.0
    total_corregido:     float = 0.0
    iva_fue_corregido:   bool = False
    total_fue_corregido: bool = False
    errores_fatales:     List[str] = field(default_factory=list)
    advertencias:        List[str] = field(default_factory=list)

@dataclass
class FilaF07:
    fecha:           str   = ""
    tipo_doc:        str   = ""
    num_documento:   str   = ""
    nit_proveedor:   str   = ""
    nombre_proveedor:str   = ""
    exento:          float = 0.0
    gravado:         float = 0.0
    iva:             float = 0.0
    total:           float = 0.0
    dui_proveedor:   str   = ""
    tiene_errores:   bool  = False
    tiene_advertencias: bool = False
    errores:         list  = field(default_factory=list)
    advertencias:    list  = field(default_factory=list)
    archivo_origen:  str   = ""
    codgen:          str   = ""

# ─────────────────────────────────────────────────────────────
#  PATRONES REGEX
# ─────────────────────────────────────────────────────────────
class PatronesRegex:
    CODGEN = re.compile(
        r'\b([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}'
        r'-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})\b'
    )
    NUM_CONTROL = re.compile(
        r'(DTE-(?:03|05|06|07|08|09|11|14|15)-[A-Z0-9]+-\d+)',
        re.IGNORECASE
    )
    TIPO_DTE = re.compile(r'DTE-(0[3-9]|1[0-9])-', re.IGNORECASE)
    FECHA = re.compile(r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b')
    NIT = re.compile(r'\b(\d{4}-\d{6}-\d{3}-\d)\b')
    NRC = re.compile(r'NRC[:\s]*([0-9\-]+)', re.IGNORECASE)
    DUI = re.compile(r'\b(\d{8}-\d)\b')

    MONTO = r'\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})'

    GRAVADO = re.compile(
        r'(?:'
        r'Suma\s+[Tt]otal\s+de\s+[Oo]peraciones'
        r'|Total\s+Gravada?'
        r'|Subtotal\s+Gravado'
        r'|Compras?\s+Gravadas?'
        r'|Venta\s+Gravada?'
        r')' + r'[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    EXENTO = re.compile(
        r'(?:'
        r'Ventas?\s+[Ee]xentas?'
        r'|Ventas?\s+no\s+[Ss]ujetas?'
        r'|Compras?\s+[Ee]xentas?'
        r'|[Ee]xentas?\s+o\s+[Nn]o\s+[Ss]ujetas?'
        r'|[Mm]onto\s+[Ee]xento'
        r')' + r'[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    IVA = re.compile(
        r'(?:'
        r'Impuesto\s+al?\s+[Vv]alor\s+[Aa]gregado'
        r'|IVA\s+13\s*%'
        r'|D[eé]bito\s+[Ff]iscal'
        r'|Cr[eé]dito\s+[Ff]iscal'
        r'|Impuesto\s+IVA'
        r')' +
        r'(?:[^\d\n]*(?:13\s*%?|\(13%\)))?'
        r'[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    FOVIAL = re.compile(r'FOVIAL[^\d\n]*' + MONTO, re.IGNORECASE)
    COTRANS = re.compile(r'COTRANS[^\d\n]*' + MONTO, re.IGNORECASE)

    TOTAL = re.compile(
        r'(?:'
        r'TOTAL\s+A\s+PAGAR'
        r'|Total\s+a\s+[Pp]agar'
        r'|Monto\s+[Tt]otal\s+de\s+la\s+[Oo]peraci[oó]n'
        r'|TOTAL\s+(?!otros|Otros|al\s+Valor)'
        r')' + r'[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

    RETENCION_RENTA = re.compile(
        r'Retenci[oó]n\s+[Rr]enta[^\d\n]*' + MONTO,
        re.IGNORECASE
    )

# ─────────────────────────────────────────────────────────────
#  EXTRACTOR V10
# ─────────────────────────────────────────────────────────────
class ExtractorV10:
    def __init__(self):
        self.px = PatronesRegex()

    def extraer(self, ruta_pdf: str) -> ResultadoExtraccion:
        resultado = ResultadoExtraccion()
        resultado.archivo = Path(ruta_pdf).name

        try:
            texto = self._extraer_texto(ruta_pdf)
            if not texto or len(texto.strip()) < 50:
                resultado.errores.append(
                    "PDF sin texto extraible o muy corto"
                )
                return resultado

            resultado.texto_crudo = texto
            self._extraer_identificacion(texto, resultado)
            self._extraer_datos_entidades(texto, resultado)
            self._extraer_montos(texto, resultado)

        except Exception as e:
            resultado.errores.append(f"Error general: {str(e)}")
            logger.error(f"Error extrayendo: {e}")

        return resultado

    def _extraer_texto(self, ruta_pdf: str) -> str:
        texto = ""

        # Intentar con pdfplumber primero
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

        # Fallback: PyMuPDF
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

    def _extraer_identificacion(self, texto: str,
                                 resultado: ResultadoExtraccion):
        m = self.px.CODGEN.search(texto)
        if m:
            resultado.codgen = m.group(1).upper()

        m = self.px.NUM_CONTROL.search(texto)
        if m:
            resultado.num_control = m.group(1).upper()

        m = self.px.TIPO_DTE.search(resultado.num_control or texto)
        if m:
            resultado.tipo_dte = m.group(1)

        for m in self.px.FECHA.finditer(texto):
            dia, mes, anio = m.group(1), m.group(2), m.group(3)
            if 1 <= int(dia) <= 31 and 1 <= int(mes) <= 12:
                resultado.fecha = f"{dia.zfill(2)}/{mes.zfill(2)}/{anio}"
                break

    def _extraer_datos_entidades(self, texto: str,
                                  resultado: ResultadoExtraccion):
        nits = self.px.NIT.findall(texto)
        if len(nits) >= 1:
            resultado.nit_emisor = nits[0]
        if len(nits) >= 2:
            resultado.nit_receptor = nits[1]

        nrcs = self.px.NRC.findall(texto)
        if len(nrcs) >= 1:
            resultado.nrc_emisor = nrcs[0].strip()
        if len(nrcs) >= 2:
            resultado.nrc_receptor = nrcs[1].strip()

        m = self.px.DUI.search(texto)
        if m:
            resultado.dui_emisor = m.group(1)

        resultado.nombre_emisor = self._extraer_nombre_emisor(texto)
        resultado.nombre_receptor = self._extraer_nombre_receptor(texto)

    def _extraer_nombre_emisor(self, texto: str) -> str:
        patrones = [
            r'(?:Emisor|Proveedor|Razón\s+Social|Nombre)'
            r'[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑA-Za-z0-9,\.\s]+)',
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
        m = re.search(
            r'(?:Receptor|Cliente|Comprador)[:\s]+'
            r'([A-ZÁÉÍÓÚÑA-Za-záéíóúñ][A-ZÁÉÍÓÚÑA-Za-záéíóúñ0-9,\.\s]+)',
            texto, re.IGNORECASE
        )
        if m:
            nombre = m.group(1).strip().split('\n')[0]
            if 4 < len(nombre) < 120:
                return nombre
        return ""

    def _extraer_montos(self, texto: str, resultado: ResultadoExtraccion):
        def parse_monto(valor_str: str) -> float:
            limpio = valor_str.replace(',', '').replace('$', '').strip()
            try:
                return round(float(limpio), 2)
            except ValueError:
                return 0.0

        m = self.px.GRAVADO.search(texto)
        if m:
            resultado.gravado = parse_monto(m.group(1))
        else:
            resultado.advertencias.append(
                "No se encontró campo 'Gravado'. Verificar manualmente."
            )

        m = self.px.EXENTO.search(texto)
        if m:
            resultado.exento = parse_monto(m.group(1))
        else:
            resultado.exento = 0.0

        m = self.px.IVA.search(texto)
        if m:
            resultado.iva = parse_monto(m.group(1))

        m = self.px.FOVIAL.search(texto)
        if m:
            resultado.fovial = parse_monto(m.group(1))
            resultado.tiene_fovial = resultado.fovial > 0

        m = self.px.COTRANS.search(texto)
        if m:
            resultado.cotrans = parse_monto(m.group(1))

        m = self.px.RETENCION_RENTA.search(texto)
        if m:
            resultado.retencion_renta = parse_monto(m.group(1))
            resultado.tiene_retenciones = resultado.retencion_renta > 0

        m = self.px.TOTAL.search(texto)
        if m:
            resultado.total = parse_monto(m.group(1))

        resultado.metodo_extraccion = "REGEX_V10"

# ─────────────────────────────────────────────────────────────
#  VALIDADOR TRIBUTARIO
# ─────────────────────────────────────────────────────────────
class ValidadorTributario:
    TASA_IVA             = 0.13
    TOLERANCIA_IVA       = 0.05
    TOLERANCIA_TOTAL     = 0.50
    TIPOS_DTE_VALIDOS    = ["03", "05", "06", "07", "08", "09", "11", "14", "15"]

    def validar(self, r: ResultadoExtraccion) -> ResultadoValidacion:
        vr = ResultadoValidacion()
        vr.iva_corregido   = r.iva
        vr.total_corregido = r.total

        self._validar_campos_obligatorios(r, vr)
        self._validar_tipo_dte(r, vr)
        self._validar_fecha(r, vr)
        self._validar_nit_formato(r, vr)
        self._validar_iva(r, vr)
        self._validar_total(r, vr)
        self._validar_coherencia_montos(r, vr)
        self._generar_advertencias(r, vr)

        vr.es_valido = len(vr.errores_fatales) == 0
        return vr

    def _validar_campos_obligatorios(self, r: ResultadoExtraccion,
                                      vr: ResultadoValidacion):
        if not r.codgen:
            vr.errores_fatales.append(
                "CODGEN (UUID) no encontrado en el documento."
            )
        if not r.fecha:
            vr.errores_fatales.append(
                "Fecha de emisión no encontrada."
            )
        if not r.nit_emisor:
            vr.errores_fatales.append(
                "NIT del emisor no encontrado."
            )
        if r.gravado <= 0 and r.exento <= 0:
            vr.errores_fatales.append(
                "Gravado y Exento son ambos $0.00. Al menos uno debe ser > 0."
            )
        if r.total <= 0:
            vr.errores_fatales.append(
                "Total debe ser mayor a $0.00."
            )

    def _validar_tipo_dte(self, r: ResultadoExtraccion,
                           vr: ResultadoValidacion):
        if r.tipo_dte and r.tipo_dte not in self.TIPOS_DTE_VALIDOS:
            vr.errores_fatales.append(
                f"Tipo DTE '{r.tipo_dte}' no es válido."
            )

    def _validar_fecha(self, r: ResultadoExtraccion,
                        vr: ResultadoValidacion):
        if not r.fecha:
            return
        try:
            fecha = datetime.strptime(r.fecha, "%d/%m/%Y")
            año = fecha.year
            if año < 2019 or año > 2030:
                vr.advertencias.append(
                    f"Fecha {r.fecha} fuera del rango esperado (2019-2030)."
                )
        except ValueError:
            vr.errores_fatales.append(
                f"Formato de fecha inválido: '{r.fecha}'. Se esperaba DD/MM/YYYY."
            )

    def _validar_nit_formato(self, r: ResultadoExtraccion,
                               vr: ResultadoValidacion):
        patron_nit = re.compile(r'^\d{4}-\d{6}-\d{3}-\d$')
        if r.nit_emisor and not patron_nit.match(r.nit_emisor):
            vr.errores_fatales.append(
                f"Formato NIT emisor inválido: '{r.nit_emisor}'."
            )

    def _validar_iva(self, r: ResultadoExtraccion,
                      vr: ResultadoValidacion):
        if r.gravado <= 0:
            if r.iva > 0:
                vr.advertencias.append(
                    f"IVA ${r.iva:.2f} con Gravado $0.00. Inconsistente."
                )
            return

        iva_esperado = round(r.gravado * self.TASA_IVA, 2)
        diferencia   = abs(r.iva - iva_esperado)

        if r.iva == 0.0:
            vr.iva_corregido     = iva_esperado
            vr.iva_fue_corregido = True
            vr.advertencias.append(
                f"IVA no encontrado. Calculado: ${iva_esperado:.2f}"
            )
        elif diferencia > self.TOLERANCIA_IVA:
            vr.iva_corregido     = iva_esperado
            vr.iva_fue_corregido = True
            vr.advertencias.append(
                f"IVA recalculado: ${r.iva:.2f} → ${iva_esperado:.2f}"
            )
        else:
            vr.iva_corregido = r.iva

    def _validar_total(self, r: ResultadoExtraccion,
                        vr: ResultadoValidacion):
        iva_final = vr.iva_corregido
        total_esperado = round(
            r.exento + r.gravado + iva_final + r.fovial + r.cotrans, 2
        )
        diferencia = abs(r.total - total_esperado)

        if r.total == 0.0:
            vr.total_corregido     = total_esperado
            vr.total_fue_corregido = True
            vr.advertencias.append(
                f"Total no encontrado. Calculado: ${total_esperado:.2f}"
            )
        elif diferencia > self.TOLERANCIA_TOTAL:
            vr.errores_fatales.append(
                f"INCONSISTENCIA TOTAL: ${r.total:.2f} vs ${total_esperado:.2f}"
            )
        else:
            vr.total_corregido = r.total

    def _validar_coherencia_montos(self, r: ResultadoExtraccion,
                                    vr: ResultadoValidacion):
        if r.gravado > r.total > 0:
            vr.errores_fatales.append(
                f"Gravado (${r.gravado:.2f}) mayor que Total (${r.total:.2f})."
            )

        if r.exento > r.total > 0:
            vr.errores_fatales.append(
                f"Exento (${r.exento:.2f}) mayor que Total (${r.total:.2f})."
            )

        if vr.iva_corregido > r.gravado > 0:
            vr.errores_fatales.append(
                f"IVA (${vr.iva_corregido:.2f}) mayor que Gravado (${r.gravado:.2f})."
            )

    def _generar_advertencias(self, r: ResultadoExtraccion,
                               vr: ResultadoValidacion):
        if r.tiene_fovial:
            vr.advertencias.append(
                f"FOVIAL=${r.fovial:.2f} + COTRANS=${r.cotrans:.2f} (combustible)"
            )
        if r.tiene_retenciones:
            vr.advertencias.append(
                f"Retención Renta=${r.retencion_renta:.2f}"
            )
        if not r.nombre_emisor:
            vr.advertencias.append(
                "Nombre del emisor no extraído. Completar manualmente."
            )
        if r.tipo_dte == "05":
            vr.advertencias.append(
                "DTE-05 (Exportación) con IVA. Verificar exención."
            )

# ─────────────────────────────────────────────────────────────
#  GENERADOR F-07
# ─────────────────────────────────────────────────────────────
class GeneradorF07:
    COLUMNAS = [
        "A. Fecha Emision",
        "B. Clase",
        "C. Tipo Documento",
        "D. Numero Documento",
        "E. NIT/NRC Proveedor",
        "F. Nombre Proveedor",
        "G. Compras Exentas/NS",
        "H. Internacion Exenta/NS",
        "I. Importacion Exenta/NS",
        "J. Compra Gravada Local",
        "K. Internacion Gravada",
        "L. Importacion Gravada Bienes",
        "M. Importacion Gravada Servicios",
        "N. Credito Fiscal (IVA 13%)",
        "O. Total de Compra",
        "P. DUI Proveedor",
        "Q. Tipo Operacion",
        "R. Clasificacion Compra",
        "S. Sector Actividad",
        "T. Tipo Costo/Gasto",
        "U. Numero Anexo",
    ]

    def __init__(self):
        self.filas: List[FilaF07] = []

    def agregar_documento(self,
                           extraccion: ResultadoExtraccion,
                           validacion: ResultadoValidacion) -> FilaF07:
        fila = FilaF07()

        fila.archivo_origen   = extraccion.archivo
        fila.codgen           = extraccion.codgen
        fila.fecha            = extraccion.fecha
        fila.tipo_doc         = extraccion.tipo_dte or "03"
        fila.num_documento    = extraccion.codgen
        fila.nit_proveedor    = extraccion.nit_emisor
        fila.nombre_proveedor = extraccion.nombre_emisor
        fila.dui_proveedor    = extraccion.dui_emisor

        fila.exento  = round(extraccion.exento, 2)
        fila.gravado = round(extraccion.gravado, 2)
        fila.iva     = round(validacion.iva_corregido, 2)
        fila.total   = round(validacion.total_corregido, 2)

        fila.tiene_errores      = not validacion.es_valido
        fila.tiene_advertencias = len(validacion.advertencias) > 0
        fila.errores            = validacion.errores_fatales.copy()
        fila.advertencias       = validacion.advertencias.copy()

        self.filas.append(fila)
        return fila

    def generar_excel(self, ruta_salida: str,
                       periodo: str = "2025") -> Dict:
        if not self.filas:
            raise ValueError("No hay filas para generar el F-07.")

        filas_validas    = [f for f in self.filas if not f.tiene_errores]
        filas_invalidas  = [f for f in self.filas if f.tiene_errores]

        df_principal = self._crear_dataframe(filas_validas)

        with pd.ExcelWriter(ruta_salida, engine='openpyxl') as writer:
            df_principal.to_excel(
                writer, sheet_name="F-07 Compras",
                index=False
            )

            if filas_invalidas:
                df_errores = self._crear_dataframe_errores(filas_invalidas)
                df_errores.to_excel(
                    writer, sheet_name="Errores",
                    index=False
                )

            df_resumen = self._crear_dataframe_resumen(filas_validas, periodo)
            df_resumen.to_excel(
                writer, sheet_name="Resumen",
                index=False
            )

        return self._calcular_estadisticas(
            filas_validas, filas_invalidas, ruta_salida
        )

    def _crear_dataframe(self, filas: List[FilaF07]) -> pd.DataFrame:
        registros = []
        for fila in filas:
            registro = {
                "A. Fecha Emision":       fila.fecha,
                "B. Clase":               4,
                "C. Tipo Documento":      fila.tipo_doc,
                "D. Numero Documento":    fila.num_documento,
                "E. NIT/NRC Proveedor":   fila.nit_proveedor,
                "F. Nombre Proveedor":    fila.nombre_proveedor,
                "G. Compras Exentas/NS":  fila.exento,
                "H. Internacion Exenta/NS": 0.00,
                "I. Importacion Exenta/NS": 0.00,
                "J. Compra Gravada Local": fila.gravado,
                "K. Internacion Gravada": 0.00,
                "L. Importacion Gravada Bienes": 0.00,
                "M. Importacion Gravada Servicios": 0.00,
                "N. Credito Fiscal (IVA 13%)": fila.iva,
                "O. Total de Compra":     fila.total,
                "P. DUI Proveedor":       fila.dui_proveedor or "",
                "Q. Tipo Operacion":      1,
                "R. Clasificacion Compra": 1,
                "S. Sector Actividad":    1,
                "T. Tipo Costo/Gasto":    1,
                "U. Numero Anexo":        3,
            }
            registros.append(registro)

        df = pd.DataFrame(registros, columns=self.COLUMNAS)

        fila_totales = {col: "" for col in self.COLUMNAS}
        fila_totales["A. Fecha Emision"]           = "TOTALES"
        fila_totales["G. Compras Exentas/NS"]       = df["G. Compras Exentas/NS"].sum()
        fila_totales["J. Compra Gravada Local"]     = df["J. Compra Gravada Local"].sum()
        fila_totales["N. Credito Fiscal (IVA 13%)"] = df["N. Credito Fiscal (IVA 13%)"].sum()
        fila_totales["O. Total de Compra"]          = df["O. Total de Compra"].sum()

        df_totales = pd.DataFrame([fila_totales])
        df = pd.concat([df, df_totales], ignore_index=True)

        return df

    def _crear_dataframe_errores(self, filas: List[FilaF07]) -> pd.DataFrame:
        if not filas:
            return pd.DataFrame()

        registros = []
        for fila in filas:
            registro = {
                "Archivo":          fila.archivo_origen,
                "CODGEN":           fila.codgen,
                "Fecha":            fila.fecha,
                "NIT Proveedor":    fila.nit_proveedor,
                "Nombre Proveedor": fila.nombre_proveedor,
                "Gravado":          fila.gravado,
                "IVA":              fila.iva,
                "Total":            fila.total,
                "Errores":          " | ".join(fila.errores),
                "Advertencias":     " | ".join(fila.advertencias),
            }
            registros.append(registro)

        return pd.DataFrame(registros)

    def _crear_dataframe_resumen(self, filas: List[FilaF07],
                                  periodo: str) -> pd.DataFrame:
        if not filas:
            return pd.DataFrame()

        total_exento  = sum(f.exento for f in filas)
        total_gravado = sum(f.gravado for f in filas)
        total_iva     = sum(f.iva for f in filas)
        total_compras = sum(f.total for f in filas)
        total_docs    = len(filas)

        resumen = [
            {"Campo": "Periodo Fiscal",            "Valor": periodo},
            {"Campo": "Total Documentos",           "Valor": total_docs},
            {"Campo": "Total Compras Exentas",     "Valor": f"${total_exento:,.2f}"},
            {"Campo": "Total Compras Gravadas",    "Valor": f"${total_gravado:,.2f}"},
            {"Campo": "Total Credito Fiscal",      "Valor": f"${total_iva:,.2f}"},
            {"Campo": "Total General Compras",     "Valor": f"${total_compras:,.2f}"},
            {"Campo": "Promedio por Documento",    "Valor": f"${total_compras/total_docs:,.2f}" if total_docs else "$0.00"},
            {"Campo": "Tasa IVA Aplicada",         "Valor": "13%"},
        ]

        return pd.DataFrame(resumen)

    def _calcular_estadisticas(self,
                                validas: List[FilaF07],
                                invalidas: List[FilaF07],
                                ruta_salida: str) -> Dict:
        return {
            "total_procesados":    len(validas) + len(invalidas),
            "total_validos":       len(validas),
            "total_invalidos":     len(invalidas),
            "total_exento":        round(sum(f.exento for f in validas), 2),
            "total_gravado":       round(sum(f.gravado for f in validas), 2),
            "total_iva":           round(sum(f.iva for f in validas), 2),
            "total_compras":       round(sum(f.total for f in validas), 2),
            "ruta_excel":          ruta_salida,
            "tasa_exito":          round(
                len(validas) / max(len(validas) + len(invalidas), 1) * 100, 1
            ),
        }

    def limpiar(self):
        self.filas = []

# ─────────────────────────────────────────────────────────────
#  INICIALIZACION SESSION STATE
# ─────────────────────────────────────────────────────────────
def inicializar_estado():
    if "resultados"    not in st.session_state:
        st.session_state.resultados    = []
    if "generador"     not in st.session_state:
        st.session_state.generador     = GeneradorF07()
    if "periodo"       not in st.session_state:
        st.session_state.periodo       = str(datetime.now().year)

inicializar_estado()

@st.cache_resource
def get_extractor():
    return ExtractorV10()

@st.cache_resource
def get_validador():
    return ValidadorTributario()

extractor = get_extractor()
validador = get_validador()

# ─────────────────────────────────────────────────────────────
#  FUNCIONES AUXILIARES
# ─────────────────────────────────────────────────────────────
def procesar_pdf(archivo_bytes: bytes, nombre_archivo: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(archivo_bytes)
        ruta_tmp = tmp.name

    try:
        extraccion = extractor.extraer(ruta_tmp)
        extraccion.archivo = nombre_archivo

        validacion = validador.validar(extraccion)

        fila = st.session_state.generador.agregar_documento(
            extraccion, validacion
        )

        return {
            "nombre":         nombre_archivo,
            "extraccion":     extraccion,
            "validacion":     validacion,
            "fila":           fila,
            "es_valido":      validacion.es_valido,
            "errores":        validacion.errores_fatales,
            "advertencias":   validacion.advertencias,
        }
    finally:
        os.unlink(ruta_tmp)

# ─────────────────────────────────────────────────────────────
#  INTERFAZ PRINCIPAL
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>📊 Extractor DTE Compras V10</h1>
    <p>Formato F-07 | Ministerio de Hacienda El Salvador</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    st.divider()

    periodo = st.text_input(
        "Período Fiscal (Año)",
        value=st.session_state.periodo,
        max_chars=4,
    )
    st.session_state.periodo = periodo

    st.divider()

    if st.button("🔄 Limpiar Todo", use_container_width=True):
        st.session_state.resultados = []
        st.session_state.generador  = GeneradorF07()
        st.rerun()

# Sección: Carga de PDFs
st.subheader("1️⃣ Cargar Documentos PDF")

archivos_subidos = st.file_uploader(
    "Selecciona PDF de DTE (CCF, Facturas, etc.)",
    type=["pdf"],
    accept_multiple_files=True,
)

if archivos_subidos:
    col1, col2 = st.columns(2)
    with col1:
        procesar = st.button(
            f"▶️ Procesar {len(archivos_subidos)} PDFs",
            type="primary",
            use_container_width=True,
        )

    if procesar:
        st.session_state.resultados = []
        st.session_state.generador  = GeneradorF07()

        barra = st.progress(0)
        total = len(archivos_subidos)

        for i, archivo in enumerate(archivos_subidos):
            barra.progress((i + 1) / total)
            try:
                resultado = procesar_pdf(archivo.read(), archivo.name)
                st.session_state.resultados.append(resultado)
            except Exception as e:
                st.session_state.resultados.append({
                    "nombre":       archivo.name,
                    "es_valido":    False,
                    "errores":      [str(e)],
                    "advertencias": [],
                })

        barra.empty()
        st.success(
            f"✅ Procesados {total} documentos"
        )
        st.rerun()

# Mostrar resultados
if st.session_state.resultados:
    st.divider()
    st.subheader("2️⃣ Resumen del Lote")

    n_total   = len(st.session_state.resultados)
    n_validos = sum(1 for r in st.session_state.resultados if r["es_valido"])
    n_errores = n_total - n_validos

    totales = {
        "exento":  sum(r["fila"].exento for r in st.session_state.resultados if r.get("fila")),
        "gravado": sum(r["fila"].gravado for r in st.session_state.resultados if r.get("fila")),
        "iva":     sum(r["fila"].iva for r in st.session_state.resultados if r.get("fila")),
        "total":   sum(r["fila"].total for r in st.session_state.resultados if r.get("fila")),
    }

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Docs", n_total)
    c2.metric("Válidos", n_validos)
    c3.metric("Gravado", f"${totales['gravado']:,.2f}")
    c4.metric("IVA", f"${totales['iva']:,.2f}")
    c5.metric("Total", f"${totales['total']:,.2f}")

    # Tabla de resultados
    st.divider()
    st.subheader("3️⃣ Documentos Procesados")

    datos_tabla = []
    for r in st.session_state.resultados:
        if r.get("fila"):
            fila = r["fila"]
            datos_tabla.append({
                "Status": "✅" if r["es_valido"] else "❌",
                "Archivo": r["nombre"][:35],
                "Fecha": fila.fecha,
                "NIT": fila.nit_proveedor,
                "Proveedor": fila.nombre_proveedor[:30],
                "Gravado": f"${fila.gravado:,.2f}",
                "IVA": f"${fila.iva:,.2f}",
                "Total": f"${fila.total:,.2f}",
            })

    if datos_tabla:
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True)

    # Sección: Generar F-07
    st.divider()
    st.subheader("4️⃣ Generar F-07 Hacienda")

    validos_count = sum(1 for r in st.session_state.resultados if r["es_valido"])

    if validos_count > 0:
        nombre_excel = st.text_input(
            "Nombre del archivo:",
            value=f"F07_Compras_{st.session_state.periodo}.xlsx"
        )

        if st.button(
            f"📥 Generar F-07 ({validos_count} documentos)",
            type="primary",
            use_container_width=True,
        ):
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                ruta_excel = tmp.name

            try:
                stats = st.session_state.generador.generar_excel(
                    ruta_excel, st.session_state.periodo
                )

                with open(ruta_excel, "rb") as f:
                    excel_bytes = f.read()

                st.success("✅ F-07 generado exitosamente")

                st.download_button(
                    label="⬇️ Descargar Excel",
                    data=excel_bytes,
                    file_name=nombre_excel,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(ruta_excel):
                    os.unlink(ruta_excel)
    else:
        st.warning("⚠️ No hay documentos válidos para generar F-07")

else:
    st.info("👆 Sube PDFs para comenzar a procesar")
