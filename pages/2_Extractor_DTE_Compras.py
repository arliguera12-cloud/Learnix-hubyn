"""
Extractor DTE Compras — Learnix Hub
Soporta: DTE-03, DTE-05, DTE-06
Fuentes: PDF (motor V10) | JSON (formato Hacienda)
Validacion: Gemini 1.5 Flash
"""

import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import pytesseract
import json
import os
import gc
import sys
import platform
from io import BytesIO

# ═══════════════════════════════════════════════════════════════
# PATH PARA MODULOS CORE
# ═══════════════════════════════════════════════════════════════

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from core.extractor.gemini_validator import (
        necesita_gemini, validar_con_gemini,
        aplicar_correcciones_gemini, gemini_disponible
    )
    from core.extractor.filtros import render_panel_filtros
    from core.extractor.json_parser import parsear_json_dte, parsear_multiples_json
    CORE_DISPONIBLE = True
except ImportError:
    CORE_DISPONIBLE = False

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
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ═══════════════════════════════════════════════════════════════
# ESTILOS
# ═══════════════════════════════════════════════════════════════

st.markdown("""
<style>
    [data-testid="stAppViewContainer"],[data-testid="stHeader"]{background-color:#000!important}
    [data-testid="stSidebar"]{background-color:#161616!important;border-right:1px solid #333}
    h1,h2,h3,h4,h5,h6,p,label,span{color:#F7F5EE!important}
    [data-testid="stDataFrame"] span{color:inherit!important}
    div.stButton>button[kind="primary"],div.stDownloadButton>button[kind="primary"]{
        background-color:#003057!important;border:1px solid #00407A!important;border-radius:6px;transition:.3s}
    div.stButton>button[kind="primary"]*,div.stDownloadButton>button[kind="primary"]*{
        color:#fff!important;font-weight:700!important}
    div.stButton>button[kind="primary"]:hover,div.stDownloadButton>button[kind="primary"]:hover{
        background-color:#00407A!important}
    div.stButton>button[kind="secondary"]{
        background-color:#2A2A2A!important;border:1px solid #555!important;border-radius:6px}
    div.stButton>button[kind="secondary"]*{color:#fff!important;font-weight:700!important}
    div[data-testid="stAlert"]{min-height:80px;display:flex;align-items:center}
    .stAlert *{color:inherit!important}
    .scroll-list{max-height:150px;overflow-y:auto;padding:10px;background:#111;
        border-radius:5px;border:1px solid #333;font-family:monospace;font-size:13px;color:#66ff66}
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]{
        color:#4DA8DA!important;border-bottom-color:#4DA8DA!important}
    .stTabs [data-baseweb="tab-list"] button{color:#777!important}
    [data-testid="stExpander"]{background-color:#161616!important;border:1px solid #444!important;border-radius:6px}
    .alerta-activo{padding:10px;border-radius:6px;border-left:4px solid #00407A;
        background:#111;color:#fff;margin-bottom:15px;font-size:14px}
    .inbox-revision{background:#1a1a1a;border:1px solid #ffaa00;border-radius:10px;
        padding:20px;margin-top:20px;margin-bottom:20px}
    .indicador-confianza{display:inline-block;padding:3px 10px;border-radius:20px;
        font-size:11px;font-weight:700;margin-left:6px;letter-spacing:.5px}
    .confianza-alta{background:#1b5e20;color:#81c784;border:1px solid #2e7d32}
    .confianza-media{background:#e65100;color:#ffb74d;border:1px solid #bf360c}
    .confianza-baja{background:#7f1010;color:#ef9a9a;border:1px solid #b71c1c}
    .confianza-cache{background:#1a237e;color:#90caf9;border:1px solid #283593}
    .confianza-tabla{background:#4a148c;color:#ce93d8;border:1px solid #7b1fa2}
    .confianza-ocr{background:#01579b;color:#81d4fa;border:1px solid #0277bd}
    .badge-revision{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;
        font-weight:700;background:#ff6f00;color:#fff;letter-spacing:.5px}
    .metric-box{background:#161616;border:1px solid #30363d;border-radius:6px;
        padding:12px;margin:4px 0;text-align:center}
    .debug-box{background:#0d1117;border:1px solid #30363d;border-radius:6px;
        padding:10px 14px;font-family:monospace;font-size:12px;color:#8b949e;margin-bottom:6px}
    .debug-ok{color:#3fb950}.debug-err{color:#f85149}.debug-warn{color:#d29922}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

NOMBRE_PLACEHOLDER  = "ESCRIBE EL NOMBRE AQUI"
ARCHIVO_PROVEEDORES = "data/proveedores.json"

PALABRAS_BASURA = frozenset([
    "DOCUMENTO","TRIBUTARIO","ELECTRONICO","REPRESENTACION","RECEPTOR",
    "CLIENTE","EMISOR","FACTURA","CONSUMIDOR","FACTURACION","COMPROBANTE",
    "DIRECC","CODIGO","SELLO","VERSION","TRANSMISION","MINISTERIO","HACIENDA",
    "COLONIA","BOULEVARD","CALLE","AVENIDA","MUNICIPIO","GIRO:",
    "ACTIVIDAD","ECONOMICA","TIPO ESTABLECIMIENTO","SUCURSAL","AGENCIA",
    "PAGO DE","TARJETA","EFECTIVO","FECHA","HORA","EMISION","GENERACION","TELEFONO"
])
BASURA_ESTRICTA   = frozenset(["@","EMAIL","CORREO",".COM","WWW."])
NOMBRES_INVALIDOS = frozenset(["S.A. DE C.V.","C.V.","SA DE CV","LTDA","LTDA.","S.A.","DE C.V."])
MARCAS_COMERCIALES
