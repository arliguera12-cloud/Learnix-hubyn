# core/constantes.py
"""
Constantes y configuraciones globales del sistema
"""

# ═══════════════════════════════════════════════════════════════
# TIPOS DE DTE
# ═══════════════════════════════════════════════════════════════

TIPOS_DTE = {
    "01": "Factura Electronica",
    "03": "Comprobante de Crédito Fiscal",
    "04": "Documento de Remisión",
    "05": "Nota de Débito de Servicios Financieros",
    "06": "Nota de Crédito",
    "07": "Comprobante de Retención",
    "08": "Comprobante de Liquidación",
    "09": "Documento Contable de Liquidación",
    "10": "Retención/Percepción por Terceros",
    "11": "Factura de Exportación",
    "12": "Factura Negociable",
    "13": "Factura de Sujeto Excluido",
    "14": "Factura para Sujetos Excluidos",
    "15": "Nota de Crédito para Sujetos Excluidos",
}

# ═══════════════════════════════════════════════════════════════
# FORMATOS
# ═══════════════════════════════════════════════════════════════

FORMATOS_FECHA = [
    "%Y-%m-%d",      # 2025-01-15
    "%d/%m/%Y",      # 15/01/2025
    "%d-%m-%Y",      # 15-01-2025
    "%Y/%m/%d",      # 2025/01/15
    "%d.%m.%Y",      # 15.01.2025
]

# ═══════════════════════════════════════════════════════════════
# CAMPOS DE CADA TIPO DE DOCUMENTO
# ═══════════════════════════════════════════════════════════════

CAMPOS_VENTAS = [
    "fecha",
    "nit",
    "nom",
    "tipo",
    "ctrl",
    "gen",
    "sello",
    "nos",      # No sujeto
    "exe",      # Exento
    "gra",      # Gravado
    "iva",      # IVA
    "exp_serv", # Exportación servicios
    "tot",      # Total
    "t_ing",    # Tipo de ingreso
    "motor",    # Origen (PDF, JSON, OCR)
    "iva_calculado",
    "confianza_nit",
    "confianza_rs",
    "fuente",
    "archivo",
]

CAMPOS_COMPRAS = [
    "fecha",
    "nit_prov",
    "nom_prov",
    "dui_prov",
    "tipo",
    "ctrl",
    "gen",
    "sello",
    "exe",      # Exento
    "gra",      # Gravado
    "iva",      # IVA
    "ret",      # Retención
    "perc",     # Percepción
    "tot",      # Total
    "motor",
    "iva_calc",
    "confianza_nit",
    "confianza_rs",
    "fuente",
    "archivo",
]

CAMPOS_RETENCIONES = [
    "fecha",
    "nit_contraparte",
    "nom_contraparte",
    "tipo",
    "ctrl",
    "gen",
    "sello",
    "monto_sujeto",
    "monto_retenido",
    "ret_calc",
    "motor",
    "confianza_nit",
    "confianza_rs",
    "fuente",
    "archivo",
]

CAMPOS_SUJETOS_EXCLUIDOS = [
    "fecha",
    "nombre",
    "documento",
    "nit",
    "dui",
    "tipo",
    "ctrl",
    "gen",
    "sello",
    "monto",
    "retencion",
    "retencion_calculada",
    "motor",
    "fuente",
    "archivo",
]

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE GEMINI
# ═══════════════════════════════════════════════════════════════

GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_MAX_TOKENS = 1000

# ═══════════════════════════════════════════════════════════════
# PATRONES REGEX
# ═══════════════════════════════════════════════════════════════

PATRON_NIT = r'\b(\d{4})-(\d{6})-(\d{3})-(\d{1})\b'  # 0614-123456-789-0
PATRON_DUI = r'\b(\d{8})-(\d{1})\b'                  # 12345678-9
PATRON_FECHA_ISO = r'\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\b'
PATRON_FECHA_TRADICIONAL = r'\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b'
PATRON_UUID = r'[A-F0-9a-f]{32}'
PATRON_MONTO = r'[\$]?\s*[\d,.\s]+'

# ═══════════════════════════════════════════════════════════════
# UMBRALES DE CONFIANZA
# ═══════════════════════════════════════════════════════════════

CONFIANZA_UMBRALES = {
    "alta": 0.85,
    "media": 0.60,
    "baja": 0.30,
    "nula": 0.00,
}

# ═══════════════════════════════════════════════════════════════
# MENSAJES Y TEXTOS
# ═══════════════════════════════════════════════════════════════

MENSAJES = {
    "sin_cliente": "⚠️ Selecciona un cliente primero desde el Dashboard.",
    "sin_archivos": "📁 No hay archivos para procesar. Carga un PDF o JSON.",
    "error_gemini": "❌ Error al validar con Gemini. Revisa tu API Key.",
    "exito_extraccion": "✅ Extracción completada exitosamente.",
    "exito_guardado": "✅ Datos guardados correctamente.",
}
