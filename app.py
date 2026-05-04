import streamlit as st
import time
import os

# ─────────────────────────────────────────────
# 1. PAGE CONFIG — PRIMERA LÍNEA OBLIGATORIA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title = "Learnix DTE Hub",
    layout     = "wide",         # ✅ wide para consistencia con páginas internas
    page_icon  = "⚡",
    initial_sidebar_state = "collapsed"  # Sidebar oculto en login
)

# ─────────────────────────────────────────────
# 2. CREDENCIALES — Variables de entorno
#    En local: crea un archivo .env o usa st.secrets
#    En Streamlit Cloud: define en Secrets (Settings > Secrets)
#
#    Formato en secrets.toml:
#    [auth]
#    usuario = "admin"
#    clave   = "tu_clave_segura"
# ─────────────────────────────────────────────
def verificar_credenciales(usuario: str, clave: str) -> bool:
    """
    Valida credenciales contra st.secrets o variables de entorno.
    Nunca hardcodear en el código fuente.
    """
    try:
        # ✅ Método 1: Streamlit Secrets (recomendado para Cloud)
        usr_valido = st.secrets["auth"]["usuario"]
        pwd_valido = st.secrets["auth"]["clave"]
        return usuario.strip().lower() == usr_valido.lower() and clave == pwd_valido
    except (KeyError, FileNotFoundError):
        # ✅ Método 2: Variables de entorno (para Docker/local)
        usr_env = os.environ.get("APP_USUARIO", "admin")
        pwd_env = os.environ.get("APP_CLAVE",   "learnix2026")
        return usuario.strip().lower() == usr_env.lower() and clave == pwd_env

