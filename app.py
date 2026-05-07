import streamlit as st
import time
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from styles import DARK_PRO_CSS

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Learnix DTE Hub",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# CREDENCIALES
# ─────────────────────────────────────────────
def verificar_credenciales(usuario: str, clave: str) -> bool:
    try:
        usr_valido = st.secrets["auth"]["usuario"]
        pwd_valido = st.secrets["auth"]["clave"]
        return usuario.strip().lower() == usr_valido.lower() and clave == pwd_valido
    except (KeyError, FileNotFoundError):
        usr_env = os.environ.get("APP_USUARIO", "")
        pwd_env = os.environ.get("APP_CLAVE",   "")
        if not usr_env or not pwd_env:
            return False
        return usuario.strip().lower() == usr_env.lower() and clave == pwd_env

# ─────────────────────────────────────────────
# ESTILOS GLOBALES
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
defaults = {
    "autenticado":     False,
    "intentos_login":  0,
    "bloqueado_hasta": 0,
    "confirmar_logout": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# PANTALLA DE LOGIN
# ─────────────────────────────────────────────
if not st.session_state["autenticado"]:

    st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])

    with col:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)

        # Logo + branding
        st.markdown('<div class="login-logo">YN</div>', unsafe_allow_html=True)
        st.markdown('<span class="login-badge">LEARNIX &nbsp;·&nbsp; DTE HUB</span>', unsafe_allow_html=True)
        st.markdown('<p class="login-title">Bienvenido de nuevo</p>', unsafe_allow_html=True)
        st.markdown('<p class="login-sub">Ingresa tus credenciales para acceder al sistema.</p>', unsafe_allow_html=True)

        # Estado de bloqueo / intentos
        ahora        = time.time()
        bloqueado    = st.session_state["bloqueado_hasta"] > ahora
        seg_rest     = int(st.session_state["bloqueado_hasta"] - ahora)
        intentos_act = st.session_state["intentos_login"]

        if bloqueado:
            st.error(
                f"⛔ Cuenta bloqueada temporalmente. "
                f"Vuelve a intentarlo en **{seg_rest} segundos**.",
                icon="🔒"
            )
        else:
            if intentos_act > 0:
                restantes = max(0, 5 - intentos_act)
                color = "#F85149" if restantes <= 1 else "#D29922"
                icono = "🔴" if restantes <= 1 else "⚠️"
                st.markdown(
                    f'<div class="intentos-badge">'
                    f'{icono} Intento {intentos_act} de 5 &nbsp;·&nbsp; '
                    f'<strong style="color:{color}">{restantes} restante{"s" if restantes != 1 else ""}</strong>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            with st.form("login_form", clear_on_submit=False):
                usuario = st.text_input(
                    "Usuario",
                    placeholder="tu.usuario",
                    label_visibility="visible"
                )
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
                    if not usuario.strip():
                        st.error("El campo usuario es obligatorio.")
                    elif not clave:
                        st.error("El campo contraseña es obligatorio.")
                    elif verificar_credenciales(usuario, clave):
                        st.session_state["autenticado"]     = True
                        st.session_state["intentos_login"]  = 0
                        st.session_state["bloqueado_hasta"] = 0
                        st.session_state["confirmar_logout"] = False
                        st.rerun()
                    else:
                        st.session_state["intentos_login"] += 1
                        n = st.session_state["intentos_login"]
                        if n >= 5:
                            st.session_state["bloqueado_hasta"] = time.time() + 60
                            st.error("⛔ Demasiados intentos. Sistema bloqueado **60 segundos**.")
                        else:
                            restantes = 5 - n
                            st.error(
                                f"Credenciales incorrectas. "
                                f"{'Último intento disponible.' if restantes == 1 else f'{restantes} intentos restantes.'}"
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
# SIDEBAR — LOGO + CLIENTE ACTIVO
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h2 style='font-family:Courier New,monospace; color:#56D364;"
        " letter-spacing:6px; text-align:center; margin:12px 0 2px; font-size:1.6rem;'>YN</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center; font-size:0.60rem; color:#6E7681;"
        " letter-spacing:3px; margin:0 0 12px; text-transform:uppercase;'>LEARNIX DTE HUB</p>",
        unsafe_allow_html=True
    )
    st.divider()

    if st.session_state.get("cliente_activo"):
        cliente = st.session_state.cliente_activo
        st.markdown(
            f"<div class='card-cliente-activo'>"
            f"<span class='label'>CLIENTE ACTIVO</span><br>"
            f"<span class='nombre'>{cliente.get('nombre','—')}</span><br>"
            f"<span class='nit'>NIT: {cliente.get('nit','—')}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── Gemini API Key (fallback de extracción) ───────────────────────────────
    try:
        _gemini_secret = st.secrets.get("gemini", {}).get("api_key", "")
    except Exception:
        _gemini_secret = ""
    if not _gemini_secret:
        with st.expander("⚡ IA · Gemini", expanded=False):
            gemini_key = st.text_input(
                "API Key Gemini 1.5 Flash",
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
# CIERRE DE SESIÓN
# ─────────────────────────────────────────────
with st.sidebar:
    st.divider()

    if not st.session_state["confirmar_logout"]:
        if st.button("↩ Cerrar sesión", use_container_width=True, type="secondary"):
            st.session_state["confirmar_logout"] = True
            st.rerun()
    else:
        st.warning("¿Confirmas cerrar sesión?")
        c_si, c_no = st.columns(2)
        with c_si:
            if st.button("Sí, salir", type="primary", use_container_width=True):
                conservar = {"intentos_login", "bloqueado_hasta"}
                for k in [k for k in st.session_state if k not in conservar]:
                    del st.session_state[k]
                st.rerun()
        with c_no:
            if st.button("Cancelar", use_container_width=True):
                st.session_state["confirmar_logout"] = False
                st.rerun()

    st.markdown(
        "<p style='text-align:center; font-size:0.62rem; color:#30363D;"
        " margin-top:10px;'>v3.1 &nbsp;·&nbsp; El Salvador</p>",
        unsafe_allow_html=True
    )
