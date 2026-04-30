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
    .confianza-alta {
        background-color: #1b5e20;
        color: #81c784;
        border: 1px solid #2e7d32;
    }
    .confianza-media {
        background-color: #e65100;
        color: #ffb74d;
        border: 1px solid #bf360c;
    }
    .confianza-baja {
        background-color: #7f1010;
        color: #ef9a9a;
        border: 1px solid #b71c1c;
    }
    .confianza-cache {
        background-color: #1a237e;
        color: #90caf9;
        border: 1px solid #283593;
    }
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
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

NOMBRE_PLACEHOLDER = "ESCRIBE EL NOMBRE AQUI"
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

BASURA_ESTRICTA = frozenset(["@", "EMAIL", "CORREO", ".COM", "WWW."])

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
        workbook = writer.book
        worksheet = writer.sheets['Compras_F07']

        fmt_texto  = workbook.add_format({'num_format': '@'})
        fmt_num_izq = workbook.add_format({'num_format': '0.00', 'align': 'left'})

        def get_max_len(col_idx):
            try:
                return max(
                    df.iloc[:, col_idx].astype(str).map(len).max() if not df.empty else 15,
                    15
                ) + 2
            except Exception:
                return 17

        worksheet.set_column(0,  0,  10,  fmt_texto)
        worksheet.set_column(1,  1,  1,   fmt_texto)
        worksheet.set_column(2,  2,  2,   fmt_texto)
        worksheet.set_column(3,  3,  get_max_len(3), fmt_texto)
        worksheet.set_column(4,  4,  14,  fmt_texto)
        worksheet.set_column(5,  5,  get_max_len(5), fmt_texto)
        worksheet.set_column(6,  14, 10.71, fmt_num_izq)
        worksheet.set_column(15, 15, 9,  fmt_texto)
        worksheet.set_column(16, 20, 1,  fmt_texto)

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
    """Retorna HTML del badge de confianza para NIT / Razon Social."""
    c = str(confianza).lower().strip()
    if c == "alta":
        return '<span class="indicador-confianza confianza-alta">ALTA</span>'
    elif c == "media":
        return '<span class="indicador-confianza confianza-media">MEDIA</span>'
    elif c == "cache":
        return '<span class="indicador-confianza confianza-cache">CACHE</span>'
    else:
        return '<span class="indicador-confianza confianza-baja">BAJA</span>'

# ═══════════════════════════════════════════════════════════════
# EXTRACCION DE NIT  (CORREGIDA — no hace return prematuro)
# ═══════════════════════════════════════════════════════════════

def _extraer_solo_nit(texto_emisor):
    """
    Extrae SOLO el NIT del bloque del emisor.
    Devuelve (nit_str, confianza).  nit_str es solo digitos.
    NO hace return prematuro para que el llamador continue con RS.
    """
    t = re.sub(r'\s+', ' ', texto_emisor).upper()

    # Patron 1 — NIT con guiones XXXX-XXXXXX-XXX-X
    m = re.search(
        r'NIT\s*[#:]?\s*(\d{4})\s*-\s*(\d{6})\s*-\s*(\d{3})\s*-\s*(\d)',
        t
    )
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}", "alta"

    # Patron 2 — NIT con guiones sin espacios entre grupos
    m = re.search(
        r'NIT\s*[#:]?\s*(\d{4}-\d{6}-\d{3}-\d)',
        t
    )
    if m:
        return re.sub(r'[^0-9]', '', m.group(1)), "alta"

    # Patron 3 — NIT 14 digitos pegados tras etiqueta
    m = re.search(r'NIT\s*[#:.]?\s*(\d{14})', t)
    if m:
        return m.group(1), "alta"

    # Patron 4 — Cualquier 14 digitos que empiece con 0
    #            (evita capturar totales grandes)
    m = re.search(r'\b(0\d{13})\b', t)
    if m:
        return m.group(1), "media"

    # Patron 5 — DUI 8+1
    m = re.search(r'DUI\s*[#:]?\s*(\d{8})\s*-?\s*(\d)', t)
    if m:
        return f"{m.group(1)}{m.group(2)}", "media"

    return "", "baja"


