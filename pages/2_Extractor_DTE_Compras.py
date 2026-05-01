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
    .debug-row {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        border-bottom: 1px solid #2a2a2a;
        font-size: 12px;
        font-family: monospace;
    }
    .debug-label { color: #777; }
    .debug-ok    { color: #66cc66; font-weight: bold; }
    .debug-fail  { color: #cc4444; font-weight: bold; }
    .debug-warn  { color: #ffaa00; font-weight: bold; }
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

# ═══════════════════════════════════════════════════════════════
# BASE DE DATOS DE PROVEEDORES
# ═══════════════════════════════════════════════════════════════

def cargar_proveedores_json():
    if not os.path.exists(ARCHIVO_PROVEEDORES):
        return {}
    try:
        with open(ARCHIVO_PROVEEDORES, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = {"nombre": v, "nrc": ""}
        return data
    except Exception:
        return {}


def guardar_proveedor_rapido(nit, nombre):
    if not os.path.exists("data"):
        os.makedirs("data")
    db = cargar_proveedores_json()
    nrc_existente = db.get(nit, {}).get("nrc", "") if isinstance(db.get(nit), dict) else ""
    db[nit] = {"nombre": nombre.strip().upper(), "nrc": nrc_existente}
    try:
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as err:
        st.error(f"Error al guardar proveedor: {err}")


def guardar_lote_proveedores(nuevos_proveedores: dict):
    if not nuevos_proveedores:
        return
    if not os.path.exists("data"):
        os.makedirs("data")
    db = cargar_proveedores_json()
    for nit, nombre in nuevos_proveedores.items():
        if nit and nombre:
            nrc_existente = db.get(nit, {}).get("nrc", "") if isinstance(db.get(nit), dict) else ""
            db[nit] = {"nombre": str(nombre).strip().upper(), "nrc": nrc_existente}
    try:
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as err:
        st.error(f"Error al guardar lote: {err}")

# ═══════════════════════════════════════════════════════════════
# EXPORTACION EXCEL
# ═══════════════════════════════════════════════════════════════

def to_excel_hacienda_compras(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Compras_F07')
        workbook  = writer.book
        worksheet = writer.sheets['Compras_F07']
        fmt_texto   = workbook.add_format({'num_format': '@'})
        fmt_num_izq = workbook.add_format({'num_format': '0.00', 'align': 'left'})

        def get_max_len(col_idx):
            try:
                return max(
                    df.iloc[:, col_idx].astype(str).map(len).max() if not df.empty else 15,
                    15
                ) + 2
            except Exception:
                return 17

        worksheet.set_column(0,  0,  10,             fmt_texto)
        worksheet.set_column(1,  1,  1,              fmt_texto)
        worksheet.set_column(2,  2,  2,              fmt_texto)
        worksheet.set_column(3,  3,  get_max_len(3), fmt_texto)
        worksheet.set_column(4,  4,  14,             fmt_texto)
        worksheet.set_column(5,  5,  get_max_len(5), fmt_texto)
        worksheet.set_column(6,  14, 10.71,          fmt_num_izq)
        worksheet.set_column(15, 15, 9,              fmt_texto)
        worksheet.set_column(16, 20, 1,              fmt_texto)

    output.seek(0)
    return output.getvalue()

# ═══════════════════════════════════════════════════════════════
# FUNCIONES UTILITARIAS
# ═══════════════════════════════════════════════════════════════

def limpiar_monto(monto_str):
    try:
        s = re.sub(r'[^\d.,]', '', str(monto_str)).strip()
        if not s:
            return 0.0
        ultimo_sep = re.search(r'([.,])(\d{1,4})$', s)
        if ultimo_sep:
            decimals = ultimo_sep.group(2)
            enteros  = re.sub(r'[^\d]', '', s[:ultimo_sep.start()])
            if not enteros:
                enteros = "0"
            return round(float(f"{enteros}.{decimals}"), 2)
        else:
            return float(re.sub(r'[^\d]', '', s))
    except (ValueError, AttributeError):
        return 0.0


def extraer_y_formatear_fecha(texto):
    m = re.search(
        r"\b(20[2-3]\d)\s*[-/]\s*(0[1-9]|1[0-2])\s*[-/]\s*([0-2]\d|3[01])\b",
        texto
    )
    if m:
        return f"{int(m.group(3)):02d}/{int(m.group(2)):02d}/{m.group(1)}"

    m2 = re.search(
        r"\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(20[2-3]\d)\b",
        texto
    )
    if m2:
        p1, p2, y = int(m2.group(1)), int(m2.group(2)), m2.group(3)
        es_selectos = "SELECTOS" in texto.upper()
        if es_selectos and p1 <= 12 and p2 <= 31:
            return f"{p2:02d}/{p1:02d}/{y}"
        if p1 <= 12 and p2 > 12:
            return f"{p2:02d}/{p1:02d}/{y}"
        elif p2 <= 12 and p1 > 12:
            return f"{p1:02d}/{p2:02d}/{y}"
        elif p2 <= 12 and p1 <= 31:
            return f"{p1:02d}/{p2:02d}/{y}"

    m3 = re.search(
        r"(?:FECHA\s*DE\s*EMISI[OO]N|FECHA\s*DE\s*GENERACI[OO]N|FECHA)"
        r"[^\d]*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})",
        texto, re.I
    )
    if m3:
        d, mo, y = int(m3.group(1)), int(m3.group(2)), int(m3.group(3))
        if "SELECTOS" in texto.upper() and d <= 12 and mo <= 31:
            return f"{mo:02d}/{d:02d}/{y}"
        if d <= 12 and mo > 12:
            d, mo = mo, d
        if mo <= 12:
            return f"{d:02d}/{mo:02d}/{y}"

    return ""


def normalizar_nombre_proveedor(nombre_raw, cliente_nombre):
    if not nombre_raw:
        return NOMBRE_PLACEHOLDER
    nombre = re.sub(
        r"^(?:(?:O\s*)?RAZ[OO]N\s*SOCIAL|NOMBRE(?: O RAZ[OO]N SOCIAL)?|"
        r"CLIENTE|NOMBRE COMERCIAL|COMERCIAL)[\s:]*",
        "", nombre_raw, flags=re.I
    ).strip()
    nombre = re.sub(r"^[^A-Za-z0-9]+", "", nombre).strip()
    if (
        len(nombre) > 65
        or len(nombre) < 4
        or nombre.upper() in NOMBRES_INVALIDOS
        or any(bad in nombre.upper() for bad in BASURA_ESTRICTA)
    ):
        return NOMBRE_PLACEHOLDER
    palabras_cliente = cliente_nombre.upper().split()[:2]
    if any(p in nombre.upper() for p in palabras_cliente if len(p) > 3):
        return NOMBRE_PLACEHOLDER
    return nombre.upper()


def mostrar_indicador_confianza(confianza):
    c = str(confianza).lower().strip()
    if c == "alta":
        return '<span class="indicador-confianza confianza-alta">ALTA</span>'
    elif c == "media":
        return '<span class="indicador-confianza confianza-media">MEDIA</span>'
    elif c == "cache":
        return '<span class="indicador-confianza confianza-cache">CACHE</span>'
    elif c == "tabla":
        return '<span class="indicador-confianza confianza-tabla">TABLA</span>'
    elif c == "ocr":
        return '<span class="indicador-confianza confianza-ocr">OCR</span>'
    else:
        return '<span class="indicador-confianza confianza-baja">BAJA</span>'

# ═══════════════════════════════════════════════════════════════
# HELPERS PARA CACHE FLEXIBLE
# ═══════════════════════════════════════════════════════════════

def _normalizar_nit_para_cache(nit_raw):
    return re.sub(r'[^0-9]', '', str(nit_raw))


def _buscar_en_cache_flexible(nit_prov, prov_db):
    if not nit_prov or not prov_db:
        return "", False

    nit_solo_digitos = _normalizar_nit_para_cache(nit_prov)

    if nit_prov in prov_db:
        nombre = prov_db[nit_prov].get("nombre", "")
        if nombre and nombre != NOMBRE_PLACEHOLDER:
            return nombre, True

    for clave_json, valor in prov_db.items():
        if _normalizar_nit_para_cache(clave_json) == nit_solo_digitos:
            nombre = valor.get("nombre", "") if isinstance(valor, dict) else str(valor)
            if nombre and nombre != NOMBRE_PLACEHOLDER:
                return nombre, True

    if len(nit_solo_digitos) >= 8:
        prefijo = nit_solo_digitos[:8]
        for clave_json, valor in prov_db.items():
            if _normalizar_nit_para_cache(clave_json).startswith(prefijo):
                nombre = valor.get("nombre", "") if isinstance(valor, dict) else str(valor)
                if nombre and nombre != NOMBRE_PLACEHOLDER:
                    return nombre, True

    return "", False

# ═══════════════════════════════════════════════════════════════
# EXTRACCION DE NIT
# ═══════════════════════════════════════════════════════════════

def _extraer_nit_completo_pdf(texto_lineal, texto_visual, file_bytes):
    for texto in [texto_lineal, texto_visual]:
        t = re.sub(r'\s+', ' ', texto).upper()

        m = re.search(r'NIT\s*[#:]?\s*(\d{4})\s*-\s*(\d{6})\s*-\s*(\d{3})\s*-\s*(\d)', t)
        if m:
            return f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}", "alta"

        m = re.search(r'NIT\s*[#:]?\s*(\d{14})', t)
        if m:
            return m.group(1), "alta"

        m = re.search(r'\b([01]\d{13})\b', t)
        if m:
            nit = m.group(1)
            if int(nit) < 100000000000000:
                return nit, "media"

        m = re.search(r'DUI\s*[#:]?\s*(\d{8})\s*-?\s*(\d)', t)
        if m:
            return f"{m.group(1)}{m.group(2)}", "media"

    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:3]:
                for table in (page.extract_tables() or []):
                    for row in table:
                        for cell in (row or []):
                            if not cell:
                                continue
                            cell_str = str(cell).upper()
                            m = re.search(r'\b(0\d{13}|1\d{13})\b', cell_str)
                            if m:
                                return m.group(1), "media"
                            m = re.search(r'(\d{4})-?(\d{6})-?(\d{3})-?(\d)', cell_str)
                            if m:
                                nit = f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"
                                if nit.startswith('0') or nit.startswith('1'):
                                    return nit, "media"
    except Exception:
        pass

    return "", "baja"


def _buscar_nit_en_todas_lineas(texto_emisor):
    for linea in texto_emisor.split('\n'):
        linea_clean = linea.upper().strip()
        if re.search(r'^\d{4}\s*-?\s*\d{6}', linea_clean):
            m = re.search(r'(\d{4})\s*-?(\d{6})\s*-?(\d{3})\s*-?(\d)', linea_clean)
            if m:
                return f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}", "alta"
        m = re.search(r'\b(\d{14})\b', linea_clean)
        if m:
            if not re.search(r'(19|20)\d{2}', linea_clean):
                return m.group(1), "media"
    return "", "baja"

# ═══════════════════════════════════════════════════════════════
# EXTRACCION DE RAZON SOCIAL DE TABLAS
# ═══════════════════════════════════════════════════════════════

def _extraer_razon_social_de_tablas(file_bytes, nit_prov):
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:2]:
                tables = page.extract_tables()
                if not tables:
                    continue
                for table in tables:
                    for row_idx, row in enumerate(table):
                        if not row:
                            continue
                        for col_idx, cell in enumerate(row):
                            if not cell:
                                continue
                            cell_str = str(cell).strip()
                            if nit_prov and nit_prov in cell_str.replace('-', ''):
                                if col_idx + 1 < len(row):
                                    rc = str(row[col_idx + 1] or "").strip().upper()
                                    if len(rc) > 5 and len(rc) < 70 and not any(b in rc for b in BASURA_ESTRICTA) and not re.search(r'^\d+', rc):
                                        return rc, "tabla"
                                if row_idx + 1 < len(table):
                                    dc = str(table[row_idx + 1][col_idx] or "").strip().upper()
                                    if len(dc) > 5 and len(dc) < 70 and not any(b in dc for b in BASURA_ESTRICTA) and not re.search(r'^\d+', dc):
                                        return dc, "tabla"
                                if col_idx - 1 >= 0:
                                    lc = str(row[col_idx - 1] or "").strip().upper()
                                    if len(lc) > 5 and len(lc) < 70 and not any(b in lc for b in BASURA_ESTRICTA) and not re.search(r'^\d+', lc):
                                        return lc, "tabla"
                        for col_idx, cell in enumerate(row):
                            if not cell:
                                continue
                            cell_str = str(cell).strip().upper()
                            if any(marca in cell_str for marca in ["GRUPO ", "S.A.", "S.A DE", "LTDA", "S.R.L."]):
                                if len(cell_str) > 5 and len(cell_str) < 70 and not any(b in cell_str for b in BASURA_ESTRICTA):
                                    return cell_str, "tabla"
    except Exception:
        pass
    return "", "baja"

# ═══════════════════════════════════════════════════════════════
# EXTRACCION DE RAZON SOCIAL CON OCR LOCALIZADO
# ═══════════════════════════════════════════════════════════════

def _extraer_razon_social_con_ocr(file_bytes, nit_prov):
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:2]:
                img      = page.to_image(resolution=200)
                ocr_text = pytesseract.image_to_string(img.original, lang='spa')
                for linea in ocr_text.split('\n'):
                    if nit_prov and nit_prov[:8] in linea.replace('-', ''):
                        lineas_list = ocr_text.split('\n')
                        try:
                            idx = lineas_list.index(linea)
                        except ValueError:
                            idx = -1
                        if idx > -1:
                            for next_line in lineas_list[idx + 1:idx + 4]:
                                nc = next_line.strip().upper()
                                if len(nc) > 5 and len(nc) < 70 and not re.search(r'^\d+', nc) and not any(bad in nc for bad in BASURA_ESTRICTA):
                                    return nc, "ocr"
    except Exception:
        pass
    return "", "baja"

# ═══════════════════════════════════════════════════════════════
# EXTRACCION DE RAZON SOCIAL — V6
# ═══════════════════════════════════════════════════════════════

def _extraer_razon_social_v6(nit_prov, texto_emisor, prov_db, cliente_nombre, file_bytes):
    nombre_cache, encontrado = _buscar_en_cache_flexible(nit_prov, prov_db)
    if encontrado:
        return nombre_cache, "cache"

    patrones = [
        (
            r"(?:RAZ[OÓ]N\s*SOCIAL|NOMBRE\s+O\s+RAZ[OÓ]N\s*SOCIAL)\s*[:\-]?\s*"
            r"([A-Z][A-Za-z0-9\s\.\,\&\-]{4,60}?)(?=\s{2,}|\n|NIT|NRC|GIRO|ACTIVIDAD|$)",
            "alta"
        ),
        (
            r"(?<!\w)NOMBRE\s*[:\-]\s*"
            r"([A-Z][A-Za-z0-9\s\.\,\&\-]{4,60}?)(?=\s{2,}|\n|NIT|NRC|GIRO|ACTIVIDAD|$)",
            "alta"
        ),
        (
            r"NOMBRE\s+COMERCIAL\s*[:\-]?\s*"
            r"([A-Z][A-Za-z0-9\s\.\,\&\-]{4,60}?)(?=\s{2,}|\n|NIT|NRC|GIRO|$)",
            "media"
        ),
    ]

    for patron, confianza in patrones:
        m = re.search(patron, texto_emisor, re.IGNORECASE | re.MULTILINE)
        if not m:
            continue
        candidato = re.sub(r'\s+', ' ', m.group(1).strip()).rstrip('.,;:')
        if len(candidato) < 5 or len(candidato) > 65:
            continue
        if any(bad in candidato.upper() for bad in BASURA_ESTRICTA):
            continue
        if any(b in candidato.upper() for b in PALABRAS_BASURA):
            continue
        if re.search(r'\d{5,}', candidato):
            continue
        if sum(c.isdigit() for c in candidato) / max(len(candidato), 1) > 0.30:
            continue
        return candidato.upper(), confianza

    if nit_prov:
        rs_tabla, conf_tabla = _extraer_razon_social_de_tablas(file_bytes, nit_prov)
        if rs_tabla:
            return rs_tabla, conf_tabla

    if nit_prov:
        rs_ocr, conf_ocr = _extraer_razon_social_con_ocr(file_bytes, nit_prov)
        if rs_ocr:
            return rs_ocr, conf_ocr

    for linea in texto_emisor.split('\n')[:30]:
        L = linea.strip().upper()
        if len(L) < 5:
            continue
        if sum(c.isdigit() for c in L) / max(len(L), 1) > 0.3:
            continue
        if any(b in L for b in PALABRAS_BASURA):
            continue
        if any(bad in L for bad in BASURA_ESTRICTA):
            continue
        if re.search(r'\d{5,}', L):
            continue
        if any(marca in L for marca in MARCAS_COMERCIALES):
            clean = re.split(r'\s{4,}|NIT|NRC', L)[0].strip()
            palabras_cli = cliente_nombre.upper().split()[:2]
            if clean and not any(p in clean for p in palabras_cli if len(p) > 3):
                return clean, "media"

    return NOMBRE_PLACEHOLDER, "baja"

# ═══════════════════════════════════════════════════════════════
# EXTRACCION DE MONTOS — V8 (CON DEBUG INTEGRADO)
# ═══════════════════════════════════════════════════════════════

def _extraer_montos_v8(texto_completo, t_clean, tipo, e, ret):
    """
    V8: Extraccion por etiquetas + debug completo de cada paso.
    Retorna: (g, i, t, iva_calculado, debug)
    
    Pasos:
      1. Total por etiqueta exacta
      2. IVA por etiqueta exacta
      3. Gravado por etiqueta exacta
      4. Calculo algebraico (si faltan campos)
      5. Triple-loop fallback (solo si t == 0)
      6. Validacion de coherencia tributaria
      7. Guardia final: Gravado > Total -> recalcular
    """
    g, i, t = 0.0, 0.0, 0.0
    iva_calculado = False
    debug = {
        "P1_total":      "No encontrado",
        "P2_iva":        "No encontrado",
        "P3_gravado":    "No encontrado",
        "P4_calculo":    "No aplico",
        "P5_fallback":   "No aplico",
        "P6_validacion": "No aplico",
        "P7_guardia":    "No aplico",
        "montos_pdf":    [],
        "resultado":     ""
    }

    # ─────────────────────────────────────────────────────────
    # PASO 1: Total por etiqueta
    # ─────────────────────────────────────────────────────────
    patrones_total = [
        r"(?:TOTAL\s+A\s+PAGAR|MONTO\s+TOTAL\s+DE\s+LA\s+OPERACI[OO]N|"
        r"TOTAL\s+DE\s+LA\s+OPERACI[OO]N|TOTAL\s+OPERACI[OO]N|"
        r"VENTA\s+TOTAL|TOTAL\s+PAGAR|TOTAL\s+\$)"
        r"[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    ]
    for patron in patrones_total:
        m = re.search(patron, t_clean, re.I)
        if m:
            t = limpiar_monto(m.group(1))
            debug["P1_total"] = f"OK: {t} | match: '{m.group(0)[:50]}'"
            break

    # ─────────────────────────────────────────────────────────
    # PASO 2: IVA por etiqueta
    # ─────────────────────────────────────────────────────────
    patrones_iva = [
        r"(?:Impuesto\s+al\s+Valor\s+Agregado|I\.V\.A\.?|IVA)"
        r"(?:\s*\(?13\s*%\)?)?\s*[:\-]?\s*"
        r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:13\s*%\s*(?:de\s*)?IVA|IVA\s*13\s*%)"
        r"[^\d]{0,20}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    ]
    for patron in patrones_iva:
        m = re.search(patron, t_clean, re.I)
        if m:
            i = limpiar_monto(m.group(1))
            debug["P2_iva"] = f"OK: {i} | match: '{m.group(0)[:50]}'"
            break

    # ─────────────────────────────────────────────────────────
    # PASO 3: Gravado por etiqueta (PRIMER match, no el mayor)
    # ─────────────────────────────────────────────────────────
    patrones_gravado = [
        r"Subtotal\s+Gravado[^\d]{0,10}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"Monto\s+Sujeto\s+a\s+IVA[^\d]{0,10}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:Venta|Compra)\s+Gravada[^\d]{0,10}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:Sub\s*[Tt]otal|Subtotal)[^\d]{0,10}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    ]
    for patron in patrones_gravado:
        matches = re.findall(patron, t_clean, re.I)
        if matches:
            g = limpiar_monto(matches[0])
            debug["P3_gravado"] = f"OK: {g} | patron: '{patron[:50]}' | todos: {[limpiar_monto(x) for x in matches]}"
            break

    # ─────────────────────────────────────────────────────────
    # PASO 4: Calculo algebraico si faltan campos
    # ─────────────────────────────────────────────────────────
    ops = []
    if t > 0 and i > 0 and g == 0.0:
        g_calc = round(t - i - e + ret, 2)
        g = max(0.0, g_calc)
        ops.append(f"G={g} (T-I-E+Ret = {t}-{i}-{e}+{ret})")

    if t > 0 and i == 0.0 and g > 0:
        i = round(g * 0.13, 2)
        ops.append(f"I={i} (G*0.13 = {g}*0.13)")

    if t > 0 and i == 0.0 and g == 0.0 and tipo == "03":
        g = round((t + ret - e) / 1.13, 2)
        i = round(t + ret - e - g, 2)
        iva_calculado = True
        ops.append(f"G={g}, I={i} (tipo 03 descomposicion)")

    if ops:
        debug["P4_calculo"] = " | ".join(ops)

    # ─────────────────────────────────────────────────────────
    # PASO 5: Triple-loop fallback SOLO si t == 0
    # ─────────────────────────────────────────────────────────
    if t == 0.0:
        montos_raw = re.findall(
            r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            t_clean
        )
        valores = sorted(list(set(limpiar_monto(x) for x in montos_raw)), reverse=True)
        valores = [v for v in valores if v > 0.01]
        debug["montos_pdf"]  = valores[:15]
        debug["P5_fallback"] = f"Iniciando triple-loop con {len(valores)} montos"

        encontrado_fl = False
        for val_t in valores:
            if encontrado_fl:
                break
            for val_g in valores:
                if val_g >= val_t:
                    continue
                for val_i in valores:
                    if val_i >= val_g:
                        continue
                    if abs(round(val_g * 0.13, 2) - round(val_i, 2)) <= 0.05:
                        total_calc = round(val_g + val_i + e - ret, 2)
                        if abs(total_calc - round(val_t, 2)) <= 0.10:
                            g, i, t = val_g, val_i, val_t
                            encontrado_fl = True
                            debug["P5_fallback"] = f"OK: G={g}, I={i}, T={t}"
                            break

        if not encontrado_fl:
            debug["P5_fallback"] = "FALLO: no se encontro combinacion valida"
    else:
        debug["montos_pdf"] = []

    # ─────────────────────────────────────────────────────────
    # PASO 6: Validacion de coherencia tributaria
    # ─────────────────────────────────────────────────────────
    if g > 0 and i > 0:
        iva_esperado = round(g * 0.13, 2)
        diferencia   = abs(iva_esperado - i)
        if diferencia > 1.00:
            i_viejo = i
            i = iva_esperado
            debug["P6_validacion"] = f"IVA CORREGIDO: {i_viejo} -> {i} (esperado={iva_esperado}, diff={diferencia:.2f})"
        else:
            debug["P6_validacion"] = f"IVA coherente: {i} ≈ {iva_esperado} (diff={diferencia:.2f})"

    if g > 0 and i > 0 and t == 0.0:
        t = round(g + i + e - ret, 2)
        debug["P6_validacion"] += f" | Total calculado: {t}"

    # ─────────────────────────────────────────────────────────
    # PASO 7: Guardia — Gravado no puede ser mayor que Total
    # ─────────────────────────────────────────────────────────
    if g > 0 and t > 0 and g >= t:
        g_viejo = g
        g = round(t / 1.13, 2)
        i = round(t - g, 2)
        iva_calculado = True
        debug["P7_guardia"] = f"ALERTA: G={g_viejo} >= T={t}. Recalculado: G={g}, I={i}"
    else:
        if g > 0 and t > 0:
            debug["P7_guardia"] = f"OK: G={g} < T={t}"

    g = max(0.0, g)
    i = max(0.0, i)

    debug["resultado"] = f"G={g} | I={i} | T={t} | IVA_CALC={iva_calculado}"
    return g, i, t, iva_calculado, debug

