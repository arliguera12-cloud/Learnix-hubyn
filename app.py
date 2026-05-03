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

    [data-testid="stAppViewContainer"] {
        background-color: var(--color-bg-main) !important;
    }

    [data-testid="stHeader"] {
        background-color: var(--color-bg-main) !important;
        border-bottom: 1px solid var(--color-border) !important;
    }

    [data-testid="stSidebar"] {
        background-color: var(--color-bg-tertiary) !important;
        border-right: 1px solid var(--color-border) !important;
    }

    [data-testid="stSidebarContent"] {
        background-color: var(--color-bg-tertiary) !important;
    }

    h1, h2, h3, h4, h5, h6 {
        color: var(--color-text-primary) !important;
        font-weight: 600 !important;
    }

    p, label, span, div {
        color: var(--color-text-primary) !important;
    }

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

    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: var(--color-accent) !important;
        border-bottom-color: var(--color-accent) !important;
    }

    .stTabs [data-baseweb="tab-list"] button {
        color: var(--color-text-secondary) !important;
    }

    .streamlit-expanderHeader {
        background-color: var(--color-bg-secondary) !important;
        border: 1px solid var(--color-border) !important;
        color: var(--color-text-primary) !important;
    }

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

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: var(--color-bg-secondary); }
    ::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--color-accent); }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 3️⃣ CONFIGURACIÓN DE CARPETAS
# ═══════════════════════════════════════════════════════════════

DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# ═══════════════════════════════════════════════════════════════
# 4️⃣ FUNCIONES DE SEGURIDAD Y BASE DE DATOS
# ═══════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """Encripta contraseña con SHA256 — UTF-8 consistente."""
    if isinstance(password, str):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def _cargar_todos_usuarios() -> dict:
    """Lee data/usuarios.json. Si no existe o está roto, devuelve {}."""
    archivo = f"{DATA_FOLDER}/usuarios.json"
    if not os.path.exists(archivo):
        return {}
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _guardar_todos_usuarios(usuarios: dict) -> bool:
    """Escribe data/usuarios.json."""
    archivo = f"{DATA_FOLDER}/usuarios.json"
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)
        return True
    except OSError:
        return False


