import streamlit as st
import time
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from styles import DARK_PRO_CSS

# ─────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Learnix DTE Hub",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# 2. CREDENCIALES
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
# 3. ESTILOS GLOBALES
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 4. INICIALIZACIÓN DE SESSION STATE
# ─────────────────────────────────────────────
if "autenticado"     not in st.session_state: st.session_state["autenticado"]     = False
if "intentos_login"  not in st.session_state: st.session_state["intentos_login"]  = 0
if "bloqueado_hasta" not in st.session_state: st.session_state["bloqueado_hasta"] = 0

# ─────────────────────────────────────────────
# 5. PANTALLA DE LOGIN
# ─────────────────────────────────────────────
if not st.session_state["autenticado"]:

    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_centro, _ = st.columns([1, 1.4, 1])

    with col_centro:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)

        st.markdown('<div class="login-logo">YN</div>', unsafe_allow_html=True)
        st.markdown('<span class="login-badge">LEARNIX DTE HUB</span>', unsafe_allow_html=True)
        st.markdown('<p class="login-title">Acceso al Sistema</p>', unsafe_allow_html=True)
        st.markdown('<p class="login-sub">Ingresa tus credenciales para continuar.</p>', unsafe_allow_html=True)

        st.divider()

        ahora         = time.time()
        bloqueado     = st.session_state["bloqueado_hasta"] > ahora
        seg_rest      = int(st.session_state["bloqueado_hasta"] - ahora)
        intentos_act  = st.session_state["intentos_login"]

        if bloqueado:
            st.error(
                f"⛔ Demasiados intentos fallidos. "
                f"Espera **{seg_rest}s** antes de intentar de nuevo."
            )
        else:
            if intentos_act > 0:
                restantes = max(0, 5 - intentos_act)
                st.markdown(
                    f'<div class="intentos-badge">'
                    f'⚠️ Intento {intentos_act}/5 — quedan <strong>{restantes}</strong> oportunidades'
                    f'</div>',
                    unsafe_allow_html=True
                )
                st.markdown("")

            with st.form("login_form", clear_on_submit=True):
                usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
                clave   = st.text_input("Contraseña", type="password", placeholder="••••••••")

                submitted = st.form_submit_button(
                    "Iniciar Sesión",
                    type="primary",
                    use_container_width=True
                )

                if submitted:
                    if not usuario or not clave:
                        st.error("Ingresa usuario y contraseña.")
                    elif verificar_credenciales(usuario, clave):
                        st.session_state["autenticado"]     = True
                        st.session_state["intentos_login"]  = 0
                        st.session_state["bloqueado_hasta"] = 0
                        st.success("✅ Acceso concedido. Cargando entorno...")
                        st.rerun()
                    else:
                        st.session_state["intentos_login"] += 1
                        intentos = st.session_state["intentos_login"]
                        if intentos >= 5:
                            st.session_state["bloqueado_hasta"] = time.time() + 60
                            st.error("⛔ 5 intentos fallidos. Sistema bloqueado por 60 segundos.")
                        else:
                            st.error("❌ Credenciales incorrectas.")

        st.markdown(
            '<p class="login-footer">Learnix DTE Hub v3.0 &nbsp;·&nbsp; El Salvador &nbsp;·&nbsp; Sistema Tributario DTE</p>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

# ─────────────────────────────────────────────
# 6. PÁGINAS (solo si autenticado)
# ─────────────────────────────────────────────
page_dashboard   = st.Page("pages/0_Dashboard_Inicio.py",                title="Dashboard Hub",               icon="🏠")
page_ventas      = st.Page("pages/1_Extractor_DTE_Ventas.py",            title="Extractor DTE Ventas",        icon="📈")
page_compras     = st.Page("pages/2_Extractor_DTE_Compras.py",           title="Extractor DTE Compras",       icon="🛒")
page_retenciones = st.Page("pages/3_Extractor_DTE_retenciones.py",       title="Extractor DTE Retenciones",   icon="✂️")
page_sujetos     = st.Page("pages/4_Extractor_DTE_Sujetos_Excluidos.py", title="Extractor Sujetos Excluidos", icon="⚖️")
page_clientes    = st.Page("pages/5_Directorio_Clientes.py",             title="Directorio Clientes",         icon="👥")
page_proveedores = st.Page("pages/6_Directorio_Proveedores.py",          title="Directorio Proveedores",      icon="🏢")

secciones_menu = {
    "Inicio"                   : [page_dashboard],
    "Módulos de Procesamiento" : [page_ventas, page_compras, page_retenciones, page_sujetos],
    "Administración"           : [page_clientes, page_proveedores],
}

nav = st.navigation(secciones_menu)

# ─────────────────────────────────────────────
# 7. SIDEBAR — LOGO + CLIENTE ACTIVO
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #A8E870;"
        " letter-spacing: 5px; text-align: center; margin: 10px 0 2px;'>YN</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center; font-size:0.65rem; color:#3A5830;"
        " letter-spacing:3px; margin:0 0 10px; text-transform:uppercase;'>LEARNIX DTE HUB</p>",
        unsafe_allow_html=True
    )
    st.divider()

    if st.session_state.get("cliente_activo"):
        cliente = st.session_state.cliente_activo
        st.markdown(
            f"<div style='background:linear-gradient(145deg,#111E12,#0C1810);"
            f" border:1px solid #1E3020; border-left:3px solid #5EA830;"
            f" border-radius:8px; padding:10px 13px; font-size:13px; margin-bottom:8px;'>"
            f"<span style='color:#3A5830;font-size:0.65rem;letter-spacing:1.5px;text-transform:uppercase;'>CLIENTE ACTIVO</span><br>"
            f"<strong style='color:#A8E870;font-size:0.95rem;'>{cliente.get('nombre','—')}</strong><br>"
            f"<span style='color:#6AB040;font-size:0.8rem;'>NIT: {cliente.get('nit','—')}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        st.markdown("")

# ─────────────────────────────────────────────
# 8. EJECUTAR NAVEGACIÓN
# ─────────────────────────────────────────────
nav.run()

# ─────────────────────────────────────────────
# 9. CERRAR SESIÓN
# ─────────────────────────────────────────────
with st.sidebar:
    st.divider()

    if "confirmar_logout" not in st.session_state:
        st.session_state["confirmar_logout"] = False

    if not st.session_state["confirmar_logout"]:
        if st.button("Cerrar Sesión", use_container_width=True, type="secondary"):
            st.session_state["confirmar_logout"] = True
            st.rerun()
    else:
        st.warning("¿Confirmas que deseas cerrar sesión?")
        c_si, c_no = st.columns(2)
        with c_si:
            if st.button("Sí, salir", type="primary", use_container_width=True):
                keys_a_borrar = [
                    k for k in st.session_state.keys()
                    if k not in ("intentos_login", "bloqueado_hasta")
                ]
                for k in keys_a_borrar:
                    del st.session_state[k]
                st.rerun()
        with c_no:
            if st.button("Cancelar", use_container_width=True):
                st.session_state["confirmar_logout"] = False
                st.rerun()

    st.markdown(
        "<p style='text-align:center; font-size:0.65rem; color:#1E3020;"
        " margin-top:8px;'>v3.0 · El Salvador</p>",
        unsafe_allow_html=True
    )
