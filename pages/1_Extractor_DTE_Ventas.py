import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

# ─────────────────────────────────────────────
# 1. PAGE CONFIG — SIEMPRE PRIMERO
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Extractor DTE · Ventas",
    layout="wide",
    page_icon="📈"
)

# ─────────────────────────────────────────────
# 2. ESTILOS — VERDE OLIVA ARMONIZADO
# ─────────────────────────────────────────────
ESTILO = """
<style>
  /* ── Fondos ── */
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"]          { background-color: #0D0F07 !important; }
  [data-testid="stSidebar"]         { background-color: #141A08 !important;
                                      border-right: 1px solid #4A5520 !important; }

  /* ── Tipografía global ── */
  h1, h2, h3, h4, h5, h6           { color: #C8D87A !important; letter-spacing: 1px; }
  p, label, span, li, div           { color: #F0EDD8 !important; }
  [data-testid="stDataFrame"] span  { color: inherit !important; }

  /* ── Botones primarios ── */
  div.stButton > button[kind="primary"],
  div.stDownloadButton > button[kind="primary"] {
    background-color: #6B7A2A !important;
    border: 1px solid #8A9A35 !important;
    border-radius: 6px !important;
    transition: background-color 0.25s ease, transform 0.1s ease;
  }
  div.stButton > button[kind="primary"]:hover,
  div.stDownloadButton > button[kind="primary"]:hover {
    background-color: #8A9A35 !important;
    transform: scale(1.02);
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #FFFFFF !important;
    font-weight: bold !important;
  }

  /* ── Botones secundarios ── */
  div.stButton > button[kind="secondary"] {
    background-color: transparent !important;
    border: 1px solid #4A5520 !important;
    border-radius: 6px !important;
    color: #C8D87A !important;
    transition: 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover {
    background-color: #1A2008 !important;
  }

  /* ── Tabs ── */
  button[data-baseweb="tab"]        { color: #C8D87A !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom: 2px solid #8A9A35 !important;
    color: #F0EDD8 !important;
  }

  /* ── Alertas ── */
  div[data-testid="stAlert"]        { min-height: 60px; display: flex; align-items: center; }

  /* ── Card emisor activo ── */
  .card-emisor {
    padding: 12px 16px;
    border-radius: 8px;
    border-left: 4px solid #8A9A35;
    background-color: #1A2008;
    color: #F0EDD8 !important;
    margin-bottom: 18px;
    font-size: 14px;
    line-height: 1.6;
  }
  .card-emisor strong { color: #C8D87A !important; }

  /* ── Badge de tipo doc ── */
  .badge-tipo {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background-color: #4A5520;
    color: #F0EDD8;
    font-size: 12px;
    font-weight: bold;
  }

  /* ── Separador ── */
  hr { border-color: #4A5520 !important; opacity: 0.5; }
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
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Ventas.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. CONSTANTES Y MAPEO DE TIPOS DTE
# ─────────────────────────────────────────────
TIPOS_CONTRIBUYENTE = {"03", "05", "06", "11"}

NOMBRES_TIPO = {
    "01": "Factura (CCF consumidor)",
    "03": "CCF Contribuyente",
    "05": "Nota de Crédito",
    "06": "Nota de Débito",
    "11": "Factura Exportación",
}

PALABRAS_SUCIAS = ["@", "EMAIL", "CORREO", ".COM", "HTTP", "WWW"]

MAX_VALORES_LOOP = 30  # 🔒 Límite para evitar congelamiento O(n³)

# ─────────────────────────────────────────────
# 5. FUNCIONES AUXILIARES
# ─────────────────────────────────────────────
def limpiar_monto(monto_str: str) -> float:
    """
    Convierte string de monto a float.
    Maneja formatos: 1,234.56 / 1.234,56 / 1234.56
    """
    s = re.sub(r'[^\d.,]', '', str(monto_str).strip())
    if not s:
        return 0.0

    # Detectar si el último separador es decimal
    ultimo_coma  = s.rfind(',')
    ultimo_punto = s.rfind('.')

    if ultimo_coma > ultimo_punto:
        # Formato europeo: 1.234,56
        s = s.replace('.', '').replace(',', '.')
    elif ultimo_punto > ultimo_coma:
        # Formato anglosajón: 1,234.56
        s = s.replace(',', '')
    else:
        # Sin separador decimal claro — limpiar todo
        s = s.replace(',', '').replace('.', '')

    try:
        return float(s)
    except ValueError:
        return 0.0


def es_uuid_valido(texto: str) -> bool:
    """Verifica si el string tiene formato UUID estándar."""
    return bool(re.fullmatch(
        r"[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}",
        texto.upper()
    ))


def extraer_ventas_nativo(file_bytes: bytes, cliente_activo: dict) -> dict:
    """
    Extrae datos fiscales de un DTE en PDF (texto nativo).
    Retorna dict con campos normalizados o con clave 'error'.
    """
    # ── Validación básica de bytes ──
    if not file_bytes or len(file_bytes) < 100:
        return {"error": "Archivo vacío o corrupto."}

    try:
        # ── Extracción de texto ──
        texto_completo = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            if len(pdf.pages) == 0:
                return {"error": "PDF sin páginas."}
            for page in pdf.pages:
                texto_completo += (page.extract_text() or "") + "\n"

        if len(texto_completo.strip()) < 50:
            return {"error": "PDF de imagen — sin texto extraíble. Usa OCR."}

        # ── Normalización de texto ──
        t_clean    = re.sub(r'[ \t]+', ' ', texto_completo)   # Normaliza espacios horizontales
        t_no_sp    = re.sub(r'\s+', '', t_clean).upper()       # Sin espacios, mayúsculas

        # ── Código de control / Tipo DTE ──
        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_sp)
        if not m_ctrl:
            return {"error_tipo": "No se encontró código de control DTE válido."}

        ctrl   = m_ctrl.group(1).replace("O", "0")
        m_tipo = re.search(r"DTE-(\d{2})", ctrl)
        tipo   = m_tipo.group(1) if m_tipo else "01"

        # ── UUID / Número de generación ──
        gen = ""
        m_uuid = re.search(
            r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
            t_no_sp
        )
        if m_uuid:
            limpio = m_uuid.group(1).replace("-", "")
            gen = f"{limpio[:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:]}"

        # ── Número de resolución (diferente al UUID) ──
        num_resolucion = ""
        m_resol = re.search(
            r"(?:N[uú]mero\s+de\s+Resoluci[oó]n|Resoluci[oó]n\s+N[°o]?\.?)[:\s]*([A-Z0-9\-]+)",
            t_clean, re.I
        )
        if m_resol:
            num_resolucion = m_resol.group(1).strip()

        # ── Fecha de emisión ──
        # Acepta YYYY-MM-DD o YYYY/MM/DD, valida días 01-31 y meses 01-12
        m_fecha = re.search(
            r"\b(20[2-3]\d)\s*[-\/]\s*(0[1-9]|1[0-2])\s*[-\/]\s*(0[1-9]|[12]\d|3[01])\b",
            t_clean
        )
        fecha = (
            f"{m_fecha.group(3)}/{m_fecha.group(2)}/{m_fecha.group(1)}"
            if m_fecha else ""
        )

        # ── Identificadores del emisor ──
        nit_emisor = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
        dui_emisor = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))

        # ── Datos del receptor ──
        nit_cliente = ""
        nom_cliente = (
            "CONSUMIDOR FINAL"   if tipo == "01"
            else "SIN NOMBRE"    # limpio, sin emoji para el Excel
        )

        if tipo in TIPOS_CONTRIBUYENTE:
            # Patron unificado para NIT (14 dígitos), DUI (9 dígitos), NRC
            patron_ids = (
                r"\b\d{4}\s*-?\s*\d{6}\s*-?\s*\d{3}\s*-?\s*\d\b"   # NIT formato
                r"|\b\d{14}\b"                                         # NIT plano
                r"|\b\d{8}\s*-?\s*\d\b"                               # DUI
                r"|\b\d{9}\b"                                          # NRC/otro
            )
            ids_encontrados = re.findall(patron_ids, texto_completo)
            ids_limpios = list(dict.fromkeys(
                re.sub(r'[^0-9]', '', n) for n in ids_encontrados
            ))
            candidatos = [
                n for n in ids_limpios
                if n not in (nit_emisor, dui_emisor) and len(n) >= 8
            ]
            if candidatos:
                nit_cliente = candidatos[0]

            # ── Nombre del receptor ──
            if nit_cliente:
                partes_receptor = re.split(
                    r"(?i)\b(RECEPTOR|CLIENTE\s*:|A\s*:\s*(?=\w))\b",
                    texto_completo
                )
                texto_busqueda = partes_receptor[-1] if len(partes_receptor) > 1 else texto_completo

                regex_nombre = (
                    r"(?:Nombre(?:\s+o\s+[Rr]az[oó]n\s+[Ss]ocial)?|"
                    r"Raz[oó]n\s+Social)[:\s]+(.*?)"
                    r"(?=\s*(?:NIT|NRC|Giro|Actividad|Direcci[oó]n|\n\n|$))"
                )
                m_nombre = re.search(regex_nombre, texto_busqueda, re.I | re.DOTALL)
                if m_nombre:
                    candidato = re.sub(r'\s+', ' ', m_nombre.group(1)).strip()
                    if (
                        len(candidato) > 4
                        and not any(p in candidato.upper() for p in PALABRAS_SUCIAS)
                    ):
                        nom_cliente = re.sub(r'^[\s\-_.,;:]+', '', candidato.upper())

        # ── Extracción de montos ──
        exe, gra, iva, ret, tot = 0.0, 0.0, 0.0, 0.0, 0.0

        # Retención
        m_ret = re.search(
            r"(?:IVA\s+)?(?:Retenido|Retenci[oó]n)[^\d]{0,20}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_ret:
            ret = limpiar_monto(m_ret.group(1))

        # Ventas exentas
        m_exe = re.search(
            r"(?:Ventas?\s+Exentas?|Total\s+Exento)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_exe:
            exe = limpiar_monto(m_exe.group(1))

        # Total explícito
        m_tot = re.search(
            r"(?:TOTAL\s+A\s+PAGAR|MONTO\s+TOTAL|TOTAL\s+OPERACI[OÓ]N|"
            r"VENTA\s+TOTAL|TOTAL\s+FACTURA)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_tot:
            tot = limpiar_monto(m_tot.group(1))

        # IVA explícito
        m_iva = re.search(
            r"(?:IVA\s+13%|13%\s+IVA|I\.V\.A\.?|DÉBITO\s+FISCAL)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_iva:
            iva = limpiar_monto(m_iva.group(1))

        # ── Reconciliación inteligente por triada g/i/t ──
        encontrado = False
        if not (tot > 0 and iva > 0):
            montos_raw = re.findall(
                r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                t_clean
            )
            valores = sorted(
                list({limpiar_monto(m) for m in montos_raw if limpiar_monto(m) > 0}),
                reverse=True
            )[:MAX_VALORES_LOOP]  # 🔒 Límite O(n³) controlado

            for vt in valores:
                if encontrado: break
                for vg in valores:
                    if vg >= vt: continue
                    if encontrado: break
                    for vi in valores:
                        if vi >= vg: continue
                        iva_calc = round(vg * 0.13, 2)
                        tot_calc = round(vg + vi + exe - ret, 2)
                        if abs(iva_calc - round(vi, 2)) <= 0.05 and abs(tot_calc - round(vt, 2)) <= 0.05:
                            gra, iva, tot = vg, vi, vt
                            encontrado = True
                            break

        # ── Fallback de cálculo si se tienen total + IVA ──
        if not encontrado:
            if tot > 0 and iva > 0:
                gra = round(tot - iva - exe + ret, 2)
                encontrado = True
            elif tot > 0 and iva == 0 and tipo in TIPOS_CONTRIBUYENTE:
                gra = round((tot + ret - exe) / 1.13, 2)
                iva  = round(tot + ret - exe - gra, 2)
                encontrado = True

        # ── Validación final de coherencia ──
        estado = "✅ OK"
        if tot == 0:
            estado = "⚠️ Sin total"
        elif abs(round(gra + iva + exe - ret, 2) - round(tot, 2)) > 0.10:
            estado = "⚠️ Descuadre"

        return {
            "fecha"     : fecha,
            "nit_cli"   : nit_cliente,
            "nom_cli"   : nom_cliente,
            "tipo"      : tipo,
            "tipo_desc" : NOMBRES_TIPO.get(tipo, f"Tipo {tipo}"),
            "gen"       : gen,
            "num_resol" : num_resolucion,   # ← Campo separado del UUID
            "exe"       : exe,
            "gra"       : gra,
            "iva"       : iva,
            "ret"       : ret,
            "tot"       : tot,
            "estado"    : estado,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error": "PDF inválido o con sintaxis corrupta."}
    except Exception as err:
        return {"error": f"Error inesperado: {str(err)}"}


# ─────────────────────────────────────────────
# 6. ENCABEZADO DE PÁGINA
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #8A9A35;"
        " letter-spacing: 3px; margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_titulo:
    st.title("📈 Extractor DTE — Ventas")

st.markdown(f"""
<div class="card-emisor">
    <strong>EMISOR ACTIVO:</strong> {cliente['nombre']}<br>
    <strong>NIT:</strong> {cliente['nit']}
