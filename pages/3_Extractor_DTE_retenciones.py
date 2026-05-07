import streamlit as st
import pdfplumber
import pandas as pd
import re
import json
import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from styles import DARK_PRO_CSS
from utils.pdf_utils import (
    safe_str,
    normalizar_unicode,
    limpiar_monto,
    extraer_y_formatear_fecha,
    extraer_texto_pdf,
)
from utils.gemini_utils import (
    gemini_disponible,
    gemini_ultimo_error,
    procesar_dte_con_gemini,
)

# ─────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Extractor DTE · Retenciones", layout="wide", page_icon="✂️")

# ─────────────────────────────────────────────
# 2. ESTILOS
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. SEGURIDAD
# ─────────────────────────────────────────────
if not st.session_state.get("autenticado"):
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if not st.session_state.get("cliente_activo"):
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Retenciones.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. FUNCIONES AUXILIARES
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








def extraer_sello(texto_original: str) -> str:
    m = re.search(
        r"[Ss]ello\s+de\s+[Rr]ecepci[oó]n\s*[:\-]?\s*([A-Z0-9]{20,})",
        texto_original, re.I
    )
    if m:
        return m.group(1).strip()

    t_ns = re.sub(r'\s+', '', texto_original).upper()
    m2 = re.search(r"SELLODERECE[PC]CI[O0]N[:\-]?([A-Z0-9]{20,})", t_ns)
    if m2:
        return m2.group(1).strip()

    m3 = re.search(
        r"[Tt]ransmisi[oó]n\s+normal\s+([A-Z0-9]{20,})",
        texto_original, re.I
    )
    if m3:
        return m3.group(1).strip()

    for linea in texto_original.splitlines():
        linea_s = linea.strip()
        mc = re.match(r'^(20[2-3]\d[A-Z0-9]{26,})$', linea_s, re.I)
        if mc:
            candidato = mc.group(1).upper()
            if '-' not in candidato:
                return candidato

    return ""