def _extraer_solo_razon_social(texto_emisor, cliente_nombre):
    """
    Extrae SOLO la Razon Social del bloque del emisor.
    Devuelve (nombre_str, confianza).
    Usa patrones ESTRICTOS para no capturar basura.
    """
    # Lista ordenada de mayor a menor confianza
    patrones = [
        # Etiqueta explícita "Nombre o razon social" / "Razon Social"
        (
            r"(?:RAZ[OÓ]N\s*SOCIAL|NOMBRE\s+O\s+RAZ[OÓ]N\s*SOCIAL)\s*[:\-]?\s*"
            r"([A-Z][A-Za-z0-9\s\.\,\&\-]{4,60}?)(?=\s{2,}|\n|NIT|NRC|GIRO|ACTIVIDAD|$)",
            "alta"
        ),
        # Etiqueta "Nombre:" sola
        (
            r"(?<!\w)NOMBRE\s*[:\-]\s*"
            r"([A-Z][A-Za-z0-9\s\.\,\&\-]{4,60}?)(?=\s{2,}|\n|NIT|NRC|GIRO|ACTIVIDAD|$)",
            "alta"
        ),
        # Nombre Comercial
        (
            r"NOMBRE\s+COMERCIAL\s*[:\-]?\s*"
            r"([A-Z][A-Za-z0-9\s\.\,\&\-]{4,60}?)(?=\s{2,}|\n|NIT|NRC|GIRO|$)",
            "media"
        ),
        # Linea que contiene indicador de persona juridica (SA, SRL, etc.)
        # pero que no sea una linea de basura numerica
        (
            r"(?:^|\n)\s*"
            r"([A-Z][A-Za-z\s]{3,50}"
            r"(?:S\.A\.|S\.A|C\.V\.|SOCIEDAD|S\.R\.L\.|LIMITADA|LTDA)"
            r"[A-Za-z\s\.]*)"
            r"(?=\s*\n|\s{3,}|$)",
            "media"
        ),
    ]

    for patron, confianza in patrones:
        m = re.search(patron, texto_emisor, re.IGNORECASE | re.MULTILINE)
        if not m:
            continue

        candidato = m.group(1).strip()
        candidato = re.sub(r'\s+', ' ', candidato).rstrip('.,;:')

        # Rechazar si es muy corto o muy largo
        if len(candidato) < 5 or len(candidato) > 65:
            continue
        # Rechazar si tiene caracteres de correo / URL
        if any(bad in candidato.upper() for bad in BASURA_ESTRICTA):
            continue
        # Rechazar si contiene palabras de cabecera del DTE
        if any(b in candidato.upper() for b in PALABRAS_BASURA):
            continue
        # Rechazar si es el nombre del receptor
        palabras_cli = cliente_nombre.upper().split()[:2]
        if any(p in candidato.upper() for p in palabras_cli if len(p) > 3):
            continue
        # Rechazar si tiene demasiados digitos consecutivos (probable NIT/fecha)
        if re.search(r'\d{5,}', candidato):
            continue
        # Rechazar si la proporcion de digitos es mayor al 30 %
        if len(candidato) > 0 and sum(c.isdigit() for c in candidato) / len(candidato) > 0.30:
            continue

        return candidato.upper(), confianza

    return "", "baja"


def _extraer_nit_de_tablas(file_bytes):
    """
    Fallback: busca un NIT de 14 digitos dentro de las tablas del PDF.
    """
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:2]:
                for table in (page.extract_tables() or []):
                    for row in table:
                        for cell in (row or []):
                            if not cell:
                                continue
                            cell_str = str(cell)
                            # 14 digitos seguidos
                            m = re.search(r'\b(\d{14})\b', cell_str)
                            if m:
                                return m.group(1)
                            # Formato XXXX-XXXXXX-XXX-X
                            m2 = re.search(
                                r'(\d{4})-(\d{6})-(\d{3})-(\d)', cell_str
                            )
                            if m2:
                                return f"{m2.group(1)}{m2.group(2)}{m2.group(3)}{m2.group(4)}"
    except Exception:
        pass
    return ""

