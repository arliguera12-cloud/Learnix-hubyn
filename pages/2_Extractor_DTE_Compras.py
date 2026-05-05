import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import json
import os
import gc
from io import BytesIO

# ─────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Extractor DTE · Compras", layout="wide", page_icon="🛒")

# ─────────────────────────────────────────────
# 2. ESTILOS
# ─────────────────────────────────────────────
ESTILO = """
<style>
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"]          { background-color: #0D0F07 !important; }
  [data-testid="stSidebar"]         { background-color: #141A08 !important;
                                      border-right: 1px solid #4A5520 !important; }
  h1, h2, h3, h4, h5, h6           { color: #C8D87A !important; letter-spacing: 0.5px; }
  p, label, span, li                { color: #F0EDD8 !important; }
  [data-testid="stDataFrame"] span  { color: inherit !important; }

  div.stButton > button[kind="primary"],
  div.stDownloadButton > button[kind="primary"] {
    background-color : #6B7A2A !important;
    border           : 1px solid #8A9A35 !important;
    border-radius    : 6px !important;
    transition       : background-color 0.25s ease, transform 0.1s ease;
  }
  div.stButton > button[kind="primary"]:hover,
  div.stDownloadButton > button[kind="primary"]:hover {
    background-color : #8A9A35 !important; transform: scale(1.02);
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #FFFFFF !important; font-weight: bold !important;
  }
  div.stButton > button[kind="secondary"] {
    background-color : transparent !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important; transition: 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover { background-color: #1A2008 !important; }
  div.stButton > button[kind="secondary"] *     { color: #C8D87A !important; }

  div[data-testid="stTextInput"] input,
  div[data-testid="stNumberInput"] input {
    background-color : #1A2008 !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    color            : #F0EDD8 !important;
    caret-color      : #C8D87A;
  }
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stNumberInput"] input:focus {
    border-color : #8A9A35 !important;
    box-shadow   : 0 0 0 2px rgba(138,154,53,0.25) !important;
  }
  button[data-baseweb="tab"] { color: #8A9A35 !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom : 2px solid #8A9A35 !important; color: #F0EDD8 !important;
  }
  div[data-testid="stAlert"]  { display: flex; align-items: center; min-height: 56px; }
  hr { border-color: #4A5520 !important; opacity: 0.4; }

  .card-emisor {
    padding: 12px 16px; border-radius: 8px; background-color: #1A2008;
    color: #F0EDD8 !important; margin-bottom: 18px; font-size: 14px;
    line-height: 1.6; border: 1px solid #2A3010; border-left: 4px solid #8A9A35;
  }
  .card-emisor strong { color: #C8D87A !important; }

  .scroll-list {
    max-height: 200px; overflow-y: auto; padding: 8px 12px;
    background-color: #1A2008; border-radius: 6px;
    border: 1px solid #2A3010; font-family: monospace;
    font-size: 12px; color: #A8BB45; line-height: 1.8;
  }
  .inbox-revision {
    background-color: #1A2008; border: 1px solid #8A9A35;
    border-radius: 10px; padding: 20px; margin-top: 20px; margin-bottom: 20px;
  }
  .inbox-revision h3 { color: #C8D87A !important; margin-top: 0; }
  .inbox-revision p  { color: #8A9A35 !important; }
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. SEGURIDAD
# ─────────────────────────────────────────────
if not st.session_state.get("autenticado"):
    st.warning("Acceso denegado. Por favor, inicia sesion en la pagina principal.")
    st.stop()
if not st.session_state.get("cliente_activo"):
    st.warning("Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Compras.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. CONSTANTES
# ─────────────────────────────────────────────
MAX_VALORES_LOOP = 30

PALABRAS_BASURA = [
    "DOCUMENTO", "TRIBUTARIO", "ELECTRONICO", "ELECTRÓNICO",
    "REPRESENTACIÓN", "REPRESENTACION", "RECEPTOR", "CLIENTE",
    "EMISOR", "FACTURA", "CONSUMIDOR", "COMPROBANTE", "CODIGO",
    "CÓDIGO", "SELLO", "VERSION", "VERSIÓN", "TRANSMISION",
    "TRANSMISIÓN", "MINISTERIO", "HACIENDA", "MUNICIPIO",
    "GIRO:", "ACTIVIDAD", "ECONOMICA", "AGENCIA", "EFECTIVO",
    "FECHA", "HORA", "EMISIÓN", "EMISION", "GENERACIÓN",
    "GENERACION", "TELÉFONO", "TELEFONO", "TIPO ESTABLECIMIENTO",
    "ESTABLECIMIENTO", "CASA MATRIZ", "SUCURSAL:", "NIT:", "NRC:",
    "NUMERO DE CONTROL", "NÚMERO DE CONTROL",
    "MODELO DE FACTURACION", "TIPO DE TRANSMISION",
]
BASURA_ESTRICTA = ["@", "EMAIL", "CORREO", ".COM", "WWW.", "HTTP"]
PREFIJOS_DIRECCION = (
    "KM ", "KM.", "AV.", "AV ", "AVENIDA", "CALLE ", "PASAJE",
    "COLONIA", "COL.", "COL ", "URB.", "URB ", "URBANIZACION",
    "URBANIZACIÓN", "RESIDENCIAL", "LOTIFICACION", "LOTIFICACIÓN",
    "BARRIO", "CANTON", "CANTÓN", "CTON", "CARRETERA", "CARR.",
    "BULEVAR", "BOULEVARD", "BLVD", "POLIGONO", "POLÍGONO",
    "LOCAL ", "NIVEL ", "PISO ", "EDIFICIO", "CENTRO COMERCIAL",
    "COMPLEJO", "PARQUE INDUSTRIAL", "ZONA FRANCA",
    "FINAL ", "FINAL,", "ENTRE ", "#", "NO.",
)
PALABRAS_COMERCIALES = [
    "S.A.", "S.A.S.", "SA ", "C.V.", "CV ", "LTDA.", "LTDA",
    "SOCIEDAD", "DISTRIBUIDORA", "FARMACIA", "GRUPO",
    "LABORATORIOS", "INDUSTRIAS", "SERVICIOS", "COMERCIAL",
    "IMPORTADORA", "EXPORTADORA", "CONSTRUCTORA", "CONSULTORES",
    "CONSULTORA", "INVERSIONES", "ALIMENTOS", "TECNOLOGIA",
    "CLINICA", "HOSPITAL", "SUPERMERCADO", "FERRETERIA", "EMPRESA",
]
NOMBRES_INVALIDOS = {
    "MATRIZ", "LOCAL", "SUCURSAL", "AGENCIA", "OFICINA", "SEDE",
    "ESTABLECIMIENTO", "PUNTO DE VENTA", "TIENDA", "ALMACEN",
    "ALMACÉN", "BODEGA", "CASA", "CONTRIBUYENTE", "DATOS",
}
CORTE_NOMBRE = re.compile(
    r"\s*(?:NIT|NRC|GIRO|ACTIVIDAD|DIRECCI[OÓ]N|CORREO|TEL[EÉ]F|FONO|"
    r"TIPO\s+ESTAB|MUNICIPIO|DEPARTAMENTO|NUMERO\s+DE\s+CONTROL|"
    r"MODELO\s+DE|TIPO\s+DE\s+TRANS|N\.?\s*I\.?\s*T\.?\s*[:\s]|"
    r"N\.?\s*R\.?\s*C\.?\s*[:\s]|\d{4}[\s\-]\d{6})"
    r".*$",
    re.I | re.S
)


# ─────────────────────────────────────────────
# 5. UTILIDADES SEGURAS
# ─────────────────────────────────────────────
def safe_str(val) -> str:
    """Convierte cualquier valor a string seguro, nunca retorna None."""
    if val is None:
        return ""
    return str(val)


def safe_extract_text(page, layout: bool = False) -> str:
    """Extrae texto de una página PDF sin lanzar excepción si falla."""
    try:
        if layout:
            txt = page.extract_text(layout=True)
        else:
            txt = page.extract_text(layout=False)
        return safe_str(txt)
    except Exception:
        try:
            return safe_str(page.extract_text())
        except Exception:
            return ""


def es_linea_direccion(texto: str) -> bool:
    L = safe_str(texto).upper().strip()
    return any(L.startswith(p) or (f" {p}" in L[:50]) for p in PREFIJOS_DIRECCION)


# ─────────────────────────────────────────────
# 6. FUNCIONES AUXILIARES
# ─────────────────────────────────────────────
def cargar_proveedores_json() -> dict:
    archivo = "data/proveedores.json"
    if not os.path.exists(archivo):
        return {}
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = {"nombre": v, "nrc": ""}
        return data
    except Exception:
        return {}


def guardar_proveedor_rapido(nit: str, nombre: str) -> None:
    if not nit or not safe_str(nombre).strip():
        return
    archivo = "data/proveedores.json"
    if not os.path.exists("data"):
        os.makedirs("data")
    db = cargar_proveedores_json()
    nrc_existente = db.get(nit, {}).get("nrc", "")
    db[nit] = {"nombre": safe_str(nombre).strip().upper(), "nrc": nrc_existente}
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)


def actualizar_nombre_en_db(nit: str, nombre: str) -> None:
    if not nit or not safe_str(nombre).strip():
        return
    df = st.session_state.get("db_compras", pd.DataFrame())
    if df.empty or "nit_prov" not in df.columns:
        return
    mask = df["nit_prov"] == nit
    if mask.any():
        st.session_state.db_compras.loc[mask, "nom_prov"] = safe_str(nombre).strip().upper()


def limpiar_monto(monto_str) -> float:
    """Limpia y convierte un string de monto a float, nunca lanza excepción."""
    try:
        s = re.sub(r'[^\d.,]', '', safe_str(monto_str).strip())
        if not s:
            return 0.0
        ultimo_coma  = s.rfind(',')
        ultimo_punto = s.rfind('.')
        if ultimo_coma > ultimo_punto:
            s = s.replace('.', '').replace(',', '.')
        elif ultimo_punto > ultimo_coma:
            s = s.replace(',', '')
        else:
            s = s.replace(',', '').replace('.', '')
        return float(s)
    except Exception:
        return 0.0


def extraer_y_formatear_fecha(texto: str) -> str:
    """Extrae y normaliza fecha a DD/MM/YYYY. Inmune a horas y formatos mixtos."""
    try:
        texto = safe_str(texto)
        # Limpiar horas pegadas (ej. 14/04/2026-16:38 o 2026-04-20 11:15:43)
        texto = re.sub(r'-\s*\d{1,2}:\d{2}(?::\d{2})?', '', texto)
        texto = re.sub(r'\s+\d{1,2}:\d{2}(?::\d{2})?', '', texto)

        # 1. Formato ISO: YYYY-MM-DD o YYYY/MM/DD
        m_f = re.search(
            r"\b(20[2-3]\d)\s*[-\/]\s*(0[1-9]|1[0-2])\s*[-\/]\s*([0-2]\d|3[01])\b",
            texto
        )
        if m_f:
            return f"{int(m_f.group(3)):02d}/{int(m_f.group(2)):02d}/{m_f.group(1)}"

        # 2. Con etiqueta FECHA DE EMISION / GENERACION (Universal)
        m_f = re.search(
            r"(?:FECHA\s*(?:DE\s*)?(?:EMISI[OÓ]N|GENERACI[OÓ]N|EMISION|GENERACION)?)"
            r"[^\d]{0,20}(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})",
            texto, re.I
        )
        if m_f:
            d, mo, y = int(m_f.group(1)), int(m_f.group(2)), int(m_f.group(3))
            if d <= 12 and mo > 12:
                d, mo = mo, d
            if mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}"

        # 3. DD-MM-YYYY o DD/MM/YYYY libre
        m_f = re.search(
            r"\b(\d{1,2})\s*[\/\-\.]\s*(\d{1,2})\s*[\/\-\.]\s*(20[2-3]\d)\b",
            texto
        )
        if m_f:
            p1, p2, y = int(m_f.group(1)), int(m_f.group(2)), m_f.group(3)
            if p1 <= 12 and p2 > 12:
                return f"{p2:02d}/{p1:02d}/{y}"
            elif p2 <= 12 and p1 > 12:
                return f"{p1:02d}/{p2:02d}/{y}"
            elif p2 <= 12 and p1 <= 31:
                return f"{p1:02d}/{p2:02d}/{y}"
    except Exception:
        pass
    return ""


# ══════════════════════════════════════════════════════════════
# EXTRACCIÓN DE NOMBRE DEL PROVEEDOR (Con Filtro Inverso)
# ══════════════════════════════════════════════════════════════
def extraer_nombre_proveedor(
    texto_completo: str,
    pos_nit: int,
    cliente_activo: dict,
) -> str:
    texto_completo = safe_str(texto_completo)
    
    # INVERSIÓN DE FILTRO: Obtenemos el nombre de nuestro cliente para ignorarlo radicalmente
    nombre_receptor = safe_str(cliente_activo.get('nombre', '')).strip().upper()

    def limpiar(s: str) -> str:
        try:
            s = safe_str(s)
            
            # Borrar activamente a nuestro cliente de la linea (Evita fusiones)
            if nombre_receptor and len(nombre_receptor) > 3:
                s = re.compile(re.escape(nombre_receptor), re.I).sub("", s)
            
            # Si quedaron etiquetas pegadas (ej. NOMBRE O RAZON:), cortar por la derecha
            s = re.split(r"(?i)(?:NOMBRE\s+O\s+RAZ[OÓ]N\s+SOCIAL|RAZ[OÓ]N\s+SOCIAL|CLIENTE)\s*[:\-]*\s*", s)[0]

            s = re.sub(
                r"^[\s\-:]*(?:RAZ[OÓ]N\s*SOCIAL|NOMBRE(?:\s+O\s+RAZ[OÓ]N\s+SOCIAL)?|"
                r"NOMBRE\s+COMERCIAL|EMISOR|DATOS\s+DEL\s+EMISOR|"
                r"TIPO\s+DE?\s+ESTABLECIMIENTO|ESTABLECIMIENTO|"
                r"CONTRIBUYENTE\s+EMISOR)[\s:]*",
                s, flags=re.I
            ).strip()
            s = CORTE_NOMBRE.sub("", s).strip()
            s = re.sub(r"^[-_.,;:\s]+|[-_.,;:\s]+$", "", s)
            s = re.sub(r'\s{2,}', ' ', s)
            return s.upper()
        except Exception:
            return ""

    def valido(s: str) -> bool:
        try:
            T = safe_str(s).strip().upper()
            if len(T) < 4 or len(T) > 90:
                return False
            # Bloqueo estricto
            if nombre_receptor and (T == nombre_receptor or T.startswith(nombre_receptor[:15])):
                return False
            if any(b in T for b in BASURA_ESTRICTA):
                return False
            if es_linea_direccion(T):
                return False
            for b in PALABRAS_BASURA:
                if b in T and len(b) > 5:
                    return False
            if T in NOMBRES_INVALIDOS:
                return False
            digitos = sum(c.isdigit() for c in T)
            if len(T) > 0 and digitos / len(T) > 0.40:
                return False
            if re.fullmatch(r'[\d\s\-\.]+', T):
                return False
            return True
        except Exception:
            return False

    try:
        inicio  = max(0, pos_nit - 1500)
        fin     = min(len(texto_completo), pos_nit + 600)
        ventana = texto_completo[inicio:fin]

        # Estrategia A: etiqueta explicita
        patron_etq = re.compile(
            r"(?:Nombre(?:\s+[Oo]\s+[Rr]az[oó]n\s+[Ss]ocial)?|"
            r"[Rr]az[oó]n\s+[Ss]ocial|Nombre\s+[Cc]omercial|"
            r"[Rr]az[oó]n\s*[Ss]ocial\s*del\s*[Ee]misor|"
            r"Nombre\s+del\s+[Ee]misor)"
            r"\s*[:\s]+\s*"
            r"([^\n]{3,80}(?:\n[^\n]{3,60})?)",
            re.I
        )
        for m_etq in patron_etq.finditer(ventana):
            lineas_cap = safe_str(m_etq.group(1)).split('\n')
            candidato  = limpiar(lineas_cap[0])
            if len(candidato) < 6 and len(lineas_cap) > 1:
                candidato = limpiar(lineas_cap[0] + " " + lineas_cap[1])
            if valido(candidato):
                return candidato

        # Estrategia B: lineas antes del NIT
        ventana_antes = texto_completo[inicio:pos_nit]
        lineas_antes  = [ln.strip() for ln in ventana_antes.split('\n') if ln.strip()]
        for linea in reversed(lineas_antes[-22:]):
            candidato = limpiar(linea)
            if valido(candidato):
                return candidato

        # Estrategia C: lineas despues del NIT
        ventana_despues = texto_completo[pos_nit:fin]
        lineas_despues  = [ln.strip() for ln in ventana_despues.split('\n') if ln.strip()]
        for linea in lineas_despues[:10]:
            candidato = limpiar(linea)
            if valido(candidato):
                return candidato

        # Estrategia D: palabras comerciales
        for linea in ventana.split('\n'):
            L = safe_str(linea).strip().upper()
            if not any(w in L for w in PALABRAS_COMERCIALES):
                continue
            clean     = re.split(r'\s{4,}|(?:NIT|NRC|N\.I\.T|N\.R\.C)\s', L)[0].strip()
            candidato = limpiar(clean)
            if valido(candidato):
                return candidato

        # Estrategia E: seccion EMISOR delimitada
        m_sec = re.search(
            r"(?i)(?:DATOS\s+DEL\s+EMISOR|EMISOR\s*[:\-]|CONTRIBUYENTE\s+EMISOR)"
            r"(.{10,600}?)"
            r"(?:DATOS\s+DEL\s+RECEPTOR|RECEPTOR|ADQUIRIENTE|CLIENTE\s*:)",
            texto_completo, re.S
        )
        if m_sec:
            seccion = safe_str(m_sec.group(1))
            m_n = re.search(
                r"(?:Nombre|Raz[oó]n\s+[Ss]ocial)[:\s]+([^\n]{4,80})",
                seccion, re.I
            )
            if m_n:
                candidato = limpiar(safe_str(m_n.group(1)))
                if valido(candidato):
                    return candidato
            for linea in seccion.split('\n'):
                candidato = limpiar(linea.strip())
                if valido(candidato):
                    return candidato

    except Exception:
        pass

    return ""


# ══════════════════════════════════════════════════════════════
# EXTRACTOR PRINCIPAL — COMPRAS (Robustecido)
# ══════════════════════════════════════════════════════════════
def extraer_compras_nativo_pro(file_bytes: bytes, cliente_activo: dict) -> dict:

    # ── Validación física ─────────────────────────────────────
    if not file_bytes or len(file_bytes) < 512:
        return {"error_fatal": "Archivo vacio o demasiado pequeño."}

    try:
        texto_lineal = ""
        texto_visual = ""

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                return {"error_fatal": "PDF sin paginas."}
            for page in pdf.pages:
                texto_lineal += safe_extract_text(page, layout=False) + "\n"
                texto_visual  += safe_extract_text(page, layout=True)  + "\n"

        texto_lineal   = safe_str(texto_lineal)
        texto_visual   = safe_str(texto_visual)
        texto_completo = texto_lineal + "\n" + texto_visual

        if len(texto_completo.strip()) < 50:
            return {"error_fatal": "PDF de imagen sin texto extraible. Usa OCR."}

        # ── Normalización segura ──────────────────────────────
        t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
        t_no_sp = re.sub(r'\s+', '', t_clean).upper()

        # ── Tipo DTE ──────────────────────────────────────────
        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_sp)
        tipo   = "01"
        ctrl   = ""
        if m_ctrl:
            ctrl   = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo:
                tipo = m_tipo.group(1)

        if not ctrl:
            return {"error_tipo": "No se detecto un Numero de Control DTE valido."}
        if tipo not in ("03", "05", "06"):
            return {"error_tipo": f"Documento DTE-{tipo}. Solo se admiten 03, 05 y 06."}

        nit_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nit', '')))
        dui_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('dui', '')))
        excluir_nits = {nit_receptor, dui_receptor} - {""}

        # ── UUID / Código de Generación ───────────────────────
        gen   = ""
        m_url = re.search(r"CODGEN=([A-F0-9\-]{36})", t_no_sp)
        if m_url:
            gen = safe_str(m_url.group(1)).upper()
        else:
            m_uuid = re.search(
                r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
                t_no_sp
            )
            if m_uuid:
                raw = safe_str(m_uuid.group(1)).replace("-", "")
                if len(raw) == 32:
                    gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

        if not gen:
            m_uuid2 = re.search(
                r"([0-9A-Fa-f]{8}[- ]?[0-9A-Fa-f]{4}[- ]?"
                r"[0-9A-Fa-f]{4}[- ]?[0-9A-Fa-f]{4}[- ]?[0-9A-Fa-f]{12})",
                texto_completo
            )
            if m_uuid2:
                raw2 = re.sub(r'[^0-9A-Fa-f]', '', safe_str(m_uuid2.group(1)))
                if len(raw2) == 32:
                    gen = f"{raw2[:8]}-{raw2[8:12]}-{raw2[12:16]}-{raw2[16:20]}-{raw2[20:]}".upper()

        # ── Zona segura para Fechas (Header Cropping) ─────────
        # Cortamos ANTES de la tabla de detalles para no atrapar fechas de vencimiento de productos
        corte_detalles = re.search(r"(?i)\b(CANTIDAD|CANT\.|DESCRIPCI[OÓ]N|DOCUMENTOS RELACIONADOS|CÓDIGO)\b", texto_completo)
        texto_encabezado = texto_completo[:corte_detalles.start()] if corte_detalles else texto_completo[:1500]
        
        fecha = extraer_y_formatear_fecha(texto_encabezado)

        # ── Datos del proveedor ───────────────────────────────
        nit_prov       = ""
        dui_prov       = ""
        nom_prov       = "ESCRIBE EL NOMBRE AQUI"
        es_nuevo       = True
        pos_nit_emisor = -1
        proveedores_db = cargar_proveedores_json()

        patron_etq_nit = re.compile(
            r"N\.?\s*I\.?\s*T\.?\s*[:\s]\s*"
            r"((?:\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d)"
            r"|(?:\d{14})"
            r"|(?:\d{8}[\s\-]?\d))",
            re.I
        )

        for m_etq_nit in patron_etq_nit.finditer(texto_completo):
            nit_cand = re.sub(r'[^0-9]', '', safe_str(m_etq_nit.group(1)))
            if nit_cand not in excluir_nits and len(nit_cand) in (9, 14):
                nit_prov       = nit_cand
                pos_nit_emisor = m_etq_nit.start()
                break

        if not nit_prov:
            partes_doc = re.split(
                r"(?i)\b(?:DATOS\s+DEL\s+RECEPTOR|RECEPTOR\s*[:\-]|"
                r"DATOS\s+DEL\s+ADQUIRIENTE|ADQUIRIENTE\s*[:\-]|"
                r"RECEPTOR\b|CLIENTE\s*:|COMPRADOR\b)\b",
                texto_completo, maxsplit=1
            )
            texto_emisor   = partes_doc[0] if len(partes_doc[0]) > 80 else texto_completo[:2500]
            patron_nit_raw = re.compile(
                r"\b(\d{4})[\s\-]?\d{3,6}[\s\-]?\d{2,6}[\s\-]?\d\b|\b(\d{14})\b"
            )
            for m_raw_nit in patron_nit_raw.finditer(texto_emisor):
                nit_cand = re.sub(r'[^0-9]', '', safe_str(m_raw_nit.group(0)))
                if nit_cand not in excluir_nits and len(nit_cand) == 14:
                    nit_prov       = nit_cand
                    pos_nit_emisor = m_raw_nit.start()
                    break

        if not nit_prov:
            m_url_nit = re.search(r"NIT[=\s]?(\d{14})", t_no_sp)
            if m_url_nit:
                nit_cand = safe_str(m_url_nit.group(1))
                if nit_cand not in excluir_nits:
                    nit_prov = nit_cand

        if not nit_prov:
            patron_todos = re.compile(
                r"\b\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d\b"
                r"|\b\d{14}\b|\b\d{8}[\s\-]?\d\b|\b\d{9}\b"
            )
            for m_any_nit in patron_todos.finditer(texto_completo):
                nit_cand = re.sub(r'[^0-9]', '', safe_str(m_any_nit.group(0)))
                if nit_cand not in excluir_nits and len(nit_cand) in (9, 14):
                    nit_prov       = nit_cand
                    pos_nit_emisor = m_any_nit.start()
                    break

        if len(nit_prov) == 9:
            dui_prov = nit_prov

        # ── BD de proveedores (Filtro Directo) ────────────────
        if nit_prov and nit_prov in proveedores_db:
            nom_prov = safe_str(proveedores_db[nit_prov].get("nombre", ""))
            es_nuevo = False

        # ── Nombre del proveedor ──────────────────────────────
        if es_nuevo and nit_prov:
            pos_busqueda = pos_nit_emisor if pos_nit_emisor >= 0 else len(texto_completo) // 4

            # Le pasamos el cliente_activo para aislar y borrar su nombre
            nombre_encontrado = extraer_nombre_proveedor(
                texto_completo, pos_busqueda, cliente_activo
            )

            if not nombre_encontrado and texto_visual.strip():
                pos_vis = -1
                for m_vis_nit in patron_etq_nit.finditer(texto_visual):
                    nc = re.sub(r'[^0-9]', '', safe_str(m_vis_nit.group(1)))
                    if nc == nit_prov:
                        pos_vis = m_vis_nit.start()
                        break
                if pos_vis < 0:
                    m_crudo = re.search(re.escape(nit_prov[:8]), texto_visual)
                    pos_vis = m_crudo.start() if m_crudo else len(texto_visual) // 4

                nombre_encontrado = extraer_nombre_proveedor(
                    texto_visual, pos_vis, cliente_activo
                )

            nom_prov = nombre_encontrado if nombre_encontrado else "ESCRIBE EL NOMBRE AQUI"

        # ── Extracción de montos ──────────────────────────────
        e, g, i, ret, perc, t = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        iva_calculado = False

        # FIX GASOLINERAS: Exentos -> FOVIAL y COTRANS
        for impuesto in ["FOVIAL", "COTRANS"]:
            m_imp = re.search(fr"{impuesto}[^\d]{{0,30}}(\d{{1,3}}(?:[.,]\d{{3}})*[.,]\d{{1,2}})", t_clean, re.I)
            if m_imp:
                e += limpiar_monto(safe_str(m_imp.group(1)))

        m_exe = re.search(
            r"(?:Ventas?\s+Exentas?|Total\s+Exento|Exentas?)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_exe:
            val_exe = limpiar_monto(safe_str(m_exe.group(1)))
            # Priorizamos el valor explicito Exento si es mayor que la suma manual de fovial
            if val_exe > e:
                e = val_exe
        e = round(e, 2)

        m_ret = re.search(
            r"(?:Retenido|Retenci[oó]n\s+IVA|IVA\s+Retenido)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_ret:
            ret = limpiar_monto(safe_str(m_ret.group(1)))

        patrones_total = [
            r"(?:TOTAL\s+A\s+PAGAR|TOTAL\s+PAGAR)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:MONTO\s+TOTAL|TOTAL\s+OPERACI[OÓ]N)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:VENTA\s+TOTAL|TOTAL\s*\$)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:VALOR\s+TOTAL\s+A\s+PAGAR|TOTAL\s+FACTURA)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:TOTAL\s+(?:EN\s+)?LETRAS?)[^\d]{0,60}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
        ]
        for pat_tot in patrones_total:
            m_tot = re.search(pat_tot, t_clean, re.I)
            if m_tot:
                t = limpiar_monto(safe_str(m_tot.group(1)))
                if t > 0:
                    break

        patrones_iva = [
            r"(?:Impuesto\s+al\s+Valor\s+Agregado|IVA\s*13\s*%|13\s*%\s*IVA)"
            r"[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:I\.V\.A\.?|DÉBITO\s+FISCAL|DEBITO\s+FISCAL)"
            r"[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:Impuesto\s+IVA|IVA\s+Débito|IVA\s+Debito)"
            r"[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
        ]
        for pat_iva in patrones_iva:
            m_iva = re.search(pat_iva, t_clean, re.I)
            if m_iva:
                i = limpiar_monto(safe_str(m_iva.group(1)))
                if i > 0:
                    break

        # ── Reconciliación ──────────────────────────────
        encontrado = False
        if not (t > 0 and i > 0):
            montos_raw = re.findall(
                r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                t_clean
            )
            set_montos = set()
            for raw_val in montos_raw:
                val_limpio = limpiar_monto(raw_val)
                if val_limpio > 0:
                    set_montos.add(val_limpio)

            valores = sorted(list(set_montos), reverse=True)[:MAX_VALORES_LOOP]

            for vt in valores:
                if encontrado:
                    break
                for vg in valores:
                    if vg >= vt:
                        continue
                    if encontrado:
                        break
                    for vi in valores:
                        if vi >= vg:
                            continue
                        if abs(round(vg * 0.13, 2) - round(vi, 2)) <= 0.05:
                            if abs(round(vg + vi + e - ret, 2) - round(vt, 2)) <= 0.05:
                                g, i, t    = vg, vi, vt
                                encontrado = True
                                break

        if not encontrado:
            if t > 0 and i > 0:
                g          = round(t - i - e + ret, 2)
                encontrado = True
            elif t > 0 and i == 0.0 and tipo == "03":
                g             = round((t + ret - e) / 1.13, 2)
                i             = round(t + ret - e - g, 2)
                iva_calculado = True
                encontrado    = True

        return {
            "fecha"    : fecha,
            "nit_prov" : nit_prov,
            "dui_prov" : dui_prov,
            "nom_prov" : nom_prov,
            "tipo"     : tipo,
            "gen"      : gen,
            "exe"      : e,
            "gra"      : g,
            "iva"      : i,
            "ret"      : ret,
            "perc"     : perc,
            "tot"      : t,
            "estado"   : "OK",
            "iva_calc" : iva_calculado,
            "es_nuevo" : es_nuevo,
            "nit_nuevo": nit_prov,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
    except Exception as err:
        return {"error_extraccion": safe_str(err)}


# ─────────────────────────────────────────────
# EXPORTAR EXCEL
# ─────────────────────────────────────────────
def to_excel_hacienda_compras(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Compras_F07')
        ws = writer.sheets['Compras_F07']
        anchos = [10, 2, 2, 38, 16, 45, 10, 10, 10, 12, 10, 10, 10, 12, 14, 10, 2, 2, 2, 2, 4]
        for idx_col, ancho in enumerate(anchos, start=1):
            ws.column_dimensions[ws.cell(1, idx_col).column_letter].width = ancho
        for fila in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=7, max_col=15):
            for celda in fila:
                if isinstance(celda.value, (int, float)):
                    celda.number_format = '#,##0.00'
    return output.getvalue()


@st.dialog("Seguro de Calidad de Compras")
def ventana_descarga_compras(df_resultados: pd.DataFrame, nombre_archivo: str) -> None:
    st.write(
        "Asegurate de haber procesado unicamente los comprobantes que deseas "
        "declarar en el anexo de Compras antes de descargar."
    )
    st.download_button(
        "📥 Confirmar y Descargar Anexo F-07",
        data=to_excel_hacienda_compras(df_resultados),
        file_name=nombre_archivo,
        type="primary"
    )


# ─────────────────────────────────────────────
# HELPER: alerta + lista expandible
# ─────────────────────────────────────────────
def alerta_con_lista(tipo_alerta: str, icono: str, titulo: str, archivos: list) -> None:
    fn = getattr(st, tipo_alerta)
    if archivos:
        fn(f"{icono} **{len(archivos)} {titulo}**")
        with st.expander(f"Ver {len(archivos)} archivo(s)"):
            items_html = "".join(f"<div>📄 {safe_str(a)}</div>" for a in archivos)
            st.markdown(
                f'<div class="scroll-list">{items_html}</div>',
                unsafe_allow_html=True
            )
    else:
        st.success(f"✅ 0 {titulo}")


# ─────────────────────────────────────────────
# HELPER: datos vacíos para revisión manual
# ─────────────────────────────────────────────
def datos_revision_vacio(causa: str = "") -> dict:
    return {
        "fecha"    : "",
        "nit_prov" : "",
        "dui_prov" : "",
        "nom_prov" : "",
        "tipo"     : "03",
        "gen"      : "",
        "exe"      : 0.0,
        "gra"      : 0.0,
        "iva"      : 0.0,
        "ret"      : 0.0,
        "perc"     : 0.0,
        "tot"      : 0.0,
        "estado"   : "REVISION",
        "iva_calc" : False,
        "es_nuevo" : True,
        "nit_nuevo": "",
        "_error"   : safe_str(causa),
    }


# ─────────────────────────────────────────────
# 7. ENCABEZADO
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family:Courier New,monospace;color:#8A9A35;"
        "letter-spacing:3px;margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_titulo:
    st.title("🛒 Extractor DTE — Compras")

st.markdown(f"""
<div class="card-emisor">
    <strong>RECEPTOR ACTIVO:</strong> {safe_str(cliente.get('nombre',''))}<br>
    <strong>NIT:</strong> {safe_str(cliente.get('nit',''))}
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 8. SESSION STATE
# ─────────────────────────────────────────────
if 'cola_revision'     not in st.session_state: st.session_state.cola_revision     = []
if 'comp_uploader_key' not in st.session_state: st.session_state.comp_uploader_key = 0
if 'db_compras'        not in st.session_state: st.session_state.db_compras        = pd.DataFrame()
if 'archivos_comp'     not in st.session_state: st.session_state.archivos_comp     = []
if 'reporte_compras'   not in st.session_state: st.session_state.reporte_compras   = None

