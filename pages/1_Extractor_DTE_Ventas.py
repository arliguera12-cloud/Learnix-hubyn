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
st.set_page_config(page_title="Extractor DTE · Ventas", layout="wide", page_icon="📋")

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
  div[data-testid="stAlert"] { display: flex; align-items: center; min-height: 56px; }
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
  .resumen-box {
    background-color: #1A2008; border: 1px solid #4A5520;
    border-radius: 8px; padding: 14px 20px; margin: 12px 0;
    font-size: 14px; line-height: 2;
  }
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
    st.warning("Debes seleccionar un Cliente Activo en el Dashboard.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. CONSTANTES
# ─────────────────────────────────────────────
MAX_VALORES_LOOP = 30

PALABRAS_BASURA_NOMBRE = [
    "DOCUMENTO", "TRIBUTARIO", "ELECTRONICO", "ELECTRÓNICO",
    "REPRESENTACIÓN", "REPRESENTACION", "EMISOR", "FACTURA",
    "CONSUMIDOR", "COMPROBANTE", "CODIGO", "CÓDIGO", "SELLO",
    "VERSION", "VERSIÓN", "TRANSMISION", "TRANSMISIÓN",
    "MINISTERIO", "HACIENDA", "MUNICIPIO", "ACTIVIDAD",
    "ECONOMICA", "AGENCIA", "EFECTIVO", "HORA", "EMISIÓN",
    "EMISION", "GENERACIÓN", "GENERACION", "TELÉFONO",
    "TELEFONO", "TIPO ESTABLECIMIENTO", "ESTABLECIMIENTO",
    "CASA MATRIZ", "SUCURSAL:", "NIT:", "NRC:",
    "NUMERO DE CONTROL", "NÚMERO DE CONTROL",
    "MODELO DE FACTURACION", "TIPO DE TRANSMISION",
]
BASURA_ESTRICTA = ["@", "EMAIL", "CORREO", ".COM", "WWW.", "HTTP"]
PREFIJOS_DIRECCION = (
    "KM ", "KM.", "AV.", "AV ", "AVENIDA", "CALLE ", "PASAJE",
    "COLONIA", "COL.", "COL ", "URB.", "URB ", "URBANIZACION",
    "URBANIZACIÓN", "RESIDENCIAL", "LOTIFICACION", "BARRIO",
    "CANTON", "CANTÓN", "CARRETERA", "CARR.", "BULEVAR",
    "BOULEVARD", "BLVD", "POLIGONO", "POLÍGONO", "LOCAL ",
    "NIVEL ", "PISO ", "EDIFICIO", "CENTRO COMERCIAL",
    "COMPLEJO", "PARQUE INDUSTRIAL", "FINAL ", "ENTRE ", "#",
)
PALABRAS_COMERCIALES = [
    "S.A.", "S.A.S.", "SA DE", "C.V.", "LTDA.", "LTDA",
    "SOCIEDAD", "DISTRIBUIDORA", "FARMACIA", "GRUPO",
    "LABORATORIOS", "INDUSTRIAS", "SERVICIOS", "COMERCIAL",
    "IMPORTADORA", "EXPORTADORA", "CONSTRUCTORA", "CONSULTORES",
    "CONSULTORA", "INVERSIONES", "ALIMENTOS", "TECNOLOGIA",
    "CLINICA", "HOSPITAL", "SUPERMERCADO", "FERRETERIA",
]
NOMBRES_INVALIDOS = {
    "MATRIZ", "LOCAL", "SUCURSAL", "AGENCIA", "OFICINA",
    "ESTABLECIMIENTO", "PUNTO DE VENTA", "TIENDA", "ALMACEN",
    "ALMACÉN", "BODEGA", "CONTRIBUYENTE", "DATOS", "RECEPTOR",
    "CLIENTE", "ADQUIRIENTE",
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
    return "" if val is None else str(val)


def safe_extract_text(page, layout: bool = False) -> str:
    try:
        return safe_str(page.extract_text(layout=layout))
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
def cargar_clientes_json() -> dict:
    """Carga directorio de clientes/receptores conocidos."""
    for ruta in ("data/clientes.json", "data/proveedores.json"):
        if os.path.exists(ruta):
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, str):
                        data[k] = {"nombre": v, "nrc": ""}
                return data
            except Exception:
                pass
    return {}


def guardar_cliente_rapido(nit: str, nombre: str) -> None:
    if not nit or not safe_str(nombre).strip():
        return
    ruta = "data/clientes.json"
    if not os.path.exists("data"):
        os.makedirs("data")
    db = cargar_clientes_json()
    db[nit] = {"nombre": safe_str(nombre).strip().upper(),
               "nrc": db.get(nit, {}).get("nrc", "")}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)


def actualizar_nombre_en_db_ventas(nit: str, nombre: str) -> None:
    if not nit or not safe_str(nombre).strip():
        return
    df = st.session_state.get("db_ventas", pd.DataFrame())
    if df.empty or "nit_cli" not in df.columns:
        return
    mask = df["nit_cli"] == nit
    if mask.any():
        st.session_state.db_ventas.loc[mask, "nom_cli"] = safe_str(nombre).strip().upper()


def limpiar_monto(monto_str) -> float:
    try:
        s = re.sub(r'[^\d.,]', '', safe_str(monto_str).strip())
        if not s:
            return 0.0
        uc, up = s.rfind(','), s.rfind('.')
        if uc > up:
            s = s.replace('.', '').replace(',', '.')
        elif up > uc:
            s = s.replace(',', '')
        else:
            s = s.replace(',', '').replace('.', '')
        return float(s)
    except Exception:
        return 0.0


