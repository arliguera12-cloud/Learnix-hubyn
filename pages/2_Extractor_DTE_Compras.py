import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import pytesseract
import json
import os
import gc
from io import BytesIO
import platform

# ═══════════════════════════════════════════════════════════════
# VERIFICACION DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
st.warning("Acceso denegado. Por favor, inicia sesion en la pagina principal.")
st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
st.warning("Debes seleccionar un Cliente Activo antes de extraer Compras.")
st.stop()

if not isinstance(st.session_state.cliente_activo, dict):
st.warning("El cliente activo no es valido. Regresa al Dashboard y vuelvelo a seleccionar.")
st.stop()

cliente = st.session_state.cliente_activo

# ═══════════════════════════════════════════════════════════════
# CONFIGURACION TECNICA
# ═══════════════════════════════════════════════════════════════
if platform.system() == "Windows":
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ═══════════════════════════════════════════════════════════════
# ESTILOS GLOBALES
# ═══════════════════════════════════════════════════════════════
estilo_custom = """
<style>
   [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
       background-color: #000000 !important;
   }
   [data-testid="stSidebar"] {
       background-color: #161616 !important;
       border-right: 1px solid #333333;
   }
   h1, h2, h3, h4, h5, h6, p, label, span {
       color: #F7F5EE !important;
   }
   [data-testid="stDataFrame"] span { color: inherit !important; }
   div.stButton > button[kind="primary"],
   div.stDownloadButton > button[kind="primary"] {
       background-color: #003057 !important;
       border: 1px solid #00407A !important;
       border-radius: 6px;
       transition: 0.3s;
   }
   div.stButton > button[kind="primary"] *,
   div.stDownloadButton > button[kind="primary"] * {
       color: #FFFFFF !important;
       font-weight: bold !important;
   }
   div.stButton > button[kind="primary"]:hover,
   div.stDownloadButton > button[kind="primary"]:hover {
       background-color: #00407A !important;
   }
   div.stButton > button[kind="secondary"] {
       background-color: #2A2A2A !important;
       border: 1px solid #555555 !important;
       border-radius: 6px;
   }
   div.stButton > button[kind="secondary"] * {
       color: #FFFFFF !important;
       font-weight: bold !important;
   }
   div[data-testid="stAlert"] {
       min-height: 80px;
       display: flex;
       align-items: center;
   }
   .stAlert * { color: inherit !important; }
   .scroll-list {
       max-height: 150px;
       overflow-y: auto;
       padding: 10px;
       background-color: #111111;
       border-radius: 5px;
       border: 1px solid #333;
       font-family: monospace;
       font-size: 13px;
       color: #66ff66;
   }
   .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
       color: #4DA8DA !important;
       border-bottom-color: #4DA8DA !important;
   }
   .stTabs [data-baseweb="tab-list"] button { color: #777777 !important; }
   [data-testid="stExpander"] {
       background-color: #161616 !important;
       border: 1px solid #444444 !important;
       border-radius: 6px;
   }
   .alerta-activo {
       padding: 10px;
       border-radius: 6px;
       border-left: 4px solid #00407A;
       background-color: #111111;
       color: white;
       margin-bottom: 15px;
       font-size: 14px;
   }
   .inbox-revision {
       background-color: #1a1a1a;
       border: 1px solid #ffaa00;
       border-radius: 10px;
       padding: 20px;
       margin-top: 20px;
       margin-bottom: 20px;
   }
   .indicador-confianza {
       display: inline-block;
       padding: 3px 10px;
       border-radius: 20px;
       font-size: 11px;
       font-weight: bold;
       margin-left: 6px;
       letter-spacing: 0.5px;
   }
   .confianza-alta  { background-color: #1b5e20; color: #81c784; border: 1px solid #2e7d32; }
   .confianza-media { background-color: #e65100; color: #ffb74d; border: 1px solid #bf360c; }
   .confianza-baja  { background-color: #7f1010; color: #ef9a9a; border: 1px solid #b71c1c; }
   .confianza-cache { background-color: #1a237e; color: #90caf9; border: 1px solid #283593; }
   .confianza-tabla { background-color: #4a148c; color: #ce93d8; border: 1px solid #7b1fa2; }
   .confianza-ocr   { background-color: #01579b; color: #81d4fa; border: 1px solid #0277bd; }
   .badge-revision {
       display: inline-block;
       padding: 3px 10px;
       border-radius: 12px;
       font-size: 11px;
       font-weight: bold;
       background-color: #ff6f00;
       color: white;
       letter-spacing: 0.5px;
   }
   .confianza-row {
       display: flex;
       gap: 20px;
       align-items: center;
       padding: 10px 0 6px 0;
       flex-wrap: wrap;
   }
   .confianza-item {
       display: flex;
       align-items: center;
       font-size: 13px;
       color: #aaaaaa;
   }
   .debug-box {
       background-color: #0d1117;
       border: 1px solid #30363d;
       border-radius: 6px;
       padding: 10px 14px;
       font-family: monospace;
       font-size: 12px;
       color: #8b949e;
       margin-bottom: 6px;
   }
   .debug-ok   { color: #3fb950; }
   .debug-err  { color: #f85149; }
   .debug-warn { color: #d29922; }
   .metric-box {
       background-color: #161616;
       border: 1px solid #30363d;
       border-radius: 6px;
       padding: 12px;
       margin: 4px 0;
       text-align: center;
   }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

NOMBRE_PLACEHOLDER  = "ESCRIBE EL NOMBRE AQUI"
ARCHIVO_PROVEEDORES = "data/proveedores.json"

PALABRAS_BASURA = frozenset([
"DOCUMENTO", "TRIBUTARIO", "ELECTRONICO", "REPRESENTACION",
"RECEPTOR", "CLIENTE", "EMISOR", "FACTURA", "CONSUMIDOR",
"FACTURACION", "COMPROBANTE", "DIRECC", "CODIGO", "SELLO",
"VERSION", "TRANSMISION", "MINISTERIO", "HACIENDA", "COLONIA",
"BOULEVARD", "CALLE", "AVENIDA", "MUNICIPIO", "GIRO:",
"ACTIVIDAD", "ECONOMICA", "TIPO ESTABLECIMIENTO", "SUCURSAL",
"AGENCIA", "PAGO DE", "TARJETA", "EFECTIVO", "FECHA",
"HORA", "EMISION", "GENERACION", "TELEFONO"
])

BASURA_ESTRICTA   = frozenset(["@", "EMAIL", "CORREO", ".COM", "WWW."])
NOMBRES_INVALIDOS = frozenset([
"S.A. DE C.V.", "C.V.", "SA DE CV", "LTDA", "LTDA.", "S.A.", "DE C.V."
])
MARCAS_COMERCIALES = [
"S.A.", "SA ", "C.V.", "CV ", "LTDA.", "LTDA", "SOCIEDAD",
"DISTRIBUIDORA", "FARMACIA", "GRUPO", "LABORATORIOS", "INDUSTRIAS",
"COMERCIAL", "SERVICIOS", "IMPORTADORA", "EXPORTADORA"
]

# Etiquetas de pie de tabla CCF — en orden de aparicion tipica
ETIQUETAS_PIE_CCF = {
"gravado": [
"subtotal gravado", "venta gravada", "ventas gravadas",
@@ -654,35 +653,22 @@
# ═══════════════════════════════════════════════════════════════

def _buscar_monto_en_linea(linea_texto):
    """
    Extrae el primer monto numerico valido de una linea de texto.
    Maneja formatos: 1,234.56 / 1.234,56 / 1234.56 / $1,234.56
    """
linea_limpia = re.sub(r'[^\d.,]', ' ', linea_texto).strip()
    # Patron: numero con separador decimal de 2 cifras al final
matches = re.findall(r'\d{1,3}(?:[.,]\d{3})*[.,]\d{2}', linea_limpia)
if matches:
        return limpiar_monto(matches[-1])   # el ultimo suele ser el monto final
    # Fallback: numero simple con decimales
        return limpiar_monto(matches[-1])
m = re.search(r'(\d+)[.,](\d{2})$', linea_limpia.strip())
if m:
return limpiar_monto(f"{m.group(1)}.{m.group(2)}")
return 0.0


def _extraer_montos_de_tablas_ccf(file_bytes):
    """
    Estrategia especializada para CCF:
    Busca el PIE de las tablas en busca de las filas de resumen
    (Subtotal Gravado, Exento, IVA, Total).

    Retorna dict con: g, exe, i, t y fuente por campo.
    """
resultado = {
        "g":       0.0, "g_fuente":   "no encontrado",
        "exe":     0.0, "exe_fuente": "no encontrado",
        "i":       0.0, "i_fuente":   "no encontrado",
        "t":       0.0, "t_fuente":   "no encontrado",
        "g": 0.0, "g_fuente": "no encontrado",
        "exe": 0.0, "exe_fuente": "no encontrado",
        "i": 0.0, "i_fuente": "no encontrado",
        "t": 0.0, "t_fuente": "no encontrado",
}

try:
@@ -692,22 +678,18 @@
for table in tables:
if not table:
continue
                    # Recorremos las filas en REVERSO (pie de tabla = ultimas filas)
for row in reversed(table):
if not row:
continue
                        # Concatenar todas las celdas como texto unico de la fila
texto_fila = " ".join(
str(c).strip() for c in row if c
).upper().strip()

if len(texto_fila) < 2:
continue

                        # Buscar el monto en la fila
monto_fila = _buscar_monto_en_linea(texto_fila)
if monto_fila <= 0:
                            # Intentar cada celda individualmente
for celda in reversed(row):
if celda and str(celda).strip():
m = _buscar_monto_en_linea(str(celda))
@@ -720,36 +702,32 @@

texto_lower = texto_fila.lower()

                        # ── TOTAL (prioridad maxima) ──────────────────
if resultado["t"] == 0.0:
for etiq in ETIQUETAS_PIE_CCF["total"]:
if etiq in texto_lower:
                                    resultado["t"]       = monto_fila
                                    resultado["t_fuente"] = f"tabla:'{etiq}'=>{monto_fila}"
                                    resultado["t"] = monto_fila
                                    resultado["t_fuente"] = f"tabla:'{etiq}'"
break

                        # ── IVA ───────────────────────────────────────
if resultado["i"] == 0.0:
for etiq in ETIQUETAS_PIE_CCF["iva"]:
if etiq in texto_lower:
                                    resultado["i"]       = monto_fila
                                    resultado["i_fuente"] = f"tabla:'{etiq}'=>{monto_fila}"
                                    resultado["i"] = monto_fila
                                    resultado["i_fuente"] = f"tabla:'{etiq}'"
break

                        # ── EXENTO ────────────────────────────────────
if resultado["exe"] == 0.0:
for etiq in ETIQUETAS_PIE_CCF["exento"]:
if etiq in texto_lower:
                                    resultado["exe"]       = monto_fila
                                    resultado["exe_fuente"] = f"tabla:'{etiq}'=>{monto_fila}"
                                    resultado["exe"] = monto_fila
                                    resultado["exe_fuente"] = f"tabla:'{etiq}'"
break

                        # ── GRAVADO ───────────────────────────────────
if resultado["g"] == 0.0:
for etiq in ETIQUETAS_PIE_CCF["gravado"]:
if etiq in texto_lower:
                                    resultado["g"]       = monto_fila
                                    resultado["g_fuente"] = f"tabla:'{etiq}'=>{monto_fila}"
                                    resultado["g"] = monto_fila
                                    resultado["g_fuente"] = f"tabla:'{etiq}'"
break

except Exception:
@@ -759,12 +737,6 @@


def _extraer_montos_de_lineas_ccf(t_clean):
    """
    Estrategia de lineas de texto para CCF.
    Analiza linea a linea buscando pares etiqueta + monto.
    Mas flexible que regex fijo porque el CCF puede tener
    espacios variables entre etiqueta y valor.
    """
resultado = {
"g": 0.0, "g_fuente": "no encontrado",
"exe": 0.0, "exe_fuente": "no encontrado",
@@ -774,7 +746,6 @@

lineas = t_clean.split('\n') if '\n' in t_clean else re.split(r'(?<=[.?!])\s+', t_clean)

    # Si no hay saltos de linea reales, dividir por puntos o separadores logicos
if len(lineas) < 5:
lineas = re.split(r'\s{3,}', t_clean)

@@ -788,108 +759,86 @@
if monto <= 0:
continue

        # ── TOTAL ──────────────────────────────────────────────
if resultado["t"] == 0.0:
for etiq in ETIQUETAS_PIE_CCF["total"]:
if etiq in linea_lower:
                    resultado["t"]       = monto
                    resultado["t_fuente"] = f"linea:'{etiq}'=>{monto}"
                    resultado["t"] = monto
                    resultado["t_fuente"] = f"linea:'{etiq}'"
break

        # ── IVA ────────────────────────────────────────────────
if resultado["i"] == 0.0:
for etiq in ETIQUETAS_PIE_CCF["iva"]:
if etiq in linea_lower:
                    resultado["i"]       = monto
                    resultado["i_fuente"] = f"linea:'{etiq}'=>{monto}"
                    resultado["i"] = monto
                    resultado["i_fuente"] = f"linea:'{etiq}'"
break

        # ── EXENTO ─────────────────────────────────────────────
if resultado["exe"] == 0.0:
for etiq in ETIQUETAS_PIE_CCF["exento"]:
if etiq in linea_lower:
                    resultado["exe"]       = monto
                    resultado["exe_fuente"] = f"linea:'{etiq}'=>{monto}"
                    resultado["exe"] = monto
                    resultado["exe_fuente"] = f"linea:'{etiq}'"
break

        # ── GRAVADO ────────────────────────────────────────────
if resultado["g"] == 0.0:
for etiq in ETIQUETAS_PIE_CCF["gravado"]:
if etiq in linea_lower:
                    resultado["g"]       = monto
                    resultado["g_fuente"] = f"linea:'{etiq}'=>{monto}"
                    resultado["g"] = monto
                    resultado["g_fuente"] = f"linea:'{etiq}'"
break

return resultado

# ═══════════════════════════════════════════════════════════════
# MOTOR V10: EXTRACCION DE MONTOS CCF CON 4 ESTRATEGIAS
# MOTOR V10: EXTRACCION DE MONTOS CCF
# ═══════════════════════════════════════════════════════════════

def _extraer_montos_v10(texto_completo, t_clean, tipo, e_fovial, ret, file_bytes):
"""
   Motor V10: 4 estrategias en cascada para CCF y facturas.

    ORDEN DE PRIORIDAD:
      E1 — Regex con etiquetas explicitas (texto plano)
      E2 — Analisis linea a linea (CCF sin estructura clara)
      E3 — Extraccion de tablas PDF (CCF con tabla de pie)
      E4 — Fallback cuadruple-loop (ULTIMO RECURSO)

    FORMULA CORRECTA:
      Total = Gravado + IVA(13%) + Exento - Retenciones
      (Exento NO genera IVA pero SI suma al Total)
    E1 → E2 → E3 → E4
   """
g, i, exe, t = 0.0, 0.0, 0.0, 0.0
iva_calculado = False
debug = {
        "E1_regex":      {},
        "E2_lineas":     {},
        "E3_tablas":     {},
        "E4_fallback":   "no aplicado",
        "P_algebra":     "no aplicado",
        "P_validacion":  "no aplicada",
        "P_aseguranza":  "no aplicada",
        "montos_raw":    [],
        "resultado":     "",
        "E1_regex": {},
        "E2_lineas": {},
        "E3_tablas": {},
        "E4_fallback": "no aplicado",
        "P_algebra": "no aplicado",
        "P_validacion": "no aplicada",
        "P_aseguranza": "no aplicada",
        "montos_raw": [],
        "resultado": "",
"estrategia_ganadora": "ninguna"
}

    # ══════════════════════════════════════════════════════════
    # E1: REGEX CON ETIQUETAS EXPLICITAS
    # ══════════════════════════════════════════════════════════
    # E1: REGEX
e1 = {"g": 0.0, "i": 0.0, "exe": 0.0, "t": 0.0}

    # Total
for patron in [
        r"(?:TOTAL\s+A\s+PAGAR|MONTO\s+TOTAL\s+(?:DE\s+LA\s+)?OPERACI[OO]N|"
        r"TOTAL\s+(?:DE\s+LA\s+)?OPERACI[OO]N|VENTA\s+TOTAL|TOTAL\s+PAGAR|TOTAL\s+\$)"
        r"(?:TOTAL\s+A\s+PAGAR|MONTO\s+TOTAL\s+(?:DE\s+LA\s+)?OPERACI[OO]N|TOTAL\s+\$)"
r"[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
]:
m = re.search(patron, t_clean, re.I)
if m:
e1["t"] = limpiar_monto(m.group(1))
break

    # IVA
for patron in [
r"(?:Impuesto\s+al\s+Valor\s+Agregado|D[eé]bito\s+Fiscal|Cr[eé]dito\s+Fiscal|"
r"I\.V\.A\.?|IVA)(?:\s*\(?13\s*%\)?)?\s*[:\-]?\s*"
r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:13\s*%\s*(?:de\s*)?IVA|IVA\s*13\s*%)[^\d]{0,20}?"
        r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
]:
m = re.search(patron, t_clean, re.I)
if m:
e1["i"] = limpiar_monto(m.group(1))
break

    # Gravado
for patron in [
r"Subtotal\s+Gravado[^\d]{0,10}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:Monto\s+Sujeto\s+a\s+IVA|Venta\s+Gravada|Ventas\s+Gravadas|"
        r"Compras?\s+Gravadas?)[^\d]{0,20}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"Sub\s*[Tt]otal\s+Gravado[^\d]{0,10}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:Monto\s+Sujeto\s+a\s+IVA|Venta\s+Gravada|Ventas\s+Gravadas)[^\d]{0,20}?"
        r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
]:
matches = re.findall(patron, t_clean, re.I)
if matches:
@@ -898,11 +847,9 @@
e1["g"] = cand
break

    # Exento
for patron in [
r"(?:Ventas?\s+Exentas?|Monto\s+Exento|Total\s+Exento|"
        r"Compras?\s+Exentas?|Subtotal\s+Exento|Sub\s+Total\s+Exento|"
        r"Venta\s+No\s+Sujeta|No\s+Sujeta|No\s+Gravado)"
        r"Compras?\s+Exentas?|Subtotal\s+Exento|Venta\s+No\s+Sujeta|No\s+Gravado)"
r"[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
]:
m = re.search(patron, t_clean, re.I)
@@ -916,84 +863,68 @@
"g": e1["g"], "i": e1["i"], "exe": e1["exe"], "t": e1["t"]
}

    # ── Si E1 encontro los 4 campos, usarla directamente ──────
if e1["t"] > 0 and (e1["g"] > 0 or e1["exe"] > 0):
g, i, exe, t = e1["g"], e1["i"], e1["exe"], e1["t"]
debug["estrategia_ganadora"] = "E1_regex"
else:
        # ══════════════════════════════════════════════════════
        # E2: ANALISIS LINEA A LINEA (CCF sin estructura clara)
        # ══════════════════════════════════════════════════════
        # E2: LINEAS
e2 = _extraer_montos_de_lineas_ccf(texto_completo)
debug["E2_lineas"] = {
            "g":   e2["g"],   "g_fuente":   e2["g_fuente"],
            "i":   e2["i"],   "i_fuente":   e2["i_fuente"],
            "g": e2["g"], "g_fuente": e2["g_fuente"],
            "i": e2["i"], "i_fuente": e2["i_fuente"],
"exe": e2["exe"], "exe_fuente": e2["exe_fuente"],
            "t":   e2["t"],   "t_fuente":   e2["t_fuente"],
            "t": e2["t"], "t_fuente": e2["t_fuente"],
}

if e2["t"] > 0 and (e2["g"] > 0 or e2["exe"] > 0):
            g   = e2["g"]   if e2["g"]   > 0 else e1["g"]
            i   = e2["i"]   if e2["i"]   > 0 else e1["i"]
            g = e2["g"] if e2["g"] > 0 else e1["g"]
            i = e2["i"] if e2["i"] > 0 else e1["i"]
exe = e2["exe"] if e2["exe"] > 0 else e1["exe"]
            t   = e2["t"]
            t = e2["t"]
debug["estrategia_ganadora"] = "E2_lineas"
else:
            # ══════════════════════════════════════════════════
            # E3: EXTRACCION DE TABLAS PDF (pie de tabla CCF)
            # ══════════════════════════════════════════════════
            # E3: TABLAS
e3 = _extraer_montos_de_tablas_ccf(file_bytes)
debug["E3_tablas"] = {
                "g":   e3["g"],   "g_fuente":   e3["g_fuente"],
                "i":   e3["i"],   "i_fuente":   e3["i_fuente"],
                "g": e3["g"], "g_fuente": e3["g_fuente"],
                "i": e3["i"], "i_fuente": e3["i_fuente"],
"exe": e3["exe"], "exe_fuente": e3["exe_fuente"],
                "t":   e3["t"],   "t_fuente":   e3["t_fuente"],
                "t": e3["t"], "t_fuente": e3["t_fuente"],
}

            # Combinar lo mejor de E1 + E2 + E3
            g   = e3["g"]   if e3["g"]   > 0 else (e2["g"]   if e2["g"]   > 0 else e1["g"])
            i   = e3["i"]   if e3["i"]   > 0 else (e2["i"]   if e2["i"]   > 0 else e1["i"])
            g = e3["g"] if e3["g"] > 0 else (e2["g"] if e2["g"] > 0 else e1["g"])
            i = e3["i"] if e3["i"] > 0 else (e2["i"] if e2["i"] > 0 else e1["i"])
exe = e3["exe"] if e3["exe"] > 0 else (e2["exe"] if e2["exe"] > 0 else e1["exe"])
            t   = e3["t"]   if e3["t"]   > 0 else (e2["t"]   if e2["t"]   > 0 else e1["t"])
            t = e3["t"] if e3["t"] > 0 else (e2["t"] if e2["t"] > 0 else e1["t"])

if t > 0 and (g > 0 or exe > 0):
debug["estrategia_ganadora"] = "E3_tablas"

    # ══════════════════════════════════════════════════════════
    # ALGEBRA: Calcular lo que falte usando lo que se encontro
    # Solo si la extraccion no fue completa
    # ══════════════════════════════════════════════════════════
    # ALGEBRA
algebra_log = []

    # Si no hay IVA pero hay Gravado -> calcular IVA
if g > 0 and i == 0.0:
i = round(g * 0.13, 2)
iva_calculado = True
algebra_log.append(f"I = {g} x 0.13 = {i}")

    # Si no hay Gravado pero hay Total e IVA -> despejar Gravado
if g == 0.0 and t > 0 and i > 0:
g = max(0.0, round(t - i - exe, 2))
algebra_log.append(f"G = {t} - {i} - {exe} = {g}")

    # Si no hay Gravado ni IVA pero hay Total (tipo 03) -> descomponer
if g == 0.0 and i == 0.0 and t > 0 and tipo == "03":
g = round((t - exe) / 1.13, 2)
i = round((t - exe) - g, 2)
iva_calculado = True
algebra_log.append(f"Tipo-03: ({t} - {exe}) / 1.13 = G:{g}, I:{i}")

    # Si no hay Total pero tenemos todo lo demas -> calcular Total
if t == 0.0 and g > 0 and i > 0:
t = round(g + i + exe - ret, 2)
algebra_log.append(f"T = {g} + {i} + {exe} - {ret} = {t}")

debug["P_algebra"] = " | ".join(algebra_log) if algebra_log else "no necesario"

    # ══════════════════════════════════════════════════════════
    # E4: FALLBACK CUADRUPLE-LOOP (ULTIMO RECURSO)
    # Solo si todavia no tenemos datos utiles
    # ══════════════════════════════════════════════════════════
    # E4: FALLBACK
if t == 0.0 or (g == 0.0 and exe == 0.0):
montos_raw = re.findall(
r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
@@ -1017,15 +948,13 @@
for val_i in valores:
if val_i >= val_g:
continue
                    # Primer intento: sin exento
if abs(round(val_g * 0.13, 2) - round(val_i, 2)) <= 0.05:
total_calc = round(val_g + val_i, 2)
if abs(total_calc - round(val_t, 2)) <= 0.10:
g, i, exe, t = val_g, val_i, 0.0, val_t
encontrado = True
debug["E4_fallback"] = f"OK(sin exe) => G={g}, I={i}, T={t}"
break
                    # Segundo intento: con exento
for val_exe in valores:
if val_exe >= val_g:
continue
@@ -1046,43 +975,34 @@
if debug["estrategia_ganadora"] == "ninguna" and encontrado:
debug["estrategia_ganadora"] = "E4_fallback"

    # ══════════════════════════════════════════════════════════
    # VALIDACION TRIBUTARIA
    # IVA debe ser ~13% del Gravado
    # ══════════════════════════════════════════════════════════
    # VALIDACION
if g > 0 and i > 0:
iva_esperado = round(g * 0.13, 2)
        diferencia   = abs(iva_esperado - i)
        diferencia = abs(iva_esperado - i)
if diferencia > 1.00:
i_viejo = i
i = iva_esperado
iva_calculado = True
            debug["P_validacion"] = f"IVA {i_viejo} -> corregido a {i} (G x 0.13 = {iva_esperado})"
            debug["P_validacion"] = f"IVA {i_viejo} -> {i} (G x 0.13 = {iva_esperado})"
else:
debug["P_validacion"] = f"OK: IVA {i} ~ {iva_esperado} (dif={diferencia:.2f})"

    # Recalcular Total si ahora tenemos los componentes
if g > 0 and i > 0 and t == 0.0:
t = round(g + i + exe - ret, 2)
debug["P_validacion"] += f" | T inferido = {t}"

    # ══════════════════════════════════════════════════════════
    # ASEGURANZA FINAL
    # Total debe ser = Gravado + IVA + Exento
    # ══════════════════════════════════════════════════════════
    # ASEGURANZA
if g > 0 and i > 0 and t > 0:
total_algebraico = round(g + i + exe, 2)

if g > t:
            # Gravado no puede ser mayor que el Total
g_viejo = g
g = max(0.0, round(t - i - exe, 2))
debug["P_aseguranza"] = (
f"CORRECCION: G {g_viejo} > T {t}. "
f"Recalculado G = {t} - {i} - {exe} = {g}"
)
elif abs(total_algebraico - t) > 0.50:
            # Los componentes no cuadran con el total
g_viejo = g
g = max(0.0, round(t - i - exe, 2))
debug["P_aseguranza"] = (
@@ -1094,19 +1014,19 @@
f"OK: {g} + {i} + {exe} = {total_algebraico} ≈ {t}"
)

    g   = max(0.0, g)
    i   = max(0.0, i)
    g = max(0.0, g)
    i = max(0.0, i)
exe = max(0.0, exe)

debug["resultado"] = (
f"FINAL => G={g:.2f} | I={i:.2f} | EXE={exe:.2f} | T={t:.2f} | "
        f"IVA_CALC={iva_calculado} | ESTRATEGIA={debug['estrategia_ganadora']}"
        f"IVA_CALC={iva_calculado} | EST={debug['estrategia_ganadora']}"
)

return g, i, exe, t, iva_calculado, debug

# ═══════════════════════════════════════════════════════════════
# HELPER: RENDERIZAR DEBUG EN EXPANDER
# HELPER: RENDERIZAR DEBUG
# ═══════════════════════════════════════════════════════════════

def _render_debug_montos(debug: dict):
@@ -1116,103 +1036,78 @@

estrategia = debug.get("estrategia_ganadora", "ninguna")
colores_estrategia = {
        "E1_regex":   "#3fb950",
        "E2_lineas":  "#79c0ff",
        "E3_tablas":  "#d2a8ff",
        "E4_fallback":"#d29922",
        "ninguna":    "#f85149",
        "E1_regex": "#3fb950",
        "E2_lineas": "#79c0ff",
        "E3_tablas": "#d2a8ff",
        "E4_fallback": "#d29922",
        "ninguna": "#f85149",
}
color_est = colores_estrategia.get(estrategia, "#aaaaaa")

html = '<div class="debug-box">'
html += (
f'<div style="margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid #30363d;">'
        f'<strong style="color:#cdd9e5">Estrategia ganadora:</strong> '
        f'<strong style="color:#cdd9e5">Estrategia:</strong> '
f'<span style="color:{color_est}; font-weight:bold;">{estrategia.upper()}</span>'
f'</div>'
)

    # E1: Regex
e1 = debug.get("E1_regex", {})
if e1:
html += (
f'<div><strong style="color:#cdd9e5">E1 Regex:</strong> '
            f'<span class="debug-ok">G={e1.get("g",0):.2f} | '
            f'EXE={e1.get("exe",0):.2f} | '
            f'I={e1.get("i",0):.2f} | '
            f'T={e1.get("t",0):.2f}</span></div>'
            f'<span class="debug-ok">G={e1.get("g",0):.2f} | EXE={e1.get("exe",0):.2f} | '
            f'I={e1.get("i",0):.2f} | T={e1.get("t",0):.2f}</span></div>'
)

    # E2: Lineas
e2 = debug.get("E2_lineas", {})
    if e2:
    if e2 and e2.get("t", 0) > 0:
html += (
f'<div><strong style="color:#cdd9e5">E2 Lineas:</strong> '
            f'<span style="color:#79c0ff">'
            f'G={e2.get("g",0):.2f}({e2.get("g_fuente","—")}) | '
            f'EXE={e2.get("exe",0):.2f} | '
            f'I={e2.get("i",0):.2f} | '
            f'T={e2.get("t",0):.2f}</span></div>'
            f'<span style="color:#79c0ff">G={e2.get("g",0):.2f} | EXE={e2.get("exe",0):.2f} | '
            f'I={e2.get("i",0):.2f} | T={e2.get("t",0):.2f}</span></div>'
)

    # E3: Tablas
e3 = debug.get("E3_tablas", {})
    if e3:
    if e3 and e3.get("t", 0) > 0:
html += (
f'<div><strong style="color:#cdd9e5">E3 Tablas:</strong> '
            f'<span style="color:#d2a8ff">'
            f'G={e3.get("g",0):.2f}({e3.get("g_fuente","—")}) | '
            f'EXE={e3.get("exe",0):.2f} | '
            f'I={e3.get("i",0):.2f} | '
            f'T={e3.get("t",0):.2f}</span></div>'
            f'<span style="color:#d2a8ff">G={e3.get("g",0):.2f} | EXE={e3.get("exe",0):.2f} | '
            f'I={e3.get("i",0):.2f} | T={e3.get("t",0):.2f}</span></div>'
)

    # Algebra, Validacion, Aseguranza
for label, key, cls in [
        ("Algebra",    "P_algebra",    ""),
        ("Algebra", "P_algebra", ""),
("Validacion", "P_validacion", ""),
("Aseguranza", "P_aseguranza", ""),
        ("E4 Fallback","E4_fallback",  ""),
]:
valor_str = str(debug.get(key, "—"))
        if valor_str.startswith("OK") or valor_str == "no necesario":
        if "OK" in valor_str or "necesario" in valor_str:
cls = "debug-ok"
        elif any(w in valor_str.upper() for w in ["CORRECCION", "WARN"]):
        elif "CORRECCION" in valor_str:
cls = "debug-warn"
        elif "no " in valor_str.lower() or valor_str == "—":
            cls = "debug-err"
else:
            cls = ""
            cls = "debug-err" if "no " in valor_str.lower() else ""
html += (
f'<div><strong style="color:#cdd9e5">{label}:</strong> '
f'<span class="{cls}">{valor_str}</span></div>'
)

    montos = debug.get("montos_raw", [])
    if montos:
        montos_str = ", ".join([f"${m:.2f}" for m in montos[:8]])
        html += (
            f'<div style="margin-top:6px">'
            f'<strong style="color:#cdd9e5">Montos E4 (pool):</strong> '
            f'<span style="color:#79c0ff">{montos_str}</span></div>'
        )

resultado = debug.get("resultado", "")
if resultado:
html += (
            f'<div style="margin-top:8px;border-top:1px solid #30363d;'
            f'padding-top:6px"><strong style="color:#e3b341">{resultado}</strong></div>'
            f'<div style="margin-top:8px;border-top:1px solid #30363d;padding-top:6px">'
            f'<strong style="color:#e3b341">{resultado}</strong></div>'
)

html += '</div>'
st.markdown(html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# MOTOR PRINCIPAL — V10
# MOTOR PRINCIPAL V10
# ═══════════════════════════════════════════════════════════════

def extraer_compras_nativo_pro_v10(file_bytes, cliente_activo, proveedores_cache=None):
    """Motor V10: 4 estrategias en cascada para CCF y facturas."""
motor = "Nativo"

try:
@@ -1230,15 +1125,15 @@
motor = "OCR"
with pdfplumber.open(BytesIO(file_bytes)) as pdf:
for page in pdf.pages:
                    img     = page.to_image(resolution=300)
                    img = page.to_image(resolution=300)
ocr_txt = pytesseract.image_to_string(img.original, lang='spa')
                    texto_lineal  += ocr_txt + "\n"
                    texto_lineal += ocr_txt + "\n"
texto_completo = texto_lineal

if len(texto_completo.strip()) < 50:
return {"error": "El PDF no tiene texto legible ni imagen procesable."}

        t_clean     = re.sub(r'\s+', ' ', texto_completo)
        t_clean = re.sub(r'\s+', ' ', texto_completo)
t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
@@ -1247,7 +1142,7 @@

if m_ctrl:
ctrl = m_ctrl.group(1).replace("O", "0")
            m_t  = re.search(r"DTE-(\d{2})", ctrl)
            m_t = re.search(r"DTE-(\d{2})", ctrl)
if m_t:
tipo = m_t.group(1)

@@ -1283,18 +1178,25 @@
if len(texto_emisor.strip()) < 100:
texto_emisor = texto_lineal[:1500]

        prov_db = proveedores_cache if proveedores_cache is not None else cargar_proveedores_json()
        prov_db = (
            proveedores_cache
            if proveedores_cache is not None
            else cargar_proveedores_json()
        )

        nit_prov, confianza_nit = _extraer_nit_completo_pdf(texto_lineal, texto_visual, file_bytes)
        nit_prov, confianza_nit = _extraer_nit_completo_pdf(
            texto_lineal, texto_visual, file_bytes
        )
if not nit_prov:
nit_prov, confianza_nit = _buscar_nit_en_todas_lineas(texto_emisor)

if nit_prov in (nit_receptor, dui_receptor):
            nit_prov      = ""
            nit_prov = ""
confianza_nit = "baja"

nom_prov, confianza_rs = _extraer_razon_social_v6(
            nit_prov, texto_emisor, prov_db, cliente_activo.get('nombre', ''), file_bytes
            nit_prov, texto_emisor, prov_db,
            cliente_activo.get('nombre', ''), file_bytes
)

es_nuevo = True
@@ -1307,7 +1209,6 @@
if len(nit_prov) == 9:
dui_prov = nit_prov

        # ─── FOVIAL / COTRANS / RETENCIONES ───────────────────
e_fovial, ret, perc = 0.0, 0.0, 0.0

m_fovial = re.search(r"FOVIAL.{0,50}", texto_completo, re.I)
@@ -1330,33 +1231,32 @@
if m_ret:
ret = limpiar_monto(m_ret.group(1))

        # ─── MOTOR V10 ─────────────────────────────────────────
g, i, exe, t, iva_calculado, debug_montos = _extraer_montos_v10(
texto_completo, t_clean, tipo, e_fovial, ret, file_bytes
)

return {
            "fecha":         fecha,
            "nit_prov":      nit_prov,
            "dui_prov":      dui_prov,
            "nom_prov":      nom_prov,
            "tipo":          tipo,
            "ctrl":          ctrl,
            "gen":           gen,
            "exe":           round(exe,      2),
            "gra":           round(g,        2),
            "iva":           round(i,        2),
            "ret":           round(ret,      2),
            "perc":          perc,
            "tot":           round(t,        2),
            "estado":        "OK",
            "iva_calc":      iva_calculado,
            "es_nuevo":      es_nuevo,
            "nit_nuevo":     nit_prov,
            "motor":         motor,
            "fecha": fecha,
            "nit_prov": nit_prov,
            "dui_prov": dui_prov,
            "nom_prov": nom_prov,
            "tipo": tipo,
            "ctrl": ctrl,
            "gen": gen,
            "exe": round(exe, 2),
            "gra": round(g, 2),
            "iva": round(i, 2),
            "ret": round(ret, 2),
            "perc": perc,
            "tot": round(t, 2),
            "estado": "OK",
            "iva_calc": iva_calculado,
            "es_nuevo": es_nuevo,
            "nit_nuevo": nit_prov,
            "motor": motor,
"confianza_nit": confianza_nit,
            "confianza_rs":  confianza_rs,
            "_debug":        debug_montos,
            "confianza_rs": confianza_rs,
            "_debug": debug_montos,
}

except Exception as err:
@@ -1402,11 +1302,16 @@
# INICIALIZACION DE ESTADO
# ═══════════════════════════════════════════════════════════════

if 'cola_revision'     not in st.session_state: st.session_state.cola_revision     = []
if 'comp_uploader_key' not in st.session_state: st.session_state.comp_uploader_key = str(time.time())
if 'db_compras'        not in st.session_state: st.session_state.db_compras        = pd.DataFrame()
if 'archivos_comp'     not in st.session_state: st.session_state.archivos_comp     = set()
if 'reporte_compras'   not in st.session_state: st.session_state.reporte_compras   = None
if 'cola_revision' not in st.session_state:
    st.session_state.cola_revision = []
if 'comp_uploader_key' not in st.session_state:
    st.session_state.comp_uploader_key = str(time.time())
if 'db_compras' not in st.session_state:
    st.session_state.db_compras = pd.DataFrame()
if 'archivos_comp' not in st.session_state:
    st.session_state.archivos_comp = set()
if 'reporte_compras' not in st.session_state:
    st.session_state.reporte_compras = None

# ═══════════════════════════════════════════════════════════════
# SIDEBAR — CARGA Y PROCESAMIENTO
@@ -1426,22 +1331,22 @@

if archivos and st.button("Procesar Compras", type="primary", use_container_width=True):

        extracted           = []
        duplicados          = []
        extracted = []
        duplicados = []
iva_calculado_files = []
        intrusos            = []
        invalidos           = []
        corruptos           = []
        nuevos_proveedores  = {}
        intrusos = []
        invalidos = []
        corruptos = []
        nuevos_proveedores = {}

nuevos = [f for f in archivos if f.name not in st.session_state.archivos_comp]

if nuevos:
            bar          = st.progress(0)
            bar = st.progress(0)
txt_progreso = st.empty()
            t_inicio     = time.time()
            total        = len(nuevos)
            prov_cache   = cargar_proveedores_json()
            t_inicio = time.time()
            total = len(nuevos)
            prov_cache = cargar_proveedores_json()

for idx, f in enumerate(nuevos):

@@ -1450,7 +1355,7 @@

if idx > 0:
elapsed = time.time() - t_inicio
                    eta     = int((elapsed / idx) * (total - idx))
                    eta = int((elapsed / idx) * (total - idx))
m_t2, s = divmod(eta, 60)
txt_progreso.markdown(
f"Procesando: **{idx+1}** de **{total}** "
@@ -1471,7 +1376,7 @@

res = extraer_compras_nativo_pro_v10(file_bytes, cliente, prov_cache)

                codigo_gen  = res.get('gen', '')
                codigo_gen = res.get('gen', '')
dup_memoria = (
not st.session_state.db_compras.empty
and codigo_gen != ""
@@ -1491,7 +1396,7 @@
elif dup_memoria or dup_lote:
duplicados.append(f.name)
elif "error" not in res:
                    fecha_str    = str(res.get('fecha', '')).strip()
                    fecha_str = str(res.get('fecha', '')).strip()
nom_prov_str = str(res.get('nom_prov', '')).strip()
nit_prov_str = str(res.get('nit_prov', '')).strip()
nom_es_placeholder = nom_prov_str in (
@@ -1514,8 +1419,8 @@
if necesita_revision:
st.session_state.cola_revision.append({
"archivo": f.name,
                            "bytes":   file_bytes,
                            "datos":   res
                            "bytes": file_bytes,
                            "datos": res
})
else:
if res.get('iva_calc'):
@@ -1538,12 +1443,12 @@
guardar_lote_proveedores(nuevos_proveedores)

st.session_state.reporte_compras = {
                "intrusos":           intrusos,
                "invalidos":          invalidos,
                "duplicados":         duplicados,
                "iva_calc":           iva_calculado_files,
                "intrusos": intrusos,
                "invalidos": invalidos,
                "duplicados": duplicados,
                "iva_calc": iva_calculado_files,
"nuevos_proveedores": nuevos_proveedores,
                "corruptos":          corruptos
                "corruptos": corruptos
}

if extracted:
@@ -1581,9 +1486,9 @@

if st.session_state.cola_revision:

    total_cola  = len(st.session_state.cola_revision)
    total_cola = len(st.session_state.cola_revision)
item_actual = st.session_state.cola_revision[0]
    datos       = item_actual["datos"]
    datos = item_actual["datos"]

st.markdown("""
   <div class="inbox-revision">