# ─────────────────────────────────────────────
# 9. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga de Compras")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra facturas de proveedores (PDF)",
        type="pdf",
        accept_multiple_files=True,
        key=str(st.session_state.comp_uploader_key)
    )

    procesar = st.button(
        "🚀 Procesar Compras",
        type="primary",
        use_container_width=True,
        disabled=not archivos
    )

    if procesar and archivos:
        nombres_procesados = set(st.session_state.archivos_comp)
        nuevos_archivos    = [f for f in archivos if f.name not in nombres_procesados]

        if not nuevos_archivos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            extracted, duplicados, iva_calc_files      = [], [], []
            invalidos, corruptos, nuevos_proveedores_d = [], [], {}

            bar          = st.progress(0)
            txt_progreso = st.empty()
            t_inicio     = time.time()
            total        = len(nuevos_archivos)

            for idx, f in enumerate(nuevos_archivos):
                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                if idx > 0:
                    elapsed   = time.time() - t_inicio
                    remaining = int((elapsed / idx) * (total - idx))
                    m_t, s_t  = divmod(remaining, 60)
                    txt_progreso.caption(
                        f"⏳ {idx+1}/{total} — Restante: {m_t:02d}:{s_t:02d}"
                    )
                else:
                    txt_progreso.caption(f"⏳ Procesando 1 de {total}...")

                file_bytes = f.read()

                if len(file_bytes) < 512:
                    corruptos.append(f.name)
                    st.session_state.archivos_comp.append(f.name)
                    bar.progress((idx + 1) / total)
                    continue

                res = extraer_compras_nativo_pro(file_bytes, cliente)

                cod_gen     = safe_str(res.get('gen', ''))
                dup_memoria = (
                    not st.session_state.db_compras.empty
                    and cod_gen
                    and 'gen' in st.session_state.db_compras.columns
                    and (st.session_state.db_compras['gen'] == cod_gen).any()
                )
                dup_lote = cod_gen and any(d.get('gen') == cod_gen for d in extracted)

                if "error_tipo" in res:
                    invalidos.append(f.name)

                elif dup_memoria or dup_lote:
                    duplicados.append(f.name)

                elif "error_fatal" in res:
                    corruptos.append(f.name)

                elif "error_extraccion" in res:
                    st.session_state.cola_revision.append({
                        "archivo": f.name,
                        "bytes"  : file_bytes,
                        "datos"  : datos_revision_vacio(res["error_extraccion"]),
                    })

                else:
                    nom_res = safe_str(res.get('nom_prov', '')).strip()
                    va_a_revision = (
                        res.get('tot', 0.0) == 0.0
                        or not res.get('gen')
                        or not safe_str(res.get('fecha', '')).strip()
                        or nom_res in ("ESCRIBE EL NOMBRE AQUI", "ESCRIBE EL NOMBRE AQUÍ", "")
                    )
                    if va_a_revision:
                        st.session_state.cola_revision.append({
                            "archivo": f.name,
                            "bytes"  : file_bytes,
                            "datos"  : res,
                        })
                    else:
                        if res.get('iva_calc'):
                            iva_calc_files.append(f.name)
                        if res.get("es_nuevo") and res.get("nit_nuevo"):
                            nit_n = res["nit_nuevo"]
                            nom_n = res["nom_prov"]
                            nuevos_proveedores_d[nit_n] = nom_n
                            guardar_proveedor_rapido(nit_n, nom_n)
                        res["archivo"] = f.name
                        extracted.append(res)

                st.session_state.archivos_comp.append(f.name)
                bar.progress((idx + 1) / total)

            txt_progreso.success(f"✅ {total} facturas escaneadas.")

            st.session_state.reporte_compras = {
                "invalidos"         : invalidos,
                "duplicados"        : duplicados,
                "iva_calc"          : iva_calc_files,
                "nuevos_proveedores": nuevos_proveedores_d,
                "corruptos"         : corruptos,
            }

            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_compras.empty:
                    st.session_state.db_compras = new_df
                else:
                    st.session_state.db_compras = pd.concat(
                        [st.session_state.db_compras, new_df], ignore_index=True
                    )

    st.divider()
    if st.button("🧹 Limpiar Memoria Compras", type="secondary", use_container_width=True):
        for key in ('db_compras', 'archivos_comp', 'reporte_compras', 'cola_revision'):
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.comp_uploader_key = st.session_state.get('comp_uploader_key', 0) + 1
        st.rerun()

    if not st.session_state.db_compras.empty:
        st.divider()
        total_docs  = len(st.session_state.db_compras)
        total_monto = st.session_state.db_compras["tot"].sum()
        st.markdown(f"**📄 Documentos:** `{total_docs}`")
        st.markdown(f"**💰 Total:** `${total_monto:,.2f}`")