def extraer_retencion_nativa(file_bytes: bytes, cliente_activo: dict) -> dict:
    if not file_bytes or len(file_bytes) < 512:
        return {"error": "Archivo vacío o corrupto."}
    try:
        texto_lineal, texto_visual = extraer_texto_pdf(file_bytes)
        texto_completo = texto_lineal + "\n" + texto_visual

        if len(texto_completo.strip()) < 50:
            return {"error": "PDF de imagen — sin texto extraíble."}

        t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
        t_no_sp = re.sub(r'\s+', '', t_clean).upper()

        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]{1,20}-\d{9,18})", t_no_sp)
        tipo   = "07"
        if m_ctrl:
            ctrl   = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo:
                tipo = m_tipo.group(1)

        if tipo != "07":
            return {"error_tipo": f"Documento DTE-{tipo}. Solo se admiten DTE-07 (Retenciones)."}

        nit_cliente = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))

        gen = ""
        m_uuid = re.search(
            r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
            t_no_sp
        )
        if m_uuid:
            raw = m_uuid.group(1).replace("-", "")
            gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

        sello = extraer_sello(t_clean)
        fecha = extraer_y_formatear_fecha(t_clean)

        nit_prov = ""
        patron_ids = (
            r"\b\d{4}\s*-?\s*\d{6}\s*-?\s*\d{3}\s*-?\s*\d\b"
            r"|\b\d{14}\b"
        )
        # Buscar en texto_completo (con espacios, captura NITs con separadores)
        ids_raw  = re.findall(patron_ids, texto_completo)
        # Fallback: buscar 14 dígitos consecutivos en texto sin espacios
        ids_raw += re.findall(r'\d{14}', t_no_sp)
        ids_limp   = list(dict.fromkeys(re.sub(r'[^0-9]', '', n) for n in ids_raw))
        candidatos = [n for n in ids_limp if n != nit_cliente and len(n) == 14]

        proveedores_db = cargar_proveedores_json()
        for n in candidatos:
            if n in proveedores_db:
                nit_prov = n
                break

        if not nit_prov and candidatos:
            nit_prov = candidatos[0]

        base, ret = 0.0, 0.0

        m_base = re.search(
            r"(?:Monto\s+[Ss]ujeto|[Ss]ujeto\s+a\s+[Rr]etenci[oó]n|"
            r"[Tt]otal\s+[Mm]onto\s+[Ss]ujeto(?:\s+a\s+[Rr]etener?)?)"
            r"[^\d$]{0,30}\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+)",
            t_clean, re.I
        )
        m_ret = re.search(
            r"(?:[Tt]otal\s+IVA\s+[Rr]etenido|[Tt]otal\s+IVA\s+[Rr]eteni"
            r"|[Ii]mpuesto\s+[Rr]etenido|[Rr]etenci[oó]n\s+1%|[Mm]onto\s+[Rr]etenci[oó]n)"
            r"[^\d$]{0,30}\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+)",
            t_clean, re.I
        )

        if m_base:
            base = limpiar_monto(m_base.group(1))
        if m_ret:
            ret = limpiar_monto(m_ret.group(1))

        if base == 0.0:
            montos_raw = re.findall(
                r"(?:US\$?|\$)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d{2,}(?:[.,]\d{1,2})?)",
                t_clean
            )
            valores = sorted(
                list({limpiar_monto(m) for m in montos_raw if limpiar_monto(m) > 0}),
                reverse=True
            )
            for v in valores:
                ret_calc = round(v * 0.01, 2)
                if any(abs(r - ret_calc) <= 0.05 for r in valores if r < v):
                    base = v
                    ret  = ret_calc
                    break

        if base > 0 and ret == 0:
            ret = round(base * 0.01, 2)

        if ret > 0 and base == 0:
            base = round(ret * 100, 2)

        # ── Verificación con Gemini ───────────────────────────────────────
        gemini_correcciones: list[str] = []
        if gemini_disponible():
            _nit_cliente = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
            _campos_act  = {"fecha": fecha, "nit_prov": nit_prov}
            _corr_dict, gemini_correcciones = procesar_dte_con_gemini(
                texto_lineal,
                "retenciones",
                _campos_act,
                {"nit": _nit_cliente, "nombre": cliente_activo.get('nombre', '')},
            )
            if _corr_dict.get("fecha"):
                fecha    = _corr_dict["fecha"]
            if _corr_dict.get("nit_prov"):
                nit_prov = _corr_dict["nit_prov"]

        return {
            "nit_prov"            : nit_prov,
            "fecha"               : fecha,
            "tipo"                : tipo,
            "sello"               : sello,
            "gen"                 : gen,
            "base"                : base,
            "ret"                 : ret,
            "estado"              : 7,
            "gemini_correcciones" : gemini_correcciones,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error": "PDF inválido o corrupto."}
    except Exception as err:
        return {"error": str(err)}


def generar_excel(df: pd.DataFrame, nombre_cliente: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Retenciones F-14"

    columnas = [
        ("NIT Proveedor",      "nit_prov", 18),
        ("Fecha",              "fecha",    14),
        ("Tipo",               "tipo",      6),
        ("Sello de Recepción", "sello",    44),
        ("Código de Gen.",     "gen",      38),
        ("Base ($)",           "base",     14),
        ("Retención ($)",      "ret",      14),
        ("Estado",             "estado",    8),
    ]

    header_fill = PatternFill("solid", fgColor="1A2C18")
    header_font = Font(bold=True, color="A8E870", size=10)
    border_side  = Side(style="thin", color="2E4828")
    cell_border  = Border(
        left=border_side, right=border_side,
        top=border_side,  bottom=border_side
    )
    num_fmt  = '#,##0.00'
    alt_fill = PatternFill("solid", fgColor="F2F7EF")

    for col_idx, (header, _, width) in enumerate(columnas, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border    = cell_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 20

    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        fill = alt_fill if row_idx % 2 == 0 else PatternFill()
        for col_idx, (_, field, _) in enumerate(columnas, start=1):
            valor = row.get(field, "")
            cell  = ws.cell(row=row_idx, column=col_idx, value=valor)
            cell.border    = cell_border
            cell.alignment = Alignment(vertical="center")
            if fill.fill_type:
                cell.fill = fill
            if field in ("base", "ret"):
                cell.number_format = num_fmt
                cell.alignment     = Alignment(horizontal="right", vertical="center")
            elif field == "estado":
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif field in ("tipo", "fecha"):
                cell.alignment = Alignment(horizontal="center", vertical="center")

    total_row = len(df) + 2
    ws.cell(row=total_row, column=5, value="TOTALES").font = Font(bold=True)
    ws.cell(row=total_row, column=5).alignment = Alignment(horizontal="right")

    base_col = [c[1] for c in columnas].index("base") + 1
    ret_col  = [c[1] for c in columnas].index("ret")  + 1

    tot_base = ws.cell(row=total_row, column=base_col, value=df["base"].sum())
    tot_ret  = ws.cell(row=total_row, column=ret_col,  value=df["ret"].sum())
    for cell in (tot_base, tot_ret):
        cell.font          = Font(bold=True, color="111E12")
        cell.number_format = num_fmt
        cell.alignment     = Alignment(horizontal="right", vertical="center")
        cell.fill          = PatternFill("solid", fgColor="A8E870")
        cell.border        = cell_border

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────
# 5. ENCABEZADO
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #A8E870;"
        " letter-spacing: 3px; margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_titulo:
    st.title("✂️ Extractor DTE — Retenciones 1%")

st.markdown(f"""
<div class="card-emisor">
    <div class="label">Agente de Retención</div>
    <div class="nombre">{cliente['nombre']}</div>
    <div class="nit">NIT: {cliente['nit']}</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 6. SESSION STATE
# ─────────────────────────────────────────────
if 'db_ret'       not in st.session_state: st.session_state.db_ret       = pd.DataFrame()
if 'archivos_ret' not in st.session_state: st.session_state.archivos_ret = []

# ─────────────────────────────────────────────
# 7. SIDEBAR — CARGA Y PROCESAMIENTO
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga DTE-07")
    st.caption("Comprobantes de Retención 1% — Formulario F-14")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra los PDFs aquí",
        type="pdf",
        accept_multiple_files=True
    )

    procesar = st.button(
        "🚀 Procesar Retenciones",
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
        st.session_state.db_ret       = pd.DataFrame()
        st.session_state.archivos_ret = []
        st.success("Memoria limpiada.")
        st.rerun()

    if procesar and archivos:
        procesados = set(st.session_state.archivos_ret)
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
                res = extraer_retencion_nativa(f.read(), cliente)

                if "error" in res:
                    errores.append(f"❌ `{f.name}` — {res['error']}")
                elif "error_tipo" in res:
                    errores.append(f"⚠️ `{f.name}` — {res['error_tipo']}")
                else:
                    res["archivo"] = f.name
                    extracted.append(res)

                st.session_state.archivos_ret.append(f.name)
                bar.progress((idx + 1) / total)

            estado_txt.empty()

            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_ret.empty:
                    st.session_state.db_ret = new_df
                else:
                    st.session_state.db_ret = pd.concat(
                        [st.session_state.db_ret, new_df], ignore_index=True
                    )
                st.success(f"✅ {len(extracted)} retenciones procesadas.")

            if errores:
                st.warning(f"⚠️ {len(errores)} con error:")
                for e in errores:
                    st.markdown(e)

    if not st.session_state.db_ret.empty:
        st.divider()
        total_base = st.session_state.db_ret["base"].sum()
        total_ret  = st.session_state.db_ret["ret"].sum()
        st.markdown(f"**📄 Documentos:** `{len(st.session_state.db_ret)}`")
        st.markdown(f"**📊 Base Total:** `${total_base:,.2f}`")
        st.markdown(f"**✂️ Ret. Total:** `${total_ret:,.2f}`")

# ─────────────────────────────────────────────
# 8. TABLA, FILTROS Y EXPORT
# ─────────────────────────────────────────────
if not st.session_state.db_ret.empty:
    df = st.session_state.db_ret.copy()

    # ── Panel de Filtros ────────────────────────────────────────────────────
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    st.markdown('<span class="filter-title">🔍 Filtros — Libro de Retenciones F-14</span>', unsafe_allow_html=True)

    ff1, ff2, ff3, ff4, ff5 = st.columns([2, 1, 1, 1, 1])
    with ff1:
        busqueda_ret = st.text_input(
            "busqueda_ret", label_visibility="collapsed",
            placeholder="Buscar NIT proveedor o Sello/UUID…"
        )
    with ff2:
        fd_desde = st.date_input("Desde", value=None, format="DD/MM/YYYY", key="ret_fd")
    with ff3:
        fd_hasta = st.date_input("Hasta", value=None, format="DD/MM/YYYY", key="ret_fh")
    with ff4:
        base_min = st.number_input("Base mín. ($)", min_value=0.0, value=0.0, step=10.0, key="ret_bm")
    with ff5:
        base_max = st.number_input("Base máx. ($)", min_value=0.0, value=0.0, step=100.0,
                                    key="ret_bx", help="0 = sin límite")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Aplicar filtros ──────────────────────────────────────────────────────
    df_fil = df.copy()

    if busqueda_ret:
        t = busqueda_ret.strip()
        mask = (
            df_fil['nit_prov'].str.contains(t, case=False, na=False) |
            df_fil['sello'].str.contains(t, case=False, na=False)    |
            df_fil['gen'].str.contains(t, case=False, na=False)
        )
        df_fil = df_fil[mask]

    def _dmy_ts(fecha_str: str):
        try:
            p = str(fecha_str).strip().split('/')
            if len(p) == 3:
                return pd.Timestamp(int(p[2]), int(p[1]), int(p[0]))
        except Exception:
            pass
        return pd.NaT

    if (fd_desde or fd_hasta) and 'fecha' in df_fil.columns:
        df_fil['_fts'] = df_fil['fecha'].apply(_dmy_ts)
        if fd_desde:
            df_fil = df_fil[df_fil['_fts'] >= pd.Timestamp(fd_desde)]
        if fd_hasta:
            df_fil = df_fil[df_fil['_fts'] <= pd.Timestamp(fd_hasta)]
        df_fil = df_fil.drop(columns=['_fts'], errors='ignore')

    if base_min > 0:
        df_fil = df_fil[df_fil['base'] >= base_min]
    if base_max > 0:
        df_fil = df_fil[df_fil['base'] <= base_max]

    # Badge de resultados
    n_tot = len(df)
    n_fil = len(df_fil)
    filtros_activos = sum([
        bool(busqueda_ret), bool(fd_desde), bool(fd_hasta),
        bool(base_min > 0), bool(base_max > 0),
    ])
    badge_extra = (f'<span class="active-filters"> · {filtros_activos} filtro(s) activo(s)</span>'
                   if filtros_activos else "")
    st.markdown(
        f'<div class="results-badge"><span class="cnt">{n_fil}</span> de {n_tot} registros{badge_extra}</div>',
        unsafe_allow_html=True
    )

    # ── Tabla principal ──────────────────────────────────────────────────────
    st.markdown("#### 📋 Libro de Retenciones — Base para Formulario F-14")

    COLS_DISPLAY = {
        "nit_prov" : "NIT Proveedor",
        "fecha"    : "Fecha",
        "tipo"     : "Tipo",
        "sello"    : "Sello de Recepción",
        "gen"      : "Código de Generación",
        "base"     : "Base ($)",
        "ret"      : "Retención ($)",
        "estado"   : "Estado",
    }

    cols_existentes = {k: v for k, v in COLS_DISPLAY.items() if k in df_fil.columns}
    df_vista = df_fil[list(cols_existentes.keys())].rename(columns=cols_existentes)

    st.dataframe(
        df_vista.style.format({
            "Base ($)"      : "${:,.2f}",
            "Retención ($)" : "${:,.2f}",
        }),
        hide_index=True,
        use_container_width=True,
        height=min(40 + len(df_vista) * 35, 600),
    )

    # Resumen de totales
    base_tot = df_fil['base'].sum() if 'base' in df_fil.columns else 0.0
    ret_tot  = df_fil['ret'].sum()  if 'ret'  in df_fil.columns else 0.0
    st.markdown(
        f"> **Base Total:** `${base_tot:,.2f}` &nbsp;|&nbsp;"
        f"**Retención Total 1%:** `${ret_tot:,.2f}`"
    )

    st.markdown("---")

    # ── Descarga Excel ───────────────────────────────────────────────────────
    col_dl1, col_dl2, _ = st.columns([2, 2, 2])
    with col_dl1:
        excel_bytes = generar_excel(df_fil, cliente['nombre'])
        st.download_button(
            "📥 Descargar Base para F-14 (Excel)",
            data=excel_bytes,
            file_name=f"Retenciones_F14_{cliente['nombre'].replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
    with col_dl2:
        csv_bytes = df_fil[list(cols_existentes.keys())].to_csv(index=False).encode("utf-8")
        st.download_button(
            "📄 Descargar CSV",
            data=csv_bytes,
            file_name=f"Retenciones_F14_{cliente['nombre'].replace(' ','_')}.csv",
            mime="text/csv",
            type="secondary",
            use_container_width=True,
        )

else:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px;">
        <p style="font-size:2.5rem; margin-bottom:8px;">📂</p>
        <h3 style="color:#6AB040 !important;">Sin documentos cargados</h3>
        <p style="color:#3A5830 !important;">
            Usa el panel lateral para cargar y procesar DTE-07 de retenciones.<br>
            El sistema extrae automáticamente base gravable y retención 1%.
        </p>
    </div>
    """, unsafe_allow_html=True)
