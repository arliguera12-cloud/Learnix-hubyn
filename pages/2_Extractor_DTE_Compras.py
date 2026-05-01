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
# EXTRACCION DE MONTOS DESDE TABLAS PDF — CCF ESPECIFICO
# ═══════════════════════════════════════════════════════════════

def _extraer_montos_desde_tablas_ccf(file_bytes):
    """
    Extrae montos del resumen al PIE de tabla de un CCF.

    Los CCF tienen una tabla de detalle de items y al final
    un bloque de resumen con etiquetas como:
        | Subtotal Gravado | 90.00 |
        | Venta Exenta     |  5.00 |
        | IVA (13%)        | 11.70 |
        | Total a Pagar    |106.70 |

    Esta funcion escanea TODAS las tablas de todas las paginas
    buscando ese bloque resumen al pie.
    """
    resultado = {
        "g": 0.0, "i": 0.0, "exe": 0.0, "t": 0.0,
        "fuente": "no encontrado"
    }

    # Palabras clave que identifican cada fila del resumen
    LABELS_GRAVADO = [
        "SUBTOTAL GRAVADO", "GRAVADO", "VENTA GRAVADA",
        "MONTO GRAVADO", "TOTAL GRAVADO", "SUJETO A IVA",
        "MONTO SUJETO"
    ]
    LABELS_EXENTO = [
        "VENTA EXENTA", "EXENTO", "NO GRAVADO", "EXENTA",
        "MONTO EXENTO", "TOTAL EXENTO", "NO SUJETO", "SUBTOTAL EXENTO"
    ]
    LABELS_IVA = [
        "IVA", "I.V.A", "IMPUESTO AL VALOR", "13%",
        "DEBITO FISCAL", "CREDITO FISCAL"
    ]
    LABELS_TOTAL = [
        "TOTAL A PAGAR", "TOTAL PAGAR", "TOTAL OPERACION",
        "MONTO TOTAL", "TOTAL DE LA OPERACION", "VENTA TOTAL",
        "TOTAL"
    ]

    def _es_monto_valido(valor_str):
        """Verifica que el string sea un monto numerico valido."""
        limpio = limpiar_monto(valor_str)
        return limpio > 0.0, limpio

    def _label_coincide(celda, lista_labels):
        """Comprueba si la celda contiene alguna de las etiquetas."""
        celda_up = str(celda or "").upper().strip()
        return any(lbl in celda_up for lbl in lista_labels)

    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tablas = page.extract_tables() or []
                for tabla in tablas:
                    if not tabla:
                        continue

                    for row in tabla:
                        if not row:
                            continue

                        # Filtrar celdas nulas para trabajar con el texto real
                        celdas = [str(c or "").strip() for c in row]

                        # Buscar filas de 2 columnas: [etiqueta, valor]
                        # o de N columnas donde la ultima es el valor
                        if len(celdas) < 2:
                            continue

                        etiqueta = celdas[0]
                        # El valor puede estar en la ultima columna no vacia
                        valor_str = ""
                        for c in reversed(celdas[1:]):
                            if c:
                                valor_str = c
                                break

                        if not etiqueta or not valor_str:
                            continue

                        ok, monto = _es_monto_valido(valor_str)
                        if not ok:
                            continue

                        if _label_coincide(etiqueta, LABELS_GRAVADO):
                            if resultado["g"] == 0.0:
                                resultado["g"] = monto
                                resultado["fuente"] = "tabla-resumen"

                        elif _label_coincide(etiqueta, LABELS_EXENTO):
                            if resultado["exe"] == 0.0:
                                resultado["exe"] = monto

                        elif _label_coincide(etiqueta, LABELS_IVA):
                            if resultado["i"] == 0.0:
                                resultado["i"] = monto

                        elif _label_coincide(etiqueta, LABELS_TOTAL):
                            # Tomar el mayor Total encontrado
                            if monto > resultado["t"]:
                                resultado["t"] = monto

    except Exception:
        pass

    return resultado