@@ -1596,7 +1501,7 @@
   """, unsafe_allow_html=True)

conf_nit = datos.get("confianza_nit", "baja")
    conf_rs  = datos.get("confianza_rs",  "baja")
    conf_rs = datos.get("confianza_rs", "baja")

st.markdown(f"""
   <div class="confianza-row">
@@ -1642,15 +1547,14 @@
if nom_sugerido in [NOMBRE_PLACEHOLDER, "ESCRIBE EL NOMBRE AQUI"]:
nom_sugerido = ""

        nit_actual         = datos.get("nit_prov", "")
        nit_actual = datos.get("nit_prov", "")
es_nuevo_proveedor = datos.get("es_nuevo", True)

if nit_actual and es_nuevo_proveedor:
st.info(f"Proveedor Nuevo: NIT {nit_actual} no esta en el directorio.")
elif nit_actual:
st.success(f"Proveedor Existente: NIT {nit_actual}")

        # ── METRICS V10: 4 campos ──────────────────────────────
st.markdown("**Montos detectados por el motor:**")
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
@@ -1678,7 +1582,6 @@
unsafe_allow_html=True
)

        # Validacion inmediata de coherencia
try:
gra_v = float(datos.get('gra', 0))
exe_v = float(datos.get('exe', 0))
@@ -1698,13 +1601,11 @@
except Exception:
pass

        # ── DEBUG ─────────────────────────────────────────────