# ═══════════════════════════════════════════════════════════════
# MOTOR DE EXTRACCION DTE COMPRAS  (VERSION 3 — estable)
# ═══════════════════════════════════════════════════════════════

def extraer_compras_nativo_pro_v3(file_bytes, cliente_activo, proveedores_cache=None):
    """
    Motor de extraccion DTE Compras El Salvador.
    Combina el flujo robusto original con extraccion mejorada de NIT/RS
    y SIN los bugs de retorno prematuro ni patrones demasiado permisivos.
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

        # ── Tipo y numero de control DTE ──────────────────────────────
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

        # ── UUID / Codigo de generacion ───────────────────────────────
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

        # ── Fecha ─────────────────────────────────────────────────────
        fecha = extraer_y_formatear_fecha(t_clean)

        # ── Bloque del EMISOR (todo lo que precede a "RECEPTOR") ──────
        partes_emisor = re.split(
            r"(?i)\b(?:RECEPTOR|CLIENTE:|CLIENTE\s|SOCIO/EMPRESA)\b",
            texto_lineal
        )
        texto_emisor = partes_emisor[0] if partes_emisor else texto_lineal
        if len(texto_emisor.strip()) < 100:
            texto_emisor = texto_lineal[:1500]

        # ── Carga cache de proveedores ────────────────────────────────
        prov_db = proveedores_cache if proveedores_cache is not None else cargar_proveedores_json()

        # ────────────────────────────────────────────────────────────
        # EXTRACCION DE NIT  — 3 pasos en cascada
        # ────────────────────────────────────────────────────────────
        nit_prov      = ""
        dui_prov      = ""
        nom_prov      = NOMBRE_PLACEHOLDER
        es_nuevo      = True
        confianza_nit = "baja"
        confianza_rs  = "baja"

        # PASO A: patrones mejorados sobre bloque emisor
        nit_prov, confianza_nit = _extraer_solo_nit(texto_emisor)

        # Descartar si es el receptor
        if nit_prov in (nit_receptor, dui_receptor):
            nit_prov      = ""
            confianza_nit = "baja"

        # PASO B: si no se encontro, usar método original (regex amplio + cache)
        if not nit_prov:
            patron_ids = (
                r"\b\d{4}\s*[-]?\s*\d{6}\s*[-]?\s*\d{3}\s*[-]?\s*\d{1}\b"
                r"|\b\d{14}\b"
                r"|\b\d{8}\s*[-]?\s*\d{1}\b"
                r"|\b\d{9}\b"
            )
            nits_raw     = re.findall(patron_ids, texto_emisor)
            nits_limpios = list(dict.fromkeys([re.sub(r'[^0-9]', '', n) for n in nits_raw]))
            candidatos   = [
                n for n in nits_limpios
                if n not in (nit_receptor, dui_receptor) and len(n) >= 9
            ]

            # Preferir el que ya este en cache
            for n in candidatos:
                if n in prov_db:
                    nit_prov      = n
                    nom_prov      = prov_db[n].get("nombre", NOMBRE_PLACEHOLDER)
                    es_nuevo      = False
                    confianza_nit = "cache"
                    confianza_rs  = "cache"
                    break

            if not nit_prov and candidatos:
                nit_prov      = candidatos[0]
                confianza_nit = "baja"

        # PASO C: fallback en tablas del PDF
        if not nit_prov:
            nit_prov = _extraer_nit_de_tablas(file_bytes)
            if nit_prov:
                confianza_nit = "media"

        # Verificar cache para el NIT recien encontrado
        if nit_prov and es_nuevo and nit_prov in prov_db:
            nom_prov      = prov_db[nit_prov].get("nombre", NOMBRE_PLACEHOLDER)
            es_nuevo      = False
            confianza_nit = "cache"
            confianza_rs  = "cache"

        # DUI si son 9 digitos
        if len(nit_prov) == 9:
            dui_prov = nit_prov

        # ────────────────────────────────────────────────────────────
        # EXTRACCION DE RAZON SOCIAL (solo si es proveedor nuevo)
        # ────────────────────────────────────────────────────────────
        if es_nuevo and nom_prov == NOMBRE_PLACEHOLDER:

            # Paso 1: patrones estrictos
            rs_candidato, confianza_rs = _extraer_solo_razon_social(
                texto_emisor, cliente_activo.get('nombre', '')
            )

            if rs_candidato:
                nom_prov = normalizar_nombre_proveedor(
                    rs_candidato, cliente_activo.get('nombre', '')
                )

            # Paso 2: metodo original — buscar linea con marca comercial
            if nom_prov == NOMBRE_PLACEHOLDER:
                nombre_encontrado = ""
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
                        palabras_cli = cliente_activo.get('nombre', '').upper().split()[:2]
                        if clean and not any(p in clean for p in palabras_cli if len(p) > 3):
                            nombre_encontrado = clean
                            break

                if nombre_encontrado:
                    nom_prov     = normalizar_nombre_proveedor(
                        nombre_encontrado, cliente_activo.get('nombre', '')
                    )
                    confianza_rs = "media"

        # ────────────────────────────────────────────────────────────
        # EXTRACCION DE MONTOS
        # ────────────────────────────────────────────────────────────
        e, g, i, ret, perc, t = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        iva_calculado = False

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
            ret = limpiar_monto(m_ret.group(1))

        # Algoritmo matematico principal
        montos_raw = re.findall(
            r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})",
            t_clean
        )
        valores = sorted(
            list(set(limpiar_monto(m) for m in montos_raw)),
            reverse=True
        )
        valores = [v for v in valores if v > 0.01]

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
                    if abs(round(val_g * 0.13, 2) - round(val_i, 2)) <= 0.05:
                        total_calculado = round(val_g + val_i + e - ret, 2)
                        if abs(total_calculado - round(val_t, 2)) <= 0.10:
                            g, i, t = val_g, val_i, val_t
                            encontrado = True
                            break

        if not encontrado:
            m_t = re.search(
                r"(?:TOTAL\s+A\s+PAGAR|TOTAL\s+PAGAR|MONTO\s+TOTAL|"
                r"TOTAL\s+OPERACI.N|VENTA\s+TOTAL|TOTAL\s+\$)"
                r"[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})",
                t_clean, re.I
            )
            if m_t:
                t = limpiar_monto(m_t.group(1))

            m_i = re.search(
                r"(?:Impuesto.*Agregado|IVA|13%\s+IVA|I\.V\.A)"
                r"[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})",
                t_clean, re.I
            )
            if m_i:
                i = limpiar_monto(m_i.group(1))

            if t > 0 and i == 0.0 and tipo == "03":
                g = round((t + ret - e) / 1.13, 2)
                i = round(t + ret - e - g, 2)
                iva_calculado = True
            elif t > 0 and i > 0:
                g = round(t - i - e + ret, 2)
                if g < 0:
                    g = 0.0

        return {
            "fecha":         fecha,
            "nit_prov":      nit_prov,
            "dui_prov":      dui_prov,
            "nom_prov":      nom_prov,
            "tipo":          tipo,
            "ctrl":          ctrl,
            "gen":           gen,
            "exe":           round(e,   2),
            "gra":           max(0.0, g),
            "iva":           max(0.0, i),
            "ret":           ret,
            "perc":          perc,
            "tot":           t,
            "estado":        "OK",
            "iva_calc":      iva_calculado,
            "es_nuevo":      es_nuevo,
            "nit_nuevo":     nit_prov,
            "motor":         motor,
            "confianza_nit": confianza_nit,
            "confianza_rs":  confianza_rs,
        }

    except Exception as err:
        return {"error": str(err)}

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

if 'cola_revision'      not in st.session_state: st.session_state.cola_revision      = []
if 'comp_uploader_key'  not in st.session_state: st.session_state.comp_uploader_key  = str(time.time())
if 'db_compras'         not in st.session_state: st.session_state.db_compras         = pd.DataFrame()
if 'archivos_comp'      not in st.session_state: st.session_state.archivos_comp      = set()
if 'reporte_compras'    not in st.session_state: st.session_state.reporte_compras    = None

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

        extracted          = []
        duplicados         = []
        iva_calculado_files = []
        intrusos           = []
        invalidos          = []
        corruptos          = []
        nuevos_proveedores = {}

        nuevos = [f for f in archivos if f.name not in st.session_state.archivos_comp]

        if nuevos:
            bar           = st.progress(0)
            txt_progreso  = st.empty()
            t_inicio      = time.time()
            total         = len(nuevos)
            prov_cache    = cargar_proveedores_json()

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

                res = extraer_compras_nativo_pro_v3(file_bytes, cliente, prov_cache)

                codigo_gen = res.get('gen', '')
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
                    fecha_str    = str(res.get('fecha', '')).strip()
                    nom_prov_str = str(res.get('nom_prov', '')).strip()

                    nom_es_placeholder = (
                        nom_prov_str in (NOMBRE_PLACEHOLDER, "ESCRIBE EL NOMBRE AQUI", "")
                    )

                    try:
                        tot_float = float(res.get('tot', 0.0))
                    except (TypeError, ValueError):
                        tot_float = 0.0

                    necesita_revision = (
                        tot_float == 0.0
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
                "intrusos":          intrusos,
                "invalidos":         invalidos,
                "duplicados":        duplicados,
                "iva_calc":          iva_calculado_files,
                "nuevos_proveedores": nuevos_proveedores,
                "corruptos":         corruptos
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
# BANDEJA DE REVISION MANUAL — CON INDICADORES DE CONFIANZA
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

    # ── Indicadores de confianza ──────────────────────────────────────
    conf_nit = datos.get("confianza_nit", "baja")
    conf_rs  = datos.get("confianza_rs",  "baja")

    st.markdown(f"""
    <div class="confianza-row">
        <div class="confianza-item">
            <strong>NIT Extraido:</strong>&nbsp;{mostrar_indicador_confianza(conf_nit)}
            &nbsp;<span style="color:#888;font-size:12px;">{datos.get('nit_prov','—')}</span>
        </div>
        <div class="confianza-item">
            <strong>Razon Social:</strong>&nbsp;{mostrar_indicador_confianza(conf_rs)}
            &nbsp;<span style="color:#888;font-size:12px;">{datos.get('nom_prov','—')[:40]}</span>
        </div>
        <div class="confianza-item">
            <span class="badge-revision">REVISION REQUERIDA</span>
            &nbsp;<span style="color:#888;font-size:12px;">Doc {1} de {total_cola}</span>
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
                    texto_crudo += (
                        page.extract_text(layout=True) or page.extract_text() or ""
                    ) + "\n"

                st.markdown("**Texto extraido del PDF:**")
                st.text_area(
                    "Texto",
                    value=texto_crudo.strip(),
                    height=180,
                    label_visibility="collapsed"
                )
        except Exception:
            st.error("No se pudo cargar la vista previa del PDF.")

    with col_form:
        st.markdown("### Correccion Rapida")

        nom_sugerido = datos.get("nom_prov", "")
        if nom_sugerido in [NOMBRE_PLACEHOLDER, "ESCRIBE EL NOMBRE AQUI"]:
            nom_sugerido = ""

        with st.form(key=f"form_rev_{item_actual['archivo']}_{total_cola}"):
            f_fecha = st.text_input(
                "Fecha (DD/MM/YYYY) *",
                value=datos.get("fecha", ""),
                placeholder="15/03/2024"
            )
            f_gen = st.text_input(
                "Codigo de Generacion (UUID) *",
                value=datos.get("gen", ""),
                placeholder="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
            )
            f_nom = st.text_input(
                "Razon Social del Proveedor *",
                value=nom_sugerido,
                placeholder="Empresa Proveedora S.A. de C.V."
            )

            c_mon1, c_mon2 = st.columns(2)
            with c_mon1:
                try:
                    tot_default = float(datos.get("tot", 0.0))
                except (TypeError, ValueError):
                    tot_default = 0.0
                f_tot = st.number_input(
                    "Total a Pagar ($) *", value=tot_default,
                    format="%.2f", min_value=0.0
                )
            with c_mon2:
                try:
                    exe_default = float(datos.get("exe", 0.0))
                except (TypeError, ValueError):
                    exe_default = 0.0
                f_exe = st.number_input(
                    "Exento/Fovial ($)", value=exe_default,
                    format="%.2f", min_value=0.0
                )

            st.write("")
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                submit_aprobar   = st.form_submit_button("Aprobar y Guardar",  type="primary", use_container_width=True)
            with c_btn2:
                submit_descartar = st.form_submit_button("Descartar Archivo", use_container_width=True)

        if submit_aprobar:
            if not f_fecha or not f_gen or not f_nom or f_tot <= 0:
                st.error("Rellena todos los campos marcados con (*) para continuar.")
            else:
                nit_actual = datos.get("nit_prov", "")
                if nit_actual:
                    guardar_proveedor_rapido(nit_actual, f_nom.upper())
                    for item in st.session_state.cola_revision[1:]:
                        if item["datos"].get("nit_prov") == nit_actual:
                            item["datos"]["nom_prov"] = f_nom.upper()

                try:
                    iva_actual = float(datos.get("iva", 0.0))
                except (TypeError, ValueError):
                    iva_actual = 0.0

                datos["fecha"]   = f_fecha.strip()
                datos["gen"]     = f_gen.strip().upper()
                datos["nom_prov"] = f_nom.strip().upper()
                datos["tot"]     = round(f_tot, 2)
                datos["exe"]     = round(f_exe, 2)

                if f_tot > 0 and iva_actual == 0.0:
                    datos["gra"]      = round((f_tot - f_exe) / 1.13, 2)
                    datos["iva"]      = round(f_tot - f_exe - datos["gra"], 2)
                    datos["iva_calc"] = True

                datos["archivo"] = item_actual["archivo"]

                nuevo_df = pd.DataFrame([datos])
                if st.session_state.db_compras.empty:
                    st.session_state.db_compras = nuevo_df
                else:
                    st.session_state.db_compras = pd.concat(
                        [st.session_state.db_compras, nuevo_df], ignore_index=True
                    )

                st.session_state.cola_revision.pop(0)
                st.rerun()

        if submit_descartar:
            st.session_state.cola_revision.pop(0)
            st.rerun()

    st.divider()

