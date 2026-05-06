import streamlit as st
import pdfplumber
import pandas as pd
import re
import json
import os
from io import BytesIO

# ─────────────────────────────────────────────
# 1. PAGE CONFIG — SIEMPRE PRIMERO
# ─────────────────────────────────────────────
st.set_page_config(page_title="Extractor DTE · Sujetos Excluidos", layout="wide", page_icon="⚖️")

# ─────────────────────────────────────────────
# 2. ESTILOS — VERDE OLIVA UNIFICADO
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
    background-color : #8A9A35 !important;
    transform        : scale(1.02);
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #FFFFFF !important; font-weight: bold !important;
  }

  div.stButton > button[kind="secondary"] {
    background-color : transparent !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    transition       : 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover { background-color: #1A2008 !important; }
  div.stButton > button[kind="secondary"] *     { color: #C8D87A !important; }

  div[data-testid="stAlert"] { display: flex; align-items: center; min-height: 56px; }
  hr                         { border-color: #4A5520 !important; opacity: 0.4; }

  .card-emisor {
    padding          : 12px 16px;
    border-radius    : 8px;
    border           : 1px solid #2A3010;
    border-left      : 4px solid #8A9A35;
    background-color : #1A2008;
    color            : #F0EDD8 !important;
    margin-bottom    : 18px;
    font-size        : 14px;
    line-height      : 1.6;
  }
  .card-emisor strong { color: #C8D87A !important; }
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. VERIFICACIÓN DE SEGURIDAD
# ─────────────────────────────────────────────
if not st.session_state.get("autenticado"):
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if not st.session_state.get("cliente_activo"):
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Sujetos Excluidos.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. FUNCIONES AUXILIARES
# ─────────────────────────────────────────────
def limpiar_monto(monto_str: str) -> float:
    s = re.sub(r'[^\d.,]', '', str(monto_str).strip())
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
    try:
        return float(s)
    except ValueError:
        return 0.0


def extraer_y_formatear_fecha(texto: str) -> str:
    m = re.search(
        r"\b(20[2-3]\d)\s*[-\/]\s*(0[1-9]|1[0-2])\s*[-\/]\s*([0-2]\d|3[01])\b",
        texto
    )
    if m:
        return f"{int(m.group(3)):02d}/{int(m.group(2)):02d}/{m.group(1)}"
    m = re.search(r"\b(\d{1,2})\s*[\/\-\.]\s*(\d{1,2})\s*[\/\-\.]\s*(20[2-3]\d)\b", texto)
    if m:
        p1, p2, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if p1 <= 12 and p2 > 12:  return f"{p2:02d}/{p1:02d}/{y}"
        if p2 <= 12 and p1 > 12:  return f"{p1:02d}/{p2:02d}/{y}"
        if p2 <= 12 and p1 <= 31: return f"{p1:02d}/{p2:02d}/{y}"
    return ""


def limpiar_nit(raw: str) -> str:
    """Devuelve solo dígitos del NIT/DUI."""
    return re.sub(r'[^0-9]', '', raw)


def extraer_sujetos_nativo(file_bytes: bytes, cliente_activo: dict) -> dict:
    if not file_bytes or len(file_bytes) < 512:
        return {"error": "Archivo vacío o corrupto."}
    try:
        texto_completo = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                return {"error": "PDF sin páginas."}
            for page in pdf.pages:
                texto_completo += (page.extract_text() or "") + "\n"

        if len(texto_completo.strip()) < 50:
            return {"error": "PDF de imagen — sin texto extraíble."}

        t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
        t_no_sp = re.sub(r'\s+', '', t_clean).upper()

        # ── Tipo DTE ──
        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_sp)
        tipo   = "14"
        if m_ctrl:
            ctrl   = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo:
                tipo = m_tipo.group(1)

        if tipo != "14":
            return {"error_tipo": f"Documento DTE-{tipo}. Solo se admiten DTE-14 (Sujetos Excluidos)."}

        nit_cliente = limpiar_nit(cliente_activo.get('nit', ''))

        # ── UUID / Código de Generación ──
        gen = ""
        m_uuid = re.search(
            r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
            t_no_sp
        )
        if m_uuid:
            raw = m_uuid.group(1).replace("-", "")
            gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

        # ── Número de Control ──
        num_control = ""
        m_nc = re.search(r"(DTE-14-[A-Z0-9]+-\d+)", t_no_sp)
        if m_nc:
            num_control = m_nc.group(1)

        fecha = extraer_y_formatear_fecha(t_clean)

        # ── Nombre del receptor (sujeto excluido) ──
        # Busca la línea que sigue a "RECEPTOR" o "Nombre o razón social:" en la sección receptor
        nom_sujeto = ""
        # Intento 1: sección RECEPTOR explícita
        m_rec = re.search(
            r"RECEPTOR\s*\n.*?[Nn]ombre\s+o\s+raz[oó]n\s+social\s*[:\-]?\s*(.+?)(?:\n|NIT|DUI|N[úu]mero)",
            texto_completo, re.S | re.I
        )
        if m_rec:
            nom_sujeto = re.sub(r'\s+', ' ', m_rec.group(1)).strip()

        # Intento 2: buscar "Nombre o razón social:" que aparezca DESPUÉS de la mitad del texto
        # (la segunda ocurrencia suele ser el receptor)
        if not nom_sujeto or len(nom_sujeto) < 4:
            nombres = re.findall(
                r"[Nn]ombre\s+o\s+raz[oó]n\s+social\s*[:\-]?\s*(.+?)(?:\n|NIT|DUI|N[úu]mero|\d{2}[\/\-])",
                texto_completo, re.I
            )
            if len(nombres) >= 2:
                nom_sujeto = re.sub(r'\s+', ' ', nombres[-1]).strip()
            elif len(nombres) == 1:
                nom_sujeto = re.sub(r'\s+', ' ', nombres[0]).strip()

        # Limpiar nombre
        nom_sujeto = nom_sujeto.strip()
        if len(nom_sujeto) > 65 or not nom_sujeto:
            nom_sujeto = "⚠️ REVISAR NOMBRE"

        # ── NIT/DUI del receptor ──
        id_sujeto = ""

        # Buscar específicamente en la sección RECEPTOR el NIT
        m_nit_rec = re.search(
            r"RECEPTOR.*?NIT\s*[:\-]?\s*([\d\-]{7,20})",
            texto_completo, re.S | re.I
        )
        if m_nit_rec:
            id_sujeto = limpiar_nit(m_nit_rec.group(1))

        # Fallback: buscar todos los IDs numéricos y excluir los del emisor
        if not id_sujeto or id_sujeto == nit_cliente:
            patron_ids = (
                r"\b\d{4}\s*-?\s*\d{6}\s*-?\s*\d{3}\s*-?\s*\d\b"   # NIT empresa
                r"|\b\d{8}\s*-?\s*\d\b"                               # DUI persona natural
                r"|\b\d{9}\b"                                          # DUI sin guión
            )
            ids_raw   = re.findall(patron_ids, texto_completo)
            ids_limp  = list(dict.fromkeys(limpiar_nit(n) for n in ids_raw))
            candidatos = [n for n in ids_limp if n != nit_cliente and len(n) >= 8]
            if candidatos:
                id_sujeto = candidatos[0]

        # ── Montos: Ventas (base), Retención Renta 10%, IVA Retenido ──
        base = 0.0
        ret  = 0.0

        # Retención Renta — etiqueta explícita (más confiable)
        m_ret_renta = re.search(
            r"[Rr]etenci[oó]n\s+[Rr]enta\s*[:\-]?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)",
            t_clean
        )
        if m_ret_renta:
            ret = limpiar_monto(m_ret_renta.group(1))

        # Sub-Total o Sumatoria de ventas — etiqueta explícita
        m_base = re.search(
            r"(?:[Ss]umatoria\s+de\s+[Vv]entas|[Ss]ub[-\s]?[Tt]otal)\s*[:\-]?\s*"
            r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)",
            t_clean
        )
        if m_base:
            base = limpiar_monto(m_base.group(1))

        # Si no encontramos base con etiqueta, intentar por relación matemática 10%
        if base == 0.0 and ret > 0:
            base = round(ret * 10, 2)

        # Si aún no tenemos base, heurística
        if base == 0.0:
            montos_raw = re.findall(
                r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                t_clean
            )
            valores = sorted(
                list({limpiar_monto(m) for m in montos_raw if limpiar_monto(m) > 0}),
                reverse=True
            )
            for v in valores:
                ret_calc = round(v * 0.10, 2)
                if any(abs(r - ret_calc) <= 0.05 for r in valores if r < v):
                    base = v
                    if ret == 0:
                        ret = ret_calc
                    break

        if base > 0 and ret == 0:
            ret = round(base * 0.10, 2)

        return {
            "fecha"      : fecha,
            "id_sujeto"  : id_sujeto,
            "nom_sujeto" : nom_sujeto,
            "tipo"       : tipo,
            "gen"        : gen,
            "num_control": num_control,
            "base"       : base,
            "ret"        : ret,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error": "PDF inválido o corrupto."}
    except Exception as err:
        return {"error": str(err)}


# ─────────────────────────────────────────────
# GENERADORES DE EXCEL — 2 formatos
# ─────────────────────────────────────────────

def generar_excel_libro(df: pd.DataFrame, nombre_cliente: str) -> bytes:
    """
    LIBRO SUJETO EXCLUIDO — columnas:
    A  B(tipo=2)  C(id_sujeto)  D(nom_sujeto)  E(fecha)  F(gen/sello_largo)
    G(num_control)  H(base)  I(0.00)  J K L M (1 1 4 5 5)
    Replica la imagen 3.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "LIBRO SUJETO EXCLUIDO"

    columnas = [
        ("",    "const_a",    4),   # A — vacío o "2" según imagen
        ("",    "const_b",    5),   # B — "2" fijo
        ("DUI/NIT",   "id_sujeto",  14),
        ("Nombre",    "nom_sujeto", 32),
        ("Fecha",     "fecha",      13),
        ("Cód. Gen.", "gen",        38),
        ("Núm. Control","num_control",38),
        ("Base ($)",  "base",       13),
        ("0.00",      "cero",        9),
        ("1","c1",4),("1","c2",4),("4","c3",4),("5","c4",4),("5","c5",4),
    ]

    header_fill = PatternFill("solid", fgColor="4A5520")
    header_font = Font(bold=True, color="FFFFFF", size=9)
    border_side = Side(style="thin", color="CCCCCC")
    cell_border  = Border(left=border_side, right=border_side,
                          top=border_side,  bottom=border_side)
    num_fmt  = '#,##0.00'
    alt_fill = PatternFill("solid", fgColor="F5F5F0")

    for col_idx, (header, _, width) in enumerate(columnas, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border    = cell_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 16

    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        fill = alt_fill if row_idx % 2 == 0 else PatternFill()
        for col_idx, (_, field, _) in enumerate(columnas, start=1):
            if field == "const_a":
                valor = ""
            elif field == "const_b":
                valor = 2
            elif field == "cero":
                valor = 0.00
            elif field.startswith("c") and field[1:].isdigit():
                valor = int(field[1:])
            else:
                valor = row.get(field, "")
            cell  = ws.cell(row=row_idx, column=col_idx, value=valor)
            cell.border    = cell_border
            cell.alignment = Alignment(vertical="center")
            if fill.fill_type:
                cell.fill = fill
            if field == "base":
                cell.number_format = num_fmt
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif field in ("fecha",):
                cell.alignment = Alignment(horizontal="center", vertical="center")

    # Totales
    total_row = len(df) + 2
    base_col  = [c[1] for c in columnas].index("base") + 1
    tot = ws.cell(row=total_row, column=base_col, value=df["base"].sum())
    tot.font = Font(bold=True)
    tot.number_format = num_fmt
    tot.alignment = Alignment(horizontal="right", vertical="center")
    tot.fill = PatternFill("solid", fgColor="C8D87A")
    tot.border = cell_border

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generar_excel_retencion(df: pd.DataFrame, nombre_cliente: str) -> bytes:
    """
    RETENCIÓN HONORARIOS — columnas:
    A(1) B(9300) C(nom_sujeto) D(id_sujeto) E(11) F(base) G(ret) H(0.00)...
    Replica la imagen 2.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "RETENCIÓN HONORARIOS"

    columnas = [
        ("",    "c1",        4),   # A — "1"
        ("Cód", "c9300",     6),   # B — "9300"
        ("Nombre",    "nom_sujeto", 32),
        ("DUI/NIT",   "id_sujeto",  13),
        ("",    "c11",       4),   # E — "11"
        ("Base ($)",  "base",       13),
        ("Ret. ($)",  "ret",        12),
        ("0.00", "cero",     8),
        ("0.00", "cero2",    8),
        ("0.00", "cero3",    8),
        ("0.00", "cero4",    8),
        ("0.00", "cero5",    8),
        ("0.00", "cero6",    8),
        ("0.00", "cero7",    8),
        ("1","d1",4),("1","d2",4),("4","d3",4),("5","d4",4),
        ("Mes/Año","mesanio",10),
    ]

    header_fill = PatternFill("solid", fgColor="4A5520")
    header_font = Font(bold=True, color="FFFFFF", size=9)
    border_side = Side(style="thin", color="CCCCCC")
    cell_border  = Border(left=border_side, right=border_side,
                          top=border_side,  bottom=border_side)
    num_fmt  = '#,##0.00'
    alt_fill = PatternFill("solid", fgColor="F5F5F0")

    for col_idx, (header, _, width) in enumerate(columnas, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border    = cell_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 16

    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        fill = alt_fill if row_idx % 2 == 0 else PatternFill()

        # Extraer mes/año de la fecha dd/mm/yyyy
        fecha_str = row.get("fecha", "")
        mesanio = ""
        mf = re.match(r"\d{2}\/(\d{2})\/(\d{4})", str(fecha_str))
        if mf:
            mesanio = f"{mf.group(1)}{mf.group(2)}"

        for col_idx, (_, field, _) in enumerate(columnas, start=1):
            if field == "c1":
                valor = 1
            elif field == "c9300":
                valor = 9300
            elif field == "c11":
                valor = 11
            elif field.startswith("cero"):
                valor = 0.00
            elif field.startswith("d") and field[1:].isdigit():
                valor = int(field[1:])
            elif field == "mesanio":
                valor = mesanio
            else:
                valor = row.get(field, "")

            cell  = ws.cell(row=row_idx, column=col_idx, value=valor)
            cell.border    = cell_border
            cell.alignment = Alignment(vertical="center")
            if fill.fill_type:
                cell.fill = fill
            if field in ("base", "ret") or field.startswith("cero"):
                cell.number_format = num_fmt
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif field in ("c1", "c9300", "c11", "d1", "d2", "d3", "d4"):
                cell.alignment = Alignment(horizontal="center", vertical="center")

    # Totales
    total_row = len(df) + 2
    base_col = [c[1] for c in columnas].index("base") + 1
    ret_col  = [c[1] for c in columnas].index("ret")  + 1

    for col_i, val in [(base_col, df["base"].sum()), (ret_col, df["ret"].sum())]:
        tot = ws.cell(row=total_row, column=col_i, value=val)
        tot.font = Font(bold=True)
        tot.number_format = num_fmt
        tot.alignment = Alignment(horizontal="right", vertical="center")
        tot.fill = PatternFill("solid", fgColor="C8D87A")
        tot.border = cell_border

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────
# 5. ENCABEZADO
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #8A9A35;"
        " letter-spacing: 3px; margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_titulo:
    st.title("⚖️ Extractor DTE — Sujetos Excluidos")

st.markdown(f"""
<div class="card-emisor">
    <strong>AGENTE DE RETENCIÓN:</strong> {cliente['nombre']}<br>
    <strong>NIT:</strong> {cliente['nit']}
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 6. SESSION STATE
# ─────────────────────────────────────────────
if 'db_sujetos'   not in st.session_state: st.session_state.db_sujetos   = pd.DataFrame()
if 'archivos_suj' not in st.session_state: st.session_state.archivos_suj = []

# ─────────────────────────────────────────────
# 7. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga DTE-14")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra DTE Sujetos Excluidos (PDF)",
        type="pdf",
        accept_multiple_files=True
    )

    procesar = st.button(
        "🚀 Procesar Documentos",
        type="primary",
        use_container_width=True,
        disabled=not archivos
    )
    limpiar = st.button(
        "🧹 Limpiar Memoria",
        type="secondary",
        use_container_width=True
    )

    if limpiar:
        st.session_state.db_sujetos   = pd.DataFrame()
        st.session_state.archivos_suj = []
        st.success("Memoria limpiada.")
        st.rerun()

    if procesar and archivos:
        procesados = set(st.session_state.archivos_suj)
        nuevos     = [f for f in archivos if f.name not in procesados]

        if not nuevos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            extracted  = []
            errores    = []
            bar        = st.progress(0)
            estado_txt = st.empty()
            total      = len(nuevos)

            for idx, f in enumerate(nuevos):
                estado_txt.caption(f"⏳ {idx+1}/{total}: `{f.name}`")
                res = extraer_sujetos_nativo(f.read(), cliente)

                if "error" in res:
                    errores.append(f"❌ `{f.name}` — {res['error']}")
                elif "error_tipo" in res:
                    errores.append(f"⚠️ `{f.name}` — {res['error_tipo']}")
                else:
                    res["archivo"] = f.name
                    extracted.append(res)

                st.session_state.archivos_suj.append(f.name)
                bar.progress((idx + 1) / total)

            estado_txt.empty()

            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_sujetos.empty:
                    st.session_state.db_sujetos = new_df
                else:
                    st.session_state.db_sujetos = pd.concat(
                        [st.session_state.db_sujetos, new_df], ignore_index=True
                    )
                st.success(f"✅ {len(extracted)} documentos procesados.")

            if errores:
                st.warning(f"⚠️ {len(errores)} con error:")
                for e in errores:
                    st.markdown(e)

    if not st.session_state.db_sujetos.empty:
        st.divider()
        total_base = st.session_state.db_sujetos["base"].sum()
        total_ret  = st.session_state.db_sujetos["ret"].sum()
        st.markdown(f"**📄 Documentos:** `{len(st.session_state.db_sujetos)}`")
        st.markdown(f"**📊 Base Total:** `${total_base:,.2f}`")
        st.markdown(f"**⚖️ Ret. Total:** `${total_ret:,.2f}`")

# ─────────────────────────────────────────────
# 8. TABLA Y EXPORT
# ─────────────────────────────────────────────
if not st.session_state.db_sujetos.empty:
    df = st.session_state.db_sujetos.copy()

    st.markdown("#### 📋 Casilla 66 — Sujetos Excluidos (Base para F-14)")

    COLS_DISPLAY = {
        "fecha"      : "Fecha",
        "id_sujeto"  : "DUI/NIT",
        "nom_sujeto" : "Nombre",
        "tipo"       : "Tipo",
        "gen"        : "Código de Gen.",
        "num_control": "Núm. Control",
        "base"       : "Base ($)",
        "ret"        : "Ret. Renta ($)",
    }
    cols_existentes = {k: v for k, v in COLS_DISPLAY.items() if k in df.columns}
    df_vista = df[list(cols_existentes.keys())].rename(columns=cols_existentes)

    st.dataframe(
        df_vista.style.format({
            "Base ($)"       : "${:,.2f}",
            "Ret. Renta ($)" : "${:,.2f}",
        }),
        hide_index=True,
        use_container_width=True,
        height=min(40 + len(df_vista) * 35, 600),
    )

    st.markdown(
        f"> **Base Total Operaciones:** `${df['base'].sum():,.2f}` &nbsp;|&nbsp;"
        f"**Retención Total 10%:** `${df['ret'].sum():,.2f}`"
    )

    st.markdown("---")

    # ── Dos botones de descarga ──
    col1, col2 = st.columns(2)

    with col1:
        excel_libro = generar_excel_libro(df, cliente['nombre'])
        st.download_button(
            "📥 Libro Sujeto Excluido (F-14)",
            data=excel_libro,
            file_name=f"Libro_Sujeto_Excluido_{cliente['nombre'].replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

    with col2:
        excel_ret = generar_excel_retencion(df, cliente['nombre'])
        st.download_button(
            "📥 Retención Honorarios (F-14)",
            data=excel_ret,
            file_name=f"Retencion_Honorarios_{cliente['nombre'].replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

else:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #6B7A2A;">
        <h3 style="color:#8A9A35 !important;">📂 Sin documentos cargados</h3>
        <p style="color:#4A5520 !important;">Usa el panel lateral para cargar y procesar DTE-14 de sujetos excluidos.</p>
    </div>
    """, unsafe_allow_html=True)
