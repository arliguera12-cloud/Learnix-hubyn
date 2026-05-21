import streamlit as st
import pandas as pd
import sys
import os

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
# 2. SEGURIDAD
# ─────────────────────────────────────────────
from utils.auth_guard import check_auth
check_auth()

# ─────────────────────────────────────────────
# 3. ESTILOS
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 4. COMPONENTES UI
# ─────────────────────────────────────────────
from components.ui_components import (
    page_header, section_label, kpi_card,
    empty_state, sidebar_cliente_card,
)

# ─────────────────────────────────────────────
# 5. CARGA DE CLIENTES
# ─────────────────────────────────────────────
from utils.supabase_client import cargar_clientes_db

clientes_list: list[dict] = cargar_clientes_db()

# ─────────────────────────────────────────────
# 6. ENCABEZADO
# ─────────────────────────────────────────────
org_plan = (st.session_state.get("sb_organizacion") or {}).get("plan_suscripcion", "starter").upper()
page_header(
    icon="🏠",
    title="Hub DTE — El Salvador",
    subtitle="Procesamiento inteligente de Documentos Tributarios Electrónicos · Anexos F-07 y F-14",
    badge=f"v4.0 · {org_plan}",
)

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 7. SELECTOR DE EMPRESA
# ─────────────────────────────────────────────
section_label("Espacio de Trabajo", "🏢")

st.markdown('<div class="selector-empresa-wrap">', unsafe_allow_html=True)

if not clientes_list:
    st.warning("⚠️ Tu organización no tiene clientes registrados. Agrégalos en **Directorio Clientes**.")
else:
    opciones: list[str] = ["— Selecciona una empresa —"]
    mapa: dict[str, dict] = {}

    for cliente in clientes_list:
        nombre = cliente.get("nombre_comercial", "Sin nombre")
        nit    = cliente.get("nit", "")
        label  = f"{nombre}  ·  {nit}"
        mapa[label] = {
            "id":        cliente.get("id"),
            "nit":       nit,
            "nombre":    nombre,
            "nrc":       cliente.get("nrc", ""),
            "dui":       cliente.get("dui", ""),
            "actividad": cliente.get("actividad", ""),
        }
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
        help="Selecciona la empresa de tu organización para la cual procesarás los DTE",
        label_visibility="collapsed",
    )

    if seleccion != "— Selecciona una empresa —":
        cliente_sel = mapa[seleccion]
        if (
            not st.session_state.get("cliente_activo")
            or st.session_state["cliente_activo"].get("nit") != cliente_sel.get("nit")
        ):
            st.session_state["cliente_activo"] = cliente_sel

        # Card de cliente activo inline
        nombre_c = cliente_sel.get("nombre", "—")
        nit_c    = cliente_sel.get("nit", "—")
        nrc_c    = cliente_sel.get("nrc", "")
        act_c    = cliente_sel.get("actividad", "")
        st.markdown(
            f"""
            <div style="margin-top:12px;background:var(--accent-light);
                        border:1px solid var(--border-accent);border-radius:var(--radius);
                        padding:14px 18px;display:flex;align-items:center;gap:14px;">
              <div style="width:42px;height:42px;background:var(--accent);border-radius:10px;
                          display:flex;align-items:center;justify-content:center;
                          font-size:1.4rem;flex-shrink:0;">🏢</div>
              <div style="flex:1;min-width:0;">
                <div style="font-size:0.60rem;font-weight:700;color:var(--accent-dark);
                            letter-spacing:2px;text-transform:uppercase;margin-bottom:2px;">
                  Espacio de Trabajo Activo
                </div>
                <div style="font-size:1.0rem;font-weight:800;color:var(--navy);">{nombre_c}</div>
                <div style="font-size:0.75rem;color:var(--text-secondary);
                            font-family:'Courier New',monospace;margin-top:2px;">
                  NIT: {nit_c}
                  {f" &nbsp;·&nbsp; NRC: {nrc_c}" if nrc_c else ""}
                  {f" &nbsp;·&nbsp; {act_c}" if act_c else ""}
                </div>
              </div>
              <span class="status-badge ok">&#x25CF;&nbsp;Activo</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info("☝️ Selecciona una empresa para activar los módulos de procesamiento.")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 8. KPIs DE SESIÓN
# ─────────────────────────────────────────────
cliente_activo = st.session_state.get("cliente_activo")

if cliente_activo:
    df_ventas  = st.session_state.get("db_ventas",  pd.DataFrame())
    df_compras = st.session_state.get("db_compras", pd.DataFrame())
    df_ret     = st.session_state.get("db_ret",     pd.DataFrame())

    n_ventas  = len(df_ventas)
    n_compras = len(df_compras)
    n_ret     = len(df_ret)

    sum_ventas = (
        float(df_ventas["total"].sum())  if not df_ventas.empty  and "total" in df_ventas.columns
        else float(df_ventas["tot"].sum()) if not df_ventas.empty  and "tot"   in df_ventas.columns
        else 0.0
    )
    sum_compras = (
        float(df_compras["tot"].sum()) if not df_compras.empty and "tot" in df_compras.columns else 0.0
    )
    sum_ret = (
        float(df_ret["base"].sum()) if not df_ret.empty and "base" in df_ret.columns else 0.0
    )

    section_label("Resumen de Sesión Actual", "📊")

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        kpi_card(str(n_ventas), "DTE Ventas", "Procesados en sesión", icon="📈", accent="teal", animate_delay=1)
    with k2:
        kpi_card(f"${sum_ventas:,.2f}", "Total Ventas", "Monto acumulado", icon="💰", accent="green", animate_delay=2)
    with k3:
        kpi_card(str(n_compras), "DTE Compras", "Procesados en sesión", icon="🛒", accent="blue", animate_delay=3)
    with k4:
        kpi_card(f"${sum_compras:,.2f}", "Total Compras", "Monto acumulado", icon="💳", accent="amber", animate_delay=4)
    with k5:
        kpi_card(str(n_ret), "Retenciones", "DTE-07 cargados", icon="✂️", accent="purple", animate_delay=5)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 9. TARJETAS DE MÓDULOS
# ─────────────────────────────────────────────
section_label("Módulos Disponibles", "🗂️")

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("""
    <div class="modulo-card animate-fade-in-up animate-delay-1">
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
    <div class="modulo-card animate-fade-in-up animate-delay-3">
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
    <div class="modulo-card animate-fade-in-up animate-delay-2">
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
    <div class="modulo-card animate-fade-in-up animate-delay-4">
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
# 10. ESTADO VACÍO (sin cliente seleccionado)
# ─────────────────────────────────────────────
if not cliente_activo and clientes_list:
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    empty_state(
        icon="☝️",
        title="Selecciona una empresa para comenzar",
        subtitle="Elige una empresa en el selector de arriba para activar los módulos y visualizar el resumen de sesión.",
        action_hint="→ Usa el selector de empresa en la parte superior de esta página",
    )

# ─────────────────────────────────────────────
# 11. FOOTER
# ─────────────────────────────────────────────
st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.markdown(
    "<p class='app-footer'>"
    "<strong>Learnix DTE Hub</strong> &nbsp;·&nbsp; v4.0 SaaS "
    "&nbsp;·&nbsp; El Salvador &nbsp;·&nbsp; "
    "Datos aislados por organización vía Supabase RLS</p>",
    unsafe_allow_html=True,
)
