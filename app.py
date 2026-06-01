import streamlit as st
import time
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from styles import DARK_PRO_CSS
from utils.supabase_client import login, logout
from components.ui_components import (
    sidebar_logo,
    sidebar_cliente_card,
)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Learnix DTE Hub",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# ESTILOS GLOBALES
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE — valores por defecto
# ─────────────────────────────────────────────
defaults = {
    "autenticado":      False,
    "intentos_login":   0,
    "bloqueado_hasta":  0,
    "confirmar_logout": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# PANTALLA DE LOGIN
# ─────────────────────────────────────────────
if not st.session_state["autenticado"]:

    st.markdown("<div style='height:5vh'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.1, 1])

    with col:
        st.markdown('<div class="login-box animate-fade-in-up">', unsafe_allow_html=True)

        st.markdown('<div class="login-logo">YN</div>', unsafe_allow_html=True)
        st.markdown('<span class="login-badge">LEARNIX &nbsp;·&nbsp; DTE HUB</span>', unsafe_allow_html=True)
        st.markdown('<p class="login-title">Bienvenido de nuevo</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="login-sub">Ingresa la contraseña para acceder<br>al sistema de procesamiento tributario.</p>',
            unsafe_allow_html=True
        )

        ahora        = time.time()
        bloqueado    = st.session_state["bloqueado_hasta"] > ahora
        seg_rest     = int(st.session_state["bloqueado_hasta"] - ahora)
        intentos_act = st.session_state["intentos_login"]

        if bloqueado:
            st.error(
                f"Demasiados intentos. Vuelve a intentarlo en **{seg_rest} segundos**.",
                icon="🔒"
            )
        else:
            if intentos_act > 0:
                restantes = max(0, 5 - intentos_act)
                st.markdown(
                    f'<div class="intentos-badge">'
                    f'{"🔴" if restantes <= 1 else "⚠️"} Intento {intentos_act} de 5 &nbsp;·&nbsp; '
                    f'<strong>{restantes} restante{"s" if restantes != 1 else ""}</strong>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            with st.form("login_form", clear_on_submit=False):
                clave = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="••••••••••",
                    label_visibility="visible"
                )

                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

                submitted = st.form_submit_button(
                    "Iniciar sesión →",
                    type="primary",
                    use_container_width=True
                )

                if submitted:
                    if not clave:
                        st.error("La contraseña es obligatoria.")
                    else:
                        exito, msg_error = login("", clave)
                        if exito:
                            st.session_state["confirmar_logout"] = False
                            st.rerun()
                        else:
                            st.session_state["intentos_login"] += 1
                            n = st.session_state["intentos_login"]
                            if n >= 5:
                                st.session_state["bloqueado_hasta"] = time.time() + 60
                                st.error("Demasiados intentos. Sistema bloqueado **60 segundos**.")
                            else:
                                restantes = 5 - n
                                st.error(
                                    f"{msg_error} "
                                    f"{'Último intento disponible.' if restantes == 1 else f'({restantes} intentos restantes)'}"
                                )

        st.markdown(
            '<p class="login-footer">'
            'Learnix DTE Hub &nbsp;·&nbsp; El Salvador &nbsp;·&nbsp; '
            'Sistema Tributario Electrónico'
            '</p>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

# ─────────────────────────────────────────────
# PÁGINAS (solo si autenticado)
# ─────────────────────────────────────────────
page_dashboard   = st.Page("pages/0_Dashboard_Inicio.py",                title="Dashboard Hub",               icon="🏠")
page_ventas      = st.Page("pages/1_Extractor_DTE_Ventas.py",            title="Extractor DTE Ventas",        icon="📈")
page_compras     = st.Page("pages/2_Extractor_DTE_Compras.py",           title="Extractor DTE Compras",       icon="🛒")
page_retenciones = st.Page("pages/3_Extractor_DTE_retenciones.py",       title="Extractor DTE Retenciones",   icon="✂️")
page_sujetos     = st.Page("pages/4_Extractor_DTE_Sujetos_Excluidos.py", title="Extractor Sujetos Excluidos", icon="⚖️")
page_clientes    = st.Page("pages/5_Directorio_Clientes.py",             title="Directorio Clientes",         icon="👥")
page_proveedores = st.Page("pages/6_Directorio_Proveedores.py",          title="Directorio Proveedores",      icon="🏢")

nav = st.navigation({
    "Inicio":                    [page_dashboard],
    "Módulos de Procesamiento":  [page_ventas, page_compras, page_retenciones, page_sujetos],
    "Administración":            [page_clientes, page_proveedores],
})

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    sidebar_logo()
    st.markdown(
        "<div style='margin:0 10px;border-top:1px solid rgba(255,255,255,0.07);'></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='margin:8px 10px;padding:10px 14px;"
        "background:rgba(255,255,255,0.05);border-radius:10px;"
        "border:1px solid rgba(255,255,255,0.08);'>"
        "<div style='color:#fff;font-weight:600;font-size:0.83rem;'>Learnix DTE Hub</div>"
        "<div style='color:#3B82F6;font-size:0.62rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:1.5px;'>Sistema Activo</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("cliente_activo"):
        sidebar_cliente_card(st.session_state.cliente_activo)

    try:
        _gemini_secret = st.secrets.get("gemini", {}).get("api_key", "")
    except Exception:
        _gemini_secret = ""
    if not _gemini_secret:
        with st.expander("⚡ IA · Gemini", expanded=False):
            gemini_key = st.text_input(
                "API Key Gemini 2.5 Flash",
                type="password",
                value=st.session_state.get("gemini_api_key", ""),
                placeholder="AIza...",
                help="Mejora la extracción de nombres cuando el PDF tiene formato inusual.",
                label_visibility="collapsed",
            )
            if gemini_key != st.session_state.get("gemini_api_key", ""):
                st.session_state["gemini_api_key"] = gemini_key
                st.rerun()
            if st.session_state.get("gemini_api_key"):
                st.success("Gemini activo", icon="⚡")
            else:
                st.caption("Sin clave — extracción solo con regex.")

# ─────────────────────────────────────────────
# EJECUTAR NAVEGACIÓN
# ─────────────────────────────────────────────
nav.run()

# ─────────────────────────────────────────────
# CIERRE DE SESIÓN (sidebar, después del nav)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='margin:8px 10px;border-top:1px solid rgba(255,255,255,0.07);'></div>",
        unsafe_allow_html=True,
    )

    if not st.session_state["confirmar_logout"]:
        if st.button("↩ Cerrar sesión", use_container_width=True, type="secondary"):
            st.session_state["confirmar_logout"] = True
            st.rerun()
    else:
        st.warning("¿Confirmas cerrar sesión?")
        c_si, c_no = st.columns(2)
        with c_si:
            if st.button("Sí, salir", type="primary", use_container_width=True):
                logout()
                st.rerun()
        with c_no:
            if st.button("Cancelar", use_container_width=True):
                st.session_state["confirmar_logout"] = False
                st.rerun()

    st.markdown(
        "<div class='sidebar-version'>v5.0 Local &nbsp;·&nbsp; El Salvador</div>",
        unsafe_allow_html=True,
    )
