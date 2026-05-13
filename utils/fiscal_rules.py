"""
utils/fiscal_rules.py — Reglas fiscales centralizadas del MH El Salvador.

Fuente: Manual Técnico DTE v3, Instructivo F-07, F-14, Art. 65 Ley IVA.
Único punto de verdad para prompts de Gemini, validaciones de qa_utils
y construcción de DataFrames de exportación.
"""
from __future__ import annotations
import re

# ── Tipos de DTE ──────────────────────────────────────────────────────────────

DTE_TIPOS: dict[str, str] = {
    "01": "Factura de Consumidor Final",
    "03": "Comprobante de Crédito Fiscal (CCF)",
    "05": "Nota de Crédito",
    "06": "Nota de Débito",
    "07": "Comprobante de Retención",
    "08": "Comprobante de Liquidación",
    "09": "Documento Contable de Liquidación",
    "11": "Factura de Exportación / Factura Exenta",
    "14": "Comprobante de Sujeto Excluido",
    "15": "Comprobante de Donación",
}

DTE_TIPOS_VALIDOS_VENTAS    : frozenset = frozenset({"01", "03", "05", "06", "11"})
DTE_TIPOS_VALIDOS_COMPRAS   : frozenset = frozenset({"03", "05", "06", "11"})
DTE_TIPOS_VALIDOS_RETENCIONES: frozenset = frozenset({"07"})
DTE_TIPOS_VALIDOS_SUJETOS   : frozenset = frozenset({"14"})

# Alias de texto → código numérico (para normalizar Gemini output y tipoDte JSON)
_ALIAS_TIPO: dict[str, str] = {
    "CCF": "03", "COMPROBANTE DE CREDITO FISCAL": "03", "COMPROBANTE DE CRÉDITO FISCAL": "03",
    "FACTURA": "01", "FAC": "01", "FACTURA CONSUMIDOR": "01",
    "NC": "05", "NOTA DE CREDITO": "05", "NOTA DE CRÉDITO": "05",
    "ND": "06", "NOTA DE DEBITO": "06", "NOTA DE DÉBITO": "06",
    "RETENCION": "07", "RETENCIÓN": "07", "COMPROBANTE DE RETENCION": "07",
    "SUJETO EXCLUIDO": "14", "COMPROBANTE SUJETO": "14",
    "FACTURA EXENTA": "11", "FAC EXENTA": "11",
    "LIQUIDACION": "08",
}