def _extraer_montos_pie_texto_ccf(t_clean):
    """
    Extrae montos del bloque de texto al PIE del CCF.

    Muchos CCF tienen el resumen como texto corrido al final:
        Subtotal Gravado $90.00 Venta Exenta $5.00 IVA $11.70 Total $106.70

    Esta funcion busca ese patron en el texto limpio.
    """
    resultado = {"g": 0.0, "i": 0.0, "exe": 0.0, "t": 0.0, "fuente": "no encontrado"}

    bloques_resumen = re.findall(
        r"(?:Subtotal|Total|Exento|IVA|Gravado).{0,300}",
        t_clean, re.I
    )

    # Patron completo de resumen en linea: etiqueta + monto
    PAT_GRAVADO = (
        r"(?:Subtotal\s+Gravado|Monto\s+Gravado|Venta\s+Gravada|"
        r"Sujeto\s+a\s+IVA)[^\d]{0,20}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})"
    )
    PAT_EXENTO  = (
        r"(?:Venta\s+Exenta|Exento|No\s+Gravado|Monto\s+Exento|"
        r"Subtotal\s+Exento|No\s+Sujeto)[^\d]{0,20}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})"
    )
    PAT_IVA     = (
        r"(?:Impuesto\s+al\s+Valor\s+Agregado|I\.?V\.?A\.?)"
        r"(?:\s*\(?\s*13\s*%\s*\)?)?\s*[:\-]?\s*"
        r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})"
    )
    PAT_TOTAL   = (
        r"(?:Total\s+a\s+Pagar|Total\s+Operaci[oo]n|Monto\s+Total|"
        r"Total\s+de\s+la\s+Operaci[oo]n|Total\s+Pagar)"
        r"[^\d]{0,20}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})"
    )

    for bloque in bloques_resumen:
        if resultado["g"] == 0.0:
            mg = re.search(PAT_GRAVADO, bloque, re.I)
            if mg:
                resultado["g"] = limpiar_monto(mg.group(1))
                resultado["fuente"] = "pie-texto"

        if resultado["exe"] == 0.0:
            me = re.search(PAT_EXENTO, bloque, re.I)
            if me:
                resultado["exe"] = limpiar_monto(me.group(1))

        if resultado["i"] == 0.0:
            mi = re.search(PAT_IVA, bloque, re.I)
            if mi:
                resultado["i"] = limpiar_monto(mi.group(1))

        mt = re.search(PAT_TOTAL, bloque, re.I)
        if mt:
            val = limpiar_monto(mt.group(1))
            if val > resultado["t"]:
                resultado["t"] = val

    return resultado

# ═══════════════════════════════════════════════════════════════
# MOTOR V10 — EXTRACCION DE MONTOS COMPLETA
# ═══════════════════════════════════════════════════════════════

