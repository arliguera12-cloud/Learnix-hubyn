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
  div.stDownloadButton > button[kind="primary"] * { color:#FFFFFF !important; font-weight:bold !important; }
  div.stButton > button[kind="secondary"] {
    background-color : transparent !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important; transition: 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover { background-color:#1A2008 !important; }
  div.stButton > button[kind="secondary"] *     { color:#C8D87A !important; }
  div[data-testid="stTextInput"] input,
  div[data-testid="stNumberInput"] input {
    background-color:#1A2008 !important; border:1px solid #4A5520 !important;
    border-radius:6px !important; color:#F0EDD8 !important; caret-color:#C8D87A;
  }
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stNumberInput"] input:focus {
    border-color:#8A9A35 !important;
    box-shadow:0 0 0 2px rgba(138,154,53,0.25) !important;
  }
  button[data-baseweb="tab"] { color:#8A9A35 !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom:2px solid #8A9A35 !important; color:#F0EDD8 !important;
  }
  div[data-testid="stAlert"] { display:flex; align-items:center; min-height:56px; }
  hr { border-color:#4A5520 !important; opacity:0.4; }
  .card-emisor {
    padding:12px 16px; border-radius:8px; background-color:#1A2008;
    color:#F0EDD8 !important; margin-bottom:18px; font-size:14px;
    line-height:1.6; border:1px solid #2A3010; border-left:4px solid #8A9A35;
  }
  .card-emisor strong { color:#C8D87A !important; }
  .scroll-list {
    max-height:200px; overflow-y:auto; padding:8px 12px;
    background-color:#1A2008; border-radius:6px;
    border:1px solid #2A3010; font-family:monospace;
    font-size:12px; color:#A8BB45; line-height:1.8;
  }
  .inbox-revision {
    background-color:#1A2008; border:1px solid #8A9A35;
    border-radius:10px; padding:20px; margin-top:20px; margin-bottom:20px;
  }
  .inbox-revision h3 { color:#C8D87A !important; margin-top:0; }
  .inbox-revision p  { color:#8A9A35 !important; }
  .debug-box {
    background-color:#111808; border:1px solid #2A3010; border-radius:6px;
    padding:10px 14px; font-family:monospace; font-size:11px;
    color:#7A9A35; line-height:1.7; margin-top:8px;
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
    st.warning("Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Compras.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. CONSTANTES
# ─────────────────────────────────────────────
MAX_VALORES_LOOP = 30

# Tipos válidos para compras según manual F-07
TIPOS_VALIDOS_COMPRAS = {"03", "05", "06", "11", "14", "01"}

SKIP_LINEAS = re.compile(
    r'^(?:DOCUMENTO|TRIBUTARIO|ELECTRÓNICO|ELECTRONICO|COMPROBANTE|'
    r'CRÉDITO|CREDITO|FISCAL|CÓDIGO|CODIGO|SELLO|NÚMERO|NUMERO|'
    r'MODELO|TIPO\s+DE|FECHA|RECEPTOR|EMISOR|CLIENTE|DTE-|'
    r'PÁGINA|PAGINA|VER\.|VERSION|VERSIÓN|[A-F0-9]{8}-)',
    re.I
)
BASURA_ESTRICTA    = {"@", "EMAIL", "CORREO", ".COM", "WWW.", "HTTP", "FACTURA.GOB"}
PREFIJOS_DIRECCION = (
    "KM ", "KM.", "AV.", "AV ", "AVENIDA", "CALLE ", "PASAJE",
    "COLONIA", "COL.", "URB.", "URB ", "URBANIZACION", "URBANIZACIÓN",
    "RESIDENCIAL", "LOTIFICACION", "BARRIO", "CANTON", "CANTÓN",
    "CARRETERA", "CARR.", "BULEVAR", "BOULEVARD", "BLVD", "BLVD.",
    "POLIGONO", "LOCAL ", "NIVEL ", "PISO ", "EDIFICIO",
    "CENTRO COMERCIAL", "COMPLEJO", "PARQUE INDUSTRIAL",
    "FINAL ", "ENTRE ", "#", "NO.", "S/N",
)
PALABRAS_COMERCIALES = (
    "S.A.", "S.A.S.", "S DE R.L.", "LTDA.", "LTDA",
    "SOCIEDAD", "DISTRIBUIDORA", "FARMACIA", "GRUPO",
    "LABORATORIOS", "INDUSTRIAS", "SERVICIOS", "COMERCIAL",
    "IMPORTADORA", "EXPORTADORA", "CONSTRUCTORA", "CONSULTORES",
    "INVERSIONES", "ALIMENTOS", "TECNOLOGIA", "TECNOLOGÍA",
    "FERRETERIA", "FERRETERÍA", "ALMACENES", "TIENDA", "EMPRESA",
    "GRANJA", "GASOLINERA", "COMBUSTIBLE", "CLINICA", "HOSPITAL",
)
NOMBRES_INVALIDOS = {
    "MATRIZ", "LOCAL", "SUCURSAL", "AGENCIA", "OFICINA",
    "ESTABLECIMIENTO", "PUNTO DE VENTA", "ALMACEN", "BODEGA",
}
CORTE_NOMBRE = re.compile(
    r"\s*(?:NIT|NRC|GIRO|ACTIVIDAD|DIRECCI[OÓ]N|CORREO|TEL[EÉ]F|"
    r"TIPO\s+ESTAB|MUNICIPIO|DEPARTAMENTO|NUMERO\s+DE\s+CONTROL|"
    r"MODELO\s+DE|TIPO\s+DE\s+TRANS|N\.?\s*I\.?\s*T\.?\s*[:\s]|"
    r"N\.?\s*R\.?\s*C\.?\s*[:\s]|NÚMERO\s+DE|REGISTRO|PROCESAMIENTO|"
    r"\d{4}[\s\-]\d{6})"
    r".*$",
    re.I | re.S
)

# ─────────────────────────────────────────────
# 5. UTILIDADES BÁSICAS
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
    return any(L.startswith(p) or (f" {p}" in L[:60]) for p in PREFIJOS_DIRECCION)

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

# ─────────────────────────────────────────────
# 6. DATA PERSISTENCE
# ─────────────────────────────────────────────
def cargar_proveedores_json() -> dict:
    for ruta in ("data/proveedores.json", "data/clientes.json"):
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

def guardar_proveedor_rapido(nit: str, nombre: str) -> None:
    if not nit or not safe_str(nombre).strip():
        return
    ruta = "data/proveedores.json"
    if not os.path.exists("data"):
        os.makedirs("data")
    db = cargar_proveedores_json()
    db[nit] = {
        "nombre": safe_str(nombre).strip().upper(),
        "nrc": db.get(nit, {}).get("nrc", "")
    }
    with open(ruta, "w", encoding="utf-8") as f:
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

# ─────────────────────────────────────────────
# 7. EXTRACCIÓN DE FECHA (inmune a vencimientos)
# ─────────────────────────────────────────────
def extraer_y_formatear_fecha(texto: str) -> str:
    """
    Extrae la fecha de emisión del DTE.
    Prioriza la fecha etiquetada como "Fecha" o "Emisión".
    Ignora fechas de vencimiento (Vence:, V:, Lote:).
    """
    try:
        texto = safe_str(texto)
        # Quitar horas pegadas a fechas
        texto_clean = re.sub(r'[-\s]\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?', '', texto, flags=re.I)

        candidatas = []

        # Paso 1: buscar con etiqueta explícita de emisión/fecha/generación
        for m in re.finditer(
            r'(?:[Ff]echa\s+y\s+[Hh]ora\s+de\s+(?:[Gg]eneraci[oó]n|[Ee]misi[oó]n)|'
            r'[Ff]echa\s+(?:de\s+)?[Ee]misi[oó]n|[Ff]echa\s+[Gg]eneraci[oó]n|'
            r'(?<!\w)[Ff]echa(?!\s+[Vv]ence|\s+[Vv]enc))'
            r'\s*:?\s*'
            r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]20[2-3]\d|20[2-3]\d[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})',
            texto_clean, re.I
        ):
            candidatas.append((m.start(), m.group(1)))

        # Paso 2: Formato ISO (YYYY-MM-DD) sin etiqueta
        for m in re.finditer(r'\b(20[2-3]\d)[-\/](0[1-9]|1[0-2])[-\/]([0-2]\d|3[01])\b', texto_clean):
            ctx = texto_clean[max(0, m.start()-30):m.start()].upper()
            if not any(w in ctx for w in ['VENCE', 'LOTE', 'V:', 'EXPIRA', 'CADUCIDAD']):
                candidatas.append((m.start(), f"{m.group(3)}/{m.group(2)}/{m.group(1)}"))

        # Paso 3: DD/MM/YYYY o DD-MM-YYYY sin etiqueta
        for m in re.finditer(r'\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20[2-3]\d)\b', texto_clean):
            ctx = texto_clean[max(0, m.start()-30):m.start()].upper()
            if any(w in ctx for w in ['VENCE', 'LOTE', 'V:', 'EXPIRA', 'CADUCIDAD']):
                continue
            p1, p2, y = int(m.group(1)), int(m.group(2)), m.group(3)
            if p1 > 31 or p2 > 12:
                continue
            if p2 <= 12:
                candidatas.append((m.start(), f"{p1:02d}/{p2:02d}/{y}"))

        candidatas.sort(key=lambda x: x[0])

        for _, fecha_str in candidatas:
            # Normalizar a DD/MM/YYYY
            # Si ya tiene formato string, intentar parsear
            # ISO: contiene YYYY al inicio
            m_iso = re.match(r'(20[2-3]\d)[-\/](\d{1,2})[-\/](\d{1,2})', fecha_str)
            if m_iso:
                return f"{int(m_iso.group(3)):02d}/{int(m_iso.group(2)):02d}/{m_iso.group(1)}"
            # DMY
            m_dmy = re.match(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20[2-3]\d)', fecha_str)
            if m_dmy:
                return f"{int(m_dmy.group(1)):02d}/{int(m_dmy.group(2)):02d}/{m_dmy.group(3)}"
            # Already formatted
            if re.match(r'\d{2}\/\d{2}\/20\d{2}', fecha_str):
                return fecha_str

    except Exception:
        pass
    return ""

# ─────────────────────────────────────────────
# 8. EXTRACCIÓN DE NOMBRE DEL PROVEEDOR/EMISOR
# ─────────────────────────────────────────────
def extraer_nombre_emisor(texto: str, nit_prov: str, receptor_nombre: str) -> str:
    """
    Extrae el nombre del EMISOR (proveedor) del DTE.
    
    Maneja los 3 formatos principales observados:
    1. Combustible (Granja San Diego): Nombre aparece antes de "Datos del Receptor"
    2. Vidri: Layout EMISOR | RECEPTOR en columnas, "Nombre o Razón Social:" en misma línea que receptor
    3. Adimacon: Nombre es la primera línea del documento
    """
    texto = safe_str(texto)
    receptor_up = safe_str(receptor_nombre).strip().upper()

    def limpiar(s: str) -> str:
        """Limpia candidato de ruido."""
        s = safe_str(s)
        # Quitar nombre del receptor si se coló
        if receptor_up and len(receptor_up) > 3:
            s = re.compile(re.escape(receptor_up), re.I).sub("", s)
        # Cortar en segunda ocurrencia de "Nombre o" (layout columnar Vidri)
        s = re.split(r'\s+[Nn]ombre\s+[Oo]\s+[Rr]az', s, maxsplit=1)[0]
        # Quitar etiquetas de campo
        s = re.sub(
            r'^[\s\-:]*(?:RAZ[OÓ]N\s*SOCIAL|NOMBRE(?:\s+O\s+RAZ[OÓ]N\s+SOCIAL)?|'
            r'NOMBRE\s+COMERCIAL|EMISOR|DATOS\s+DEL\s+EMISOR)[\s:]*',
            s, flags=re.I
        ).strip()
        s = CORTE_NOMBRE.sub("", s).strip()
        s = re.sub(r'^[-_.,;:\s]+|[-_.,;:\s]+$', "", s)
        # Quitar NIT/NRC inline
        s = re.sub(r'\b(?:NIT|NRC)\s*:?\s*[\d\-]+', '', s, flags=re.I).strip()
        s = re.sub(r'\s{2,}', ' ', s)
        return s.upper()

    def valido(s: str) -> bool:
        T = safe_str(s).strip().upper()
        if len(T) < 4 or len(T) > 90:
            return False
        if receptor_up and (T == receptor_up or T.startswith(receptor_up[:12])):
            return False
        if any(b in T for b in BASURA_ESTRICTA):
            return False
        if es_linea_direccion(T):
            return False
        if T in NOMBRES_INVALIDOS:
            return False
        digitos = sum(c.isdigit() for c in T)
        if len(T) > 0 and digitos / len(T) > 0.40:
            return False
        if re.fullmatch(r'[\d\s\-\.\/\(\)]+', T):
            return False
        if not re.search(r'[A-ZÁÉÍÓÚÑÜ]', T):
            return False
        # Skip metadata keywords
        if SKIP_LINEAS.match(T):
            return False
        return True

    # ── Estrategia 1: Etiqueta "Nombre o Razón Social:" en sección EMISOR ──────
    # Para Vidri: la etiqueta aparece con ambos nombres en la misma línea
    # Tomamos el PRIMER match (que es el emisor)
    m_nom = re.search(
        r'[Nn]ombre\s+[Oo]\s+[Rr]az[oó]n\s+[Ss]ocial\s*:\s*([^\n]{4,120})',
        texto
    )
    if m_nom:
        candidato = limpiar(m_nom.group(1))
        if valido(candidato):
            return candidato

    # ── Estrategia 2: Sección antes del receptor ────────────────────────────────
    parte_emisor = texto
    for pat in [
        r'(?i)\bEMISOR\s+RECEPTOR\b',   # Vidri: columnas en una línea
        r'(?i)DATOS\s+DEL\s+RECEPTOR',
        r'(?i)DATOS\s+DEL\s+CLIENTE',
        r'(?i)\bRECEPTOR\b',
        r'(?i)\bCLIENTE\b',
    ]:
        parts = re.split(pat, texto, maxsplit=1)
        if len(parts) >= 2:
            parte_emisor = parts[0]
            break

    # ── Estrategia 3: Palabras comerciales en bloque emisor ────────────────────
    for linea in parte_emisor.split('\n'):
        l = safe_str(linea).strip()
        if not l or len(l) < 4:
            continue
        if SKIP_LINEAS.match(l):
            continue
        if any(b in l.upper() for b in BASURA_ESTRICTA):
            continue
        # Bonus si tiene palabras comerciales típicas
        tiene_comercial = any(w in l.upper() for w in PALABRAS_COMERCIALES)
        candidato = limpiar(l)
        if valido(candidato) and (tiene_comercial or len(candidato) >= 8):
            return candidato

    # ── Estrategia 4: Primera línea no-metadata del documento completo ─────────
    for linea in texto.split('\n')[:20]:
        l = safe_str(linea).strip()
        if not l or len(l) < 4:
            continue
        if SKIP_LINEAS.match(l):
            continue
        if any(b in l.upper() for b in BASURA_ESTRICTA):
            continue
        candidato = limpiar(l)
        if valido(candidato):
            return candidato

    # ── Estrategia 5: Buscar por NIT del proveedor en lineas anteriores ────────
    if nit_prov and len(nit_prov) >= 9:
        nit_pattern = re.sub(r'(.{4})(.{6})(.{3})(.)', r'\1-\2-\3-\4', nit_prov) if len(nit_prov)==14 else nit_prov
        lineas = texto.split('\n')
        for i, linea in enumerate(lineas):
            if nit_prov in re.sub(r'[^0-9]', '', linea):
                for offset in [1, 2]:
                    if i - offset >= 0:
                        candidato = limpiar(lineas[i - offset].strip())
                        if valido(candidato):
                            return candidato

    return ""


# ══════════════════════════════════════════════════════════════
# 9. EXTRACTOR PRINCIPAL DE COMPRAS
# ══════════════════════════════════════════════════════════════
def extraer_compra_nativo_pro(file_bytes: bytes, cliente_activo: dict) -> dict:
    """
    Extrae datos de un DTE de compra (CCF, NC, ND, Factura Sujeto Excluido).
    
    Maneja correctamente:
    - Múltiples layouts de PDF (Granja San Diego, Vidri, Adimacon, etc.)
    - FOVIAL y COTRANS como compras exentas (columna G del F-07)
    - Sello de recepción con caracteres no-hex (Q, T, I, K, etc.)
    - Fecha de emisión vs. fecha de vencimiento (no confundir)
    - Nombre del emisor en layouts columnar y vertical
    """
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

        # ── Número de Control DTE ─────────────────────────────────────────────
        tipo        = ""
        ctrl        = ""
        num_control = ""  # Sin guiones para F-07

        m_ctrl = re.search(r'\b(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})\b', t_clean, re.I)
        if not m_ctrl:
            # Fallback sin espacios
            m_ctrl = re.search(r'(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})', t_no_sp)

        if m_ctrl:
            ctrl = m_ctrl.group(1).upper()
            # Extraer tipo del grupo 2 si existe, sino del ctrl
            if m_ctrl.lastindex and m_ctrl.lastindex >= 2:
                tipo = m_ctrl.group(2)
            else:
                m_tipo = re.search(r'DTE-(\d{2})', ctrl)
                tipo = m_tipo.group(1) if m_tipo else ""
            num_control = ctrl.replace("-", "")

        if not ctrl:
            return {"error_tipo": "No se detecto Numero de Control DTE valido."}
        if tipo not in TIPOS_VALIDOS_COMPRAS:
            return {"error_tipo": f"DTE-{tipo} no admitido en compras. Validos: {', '.join(sorted(TIPOS_VALIDOS_COMPRAS))}."}

        # ── Sello de Recepción ─────────────────────────────────────────────────
        # Los sellos pueden incluir caracteres no-hex (Q, T, I, K, etc.)
        # Son exactamente 40 chars alfanuméricos, empiezan con el año
        sello = ""

        # Primero: buscar con etiqueta explícita (más confiable)
        m_sello_etq = re.search(
            r'[Ss]ello\s+(?:[Dd][Gg][Ii]|de\s+[Rr]ecepci[oó]n)\s*:?\s*([A-Z0-9]{30,50})',
            t_clean, re.I
        )
        if m_sello_etq:
            sello = m_sello_etq.group(1)[:40]  # truncar a 40 si hay más
        
        if not sello:
            # Buscar en texto sin espacios: año + 36 alfanuméricos
            m_sello2 = re.search(r'\b(20[2-3]\d[A-Z0-9]{36})\b', t_no_sp)
            if m_sello2:
                sello = m_sello2.group(1)

        if not sello:
            # Último intento: buscar "SELLO" en t_no_sp y tomar los siguientes chars
            idx = t_no_sp.find('SELLO')
            if idx >= 0:
                # Puede ser SELLODGI o SELLORECEPCION seguido del valor
                resto = t_no_sp[idx:]
                m_s3 = re.search(r'(?:SELLO[A-Z]*:?)([A-Z0-9]{30,50})', resto)
                if m_s3:
                    sello = m_s3.group(1)[:40]

        # ── Código de Generación (UUID) ────────────────────────────────────────
        gen = ""
        # Con etiqueta
        m_gen_etq = re.search(
            r'[Cc][oó]digo\s+(?:de\s+)?[Gg]eneraci[oó]n\s*:?\s*'
            r'([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})',
            t_clean
        )
        if m_gen_etq:
            gen = m_gen_etq.group(1).upper()

        if not gen:
            # Buscar UUID estándar en texto limpio
            m_uuid = re.search(
                r'([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})',
                t_clean
            )
            if m_uuid:
                gen = m_uuid.group(1).upper()

        if not gen:
            # En t_no_sp: 32 hex chars seguidos
            m_uuid2 = re.search(r'[A-F0-9]{32}', t_no_sp)
            if m_uuid2:
                raw = m_uuid2.group(0)
                gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}".upper()

        gen_sin_guiones = gen.replace("-", "")

        # ── Fecha de emisión ────────────────────────────────────────────────────
        fecha = extraer_y_formatear_fecha(texto_lineal)
        if not fecha:
            fecha = extraer_y_formatear_fecha(texto_completo)

        # ── Datos del Receptor (para excluir sus números) ──────────────────────
        nit_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nit', '')))
        dui_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('dui', '')))
        nrc_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nrc', '')))
        nom_receptor = safe_str(cliente_activo.get('nombre', '')).strip().upper()
        excluir_nits = {nit_receptor, dui_receptor, nrc_receptor} - {""}
        # Añadir variantes sin guiones de NIT del receptor
        excluir_nits.add(re.sub(r'[^0-9]', '', nit_receptor))

        # ── NIT del Proveedor/Emisor ───────────────────────────────────────────
        nit_prov       = ""
        dui_prov       = ""
        nom_prov       = ""
        es_nuevo       = True
        pos_nit_prov   = -1
        proveedores_db = cargar_proveedores_json()

        # Separar sección EMISOR del texto
        parte_emisor = texto_lineal
        for pat in [
            r'(?i)\bEMISOR\s+RECEPTOR\b',
            r'(?i)DATOS\s+DEL\s+RECEPTOR',
            r'(?i)DATOS\s+DEL\s+CLIENTE',
            r'(?i)\bRECEPTOR\b',
            r'(?i)\bCLIENTE\b',
        ]:
            parts = re.split(pat, texto_lineal, maxsplit=1)
            if len(parts) >= 2:
                parte_emisor = parts[0]
                break

        # Buscar NIT con etiqueta "NIT:" en sección emisor primero
        m_nit_etq = re.search(
            r'N\.?\s*I\.?\s*T\.?\s*[:\s]\s*'
            r'((?:\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d)|\d{14})',
            parte_emisor, re.I
        )
        if m_nit_etq:
            nit_cand = re.sub(r'[^0-9]', '', m_nit_etq.group(1))
            if nit_cand not in excluir_nits and len(nit_cand) == 14:
                nit_prov     = nit_cand
                pos_nit_prov = m_nit_etq.start()

        # Si no encontró en emisor, buscar en todo el texto
        if not nit_prov:
            patron_nit = re.compile(
                r'N\.?\s*I\.?\s*T\.?\s*[:\s]\s*'
                r'((?:\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d)|\d{14})',
                re.I
            )
            for m in patron_nit.finditer(texto_completo):
                nit_cand = re.sub(r'[^0-9]', '', m.group(1))
                if nit_cand not in excluir_nits and len(nit_cand) == 14:
                    nit_prov     = nit_cand
                    pos_nit_prov = m.start()
                    break

        # Fallback: cualquier número de 14 dígitos no excluido
        if not nit_prov:
            for m in re.finditer(r'\b(\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d|\d{14})\b', texto_completo):
                nit_cand = re.sub(r'[^0-9]', '', m.group(0))
                if nit_cand not in excluir_nits and len(nit_cand) == 14:
                    nit_prov     = nit_cand
                    pos_nit_prov = m.start()
                    break

        # DUI del proveedor (9 dígitos, solo si no hay NIT)
        if not nit_prov:
            for m in re.finditer(r'\b(\d{8}[\s\-]?\d|\d{9})\b', parte_emisor):
                nit_cand = re.sub(r'[^0-9]', '', m.group(0))
                if nit_cand not in excluir_nits and len(nit_cand) == 9:
                    dui_prov = nit_cand
                    break

        # ── Nombre del Proveedor ────────────────────────────────────────────────
        id_lookup = nit_prov or dui_prov
        if id_lookup and id_lookup in proveedores_db:
            nom_prov = safe_str(proveedores_db[id_lookup].get("nombre", ""))
            es_nuevo = False

        if es_nuevo:
            # Intentar en texto lineal primero (más limpio)
            nombre_encontrado = extraer_nombre_emisor(texto_lineal, nit_prov, nom_receptor)
            if not nombre_encontrado:
                nombre_encontrado = extraer_nombre_emisor(texto_visual, nit_prov, nom_receptor)
            nom_prov = nombre_encontrado if nombre_encontrado else ""

        # ── Extracción de montos ────────────────────────────────────────────────
        exe    = 0.0   # Compras exentas/no sujetas (col G) — incluye Fovial+Cotrans
        gra    = 0.0   # Compras gravadas (col J)
        iva    = 0.0   # Crédito fiscal IVA (col N)
        ret    = 0.0   # IVA retenido
        perc   = 0.0   # IVA percibido
        tot    = 0.0   # Total compras (col O)
        iva_calculado = False

        # ── FOVIAL y COTRANS: son exentos/no sujetos (col G) ──────────────────
        # Combustibles incluyen Fovial y Cotrans en el documento,
        # que son tributos exentos de IVA
        fovial  = 0.0
        cotrans = 0.0
        m_fov = re.search(r'[Ff]ovial\s*:?\s*\$?\s*(\d[\d,.]*)', t_clean)
        m_cot = re.search(r'[Cc]otrans\s*:?\s*\$?\s*(\d[\d,.]*)', t_clean)
        if m_fov:
            fovial = limpiar_monto(m_fov.group(1))
        if m_cot:
            cotrans = limpiar_monto(m_cot.group(1))
        fovial_cotrans = round(fovial + cotrans, 2)

        # ── Exentas/No Sujetas ─────────────────────────────────────────────────
        # Intentar varias etiquetas
        for pat in [
            r'[Vv]tas?\.?\s+[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Vv]entas?\s+[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Tt]otal\s+[Ee]xento\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_exe = re.search(pat, t_clean)
            if m_exe:
                val = limpiar_monto(m_exe.group(1))
                if val > 0:
                    exe = val
                    break

        # Si hay Fovial/Cotrans y son mayores que lo encontrado, tomar el mayor
        exe = max(exe, fovial_cotrans)

        # ── IVA Retenido ────────────────────────────────────────────────────────
        for pat in [
            r'[\(\-]\s*[Ii][Vv][Aa]\s+[Rr]etenido\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Ii][Vv][Aa]\s+[Rr]etenido\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Rr]etenci[oó]n\s+[Ii][Vv][Aa]\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_ret = re.search(pat, t_clean)
            if m_ret:
                ret = limpiar_monto(m_ret.group(1))
                if ret > 0:
                    break

        # ── IVA Percibido ────────────────────────────────────────────────────────
        m_perc = re.search(r'[Ii][Vv][Aa]\s+[Pp]ercibido\s*:?\s*\$?\s*(\d[\d,.]+)', t_clean)
        if m_perc:
            perc = limpiar_monto(m_perc.group(1))

        # ── Total a Pagar ────────────────────────────────────────────────────────
        for pat in [
            r'[Tt]otal\s+a\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Tt]otal\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Mm]onto\s+[Tt]otal\s+de\s+la\s+[Oo]peraci[oó]n\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Vv]alor\s+[Tt]otal\s+a\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_tot = re.search(pat, t_clean)
            if m_tot:
                tot = limpiar_monto(m_tot.group(1))
                if tot > 0:
                    break

        # ── IVA / Crédito Fiscal ─────────────────────────────────────────────────
        for pat in [
            r'[Ii]mpuesto\s+al\s+[Vv]alor\s+[Aa]gregado\s*13\s*%?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Ii]mpuesto\s+al\s+[Vv]alor\s+[Aa]gregado\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Ii][Vv][Aa]\s*13\s*%?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'13\s*%\s*[Ii]va\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Cc]r[eé]dito\s+[Ff]iscal\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Dd][eé]bito\s+[Ff]iscal\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_iva = re.search(pat, t_clean)
            if m_iva:
                iva = limpiar_monto(m_iva.group(1))
                if iva > 0:
                    break

        # ── Gravadas ─────────────────────────────────────────────────────────────
        for pat in [
            r'[Vv]ta\.?\s+[Gg]ravada\s+[Nn]eta\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Vv]entas?\s+[Gg]ravadas?\s+[Ll]ocales?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Tt]otal\s+[Gg]ravad[ao]\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Gg]ravado\s*:?\s*(\d[\d,.]+)',
            r'[Ss]ubtotal\s+ventas\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Ss]umatoria\s+de\s+[Vv]entas\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Ss]ub-?[Tt]otal\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_grav = re.search(pat, t_clean)
            if m_grav:
                gra = limpiar_monto(m_grav.group(1))
                if gra > 0:
                    break

        # ── Lógica de Reconciliación ──────────────────────────────────────────────
        encontrado = tot > 0 and iva > 0 and gra > 0

        if not encontrado and tipo == "01":
            # DTE-01 de compra (factura de sujeto excluido): sin crédito fiscal
            iva = 0.0
            gra = tot - exe
            encontrado = tot > 0

        if not encontrado:
            # Algoritmo de búsqueda por consistencia matemática
            montos_raw = re.findall(
                r'(?:\$|USD)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})',
                t_clean
            )
            set_montos = set()
            for rv in montos_raw:
                v = limpiar_monto(rv)
                if v > 0.01:
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
                        # Verificar relación IVA 13%
                        if abs(round(vg * 0.13, 2) - round(vi, 2)) <= 0.05:
                            # Verificar total
                            candidato_tot = round(vg + vi + exe - ret + perc, 2)
                            if abs(candidato_tot - round(vt, 2)) <= 0.10:
                                gra = vg
                                iva = vi
                                tot = vt
                                encontrado = True
                                break

        # Ajustes finales si aún faltan valores
        if not encontrado:
            if tot > 0 and iva > 0 and gra == 0.0:
                gra = round(tot - iva - exe + ret - perc, 2)
                encontrado = True
            elif tot > 0 and iva == 0.0 and gra == 0.0 and tipo == "03":
                # CCF sin IVA detectado: calcular
                gra = round((tot - exe + ret - perc) / 1.13, 2)
                iva = round(tot - exe + ret - perc - gra, 2)
                iva_calculado = True
                encontrado = True
            elif tot == 0.0 and gra > 0 and iva > 0:
                tot = round(gra + iva + exe - ret + perc, 2)

        # Asegurar que gravadas no sean negativas
        gra = max(gra, 0.0)
        iva = max(iva, 0.0)

        return {
            "fecha"         : fecha,
            "tipo"          : tipo,
            "num_control"   : num_control,       # Sin guiones (para F-07 col D)
            "num_control_raw": ctrl,              # Con guiones (para mostrar)
            "sello"         : sello,
            "gen"           : gen,                # Con guiones
            "gen_sin_guiones": gen_sin_guiones,   # Sin guiones (para F-07 col D cuando aplique)
            "nit_prov"      : nit_prov,
            "dui_prov"      : dui_prov,
            "nom_prov"      : nom_prov,
            "exe"           : round(exe, 2),
            "gra"           : round(gra, 2),
            "iva"           : round(iva, 2),
            "ret"           : round(ret, 2),
            "perc"          : round(perc, 2),
            "tot"           : round(tot, 2),
            "fovial"        : round(fovial, 2),
            "cotrans"       : round(cotrans, 2),
            "estado"        : "OK",
            "iva_calc"      : iva_calculado,
            "es_nuevo"      : es_nuevo,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
    except Exception as err:
        return {"error_extraccion": safe_str(err)}


# ─────────────────────────────────────────────
# 10. CONSTRUCCIÓN DEL DATAFRAME F-07 COMPRAS
# ─────────────────────────────────────────────
def construir_df_f07_compras(df_in: pd.DataFrame) -> pd.DataFrame:
    """
    Anexo 3: Detalle de Compras (F-07 V14)
    Columnas A-U (21 columnas según manual)
    
    D. Número de Documento = código de generación SIN guiones (para DTE)
    E. NIT o NRC           = nit_prov
    G. Compras Int. Exentas/NS = exe (incluye Fovial+Cotrans)
    J. Compras Gravadas    = gra
    N. Crédito Fiscal      = iva
    O. Total Compras       = tot
    P. DUI Proveedor       = dui_prov (si persona natural)
    Q-T. Clasificación Renta = valores por defecto (usuario ajusta)
    U. Num Anexo           = 3
    """
    df_out = pd.DataFrame()
    df_out["A. Fecha Emisión"]         = df_in["fecha"]
    df_out["B. Clase Documento"]       = "4"              # DTE
    df_out["C. Tipo Documento"]        = df_in["tipo"]
    # D: Código de generación SIN guiones (manual F-07 V14, col D compras = Número Documento)
    df_out["D. Num Documento (UUID)"]  = df_in["gen_sin_guiones"].astype(str)
    # E: NIT del proveedor (o vacío si solo hay DUI)
    df_out["E. NIT/NRC Proveedor"]     = df_in["nit_prov"].astype(str)
    df_out["F. Nombre Proveedor"]      = df_in["nom_prov"].astype(str)
    # G: Compras internas exentas y/o no sujetas (Fovial, Cotrans, exentas)
    df_out["G. Compras Exentas/NS"]    = df_in["exe"]
    df_out["H. Internac. Exentas/NS"]  = 0.0
    df_out["I. Import. Exentas/NS"]    = 0.0
    # J: Compras gravadas (sin IVA)
    df_out["J. Compras Gravadas"]      = df_in["gra"]
    df_out["K. Internac. Grav. Bienes"]= 0.0
    df_out["L. Import. Grav. Bienes"]  = 0.0
    df_out["M. Import. Grav. Servicios"]= 0.0
    # N: Crédito fiscal = 13% de gravadas
    df_out["N. Crédito Fiscal (IVA)"]  = df_in["iva"]
    # O: Total = G + J + N (± retenciones/percepciones)
    df_out["O. Total Compras"]         = df_in["tot"]
    # P: DUI (solo persona natural; si hay NIT este va vacío)
    df_out["P. DUI Proveedor"]         = df_in["dui_prov"].astype(str)
    # Q-T: Clasificación para ISR (valores por defecto)
    df_out["Q. Tipo Operación"]        = "1"   # 1=Gravada
    df_out["R. Clasificación"]         = "2"   # 2=Gasto (ajustar según caso)
    df_out["S. Sector"]                = "4"   # 4=Servicios/Comercio (ajustar)
    df_out["T. Tipo Costo/Gasto"]      = "2"   # 2=Gastos Administrativos (ajustar)
    df_out["U. Num Anexo"]             = "3"
    return df_out


# ─────────────────────────────────────────────
# 11. EXPORTAR EXCEL HACIENDA
# ─────────────────────────────────────────────
def to_excel_hacienda_compras(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Compras_F07')
        ws = writer.sheets['Compras_F07']
        anchos = [12, 2, 3, 38, 16, 45, 12, 12, 12, 12, 12, 12, 12, 12, 14, 10, 2, 2, 2, 2, 3]
        for idx_col, ancho in enumerate(anchos, start=1):
            ws.column_dimensions[ws.cell(1, idx_col).column_letter].width = ancho
        for fila in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=7, max_col=15):
            for celda in fila:
                if isinstance(celda.value, (int, float)):
                    celda.number_format = '#,##0.00'
    return output.getvalue()


@st.dialog("Confirmar Descarga de Compras")
def ventana_descarga_compras(df_f07: pd.DataFrame, nombre_archivo: str) -> None:
    st.write("Verifica los totales. El archivo está listo para cargar en el portal de Hacienda como **Anexo 3**.")
    
    COLS_NUM = [c for c in df_f07.columns if df_f07[c].dtype == float]
    resumen_cols = {
        "G. Compras Exentas/NS": "Exentas/NS",
        "J. Compras Gravadas"  : "Gravadas",
        "N. Crédito Fiscal (IVA)": "IVA",
        "O. Total Compras"     : "Total",
    }
    col1, col2, col3, col4 = st.columns(4)
    for col_key, label, col_obj in zip(
        resumen_cols.keys(), resumen_cols.values(),
        [col1, col2, col3, col4]
    ):
        if col_key in df_f07.columns:
            col_obj.metric(label, f"${df_f07[col_key].sum():,.2f}")
    
    st.download_button(
        "📥 Confirmar y Descargar Anexo 3",
        data=to_excel_hacienda_compras(df_f07),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary", use_container_width=True
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
            st.markdown(f'<div class="scroll-list">{items_html}</div>', unsafe_allow_html=True)
    else:
        st.success(f"✅ 0 {titulo}")


def datos_revision_vacio(causa: str = "") -> dict:
    return {
        "fecha": "", "tipo": "03",
        "num_control": "", "num_control_raw": "",
        "sello": "", "gen": "", "gen_sin_guiones": "",
        "nit_prov": "", "dui_prov": "", "nom_prov": "",
        "exe": 0.0, "gra": 0.0, "iva": 0.0,
        "ret": 0.0, "perc": 0.0, "tot": 0.0,
        "fovial": 0.0, "cotrans": 0.0,
        "estado": "REVISION", "iva_calc": False, "es_nuevo": True,
        "_error": safe_str(causa),
    }


def tipo_badge_compra(tipo: str) -> str:
    badges = {
        "03": "🟢 CCF (03)",
        "05": "🟠 Nota Crédito (05)",
        "06": "🔴 Nota Débito (06)",
        "01": "🔵 Factura (01)",
        "11": "🟡 Fac. Export. (11)",
        "14": "⚪ Suj. Excluido (14)",
    }
    return badges.get(tipo, f"📄 DTE-{tipo}")


# ─────────────────────────────────────────────
# 12. ENCABEZADO
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
    <strong>NIT:</strong> {safe_str(cliente.get('nit',''))} &nbsp;|&nbsp;
    <strong>NRC:</strong> {safe_str(cliente.get('nrc',''))}
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 13. SESSION STATE
# ─────────────────────────────────────────────
if 'cola_revision'     not in st.session_state: st.session_state.cola_revision     = []
if 'comp_uploader_key' not in st.session_state: st.session_state.comp_uploader_key = 0
if 'db_compras'        not in st.session_state: st.session_state.db_compras        = pd.DataFrame()
if 'archivos_comp'     not in st.session_state: st.session_state.archivos_comp     = []
if 'reporte_compras'   not in st.session_state: st.session_state.reporte_compras   = None

# ─────────────────────────────────────────────
# 14. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga de Compras")
    st.markdown(
        "<small style='color:#8A9A35'>Acepta: CCF (03), NC (05), ND (06), "
        "Fac. (01/11), Suj. Excluido (14)</small>",
        unsafe_allow_html=True
    )
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
        ya_procesados = set(st.session_state.archivos_comp)
        nuevos        = [f for f in archivos if f.name not in ya_procesados]

        if not nuevos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            extracted, duplicados, iva_calc_files   = [], [], []
            invalidos, corruptos, nuevos_proveedores = [], [], {}

            bar          = st.progress(0)
            txt_progreso = st.empty()
            t_inicio     = time.time()
            total_arch   = len(nuevos)

            for idx, f in enumerate(nuevos):
                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                if idx > 0:
                    elapsed   = time.time() - t_inicio
                    remaining = int((elapsed / idx) * (total_arch - idx))
                    m_t, s_t  = divmod(remaining, 60)
                    txt_progreso.caption(f"⏳ {idx+1}/{total_arch} — Restante: {m_t:02d}:{s_t:02d}")
                else:
                    txt_progreso.caption(f"⏳ Procesando 1 de {total_arch}...")

                file_bytes = f.read()

                if len(file_bytes) < 512:
                    corruptos.append(f.name)
                    st.session_state.archivos_comp.append(f.name)
                    bar.progress((idx + 1) / total_arch)
                    continue

                res = extraer_compra_nativo_pro(file_bytes, cliente)

                cod_gen  = safe_str(res.get('gen', ''))
                num_ctrl = safe_str(res.get('num_control', ''))
                dup_id   = cod_gen or num_ctrl

                dup_memoria = (
                    not st.session_state.db_compras.empty
                    and dup_id
                    and 'gen' in st.session_state.db_compras.columns
                    and (
                        (st.session_state.db_compras['gen'] == cod_gen).any()
                        if cod_gen else
                        (st.session_state.db_compras['num_control'] == num_ctrl).any()
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
                    st.session_state.cola_revision.append({
                        "archivo": f.name,
                        "bytes"  : file_bytes,
                        "datos"  : datos_revision_vacio(res["error_extraccion"]),
                    })

                else:
                    nom_res = safe_str(res.get('nom_prov', '')).strip()

                    # Criterios para ir a revisión manual
                    va_revision = (
                        res.get('tot', 0.0) == 0.0
                        or not res.get('num_control')
                        or not safe_str(res.get('fecha', '')).strip()
                        or not nom_res
                    )

                    if va_revision:
                        st.session_state.cola_revision.append({
                            "archivo": f.name,
                            "bytes"  : file_bytes,
                            "datos"  : res,
                        })
                    else:
                        if res.get('iva_calc'):
                            iva_calc_files.append(f.name)
                        if res.get("es_nuevo") and (res.get("nit_prov") or res.get("dui_prov")):
                            id_prov = res.get("nit_prov") or res.get("dui_prov")
                            nuevos_proveedores[id_prov] = res["nom_prov"]
                            guardar_proveedor_rapido(id_prov, res["nom_prov"])
                        res["archivo"] = f.name
                        # Asegurar columnas necesarias
                        for col in ['gen_sin_guiones', 'num_control_raw', 'sello', 'dui_prov',
                                    'fovial', 'cotrans']:
                            if col not in res:
                                res[col] = ""
                        extracted.append(res)

                st.session_state.archivos_comp.append(f.name)
                bar.progress((idx + 1) / total_arch)

            txt_progreso.success(f"✅ {total_arch} facturas escaneadas.")

            st.session_state.reporte_compras = {
                "invalidos"         : invalidos,
                "duplicados"        : duplicados,
                "iva_calc"          : iva_calc_files,
                "nuevos_proveedores": nuevos_proveedores,
                "corruptos"         : corruptos,
            }

            if extracted:
                new_df = pd.DataFrame(extracted)
                for col in ['gen_sin_guiones', 'num_control_raw', 'sello', 'dui_prov',
                            'fovial', 'cotrans']:
                    if col not in new_df.columns:
                        new_df[col] = ""

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
        df_sb = st.session_state.db_compras
        st.divider()
        n_ccf  = len(df_sb[df_sb['tipo'] == '03']) if 'tipo' in df_sb.columns else 0
        n_otros = len(df_sb) - n_ccf
        st.markdown(f"**📄 Total docs:** `{len(df_sb)}`")
        st.markdown(f"**🟢 CCF (03):** `{n_ccf}` | **Otros:** `{n_otros}`")
        if 'tot' in df_sb.columns:
            st.markdown(f"**💰 Total Compras:** `${df_sb['tot'].sum():,.2f}`")
        if 'iva' in df_sb.columns:
            st.markdown(f"**🏦 Crédito Fiscal:** `${df_sb['iva'].sum():,.2f}`")

# ─────────────────────────────────────────────
# 15. BANDEJA DE REVISIÓN MANUAL
# ─────────────────────────────────────────────
if st.session_state.cola_revision:
    st.markdown("""
    <div class="inbox-revision">
        <h3>📥 Bandeja de Revisión Manual</h3>
        <p>Datos incompletos o fallo de extracción. Revisa y corrige antes de agregar al libro.</p>
    </div>
    """, unsafe_allow_html=True)

    total_cola = len(st.session_state.cola_revision)

    col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
    with col_nav2:
        st.info(f"📄 Documento **1 de {total_cola}** en revisión | Quedan **{total_cola}** por revisar")

    with st.expander("🗑️ Gestión masiva"):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("🗑️ Descartar TODOS los pendientes", type="secondary", use_container_width=True):
                st.session_state.cola_revision = []
                st.rerun()
        with col_m2:
            st.caption(f"Total en cola: {total_cola} documentos")

    item_actual = st.session_state.cola_revision[0]
    datos_act   = item_actual["datos"]
    tipo_actual = safe_str(datos_act.get("tipo", "03"))

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
                        st.caption(f"**Tipo:** `{tipo_badge_compra(tipo_actual)}`")
                        st.caption(f"**Ctrl:** `{datos_act.get('num_control_raw', datos_act.get('num_control','—'))}`")
                        st.caption(f"**UUID:** `{datos_act.get('gen','—')}`")
                        st.caption(f"**Sello:** `{datos_act.get('sello','—')}`")
                        st.caption(f"**Fecha:** `{datos_act.get('fecha','—')}`")
                    with col_d2:
                        st.caption(f"**NIT prov:** `{datos_act.get('nit_prov','—')}`")
                        st.caption(f"**Nombre:** `{datos_act.get('nom_prov','—')}`")
                        st.caption(f"**Total:** `${datos_act.get('tot',0):.2f}`")
                        st.caption(f"**Gravadas:** `${datos_act.get('gra',0):.2f}`")
                        st.caption(f"**IVA:** `${datos_act.get('iva',0):.2f}`")
                        st.caption(f"**Exentas:** `${datos_act.get('exe',0):.2f}` "
                                   f"(Fov: {datos_act.get('fovial',0):.2f} | "
                                   f"Cot: {datos_act.get('cotrans',0):.2f})")
                        err = datos_act.get('_error','')
                        if err:
                            st.caption(f"**⚠️ Error:** `{err}`")

                st.markdown("**📝 Texto extraído:**")
                st.text_area("", value=texto_crudo.strip(),
                             height=220, label_visibility="collapsed")
        except Exception as ex_prev:
            st.error(f"Vista previa no disponible: {safe_str(ex_prev)}")

    with col_form:
        st.markdown("### ✍️ Corrección Manual")

        with st.form(key=f"form_rev_c_{item_actual['archivo']}"):
            st.markdown("**📋 Identificación**")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_fecha = st.text_input(
                    "📅 Fecha (DD/MM/YYYY) *",
                    value=safe_str(datos_act.get("fecha", "")),
                    placeholder="14/04/2026"
                )
                tipos_op = ["03", "05", "06", "01", "11", "14"]
                tipo_idx = tipos_op.index(tipo_actual) if tipo_actual in tipos_op else 0
                f_tipo = st.selectbox("📄 Tipo DTE", options=tipos_op, index=tipo_idx)
            with col_f2:
                f_ctrl = st.text_input(
                    "🔢 Número de Control DTE *",
                    value=safe_str(datos_act.get("num_control_raw", datos_act.get("num_control", ""))),
                    placeholder="DTE-03-M001P003-000000000005389"
                )
                f_gen = st.text_input(
                    "🔑 UUID / Código de Generación",
                    value=safe_str(datos_act.get("gen", "")),
                    placeholder="D5DD509F-AF83-4F12-9F52-0B06F528F3E2"
                )

            f_sello = st.text_input(
                "🛡️ Sello de Recepción",
                value=safe_str(datos_act.get("sello", "")),
                placeholder="2026909C551E98104C669F113E36495EFC10AQC7"
            )

            st.markdown("**🏢 Proveedor / Emisor**")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                f_nit = st.text_input(
                    "🆔 NIT del Proveedor",
                    value=safe_str(datos_act.get("nit_prov", "")),
                    placeholder="06141911921043"
                )
            with col_r2:
                f_dui = st.text_input(
                    "🪪 DUI (si persona natural)",
                    value=safe_str(datos_act.get("dui_prov", "")),
                    placeholder="opcional"
                )
            f_nom = st.text_input(
                "🏢 Razón Social del Proveedor *",
                value=safe_str(datos_act.get("nom_prov", "")),
                placeholder="GRANJA SAN DIEGO, S.A. DE C.V."
            )

            st.markdown("**💰 Montos**")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                f_tot = st.number_input(
                    "💰 Total a Pagar ($) *",
                    value=float(datos_act.get("tot", 0.0)),
                    format="%.2f", min_value=0.0
                )
            with col_m2:
                f_gra = st.number_input(
                    "🧾 Compra Gravada ($)",
                    value=float(datos_act.get("gra", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Sin IVA. Dejar en 0 para calcular."
                )
            with col_m3:
                f_iva = st.number_input(
                    "🏦 IVA Crédito Fiscal ($)",
                    value=float(datos_act.get("iva", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Dejar en 0 para calcular (13% de gravadas)."
                )

            col_m4, col_m5 = st.columns(2)
            with col_m4:
                f_exe = st.number_input(
                    "⛽ Compras Exentas/NS ($)",
                    value=float(datos_act.get("exe", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Incluye Fovial + Cotrans para combustible."
                )
            with col_m5:
                f_ret = st.number_input(
                    "🔻 IVA Retenido ($)",
                    value=float(datos_act.get("ret", 0.0)),
                    format="%.2f", min_value=0.0
                )

            if f_tot > 0:
                gra_p = f_gra if f_gra > 0 else round((f_tot - f_exe + f_ret) / 1.13, 2)
                iva_p = f_iva if f_iva > 0 else round(gra_p * 0.13, 2)
                st.caption(
                    f"📊 Preview: Gravadas `${gra_p:.2f}` | IVA `${iva_p:.2f}` | "
                    f"Exentas `${f_exe:.2f}` | Total `${f_tot:.2f}`"
                )

            actualizar_otros = st.checkbox(
                "🔄 Actualizar nombre en todos los registros del proveedor", value=True
            )

            st.markdown("")
            b1, b2, b3 = st.columns([2, 1, 1])
            with b1:
                submit_ok   = st.form_submit_button("✅ Aprobar y Agregar", type="primary", use_container_width=True)
            with b2:
                submit_skip = st.form_submit_button("⏭️ Saltar", use_container_width=True)
            with b3:
                submit_del  = st.form_submit_button("🗑️ Descartar", use_container_width=True)

            if submit_ok:
                errores = []
                if not f_fecha.strip():  errores.append("Fecha requerida.")
                if not f_ctrl.strip():   errores.append("Número de Control requerido.")
                if not f_nom.strip():    errores.append("Razón Social del Proveedor requerida.")
                if f_tot <= 0:           errores.append("Total debe ser mayor a 0.")
                if f_fecha.strip() and not re.match(r'\d{2}/\d{2}/\d{4}', f_fecha.strip()):
                    errores.append("Formato de fecha inválido. Use DD/MM/YYYY.")

                if errores:
                    for e_msg in errores:
                        st.error(e_msg)
                else:
                    nombre_limpio = f_nom.strip().upper()
                    nit_act       = f_nit.strip()
                    dui_act       = re.sub(r'[^0-9]', '', f_dui.strip()) if f_dui.strip() else ""
                    ctrl_raw      = f_ctrl.strip().upper()
                    ctrl_limpio   = ctrl_raw.replace("-", "")
                    gen_raw       = f_gen.strip().upper()
                    gen_sin_g     = gen_raw.replace("-", "")

                    id_guardar = nit_act or dui_act
                    if id_guardar:
                        guardar_proveedor_rapido(id_guardar, nombre_limpio)

                    for item_pend in st.session_state.cola_revision[1:]:
                        if item_pend["datos"].get("nit_prov") == nit_act and nit_act:
                            item_pend["datos"]["nom_prov"] = nombre_limpio
                            item_pend["datos"]["es_nuevo"] = False

                    if actualizar_otros and id_guardar:
                        actualizar_nombre_en_db(id_guardar, nombre_limpio)

                    gra_f = f_gra
                    iva_f = f_iva
                    ic    = datos_act.get("iva_calc", False)

                    if f_tot > 0 and gra_f == 0.0 and iva_f == 0.0:
                        gra_f = round((f_tot - f_exe + f_ret) / 1.13, 2)
                        iva_f = round(f_tot - f_exe + f_ret - gra_f, 2)
                        ic    = True
                    elif f_tot > 0 and iva_f == 0.0 and gra_f > 0.0:
                        iva_f = round(gra_f * 0.13, 2)
                        ic    = True

                    datos_act.update({
                        "fecha"          : f_fecha.strip(),
                        "tipo"           : f_tipo,
                        "num_control"    : ctrl_limpio,
                        "num_control_raw": ctrl_raw,
                        "sello"          : f_sello.strip().upper(),
                        "gen"            : gen_raw,
                        "gen_sin_guiones": gen_sin_g,
                        "nit_prov"       : nit_act,
                        "dui_prov"       : dui_act,
                        "nom_prov"       : nombre_limpio,
                        "exe"            : f_exe,
                        "gra"            : gra_f,
                        "iva"            : iva_f,
                        "ret"            : f_ret,
                        "tot"            : f_tot,
                        "iva_calc"       : ic,
                        "es_nuevo"       : False,
                        "archivo"        : item_actual["archivo"],
                    })

                    nuevo_df = pd.DataFrame([datos_act])
                    if st.session_state.db_compras.empty:
                        st.session_state.db_compras = nuevo_df
                    else:
                        st.session_state.db_compras = pd.concat(
                            [st.session_state.db_compras, nuevo_df], ignore_index=True
                        )

                    if id_guardar:
                        rep_act = st.session_state.get("reporte_compras") or {}
                        np_dict = rep_act.get("nuevos_proveedores", {})
                        np_dict[id_guardar] = nombre_limpio
                        if st.session_state.reporte_compras:
                            st.session_state.reporte_compras["nuevos_proveedores"] = np_dict

                    st.session_state.cola_revision.pop(0)
                    st.success("✅ Documento aprobado y agregado.")
                    st.rerun()

            if submit_skip:
                item = st.session_state.cola_revision.pop(0)
                st.session_state.cola_revision.append(item)
                st.rerun()

            if submit_del:
                st.session_state.cola_revision.pop(0)
                st.rerun()

    st.stop()

# ─────────────────────────────────────────────
# 16. REPORTE DE PROCESAMIENTO
# ─────────────────────────────────────────────
if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### 📋 Alertas de Procesamiento")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        alerta_con_lista("error" if rep.get("corruptos") else "success",
                         "💀", "Dañados", rep.get("corruptos", []))
    with c2:
        alerta_con_lista("warning" if rep.get("invalidos") else "success",
                         "⚠️", "Ignorados (tipo incorrecto)", rep.get("invalidos", []))
    with c3:
        alerta_con_lista("error" if rep.get("duplicados") else "success",
                         "🛑", "Duplicados", rep.get("duplicados", []))
    with c4:
        alerta_con_lista("info" if rep.get("iva_calc") else "success",
                         "🧮", "IVA Calculado", rep.get("iva_calc", []))

    np_dict = rep.get("nuevos_proveedores", {})
    if np_dict:
        st.markdown(f"**🆕 Proveedores nuevos guardados:** `{len(np_dict)}`")
        with st.expander("Ver proveedores registrados"):
            for nit_k, nom_k in np_dict.items():
                st.markdown(f"- `{nit_k}` — **{nom_k}**")

    st.divider()

# ─────────────────────────────────────────────
# 17. TABLA PRINCIPAL Y EXPORT
# ─────────────────────────────────────────────
if not st.session_state.db_compras.empty:
    df = st.session_state.db_compras.copy()

    # Asegurar columnas necesarias
    for col in ['gen_sin_guiones', 'num_control_raw', 'sello', 'dui_prov',
                'fovial', 'cotrans', 'num_control']:
        if col not in df.columns:
            df[col] = ""

    st.markdown("### 🔍 Filtros de Auditoría")
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("Buscar proveedor 🔎", placeholder="Nombre, NIT, DUI o UUID…")
    with col_f2:
        tipos_disponibles = df['tipo'].unique().tolist() if 'tipo' in df.columns else []
        filtro_tipo = st.multiselect(
            "Tipo DTE 📄",
            options=tipos_disponibles,
            default=tipos_disponibles
        )

    df_filtrado = df.copy()
    if busqueda:
        t_bus = busqueda.upper()
        mask = (
            df_filtrado['nom_prov'].str.contains(t_bus, case=False, na=False) |
            df_filtrado['nit_prov'].str.contains(t_bus, na=False)             |
            df_filtrado['dui_prov'].str.contains(t_bus, na=False)             |
            df_filtrado['gen'].str.contains(t_bus, case=False, na=False)      |
            df_filtrado['num_control'].str.contains(t_bus, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask]
    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]

    st.divider()

    tab1, tab2, tab3 = st.tabs([
        "📊 Libro F-07 Compras (Anexo 3)",
        "🔍 Auditoría Completa",
        "📈 Resumen por Proveedor"
    ])

    with tab1:
        if not df_filtrado.empty:
            df_f07 = construir_df_f07_compras(df_filtrado)
            COLS_NUM = [c for c in df_f07.columns if df_f07[c].dtype == float]
            st.dataframe(
                df_f07.style.format({c: "{:.2f}" for c in COLS_NUM}),
                hide_index=True, use_container_width=True
            )

            # Resumen de totales
            ETIQUETAS = {
                "G. Compras Exentas/NS"   : "Exentas/NS",
                "J. Compras Gravadas"      : "Gravadas",
                "N. Crédito Fiscal (IVA)"  : "IVA",
                "O. Total Compras"         : "Total General",
            }
            partes = []
            for col_key, etiqueta in ETIQUETAS.items():
                if col_key in df_f07.columns:
                    suma = df_f07[col_key].sum()
                    if suma > 0 or etiqueta == "Total General":
                        marcador = "**🟢**" if etiqueta == "Total General" else "**"
                        cierre   = "**" if etiqueta != "Total General" else "**"
                        partes.append(f"{marcador} {etiqueta}:{cierre} `${suma:,.2f}`")
            if partes:
                st.markdown("> " + " &nbsp;|&nbsp; ".join(partes))

            st.markdown("---")
            st.caption(
                "ℹ️ **Columnas Q-T** (Tipo Operación, Clasificación, Sector, Tipo Costo/Gasto) "
                "tienen valores por defecto. Ajústalos según la naturaleza del gasto antes de subir a Hacienda."
            )
            if st.button("📥 Generar Excel para Hacienda", type="primary"):
                ventana_descarga_compras(
                    df_f07,
                    f"F07_Compras_{safe_str(cliente.get('nombre','')).replace(' ','_')}.xlsx"
                )
        else:
            st.info("Sin compras que mostrar con el filtro actual.")

    with tab2:
        st.write(f"📊 Registros: **{len(df_filtrado)}** de **{len(df)}**")
        # Vista de auditoría con columnas clave
        cols_auditoria = ['fecha', 'tipo', 'nom_prov', 'nit_prov', 'exe', 'gra', 'iva', 'tot',
                          'fovial', 'cotrans', 'gen', 'num_control_raw', 'sello', 'archivo']
        cols_disp = [c for c in cols_auditoria if c in df_filtrado.columns]
        st.dataframe(df_filtrado[cols_disp], use_container_width=True, hide_index=True)

    with tab3:
        if not df_filtrado.empty:
            resumen = df_filtrado.groupby('nom_prov').agg(
                Docs=('tot', 'count'),
                NIT=('nit_prov', 'first'),
                Exentas=('exe', 'sum'),
                Gravadas=('gra', 'sum'),
                IVA=('iva', 'sum'),
                Total=('tot', 'sum'),
            ).reset_index()
            resumen.columns = ['Proveedor', 'Docs', 'NIT', 'Exentas', 'Gravadas', 'IVA', 'Total']
            resumen = resumen.sort_values('Total', ascending=False)

            COLS_MONTO = ['Exentas', 'Gravadas', 'IVA', 'Total']
            st.dataframe(
                resumen.style.format({c: "${:,.2f}" for c in COLS_MONTO}),
                hide_index=True, use_container_width=True
            )

            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("Total Compras", f"${df_filtrado['tot'].sum():,.2f}")
            col_r2.metric("Crédito Fiscal", f"${df_filtrado['iva'].sum():,.2f}")
            col_r3.metric("Exentas/NS", f"${df_filtrado['exe'].sum():,.2f}")
        else:
            st.info("Sin datos para mostrar.")

else:
    st.markdown("""
    <div style="text-align:center; padding:60px 20px;">
        <h3 style="color:#8A9A35 !important;">📂 Sin documentos cargados</h3>
        <p style="color:#4A5520 !important;">
            Usa el panel lateral para cargar y procesar PDFs de compras.<br>
            Acepta: CCF (03), NC (05), ND (06), Factura (01/11), Suj. Excluido (14)
        </p>
    </div>
    """, unsafe_allow_html=True)
