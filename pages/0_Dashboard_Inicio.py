import streamlit as st
import pandas as pd
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from styles import DARK_PRO_CSS

# ─────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard · Learnix DTE Hub",
    layout="wide",
    page_icon="🏠"
)

# ─────────────────────────────────────────────
# 2. SEGURIDAD — Multi-tenant SaaS
# ─────────────────────────────────────────────
from utils.auth_guard import check_auth
check_auth()   # Verifica sesión + suscripción activa

# ─────────────────────────────────────────────
# 3. ESTILOS
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 4. CARGA DE CLIENTES
# ─────────────────────────────────────────────
def cargar_clientes() -> dict:
    archivo = os.path.join(os.path.dirname(__file__), "..", "data", "clientes.json")
    if not os.path.exists(archivo):
        return {}
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Error de formato en el archivo de clientes: {e}")
        return {}
    except Exception as e:
        st.warning(f"⚠️ No se pudo cargar el directorio de clientes: {e}")
        return {}

# ─────────────────────────────────────────────
# 5. ENCABEZADO
# ─────────────────────────────────────────────
col_logo, col_hdr, col_badge = st.columns([1, 6, 2])
with col_logo:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #A8E870;"
        " letter-spacing: 3px; margin-top:14px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_hdr:
    st.markdown("<div class='bienvenida-titulo'>Hub DTE — El Salvador</div>", unsafe_allow_html=True)
    st.markdown(
        "<p class='bienvenida-sub'>Procesamiento inteligente de documentos tributarios electrónicos · Anexos F-07 y F-14</p>",
        unsafe_allow_html=True
    )
with col_badge:
    st.markdown(
        "<div style='text-align:right; margin-top:18px;'>"
        "<span style='background:#152015; border:1px solid #2E4828; border-radius:20px;"
        " padding:4px 14px; font-size:0.7rem; color:#5EA830; letter-spacing:2px;'>v3.1 · PRODUCCIÓN</span>"
        "</div>",
        unsafe_allow_html=True
    )

st.divider()

# ─────────────────────────────────────────────
# 6. SELECTOR DE EMPRESA
# ─────────────────────────────────────────────
db_clientes = cargar_clientes()

