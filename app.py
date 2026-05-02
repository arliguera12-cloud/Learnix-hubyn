# app.py
"""
Learnix Hub - Sistema de Extracción de DTE
Aplicación principal con autenticación segura
"""

import streamlit as st
import time
import json
import os
import hashlib
import importlib.util

# ═══════════════════════════════════════════════════════════════
# 1️⃣ CONFIGURACIÓN GLOBAL (UNA SOLA VEZ)
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Learnix Hub",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════
# 2️⃣ ESTILOS GLOBALES
# ═══════════════════════════════════════════════════════════════

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #000000 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #161616 !important;
        border-right: 1px solid #333333 !important;
    }
    h1, h2, h3, h4, h5, h6, p, label, span, div {
        color: #F7F5EE !important;
    }
    div.stButton > button[kind="primary"],
    div.stDownloadButton > button[kind="primary"] {
        background-color: #003057 !important;
        border: 1px solid #00407A !important;
        border-radius: 6px;
        transition: 0.3s;
    }
    div.stButton > button[kind="primary"] *,
    div.stDownloadButton > button[kind="primary"] * {
        color: #FFFFFF !important;
        font-weight: bold !important;
    }
    div.stButton > button[kind="primary"]:hover,
    div.stDownloadButton > button[kind="primary"]:hover {
        background-color: #00407A !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #4DA8DA !important;
        border-bottom-color: #4DA8DA !important;
    }
    .stTabs [data-baseweb="tab-list"] button {
        color: #777777 !important;
    }
    .login-container {
        max-width: 500px;
        margin: 0 auto;
        padding: 40px;
        border-radius: 10px;
        border: 1px solid #333333;
        background-color: #0A0A0A;
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 3️⃣ GESTOR DE BASE DE DATOS Y SEGURIDAD
# ═══════════════════════════════════════════════════════════════

DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)


def hash_password(password):
    """Encripta la contraseña por seguridad."""
    return hashlib.sha256(str.encode(password)).hexdigest()


def gestionar_usuarios(accion, username=None, password=None):
    """Maneja la base de datos JSON de usuarios."""
    archivo = f"{DATA_FOLDER}/usuarios.json"

    # Si el archivo no existe, lo crea vacío
    if not os.path.exists(archivo):
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump({}, f)

    with open(archivo, "r", encoding="utf-8") as f:
        usuarios = json.load(f)

    if accion == "registro":
        if username in usuarios:
            return False  # El usuario ya existe
        
        usuarios[username] = {
            "password": hash_password(password),
            "clientes": []
        }
        
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)
        return True

    if accion == "login":
        if username in usuarios and usuarios[username]["password"] == hash_password(password):
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# 4️⃣ CONTROL DE SESIÓN
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
# 5️⃣ UI DE LOGIN Y REGISTRO
# ═══════════════════════════════════════════════════════════════

def mostrar_registro_login():
    """Renderiza la pantalla de login/registro."""
    col_empty1, col_form, col_empty2 = st.columns([1, 2, 1])

    with col_form:
        st.markdown(
            "<h1 style='text-align: center; color: #00E5FF;'>Learnix Hub</h1>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<p style='text-align: center; color: #888888;'>Plataforma Inteligente de Auditoría Tributaria</p>",
            unsafe_allow_html=True
        )
        st.write("")

        # Sistema de Pestañas
        tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta"])

        with tab_login:
            with st.form("login_form"):
                user = st.text_input("👤 Usuario / Email", placeholder="ingresa tu usuario")
                pw = st.text_input("🔐 Contraseña", type="password", placeholder="ingresa tu contraseña")
                submit_login = st.form_submit_button(
                    "🔓 Entrar al Hub",
                    type="primary",
                    use_container_width=True
                )

                if submit_login:
                    if not user or not pw:
                        st.error("⚠️ Por favor completa todos los campos.")
                    elif gestionar_usuarios("login", user, pw):
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = user
                        st.success("✅ Acceso concedido. Iniciando módulos...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos.")

        with tab_reg:
            with st.form("reg_form"):
                new_user = st.text_input("👤 Elige un nombre de usuario", placeholder="mi_usuario")
                new_pw = st.text_input("🔐 Crea una contraseña segura", type="password")
                confirm_pw = st.text_input("🔐 Confirma tu contraseña", type="password")
                submit_reg = st.form_submit_button(
                    "✅ Registrarme",
                    type="primary",
                    use_container_width=True
                )

                if submit_reg:
                    if not new_user or not new_pw:
                        st.warning("⚠️ Por favor, completa todos los campos.")
                    elif new_pw != confirm_pw:
                        st.warning("⚠️ Las contraseñas no coinciden.")
                    elif gestionar_usuarios("registro", new_user, new_pw):
                        st.success("✅ ¡Cuenta creada con éxito! Ve a 'Iniciar Sesión' para entrar.")
                    else:
                        st.error("❌ Este usuario ya existe. Por favor elige otro.")

        st.divider()
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.info(
                "**👤 Usuarios de Prueba:**\n\n"
                "usuario: `admin`\n"
                "contraseña: `admin123`"
            )
        with col_info2:
            st.info(
                "**✨ Características:**\n\n"
                "✅ Extracción PDF + OCR\n"
                "✅ Importación JSON\n"
                "✅ Validación Gemini 1.5"
            )


