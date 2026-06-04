import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from styles import DARK_PRO_CSS
from utils.constants import SK


def _sum_col(df: pd.DataFrame, *cols: str) -> float:
    """Suma la primera columna disponible del DataFrame, retorna 0.0 si ninguna existe."""
    for col in cols:
        if not df.empty and col in df.columns:
            return float(df[col].sum())
    return 0.0

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
from utils.local_db import cargar_clientes_db

clientes_list: list[dict] = cargar_clientes_db()

# ─────────────────────────────────────────────
# 6. ENCABEZADO
# ─────────────────────────────────────────────
page_header(
    icon="🏠",
    title="Hub DTE — El Salvador",
    subtitle="Procesamiento inteligente de Documentos Tributarios Electrónicos · Anexos F-07 y F-14",
    badge="v5.0",
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
                <div style="font-size:1.0rem;font-weight:800;color:#FFFFFF;">{nombre_c}</div>
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
cliente_activo = st.session_state.get(SK.CLIENTE_ACTIVO)

if cliente_activo:
    df_ventas  = st.session_state.get(SK.DB_VENTAS,  pd.DataFrame())
    df_compras = st.session_state.get(SK.DB_COMPRAS, pd.DataFrame())
    df_ret     = st.session_state.get(SK.DB_RET,     pd.DataFrame())

    n_ventas  = len(df_ventas)
    n_compras = len(df_compras)
    n_ret     = len(df_ret)

    sum_ventas  = _sum_col(df_ventas,  "total", "tot")
    sum_compras = _sum_col(df_compras, "tot")
    sum_ret     = _sum_col(df_ret,     "base")

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

_MODULOS = [
    {
        "icon": "📈", "color": "#1DB8AA", "bg": "rgba(29,184,170,0.12)", "border": "rgba(29,184,170,0.25)",
        "title": "Extractor de Ventas",
        "sub": "Anexo F-07",
        "desc": "Procesa CCF, Facturas, Notas de Crédito y Débito en PDF nativo. Genera el F-07 separando ventas a contribuyentes (Anexo 1) y consumidores finales (Anexo 2).",
        "badges": ["DTE-01", "DTE-03", "DTE-05", "DTE-06"],
        "delay": "animate-delay-1",
    },
    {
        "icon": "🛒", "color": "#60A5FA", "bg": "rgba(96,165,250,0.12)", "border": "rgba(96,165,250,0.25)",
        "title": "Extractor de Compras",
        "sub": "Anexo F-07",
        "desc": "Digitaliza compras con motor de extracción inteligente y visión IA. Bandeja de revisión manual, detección de duplicados y directorio de proveedores persistente.",
        "badges": ["DTE-03", "DTE-05", "DTE-06", "F-07"],
        "delay": "animate-delay-2",
    },
    {
        "icon": "✂️", "color": "#A78BFA", "bg": "rgba(167,139,250,0.12)", "border": "rgba(167,139,250,0.25)",
        "title": "Retenciones 1%",
        "sub": "Anexo F-14",
        "desc": "Estructura el Libro de Retenciones desde DTE-07, calculando bases gravables y montos retenidos por proveedor para el formulario F-14.",
        "badges": ["DTE-07", "F-14"],
        "delay": "animate-delay-3",
    },
    {
        "icon": "⚖️", "color": "#FBBF24", "bg": "rgba(251,191,36,0.12)", "border": "rgba(251,191,36,0.25)",
        "title": "Sujetos Excluidos",
        "sub": "Casilla 66 · F-14",
        "desc": "Extrae DTE-14 y calcula automáticamente las retenciones del 10% para el formulario F-14, Casilla 66 de Compras.",
        "badges": ["DTE-14", "Casilla 66", "10%"],
        "delay": "animate-delay-4",
    },
]

c1, c2 = st.columns(2, gap="large")
cols = [c1, c2, c1, c2]

for mod, col in zip(_MODULOS, cols):
    _bg     = mod["bg"]
    _border = mod["border"]
    _color  = mod["color"]
    _icon   = mod["icon"]
    _sub    = mod["sub"]
    _title  = mod["title"]
    _desc   = mod["desc"]
    _delay  = mod["delay"]
    badges_html = "".join(
        f"<span style='background:{_bg};border:1px solid {_border};"
        f"color:{_color};font-size:0.62rem;font-weight:700;padding:2px 9px;"
        f"border-radius:99px;letter-spacing:0.5px;white-space:nowrap;'>{b}</span>"
        for b in mod["badges"]
    )
    with col:
        st.markdown(
            f"""
            <div class="modulo-card {_delay} animate-fade-in-up"
                 style="border-top:3px solid {_color};margin-bottom:14px;">
              <div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:12px;">
                <div style="width:44px;height:44px;border-radius:12px;flex-shrink:0;
                            background:{_bg};border:1px solid {_border};
                            display:flex;align-items:center;justify-content:center;
                            font-size:1.4rem;">
                  {_icon}
                </div>
                <div style="flex:1;min-width:0;">
                  <div style="font-size:0.60rem;font-weight:700;color:{_color};
                              letter-spacing:2px;text-transform:uppercase;margin-bottom:2px;">
                    {_sub}
                  </div>
                  <div class="modulo-title" style="margin-bottom:0!important;">{_title}</div>
                </div>
              </div>
              <div class="modulo-desc">{_desc}</div>
              <div style="display:flex;flex-wrap:wrap;gap:5px;">{badges_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
    "<strong>Learnix DTE Hub</strong> &nbsp;·&nbsp; v5.0 "
    "&nbsp;·&nbsp; El Salvador</p>",
    unsafe_allow_html=True,
)
