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

# FIX CRITICO: Verificar que sea dict valido
if not isinstance(st.session_state.cliente_activo, dict):
    st.warning("El cliente activo no es valido. Regresa al Dashboard y vuelve a seleccionarlo.")
    st.stop()

cliente = st.session_state.cliente_activo

# ═══════════════════════════════════════════════════════════════
# CONFIGURACION TECNICA
# ═══════════════════════════════════════════════════════════════
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

st.set_page_config(
    page_title="Extractor DTE Compras",
    layout="wide",
    page_icon="C"
)

# ═══════════════════════════════════════════════════════════════
# ESTILOS
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
    .kpi-total {
        background-color: #0a1628;
        border: 1px solid #003057;
        border-radius: 8px;
        padding: 12px 16px;
        margin-top: 8px;
        font-size: 13px;
        color: #4DA8DA;
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

NOMBRE_PLACEHOLDER = "ESCRIBE EL NOMBRE AQUI"  # FIX: sin acento para comparacion segura
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
# FUNCIONES DE BASE DE DATOS DE PROVEEDORES
# ═══════════════════════════════════════════════════════════════

def cargar_proveedores_json():
    """
    Carga el directorio de proveedores con migracion automatica.
    FIX: Acepta tanto formato string legacy como dict nuevo.
    """
    if not os.path.exists(ARCHIVO_PROVEEDORES):
        return {}
    try:
        with open(ARCHIVO_PROVEEDORES, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Migracion: string -> dict
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = {"nombre": v, "nrc": ""}
        return data
    except Exception:
        return {}


def guardar_proveedor_rapido(nit, nombre):
    """Guarda/actualiza un proveedor preservando el NRC existente."""
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
    """
    FIX: Guarda multiples proveedores nuevos en una sola operacion
    al final del batch, en lugar de escrituras individuales.
    """
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
        st.error(f"Error al guardar lote de proveedores: {err}")


# ═══════════════════════════════════════════════════════════════
# FUNCIONES DE EXPORTACION EXCEL
# ═══════════════════════════════════════════════════════════════

def to_excel_hacienda_compras(df):
    """
    Exporta el DataFrame al formato exacto de Hacienda para F-07 Compras.
    Sin encabezados, con formatos de celda especificos por columna.
    """
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

        worksheet.set_column(0,  0,  10,               fmt_texto)    # A: Fecha
        worksheet.set_column(1,  1,  1,                fmt_texto)    # B: Clase
        worksheet.set_column(2,  2,  2,                fmt_texto)    # C: Tipo
        worksheet.set_column(3,  3,  get_max_len(3),   fmt_texto)    # D: UUID Gen
        worksheet.set_column(4,  4,  14,               fmt_texto)    # E: NIT Prov
        worksheet.set_column(5,  5,  get_max_len(5),   fmt_texto)    # F: Nombre
        worksheet.set_column(6,  14, 10.71,            fmt_num_izq)  # G-O: Montos
        worksheet.set_column(15, 15, 9,                fmt_texto)    # P: DUI
        worksheet.set_column(16, 20, 1,                fmt_texto)    # Q-U: Clasificadores

    output.seek(0)
    return output.getvalue()


# ═══════════════════════════════════════════════════════════════
# FUNCIONES UTILITARIAS DE PARSING
# ═══════════════════════════════════════════════════════════════

def limpiar_monto(monto_str):
    """
    Convierte string de monto a float.
    FIX: Maneja correctamente 4 decimales (FOVIAL/COTRANS).
    Formatos soportados: 1,234.56 / 1.234,56 / 1234.56 / 1234.5678
    """
    try:
        s = re.sub(r'[^\d.,]', '', str(monto_str)).strip()
        if not s:
            return 0.0

        # Detectar separador decimal buscando el ultimo separador
        ultimo_sep = re.search(r'([.,])(\d{1,4})$', s)
        if ultimo_sep:
            sep      = ultimo_sep.group(1)
            decimals = ultimo_sep.group(2)
            enteros  = re.sub(r'[^\d]', '', s[:ultimo_sep.start()])
            if not enteros:
                enteros = "0"
            # Normalizar a 2 decimales (redondear si tiene 4)
            valor = float(f"{enteros}.{decimals}")
            return round(valor, 2)
        else:
            return float(re.sub(r'[^\d]', '', s))

    except (ValueError, AttributeError):
        return 0.0


def extraer_y_formatear_fecha(texto):
    """
    Extrae y formatea fecha al formato DD/MM/YYYY.
    Estrategia en cascada: ISO → libre → con etiqueta.
    """
    # Formato ISO: 2024-03-15
    m = re.search(
        r"\b(20[2-3]\d)\s*[-/]\s*(0[1-9]|1[0-2])\s*[-/]\s*([0-2]\d|3[01])\b",
        texto
    )
    if m:
        return f"{int(m.group(3)):02d}/{int(m.group(2)):02d}/{m.group(1)}"

    # Formato libre: 15/03/2024 o 03/15/2024
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

    # Formato con etiqueta explicita
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
    """
    Limpia y valida un nombre de proveedor candidato.
    FIX: Usa constante NOMBRE_PLACEHOLDER sin acentos para comparacion segura.
    Retorna nombre limpio o NOMBRE_PLACEHOLDER si es invalido.
    """
    if not nombre_raw:
        return NOMBRE_PLACEHOLDER

    # Eliminar prefijos de etiqueta
    nombre = re.sub(
        r"^(?:(?:O\s*)?RAZ[OO]N\s*SOCIAL|NOMBRE(?: O RAZ[OO]N SOCIAL)?|"
        r"CLIENTE|NOMBRE COMERCIAL|COMERCIAL)[\s:]*",
        "", nombre_raw, flags=re.I
    ).strip()

    # Eliminar caracteres basura al inicio
    nombre = re.sub(r"^[^A-Za-z0-9]+", "", nombre).strip()

    # Validaciones de longitud y contenido
    if (
        len(nombre) > 65
        or len(nombre) < 4
        or nombre.upper() in NOMBRES_INVALIDOS
        or any(bad in nombre.upper() for bad in BASURA_ESTRICTA)
    ):
        return NOMBRE_PLACEHOLDER

    # Verificar que no sea el nombre del propio cliente
    palabras_cliente = cliente_nombre.upper().split()[:2]
    if any(p in nombre.upper() for p in palabras_cliente if len(p) > 3):
        return NOMBRE_PLACEHOLDER

    return nombre.upper()


# ═══════════════════════════════════════════════════════════════
# MOTOR PRINCIPAL DE EXTRACCION — COMPRAS
# ═══════════════════════════════════════════════════════════════

def extraer_compras_nativo_pro(file_bytes, cliente_activo, proveedores_cache=None):
    """
    Motor de extraccion de DTE de Compras (El Salvador).
    Acepta DTE: 03 (CCF), 05 (Nota Credito), 06 (Nota Debito).

    FIX RENDIMIENTO: Acepta proveedores_cache para evitar
    recargar el JSON en cada llamada dentro del loop.
    """
    motor = "Nativo"

    try:
        # ── EXTRACCION DE TEXTO (Nativo + OCR Fallback) ──
        texto_lineal  = ""
        texto_visual  = ""
        usa_ocr       = False

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t_lin = page.extract_text(layout=False) or ""
                t_vis = page.extract_text() or ""
                texto_lineal += t_lin + "\n"
                texto_visual += t_vis + "\n"

        texto_completo = texto_lineal + "\n" + texto_visual

        # FIX: Fallback OCR si el PDF es imagen
        if len(texto_completo.strip()) < 80:
            motor  = "ICR (OCR)"
            usa_ocr = True
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    img = page.to_image(resolution=300)
                    ocr_txt = pytesseract.image_to_string(img.original, lang='spa')
                    texto_lineal  += ocr_txt + "\n"
                    texto_completo = texto_lineal

        if len(texto_completo.strip()) < 50:
            return {"error": "El PDF no tiene texto legible ni imagen procesable."}

        t_clean    = re.sub(r'\s+', ' ', texto_completo)
        t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        # ── DETECCION DEL TIPO DE DTE ──
        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
        tipo   = "01"
        ctrl   = ""

        if m_ctrl:
            ctrl   = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo:
                tipo = m_tipo.group(1)
        
        if not ctrl:
            return {"error_tipo": "No se detecto un Numero de Control DTE valido."}
        if tipo not in ["03", "05", "06"]:
            return {"error_tipo": f"El documento es DTE-{tipo}. Solo se admiten 03, 05 y 06."}

        # ── DATOS DEL RECEPTOR (Cliente Activo) ──
        nit_receptor = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
        dui_receptor = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))

        # ── CODIGO DE GENERACION (UUID) ──
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

        # ── FECHA ──
        fecha = extraer_y_formatear_fecha(t_clean)

        # ── IDENTIFICACION DEL PROVEEDOR (EMISOR) ──
        nit_prov = ""
        dui_prov = ""
        nom_prov = NOMBRE_PLACEHOLDER
        es_nuevo = True

        # Aislar zona del EMISOR (antes de la seccion del RECEPTOR)
        partes_emisor = re.split(
            r"(?i)\b(?:RECEPTOR|CLIENTE:|CLIENTE\s|SOCIO/EMPRESA)\b",
            texto_lineal
        )
        texto_emisor = partes_emisor[0] if len(partes_emisor) > 0 else texto_lineal
        if len(texto_emisor.strip()) < 100:
            texto_emisor = texto_lineal[:1500]

        # Radar de NITs/DUIs en la zona del emisor
        patron_ids = (
            r"\b\d{4}\s*[-]?\s*\d{6}\s*[-]?\s*\d{3}\s*[-]?\s*\d{1}\b"
            r"|\b\d{14}\b"
            r"|\b\d{8}\s*[-]?\s*\d{1}\b"
            r"|\b\d{9}\b"
        )
        nits_raw       = re.findall(patron_ids, texto_emisor)
        nits_limpios   = list(dict.fromkeys([re.sub(r'[^0-9]', '', n) for n in nits_raw]))
        nits_candidatos = [
            n for n in nits_limpios
            if n != nit_receptor and n != dui_receptor
        ]

        # FIX RENDIMIENTO: Usar cache pasada como parametro
        prov_db = proveedores_cache if proveedores_cache is not None else cargar_proveedores_json()

        # Buscar en directorio de proveedores
        for n in nits_candidatos:
            if n in prov_db:
                nit_prov = n
                nom_prov = prov_db[n].get("nombre", NOMBRE_PLACEHOLDER)
                es_nuevo = False
                break

        # Si no encontrado en directorio, tomar el primer candidato
        if not nit_prov and nits_candidatos:
            nit_prov = nits_candidatos[0]

        # DUI si es de 9 digitos
        if len(nit_prov) == 9:
            dui_prov = nit_prov

        # Extraer nombre si es proveedor nuevo
        if es_nuevo and nit_prov:
            nombre_encontrado = ""

            # Intento 1: Busqueda por etiqueta explicita
            m_etiqueta = re.search(
                r"(?:Nombre[:\s]+|Nombre\s+o\s+raz[oo]n\s+social[:\s]+|Raz[oo]n\s+Social[:\s]+)"
                r"(.*?)(?:NIT|NRC|Giro|Actividad|Direcci[oo]n|$)",
                texto_emisor, re.I | re.DOTALL
            )
            if m_etiqueta:
                candidato = m_etiqueta.group(1).strip().replace('\n', ' ')[:80]
                if (
                    len(candidato) > 5
                    and not any(bad in candidato.upper() for bad in BASURA_ESTRICTA)
                    and "RECEPTOR" not in candidato.upper()
                ):
                    nombre_encontrado = candidato

            # Intento 2: Busqueda por indicadores comerciales en lineas
            if not nombre_encontrado:
                for linea in texto_emisor.split('\n')[:30]:
                    L = linea.strip().upper()
                    if len(L) < 5:
                        continue
                    if sum(c.isdigit() for c in L) / len(L) > 0.3:
                        continue
                    if any(b in L for b in PALABRAS_BASURA):
                        continue
                    if any(bad in L for bad in BASURA_ESTRICTA):
                        continue
                    if any(marca in L for marca in MARCAS_COMERCIALES):
                        clean = re.split(r'\s{4,}|NIT|NRC', L)[0].strip()
                        palabras_cliente = cliente_activo.get('nombre', '').upper().split()[:2]
                        if clean and not any(p in clean for p in palabras_cliente if len(p) > 3):
                            nombre_encontrado = clean
                            break

            # Normalizar y validar el nombre encontrado
            nom_prov = normalizar_nombre_proveedor(
                nombre_encontrado,
                cliente_activo.get('nombre', '')
            )

        # ── EXTRACCION DE MONTOS ──
        e, g, i, ret, perc, t = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        iva_calculado = False

        # FOVIAL y COTRANS (exentos de transporte)
        fovial  = 0.0
        cotrans = 0.0

        m_fovial = re.search(r"FOVIAL.{0,50}", texto_completo, re.I)
        if m_fovial:
            nums = re.findall(r"\d+[.,]\d{2,4}", m_fovial.group(0))
            if nums:
                fovial = max(limpiar_monto(n) for n in nums)

        m_cotrans = re.search(r"COTRANS.{0,50}", texto_completo, re.I)
        if m_cotrans:
            nums = re.findall(r"\d+[.,]\d{2,4}", m_cotrans.group(0))
            if nums:
                cotrans = max(limpiar_monto(n) for n in nums)

        e = round(fovial + cotrans, 2)

        # Exentos explicitos (supera a FOVIAL+COTRANS si es mayor)
        m_exe = re.search(
            r"(?:Ventas\s+Exentas|Total\s+Exento)[^\d]{0,30}?"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})",
            t_clean, re.I
        )
        if m_exe:
            val_exe = limpiar_monto(m_exe.group(1))
            if val_exe > e:
                e = val_exe

        # Retencion
        m_ret = re.search(
            r"(?:Retenido|Retenci[oo]n)[^0-9]*"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})",
            t_clean, re.I
        )
        if m_ret:
            ret = limpiar_monto(m_ret.group(1))

        # ALGORITMO MATEMATICO PRINCIPAL: Buscar triplete (g, i, t) valido
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
                    # Verificacion 13%
                    if abs(round(val_g * 0.13, 2) - round(val_i, 2)) <= 0.05:
                        # Verificacion del total
                        total_calculado = round(val_g + val_i + e - ret, 2)
                        if abs(total_calculado - round(val_t, 2)) <= 0.10:
                            g, i, t = val_g, val_i, val_t
                            encontrado = True
                            break

        # Fallback textual si el algoritmo fallo
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
            "fecha":      fecha,
            "nit_prov":   nit_prov,
            "dui_prov":   dui_prov,
            "nom_prov":   nom_prov,
            "tipo":       tipo,
            "ctrl":       ctrl,
            "gen":        gen,
            "exe":        e,
            "gra":        max(0.0, g),
            "iva":        max(0.0, i),
            "ret":        ret,
            "perc":       perc,
            "tot":        t,
            "estado":     "OK",
            "iva_calc":   iva_calculado,
            "es_nuevo":   es_nuevo,
            "nit_nuevo":  nit_prov,
            "motor":      motor
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

            # FIX RENDIMIENTO: Cargar proveedores UNA sola vez para todo el batch
            prov_cache = cargar_proveedores_json()

            for idx, f in enumerate(nuevos):

                # GC cada 50 archivos
                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                # Progreso
                if idx > 0:
                    elapsed = time.time() - t_inicio
                    eta     = int((elapsed / idx) * (total - idx))
                    m_t, s  = divmod(eta, 60)
                    txt_progreso.markdown(
                        f"Procesando: **{idx+1}** de **{total}** "
                        f"| Restante: {m_t:02d}:{s:02d}"
                    )
                else:
                    txt_progreso.markdown(f"Procesando: **1** de **{total}** | Extrayendo...")

                file_bytes = f.read()

                if len(file_bytes) < 1024:
                    corruptos.append(f.name)
                    st.session_state.archivos_comp.add(f.name)
                    bar.progress((idx + 1) / total)
                    continue

                # FIX RENDIMIENTO: Pasar cache como argumento
                res = extraer_compras_nativo_pro(file_bytes, cliente, prov_cache)

                codigo_gen   = res.get('gen', '')
                dup_memoria  = (
                    not st.session_state.db_compras.empty
                    and codigo_gen != ""
                    and (st.session_state.db_compras['gen'] == codigo_gen).any()
                )
                dup_lote     = (
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
                    fecha_str    = str(res.get('fecha',    '')).strip()
                    nom_prov_str = str(res.get('nom_prov', '')).strip()

                    # FIX: Comparacion segura sin acentos
                    nom_es_placeholder = (
                        nom_prov_str == NOMBRE_PLACEHOLDER
                        or nom_prov_str == "ESCRIBE EL NOMBRE AQUI"
                        or nom_prov_str == ""
                    )

                    # FIX: Conversion segura del total
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
                            # FIX: Actualizar cache local para el resto del batch
                            prov_cache[res["nit_nuevo"]] = {
                                "nombre": res["nom_prov"],
                                "nrc": ""
                            }
                        res["archivo"] = f.name
                        extracted.append(res)

                else:
                    corruptos.append(f.name)

                bar.progress((idx + 1) / total)

            txt_progreso.success(f"{total} facturas escaneadas correctamente.")

            # FIX: Guardar proveedores nuevos en un solo batch al final
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
# BANDEJA DE REVISION MANUAL
# FIX: Separada del st.stop() para no bloquear el reporte
# ═══════════════════════════════════════════════════════════════

if st.session_state.cola_revision:
    st.markdown("""
    <div class="inbox-revision">
        <h3 style="margin-top:0; color:#ffaa00;">Bandeja de Revision Manual</h3>
        <p style="color:#aaa; margin-bottom:0;">
            Se encontraron datos borrosos o incompletos.
            Revisa la imagen y completa los campos requeridos.
        </p>
    </div>
    """, unsafe_allow_html=True)

    total_cola  = len(st.session_state.cola_revision)
    item_actual = st.session_state.cola_revision[0]
    datos       = item_actual["datos"]

    st.info(f"Documento **1 de {total_cola}** en revision.")

    col_img, col_form = st.columns([1.2, 1], gap="large")

    # ── COLUMNA IMAGEN ──
    with col_img:
        try:
            with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                img = pdf.pages[0].to_image(resolution=250).original
                st.image(img, caption=f"Vista Previa: {item_actual['archivo']}", use_container_width=True)

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

    # ── COLUMNA FORMULARIO ──
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
                f_tot = st.number_input("Total a Pagar ($) *", value=tot_default, format="%.2f", min_value=0.0)

            with c_mon2:
                try:
                    exe_default = float(datos.get("exe", 0.0))
                except (TypeError, ValueError):
                    exe_default = 0.0
                f_exe = st.number_input("Exento/Fovial ($)", value=exe_default, format="%.2f", min_value=0.0)

            st.write("")
            c_btn1, c_btn2 = st.columns(2)

            with c_btn1:
                submit_aprobar = st.form_submit_button(
                    "Aprobar y Guardar",
                    type="primary",
                    use_container_width=True
                )
            with c_btn2:
                submit_descartar = st.form_submit_button(
                    "Descartar Archivo",
                    use_container_width=True
                )

        # ── LOGICA FUERA DEL FORM (FIX: evita errores de estado) ──
        if submit_aprobar:
            if not f_fecha or not f_gen or not f_nom or f_tot <= 0:
                st.error("Rellena todos los campos marcados con (*) para continuar.")
            else:
                nit_actual = datos.get("nit_prov", "")

                # Guardar proveedor
                if nit_actual:
                    guardar_proveedor_rapido(nit_actual, f_nom.upper())

                    # FIX O(n): Actualizar nombre en toda la cola en una sola pasada
                    for item in st.session_state.cola_revision[1:]:
                        if item["datos"].get("nit_prov") == nit_actual:
                            item["datos"]["nom_prov"] = f_nom.upper()

                # FIX: Conversion segura de IVA
                try:
                    iva_actual = float(datos.get("iva", 0.0))
                except (TypeError, ValueError):
                    iva_actual = 0.0

                datos["fecha"]    = f_fecha.strip()
                datos["gen"]      = f_gen.strip().upper()
                datos["nom_prov"] = f_nom.strip().upper()
                datos["tot"]      = round(f_tot, 2)
                datos["exe"]      = round(f_exe, 2)

                # Calcular IVA si no se extrajo
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

    # FIX CRITICO: NO usar st.stop() aqui — permite que el reporte
    # se muestre debajo de la bandeja si hay datos procesados
    st.divider()


# ═══════════════════════════════════════════════════════════════
# DASHBOARD DE ALERTAS
# ═══════════════════════════════════════════════════════════════

if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### Alertas de Procesamiento Automatico")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        n = len(rep.get("corruptos", []))
        if n:
            st.error(f"**{n} Danados** (PDF corrupto).")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in rep["corruptos"])
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 Danados.**")

    with c2:
        intrusos_n  = len(rep.get("intrusos",  []))
        invalidos_n = len(rep.get("invalidos", []))
        total_rej   = intrusos_n + invalidos_n
        if total_rej:
            st.error(f"**{total_rej} Rechazados** ({intrusos_n} ajenos, {invalidos_n} tipo incorrecto).")
            with st.expander("Ver lista"):
                todos = rep.get("intrusos", []) + rep.get("invalidos", [])
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in todos)
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 Rechazados.**")

    with c3:
        n = len(rep.get("duplicados", []))
        if n:
            st.error(f"**{n} Omitidos** (Duplicados).")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in rep["duplicados"])
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 Omitidos.**")

    with c4:
        n = len(rep.get("iva_calc", []))
        if n:
            st.info(f"**{n} IVA Calc.** (Calculado al 13%).")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in rep["iva_calc"])
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 IVA Calc.**")

    st.divider()


