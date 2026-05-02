# core/modelos/constantes.py
"""
Constantes y valores fijos para toda la aplicación.
"""

# ═══════════════════════════════════════════════════════════════
# TIPOS DE DOCUMENTOS TRIBUTARIOS ELECTRÓNICOS
# ═══════════════════════════════════════════════════════════════

TIPOS_DTE = {
    "01": {"nombre": "Factura", "descripcion": "Factura de venta"},
    "03": {"nombre": "Comprobante de Crédito Fiscal", "descripcion": "CCF - Factura de venta con retención"},
    "05": {"nombre": "Nota de Crédito", "descripcion": "Nota de crédito por devolución o reajuste"},
    "06": {"nombre": "Nota de Débito", "descripcion": "Nota de débito por cobro adicional"},
    "07": {"nombre": "Comprobante de Retención", "descripcion": "Retención de IVA"},
    "11": {"nombre": "Exportación", "descripcion": "Factura de exportación"},
    "14": {"nombre": "Sujeto Excluido", "descripcion": "Compra a sujeto excluido"},
}

# ═══════════════════════════════════════════════════════════════
# ANEXOS Y FORMULARIOS HACIENDA
# ═══════════════════════════════════════════════════════════════

ANEXOS_DISPONIBLES = {
    "A": {
        "nombre": "Anexo de Ventas a Contribuyentes (CCF)",
        "tipos_dte": ["03", "05", "06"],
        "columnas": [
            "fecha", "clase", "tipo", "ctrl", "sello", "gen", "ctrl_vacio",
            "nit", "nom", "exe", "nos", "gra", "iva", "v_terc", "d_terc",
            "tot", "dui", "t_op", "t_ing", "n_anexo"
        ]
    },
    "B": {
        "nombre": "Anexo de Ventas a Consumidor Final (Facturas)",
        "tipos_dte": ["01", "11"],
        "columnas": [
            "fecha", "clase", "tipo", "res", "ser", "int", "pre_ctrl",
            "ctrl", "gen", "maq", "exe", "nos", "vtas_int_exe_no_suj",
            "gra", "exp_ca", "exp_fca", "exp_serv", "v_zf", "v_ter",
            "tot", "t_op", "t_ing", "n_anexo"
        ]
    },
    "Compras": {
        "nombre": "Anexo de Compras a Contribuyentes",
        "tipos_dte": ["03", "05", "06"],
        "columnas": [
            "fecha", "tipo_doc", "nit_prov", "nom_prov", "dui_prov",
            "exe", "inter_exe", "import_exe", "gra", "inter_gra",
            "import_gra", "import_gra_serv", "iva_cf", "tot", "dui",
            "t_op", "clasif", "sector", "t_gasto", "n_anexo"
        ]
    },
    "F14": {
        "nombre": "Anexo de Retenciones (F-14)",
        "tipos_dte": ["07"],
        "columnas": [
            "nit_agente", "fecha", "tipo", "serie", "num_doc", 
            "monto_sujeto", "monto_retenido", "dui", "n_anexo"
        ]
    }
}

# ═══════════════════════════════════════════════════════════════
# TIPOS DE MOTORES DE EXTRACCIÓN
# ═══════════════════════════════════════════════════════════════

MOTORES_EXTRACCION = [
    "Nativo",          # pdfplumber extracción nativa
    "OCR",             # pytesseract para imágenes
    "JSON-Parser",     # Parseo de JSON del Ministerio
    "Gemini-1.5",      # Validación con Gemini
]

# ═══════════════════════════════════════════════════════════════
# NIVELES DE CONFIANZA
# ═══════════════════════════════════════════════════════════════

NIVELES_CONFIANZA = {
    "alta": {"valor": 1.00, "color": "green", "icono": "✅"},
    "media": {"valor": 0.70, "color": "orange", "icono": "⚠️"},
    "baja": {"valor": 0.40, "color": "red", "icono": "❌"},
    "cache": {"valor": 0.95, "color": "blue", "icono": "⚡"},
    "tabla": {"valor": 0.88, "color": "purple", "icono": "📊"},
    "ocr": {"valor": 0.65, "color": "orange", "icono": "🖼️"},
}

# ═══════════════════════════════════════════════════════════════
# MAPEEO DE CAMPOS ENTRE FORMATOS
# ═══════════════════════════════════════════════════════════════

CAMPOS_NORMALIZADOS = {
    "nit": ["nit", "nit_prov", "numero_documento", "numDocumento"],
    "nombre": ["nom", "nom_prov", "nombre", "razon_social", "nombreComercial"],
    "fecha": ["fecha", "fec_emi", "fecEmi", "fecha_emision"],
    "monto_gravado": ["gra", "gravado", "totalGravada", "total_gravada"],
    "iva": ["iva", "impuesto", "totalIva", "total_iva"],
    "monto_exento": ["exe", "exento", "totalExenta", "total_exenta"],
    "total": ["tot", "total", "totalPagar", "total_pagar"],
}
