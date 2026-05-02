# app.py
"""
Learnix Hub - Sistema Inteligente de Extracción de DTE
Versión 2.0 - Diseño oscuro minimalista
"""

import streamlit as st
import time
import json
import os
import hashlib
import importlib.util
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# 1️⃣ CONFIGURACIÓN GLOBAL
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Learnix Hub",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════
# 2️⃣ ESTILOS GLOBALES - DISEÑO ORIGINAL
# ═══════════════════════════════════════════════════════════════

estilo_custom = """
<style>
    /* ── COLORES GLOBALES ── */
    :root {
        --color-primary: #003057;
        --color-secondary: #00407A;
        --color-accent: #00E5FF;
        --color-success: #00FF00;
        --color-warning: #FFA500;
        --color-error: #FF4444;
        --color-bg-main: #000000;
        --color-bg-secondary: #0A0A0A;
        --color-bg-tertiary: #161616;
        --color-text-primary: #F7F5EE;
        --color-text-secondary: #888888;
        --color-border: #333333;
    }

    /* ── APLICACIÓN ── */
    [data-testid="stAppViewContainer"] {
        background-color: var(--color-bg-main) !important;
    }

    [data-testid="stHeader"] {
        background-color: var(--color-bg-main) !important;
        border-bottom: 1px solid var(--color-border) !important;
    }

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] {
        background-color: var(--color-bg-tertiary) !important;
        border-right: 1px solid var(--color-border) !important;
    }

    [data-testid="stSidebarContent"] {
        background-color: var(--color-bg-tertiary) !important;
    }

    /* ── TEXTO ── */
    h1, h2, h3, h4, h5, h6 {
        color: var(--color-text-primary) !important;
        font-weight: 600 !important;
    }

    p, label, span, div {
        color: var(--color-text-primary) !important;
    }

    /* ── BOTONES PRIMARIOS ── */
    div.stButton > button[kind="primary"],
    div.stDownloadButton > button[kind="primary"],
    button[data-testid="baseButton-primary"] {
        background-color: var(--color-primary) !important;
        border: 1px solid var(--color-secondary) !important;
        border-radius: 6px !important;
        color: white !important;
        font-weight: bold !important;
        transition: all 0.3s ease !important;
    }

    div.stButton > button[kind="primary"]:hover,
    div.stDownloadButton > button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover {
        background-color: var(--color-secondary) !important;
        box-shadow: 0 0 15px rgba(0, 229, 255, 0.3) !important;
    }

    /* ── BOTONES SECUNDARIOS ── */
    div.stButton > button[kind="secondary"] {
        background-color: var(--color-bg-secondary) !important;
        border: 1px solid var(--color-border) !important;
        border-radius: 6px !important;
        color: white !important;
        font-weight: bold !important;
    }

    div.stButton > button[kind="secondary"]:hover {
        background-color: var(--color-bg-tertiary) !important;
        border-color: var(--color-accent) !important;
    }

    /* ── INPUTS ── */
    input, textarea, select {
        background-color: var(--color-bg-secondary) !important;
        border: 1px solid var(--color-border) !important;
        border-radius: 6px !important;
        color: var(--color-text-primary) !important;
        padding: 8px 12px !important;
    }

    input:focus, textarea:focus, select:focus {
        border-color: var(--color-accent) !important;
        box-shadow: 0 0 10px rgba(0, 229, 255, 0.2) !important;
    }

    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: var(--color-accent) !important;
        border-bottom-color: var(--color-accent) !important;
    }

    .stTabs [data-baseweb="tab-list"] button {
        color: var(--color-text-secondary) !important;
    }

    /* ── EXPANDER ── */
    .streamlit-expanderHeader {
        background-color: var(--color-bg-secondary) !important;
        border: 1px solid var(--color-border) !important;
        color: var(--color-text-primary) !important;
    }

    /* ── ALERTS ── */
    .stAlert {
        border-radius: 6px !important;
    }

    .stSuccess {
        background-color: rgba(0, 255, 0, 0.1) !important;
        border: 1px solid var(--color-success) !important;
        color: var(--color-success) !important;
    }

    .stWarning {
        background-color: rgba(255, 165, 0, 0.1) !important;
        border: 1px solid var(--color-warning) !important;
        color: var(--color-warning) !important;
    }

    .stError {
        background-color: rgba(255, 68, 68, 0.1) !important;
        border: 1px solid var(--color-error) !important;
        color: var(--color-error) !important;
    }

    .stInfo {
        background-color: rgba(0, 229, 255, 0.1) !important;
        border: 1px solid var(--color-accent) !important;
        color: var(--color-accent) !important;
    }

    /* ── DATAFRAME ── */
    .streamlit-table {
        background-color: var(--color-bg-secondary) !important;
        border: 1px solid var(--color-border) !important;
        border-radius: 6px !important;
    }

    /* ── DIVIDER ── */
    .stHorizontalDivider {
        background-color: var(--color-border) !important;
        height: 1px !important;
    }

    /* ── CUSTOM CLASSES ── */
    .login-container {
        max-width: 500px;
        margin: 0 auto;
        padding: 40px;
        border-radius: 10px;
        border: 1px solid var(--color-border);
        background-color: var(--color-bg-secondary);
    }

    .client-box {
        padding: 12px;
        border-radius: 6px;
        border-left: 4px solid var(--color-accent);
        background-color: rgba(0, 229, 255, 0.05);
        color: var(--color-text-primary);
        margin-top: 10px;
        border: 1px solid var(--color-border);
    }

    .client-box-active {
        padding: 12px;
        border-radius: 6px;
        border-left: 4px solid var(--color-success);
        background-color: rgba(0, 255, 0, 0.05);
        color: var(--color-text-primary);
        margin-top: 10px;
        border: 1px solid var(--color-success);
    }

    .module-card {
        padding: 20px;
        border: 1px solid var(--color-border);
        border-radius: 8px;
        background-color: var(--color-bg-secondary);
        text-align: center;
        transition: all 0.3s ease;
    }

    .module-card:hover {
        border-color: var(--color-accent);
        box-shadow: 0 0 15px rgba(0, 229, 255, 0.1);
    }

    .logo-title {
        font-family: 'Courier New', monospace;
        color: var(--color-accent);
        letter-spacing: 3px;
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 10px;
    }

    .subtitle {
        text-align: center;
        color: var(--color-text-secondary);
        font-size: 0.95rem;
        margin-bottom: 30px;
    }

    /* ── SCROLLBAR ── */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: var(--color-bg-secondary);
    }

    ::-webkit-scrollbar-thumb {
        background: var(--color-border);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: var(--color-accent);
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 3️⃣ CONFIGURACIÓN DE CARPETAS Y ARCHIVOS
# ═══════════════════════════════════════════════════════════════

DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)


# ═══════════════════════════════════════════════════════════════
# 4️⃣ FUNCIONES DE SEGURIDAD Y BASE DE DATOS
# ═══════════════════════════════════════════════════════════════

def hash_password(password):
    """Encripta contraseña con SHA256."""
    return hashlib.sha256(str.encode(password)).hexdigest()


def gestionar_usuarios(accion, username=None, password=None):
    """Gestiona base de datos JSON de usuarios."""
    archivo = f"{DATA_FOLDER}/usuarios.json"

    # Crear archivo si no existe
    if not os.path.exists(archivo):
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump({}, f)

    try:
        with open(archivo, "r", encoding="utf-8") as f:
            usuarios = json.load(f)
    except json.JSONDecodeError:
        usuarios = {}

    if accion == "registro":
        if username in usuarios:
            return False

        usuarios[username] = {
            "password": hash_password(password),
            "clientes": [],
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)
        return True

    if accion == "login":
        if username in usuarios and usuarios[username]["password"] == hash_password(password):
            return True
        return False


def cargar_clientes_db() -> list:
    """Carga clientes del usuario actual."""
    archivo = f"{DATA_FOLDER}/usuarios.json"
    try:
        if not os.path.exists(archivo):
            return []
        with open(archivo, "r", encoding="utf-8") as f:
            usuarios = json.load(f)
        usuario = st.session_state.get("usuario_actual", "")
        return usuarios.get(usuario, {}).get("clientes", [])
    except Exception:
        return []


def guardar_clientes_db(lista_clientes: list) -> bool:
    """Guarda clientes del usuario actual."""
    archivo = f"{DATA_FOLDER}/usuarios.json"
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            usuarios = json.load(f)
        usuario = st.session_state.get("usuario_actual", "")
        if usuario not in usuarios:
            return False
        usuarios[usuario]["clientes"] = lista_clientes
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# 5️⃣ INICIALIZACIÓN DE SESIÓN
# ═══════════════════════════════════════════════════════════════

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None
if "pagina_actual" not in st.session_state:
    st.session_state["pagina_actual"] = "dashboard"
if "cliente_activo" not in st.session_state:
    st.session_state["cliente_activo"] = None


# ═══════════════════════════════════════════════════════════════
# 6️⃣ PANTALLA DE LOGIN Y REGISTRO
# ═══════════════════════════════════════════════════════════════

def mostrar_login_registro():
    """Renderiza pantalla de autenticación."""
    col_empty1, col_form, col_empty2 = st.columns([1, 2, 1])

    with col_form:
        st.markdown('<div class="logo-title">YN</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtitle">Learnix Hub</div>', unsafe_allow_html=True)
        st.markdown(
            '<p style="text-align:center; color:#888888;">Plataforma de Auditoría Tributaria</p>',
            unsafe_allow_html=True
        )
        st.write("")

        # Pestañas de Login/Registro
        tab_login, tab_registro = st.tabs(["🔐 Iniciar Sesión", "📝 Crear Cuenta"])

        # ── PESTAÑA: LOGIN ──
        with tab_login:
            with st.form("form_login"):
                usuario = st.text_input(
                    "👤 Usuario",
                    placeholder="Ingresa tu usuario",
                    key="login_user"
                )
                contraseña = st.text_input(
                    "🔑 Contraseña",
                    type="password",
                    placeholder="Ingresa tu contraseña",
                    key="login_pw"
                )

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    btn_login = st.form_submit_button(
                        "🔓 Entrar",
                        type="primary",
                        use_container_width=True
                    )

                if btn_login:
                    if not usuario or not contraseña:
                        st.error("⚠️ Completa todos los campos")
                    elif gestionar_usuarios("login", usuario, contraseña):
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = usuario
                        st.success("✅ Acceso concedido")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")

            # Usuarios de prueba
            st.divider()
            st.info(
                "**👤 Usuarios de Prueba:**\n\n"
                "usuario: `admin` | contraseña: `admin123`\n\n"
                "usuario: `contador` | contraseña: `contador123`"
            )

        # ── PESTAÑA: REGISTRO ──
        with tab_registro:
            with st.form("form_registro"):
                nuevo_usuario = st.text_input(
                    "👤 Nuevo usuario",
                    placeholder="Elige un nombre de usuario",
                    key="reg_user"
                )
                nueva_pw = st.text_input(
                    "🔑 Contraseña",
                    type="password",
                    placeholder="Mínimo 6 caracteres",
                    key="reg_pw"
                )
                confirmar_pw = st.text_input(
                    "🔑 Confirmar contraseña",
                    type="password",
                    placeholder="Repite tu contraseña",
                    key="reg_pw_confirm"
                )

                btn_registro = st.form_submit_button(
                    "✅ Registrarse",
                    type="primary",
                    use_container_width=True
                )

                if btn_registro:
                    if not nuevo_usuario or not nueva_pw:
                        st.warning("⚠️ Completa todos los campos")
                    elif len(nueva_pw) < 6:
                        st.warning("⚠️ Contraseña mínimo 6 caracteres")
                    elif nueva_pw != confirmar_pw:
                        st.warning("⚠️ Las contraseñas no coinciden")
                    elif gestionar_usuarios("registro", nuevo_usuario, nueva_pw):
                        st.success("✅ Cuenta creada. Inicia sesión ahora.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Este usuario ya existe")

            st.divider()
            st.info("✨ **Características:**\n✅ Extracción PDF\n✅ Importación JSON\n✅ Validación IA\n✅ Gestor de Clientes")


# ═══════════════════════════════════════════════════════════════
# 7️⃣ DASHBOARD PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def mostrar_dashboard():
    """Renderiza dashboard principal."""
    st.markdown('<div class="logo-title">YN</div>', unsafe_allow_html=True)
    st.title("📊 Dashboard")

    # ── HEADER ──
    col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
    with col_h1:
        st.markdown(f"**👤 {st.session_state['usuario_actual']}**")
    with col_h2:
        st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
    with col_h3:
        if st.button("🚪 Salir", use_container_width=True, key="btn_logout"):
            st.session_state["autenticado"] = False
            st.session_state["usuario_actual"] = None
            st.session_state["cliente_activo"] = None
            st.rerun()

    st.divider()

    # ── SECCIÓN: GESTIÓN DE CLIENTES ──
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### 🏢 Clientes Registrados")

        clientes = cargar_clientes_db()

        if clientes:
            opciones = {
                f"{c.get('nombre', 'N/A')} — {c.get('nit', 'N/A')}": c
                for c in clientes
            }

            seleccion = st.selectbox(
                "Selecciona un cliente",
                list(opciones.keys()),
                key="sel_cliente"
            )

            cliente_obj = opciones[seleccion]

            col_a, col_b = st.columns(2)
            with col_a:
                st.caption(f"**NIT:** {cliente_obj.get('nit', 'N/A')}")
                st.caption(f"**DUI:** {cliente_obj.get('dui', 'N/A')}")
            with col_b:
                st.caption(f"**Email:** {cliente_obj.get('email', 'N/A')}")
                st.caption(f"**Tel:** {cliente_obj.get('telefono', 'N/A')}")

            if st.button("✅ Activar Cliente", type="primary", use_container_width=True):
                st.session_state["cliente_activo"] = cliente_obj
                st.success(f"✅ Activado: {cliente_obj.get('nombre')}")
                time.sleep(0.5)
                st.rerun()

            # Mostrar cliente activo
            if st.session_state.get("cliente_activo"):
                ca = st.session_state["cliente_activo"]
                st.markdown(
                    f"""
                    <div class="client-box-active">
                        <strong>✅ CLIENTE ACTIVO</strong><br>
                        {ca.get('nombre')}<br>
                        <small>NIT: {ca.get('nit')}</small>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("📁 No hay clientes. Crea uno a la derecha →")

    with col_right:
        st.markdown("### ➕ Nuevo Cliente")

        with st.form("form_cliente"):
            nombre = st.text_input("Nombre/Razón Social", placeholder="Empresa ABC")
            nit = st.text_input("NIT", placeholder="0614-123456-789-0")
            dui = st.text_input("DUI (opcional)", placeholder="12345678-9")
            email = st.text_input("Email", placeholder="empresa@correo.com")
            telefono = st.text_input("Teléfono", placeholder="+503 2234-5678")

            if st.form_submit_button("➕ Agregar", type="primary", use_container_width=True):
                if not nombre or not nit:
                    st.error("⚠️ Nombre y NIT son obligatorios")
                else:
                    nuevo = {
                        "nombre": nombre.strip(),
                        "nit": nit.strip(),
                        "dui": dui.strip(),
                        "email": email.strip(),
                        "telefono": telefono.strip()
                    }
                    clientes_actualizados = clientes + [nuevo]
                    if guardar_clientes_db(clientes_actualizados):
                        st.success(f"✅ {nombre} agregado")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar")

    st.divider()

    # ── SECCIÓN: MÓDULOS ──
    st.markdown("### 📈 Módulos Disponibles")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            """
            <div class="module-card">
                <h4>📈 Ventas</h4>
                <p style='color:#888; font-size:12px;'>DTE 01, 03, 05, 06, 11</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="module-card">
                <h4>🛒 Compras</h4>
                <p style='color:#888; font-size:12px;'>DTE 03, 05, 06, 07</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="module-card">
                <h4>✂️ Retenciones</h4>
                <p style='color:#888; font-size:12px;'>DTE-07 (1%)</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            """
            <div class="module-card">
                <h4>⚖️ Suj. Excluidos</h4>
                <p style='color:#888; font-size:12px;'>DTE-14 (10%)</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.divider()

    # Footer
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.caption(f"👤 {st.session_state['usuario_actual']}")
    with col_f2:
        st.caption("🏢 Learnix Hub v2.0")
    with col_f3:
        st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")