# ═══════════════════════════════════════════════════════════════
# TABLAS DE RESULTADOS Y EXPORTACION
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_compras.empty:
    df = st.session_state.db_compras.copy()

    # ── FILTROS ──
    st.markdown("### Filtros de Auditoria Rapida")
    col_f1, col_f2 = st.columns([2, 1])

    with col_f1:
        busqueda = st.text_input("Buscar Proveedor", placeholder="Nombre, NIT o UUID...")
    with col_f2:
        tipos_disponibles = df['tipo'].unique().tolist() if 'tipo' in df.columns else []
        filtro_tipo = st.multiselect(
            "Filtrar por Tipo DTE",
            options=tipos_disponibles,
            default=tipos_disponibles
        )

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

    # ── TABS ──
    tab1, tab2 = st.tabs([
        "F-07 Compras a Contribuyentes",
        "Auditoria Total"
    ])

    # ── TAB 1: FORMATO HACIENDA ──
    with tab1:
        if df_filtrado.empty:
            st.info("No hay registros que coincidan con los filtros aplicados.")
        else:
            # Construir DataFrame de Hacienda
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
                "M. Impor. Gravada Serv":   0.00,
                "N. Credito Fiscal (IVA)": df_filtrado["iva"],
                "O. Total Compras":        df_filtrado["tot"],
                "P. DUI Prov":             df_filtrado["dui_prov"],
                "Q. Tipo Operacion":       "1",
                "R. Clasificacion":        "1",
                "S. Sector":               "1",
                "T. Tipo Costo/Gasto":     "1",
                "U. Num Anexo":            "3"
            })

            # FIX: Columnas numericas por nombre, no por indice
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

            # KPIs de totales
            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            with col_kpi1:
                st.metric("Registros", len(df_h))
            with col_kpi2:
                st.metric("Total Gravado", f"${df_h['J. Compra Gravada'].sum():,.2f}")
            with col_kpi3:
                st.metric("Total IVA CF", f"${df_h['N. Credito Fiscal (IVA)'].sum():,.2f}")
            with col_kpi4:
                st.metric("Total General", f"${df_h['O. Total Compras'].sum():,.2f}")

            st.write("")
            if st.button("Generar Excel para Hacienda", type="primary", use_container_width=True):
                ventana_descarga_compras(df_h, "F07_Compras_Proveedores.xlsx")

    # ── TAB 2: AUDITORIA COMPLETA ──
    with tab2:
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.write(f"Registros filtrados: **{len(df_filtrado)}** de **{len(df)}** totales")
        with col_a2:
            motores = df['motor'].value_counts().to_dict() if 'motor' in df.columns else {}
            for motor, count in motores.items():
                st.write(f"Motor {motor}: **{count}** documentos")

        st.dataframe(df_filtrado, use_container_width=True)