def _seed_usuarios_prueba():
    """
    Si no existen los usuarios de prueba los crea con hash correcto.
    Esto garantiza que admin/admin123 y contador/contador123 siempre funcionen.
    """
    usuarios = _cargar_todos_usuarios()
    cambiado = False

    usuarios_seed = {
        "admin":    "admin123",
        "contador": "contador123",
    }

    for uname, pwd in usuarios_seed.items():
        if uname not in usuarios:
            usuarios[uname] = {
                "password": hash_password(pwd),
                "clientes": [],
                "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            cambiado = True
        else:
            # Regenerar hash si estaba corrupto (longitud distinta a 64 hex)
            hash_actual = usuarios[uname].get("password", "")
            if len(hash_actual) != 64:
                usuarios[uname]["password"] = hash_password(pwd)
                cambiado = True

    if cambiado:
        _guardar_todos_usuarios(usuarios)


def gestionar_usuarios(accion: str, username: str = None, password: str = None) -> bool:
    """Gestiona registro y login de usuarios."""
    usuarios = _cargar_todos_usuarios()

    if accion == "registro":
        if username in usuarios:
            return False
        usuarios[username] = {
            "password": hash_password(password),
            "clientes": [],
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return _guardar_todos_usuarios(usuarios)

    if accion == "login":
        user_data = usuarios.get(username)
        if not user_data:
            return False
        return user_data.get("password") == hash_password(password)

    return False


def cargar_clientes_db() -> list:
    """Carga clientes del usuario actual."""
    try:
        usuarios = _cargar_todos_usuarios()
        usuario = st.session_state.get("usuario_actual", "")
        return usuarios.get(usuario, {}).get("clientes", [])
    except Exception:
        return []


def guardar_clientes_db(lista_clientes: list) -> bool:
    """Guarda clientes del usuario actual."""
    try:
        usuarios = _cargar_todos_usuarios()
        usuario = st.session_state.get("usuario_actual", "")
        if usuario not in usuarios:
            return False
        usuarios[usuario]["clientes"] = lista_clientes
        return _guardar_todos_usuarios(usuarios)
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════════
# 5️⃣ SEED EN ARRANQUE
# ═══════════════════════════════════════════════════════════════

_seed_usuarios_prueba()

# ═══════════════════════════════════════════════════════════════
# 6️⃣ INICIALIZACIÓN DE SESIÓN
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
# 7️⃣ PANTALLA DE LOGIN Y REGISTRO
# ═══════════════════════════════════════════════════════════════

def mostrar_login_registro():
    col_empty1, col_form, col_empty2 = st.columns([1, 2, 1])

    with col_form:
        st.markdown('<div class="logo-title">YN</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtitle">Learnix Hub</div>', unsafe_allow_html=True)
        st.markdown(
            '<p style="text-align:center; color:#888888;">Plataforma de Auditoría Tributaria</p>',
            unsafe_allow_html=True
        )
        st.write("")

        tab_login, tab_registro = st.tabs(["Iniciar Sesion", "Crear Cuenta"])

        # ── LOGIN ──
        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                usuario = st.text_input(
                    "Usuario",
                    placeholder="Ingresa tu usuario",
                    key="login_user"
                )
                contrasena = st.text_input(
                    "Contrasena",
                    type="password",
                    placeholder="Ingresa tu contrasena",
                    key="login_pw"
                )
                btn_login = st.form_submit_button(
                    "Entrar",
                    type="primary",
                    use_container_width=True
                )

            if btn_login:
                if not usuario or not contrasena:
                    st.error("Completa todos los campos")
                elif gestionar_usuarios("login", usuario.strip(), contrasena):
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_actual"] = usuario.strip()
                    st.success("Acceso concedido")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error("Usuario o contrasena incorrectos")

            st.divider()
            st.info(
                "**Usuarios de Prueba:**\n\n"
                "usuario: `admin` — contrasena: `admin123`\n\n"
                "usuario: `contador` — contrasena: `contador123`"
            )

        # ── REGISTRO ──
        with tab_registro:
            with st.form("form_registro", clear_on_submit=True):
                nuevo_usuario = st.text_input(
                    "Nuevo usuario",
                    placeholder="Elige un nombre de usuario",
                    key="reg_user"
                )
                nueva_pw = st.text_input(
                    "Contrasena",
                    type="password",
                    placeholder="Minimo 6 caracteres",
                    key="reg_pw"
                )
                confirmar_pw = st.text_input(
                    "Confirmar contrasena",
                    type="password",
                    placeholder="Repite tu contrasena",
                    key="reg_pw_confirm"
                )
                btn_registro = st.form_submit_button(
                    "Registrarse",
                    type="primary",
                    use_container_width=True
                )

            if btn_registro:
                if not nuevo_usuario or not nueva_pw:
                    st.warning("Completa todos los campos")
                elif len(nueva_pw) < 6:
                    st.warning("Contrasena minimo 6 caracteres")
                elif nueva_pw != confirmar_pw:
                    st.warning("Las contrasenas no coinciden")
                elif gestionar_usuarios("registro", nuevo_usuario.strip(), nueva_pw):
                    st.success("Cuenta creada. Inicia sesion ahora.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Este usuario ya existe")

            st.divider()
            st.info(
                "**Caracteristicas:**\n\n"
                "Extraccion PDF\n\n"
                "Importacion JSON\n\n"
                "Validacion IA\n\n"
                "Gestor de Clientes"
            )

# ═══════════════════════════════════════════════════════════════
# 8️⃣ DASHBOARD PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def mostrar_dashboard():
    st.markdown('<div class="logo-title">YN</div>', unsafe_allow_html=True)
    st.title("Dashboard")

    col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
    with col_h1:
        st.markdown(f"**Usuario: {st.session_state['usuario_actual']}**")
    with col_h2:
        st.caption(f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
    with col_h3:
        if st.button("Cerrar Sesion", use_container_width=True, key="btn_logout"):
            st.session_state["autenticado"] = False
            st.session_state["usuario_actual"] = None
            st.session_state["cliente_activo"] = None
            st.rerun()

    st.divider()

    # ── GESTIÓN DE CLIENTES ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### Clientes Registrados")
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

            if st.button("Activar Cliente", type="primary", use_container_width=True):
                st.session_state["cliente_activo"] = cliente_obj
                st.success(f"Activado: {cliente_obj.get('nombre')}")
                time.sleep(0.5)
                st.rerun()

            if st.session_state.get("cliente_activo"):
                ca = st.session_state["cliente_activo"]
                st.markdown(
                    f"""
                    <div class="client-box-active">
                        <strong>CLIENTE ACTIVO</strong><br>
                        {ca.get('nombre')}<br>
                        <small>NIT: {ca.get('nit')}</small>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.divider()
            st.markdown("**Eliminar cliente**")
            cliente_a_eliminar = st.selectbox(
                "Selecciona cliente a eliminar",
                list(opciones.keys()),
                key="sel_eliminar"
            )
            if st.button("Eliminar", type="secondary", use_container_width=True):
                cliente_eliminar_obj = opciones[cliente_a_eliminar]
                clientes_nuevos = [
                    c for c in clientes
                    if c.get("nit") != cliente_eliminar_obj.get("nit")
                ]
                if guardar_clientes_db(clientes_nuevos):
                    if st.session_state.get("cliente_activo", {}).get("nit") == cliente_eliminar_obj.get("nit"):
                        st.session_state["cliente_activo"] = None
                    st.success("Cliente eliminado")
                    time.sleep(0.5)
                    st.rerun()

        else:
            st.info("No hay clientes registrados. Agrega uno a la derecha.")

    with col_right:
        st.markdown("### Nuevo Cliente")

        with st.form("form_cliente", clear_on_submit=True):
            nombre   = st.text_input("Nombre / Razon Social", placeholder="Empresa ABC")
            nit      = st.text_input("NIT", placeholder="0614-123456-789-0")
            dui      = st.text_input("DUI (opcional)", placeholder="12345678-9")
            email    = st.text_input("Email", placeholder="empresa@correo.com")
            telefono = st.text_input("Telefono", placeholder="+503 2234-5678")

            if st.form_submit_button("Agregar Cliente", type="primary", use_container_width=True):
                if not nombre.strip() or not nit.strip():
                    st.error("Nombre y NIT son obligatorios")
                else:
                    nuevo = {
                        "nombre":   nombre.strip(),
                        "nit":      nit.strip(),
                        "dui":      dui.strip(),
                        "email":    email.strip(),
                        "telefono": telefono.strip(),
                    }
                    clientes_actualizados = cargar_clientes_db() + [nuevo]
                    if guardar_clientes_db(clientes_actualizados):
                        st.success(f"Cliente '{nombre}' agregado correctamente")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Error al guardar el cliente")

    st.divider()

    # ── MÓDULOS ──
    st.markdown("### Modulos Disponibles")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            "<div class='module-card'>"
            "<h4>Ventas</h4>"
            "<p style='color:#888;font-size:12px;'>DTE 01, 03, 05, 06, 11</p>"
            "</div>",
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            "<div class='module-card'>"
            "<h4>Compras</h4>"
            "<p style='color:#888;font-size:12px;'>DTE 03, 05, 06, 07</p>"
            "</div>",
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            "<div class='module-card'>"
            "<h4>Retenciones</h4>"
            "<p style='color:#888;font-size:12px;'>DTE-07 (1%)</p>"
            "</div>",
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            "<div class='module-card'>"
            "<h4>Suj. Excluidos</h4>"
            "<p style='color:#888;font-size:12px;'>DTE-14 (10%)</p>"
            "</div>",
            unsafe_allow_html=True
        )

    st.divider()
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.caption(f"Usuario: {st.session_state['usuario_actual']}")
    with col_f2:
        st.caption("Learnix Hub v2.0")
    with col_f3:
        st.caption(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# ═══════════════════════════════════════════════════════════════
# 9️⃣ CARGADOR DE PÁGINAS DINÁMICAS
# ═══════════════════════════════════════════════════════════════

def cargar_pagina(ruta: str, nombre: str):
    try:
        if not os.path.exists(ruta):
            st.error(f"Archivo no encontrado: {ruta}")
            return
        spec   = importlib.util.spec_from_file_location(nombre, ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
    except Exception as e:
        st.error(f"Error al cargar pagina: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# 🔟 SIDEBAR
# ═══════════════════════════════════════════════════════════════

def renderizar_sidebar():
    with st.sidebar:
        st.title("NAVEGACION")
        st.divider()

        st.markdown("**Inicio**")
        if st.button("Dashboard", use_container_width=True, key="btn_dash"):
            st.session_state["pagina_actual"] = "dashboard"
            st.rerun()

        st.divider()
        st.markdown("**Modulos**")

        if st.session_state.get("cliente_activo"):
            ca = st.session_state["cliente_activo"]
            st.markdown(
                f"<div class='client-box-active'>"
                f"<small>Activo: <b>{ca.get('nombre','N/A')}</b></small>"
                f"</div>",
                unsafe_allow_html=True
            )
            st.write("")

            if st.button("Extractor Ventas", use_container_width=True, key="btn_v"):
                st.session_state["pagina_actual"] = "ventas"
                st.rerun()

            if st.button("Extractor Compras", use_container_width=True, key="btn_c"):
                st.session_state["pagina_actual"] = "compras"
                st.rerun()

            if st.button("Extractor Retenciones", use_container_width=True, key="btn_r"):
                st.session_state["pagina_actual"] = "retenciones"
                st.rerun()

            if st.button("Sujetos Excluidos", use_container_width=True, key="btn_s"):
                st.session_state["pagina_actual"] = "sujetos"
                st.rerun()
        else:
            st.info("Selecciona un cliente primero desde el Dashboard")

        st.divider()
        st.markdown("**Administracion**")

        if st.button("Clientes", use_container_width=True, key="btn_clientes"):
            st.session_state["pagina_actual"] = "dashboard"
            st.rerun()

        st.divider()
        st.caption(f"Usuario: {st.session_state['usuario_actual']}")
        st.caption(f"Fecha:   {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        if st.button("Cerrar Sesion", use_container_width=True, key="btn_logout_side"):
            st.session_state["autenticado"]   = False
            st.session_state["usuario_actual"] = None
            st.session_state["cliente_activo"] = None
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# 1️⃣1️⃣ ENRUTADOR PRINCIPAL
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
    else:
        mostrar_dashboard()
