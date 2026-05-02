# app.py
"""
Learnix Hub - Sistema de Extracción de DTE
Aplicación principal con autenticación segura y gestor de clientes
"""

import streamlit as st
import time
import json
import os
import hashlib
import importlib.util
from datetime import datetime

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
    div.stButton > button[kind="secondary"] {
        background-color: #2A2A2A !important;
        border: 1px solid #555555 !important;
        border-radius: 6px;
    }
    div.stButton > button[kind="secondary"] * {
        color: #FFFFFF !important;
        font-weight: bold !important;
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
    .client-box {
        padding: 10px;
        border-radius: 6px;
        border-left: 4px solid #00E5FF;
        background-color: #0a1628;
        color: white;
        margin-top: 10px;
    }
    .client-box-active {
        padding: 10px;
        border-radius: 6px;
        border-left: 4px solid #00FF00;
        background-color: #0a2810;
        color: white;
        margin-top: 10px;
    }
    .module-card {
        padding: 15px;
        border: 1px solid #333;
        border-radius: 8px;
        background: #0a0a0a;
        text-align: center;
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

    try:
        with open(archivo, "r", encoding="utf-8") as f:
            usuarios = json.load(f)
    except json.JSONDecodeError:
        usuarios = {}

    if accion == "registro":
        if username in usuarios:
            return False  # El usuario ya existe

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
    """Carga la lista de clientes desde el archivo del usuario."""
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
    """Guarda la lista de clientes del usuario activo."""
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
            "<h1 style='text-align: center; color: #00E5FF; font-family:Courier New,monospace;'>YN</h1>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<h2 style='text-align: center;'>Learnix Hub</h2>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<p style='text-align: center; color: #888888;'>Plataforma Inteligente de Auditoría Tributaria</p>",
            unsafe_allow_html=True
        )
        st.write("")

        # Sistema de Pestañas
        tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta"])

        # ── TAB LOGIN ──
        with tab_login:
            with st.form("login_form"):
                user = st.text_input(
                    "👤 Usuario / Email",
                    placeholder="ingresa tu usuario",
                    key="login_user"
                )
                pw = st.text_input(
                    "🔐 Contraseña",
                    type="password",
                    placeholder="ingresa tu contraseña",
                    key="login_pw"
                )
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

        # ── TAB REGISTRO ──
        with tab_reg:
            with st.form("reg_form"):
                new_user = st.text_input(
                    "👤 Elige un nombre de usuario",
                    placeholder="mi_usuario",
                    key="reg_user"
                )
                new_pw = st.text_input(
                    "🔐 Crea una contraseña segura",
                    type="password",
                    placeholder="min. 6 caracteres",
                    key="reg_pw"
                )
                confirm_pw = st.text_input(
                    "🔐 Confirma tu contraseña",
                    type="password",
                    placeholder="repite la contraseña",
                    key="reg_pw_confirm"
                )
                submit_reg = st.form_submit_button(
                    "✅ Registrarme",
                    type="primary",
                    use_container_width=True
                )

                if submit_reg:
                    if not new_user or not new_pw:
                        st.warning("⚠️ Por favor, completa todos los campos.")
                    elif len(new_pw) < 6:
                        st.warning("⚠️ La contraseña debe tener al menos 6 caracteres.")
                    elif new_pw != confirm_pw:
                        st.warning("⚠️ Las contraseñas no coinciden.")
                    elif gestionar_usuarios("registro", new_user, new_pw):
                        st.success("✅ ¡Cuenta creada con éxito! Ve a 'Iniciar Sesión' para entrar.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Este usuario ya existe. Por favor elige otro.")

        st.divider()

        # ── INFO DE PRUEBA ──
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.info(
                "**👤 Usuarios de Prueba:**\n\n"
                "usuario: `admin`\n"
                "contraseña: `admin123`\n\n"
                "usuario: `contador`\n"
                "contraseña: `contador123`"
            )
        with col_info2:
            st.info(
                "**✨ Características:**\n\n"
                "✅ Extracción PDF + OCR\n"
                "✅ Importación JSON\n"
                "✅ Validación Gemini 1.5\n"
                "✅ Gestor de Clientes"
            )


# ═══════════════════════════════════════════════════════════════
# 6️⃣ DASHBOARD PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def mostrar_dashboard():
    """Renderiza el dashboard con selector de clientes."""
    st.markdown(
        "<h2 style='font-family:Courier New,monospace; color:#00E5FF; "
        "letter-spacing:2px; margin-bottom:0;'>YN</h2>",
        unsafe_allow_html=True
    )
    st.title("📊 Dashboard Principal")

    # ── HEADER ──
    col_user1, col_user2, col_user3 = st.columns([2, 1, 1])
    with col_user1:
        st.markdown(f"### 👤 **{st.session_state['usuario_actual']}**")
    with col_user2:
        st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
    with col_user3:
        if st.button("🚪 Cerrar Sesión", use_container_width=True, key="btn_logout"):
            st.session_state["autenticado"] = False
            st.session_state["usuario_actual"] = None
            st.session_state["cliente_activo"] = None
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════
    # SECCIÓN: CLIENTE ACTIVO
    # ══════════════════════════════════════════
    col_izq, col_der = st.columns([1, 1])

    # ── COLUMNA IZQUIERDA: SELECCIONAR CLIENTE ──
    with col_izq:
        st.markdown("### 🏢 Seleccionar Cliente Activo")

        clientes = cargar_clientes_db()

        if clientes:
            opciones = {
                f"{c.get('nombre', 'N/A')} — {c.get('nit', 'N/A')}": c
                for c in clientes
            }
            seleccion = st.selectbox(
                "Cliente registrado",
                list(opciones.keys()),
                key="sel_cliente_activo"
            )

            cliente_obj = opciones[seleccion]

            col_a, col_b = st.columns(2)
            with col_a:
                st.caption(f"**NIT:** {cliente_obj.get('nit', 'N/A')}")
                st.caption(f"**DUI:** {cliente_obj.get('dui', 'N/A')}")
            with col_b:
                st.caption(f"**Email:** {cliente_obj.get('email', 'N/A')}")
                st.caption(f"**Tel:** {cliente_obj.get('telefono', 'N/A')}")

            if st.button(
                "✅ Activar este Cliente",
                type="primary",
                use_container_width=True,
                key="btn_activar"
            ):
                st.session_state["cliente_activo"] = cliente_obj
                st.success(f"✅ Cliente activo: **{cliente_obj.get('nombre')}**")
                st.info("Ahora puedes acceder a los extractores desde el menú lateral.")
                time.sleep(1)
                st.rerun()

            # ── CLIENTE ACTIVO ACTUAL ──
            if st.session_state.get("cliente_activo"):
                ca = st.session_state["cliente_activo"]
                st.markdown(
                    f"""
                    <div class='client-box-active'>
                        <strong style='color:#00FF00;'>✅ ACTIVO:</strong><br>
                        <span>{ca.get('nombre', 'N/A')}</span><br>
                        <small>NIT: {ca.get('nit', 'N/A')}</small>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.warning("⚠️ No tienes clientes registrados aún.")
            st.info("Agrega tu primer cliente en la sección de la derecha →")

    # ── COLUMNA DERECHA: AGREGAR CLIENTE ──
    with col_der:
        st.markdown("### ➕ Agregar Nuevo Cliente")

        with st.form("form_nuevo_cliente", clear_on_submit=True):
            nombre_c = st.text_input(
                "Nombre / Razón Social",
                placeholder="Empresa ABC S.A."
            )
            nit_c = st.text_input(
                "NIT",
                placeholder="0614-123456-789-0"
            )
            dui_c = st.text_input(
                "DUI (opcional)",
                placeholder="12345678-9"
            )
            email_c = st.text_input(
                "Email",
                placeholder="empresa@correo.com"
            )
            telefono_c = st.text_input(
                "Teléfono",
                placeholder="+503 2234-5678"
            )

            if st.form_submit_button(
                "➕ Agregar Cliente",
                type="primary",
                use_container_width=True
            ):
                if not nombre_c or not nit_c:
                    st.error("⚠️ Nombre y NIT son obligatorios.")
                else:
                    nuevo = {
                        "nombre": nombre_c.strip(),
                        "nit": nit_c.strip(),
                        "dui": dui_c.strip(),
                        "email": email_c.strip(),
                        "telefono": telefono_c.strip()
                    }
                    clientes_actualizados = clientes + [nuevo]
                    if guardar_clientes_db(clientes_actualizados):
                        st.success(f"✅ Cliente **{nombre_c}** agregado.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar el cliente.")

    st.divider()

    # ══════════════════════════════════════════
    # SECCIÓN: MÓDULOS DISPONIBLES
    # ══════════════════════════════════════════
    st.markdown("### 📈 Módulos Disponibles")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            """<div class='module-card'>
                <h4>📈 Ventas</h4>
                <p style='color:#888; font-size:12px;'>DTE 01, 03, 05, 06, 11</p>
            </div>""",
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """<div class='module-card'>
                <h4>🛒 Compras</h4>
                <p style='color:#888; font-size:12px;'>DTE 03, 05, 06, 07</p>
            </div>""",
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """<div class='module-card'>
                <h4>✂️ Retenciones</h4>
                <p style='color:#888; font-size:12px;'>DTE-07 (1%)</p>
            </div>""",
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            """<div class='module-card'>
                <h4>⚖️ Suj. Excluidos</h4>
                <p style='color:#888; font-size:12px;'>DTE-14 (10%)</p>
            </div>""",
            unsafe_allow_html=True
        )

    st.divider()

    # ── FOOTER ──
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.caption(f"👤 {st.session_state['usuario_actual']}")
    with col_f2:
        st.caption("🏢 Learnix Hub v2.0")
    with col_f3:
        st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")


# ═══════════════════════════════════════════════════════════════
# 7️⃣ CARGADOR DE PÁGINAS
# ═══════════════════════════════════════════════════════════════

def cargar_pagina(ruta_archivo: str, nombre_modulo: str):
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

        # ── SECCIÓN: INICIO ──
        st.markdown("**🚀 Inicio**")
        if st.button("🏠 Dashboard Hub", use_container_width=True, key="btn_dashboard"):
            st.session_state["pagina_actual"] = "dashboard"
            st.rerun()

        st.divider()

        # ── SECCIÓN: MÓDULOS ──
        st.markdown("**⚙️ Módulos de Procesamiento**")

        if st.session_state.get("cliente_activo"):
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
        else:
            st.warning("⚠️ Selecciona un cliente primero.")

        st.divider()

        # ── SECCIÓN: ADMINISTRACIÓN ──
        st.markdown("**🗄️ Administración**")

        if st.button("👥 Directorio Clientes", use_container_width=True, key="btn_clientes"):
            st.session_state["pagina_actual"] = "clientes"
            st.rerun()

        if st.button("🏢 Directorio Proveedores", use_container_width=True, key="btn_proveedores"):
            st.session_state["pagina_actual"] = "proveedores"
            st.rerun()

        st.divider()

        # ── INFO DEL USUARIO ──
        st.markdown(f"**👤 Usuario:** `{st.session_state['usuario_actual']}`")

        if st.session_state.get("cliente_activo"):
            ca = st.session_state["cliente_activo"]
            st.markdown(
                f"**🏢 Cliente:**\n`{ca.get('nombre', 'N/A')}`"
            )

        st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# ═══════════════════════════════════════════════════════════════
# 9️⃣ ENRUTADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════

if not st.session_state["autenticado"]:
    # MOSTRAR LOGIN
    mostrar_registro_login()
else:
    # MOSTRAR SIDEBAR
    renderizar_sidebar()

    # ── ENRUTAR PÁGINAS ──
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