def normalizar_tipo_dte(raw) -> str:
    """
    Normaliza cualquier representación de tipoDte a código de 2 dígitos.

    Maneja: "03", "3", "CCF", "03-Comprobante", None, etc.
    Devuelve "" si no puede determinar el tipo.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", ""):
        return ""
    # Ya es 2 dígitos
    if re.match(r'^\d{2}$', s):
        return s
    # Extraer dígitos (ej. "3" → "03", "03-CCF" → "03")
    m = re.search(r'\d+', s)
    if m:
        return m.group(0).zfill(2)
    # Alias de texto
    return _ALIAS_TIPO.get(s.upper().strip(), "")


# ── Códigos de Tributos MH ────────────────────────────────────────────────────

TRIBUTO_IVA            : frozenset = frozenset({"20"})
TRIBUTO_RETENCION_IVA  : frozenset = frozenset({"22"})
TRIBUTO_PERCEPCION_IVA : frozenset = frozenset({"23"})
TRIBUTO_FOVIAL         : frozenset = frozenset({"C3", "D1"})   # $0.20/galón
TRIBUTO_COTRANS        : frozenset = frozenset({"59", "C8"})   # $0.10/galón
TRIBUTO_RETENCION_RENTA: frozenset = frozenset({"C4", "22"})   # 10% DTE-14

# Tasas
TASA_IVA             = 0.13
TASA_RETENCION_IVA   = 0.01
TASA_PERCEPCION_IVA  = 0.01
TASA_RETENCION_RENTA = 0.10
TASA_FOVIAL_GALON    = 0.20
TASA_COTRANS_GALON   = 0.10

# ── Períodos legales ──────────────────────────────────────────────────────────

PERIODO_VENTAS_MESES    = 1   # estricto: todos los docs del mismo mes
PERIODO_COMPRAS_VENTANA = 4   # Art. 65 Ley IVA: mes declaración + 3 anteriores

# ── Identificación ────────────────────────────────────────────────────────────

NIT_LONGITUD = 14
DUI_LONGITUD = 9
NRC_MAX      = 7

# ── Sectores especiales ───────────────────────────────────────────────────────

KEYWORDS_GASOLINERA: frozenset = frozenset({
    "COMBUSTIBLE", "GALÓN", "GALON", "LITRO", "GASOLINERA",
    "SHELL", "TEXACO", "PUMA", "UNO", "PRIMAX", "DISTRIBUIDORA DE GAS",
    "ESTACION DE SERVICIO", "ESTACIÓN DE SERVICIO",
})

# ── F-07 Clase Documento ──────────────────────────────────────────────────────

F07_CLASE_DOCUMENTO: dict[str, str] = {
    "03": "1",   # CCF
    "11": "2",   # Factura Exenta / Exportación
    "06": "3",   # Nota de Débito
    "05": "4",   # Nota de Crédito
}

# ── Helpers de clasificación de tributos ──────────────────────────────────────

def tributo_es_iva(codigo: str, descripcion: str = "") -> bool:
    d = descripcion.upper()
    return codigo in TRIBUTO_IVA or "IMPUESTO AL VALOR AGREGADO" in d or ("IVA" in d and "RETENCION" not in d and "PERCEPCION" not in d)

def tributo_es_retencion_iva(codigo: str, descripcion: str = "") -> bool:
    d = descripcion.upper()
    return codigo in TRIBUTO_RETENCION_IVA or "RETENCIÓN IVA" in d or "RETENCION IVA" in d

def tributo_es_percepcion_iva(codigo: str, descripcion: str = "") -> bool:
    d = descripcion.upper()
    return codigo in TRIBUTO_PERCEPCION_IVA or "PERCEPCIÓN" in d or "PERCEPCION" in d

def tributo_es_fovial(codigo: str, descripcion: str = "") -> bool:
    return codigo.upper() in TRIBUTO_FOVIAL or "FOVIAL" in descripcion.upper()

def tributo_es_cotrans(codigo: str, descripcion: str = "") -> bool:
    return codigo.upper() in TRIBUTO_COTRANS or "COTRANS" in descripcion.upper()

def es_gasolinera(nombre: str) -> bool:
    n = str(nombre).upper()
    return any(k in n for k in KEYWORDS_GASOLINERA)


def parse_tributos(tributos_list: list) -> dict:
    """
    Parse a DTE resumen.tributos list and return classified amounts.

    Returns:
      {"iva": float, "fovial": float, "cotrans": float,
       "ret_iva": float, "perc_iva": float}
    """
    iva = fovial = cotrans = ret_iva = perc_iva = 0.0
    for t in (tributos_list or []):
        try:
            cod  = str(t.get("codigo") or "").strip().upper()
            desc = str(t.get("descripcion") or "")
            val  = float(str(t.get("valor") or 0).replace(",", ".") or 0)
        except (ValueError, TypeError, AttributeError):
            continue
        if tributo_es_iva(cod, desc):
            iva = val
        elif tributo_es_fovial(cod, desc):
            fovial = val
        elif tributo_es_cotrans(cod, desc):
            cotrans = val
        elif tributo_es_retencion_iva(cod, desc):
            ret_iva = val
        elif tributo_es_percepcion_iva(cod, desc):
            perc_iva = val
    return {"iva": iva, "fovial": fovial, "cotrans": cotrans,
            "ret_iva": ret_iva, "perc_iva": perc_iva}


# ── Detección rápida de tipo DTE desde bytes de PDF ───────────────────────────

# Palabras clave en el texto del PDF → código DTE
_KEYWORDS_TIPO: list[tuple[str, str]] = [
    # Orden importa: más específico primero
    ("SUJETO EXCLUIDO",                 "14"),
    ("COMPROBANTE DE RETENCIÓN",        "07"),
    ("COMPROBANTE DE RETENCION",        "07"),
    ("NOTA DE CRÉDITO",                 "05"),
    ("NOTA DE CREDITO",                 "05"),
    ("NOTA DE DÉBITO",                  "06"),
    ("NOTA DE DEBITO",                  "06"),
    ("COMPROBANTE DE CRÉDITO FISCAL",   "03"),
    ("COMPROBANTE DE CREDITO FISCAL",   "03"),
    ("FACTURA DE EXPORTACIÓN",          "11"),
    ("FACTURA DE EXPORTACION",          "11"),
    ("FACTURA EXENTA",                  "11"),
    ("FACTURA DE CONSUMIDOR FINAL",     "01"),
    ("FACTURA CONSUMIDOR",              "01"),
]


def detectar_tipo_dte_rapido(pdf_bytes: bytes) -> str:
    """
    Detección rápida del tipoDte a partir de los bytes del PDF, SIN llamada a API.

    Estrategia en 3 capas:
      1. Busca campo JSON `"tipoDte":"XX"` en texto extraído (JSONs embebidos o texto digital).
      2. Busca palabras clave del encabezado del DTE.
      3. Devuelve "" si no puede determinar el tipo (el llamador usará su default).

    Usa solo la primera página para rapidez (~5-20 ms).
    """
    try:
        import pdfplumber
        from io import BytesIO

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return ""
            texto = (pdf.pages[0].extract_text() or "").upper()
    except Exception:
        return ""

    if not texto:
        return ""

    # Capa 1: campo JSON tipoDte (PDFs con JSON embebido o texto digital)
    m = re.search(r'"tipoDte"\s*:\s*"(\d{1,2})"', texto, re.IGNORECASE)
    if m:
        return m.group(1).zfill(2)

    # También puede aparecer como número solo: tipoDte: 3
    m2 = re.search(r'TIPOPDTE["\s:]+(\d{1,2})', texto, re.IGNORECASE)
    if m2:
        return m2.group(1).zfill(2)

    # Capa 2: palabras clave del encabezado
    for keyword, codigo in _KEYWORDS_TIPO:
        if keyword in texto:
            return codigo

    # Capa 3: buscar "CCF" como abreviatura
    if re.search(r'\bCCF\b', texto):
        return "03"

    return ""