# ═══════════════════════════════════════════════════════════════
# DASHBOARD DE ALERTAS
# ═══════════════════════════════════════════════════════════════

if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### Alertas de Procesamiento")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        n = len(rep.get("corruptos", []))
        if n:
            st.error(f"**{n} Danados** (PDF corrupto).")
            with st.expander("Ver lista"):
                st.markdown('<div class="scroll-list">' + "".join(f"- {a}<br>" for a in rep["corruptos"]) + '</div>', unsafe_allow_html=True)
        else:
            st.success("**0 Danados.**")

    with c2:
        intrusos_n  = len(rep.get("intrusos", []))
        invalidos_n = len(rep.get("invalidos", []))
        total_rej   = intrusos_n + invalidos_n
        if total_rej:
            st.error(f"**{total_rej} Rechazados** ({intrusos_n} ajenos, {invalidos_n} tipo incorrecto).")
            with st.expander("Ver lista"):
                todos = rep.get("intrusos", []) + rep.get("invalidos", [])
                st.markdown('<div class="scroll-list">' + "".join(f"- {a}<br>" for a in todos) + '</div>', unsafe_allow_html=True)
        else:
            st.success("**0 Rechazados.**")

    with c3:
        n = len(rep.get("duplicados", []))
        if n:
            st.error(f"**{n} Omitidos** (Duplicados).")
            with st.expander("Ver lista"):
                st.markdown('<div class="scroll-list">' + "".join(f"- {a}<br>" for a in rep["duplicados"]) + '</div>', unsafe_allow_html=True)
        else:
            st.success("**0 Omitidos.**")

    with c4:
        n = len(rep.get("iva_calc", []))
        if n:
            st.info(f"**{n} IVA Calc.** (Calculado al 13%).")
            with st.expander("Ver lista"):
                st.markdown('<div class="scroll-list">' + "".join(f"- {a}<br>" for a in rep["iva_calc"]) + '</div>', unsafe_allow_html=True)
        else:
            st.success("**0 IVA Calc.**")

    st.divider()