with st.expander("Ver diagnostico detallado (V10)"):
_render_debug_montos(datos.get("_debug", {}))

st.divider()

        # ── FORMULARIO ────────────────────────────────────────
with st.form(key=f"form_rev_{item_actual['archivo']}_{total_cola}"):

f_fecha = st.text_input(
@@ -1781,9 +1682,8 @@
help="IVA = Gravado x 13%"
)

            # Validacion tributaria en tiempo real
if f_gra > 0:
                iva_esp   = round(f_gra * 0.13, 2)
                iva_esp = round(f_gra * 0.13, 2)
total_esp = round(f_gra + iva_esp + f_exe_manual, 2)
if f_iva > 0 and abs(iva_esp - f_iva) > 0.05:
st.warning(
@@ -1799,19 +1699,18 @@
st.write("")
c_btn1, c_btn2, c_btn3 = st.columns(3)
with c_btn1:
                submit_aprobar      = st.form_submit_button(
                submit_aprobar = st.form_submit_button(
"Aprobar y Guardar", type="primary", use_container_width=True
)
with c_btn2:
submit_guardar_prov = st.form_submit_button(
"Guardar Proveedor", use_container_width=True
)
with c_btn3:
                submit_descartar    = st.form_submit_button(
                submit_descartar = st.form_submit_button(
"Descartar", use_container_width=True
)

        # ── LOGICA: Guardar proveedor ──────────────────────────
if submit_guardar_prov:
if not f_nom or not nit_actual:
st.error("Debes llenar la Razon Social y tener un NIT valido.")
@@ -1825,7 +1724,6 @@
time.sleep(1)
st.rerun()

        # ── LOGICA: Aprobar ────────────────────────────────────
if submit_aprobar:
if not f_fecha or not f_gen or not f_nom or f_tot <= 0:
st.error("Rellena todos los campos marcados con (*) para continuar.")
@@ -1836,15 +1734,18 @@
if item["datos"].get("nit_prov") == nit_actual:
item["datos"]["nom_prov"] = f_nom.upper()

                datos["fecha"]    = f_fecha.strip()
                datos["gen"]      = f_gen.strip().upper()
                datos["fecha"] = f_fecha.strip()
                datos["gen"] = f_gen.strip().upper()
datos["nom_prov"] = f_nom.strip().upper()
                datos["tot"]      = round(f_tot, 2)
                datos["ret"]      = round(f_ret, 2)
                datos["tot"] = round(f_tot, 2)
                datos["ret"] = round(f_ret, 2)

if f_gra > 0:
datos["gra"] = round(f_gra, 2)
                    datos["iva"] = round(f_iva, 2) if f_iva > 0 else round(f_gra * 0.13, 2)
                    datos["iva"] = (
                        round(f_iva, 2) if f_iva > 0
                        else round(f_gra * 0.13, 2)
                    )
datos["exe"] = round(f_exe_manual, 2)
elif f_tot > 0:
try:
@@ -1853,9 +1754,9 @@
iva_actual = 0.0
if iva_actual == 0.0:
base = f_tot - f_ret - f_exe_manual
                        datos["gra"]      = round(base / 1.13, 2)
                        datos["iva"]      = round(base - datos["gra"], 2)
                        datos["exe"]      = round(f_exe_manual, 2)
                        datos["gra"] = round(base / 1.13, 2)
                        datos["iva"] = round(base - datos["gra"], 2)
                        datos["exe"] = round(f_exe_manual, 2)
datos["iva_calc"] = True

datos["archivo"] = item_actual["archivo"]
@@ -1874,7 +1775,6 @@
time.sleep(1)
st.rerun()

        # ── LOGICA: Descartar ──────────────────────────────────
if submit_descartar:
st.session_state.cola_revision.pop(0)
st.warning("Documento descartado.")
@@ -1907,9 +1807,9 @@
st.success("**0 Danados.**")

with c2:
        intrusos_n  = len(rep.get("intrusos", []))
        intrusos_n = len(rep.get("intrusos", []))
invalidos_n = len(rep.get("invalidos", []))
        total_rej   = intrusos_n + invalidos_n
        total_rej = intrusos_n + invalidos_n
if total_rej:
st.error(
f"**{total_rej} Rechazados** "
@@ -1954,7 +1854,7 @@
st.divider()

# ═══════════════════════════════════════════════════════════════
# TABLA DE RESULTADOS Y EXPORTACION
# TABLA DE RESULTADOS
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_compras.empty:
@@ -1963,9 +1863,14 @@
st.markdown("### Filtros de Auditoria Rapida")
col_f1, col_f2 = st.columns([2, 1])
with col_f1:
        busqueda = st.text_input("Buscar Proveedor", placeholder="Nombre, NIT o UUID...")
        busqueda = st.text_input(
            "Buscar Proveedor",
            placeholder="Nombre, NIT o UUID..."
        )
with col_f2:
        tipos_disponibles = df['tipo'].unique().tolist() if 'tipo' in df.columns else []
        tipos_disponibles = (
            df['tipo'].unique().tolist() if 'tipo' in df.columns else []
        )
filtro_tipo = st.multiselect(
"Filtrar por Tipo DTE",
options=tipos_disponibles,
@@ -1995,28 +1900,72 @@
st.info("No hay registros que coincidan con los filtros aplicados.")
else:
df_h = pd.DataFrame({
                "A. Fecha Emision":         df_filtrado["fecha"],
                "B. Clase":                 "4",
                "C. Tipo Doc":              df_filtrado["tipo"],
                "D. Num Documento":         df_filtrado["gen"],
                "E. NIT/NRC Prov":          df_filtrado["nit_prov"],
                "F. Nombre Prov":           df_filtrado["nom_prov"],
                "G. Compra Ext/NS":         df_filtrado["exe"],
                "H. Internacion Ext/NS":    0.00,
                "I. Importacion Ext/NS":    0.00,
                "J. Compra Gravada":        df_filtrado["gra"],
                "A. Fecha Emision": df_filtrado["fecha"],
                "B. Clase": "4",
                "C. Tipo Doc": df_filtrado["tipo"],
                "D. Num Documento": df_filtrado["gen"],
                "E. NIT/NRC Prov": df_filtrado["nit_prov"],
                "F. Nombre Prov": df_filtrado["nom_prov"],
                "G. Compra Ext/NS": df_filtrado["exe"],
                "H. Internacion Ext/NS": 0.00,
                "I. Importacion Ext/NS": 0.00,
                "J. Compra Gravada": df_filtrado["gra"],
"K. Inter. Gravada Bienes": 0.00,
"L. Impor. Gravada Bienes": 0.00,
                "M. Impor. Gravada Serv":   0.00,
                "N. Credito Fiscal (IVA)":  df_filtrado["iva"],
                "O. Total Compras":         df_filtrado["tot"],
                "P. DUI Prov":              df_filtrado["dui_prov"],
                "Q. Tipo Operacion":        "1",
                "R. Clasificacion":         "1",
                "S. Sector":                "1",
                "T. Tipo Costo/Gasto":      "1",
                "U. Num Anexo":             "3"
                "M. Impor. Gravada Serv": 0.00,
                "N. Credito Fiscal (IVA)": df_filtrado["iva"],
                "O. Total Compras": df_filtrado["tot"],
                "P. DUI Prov": df_filtrado["dui_prov"],
                "Q. Tipo Operacion": "1",
                "R. Clasificacion": "1",
                "S. Sector": "1",
                "T. Tipo Costo/Gasto": "1",
                "U. Num Anexo": "3"
})

cols_num = [
                "G. Compra Ext/NS", "H. Internacion
                "G. Compra Ext/NS", "H. Internacion Ext/NS",
                "I. Importacion Ext/NS", "J. Compra Gravada",
                "K. Inter. Gravada Bienes", "L. Impor. Gravada Bienes",
                "M. Impor. Gravada Serv", "N. Credito Fiscal (IVA)",
                "O. Total Compras"
            ]

            st.dataframe(
                df_h.style.format({c: "{:.2f}" for c in cols_num}),
                hide_index=True,
                use_container_width=True
            )

            col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
            with col_kpi1:
                st.metric("Registros", len(df_h))
            with col_kpi2:
                st.metric("Total Exento", f"${df_h['G. Compra Ext/NS'].sum():,.2f}")
            with col_kpi3:
                st.metric("Total Gravado", f"${df_h['J. Compra Gravada'].sum():,.2f}")
            with col_kpi4:
                st.metric("Total IVA CF", f"${df_h['N. Credito Fiscal (IVA)'].sum():,.2f}")
            with col_kpi5:
                st.metric("Total General", f"${df_h['O. Total Compras'].sum():,.2f}")

            st.write("")
            if st.button("Generar Excel para Hacienda", type="primary", use_container_width=True):
                ventana_descarga_compras(df_h, "F07_Compras_Proveedores.xlsx")

    with tab2:
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.write(
                f"Registros filtrados: **{len(df_filtrado)}** "
                f"de **{len(df)}** totales"
            )
        with col_a2:
            motores = (
                df['motor'].value_counts().to_dict() if 'motor' in df.columns else {}
            )
            for motor_name, count in motores.items():
                st.write(f"Motor {motor_name}: **{count}** documentos")

        cols_mostrar = [c for c in df_filtrado.columns if c != "_debug"]
        st.dataframe(df_filtrado[cols_mostrar], use_container_width=True)