def extraer_y_formatear_fecha(texto: str) -> str:
    try:
        texto = safe_str(texto)
        m = re.search(
            r"\b(20[2-3]\d)\s*[-\/]\s*(0[1-9]|1[0-2])\s*[-\/]\s*([0-2]\d|3[01])\b",
            texto
        )
        if m:
            return f"{int(m.group(3)):02d}/{int(m.group(2)):02d}/{m.group(1)}"
        m = re.search(
            r"(?:FECHA\s*(?:DE\s*)?(?:EMISI[OÓ]N|GENERACI[OÓ]N)?)"
            r"[^\d]{0,20}(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})",
            texto, re.I
        )
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if d <= 12 and mo > 12:
                d, mo = mo, d
            if mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}"
        m = re.search(
            r"\b(\d{1,2})\s*[\/\-\.]\s*(\d{1,2})\s*[\/\-\.]\s*(20[2-3]\d)\b",
            texto
        )
        if m:
            p1, p2, y = int(m.group(1)), int(m.group(2)), m.group(3)
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
# FIX: EXTRACCIÓN DE NOMBRE DEL RECEPTOR/CLIENTE
# Se borra activamente el nombre del emisor para evitar fusiones
# ══════════════════════════════════════════════════════════════
def extraer_nombre_receptor(texto_completo: str, pos_nit: int, cliente_activo: dict) -> str:
    texto_completo = safe_str(texto_completo)
    nombre_emisor = safe_str(cliente_activo.get('nombre', '')).strip().upper()
    partes_emisor = [p for p in nombre_emisor.split()[:4] if len(p) > 3]

    def limpiar(s: str) -> str:
        try:
            s = safe_str(s)
            # 1. Neutralizar la fusión borrando el nombre exacto del emisor si se coló
            if nombre_emisor and len(nombre_emisor) > 3:
                s = re.compile(re.escape(nombre_emisor), re.I).sub("", s)
            
            # 2. Si se pegaron las etiquetas (ej. NOMBRE O RAZON SOCIAL: DANIEL SORTO), tomar la última parte
            s = re.split(r"(?i)(?:NOMBRE\s+O\s+RAZ[OÓ]N\s+SOCIAL|RAZ[OÓ]N\s+SOCIAL|CLIENTE)\s*[:\-]*\s*", s)[-1]
            
            s = re.sub(
                r"^[\s\-:]*(?:NOMBRE(?:\s+O\s+RAZ[OÓ]N\s+SOCIAL)?|"
                r"NOMBRE\s+COMERCIAL|RECEPTOR|ADQUIRIENTE|DATOS\s+DEL\s+RECEPTOR|"
                r"DATOS\s+DEL\s+ADQUIRIENTE|NOMBRE\s+DEL\s+CLIENTE|"
                r"CONTRIBUYENTE\s+RECEPTOR)[\s:]*",
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
            if len(T) < 3 or len(T) > 100:
                return False
            if nombre_emisor and (T == nombre_emisor or T.startswith(nombre_emisor[:15])):
                return False
            if any(b in T for b in BASURA_ESTRICTA):
                return False
            if es_linea_direccion(T):
                return False
            for b in PALABRAS_BASURA_NOMBRE:
                if b in T and len(b) > 5:
                    return False
            if T in NOMBRES_INVALIDOS:
                return False
            digitos = sum(c.isdigit() for c in T)
            if len(T) > 0 and digitos / len(T) > 0.45:
                return False
            if re.fullmatch(r'[\d\s\-\.\/]+', T):
                return False
            if not re.search(r'[A-ZÁÉÍÓÚÑÜ]', T):
                return False
            return True
        except Exception:
            return False

    try:
        inicio  = max(0, pos_nit - 600)
        fin     = min(len(texto_completo), pos_nit + 1500)
        ventana = texto_completo[inicio:fin]

        partes_rec = re.split(r"(?i)\bRECEPTOR\b", ventana, maxsplit=1)
        ventana_receptor = partes_rec[1] if len(partes_rec) > 1 else ventana

        patron_etq = re.compile(
            r"(?:Nombre(?:\s+[Oo]\s+[Rr]az[oó]n\s+[Ss]ocial)?|"
            r"[Rr]az[oó]n\s+[Ss]ocial|Nombre\s+[Cc]omercial|"
            r"Nombre\s+del\s+[Cc]liente|Nombre\s+del\s+[Rr]eceptor|"
            r"Nombre\s+del\s+[Aa]dquiriente|[Aa]dquiriente|[Rr]eceptor)"
            r"\s*[:\s]+\s*([^\n]{3,90}(?:\n[^\n]{3,60})?)",
            re.I
        )
        for m_etq in patron_etq.finditer(ventana_receptor):
            raw_cap = safe_str(m_etq.group(1))
            lineas_cap = raw_cap.split('\n')
            candidato  = limpiar(lineas_cap[0])
            if len(candidato) < 4 and len(lineas_cap) > 1:
                candidato = limpiar(lineas_cap[0] + " " + lineas_cap[1])
            if valido(candidato):
                return candidato

        ventana_despues = texto_completo[pos_nit:fin]
        lineas_despues  = [ln.strip() for ln in ventana_despues.split('\n') if ln.strip()]
        for linea in lineas_despues[:15]:
            candidato = limpiar(linea)
            if valido(candidato):
                return candidato

        ventana_antes = texto_completo[inicio:pos_nit]
        lineas_antes  = [ln.strip() for ln in ventana_antes.split('\n') if ln.strip()]
        for linea in reversed(lineas_antes[-15:]):
            candidato = limpiar(linea)
            if valido(candidato):
                return candidato

        m_sec = re.search(
            r"(?i)(?:DATOS\s+DEL\s+(?:RECEPTOR|ADQUIRIENTE|CLIENTE)|"
            r"RECEPTOR\s*[:\-]|ADQUIRIENTE\s*[:\-]|CLIENTE\s*:)"
            r"(.{10,800}?)(?:DESCRIPCI[OÓ]N|DETALLE|CANT\.|CANTIDAD|"
            r"PRECIO|COD\.|ARTICULO|ITEM\b|\n\s*\n)",
            texto_completo, re.S | re.I
        )
        if m_sec:
            seccion = safe_str(m_sec.group(1))
            for linea in seccion.split('\n'):
                candidato = limpiar(linea.strip())
                if valido(candidato):
                    return candidato

    except Exception:
        pass
    return ""


# ══════════════════════════════════════════════════════════════
# FIX: EXTRACTOR PRINCIPAL DE VENTAS — v3
# Agregada extracción del Sello de Recepción (Serie)
# ══════════════════════════════════════════════════════════════
def extraer_venta_nativo_pro(file_bytes: bytes, cliente_activo: dict) -> dict:

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

        t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
        t_no_sp = re.sub(r'\s+', '', t_clean).upper()

        tipo   = "01"
        ctrl   = ""
        num_control = ""

        m_ctrl = re.search(
            r"\b(DTE-\d{2}-[A-Z0-9]{1,20}-\d{12,18})\b",
            t_clean, re.I
        )
        if not m_ctrl:
            m_ctrl = re.search(
                r"(DTE-\d{2}-[A-Z0-9]{1,20}-\d{12,18})(?=[^0-9]|$)",
                t_no_sp
            )

        if m_ctrl:
            ctrl   = m_ctrl.group(1).upper()
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo:
                tipo = m_tipo.group(1)
            num_control = ctrl

        if not ctrl:
            return {"error_tipo": "No se detecto un Numero de Control DTE valido."}

        tipos_validos = ("01", "03", "05", "06")
        if tipo not in tipos_validos:
            return {"error_tipo": f"Documento DTE-{tipo}. Solo se admiten 01, 03, 05 y 06."}

        # ── Sello de Recepción (40 caracteres alfanuméricos) ────────────────
        sello = ""
        m_sello = re.search(r"\b(20[2-3]\d[A-Z0-9]{36})\b", t_no_sp)
        if m_sello:
            sello = m_sello.group(1)

        # ── Código de Generación / UUID ──────────────────────────────────────
        gen = ""
        m_gen_etq = re.search(
            r"C[oó]digo\s+de\s+Generaci[oó]n\s*:\s*"
            r"([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})",
            t_clean, re.I
        )
        if m_gen_etq:
            gen = safe_str(m_gen_etq.group(1)).upper()

        if not gen:
            m_url = re.search(r"CODGEN=([A-F0-9\-]{36})", t_no_sp)
            if m_url:
                gen = safe_str(m_url.group(1)).upper()

        if not gen:
            m_uuid = re.search(
                r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
                t_no_sp
            )
            if m_uuid:
                raw = safe_str(m_uuid.group(1)).replace("-", "")
                if len(raw) == 32:
                    gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}".upper()

        fecha = extraer_y_formatear_fecha(t_clean)

        # ── EXCLUSIONES ESTRICTAS DEL EMISOR (CLIENTE ACTIVO) ─────────────────
        nit_emisor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nit', '')))
        dui_emisor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('dui', '')))
        nrc_emisor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nrc', '')))
        excluir_numeros = {nit_emisor, dui_emisor, nrc_emisor} - {""}

        # ── NIT/DUI del RECEPTOR ──────────────────────────────────────────────
        nit_cli       = ""
        dui_cli       = ""
        nom_cli       = "SIN NOMBRE"
        es_nuevo      = True
        pos_nit_rec   = -1
        clientes_db   = cargar_clientes_json()

        partes_doc = re.split(
            r"(?i)\b(?:DATOS\s+DEL\s+RECEPTOR|RECEPTOR\s*[:\-]|"
            r"DATOS\s+DEL\s+ADQUIRIENTE|ADQUIRIENTE\s*[:\-]|"
            r"DATOS\s+DEL\s+CLIENTE|CLIENTE\s*:|COMPRADOR\b)\b",
            texto_completo, maxsplit=1
        )

        texto_receptor = ""
        offset_receptor = 0

        if len(partes_doc) >= 2:
            texto_receptor_raw = partes_doc[1]
            corte_det = re.search(
                r"(?i)(?:DESCRIPCI[OÓ]N|CANT\.|CANTIDAD|PRECIO|COD\.|"
                r"ARTICULO|ITEM\b|DETALLE\b|\n\s*\n)",
                texto_receptor_raw
            )
            texto_receptor = texto_receptor_raw[:corte_det.start()] if corte_det else texto_receptor_raw[:1500]
            offset_receptor = texto_completo.find(texto_receptor[:50])
            if offset_receptor == -1: offset_receptor = len(partes_doc[0])
        else:
            m_rec_lineal = re.search(r"(?i)\bRECEPTOR\b", texto_lineal)
            if m_rec_lineal:
                texto_receptor = texto_lineal[m_rec_lineal.start():][:1500]
                offset_receptor = texto_completo.find(texto_receptor[:50])
            else:
                offset_receptor = len(texto_completo) // 2
                texto_receptor = texto_completo[offset_receptor:][:1500]

        patron_universal = re.compile(
            r"\b(?:\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d" 
            r"|\d{14}"                                      
            r"|\d{8}[\s\-]?\d"                              
            r"|\d{9})\b"                                    
        )

        candidatos_validos = []
        for match in patron_universal.finditer(texto_completo):
            num_limpio = re.sub(r'[^0-9]', '', match.group(0))
            if num_limpio not in excluir_numeros and len(num_limpio) in (9, 14):
                candidatos_validos.append((num_limpio, match.start()))

        cands_en_receptor = [
            c for c in candidatos_validos 
            if offset_receptor <= c[1] <= (offset_receptor + len(texto_receptor) + 200)
        ]

        if cands_en_receptor:
            nit_cli, pos_nit_rec = cands_en_receptor[0]
        elif candidatos_validos:
            nit_cli, pos_nit_rec = candidatos_validos[0]

        if len(nit_cli) == 9:
            dui_cli = nit_cli

        if nit_cli and nit_cli in clientes_db:
            nom_cli  = safe_str(clientes_db[nit_cli].get("nombre", "SIN NOMBRE"))
            es_nuevo = False

        if es_nuevo and nit_cli:
            pos_busqueda = pos_nit_rec if pos_nit_rec >= 0 else len(texto_completo) // 2

            # Le pasamos el cliente_activo para que borre el nombre del emisor
            nombre_encontrado = extraer_nombre_receptor(
                texto_completo, pos_busqueda, cliente_activo
            )

            if not nombre_encontrado and texto_visual.strip():
                pos_vis = pos_nit_rec
                if pos_vis < 0:
                    m_crudo = re.search(re.escape(nit_cli[:8]), texto_visual)
                    pos_vis = m_crudo.start() if m_crudo else len(texto_visual) // 2
                nombre_encontrado = extraer_nombre_receptor(
                    texto_visual, pos_vis, cliente_activo
                )

            nom_cli = nombre_encontrado if nombre_encontrado else "SIN NOMBRE"

        exentas     = 0.0
        no_sujetas  = 0.0
        gravadas    = 0.0
        debito      = 0.0
        terceros    = 0.0
        deb_terc    = 0.0
        total       = 0.0
        iva_calc    = False

        m_exe = re.search(
            r"(?:Ventas?\s+Exentas?|Total\s+Exento|Exentas?)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_exe:
            exentas = limpiar_monto(m_exe.group(1))

        m_ns = re.search(
            r"(?:No\s+Sujetas?|Ventas?\s+No\s+Sujetas?)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_ns:
            no_sujetas = limpiar_monto(m_ns.group(1))

        for pat in [
            r"(?:TOTAL\s+A\s+PAGAR)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:MONTO\s+TOTAL\s+DE\s+LA\s+OPERACI[OÓ]N)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:TOTAL\s+A\s+PAGAR|TOTAL\s+PAGAR|MONTO\s+TOTAL)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:TOTAL\s+OPERACI[OÓ]N|VENTA\s+TOTAL|TOTAL\s*\$)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:VALOR\s+TOTAL|TOTAL\s+FACTURA)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
        ]:
            m_tot = re.search(pat, t_clean, re.I)
            if m_tot:
                total = limpiar_monto(m_tot.group(1))
                if total > 0:
                    break

        for pat in [
            r"(?:D[EÉ]BITO\s+FISCAL|Débito\s+Fiscal|Debito\s+Fiscal)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:Impuesto\s+al\s+Valor\s+Agregado\s*(?:13\s*%)?)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:IVA\s*13\s*%|13\s*%\s*IVA|I\.V\.A\.?)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
        ]:
            m_iva = re.search(pat, t_clean, re.I)
            if m_iva:
                debito = limpiar_monto(m_iva.group(1))
                if debito > 0:
                    break

        m_grav = re.search(
            r"(?:Ventas?\s+Gravadas?\s+Locales?|Subtotal\s+Gravado|"
            r"Ventas?\s+Gravadas?)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_grav:
            gravadas = limpiar_monto(m_grav.group(1))

        if gravadas == 0.0 and total > 0 and debito > 0:
            gravadas = round(total - debito - exentas - no_sujetas, 2)

        if gravadas == 0.0:
            m_sub = re.search(
                r"Sub[\s\-]?Total\s*:\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                t_clean, re.I
            )
            if m_sub:
                gravadas = limpiar_monto(m_sub.group(1))

        encontrado = total > 0 and debito > 0 and gravadas > 0

        if not encontrado:
            montos_raw = re.findall(
                r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                t_clean
            )
            set_montos = set()
            for rv in montos_raw:
                v = limpiar_monto(rv)
                if v > 0:
                    set_montos.add(v)
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
                            candidato_tot = round(vg + vi + exentas + no_sujetas, 2)
                            if abs(candidato_tot - round(vt, 2)) <= 0.10:
                                gravadas   = vg
                                debito     = vi
                                total      = vt
                                encontrado = True
                                break

        if not encontrado:
            if total > 0 and debito > 0 and gravadas == 0.0:
                gravadas   = round(total - debito - exentas - no_sujetas, 2)
                encontrado = True
            elif total > 0 and debito == 0.0 and gravadas == 0.0 and tipo == "03":
                gravadas  = round((total - exentas - no_sujetas) / 1.13, 2)
                debito    = round(total - exentas - no_sujetas - gravadas, 2)
                iva_calc  = True
                encontrado = True
            elif total == 0.0 and gravadas > 0 and debito > 0:
                total = round(gravadas + debito + exentas + no_sujetas, 2)

        return {
            "fecha"      : fecha,
            "tipo"       : tipo,
            "num_control": num_control,
            "sello"      : sello,
            "gen"        : gen,
            "nit_cli"    : nit_cli,
            "dui_cli"    : dui_cli,
            "nom_cli"    : nom_cli,
            "exentas"    : round(exentas, 2),
            "no_sujetas" : round(no_sujetas, 2),
            "gravadas"   : round(gravadas, 2),
            "debito"     : round(debito, 2),
            "terceros"   : round(terceros, 2),
            "deb_terc"   : round(deb_terc, 2),
            "total"      : round(total, 2),
            "estado"     : "OK",
            "iva_calc"   : iva_calc,
            "es_nuevo"   : es_nuevo,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
    except Exception as err:
        return {"error_extraccion": safe_str(err)}


# ─────────────────────────────────────────────
# EXPORTAR EXCEL F-07 VENTAS
# ─────────────────────────────────────────────
def to_excel_hacienda_ventas(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Ventas_F07')
        ws = writer.sheets['Ventas_F07']
        anchos = [12, 3, 3, 40, 45, 35, 12, 16, 45, 12, 12, 12, 12, 12, 12, 14, 14, 3, 3, 4]
        for idx_col, ancho in enumerate(anchos, start=1):
            col_letter = ws.cell(1, idx_col).column_letter
            ws.column_dimensions[col_letter].width = ancho
        for fila in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=10, max_col=16):
            for celda in fila:
                if isinstance(celda.value, (int, float)):
                    celda.number_format = '#,##0.00'
    return output.getvalue()


def construir_df_f07_ventas(df_filtrado: pd.DataFrame) -> pd.DataFrame:
    df_out = pd.DataFrame()
    df_out["A. Fecha Emisión"]           = df_filtrado["fecha"]
    df_out["B. Clase Doc"]               = "4"
    df_out["C. Tipo Doc"]                = df_filtrado["tipo"]
    # Se eliminan guiones del número de control para cumplir el Anexo
    df_out["D. Num Resolución (Control)"]= df_filtrado["num_control"].astype(str).str.replace("-", "", regex=False)
    # Se inserta el sello de recepción en la Serie
    df_out["E. Serie"]                   = df_filtrado.get("sello", "")
    # Se eliminan guiones del código de generación para cumplir el Anexo
    df_out["F. Num Documento"]           = df_filtrado["gen"].astype(str).str.replace("-", "", regex=False)
    df_out["G. Control Interno"]         = ""
    df_out["H. NIT/NRC Cliente"]         = df_filtrado["nit_cli"]
    df_out["I. Nombre Cliente"]          = df_filtrado["nom_cli"]
    df_out["J. Ventas Exentas"]          = df_filtrado["exentas"]
    df_out["K. Ventas No Sujetas"]       = df_filtrado["no_sujetas"]
    df_out["L. Ventas Gravadas"]         = df_filtrado["gravadas"]
    df_out["M. Débito Fiscal"]           = df_filtrado["debito"]
    df_out["N. Vtas Cuenta Terceros"]    = df_filtrado["terceros"]
    df_out["O. Déb. Fiscal Terceros"]    = df_filtrado["deb_terc"]
    df_out["P. Total Ventas"]            = df_filtrado["total"]
    df_out["Q. DUI Cliente"]             = df_filtrado["dui_cli"]
    df_out["R. Tipo Operación"]          = "1"
    df_out["S. Tipo Ingreso"]            = "1"
    df_out["T. Num Anexo"]               = "2"
    return df_out


@st.dialog("Seguro de Calidad de Ventas")
def ventana_descarga_ventas(df_resultados: pd.DataFrame, nombre_archivo: str) -> None:
    st.write(
        "Asegurate de haber procesado únicamente los comprobantes que deseas "
        "declarar en el anexo de Ventas antes de descargar."
    )
    st.download_button(
        "📥 Confirmar y Descargar Anexo F-07",
        data=to_excel_hacienda_ventas(df_resultados),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )


# ─────────────────────────────────────────────
# HELPERS UI
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


def datos_revision_vacio_ventas(causa: str = "") -> dict:
    return {
        "fecha"      : "",
        "tipo"       : "03",
        "num_control": "",
        "sello"      : "",
        "gen"        : "",
        "nit_cli"    : "",
        "dui_cli"    : "",
        "nom_cli"    : "",
        "exentas"    : 0.0,
        "no_sujetas" : 0.0,
        "gravadas"   : 0.0,
        "debito"     : 0.0,
        "terceros"   : 0.0,
        "deb_terc"   : 0.0,
        "total"      : 0.0,
        "estado"     : "REVISION",
        "iva_calc"   : False,
        "es_nuevo"   : True,
        "_error"     : safe_str(causa),
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
    st.title("📋 Extractor DTE — Ventas")

st.markdown(f"""
<div class="card-emisor">
    <strong>EMISOR ACTIVO:</strong> {safe_str(cliente.get('nombre',''))}<br>
    <strong>NIT:</strong> {safe_str(cliente.get('nit',''))}
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 8. SESSION STATE
# ─────────────────────────────────────────────
if 'cola_revision_v'  not in st.session_state: st.session_state.cola_revision_v  = []
if 'ventas_uploader'  not in st.session_state: st.session_state.ventas_uploader  = 0
if 'db_ventas'        not in st.session_state: st.session_state.db_ventas        = pd.DataFrame()
if 'archivos_ventas'  not in st.session_state: st.session_state.archivos_ventas  = []
if 'reporte_ventas'   not in st.session_state: st.session_state.reporte_ventas   = None

# ─────────────────────────────────────────────
# 9. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga de Ventas")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra CCF o Facturas (PDF)",
        type="pdf",
        accept_multiple_files=True,
        key=str(st.session_state.ventas_uploader)
    )

    procesar = st.button(
        "🚀 Procesar Ventas",
        type="primary",
        use_container_width=True,
        disabled=not archivos
    )

    if procesar and archivos:
        ya_procesados  = set(st.session_state.archivos_ventas)
        nuevos         = [f for f in archivos if f.name not in ya_procesados]

        if not nuevos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            extracted, duplicados, iva_calc_files      = [], [], []
            invalidos, corruptos, nuevos_clientes_d    = [], [], {}

            bar          = st.progress(0)
            txt_progreso = st.empty()
            t_inicio     = time.time()
            total        = len(nuevos)

            for idx, f in enumerate(nuevos):
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
                    st.session_state.archivos_ventas.append(f.name)
                    bar.progress((idx + 1) / total)
                    continue

                res = extraer_venta_nativo_pro(file_bytes, cliente)

                cod_gen     = safe_str(res.get('gen', ''))
                num_ctrl    = safe_str(res.get('num_control', ''))
                dup_id      = cod_gen or num_ctrl

                dup_memoria = (
                    not st.session_state.db_ventas.empty
                    and dup_id
                    and 'gen' in st.session_state.db_ventas.columns
                    and (
                        (st.session_state.db_ventas['gen'] == cod_gen).any()
                        if cod_gen else
                        (st.session_state.db_ventas['num_control'] == num_ctrl).any()
                        if num_ctrl else False
                    )
                )
                dup_lote = dup_id and any(
                    (d.get('gen') == cod_gen and cod_gen)
                    or (d.get('num_control') == num_ctrl and num_ctrl)
                    for d in extracted
                )

                if "error_tipo" in res:
                    invalidos.append(f.name)

                elif dup_memoria or dup_lote:
                    duplicados.append(f.name)

                elif "error_fatal" in res:
                    corruptos.append(f.name)

                elif "error_extraccion" in res:
                    st.session_state.cola_revision_v.append({
                        "archivo": f.name,
                        "bytes"  : file_bytes,
                        "datos"  : datos_revision_vacio_ventas(res["error_extraccion"]),
                    })

                else:
                    nom_res = safe_str(res.get('nom_cli', '')).strip()
                    va_revision = (
                        res.get('total', 0.0) == 0.0
                        or not res.get('num_control')
                        or not safe_str(res.get('fecha', '')).strip()
                        or nom_res in ("SIN NOMBRE", "")
                    )
                    if va_revision:
                        st.session_state.cola_revision_v.append({
                            "archivo": f.name,
                            "bytes"  : file_bytes,
                            "datos"  : res,
                        })
                    else:
                        if res.get('iva_calc'):
                            iva_calc_files.append(f.name)
                        if res.get("es_nuevo") and res.get("nit_cli"):
                            nit_n = res["nit_cli"]
                            nom_n = res["nom_cli"]
                            nuevos_clientes_d[nit_n] = nom_n
                            guardar_cliente_rapido(nit_n, nom_n)
                        res["archivo"] = f.name
                        extracted.append(res)

                st.session_state.archivos_ventas.append(f.name)
                bar.progress((idx + 1) / total)

            txt_progreso.success(f"✅ {total} documentos escaneados.")

            st.session_state.reporte_ventas = {
                "invalidos"       : invalidos,
                "duplicados"      : duplicados,
                "iva_calc"        : iva_calc_files,
                "nuevos_clientes" : nuevos_clientes_d,
                "corruptos"       : corruptos,
            }

            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_ventas.empty:
                    st.session_state.db_ventas = new_df
                else:
                    st.session_state.db_ventas = pd.concat(
                        [st.session_state.db_ventas, new_df], ignore_index=True
                    )

    st.divider()
    if st.button("🧹 Limpiar Memoria Ventas", type="secondary", use_container_width=True):
        for key in ('db_ventas','archivos_ventas','reporte_ventas','cola_revision_v'):
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.ventas_uploader = st.session_state.get('ventas_uploader', 0) + 1
        st.rerun()

    if not st.session_state.db_ventas.empty:
        st.divider()
        st.markdown(f"**📄 Documentos:** `{len(st.session_state.db_ventas)}`")
        st.markdown(f"**💰 Total:** `${st.session_state.db_ventas['total'].sum():,.2f}`")

# ─────────────────────────────────────────────
# 10. BANDEJA DE REVISIÓN MANUAL
# ─────────────────────────────────────────────
if st.session_state.cola_revision_v:
    st.markdown("""
    <div class="inbox-revision">
        <h3>📥 Bandeja de Revisión Manual</h3>
        <p>Datos incompletos o fallo de extracción. Revisa y corrige antes de agregar al libro.</p>
    </div>
    """, unsafe_allow_html=True)

    total_cola  = len(st.session_state.cola_revision_v)

    col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
    with col_nav2:
        st.info(f"📄 Documento **1 de {total_cola}** en revisión | Quedan **{total_cola}** por revisar")

    with st.expander("🗑️ Gestión masiva de cola"):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("🗑️ Descartar TODOS los pendientes", type="secondary", use_container_width=True):
                st.session_state.cola_revision_v = []
                st.rerun()
        with col_m2:
            st.caption(f"Total en cola: {total_cola} documentos")

    item_actual = st.session_state.cola_revision_v[0]
    datos_act   = item_actual["datos"]

    st.divider()

    col_img, col_form = st.columns([1.2, 1], gap="large")

    with col_img:
        try:
            with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                img = pdf.pages[0].to_image(resolution=200).original
                st.image(img, caption=item_actual['archivo'], use_container_width=True)
                texto_crudo = ""
                for page in pdf.pages:
                    texto_crudo += safe_extract_text(page, layout=True) + "\n"

                with st.expander("🔍 Datos extraídos automáticamente"):
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.caption(f"**Num Control:** `{datos_act.get('num_control','—')}`")
                        st.caption(f"**UUID:** `{datos_act.get('gen','—')}`")
                        st.caption(f"**Sello:** `{datos_act.get('sello','—')}`")
                        st.caption(f"**Fecha:** `{datos_act.get('fecha','—')}`")
                        st.caption(f"**NIT receptor:** `{datos_act.get('nit_cli','—')}`")
                    with col_d2:
                        st.caption(f"**Nombre:** `{datos_act.get('nom_cli','—')}`")
                        st.caption(f"**Total:** `${datos_act.get('total',0):.2f}`")
                        st.caption(f"**Gravadas:** `${datos_act.get('gravadas',0):.2f}`")
                        st.caption(f"**Débito:** `${datos_act.get('debito',0):.2f}`")

                st.markdown("**📝 Texto extraído del PDF:**")
                st.text_area("", value=texto_crudo.strip(),
                             height=220, label_visibility="collapsed")
        except Exception as ex_prev:
            st.error(f"No se pudo cargar la vista previa: {safe_str(ex_prev)}")

    with col_form:
        st.markdown("### ✍️ Corrección Manual")

        error_causa = safe_str(datos_act.get("_error", ""))
        if error_causa:
            st.warning(f"⚠️ **Causa del fallo:** `{error_causa}`")

        nit_actual = safe_str(datos_act.get("nit_cli", ""))
        if nit_actual:
            st.info(f"🆔 NIT receptor detectado: `{nit_actual}`")

        campos_faltantes = []
        if not safe_str(datos_act.get("fecha","")).strip():      campos_faltantes.append("Fecha")
        if not safe_str(datos_act.get("num_control","")).strip(): campos_faltantes.append("Núm. Control")
        if datos_act.get("nom_cli","") in ("SIN NOMBRE",""):     campos_faltantes.append("Nombre cliente")
        if datos_act.get("total", 0.0) == 0.0:                   campos_faltantes.append("Total")
        if campos_faltantes:
            st.error(f"❌ Campos requeridos: **{', '.join(campos_faltantes)}**")

        with st.form(key=f"form_rev_v_{item_actual['archivo']}"):
            st.markdown("**📋 Identificación del documento**")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_fecha = st.text_input(
                    "📅 Fecha (DD/MM/YYYY) *",
                    value=safe_str(datos_act.get("fecha", "")),
                    placeholder="13/03/2026"
                )
                f_tipo = st.selectbox(
                    "📄 Tipo DTE",
                    options=["03", "01", "05", "06"],
                    index=["03","01","05","06"].index(safe_str(datos_act.get("tipo","03")))
                          if safe_str(datos_act.get("tipo","03")) in ["03","01","05","06"] else 0
                )
            with col_f2:
                f_ctrl = st.text_input(
                    "🔢 Número de Control DTE *",
                    value=safe_str(datos_act.get("num_control", "")),
                    placeholder="DTE-03-M001P001-000000000000033"
                )
                f_gen = st.text_input(
                    "🔑 UUID / Código de Generación",
                    value=safe_str(datos_act.get("gen", "")),
                    placeholder="25AA41EA-0412-40BC-803D-405272AC7891"
                )
                
            f_sello = st.text_input(
                "🛡️ Sello de Recepción (Serie)",
                value=safe_str(datos_act.get("sello", "")),
                placeholder="20261A71A6D9E53A4BE59631B7BED69D231B6PHP"
            )

            st.markdown("**🏢 Receptor / Cliente**")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                f_nit = st.text_input(
                    "🆔 NIT del Cliente",
                    value=safe_str(datos_act.get("nit_cli", "")),
                    placeholder="12172810871033"
                )
            with col_r2:
                f_dui = st.text_input(
                    "🪪 DUI del Cliente",
                    value=safe_str(datos_act.get("dui_cli", "")),
                    placeholder="Solo si es persona natural"
                )

            nom_sug = safe_str(datos_act.get("nom_cli", ""))
            if nom_sug in ("SIN NOMBRE", ""):
                nom_sug = ""
            f_nom = st.text_input(
                "🏢 Nombre / Razón Social del Cliente *",
                value=nom_sug,
                placeholder="JONATHAN NEFTALI RIVAS HERRERA"
            )

            st.markdown("**💰 Montos**")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                f_total = st.number_input(
                    "💰 Total a Pagar ($) *",
                    value=float(datos_act.get("total", 0.0)),
                    format="%.2f", min_value=0.0
                )
            with col_m2:
                f_gravadas = st.number_input(
                    "🧾 Ventas Gravadas ($)",
                    value=float(datos_act.get("gravadas", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Dejar en 0 para calcular automáticamente"
                )
            with col_m3:
                f_debito = st.number_input(
                    "🏦 Débito Fiscal ($)",
                    value=float(datos_act.get("debito", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Dejar en 0 para calcular automáticamente"
                )

            col_m4, col_m5 = st.columns(2)
            with col_m4:
                f_exentas = st.number_input(
                    "🔹 Ventas Exentas ($)",
                    value=float(datos_act.get("exentas", 0.0)),
                    format="%.2f", min_value=0.0
                )
            with col_m5:
                f_no_sujetas = st.number_input(
                    "🔸 Ventas No Sujetas ($)",
                    value=float(datos_act.get("no_sujetas", 0.0)),
                    format="%.2f", min_value=0.0
                )

            if f_total > 0:
                grav_preview = f_gravadas if f_gravadas > 0 else round((f_total - f_exentas - f_no_sujetas) / 1.13, 2)
                deb_preview  = f_debito if f_debito > 0 else round(grav_preview * 0.13, 2)
                st.caption(
                    f"📊 Preview: Gravadas `${grav_preview:.2f}` | "
                    f"IVA `${deb_preview:.2f}` | "
                    f"Total `${f_total:.2f}`"
                )

            actualizar_otros = st.checkbox(
                "🔄 Actualizar nombre en registros existentes con este NIT", value=True
            )

            st.markdown("")
            b1, b2, b3 = st.columns([2, 1, 1])
            with b1:
                submit_ok  = st.form_submit_button(
                    "✅ Aprobar y Agregar al Libro",
                    type="primary",
                    use_container_width=True
                )
            with b2:
                submit_skip = st.form_submit_button(
                    "⏭️ Saltar",
                    use_container_width=True,
                    help="Mover al final de la cola"
                )
            with b3:
                submit_del = st.form_submit_button(
                    "🗑️ Descartar",
                    use_container_width=True
                )

            if submit_ok:
                errores = []
                if not f_fecha.strip():  errores.append("Fecha requerida.")
                if not f_ctrl.strip():   errores.append("Número de Control requerido.")
                if not f_nom.strip():    errores.append("Nombre del Cliente requerido.")
                if f_total <= 0:         errores.append("Total debe ser mayor a 0.")

                if f_fecha.strip() and not re.match(r'\d{2}/\d{2}/\d{4}', f_fecha.strip()):
                    errores.append("Formato de fecha inválido. Use DD/MM/YYYY.")

                if errores:
                    for e_msg in errores:
                        st.error(e_msg)
                else:
                    nombre_limpio = f_nom.strip().upper()
                    nit_act       = f_nit.strip() or safe_str(datos_act.get("nit_cli", ""))
                    dui_act       = f_dui.strip() or safe_str(datos_act.get("dui_cli", ""))

                    if nit_act:
                        guardar_cliente_rapido(nit_act, nombre_limpio)

                    for item_pend in st.session_state.cola_revision_v[1:]:
                        if item_pend["datos"].get("nit_cli") == nit_act:
                            item_pend["datos"]["nom_cli"] = nombre_limpio
                            item_pend["datos"]["es_nuevo"] = False

                    if actualizar_otros and nit_act:
                        actualizar_nombre_en_db_ventas(nit_act, nombre_limpio)

                    grav_f = f_gravadas
                    deb_f  = f_debito
                    ic     = datos_act.get("iva_calc", False)

                    if f_total > 0 and grav_f == 0.0 and deb_f == 0.0:
                        grav_f = round((f_total - f_exentas - f_no_sujetas) / 1.13, 2)
                        deb_f  = round(f_total - f_exentas - f_no_sujetas - grav_f, 2)
                        ic     = True
                    elif f_total > 0 and deb_f == 0.0 and grav_f > 0.0:
                        deb_f  = round(grav_f * 0.13, 2)
                        ic     = True

                    datos_act.update({
                        "fecha"      : f_fecha.strip(),
                        "tipo"       : f_tipo,
                        "num_control": f_ctrl.strip().upper(),
                        "sello"      : f_sello.strip().upper(),
                        "gen"        : f_gen.strip().upper(),
                        "nit_cli"    : nit_act,
                        "dui_cli"    : dui_act,
                        "nom_cli"    : nombre_limpio,
                        "total"      : f_total,
                        "exentas"    : f_exentas,
                        "no_sujetas" : f_no_sujetas,
                        "gravadas"   : grav_f,
                        "debito"     : deb_f,
                        "iva_calc"   : ic,
                        "es_nuevo"   : False,
                        "archivo"    : item_actual["archivo"],
                    })

                    nuevo_df = pd.DataFrame([datos_act])
                    if st.session_state.db_ventas.empty:
                        st.session_state.db_ventas = nuevo_df
                    else:
                        st.session_state.db_ventas = pd.concat(
                            [st.session_state.db_ventas, nuevo_df], ignore_index=True
                        )

                    if nit_act:
                        rep_act = st.session_state.get("reporte_ventas") or {}
                        nc_dict = rep_act.get("nuevos_clientes", {})
                        nc_dict[nit_act] = nombre_limpio
                        if st.session_state.reporte_ventas:
                            st.session_state.reporte_ventas["nuevos_clientes"] = nc_dict

                    st.session_state.cola_revision_v.pop(0)
                    st.success("✅ Documento aprobado y agregado al libro.")
                    st.rerun()

            if submit_skip:
                item = st.session_state.cola_revision_v.pop(0)
                st.session_state.cola_revision_v.append(item)
                st.rerun()

            if submit_del:
                st.session_state.cola_revision_v.pop(0)
                st.rerun()

    st.stop()

# ─────────────────────────────────────────────
# 11. REPORTE DE PROCESAMIENTO
# ─────────────────────────────────────────────
if st.session_state.reporte_ventas:
    rep = st.session_state.reporte_ventas
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

    nc_dict = rep.get("nuevos_clientes", {})
    if nc_dict:
        st.markdown(f"**🆕 Clientes nuevos guardados:** `{len(nc_dict)}`")
        with st.expander("Ver clientes nuevos registrados"):
            for nit_k, nom_k in nc_dict.items():
                st.markdown(f"- `{nit_k}` — **{nom_k}**")

    st.divider()

# ─────────────────────────────────────────────
# 12. TABLA PRINCIPAL Y EXPORT
# ─────────────────────────────────────────────
if not st.session_state.db_ventas.empty:
    df = st.session_state.db_ventas.copy()

    st.markdown("### 🔍 Filtros de Auditoría")
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("Buscar cliente 🔎",
                                 placeholder="Nombre, NIT, Num. Control o UUID…")
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
            df_filtrado['nom_cli'].str.contains(t_bus, case=False, na=False)  |
            df_filtrado['nit_cli'].str.contains(t_bus, na=False)              |
            df_filtrado['num_control'].str.contains(t_bus, case=False, na=False) |
            df_filtrado['gen'].str.contains(t_bus, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask]
    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]

    st.divider()

    df_ccf = df_filtrado[df_filtrado['tipo'] == '03'].copy()
    df_fac = df_filtrado[df_filtrado['tipo'] == '01'].copy()
    df_otro= df_filtrado[~df_filtrado['tipo'].isin(['01','03'])].copy()

    tab1, tab2, tab3 = st.tabs([
        "📊 Libro F-07 Ventas",
        "🔍 Auditoría Completa",
        "📈 Resumen por Tipo"
    ])

    with tab1:
        if not df_ccf.empty:
            st.markdown("#### 🧾 Ventas a Contribuyentes (CCF — DTE-03)")
            df_f07_ccf = construir_df_f07_ventas(df_ccf)
            COLS_NUM = [c for c in df_f07_ccf.columns if df_f07_ccf[c].dtype == float]
            st.dataframe(
                df_f07_ccf.style.format({c: "{:.2f}" for c in COLS_NUM}),
                hide_index=True, use_container_width=True
            )

        if not df_fac.empty:
            st.markdown("#### 🧾 Ventas a Consumidor Final (Facturas — DTE-01)")
            df_f07_fac = construir_df_f07_ventas(df_fac)
            COLS_NUM = [c for c in df_f07_fac.columns if df_f07_fac[c].dtype == float]
            st.dataframe(
                df_f07_fac.style.format({c: "{:.2f}" for c in COLS_NUM}),
                hide_index=True, use_container_width=True
            )

        if not df_otro.empty:
            st.markdown("#### 📄 Otros Documentos (NC/ND)")
            df_f07_otro = construir_df_f07_ventas(df_otro)
            COLS_NUM = [c for c in df_f07_otro.columns if df_f07_otro[c].dtype == float]
            st.dataframe(
                df_f07_otro.style.format({c: "{:.2f}" for c in COLS_NUM}),
                hide_index=True, use_container_width=True
            )

        df_f07_total = construir_df_f07_ventas(df_filtrado)
        ETIQUETAS = {
            "J. Ventas Exentas"      : "Exentas",
            "K. Ventas No Sujetas"   : "No Sujetas",
            "L. Ventas Gravadas"     : "Gravadas",
            "M. Débito Fiscal"       : "Débito Fiscal",
            "N. Vtas Cuenta Terceros": "Terceros",
            "O. Déb. Fiscal Terceros": "Déb. Terceros",
            "P. Total Ventas"        : "Total General",
        }
        partes = []
        for col_key, etiqueta in ETIQUETAS.items():
            if col_key in df_f07_total.columns:
                suma = df_f07_total[col_key].sum()
                if suma > 0:
                    if col_key == "P. Total Ventas":
                        partes.append(f"**🟢 {etiqueta}:** `${suma:,.2f}`")
                    else:
                        partes.append(f"**{etiqueta}:** `${suma:,.2f}`")

        if partes:
            st.markdown("> " + " &nbsp;|&nbsp; ".join(partes))
        else:
            st.markdown("> *Sin montos registrados.*")

        st.markdown("---")
        if st.button("📥 Generar Excel para Hacienda", type="primary"):
            ventana_descarga_ventas(
                df_f07_total,
                f"F07_Ventas_{safe_str(cliente.get('nombre','')).replace(' ','_')}.xlsx"
            )

    with tab2:
        st.write(f"📊 Registros: **{len(df_filtrado)}** de **{len(df)}**")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

    with tab3:
        if not df_filtrado.empty:
            resumen_tipo = df_filtrado.groupby('tipo').agg(
                Documentos=('total', 'count'),
                Exentas=('exentas', 'sum'),
                No_Sujetas=('no_sujetas', 'sum'),
                Gravadas=('gravadas', 'sum'),
                Debito_Fiscal=('debito', 'sum'),
                Total=('total', 'sum'),
            ).reset_index()
            resumen_tipo.columns = [
                'Tipo DTE', 'Docs', 'Exentas', 'No Sujetas',
                'Gravadas', 'Débito Fiscal', 'Total'
            ]
            COLS_NUM_R = ['Exentas','No Sujetas','Gravadas','Débito Fiscal','Total']
            st.dataframe(
                resumen_tipo.style.format({c: "${:,.2f}" for c in COLS_NUM_R}),
                hide_index=True, use_container_width=True
            )
        else:
            st.info("Sin datos para mostrar.")

else:
    st.markdown("""
    <div style="text-align:center; padding:60px 20px;">
        <h3 style="color:#8A9A35 !important;">📂 Sin documentos cargados</h3>
        <p style="color:#4A5520 !important;">
            Usa el panel lateral para cargar y procesar PDFs de ventas.
        </p>
    </div>
    """, unsafe_allow_html=True)