</div>
""", unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# 7. SESSION STATE
# ─────────────────────────────────────────────
if 'db_ventas' not in st.session_state:
    st.session_state.db_ventas = pd.DataFrame()
if 'archivos_ven' not in st.session_state:
    st.session_state.archivos_ven = []   # ✅ Lista en vez de set()

# ─────────────────────────────────────────────
# 8. SIDEBAR — CARGA Y PROCESAMIENTO
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga de Ventas")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra CCF o Facturas (PDF)",
        type="pdf",
        accept_multiple_files=True,
        help="Soporta Facturas (01), CCF (03), Notas de Crédito/Débito (05/06)"
    )

    st.markdown("")
    procesar = st.button(
        "🚀 Procesar Ventas",
        type="primary",
        use_container_width=True,
        disabled=not archivos
    )
    limpiar = st.button(
        "🧹 Limpiar Todo",
        type="secondary",
        use_container_width=True
    )

    # ── Confirmar limpieza ──
    if limpiar:
        st.session_state.db_ventas    = pd.DataFrame()
        st.session_state.archivos_ven = []
        st.success("Memoria limpiada correctamente.")
        st.rerun()

    # ── Procesamiento ──
    if procesar and archivos:
        nombres_ya_procesados = set(st.session_state.archivos_ven)
        nuevos = [f for f in archivos if f.name not in nombres_ya_procesados]

        if not nuevos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            extracted  = []
            errores    = []
            bar        = st.progress(0)
            txt_estado = st.empty()
            total      = len(nuevos)

            for idx, f in enumerate(nuevos):
                txt_estado.caption(f"⏳ Procesando: `{f.name}`")
                file_bytes = f.read()
                res = extraer_ventas_nativo(file_bytes, cliente)

                if "error" in res:
                    errores.append(f"❌ `{f.name}` — {res['error']}")
                elif "error_tipo" in res:
                    errores.append(f"⚠️ `{f.name}` — {res['error_tipo']}")
                else:
                    res["archivo"] = f.name
                    extracted.append(res)

                st.session_state.archivos_ven.append(f.name)
                bar.progress((idx + 1) / total)

            txt_estado.empty()

            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_ventas.empty:
                    st.session_state.db_ventas = new_df
                else:
                    st.session_state.db_ventas = pd.concat(
                        [st.session_state.db_ventas, new_df], ignore_index=True
                    )
                st.success(f"✅ {len(extracted)} DTE procesados correctamente.")

            if errores:
                st.warning(f"⚠️ {len(errores)} archivos con error:")
                for e in errores:
                    st.markdown(e)

    # ── Resumen en sidebar ──
    if not st.session_state.db_ventas.empty:
        st.divider()
        total_docs = len(st.session_state.db_ventas)
        total_monto = st.session_state.db_ventas["tot"].sum()
        st.markdown(f"**📄 Documentos cargados:** `{total_docs}`")
        st.markdown(f"**💰 Total acumulado:** `${total_monto:,.2f}`")

# ─────────────────────────────────────────────
# 9. CONTENIDO PRINCIPAL — TABS
# ─────────────────────────────────────────────
if not st.session_state.db_ventas.empty:
    df = st.session_state.db_ventas.copy()

    tab1, tab2, tab3 = st.tabs([
        "📊 Libro F-07 (Ventas)",
        "🔍 Auditoría / Detalle",
        "📈 Resumen por Tipo"
    ])

    # ── TAB 1: Libro F-07 ──
    with tab1:
        st.markdown("#### 📋 Libro de Ventas — Formato F-07")

        # Separar por tipo
        df_consumidores   = df[~df["tipo"].isin(TIPOS_CONTRIBUYENTE)].copy()
        df_contribuyentes = df[ df["tipo"].isin(TIPOS_CONTRIBUYENTE)].copy()

        def build_f07(df_source: pd.DataFrame) -> pd.DataFrame:
            if df_source.empty:
                return pd.DataFrame()
            out = pd.DataFrame()
            out["A. Fecha Emisión"]          = df_source["fecha"]
            out["B. Clase Doc"]              = "4"
            out["C. Tipo Doc"]               = df_source["tipo"]
            out["D. Num Resolución"]         = df_source["num_resol"]  # ✅ Campo correcto
            out["E. Serie / UUID"]           = df_source["gen"]
            out["F. NIT/DUI Cliente"]        = df_source["nit_cli"]
            out["G. Nombre Cliente"]         = df_source["nom_cli"]
            out["H. Ventas Exentas"]         = df_source["exe"]
            out["I. Vtas Internas Exentas"]  = 0.00
            out["J. Ventas No Sujetas"]      = 0.00
            out["K. Ventas Gravadas Loc."]   = df_source["gra"]
            out["L. Débito Fiscal"]          = df_source["iva"]
            out["M. Ventas CTA Terceros"]    = 0.00
            out["N. Débito CTA Terceros"]    = 0.00
            out["O. IVA Retenido"]           = df_source["ret"]
            out["P. IVA Percibido"]          = 0.00
            out["Q. Total"]                  = df_source["tot"]
            out["R. Num Anexo"]              = "1"
            return out

        COLS_NUM = [
            "H. Ventas Exentas", "I. Vtas Internas Exentas", "J. Ventas No Sujetas",
            "K. Ventas Gravadas Loc.", "L. Débito Fiscal", "M. Ventas CTA Terceros",
            "N. Débito CTA Terceros", "O. IVA Retenido", "P. IVA Percibido", "Q. Total"
        ]

        if not df_consumidores.empty:
            st.markdown("##### 🧍 Ventas a Consumidores Finales (Facturas)")
            df_cons_f07 = build_f07(df_consumidores)
            st.dataframe(
                df_cons_f07.style.format({c: "{:.2f}" for c in COLS_NUM if c in df_cons_f07}),
                hide_index=True, use_container_width=True
            )
            # Totales
            st.markdown(
                f"> **Total Gravadas:** `${df_cons_f07['K. Ventas Gravadas Loc.'].sum():,.2f}` &nbsp;|&nbsp;"
                f"**IVA:** `${df_cons_f07['L. Débito Fiscal'].sum():,.2f}` &nbsp;|&nbsp;"
                f"**Total General:** `${df_cons_f07['Q. Total'].sum():,.2f}`"
            )

        if not df_contribuyentes.empty:
            st.markdown("##### 🏢 Ventas a Contribuyentes (CCF)")
            df_cont_f07 = build_f07(df_contribuyentes)
            st.dataframe(
                df_cont_f07.style.format({c: "{:.2f}" for c in COLS_NUM if c in df_cont_f07}),
                hide_index=True, use_container_width=True
            )
            st.markdown(
                f"> **Total Gravadas:** `${df_cont_f07['K. Ventas Gravadas Loc.'].sum():,.2f}` &nbsp;|&nbsp;"
                f"**IVA:** `${df_cont_f07['L. Débito Fiscal'].sum():,.2f}` &nbsp;|&nbsp;"
                f"**Total General:** `${df_cont_f07['Q. Total'].sum():,.2f}`"
            )

        # ── Exportar Excel con dos hojas ──
        st.markdown("---")
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_all_f07 = build_f07(df)
            if not df_consumidores.empty:
                build_f07(df_consumidores).to_excel(
                    writer, index=False, sheet_name='F07_Consumidores'
                )
            if not df_contribuyentes.empty:
                build_f07(df_contribuyentes).to_excel(
                    writer, index=False, sheet_name='F07_Contribuyentes'
                )
            df_all_f07.to_excel(writer, index=False, sheet_name='F07_Todo')

        st.download_button(
            "📥 Descargar Excel F-07 (todas las hojas)",
            data=output.getvalue(),
            file_name=f"F07_Ventas_{cliente['nombre'].replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

    # ── TAB 2: Auditoría ──
    with tab2:
        st.markdown("#### 🔍 Detalle de Extracción — Auditoría")
        cols_audit = [c for c in ["archivo", "fecha", "tipo", "tipo_desc",
                                   "nom_cli", "nit_cli", "exe", "gra",
                                   "iva", "ret", "tot", "estado"] if c in df.columns]
        st.dataframe(
            df[cols_audit].style.map(
                lambda v: "color: #C8D87A" if v == "✅ OK"
                else ("color: #FF8C69" if "⚠️" in str(v) else ""),
                subset=["estado"] if "estado" in cols_audit else []
            ),
            use_container_width=True, hide_index=True
        )

    # ── TAB 3: Resumen por tipo ──
    with tab3:
        st.markdown("#### 📈 Resumen Consolidado por Tipo de Documento")
        resumen = df.groupby(["tipo", "tipo_desc"]).agg(
            Cantidad    = ("tot", "count"),
            Total_Grav  = ("gra", "sum"),
            Total_IVA   = ("iva", "sum"),
            Total_Exento= ("exe", "sum"),
            Total_Ret   = ("ret", "sum"),
            Total_Gral  = ("tot", "sum"),
        ).reset_index()
        st.dataframe(
            resumen.style.format({
                "Total_Grav": "${:,.2f}", "Total_IVA": "${:,.2f}",
                "Total_Exento": "${:,.2f}", "Total_Ret": "${:,.2f}",
                "Total_Gral": "${:,.2f}"
            }),
            use_container_width=True, hide_index=True
        )

else:
    # ── Estado vacío amigable ──
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #6B7A2A;">
        <h3>📂 Sin documentos cargados</h3>
        <p style="color:#4A5520;">Usa el panel lateral para cargar y procesar PDFs de ventas.</p>
    </div>
    """, unsafe_allow_html=True)