# ═══════════════════════════════════════════════════════════════
# 8️⃣ CARGADOR DE PÁGINAS DINÁMICAS
# ═══════════════════════════════════════════════════════════════

def cargar_pagina(ruta: str, nombre: str):
    """Carga una página dinámicamente."""
    try:
        if not os.path.exists(ruta):
            st.error(f"❌ Archivo no encontrado: {ruta}")
            return

        spec = importlib.util.spec_from_file_location(nombre, ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# 9️⃣ NAVEGACIÓN LATERAL
# ═══════════════════════════════════════════════════════════════

def renderizar_sidebar():
    """Renderiza menú lateral."""
    with st.sidebar:
        st.title("📍 NAVEGACIÓN")
        st.divider()

        # Dashboard
        st.markdown("**🚀 Inicio**")
        if st.button("🏠 Dashboard", use_container_width=True, key="btn_dash"):
            st.session_state["pagina_actual"] = "dashboard"
            st.rerun()

        st.divider()

        # Módulos
        st.markdown("**⚙️ Módulos**")

        if st.session_state.get("cliente_activo"):
            if st.button("📈 Extractor Ventas", use_container_width=True, key="btn_v"):
                st.session_state["pagina_actual"] = "ventas"
                st.rerun()

            if st.button("🛒 Extractor Compras", use_container_width=True, key="btn_c"):
                st.session_state["pagina_actual"] = "compras"
                st.rerun()

            if st.button("✂️ Extractor Retenciones", use_container_width=True, key="btn_r"):
                st.session_state["pagina_actual"] = "retenciones"
                st.rerun()

            if st.button("⚖️ Sujetos Excluidos", use_container_width=True, key="btn_s"):
                st.session_state["pagina_actual"] = "sujetos"
                st.rerun()
        else:
            st.info("⚠️ Selecciona un cliente primero")

        st.divider()

        # Admin
        st.markdown("**🗄️ Administración**")

        if st.button("👥 Clientes", use_container_width=True, key="btn_clientes"):
            st.session_state["pagina_actual"] = "clientes"
            st.rerun()

        if st.button("🏢 Proveedores", use_container_width=True, key="btn_prov"):
            st.session_state["pagina_actual"] = "proveedores"
            st.rerun()

        st.divider()

        # Info
        st.markdown(f"**👤** {st.session_state['usuario_actual']}")
        if st.session_state.get("cliente_activo"):
            ca = st.session_state["cliente_activo"]
            st.markdown(f"**🏢** {ca.get('nombre', 'N/A')}")

        st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# ═══════════════════════════════════════════════════════════════
# 🔟 ENRUTADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════

if not st.session_state["autenticado"]:
    mostrar_login_registro()
else:
    renderizar_sidebar()

    pagina = st.session_state.get("pagina_actual", "dashboard")

    if pagina == "dashboard":
        mostrar_dashboard()

    elif pagina == "ventas":
        cargar_pagina("pages/1_Extractor_DTE_Ventas.py", "ventas")

    elif pagina == "compras":
        cargar_pagina("pages/2_Extractor_DTE_Compras.py", "compras")

    elif pagina == "retenciones":
        cargar_pagina("pages/3_Extractor_DTE_Retenciones.py", "retenciones")

    elif pagina == "sujetos":
        cargar_pagina("pages/4_Extractor_DTE_Sujetos_Excluidos.py", "sujetos")

    elif pagina == "clientes":
        cargar_pagina("pages/5_Directorio_Clientes.py", "clientes")

    elif pagina == "proveedores":
        cargar_pagina("pages/6_Directorio_Proveedores.py", "proveedores")

    else:
        st.warning("⚠️ Página no encontrada")