# ═══════════════════════════════════════════════════════════════
# MOTOR DE EXTRACCION DTE COMPRAS — V8
# ═══════════════════════════════════════════════════════════════

def extraer_compras_nativo_pro_v8(file_bytes, cliente_activo, proveedores_cache=None):
    """Motor V8 — Debug integrado + guardia Gravado >= Total."""
    motor = "Nativo"

    try:
        texto_lineal = ""
        texto_visual = ""

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                texto_lineal += (page.extract_text(layout=False) or "") + "\n"
                texto_visual += (page.extract_text() or "") + "\n"

        texto_completo = texto_lineal + "\n" + texto_visual

        if len(texto_completo.strip()) < 80:
            motor = "OCR"
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    img     = page.to_image(resolution=300)
                    ocr_txt = pytesseract.image_to_string(img.original, lang='spa')
                    texto_lineal += ocr_txt + "\n"
            texto_completo = texto_lineal

        if len(texto_completo.strip()) < 50:
            return {"error": "El PDF no tiene texto legible ni imagen procesable."}

        t_clean     = re.sub(r'\s+', ' ', texto_completo)
        t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
        tipo = "01"
        ctrl = ""

        if m_ctrl:
            ctrl = m_ctrl.group(1).replace("O", "0")
            m_t  = re.search(r"DTE-(\d{2})", ctrl)
            if m_t:
                tipo = m_t.group(1)

        if not ctrl:
            return {"error_tipo": "No se detecto un Numero de Control DTE valido."}
        if tipo not in ["03", "05", "06"]:
            return {"error_tipo": f"El documento es DTE-{tipo}. Solo se admiten 03, 05 y 06."}

        nit_receptor = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
        dui_receptor = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))

        gen = ""
        m_url = re.search(r"CODGEN=([A-F0-9-]+)", t_no_spaces)
        if m_url:
            gen = m_url.group(1).upper()
        else:
            m_uuid = re.search(
                r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
                t_no_spaces
            )
            if m_uuid:
                raw = m_uuid.group(1).replace("-", "")
                if len(raw) >= 32:
                    gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"

        fecha = extraer_y_formatear_fecha(t_clean)

        partes_emisor = re.split(
            r"(?i)\b(?:RECEPTOR|CLIENTE:|CLIENTE\s|SOCIO/EMPRESA)\b",
            texto_lineal
        )
        texto_emisor = partes_emisor[0] if partes_emisor else texto_lineal
        if len(texto_emisor.strip()) < 100:
            texto_emisor = texto_lineal[:1500]

        prov_db = proveedores_cache if proveedores_cache is not None else cargar_proveedores_json()

        nit_prov, confianza_nit = _extraer_nit_completo_pdf(texto_lineal, texto_visual, file_bytes)
        if not nit_prov:
            nit_prov, confianza_nit = _buscar_nit_en_todas_lineas(texto_emisor)

        if nit_prov in (nit_receptor, dui_receptor):
            nit_prov      = ""
            confianza_nit = "baja"

        nom_prov, confianza_rs = _extraer_razon_social_v6(
            nit_prov, texto_emisor, prov_db, cliente_activo.get('nombre', ''), file_bytes
        )

        es_nuevo = True
        if nit_prov:
            _, _en_cache = _buscar_en_cache_flexible(nit_prov, prov_db)
            if _en_cache:
                es_nuevo = False

        if nom_prov == NOMBRE_PLACEHOLDER:
            nom_normalizado = normalizar_nombre_proveedor(nom_prov, "")
            if nom_normalizado != NOMBRE_PLACEHOLDER:
                nom_prov = nom_normalizado

        dui_prov = ""
        if len(nit_prov) == 9:
            dui_prov = nit_prov

        # ─────────────────────────────────────────────────────────
        # FOVIAL, COTRANS y EXENTOS
        # ─────────────────────────────────────────────────────────
        e, ret, perc = 0.0, 0.0, 0.0

        m_fovial = re.search(r"FOVIAL.{0,50}", texto_completo, re.I)
        if m_fovial:
            nums = re.findall(r"\d+[.,]\d{2,4}", m_fovial.group(0))
            if nums:
                e = max(limpiar_monto(n) for n in nums)

        m_cotrans = re.search(r"COTRANS.{0,50}", texto_completo, re.I)
        if m_cotrans:
            nums = re.findall(r"\d+[.,]\d{2,4}", m_cotrans.group(0))
            if nums:
                e += max(limpiar_monto(n) for n in nums)

        m_exe = re.search(
            r"(?:Ventas\s+Exentas|Total\s+Exento)[^\d]{0,30}?"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})",
            t_clean, re.I
        )
        if m_exe:
            val_exe = limpiar_monto(m_exe.group(1))
            if val_exe > e:
                e = val_exe

        m_ret = re.search(
            r"(?:Retenido|Retenci[oo]n)[^0-9]*"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})",
            t_clean, re.I
        )
        if m_ret:
            ret =