# ─────────────────────────────────────────────
# 10. BANDEJA DE REVISIÓN MANUAL
# ─────────────────────────────────────────────
if st.session_state.cola_revision:
    st.markdown("""
    <div class="inbox-revision">
        <h3>📥 Bandeja de Revisión Manual</h3>
        <p>Datos incompletos o fallo de extracción. Revisa y corrige antes de agregar al libro.</p>
    </div>
    """, unsafe_allow_html=True)

    total_cola  = len(st.session_state.cola_revision)
    st.info(f"Quedan **{total_cola}** documento(s) por revisar.")

    item_actual = st.session_state.cola_revision[0]
    datos_act   = item_actual["datos"]

    col_img, col_form = st.columns([1.2, 1], gap="large")

    with col_img:
        try:
            with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                img = pdf.pages[0].to_image(resolution=200).original
                st.image(img, caption=item_actual['archivo'], use_container_width=True)
                texto_crudo = ""
                for page in pdf.pages:
                    texto_crudo += safe_extract_text(page, layout=True) + "\n"
                st.markdown("**📝 Texto extraído:**")
                st.text_area(
                    "", value=texto_crudo.strip(),
                    height=220, label_visibility="collapsed"
                )
        except Exception as ex_prev:
            st.error(f"No se pudo cargar la vista previa: {safe_str(ex_prev)}")

    with col_form:
        st.markdown("### ✍️ Corrección Rápida")

        error_causa = safe_str(datos_act.get("_error", ""))
        if error_causa:
            st.warning(f"⚠️ **Causa del fallo:** `{error_causa}`")

        nit_actual = safe_str(datos_act.get("nit_prov", ""))
        if nit_actual:
            st.caption(f"NIT detectado: `{nit_actual}`")

        with st.form(key=f"form_revision_{item_actual['archivo']}"):
            f_fecha = st.text_input(
                "📅 Fecha (DD/MM/YYYY) *",
                value=safe_str(datos_act.get("fecha", ""))
            )
            f_gen = st.text_input(
                "🔑 Código de Generación (UUID) *",
                value=safe_str(datos_act.get("gen", ""))
            )

            nom_sug = safe_str(datos_act.get("nom_prov", ""))
            if nom_sug in ("ESCRIBE EL NOMBRE AQUI", "ESCRIBE EL NOMBRE AQUÍ", ""):
                nom_sug = ""
            f_nom = st.text_input(
                "🏢 Razón Social del Proveedor *",
                value=nom_sug,
                placeholder="Nombre completo tal como aparece en el DTE"
            )

            c1, c2 = st.columns(2)
            with c1:
                f_tot = st.number_input(
                    "💰 Total a Pagar ($) *",
                    value=float(datos_act.get("tot", 0.0)),
                    format="%.2f", min_value=0.0
                )
            with c2:
                f_exe = st.number_input(
                    "⛽ Exento/Fovial ($)",
                    value=float(datos_act.get("exe", 0.0)),
                    format="%.2f", min_value=0.0
                )

            f_gra = st.number_input(
                "🧾 Compra Gravada ($)",
                value=float(datos_act.get("gra", 0.0)),
                format="%.2f", min_value=0.0,
                help="Deja en 0 para calcular automáticamente"
            )
            f_iva = st.number_input(
                "🏦 IVA Crédito Fiscal ($)",
                value=float(datos_act.get("iva", 0.0)),
                format="%.2f", min_value=0.0,
                help="Deja en 0 para calcular automáticamente"
            )

            actualizar_otros = st.checkbox(
                "🔄 Actualizar este proveedor en todos los registros existentes",
                value=True,
                help="Si ya había facturas de este NIT, actualiza el nombre en toda la tabla."
            )

            st.markdown("")
            b1, b2 = st.columns(2)
            with b1:
                submit_ok  = st.form_submit_button(
                    "✅ Aprobar y Guardar", type="primary", use_container_width=True
                )
            with b2:
                submit_del = st.form_submit_button(
                    "🗑️ Descartar Archivo", use_container_width=True
                )

            if submit_ok:
                errores = []
                if not f_fecha.strip(): errores.append("Fecha requerida.")
                if not f_gen.strip():   errores.append("Código de Generación requerido.")
                if not f_nom.strip():   errores.append("Razón Social del Proveedor requerida.")
                if f_tot <= 0:          errores.append("Total a Pagar debe ser mayor a 0.")

                if errores:
                    for e_msg in errores:
                        st.error(e_msg)
                else:
                    nombre_limpio = f_nom.strip().upper()
                    nit_act       = safe_str(datos_act.get("nit_prov", ""))

                    if nit_act:
                        guardar_proveedor_rapido(nit_act, nombre_limpio)

                    for item_pend in st.session_state.cola_revision[1:]:
                        if item_pend["datos"].get("nit_prov") == nit_act:
                            item_pend["datos"]["nom_prov"] = nombre_limpio
                            item_pend["datos"]["es_nuevo"]  = False

                    if actualizar_otros and nit_act:
                        actualizar_nombre_en_db(nit_act, nombre_limpio)

                    gra_final = f_gra
                    iva_final = f_iva
                    iva_calc  = datos_act.get("iva_calc", False)

                    if f_tot > 0 and gra_final == 0.0 and iva_final == 0.0:
                        gra_final = round((f_tot - f_exe) / 1.13, 2)
                        iva_final = round(f_tot - f_exe - gra_final, 2)
                        iva_calc  = True
                    elif f_tot > 0 and iva_final == 0.0 and gra_final > 0.0:
                        iva_final = round(gra_final * 0.13, 2)
                        iva_calc  = True

                    datos_act.update({
                        "fecha"    : f_fecha.strip(),
                        "gen"      : f_gen.strip().upper(),
                        "nom_prov" : nombre_limpio,
                        "tot"      : f_tot,
                        "exe"      : f_exe,
                        "gra"      : gra_final,
                        "iva"      : iva_final,
                        "iva_calc" : iva_calc,
                        "es_nuevo" : False,
                        "archivo"  : item_actual["archivo"],
                    })

                    nuevo_df = pd.DataFrame([datos_act])
                    if st.session_state.db_compras.empty:
                        st.session_state.db_compras = nuevo_df
                    else:
                        st.session_state.db_compras = pd.concat(
                            [st.session_state.db_compras, nuevo_df], ignore_index=True
                        )

                    if nit_act:
                        rep_actual = st.session_state.get("reporte_compras") or {}
                        np_dict    = rep_actual.get("nuevos_proveedores", {})
                        np_dict[nit_act] = nombre_limpio
                        if st.session_state.reporte_compras:
                            st.session_state.reporte_compras["nuevos_proveedores"] = np_dict

                    st.session_state.cola_revision.pop(0)
                    st.rerun()

            if submit_del:
                st.session_state.cola_revision.pop(0)
                st.rerun()

    st.stop()