_, col_sel, _ = st.columns([1, 2.2, 1])
with col_sel:
    if not db_clientes:
        st.warning("⚠️ El Directorio de Clientes está vacío. Agrégalos desde el menú lateral.")
    else:
        opciones: list[str] = ["— Selecciona una empresa —"]
        mapa: dict[str, dict] = {}

        for nit, datos in db_clientes.items():
            nombre = datos.get("nombre", "Sin nombre")
            label  = f"{nombre}  ·  {nit}"
            mapa[label] = {**datos, "nit": nit}
            opciones.append(label)

        cliente_previo = st.session_state.get("cliente_activo")
        idx_previo = 0
        if cliente_previo:
            label_previo = f"{cliente_previo.get('nombre','')}  ·  {cliente_previo.get('nit','')}"
            if label_previo in opciones:
                idx_previo = opciones.index(label_previo)

        seleccion = st.selectbox(
            "Empresa",
            opciones,
            index=idx_previo,
            help="Selecciona la empresa para la cual procesarás los DTE"
        )

        if seleccion != "— Selecciona una empresa —":
            cliente_sel = mapa[seleccion]
            if (
                not st.session_state.get("cliente_activo")
                or st.session_state["cliente_activo"].get("nit") != cliente_sel.get("nit")
            ):
                st.session_state["cliente_activo"] = cliente_sel

            st.markdown(f"""
            <div class="card-cliente-activo">
                <div class="label">Espacio de Trabajo Activo</div>
                <div class="nombre">{cliente_sel.get('nombre', '—')}</div>
                <div class="nit">NIT: {cliente_sel.get('nit', '—')}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("☝️ Selecciona una empresa para activar los módulos de procesamiento.")

st.markdown("")
st.divider()

# ─────────────────────────────────────────────
# 7. KPIs DE SESIÓN
# ─────────────────────────────────────────────
cliente_activo = st.session_state.get("cliente_activo")

if cliente_activo:
    df_ventas  = st.session_state.get("db_ventas",  pd.DataFrame())
    df_compras = st.session_state.get("db_compras", pd.DataFrame())
    df_ret     = st.session_state.get("db_ret",     pd.DataFrame())

    n_ventas  = len(df_ventas)
    n_compras = len(df_compras)
    n_ret     = len(df_ret)

    # buscar columna de totales compatible
    sum_ventas  = (
        float(df_ventas["total"].sum()) if not df_ventas.empty and "total" in df_ventas.columns
        else float(df_ventas["tot"].sum()) if not df_ventas.empty and "tot" in df_ventas.columns
        else 0.0
    )
    sum_compras = (
        float(df_compras["tot"].sum()) if not df_compras.empty and "tot" in df_compras.columns else 0.0
    )
    sum_ret = (
        float(df_ret["base"].sum()) if not df_ret.empty and "base" in df_ret.columns else 0.0
    )

    st.markdown(
        "<div style='font-size:0.72rem; color:#5EA830; letter-spacing:2px; text-transform:uppercase;"
        " font-weight:600; margin-bottom:10px;'>📊 Resumen de Sesión Actual</div>",
        unsafe_allow_html=True
    )
    k1, k2, k3, k4, k5 = st.columns(5)

    kpi_data = [
        (k1, str(n_ventas),        "DTE Ventas procesados",    "Documentos cargados"),
        (k2, f"${sum_ventas:,.0f}","Total Ventas",             "Monto acumulado"),
        (k3, str(n_compras),       "DTE Compras procesados",   "Documentos cargados"),
        (k4, f"${sum_compras:,.0f}","Total Compras",           "Monto acumulado"),
        (k5, str(n_ret),           "Retenciones DTE-07",       "Comprobantes cargados"),
    ]
    for col, val, lbl, sub in kpi_data:
        with col:
            st.markdown(f"""
            <div class="kpi-pro">
                <div class="value">{val}</div>
                <div class="label">{lbl}</div>
                <div class="sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("")
    st.divider()

# ─────────────────────────────────────────────
# 8. TARJETAS DE MÓDULOS
# ─────────────────────────────────────────────
st.markdown(
    "<div style='font-size:0.72rem; color:#5EA830; letter-spacing:2px; text-transform:uppercase;"
    " font-weight:600; margin-bottom:12px;'>🗂️ Módulos Disponibles</div>",
    unsafe_allow_html=True
)

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("""
    <div class="modulo-card">
        <span class="modulo-icon">📈</span>
        <div class="modulo-title">Extractor de Ventas — Anexo F-07</div>
        <div class="modulo-desc">
            Procesa CCF, Facturas, Notas de Crédito y Débito en PDF nativo.
            Genera el Anexo F-07 separando automáticamente ventas a contribuyentes
            (Anexo 1) y consumidores finales (Anexo 2).
        </div>
        <span class="modulo-badge">DTE-01 · DTE-03 · DTE-05 · DTE-06</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="modulo-card">
        <span class="modulo-icon">✂️</span>
        <div class="modulo-title">Retenciones 1% — Anexo F-14</div>
        <div class="modulo-desc">
            Lee Comprobantes de Retención DTE-07 y estructura el Libro de Retenciones
            para el Anexo F-14, calculando automáticamente bases gravables y montos
            retenidos por proveedor.
        </div>
        <span class="modulo-badge">DTE-07 · Casilla F-14</span>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="modulo-card">
        <span class="modulo-icon">🛒</span>
        <div class="modulo-title">Extractor de Compras — Anexo F-07</div>
        <div class="modulo-desc">
            Digitaliza compras con motor de extracción inteligente y OCR de respaldo.
            Incluye bandeja de revisión manual, detección de duplicados y directorio
            de proveedores persistente.
        </div>
        <span class="modulo-badge">DTE-03 · DTE-05 · DTE-06 · Anexo F-07</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="modulo-card">
        <span class="modulo-icon">⚖️</span>
        <div class="modulo-title">Sujetos Excluidos — Casilla 66 F-14</div>
        <div class="modulo-desc">
            Extrae datos de DTE-14 (Sujetos Excluidos) para la Casilla 66 de Compras
            y calcula automáticamente las retenciones del 10% para el formulario F-14.
        </div>
        <span class="modulo-badge">DTE-14 · Casilla 66 · Retención 10%</span>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 9. ESTADO VACÍO
# ─────────────────────────────────────────────
if not cliente_activo and db_clientes:
    st.markdown("")
    st.markdown("""
    <div style="text-align:center; padding: 32px 20px;
                border: 1px dashed #1E3020; border-radius: 12px; margin-top: 10px;">
        <p style="font-size:1.5rem; margin-bottom:6px;">☝️</p>
        <p style="color:#3A5830 !important; font-size:0.95rem;">
            Selecciona una empresa arriba para activar los módulos
            y visualizar el resumen de sesión.
        </p>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 10. FOOTER
# ─────────────────────────────────────────────
st.markdown("")
st.divider()
st.markdown(
    "<p style='text-align:center; font-size:0.72rem; color:#5EA830;'>"
    "Learnix DTE Hub &nbsp;·&nbsp; v3.1 &nbsp;·&nbsp; El Salvador &nbsp;·&nbsp; "
    "Todos los datos se procesan localmente sin envío a terceros.</p>",
    unsafe_allow_html=True
)