# ─────────────────────────────────────────────
# 3. ESTILOS GLOBALES — VERDE OLIVA UNIFICADO
#    Aplican tanto en login como en páginas internas
# ─────────────────────────────────────────────
ESTILO_GLOBAL = """
<style>
  /* ── Fondos ── */
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"]          { background-color: #0D0F07 !important; }
  [data-testid="stSidebar"]         { background-color: #141A08 !important;
                                      border-right: 1px solid #4A5520 !important; }

  /* ── Tipografía global ── */
  h1, h2, h3, h4, h5, h6           { color: #C8D87A !important; }
  p, label, span, li                { color: #F0EDD8 !important; }
  [data-testid="stDataFrame"] span  { color: inherit !important; }

  /* ── Botón primario ── */
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
    color       : #FFFFFF !important;
    font-weight : bold !important;
  }

  /* ── Botón secundario ── */
  div.stButton > button[kind="secondary"] {
    background-color : transparent !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    transition       : 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover {
    background-color : #1A2008 !important;
  }
  div.stButton > button[kind="secondary"] * { color: #C8D87A !important; }

  /* ── Inputs de formulario ── */
  div[data-testid="stTextInput"] input {
    background-color : #1A2008 !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    color            : #F0EDD8 !important;
    caret-color      : #C8D87A;
  }
  div[data-testid="stTextInput"] input:focus {
    border-color : #8A9A35 !important;
    box-shadow   : 0 0 0 2px rgba(138, 154, 53, 0.25) !important;
  }
  div[data-testid="stTextInput"] input::placeholder { color: #4A5520 !important; }

  /* ── Tabs ── */
  button[data-baseweb="tab"]                    { color: #8A9A35 !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom : 2px solid #8A9A35 !important;
    color         : #F0EDD8 !important;
  }

  /* ── Alertas ── */
  div[data-testid="stAlert"] { display: flex; align-items: center; }

  /* ── Separador ── */
  hr { border-color: #4A5520 !important; opacity: 0.4; }

  /* ── Sidebar nav items ── */
  [data-testid="stSidebarNavLink"]               { color: #C8D87A !important; }
  [data-testid="stSidebarNavLink"]:hover         { background-color: #1A2008 !important; }
  [data-testid="stSidebarNavLink"][aria-current] { background-color: #2A3010 !important;
                                                   border-left: 3px solid #8A9A35; }

  /* ── LOGIN BOX ── */
  .login-box {
    background-color : #141A08;
    padding          : 44px 40px;
    border-radius    : 14px;
    border           : 1px solid #4A5520;
    box-shadow       : 0 8px 32px rgba(0, 0, 0, 0.6),
                       0 0 0 1px rgba(138, 154, 53, 0.08);
  }
  .login-logo {
    text-align   : center;
    font-family  : 'Courier New', monospace;
    font-size    : 2.8rem;
    font-weight  : bold;
    letter-spacing: 6px;
    color        : #C8D87A !important;
    margin-bottom: 4px;
    text-shadow  : 0 0 20px rgba(200, 216, 122, 0.3);
  }
  .login-title {
    text-align : center;
    color      : #F0EDD8 !important;
    font-size  : 1.1rem;
    margin-top : 0;
  }
  .login-sub {
    text-align : center;
    color      : #6B7A2A !important;
    font-size  : 0.85rem;
  }
  .badge-sistema {
    display          : inline-block;
    background-color : #1A2008;
    border           : 1px solid #4A5520;
    border-radius    : 20px;
    padding          : 2px 12px;
    font-size        : 0.75rem;
    color            : #8A9A35 !important;
    letter-spacing   : 1px;
    margin           : 0 auto 20px;
    text-align       : center;
  }
  .login-footer {
    text-align  : center;
    font-size   : 0.75rem;
    color       : #4A5520 !important;
    margin-top  : 20px;
  }
</style>
"""
st.markdown(ESTILO_GLOBAL, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 4. INICIALIZACIÓN DE SESSION STATE
# ─────────────────────────────────────────────
if "autenticado"      not in st.session_state: st.session_state["autenticado"]      = False
if "intentos_login"   not in st.session_state: st.session_state["intentos_login"]   = 0
if "bloqueado_hasta"  not in st.session_state: st.session_state["bloqueado_hasta"]  = 0

# ─────────────────────────────────────────────
# 5. PANTALLA DE LOGIN
# ─────────────────────────────────────────────
if not st.session_state["autenticado"]:

    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_centro, _ = st.columns([1, 1.6, 1])

    with col_centro:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)

        # Logo y título
        st.markdown('<div class="login-logo">YN</div>', unsafe_allow_html=True)
        st.markdown('<div style="text-align:center"><span class="badge-sistema">LEARNIX DTE HUB</span></div>', unsafe_allow_html=True)
        st.markdown('<p class="login-title">Acceso al Sistema</p>', unsafe_allow_html=True)
        st.markdown('<p class="login-sub">Ingresa tus credenciales para continuar.</p>', unsafe_allow_html=True)

        st.divider()

        # ── Bloqueo por intentos fallidos ──
        ahora = time.time()
        bloqueado = st.session_state["bloqueado_hasta"] > ahora
        segundos_restantes = int(st.session_state["bloqueado_hasta"] - ahora)

        if bloqueado:
            st.error(
                f"⛔ Demasiados intentos fallidos. "
                f"Espera **{segundos_restantes}s** antes de intentar de nuevo."
            )
        else:
            with st.form("login_form", clear_on_submit=False):
                usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
                clave   = st.text_input("Contraseña", type="password", placeholder="••••••••")

                submitted = st.form_submit_button(
                    "Iniciar Sesión",
                    type="primary",
                    use_container_width=True
                )

                if submitted:
                    if verificar_credenciales(usuario, clave):
                        # ✅ Login correcto
                        st.session_state["autenticado"]    = True
                        st.session_state["intentos_login"] = 0
                        st.session_state["bloqueado_hasta"]= 0
                        st.success("✅ Acceso concedido. Cargando entorno...")
                        st.rerun()   # ✅ Sin time.sleep() — no bloquea el hilo
                    else:
                        # ✅ Incrementar contador de intentos
                        st.session_state["intentos_login"] += 1
                        intentos = st.session_state["intentos_login"]

                        if intentos >= 5:
                            st.session_state["bloqueado_hasta"] = time.time() + 60  # Bloqueo 60s
                            st.error("⛔ 5 intentos fallidos. Sistema bloqueado por 60 segundos.")
                        else:
                            restantes = 5 - intentos
                            st.error(
                                f"❌ Credenciales incorrectas. "
                                f"Intentos restantes: **{restantes}**"
                            )

        st.markdown('<p class="login-footer">Learnix DTE Hub v2.0 &nbsp;·&nbsp; El Salvador</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

# ─────────────────────────────────────────────
# 6. DEFINICIÓN DE PÁGINAS (solo si autenticado)
# ─────────────────────────────────────────────
page_dashboard   = st.Page("pages/0_Dashboard_Inicio.py",            title="Dashboard Hub",                icon="🏠")
page_ventas      = st.Page("pages/1_Extractor_DTE_Ventas.py",        title="Extractor DTE Ventas",         icon="📈")
page_compras     = st.Page("pages/2_Extractor_DTE_Compras.py",       title="Extractor DTE Compras",        icon="🛒")  # ✅ Ruta corregida
page_retenciones = st.Page("pages/3_Extractor_DTE_retenciones.py",   title="Extractor DTE Retenciones",   icon="✂️")
page_sujetos     = st.Page("pages/4_Extractor_DTE_Sujetos_Excluidos.py", title="Extractor Sujetos Excluidos", icon="⚖️")
page_clientes    = st.Page("pages/5_Directorio_Clientes.py",         title="Directorio Clientes",          icon="👥")
page_proveedores = st.Page("pages/6_Directorio_Proveedores.py",      title="Directorio Proveedores",       icon="🏢")

secciones_menu = {
    "Inicio"                    : [page_dashboard],
    "Modulos de Procesamiento"  : [page_ventas, page_compras, page_retenciones, page_sujetos],
    "Administracion"            : [page_clientes, page_proveedores],
}

nav = st.navigation(secciones_menu)

# ─────────────────────────────────────────────
# 7. SIDEBAR — LOGO + INFO + CERRAR SESIÓN
# ─────────────────────────────────────────────
with st.sidebar:
    # Logo
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #C8D87A;"   # ✅ Color oliva
        " letter-spacing: 4px; text-align: center; margin: 8px 0;'>YN</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center; font-size:0.7rem; color:#6B7A2A;"
        " letter-spacing:1px; margin-top:-8px;'>LEARNIX DTE HUB</p>",
        unsafe_allow_html=True
    )
    st.divider()

    # Cliente activo (si existe)
    if st.session_state.get("cliente_activo"):
        cliente = st.session_state.cliente_activo
        st.markdown(
            f"<div style='background:#1A2008; border:1px solid #4A5520;"
            f" border-radius:8px; padding:10px 12px; font-size:13px;'>"
            f"<span style='color:#8A9A35; font-size:11px;'>CLIENTE ACTIVO</span><br>"
            f"<strong style='color:#C8D87A;'>{cliente.get('nombre','—')}</strong><br>"
            f"<span style='color:#6B7A2A;'>NIT: {cliente.get('nit','—')}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        st.markdown("")

# ─────────────────────────────────────────────
# 8. EJECUTAR NAVEGACIÓN
# ─────────────────────────────────────────────
nav.run()

# ─────────────────────────────────────────────
# 9. CERRAR SESIÓN — Con confirmación
# ─────────────────────────────────────────────
with st.sidebar:
    st.divider()

    if "confirmar_logout" not in st.session_state:
        st.session_state["confirmar_logout"] = False

    if not st.session_state["confirmar_logout"]:
        if st.button("Cerrar Sesion", use_container_width=True, type="secondary"):
            st.session_state["confirmar_logout"] = True
            st.rerun()
    else:
        st.warning("¿Confirmas que deseas cerrar sesión?")
        c_si, c_no = st.columns(2)
        with c_si:
            if st.button("Si, salir", type="primary", use_container_width=True):
                # ✅ Limpieza selectiva — preserva solo lo necesario
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

    # Versión al pie del sidebar
    st.markdown(
        "<p style='text-align:center; font-size:0.7rem; color:#4A5520;"
        " margin-top:8px;'>v2.0 · El Salvador</p>",
        unsafe_allow_html=True
    )