# ═══════════════════════════════════════════════════════════════
# 6️⃣ DASHBOARD PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def mostrar_dashboard():
    """Renderiza el dashboard después del login."""
    st.markdown(
        "<h2 style='font-family:Courier New,monospace; color:#00E5FF; "
        "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
        unsafe_allow_html=True
    )
    st.title("📊 Dashboard Principal")

    # Header con datos del usuario
    col_user1, col_user2, col_user3 = st.columns([2, 1, 1])

    with col_user1:
        st.markdown(f"### 👤 **{st.session_state['usuario_actual']}**")

    with col_user2:
        st.caption(f"📅 {time.strftime('%d/%m/%Y')}")

    with col_user3:
        if st.button("🚪 Cerrar Sesión", use_container_width=True, key="btn_logout"):
            st.session_state["autenticado"] = False
            st.session_state["usuario_actual"] = None
            st.session_state["cliente_activo"] = None
            st.rerun()

    st.divider()

    # Información de módulos
    st.markdown("### 📈 Módulos Disponibles")
    st.info("Selecciona un módulo del menú lateral para comenzar.")

    col1, col2 = st.columns(2)

    modulos = [
        ("📈 Ventas", "Extrae DTE de ventas (01, 03, 05, 06, 11)"),
        ("🛒 Compras", "Extrae DTE de compras (03, 05, 06, 07)"),
        ("✂️ Retenciones", "Extrae DTE-07 (retenciones 1%)"),
        ("⚖️ Sujetos Excluidos", "Extrae DTE-14 (retenciones 10%)"),
    ]

    for idx, (titulo, desc) in enumerate(modulos):
        col = col1 if idx % 2 == 0 else col2
        with col:
            st.markdown(f"**{titulo}**\n\n{desc}")


# ═══════════════════════════════════════════════════════════════
# 7️⃣ CARGADOR DE PÁGINAS
# ═══════════════════════════════════════════════════════════════

def cargar_pagina(ruta_archivo, nombre_modulo):
    """Carga una página dinámicamente."""
    try:
        if not os.path.exists(ruta_archivo):
            st.error(f"❌ Archivo no encontrado: {ruta_archivo}")
            st.info("✅ Asegúrate de que el archivo existe en la carpeta `pages/`")
            return

        spec = importlib.util.spec_from_file_location(nombre_modulo, ruta_archivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)

    except Exception as e:
        st.error(f"❌ Error al cargar {nombre_modulo}: {str(e)}")
        st.info(f"📝 Detalles técnicos: {type(e).__name__}")


# ═══════════════════════════════════════════════════════════════
# 8️⃣ NAVEGACIÓN LATERAL
# ═══════════════════════════════════════════════════════════════

def renderizar_sidebar():
    """Renderiza el menú lateral."""
    with st.sidebar:
        st.title("📍 NAVEGACIÓN")
        st.divider()

        # Sección: Inicio
        st.markdown("**🚀 Inicio**")
        if st.button("🏠 Dashboard Hub", use_container_width=True, key="btn_dashboard"):
            st.session_state["pagina_actual"] = "dashboard"
            st.rerun()

        st.divider()

        # Sección: Módulos
        st.markdown("**⚙️ Módulos de Procesamiento**")
        
        if st.button("📈 Extractor DTE Ventas", use_container_width=True, key="btn_ventas"):
            st.session_state["pagina_actual"] = "ventas"
            st.rerun()

        if st.button("🛒 Extractor DTE Compras", use_container_width=True, key="btn_compras"):
            st.session_state["pagina_actual"] = "compras"
            st.rerun()

        if st.button("✂️ Extractor DTE Retenciones", use_container_width=True, key="btn_retenciones"):
            st.session_state["pagina_actual"] = "retenciones"
            st.rerun()

        if st.button("⚖️ Extractor DTE Sujetos Excluidos", use_container_width=True, key="btn_sujetos"):
            st.session_state["pagina_actual"] = "sujetos"
            st.rerun()

        st.divider()

        # Sección: Administración
        st.markdown("**🗄️ Administración**")
        
        if st.button("👥 Directorio Clientes", use_container_width=True, key="btn_clientes"):
            st.session_state["pagina_actual"] = "clientes"
            st.rerun()

        if st.button("🏢 Directorio Proveedores", use_container_width=True, key="btn_proveedores"):
            st.session_state["pagina_actual"] = "proveedores"
            st.rerun()

        st.divider()

        # Info del usuario
        st.markdown(f"**👤 Usuario:** `{st.session_state['usuario_actual']}`")
        st.caption(f"📅 {time.strftime('%d/%m/%Y %H:%M')}")


# ═══════════════════════════════════════════════════════════════
# 9️⃣ ENRUTADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════

if not st.session_state["autenticado"]:
    mostrar_registro_login()
else:
    # Mostrar sidebar
    renderizar_sidebar()

    # Enrutar páginas
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
        st.warning("⚠️ Página no encontrada.")