# ─────────────────────────────────────────────
# 11. REPORTE DE PROCESAMIENTO
# ─────────────────────────────────────────────
if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### 📋 Alertas de Procesamiento")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        alerta_con_lista(
            "error" if rep.get("corruptos") else "success",
            "💀", "Dañados", rep.get("corruptos", [])
        )
    with c2:
        alerta_con_lista(
            "warning" if rep.get("invalidos") else "success",
            "⚠️", "Ignorados (tipo incorrecto)", rep.get("invalidos", [])
        )
    with c3:
        alerta_con_lista(
            "error" if rep.get("duplicados") else "success",
            "🛑", "Duplicados", rep.get("duplicados", [])
        )
    with c4:
        alerta_con_lista(
            "info" if rep.get("iva_calc") else "success",
            "🧮", "IVA Calculado", rep.get("iva_calc", [])
        )

    np_dict = rep.get("nuevos_proveedores", {})
    if np_dict:
        st.markdown(f"**🆕 Proveedores nuevos guardados:** `{len(np_dict)}`")
        with st.expander("Ver proveedores nuevos registrados"):
            for nit_k, nom_k in np_dict.items():
                st.markdown(f"- `{nit_k}` — **{nom_k}**")

    st.divider()

# ─────────────────────────────────────────────
# 12. TABLA PRINCIPAL Y EXPORT
# ─────────────────────────────────────────────
if not st.session_state.db_compras.empty:
    df = st.session_state.db_compras.copy()

    st.markdown("### 🔍 Filtros de Auditoría")
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("Buscar proveedor 🔎", placeholder="Nombre, NIT o UUID…")
    with col_f2:
        filtro_tipo = st.multiselect(
            "Tipo DTE 📄",
            options=df['tipo'].unique().tolist(),
            default=df['tipo'].unique().tolist()
        )

    df_filtrado = df.copy()
    if busqueda:
        t_bus = busqueda.upper()
        mask = (
            df_filtrado['nom_prov'].str.contains(t_bus, case=False, na=False) |
            df_filtrado['nit_prov'].str.contains(t_bus, na=False)             |
            df_filtrado['dui_prov'].str.contains(t_bus, na=False)             |
            df_filtrado['gen'].str.contains(t_bus, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask]
    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]

    st.divider()
    tab1, tab2 = st.tabs(["📊 Libro F-07 Compras", "🔍 Auditoría Completa"])

    with tab1:
        df_f07 = pd.DataFrame()
        df_f07["A. Fecha Emisión"]        = df_filtrado["fecha"]
        df_f07["B. Clase"]                = "4"
        df_f07["C. Tipo Doc"]             = df_filtrado["tipo"]
        df_f07["D. Num Documento"]        = df_filtrado["gen"]
        df_f07["E. NIT/NRC Prov"]         = df_filtrado["nit_prov"]
        df_f07["F. Nombre Prov"]          = df_filtrado["nom_prov"]
        df_f07["G. Compra Ext/NS"]        = df_filtrado["exe"]
        df_f07["H. Internacion Ext/NS"]   = 0.00
        df_f07["I. Importacion Ext/NS"]   = 0.00
        df_f07["J. Compra Gravada"]       = df_filtrado["gra"]
        df_f07["K. Inter. Grav Bienes"]   = 0.00
        df_f07["L. Impor. Grav Bienes"]   = 0.00
        df_f07["M. Impor. Grav Serv"]     = 0.00
        df_f07["N. Crédito Fiscal (IVA)"] = df_filtrado["iva"]
        df_f07["O. Total Compras"]        = df_filtrado["tot"]
        df_f07["P. DUI Prov"]             = df_filtrado["dui_prov"]
        df_f07["Q. Tipo Operacion"]       = "1"
        df_f07["R. Clasificacion"]        = "1"
        df_f07["S. Sector"]               = "1"
        df_f07["T. Tipo Costo/Gasto"]     = "1"
        df_f07["U. Num Anexo"]            = "3"

        COLS_NUM = [c for c in df_f07.columns if df_f07[c].dtype == float]
        st.dataframe(
            df_f07.style.format({c: "{:.2f}" for c in COLS_NUM}),
            hide_index=True,
            use_container_width=True
        )

        # ── Totales dinámicos — solo columnas con suma > 0 ────
        ETIQUETAS_CORTAS = {
            "G. Compra Ext/NS"       : "Exentas/NS",
            "H. Internacion Ext/NS"  : "Intern. Ext",
            "I. Importacion Ext/NS"  : "Import. Ext",
            "J. Compra Gravada"      : "Gravadas",
            "K. Inter. Grav Bienes"  : "Intern. Grav",
            "L. Impor. Grav Bienes"  : "Import. Grav B",
            "M. Impor. Grav Serv"    : "Import. Grav S",
            "N. Crédito Fiscal (IVA)": "IVA",
            "O. Total Compras"       : "Total General",
        }
        partes_resumen = []
        for col_key, etiqueta in ETIQUETAS_CORTAS.items():
            if col_key in df_f07.columns:
                suma = df_f07[col_key].sum()
                if suma > 0:
                    if col_key == "O. Total Compras":
                        partes_resumen.append(f"**🟢 {etiqueta}:** `${suma:,.2f}`")
                    else:
                        partes_resumen.append(f"**{etiqueta}:** `${suma:,.2f}`")

        if partes_resumen:
            st.markdown("> " + " &nbsp;|&nbsp; ".join(partes_resumen))
        else:
            st.markdown("> *Sin montos registrados.*")

        st.markdown("---")
        if st.button("📥 Generar Excel para Hacienda", type="primary"):
            ventana_descarga_compras(
                df_f07,
                f"F07_Compras_{safe_str(cliente.get('nombre','')).replace(' ','_')}.xlsx"
            )

    with tab2:
        st.write(f"📊 Registros: **{len(df_filtrado)}** de **{len(df)}**")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

else:
    st.markdown("""
    <div style="text-align:center; padding:60px 20px; color:#6B7A2A;">
        <h3 style="color:#8A9A35 !important;">📂 Sin documentos cargados</h3>
        <p style="color:#4A5520 !important;">
            Usa el panel lateral para cargar y procesar PDFs de compras.
        </p>
    </div>
    """, unsafe_allow_html=True)
