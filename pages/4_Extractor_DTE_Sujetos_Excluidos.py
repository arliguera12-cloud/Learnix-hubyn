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

        nit_cliente = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))

        # ── UUID ──
        gen = ""
        m_uuid = re.search(
            r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
            t_no_sp
        )
        if m_uuid:
            raw = m_uuid.group(1).replace("-", "")
            gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

        fecha = extraer_y_formatear_fecha(t_clean)

        # ── Identificador del sujeto excluido ──
        id_sujeto  = ""
        nom_sujeto = "⚠️ SUJETO NO DETECTADO"

        patron_ids = (
            r"\b\d{4}\s*-?\s*\d{6}\s*-?\s*\d{3}\s*-?\s*\d\b"
            r"|\b\d{14}\b"
            r"|\b\d{8}\s*-?\s*\d\b"
            r"|\b\d{9}\b"
        )
        ids_raw   = re.findall(patron_ids, texto_completo)
        ids_limp  = list(dict.fromkeys(re.sub(r'[^0-9]', '', n) for n in ids_raw))
        candidatos = [n for n in ids_limp if n != nit_cliente and len(n) >= 9]

        if candidatos:
            id_sujeto = candidatos[0]

        # ── Nombre del sujeto excluido ──
        m_nombre = re.search(
            r"(?:Nombre(?:\s+del\s+Sujeto)?|Sujeto\s+Excluido)[:\s]+"
            r"(.*?)(?:NIT|DUI|Direcci[oó]n|Actividad|$)",
            texto_completo, re.I
        )
        if m_nombre:
            candidato = re.sub(r'\s+', ' ', m_nombre.group(1)).strip()
            if (
                len(candidato) > 5
                and not any(b in candidato.upper() for b in ["@", "EMAIL", "CORREO", ".COM"])
            ):
                nom_sujeto = re.sub(r"^[-_.,;:]+", "", candidato.upper()).strip()
                if len(nom_sujeto) > 65:
                    nom_sujeto = "⚠️ REVISAR NOMBRE"

        # ── Montos: Monto Operación y Retención 10% ──
        base, ret = 0.0, 0.0

        # Intento 1: relación matemática 10%
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
            if any(abs(r - ret_calc) <= 0.02 for r in valores if r < v):
                base = v
                ret  = ret_calc
                break

        # Intento 2: etiquetas explícitas
        if base == 0.0:
            m_base = re.search(
                r"(?:Monto\s+de\s+la\s+Operaci[oó]n|Monto\s+Sujeto|"
                r"Total\s+Operaci[oó]n|Compra)[^\d]{0,30}"
                r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                t_clean, re.I
            )
            if m_base:
                base = limpiar_monto(m_base.group(1))

            m_ret = re.search(
                r"(?:Impuesto\s+Retenido|Retenci[oó]n\s+Renta|10%)"
                r"[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                t_clean, re.I
            )
            if m_ret:
                ret = limpiar_monto(m_ret.group(1))

            if base > 0 and ret == 0:
                ret = round(base * 0.10, 2)

        return {
            "fecha"     : fecha,
            "id_sujeto" : id_sujeto,
            "nom_sujeto": nom_sujeto,
            "tipo"      : tipo,
            "gen"       : gen,
            "base"      : base,
            "ret"       : ret,
            "estado"    : "✅ OK",
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error": "PDF inválido o corrupto."}
    except Exception as err:
        return {"error": str(err)}

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
if 'db_sujetos'       not in st.session_state: st.session_state.db_sujetos       = pd.DataFrame()
if 'archivos_suj'     not in st.session_state: st.session_state.archivos_suj     = []

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

    COLS_MOSTRAR = [c for c in ["archivo","fecha","tipo","gen","id_sujeto","nom_sujeto","base","ret","estado"] if c in df.columns]
    COLS_NUM     = [c for c in ["base", "ret"] if c in df.columns]

    st.dataframe(
        df[COLS_MOSTRAR].style.format({c: "${:,.2f}" for c in COLS_NUM}),
        hide_index=True,
        use_container_width=True
    )

    st.markdown(
        f"> **Base Total Operaciones:** `${df['base'].sum():,.2f}` &nbsp;|&nbsp;"
        f"**Retención Total 10%:** `${df['ret'].sum():,.2f}`"
    )

    st.markdown("---")

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export = df[COLS_MOSTRAR].copy()
        df_export.to_excel(writer, index=False, sheet_name='Casilla66_Sujetos')
        wb = writer.book
        ws = writer.sheets['Casilla66_Sujetos']
        fmt_num = wb.add_format({'num_format': '#,##0.00', 'align': 'right'})
        for col_idx, col_name in enumerate(COLS_MOSTRAR):
            if col_name in ('base', 'ret'):
                ws.set_column(col_idx, col_idx, 14, fmt_num)

    st.download_button(
        "📥 Descargar Casilla 66 para F-14 (Excel)",
        data=output.getvalue(),
        file_name=f"Sujetos_Excluidos_F14_{cliente['nombre'].replace(' ','_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

else:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #6B7A2A;">
        <h3 style="color:#8A9A35 !important;">📂 Sin documentos cargados</h3>
        <p style="color:#4A5520 !important;">Usa el panel lateral para cargar y procesar DTE-14 de sujetos excluidos.</p>
    </div>
    """, unsafe_allow_html=True)