def _extraer_montos_v10(texto_completo, t_clean, tipo, e, ret, file_bytes):
    """
    Motor V10: Manejo COMPLETO de CCF con TODOS los formatos.

    JERARQUIA DE PRIORIDAD (de mayor a menor):
    ─────────────────────────────────────────
    1. ETIQUETAS EXPLICITAS en texto lineal   → maxima confianza
    2. TABLAS DE RESUMEN al pie del CCF       → alta confianza
    3. TEXTO DE PIE (resumen corrido)         → media confianza
    4. ALGEBRA (Total - IVA - Exento = Grav)  → respaldo
    5. FALLBACK CUADRUPLE LOOP                → ultimo recurso

    FORMULA CORRECTA:
        Total = Gravado + IVA(13%) + Exento + Fovial/Cotrans - Retenciones
        Exento NO genera IVA pero SI suma al Total
    """
    g, i, exe, t = 0.0, 0.0, 0.0, 0.0
    iva_calculado = False
    debug = {
        "P1_etiquetas": "pendiente",
        "P2_tablas_ccf": "pendiente",
        "P3_pie_texto":  "pendiente",
        "P4_algebra":    "no aplicado",
        "P5_fallback":   "no aplicado",
        "P6_validacion": "no aplicada",
        "P7_aseguranza": "no aplicada",
        "fuente_final":  "desconocida",
        "montos_raw":    [],
        "resultado":     ""
    }

    # ─────────────────────────────────────────────────────────
    # PASO 1: ETIQUETAS EXPLICITAS EN TEXTO LINEAL
    # Maxima prioridad — si el PDF tiene etiquetas claras,
    # las tomamos directamente sin pasar a tablas.
    # ─────────────────────────────────────────────────────────

    # 1A — Total por etiqueta
    PAT_TOTAL_EXPLICITO = [
        r"(?:TOTAL\s+A\s+PAGAR|MONTO\s+TOTAL\s+DE\s+LA\s+OPERACI[OO]N|"
        r"TOTAL\s+DE\s+LA\s+OPERACI[OO]N|TOTAL\s+OPERACI[OO]N|"
        r"VENTA\s+TOTAL|TOTAL\s+PAGAR|TOTAL\s+\$)"
        r"[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    ]
    for pat in PAT_TOTAL_EXPLICITO:
        m = re.search(pat, t_clean, re.I)
        if m:
            t = limpiar_monto(m.group(1))
            debug["P1_etiquetas"] = f"Total OK => {t}"
            break

    # 1B — IVA por etiqueta
    PAT_IVA_EXPLICITO = [
        r"(?:Impuesto\s+al\s+Valor\s+Agregado|I\.V\.A\.?|IVA)"
        r"(?:\s*\(?13\s*%\)?)?\s*[:\-]?\s*"
        r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:13\s*%\s*(?:de\s*)?IVA|IVA\s*13\s*%)"
        r"[^\d]{0,20}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    ]
    for pat in PAT_IVA_EXPLICITO:
        m = re.search(pat, t_clean, re.I)
        if m:
            i = limpiar_monto(m.group(1))
            debug["P1_etiquetas"] += f" | IVA OK => {i}"
            break

    # 1C — Gravado por etiqueta
    PAT_GRAVADO_EXPLICITO = [
        r"Subtotal\s+Gravado[^\d]{0,10}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:Monto\s+Sujeto\s+a\s+IVA|Venta\s+Gravada|Compras?\s+Gravadas?)"
        r"[^\d]{0,20}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"Sub\s*[Tt]otal[^\d]{0,15}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    ]
    for pat in PAT_GRAVADO_EXPLICITO:
        matches = re.findall(pat, t_clean, re.I)
        if matches:
            g_cand = limpiar_monto(matches[0])
            if g_cand > 0:
                g = g_cand
                debug["P1_etiquetas"] += f" | Gravado OK => {g}"
                break

    # 1D — Exento por etiqueta (PRIORIDAD SOBRE CALCULO)
    PAT_EXENTO_EXPLICITO = [
        r"(?:Ventas?\s+Exentas?|Monto\s+Exento|Total\s+Exento|Compras?\s+Exentas?)"
        r"[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:Exento|No\s+Gravado)[^\d]{0,25}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"Subtotal\s+Exento[^\d]{0,10}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        r"(?:Venta\s+No\s+Sujeta|No\s+Sujeta)[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    ]
    for pat in PAT_EXENTO_EXPLICITO:
        m = re.search(pat, t_clean, re.I)
        if m:
            exe_cand = limpiar_monto(m.group(1))
            if exe_cand > 0:
                exe = exe_cand
                debug["P1_etiquetas"] += f" | Exento OK => {exe}"
                break

    # Evaluar si P1 fue suficiente (todos los campos encontrados)
    p1_completo = (g > 0 and i > 0 and t > 0)
    if not p1_completo:
        debug["P1_etiquetas"] += " | INCOMPLETO — activando P2"
    else:
        debug["P1_etiquetas"] += " | COMPLETO"
        debug["fuente_final"] = "etiquetas-texto"

    # ─────────────────────────────────────────────────────────
    # PASO 2: TABLAS CCF (si P1 fue incompleto)
    # Escanea TODAS las tablas buscando el bloque de resumen
    # al pie (Subtotal Gravado / Exento / IVA / Total)
    # ─────────────────────────────────────────────────────────
    if not p1_completo:
        res_tabla = _extraer_montos_desde_tablas_ccf(file_bytes)

        if res_tabla["fuente"] != "no encontrado":
            if g == 0.0 and res_tabla["g"] > 0:
                g = res_tabla["g"]
            if i == 0.0 and res_tabla["i"] > 0:
                i = res_tabla["i"]
            if exe == 0.0 and res_tabla["exe"] > 0:
                exe = res_tabla["exe"]
            if t == 0.0 and res_tabla["t"] > 0:
                t = res_tabla["t"]

            debug["P2_tablas_ccf"] = (
                f"OK => G={res_tabla['g']} | I={res_tabla['i']} | "
                f"EXE={res_tabla['exe']} | T={res_tabla['t']}"
            )
            debug["fuente_final"] = "tabla-resumen-ccf"
        else:
            debug["P2_tablas_ccf"] = "no encontrado en tablas"

    # Evaluar si P2 completo lo que faltaba
    p2_completo = (g > 0 and i > 0 and t > 0)

    # ─────────────────────────────────────────────────────────
    # PASO 3: PIE DE TEXTO (si P1 y P2 incompletos)
    # Busca el bloque de resumen como texto corrido al final
    # ─────────────────────────────────────────────────────────
    if not p2_completo:
        res_pie = _extraer_montos_pie_texto_ccf(t_clean)

        if res_pie["fuente"] != "no encontrado":
            if g == 0.0 and res_pie["g"] > 0:
                g = res_pie["g"]
            if i == 0.0 and res_pie["i"] > 0:
                i = res_pie["i"]
            if exe == 0.0 and res_pie["exe"] > 0:
                exe = res_pie["exe"]
            if t == 0.0 and res_pie["t"] > 0:
                t = res_pie["t"]

            debug["P3_pie_texto"] = (
                f"OK => G={res_pie['g']} | I={res_pie['i']} | "
                f"EXE={res_pie['exe']} | T={res_pie['t']}"
            )
            debug["fuente_final"] = "pie-texto-ccf"
        else:
            debug["P3_pie_texto"] = "no encontrado en pie de texto"

    # ─────────────────────────────────────────────────────────
    # PASO 4: ALGEBRA
    # Solo si todavia faltan campos tras P1 + P2 + P3
    # FORMULA: Total = G + I + Exento + e - ret
    # ─────────────────────────────────────────────────────────
    if g == 0.0 and t > 0:
        if i > 0:
            # G = T - I - Exento
            g = max(0.0, round(t - i - exe, 2))
            debug["P4_algebra"] = f"G = T - I - EXE: {t} - {i} - {exe} = {g}"
        elif tipo == "03":
            # G = (T - Exento) / 1.13
            g = round((t - exe) / 1.13, 2)
            i = round((t - exe) - g, 2)
            iva_calculado = True
            debug["P4_algebra"] = f"Tipo-03: ({t} - {exe}) / 1.13 = {g}, I={i}"

    # Si tiene G pero no I, calcular IVA
    if g > 0 and i == 0.0:
        i = round(g * 0.13, 2)
        iva_calculado = True
        debug["P4_algebra"] = f"I = G x 0.13: {g} x 0.13 = {i}"

    # Si tiene G e I pero no T, calcular Total
    if g > 0 and i > 0 and t == 0.0:
        t = round(g + i + exe + e - ret, 2)
        debug["P4_algebra"] = (
            debug.get("P4_algebra", "") +
            f" | T inferido = {g} + {i} + {exe} + {e} - {ret} = {t}"
        )

    # ─────────────────────────────────────────────────────────
    # PASO 5: FALLBACK CUADRUPLE LOOP — ULTIMO RECURSO
    # Solo si tras todos los pasos anteriores no tenemos T
    # ─────────────────────────────────────────────────────────
    if t == 0.0:
        montos_raw = re.findall(
            r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            t_clean
        )
        valores = sorted(
            list(set(limpiar_monto(x) for x in montos_raw)),
            reverse=True
        )
        valores = [v for v in valores if v > 0.01]
        debug["montos_raw"] = valores[:12]
        debug["P5_fallback"] = f"Iniciado con {len(valores)} valores"

        encontrado = False
        for val_t in valores:
            if encontrado:
                break
            for val_g in valores:
                if val_g >= val_t:
                    continue
                for val_i in valores:
                    if val_i >= val_g:
                        continue
                    for val_exe in valores:
                        if val_exe >= val_g:
                            continue
                        if abs(round(val_g * 0.13, 2) - round(val_i, 2)) <= 0.05:
                            total_calc = round(val_g + val_i + val_exe + e - ret, 2)
                            if abs(total_calc - round(val_t, 2)) <= 0.10:
                                g, i, exe, t = val_g, val_i, val_exe, val_t
                                encontrado = True
                                debug["P5_fallback"] = (
                                    f"OK => G={g}, I={i}, EXE={exe}, T={t}"
                                )
                                debug["fuente_final"] = "fallback-loop"
                                break

        if not encontrado:
            debug["P5_fallback"] = "Sin combinacion valida — revision manual requerida"

    # ─────────────────────────────────────────────────────────
    # PASO 6: VALIDACION TRIBUTARIA
    # IVA debe ser G x 13%. Si hay discrepancia > $1, corregir.
    # ─────────────────────────────────────────────────────────
    if g > 0 and i > 0:
        iva_esperado = round(g * 0.13, 2)
        diferencia   = abs(iva_esperado - i)

        if diferencia > 1.00:
            i_viejo = i
            i = iva_esperado
            debug["P6_validacion"] = (
                f"IVA corregido: {i_viejo} -> {i} "
                f"(G={g} x 0.13 = {iva_esperado})"
            )
        else:
            debug["P6_validacion"] = (
                f"OK: IVA {i} ~ {iva_esperado} (dif={diferencia:.2f})"
            )

    # ─────────────────────────────────────────────────────────
    # PASO 7: ASEGURANZA ALGEBRAICA FINAL
    # Total DEBE ser G + I + Exento (aproximadamente).
    # Si Gravado > Total o la suma no cierra, recalcular G.
    # ─────────────────────────────────────────────────────────
    if g > 0 and i > 0 and t > 0:
        total_alg = round(g + i + exe, 2)

        if g > t:
            g_viejo = g
            g = max(0.0, round(t - i - exe, 2))
            debug["P7_aseguranza"] = (
                f"CORRECCION: G {g_viejo} > T {t}. "
                f"G = {t} - {i} - {exe} = {g}"
            )
        elif abs(total_alg - t) > 0.50:
            g_viejo = g
            g = max(0.0, round(t - i - exe, 2))
            debug["P7_aseguranza"] = (
                f"CORRECCION: {g_viejo}+{i}+{exe}={total_alg} != {t}. "
                f"G recalculado = {g}"
            )
        else:
            debug["P7_aseguranza"] = (
                f"OK: {g}+{i}+{exe}={total_alg} ~ {t}"
            )

    g   = max(0.0, g)
    i   = max(0.0, i)
    exe = max(0.0, exe)

    debug["resultado"] = (
        f"FINAL => G={g:.2f} | I={i:.2f} | EXE={exe:.2f} | T={t:.2f} | "
        f"FUENTE={debug['fuente_final']} | IVA_CALC={iva_calculado}"
    )

    return g, i, exe, t, iva_calculado, debug

# ═══════════════════════════════════════════════════════════════
# HELPER: RENDERIZAR DEBUG
# ═══════════════════════════════════════════════════════════════

def _render_debug_montos(debug: dict):
    if not debug:
        st.info("Sin datos de debug disponibles.")
        return

    filas = [
        ("P1 Etiquetas Explicitas", debug.get("P1_etiquetas",   "—")),
        ("P2 Tablas CCF",           debug.get("P2_tablas_ccf",  "—")),
        ("P3 Pie de Texto",         debug.get("P3_pie_texto",   "—")),
        ("P4 Algebra",              debug.get("P4_algebra",     "—")),
        ("P5 Fallback Loop",        debug.get("P5_fallback",    "—")),
        ("P6 Validacion IVA",       debug.get("P6_validacion",  "—")),
        ("P7 Aseguranza Final",     debug.get("P7_aseguranza",  "—")),
        ("Fuente Final",            debug.get("fuente_final",   "—")),
    ]

    html = '<div class="debug-box">'
    for label, valor in filas:
        valor_str = str(valor)
        if valor_str.startswith("OK") or valor_str.startswith("COMPLETO"):
            cls = "debug-ok"
        elif any(w in valor_str.upper() for w in ["CORRECCION", "INCONSISTENTE", "WARN"]):
            cls = "debug-warn"
        elif any(w in valor_str.lower() for w in ["no encontrado", "no aplicado", "incompleto", "pendiente"]):
            cls = "debug-err"
        else:
            cls = ""
        html += (
            f'<div><strong style="color:#cdd9e5">{label}:</strong> '
            f'<span class="{cls}">{valor_str}</span></div>'
        )

    montos = debug.get("montos_raw", [])
    if montos:
        ms = ", ".join([f"${m:.2f}" for m in montos[:6]])
        html += (
            f'<div style="margin-top:6px"><strong style="color:#cdd9e5">'
            f'Montos detectados:</strong> <span style="color:#79c0ff">{ms}</span></div>'
        )

    resultado = debug.get("resultado", "")
    if resultado:
        html += (
            f'<div style="margin-top:8px;border-top:1px solid #30363d;'
            f'padding-top:6px"><strong style="color:#e3b341">{resultado}</strong></div>'
        )

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# MODAL DE DESCARGA
# ═══════════════════════════════════════════════════════════════

@st.dialog("Seguro de Calidad de Compras")
def ventana_descarga_compras(df_resultados, nombre_archivo):
    st.write(
        "Asegurate de haber procesado unicamente los comprobantes "
        "que deseas declarar en el anexo de Compras antes de descargar."
    )
    st.download_button(
        label="Confirmar y Descargar Anexo F-07",
        data=to_excel_hacienda_compras(df_resultados),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True
    )

# ═══════════════════════════════════════════════════════════════
# MOTOR PRINCIPAL — V10
# ═══════════════════════════════════════════════════════════════

def extraer_compras_nativo_pro_v10(file_bytes, cliente_activo, proveedores_cache=None):
    """
    Motor V10 — Soporta TODOS los formatos de CCF:
      - CCF con etiquetas explicitas
      - CCF con resumen en tabla al pie
      - CCF con resumen como texto corrido
      - CCF escaneados (OCR)
    """
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
                    texto_lineal  += ocr_txt + "\n"
            texto_completo = texto_lineal

        if len(texto_completo.strip()) < 50:
            return {"error": "El PDF no tiene texto legible ni imagen procesable."}

        t_clean     = re.sub(r'\s+', ' ', texto_completo)
        t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        # Detectar tipo DTE
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

        # Codigo de generacion UUID
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

        # Separar texto del emisor del receptor
        partes_emisor = re.split(
            r"(?i)\b(?:RECEPTOR|CLIENTE:|CLIENTE\s|SOCIO/EMPRESA)\b",
            texto_lineal
        )
        texto_emisor = partes_emisor[0] if partes_emisor else texto_lineal
        if len(texto_emisor.strip()) < 100:
            texto_emisor = texto_lineal[:1500]

        prov_db = proveedores_cache if proveedores_cache is not None else cargar_proveedores_json()

        # NIT del proveedor
        nit_prov, confianza_nit = _extraer_nit_completo_pdf(
            texto_lineal, texto_visual, file_bytes
        )
        if not nit_prov:
            nit_prov, confianza_nit = _buscar_nit_en_todas_lineas(texto_emisor)

        if nit_prov in (nit_receptor, dui_receptor):
            nit_prov      = ""
            confianza_nit = "baja"

        # Razon social del proveedor
        nom_prov, confianza_rs = _extraer_razon_social_v6(
            nit_prov, texto_emisor, prov_db, cliente_activo.get('nombre', ''), file_bytes
        )

        es_nuevo = True
        if nit_prov:
            _, _en_cache = _buscar_en_cache_flexible(nit_prov, prov_db)
            if _en_cache:
                es_nuevo = False

        dui_prov = ""
        if len(nit_prov) == 9:
            dui_prov = nit_prov

        # Fovial / Cotrans / Retenciones
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

        m_ret = re.search(
            r"(?:Retenido|Retenci[oo]n)[^0-9]*"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})",
            t_clean, re.I
        )
        if m_ret:
            ret = limpiar_monto(m_ret.group(1))

        # ── MOTOR V10 ──────────────────────────────────────────
        g, i, exe, t, iva_calculado, debug_montos = _extraer_montos_v10(
            texto_completo, t_clean, tipo, e, ret, file_bytes
        )

        return {
            "fecha":         fecha,
            "nit_prov":      nit_prov,
            "dui_prov":      dui_prov,
            "nom_prov":      nom_prov,
            "tipo":          tipo,
            "ctrl":          ctrl,
            "gen":           gen,
            "exe":           round(exe, 2),
            "gra":           round(g,   2),
            "iva":           round(i,   2),
            "ret":           round(ret, 2),
            "perc":          perc,
            "tot":           round(t,   2),
            "estado":        "OK",
            "iva_calc":      iva_calculado,
            "es_nuevo":      es_nuevo,
            "nit_nuevo":     nit_prov,
            "motor":         motor,
            "confianza_nit": confianza_nit,
            "confianza_rs":  confianza_rs,
            "_debug":        debug_montos,
        }

    except Exception as err:
        return {"error": str(err)}

# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:Courier New,monospace; color:#003057; "
    "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("Extractor DTE - Compras")
st.markdown(f"""
<div class="alerta-activo">
    <strong>RECEPTOR ACTUAL (Cliente Activo):</strong>
    {cliente.get('nombre', 'N/A')} (NIT/DUI: {cliente.get('nit', 'N/A')})
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# INICIALIZACION DE ESTADO
# ═══════════════════════════════════════════════════════════════

if 'cola_revision'     not in st.session_state: st.session_state.cola_revision     = []
if 'comp_uploader_key' not in st.session_state: st.session_state.comp_uploader_key = str(time.time())
if 'db_compras'        not in st.session_state: st.session_state.db_compras        = pd.DataFrame()
if 'archivos_comp'     not in st.session_state: st.session_state.archivos_comp     = set()
if 'reporte_compras'   not in st.session_state: st.session_state.reporte_compras   = None

# ═══════════════════════════════════════════════════════════════
# SIDEBAR — CARGA Y PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("Carga de Compras")
    st.caption(f"Receptor: {cliente.get('nombre', 'N/A')}")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra facturas de proveedores (PDF)",
        type="pdf",
        accept_multiple_files=True,
        key=st.session_state.comp_uploader_key
    )

    if archivos and st.button("Procesar Compras", type="primary", use_container_width=True):

        extracted           = []
        duplicados          = []
        iva_calculado_files = []
        intrusos            = []
        invalidos           = []
        corruptos           = []
        nuevos_proveedores  = {}

        nuevos = [f for f in archivos if f.name not in st.session_state.archivos_comp]

        if nuevos:
            bar          = st.progress(0)
            txt_progreso = st.empty()
            t_inicio     = time.time()
            total        = len(nuevos)
            prov_cache   = cargar_proveedores_json()

            for idx, f in enumerate(nuevos):

                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                if idx > 0:
                    elapsed = time.time() - t_inicio
                    eta     = int((elapsed / idx) * (total - idx))
                    m_t2, s = divmod(eta, 60)
                    txt_progreso.markdown(
                        f"Procesando: **{idx+1}** de **{total}** "
                        f"| Restante: {m_t2:02d}:{s:02d}"
                    )
                else:
                    txt_progreso.markdown(f"Procesando: **1** de **{total}** | Extrayendo...")

                file_bytes = f.read()

                if len(file_bytes) < 1024:
                    corruptos.append(f.name)
                    st.session_state.archivos_comp.add(f.name)
                    bar.progress((idx + 1) / total)
                    continue

                res = extraer_compras_nativo_pro_v10(file_bytes, cliente, prov_cache)

                codigo_gen  = res.get('gen', '')
                dup_memoria = (
                    not st.session_state.db_compras.empty
                    and codigo_gen != ""
                    and (st.session_state.db_compras['gen'] == codigo_gen).any()
                )
                dup_lote = (
                    codigo_gen != ""
                    and any(d.get('gen') == codigo_gen for d in extracted)
                )

                st.session_state.archivos_comp.add(f.name)

                if "error_intruso" in res:
                    intrusos.append(f.name)
                elif "error_tipo" in res:
                    invalidos.append(f.name)
                elif dup_memoria or dup_lote:
                    duplicados.append(f.name)
                elif "error" not in res:
                    fecha_str          = str(res.get('fecha', '')).strip()
                    nom_prov_str       = str(res.get('nom_prov', '')).strip()
                    nit_prov_str       = str(res.get('nit_prov', '')).strip()
                    nom_es_placeholder = nom_prov_str in (NOMBRE_PLACEHOLDER, "ESCRIBE EL NOMBRE AQUI", "")

                    try:
                        tot_float = float(res.get('tot', 0.0))
                    except (TypeError, ValueError):
                        tot_float = 0.0

                    necesita_revision = (
                        not nit_prov_str
                        or tot_float == 0.0
                        or not res.get('gen')
                        or not fecha_str
                        or nom_es_placeholder
                    )

                    if necesita_revision:
                        st.session_state.cola_revision.append({
                            "archivo": f.name,
                            "bytes":   file_bytes,
                            "datos":   res
                        })
                    else:
                        if res.get('iva_calc'):
                            iva_calculado_files.append(f.name)
                        if res.get("es_nuevo") and res.get("nit_nuevo"):
                            nuevos_proveedores[res["nit_nuevo"]] = res["nom_prov"]
                            prov_cache[res["nit_nuevo"]] = {"nombre": res["nom_prov"], "nrc": ""}
                        res["archivo"] = f.name
                        extracted.append(res)
                else:
                    corruptos.append(f.name)

                bar.progress((idx + 1) / total)

            txt_progreso.success(f"{total} facturas escaneadas correctamente.")

            if nuevos_proveedores:
                guardar_lote_proveedores(nuevos_proveedores)

            st.session_state.reporte_compras = {
                "intrusos":           intrusos,
                "invalidos":          invalidos,
                "duplicados":         duplicados,
                "iva_calc":           iva_calculado_files,
                "nuevos_proveedores": nuevos_proveedores,
                "corruptos":          corruptos
            }

            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_compras.empty:
                    st.session_state.db_compras = new_df
                else:
                    st.session_state.db_compras = pd.concat(
                        [st.session_state.db_compras, new_df], ignore_index=True
                    )

            gc.collect()
            time.sleep(0.3)
            st.rerun()

    st.divider()

    if st.button("Limpiar Memoria Compras", type="secondary", use_container_width=True):
        for key in ['db_compras', 'archivos_comp', 'reporte_compras', 'cola_revision']:
            st.session_state.pop(key, None)
        st.session_state.comp_uploader_key = str(time.time())
        gc.collect()
        st.rerun()

    if not st.session_state.db_compras.empty:
        st.divider()
        st.caption(f"Registros: {len(st.session_state.db_compras)}")
        en_cola = len(st.session_state.cola_revision)
        if en_cola > 0:
            st.warning(f"{en_cola} en bandeja de revision")

# ═══════════════════════════════════════════════════════════════
# BANDEJA DE REVISION MANUAL
# ═══════════════════════════════════════════════════════════════

if st.session_state.cola_revision:

    total_cola  = len(st.session_state.cola_revision)
    item_actual = st.session_state.cola_revision[0]
    datos       = item_actual["datos"]

    st.markdown("""
    <div class="inbox-revision">
        <h3 style="margin-top:0; color:#ffaa00;">Bandeja de Revision Manual</h3>
        <p style="color:#aaa; margin-bottom:0;">
            Se encontraron datos borrosos o incompletos.
            Revisa la imagen y completa los campos requeridos.
        </p>
    </div>
    """, unsafe_allow_html=True)

    conf_nit = datos.get("confianza_nit", "baja")
    conf_rs  = datos.get("confianza_rs",  "baja")

    st.markdown(f"""
    <div class="confianza-row">
        <div class="confianza-item">
            <strong>NIT:</strong>&nbsp;{mostrar_indicador_confianza(conf_nit)}
            &nbsp;<span style="color:#888;font-size:12px;">{datos.get('nit_prov','—')}</span>
        </div>
        <div class="confianza-item">
            <strong>Razon Social:</strong>&nbsp;{mostrar_indicador_confianza(conf_rs)}
            &nbsp;<span style="color:#888;font-size:12px;">{datos.get('nom_prov','—')[:40]}</span>
        </div>
        <div class="confianza-item">
            <span class="badge-revision">REVISION REQUERIDA</span>
            &nbsp;<span style="color:#888;font-size:12px;">Doc 1 de {total_cola}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_img, col_form = st.columns([1.2, 1], gap="large")

    with col_img:
        try:
            with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                img = pdf.pages[0].to_image(resolution=250).original
                st.image(img, caption=item_actual['archivo'], use_container_width=True)
                texto_crudo = ""
                for page in pdf.pages:
                    texto_crudo += (page.extract_text(layout=True) or page.extract_text() or "") + "\n"
                st.markdown("**Texto extraido del PDF:**")
                st.text_area(
                    "Texto", value=texto_crudo.strip(),
                    height=180, label_visibility="collapsed"
                )
        except Exception:
            st.error("No se pudo cargar la vista previa del PDF.")

    with col_form:
        st.markdown("### Correccion Rapida")

        nom_sugerido = datos.get("nom_prov", "")
        if nom_sugerido in [NOMBRE_PLACEHOLDER, "ESCRIBE EL NOMBRE AQUI"]:
            nom_sugerido = ""

        nit_actual         = datos.get("nit_prov", "")
        es_nuevo_proveedor = datos.get("es_nuevo", True)

        if nit_actual and es_nuevo_proveedor:
            st.info(f"Proveedor Nuevo: NIT {nit_actual} no esta en el directorio.")
        elif nit_actual:
            st.success(f"Proveedor Existente: NIT {nit_actual}")

        # ── METRICS V10: 4 campos ──────────────────────────────
        st.markdown("**Montos detectados por el motor:**")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.markdown(f'<div class="metric-box"><strong>Gravado</strong><br/>${datos.get("gra", 0):.2f}</div>', unsafe_allow_html=True)
        with col_m2:
            st.markdown(f'<div class="metric-box"><strong>Exento</strong><br/>${datos.get("exe", 0):.2f}</div>', unsafe_allow_html=True)
        with col_m3:
            st.markdown(f'<div class="metric-box"><strong>IVA</strong><br/>${datos.get("iva", 0):.2f}</div>', unsafe_allow_html=True)
        with col_m4:
            st.markdown(f'<div class="metric-box"><strong>Total</strong><br/>${datos.get("tot", 0):.2f}</div>', unsafe_allow_html=True)

        # Validacion inmediata
        try:
            gra_v = float(datos.get('gra', 0))
            exe_v = float(datos.get('exe', 0))
            iva_v = float(datos.get('iva', 0))
            tot_v = float(datos.get('tot', 0))
            suma  = round(gra_v + exe_v + iva_v, 2)
            if abs(suma - tot_v) > 0.50:
                st.error(
                    f"INCONSISTENCIA: ${gra_v:.2f} + ${exe_v:.2f} + ${iva_v:.2f} = "
                    f"${suma:.2f} != Total ${tot_v:.2f}"
                )
            elif gra_v > 0 and iva_v > 0 and