# ═══════════════════════════════════════════════════════════════
# TABLA DE RESULTADOS Y EXPORTACION
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_compras.empty:
    df = st.session_state.db_compras.copy()

    st.markdown("### Filtros de Auditoria Rapida")
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("Buscar Proveedor", placeholder="Nombre, NIT o UUID...")
    with col_f2:
        tipos_disponibles = df['tipo'].unique().tolist() if 'tipo' in df.columns else []
        filtro_tipo = st.multiselect("Filtrar por Tipo DTE", options=tipos_disponibles, default=tipos_disponibles)

    df_filtrado = df.copy()

    if busqueda:
        termino = busqueda.upper()
        mask = (
            df_filtrado['nom_prov'].str.upper().str.contains(termino, na=False)
            | df_filtrado['nit_prov'].str.contains(termino, na=False)
            | df_filtrado['dui_prov'].str.contains(termino, na=False)
            | df_filtrado['gen'].str.upper().str.contains(termino, na=False)
        )
        df_filtrado = df_filtrado[mask]

    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]

    st.divider()
    tab1, tab2 = st.tabs(["F-07 Compras a Contribuyentes", "Auditoria Total"])

    with tab1:
        if df_filtrado.empty:
            st.info("No hay registros que coincidan con los filtros aplicados.")
        else:
            df_h = pd.DataFrame({
                "A. Fecha Emision":        df_filtrado["fecha"],
                "B. Clase":                "4",
                "C. Tipo Doc":             df_filtrado["tipo"],
                "D. Num Documento":        df_filtrado["gen"],
                "E. NIT/NRC Prov":         df_filtrado["nit_prov"],
                "F. Nombre Prov":          df_filtrado["nom_prov"],
                "G. Compra Ext/NS":        df_filtrado["exe"],
                "H. Internacion Ext/NS":   0.00,
                "I. Importacion Ext/NS":   0.00,
                "J. Compra Gravada":       df_filtrado["gra"],
                "K. Inter. Gravada Bienes": 0.00,
                "L. Impor. Gravada Bienes": 0.00,
                "M. Impor. Gravada Serv":  0.00,
                "N. Credito Fiscal (IVA)": df_filtrado["iva"],
                "O. Total Compras":        df_filtrado["tot"],
                "P. DUI Prov":             df_filtrado["dui_prov"],
                "Q. Tipo Operacion":       "1",
                "R. Clasificacion":        "1",
                "S. Sector":               "1",
                "T. Tipo Costo/Gasto":     "1",
                "U. Num Anexo":            "3"
            })

            cols_num = [
                "G. Compra Ext/NS", "H. Internacion Ext/NS", "I. Importacion Ext/NS",
                "J. Compra Gravada", "K. Inter. Gravada Bienes", "L. Impor. Gravada Bienes",
                "M. Impor. Gravada Serv", "N. Credito Fiscal (IVA)", "O. Total Compras"
            ]

            st.dataframe(
                df_h.style.format({c: "{:.2f}" for c in cols_num}),
                hide_index=True,
                use_container_width=True
            )

            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            with col_kpi1: st.metric("Registros",     len(df_h))
            with col_kpi2: st.metric("Total Gravado", f"${df_h['J. Compra Gravada'].sum():,.2f}")
            with col_kpi3: st.metric("Total IVA CF",  f"${df_h['N. Credito Fiscal (IVA)'].sum():,.2f}")
            with col_kpi4: st.metric("Total General", f"${df_h['O. Total Compras'].sum():,.2f}")

            st.write("")
            if st.button("Generar Excel para Hacienda", type="primary", use_container_width=True):
                ventana_descarga_compras(df_h, "F07_Compras_Proveedores.xlsx")

    with tab2:
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.write(f"Registros filtrados: **{len(df_filtrado)}** de **{len(df)}** totales")
        with col_a2:
            motores = df['motor'].value_counts().to_dict() if 'motor' in df.columns else {}
            for motor_name, count in motores.items():
                st.write(f"Motor {motor_name}: **{count}** documentos")
        st.dataframe(df_filtrado, use_container_width=True)
