# app.py
"""
Learnix Hub - Sistema de Extracción de DTE
Aplicación principal con autenticación segura
"""

import streamlit as st
import json
import os
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Learnix Hub - DTE Extractor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Directorio de datos
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# FUNCIONES SEGURAS DE CARGA JSON
# ═══════════════════════════════════════════════════════════════

def cargar_json_seguro(ruta_archivo: str, estructura_default: dict) -> dict:
    """
    Carga un archivo JSON de forma segura.
    Si hay error, devuelve la estructura por defecto.
    
    Args:
        ruta_archivo: ruta al archivo JSON
        estructura_default: dict con estructura por defecto
    
    Returns:
        dict con los datos cargados o estructura por defecto
    """
    try:
        if not os.path.exists(ruta_archivo):
            # Crear archivo con estructura por defecto
            with open(ruta_archivo, 'w', encoding='utf-8') as f:
                json.dump(estructura_default, f, indent=2, ensure_ascii=False)
            return estructura_default

        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            contenido = f.read().strip()
            
            if not contenido:
                # Archivo vacío
                return estructura_default
            
            return json.loads(contenido)

    except json.JSONDecodeError as e:
        st.error(f"❌ Error al cargar {ruta_archivo}: JSON inválido")
        st.error(f"Detalles: {str(e)}")
        return estructura_default
    except Exception as e:
        st.error(f"❌ Error inesperado al cargar {ruta_archivo}: {str(e)}")
        return estructura_default


def guardar_json_seguro(ruta_archivo: str, datos: dict) -> bool:
    """
    Guarda datos a un archivo JSON de forma segura.
    
    Args:
        ruta_archivo: ruta al archivo
        datos: dict a guardar
    
    Returns:
        True si tuvo éxito, False si hubo error
    """
    try:
        os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ Error al guardar {ruta_archivo}: {str(e)}")
        return False


# ═══════════════════════════════════════════════════════════════
# CARGAR DATOS
# ═══════════════════════════════════════════════════════════════

# Estructura por defecto para usuarios
ESTRUCTURA_USUARIOS = {
    "usuarios": [
        {
            "id": 1,
            "usuario": "admin",
            "password": "admin123",
            "nombre": "Administrador",
            "email": "admin@learnixhub.com",
            "rol": "admin",
            "activo": True,
            "fecha_registro": "2026-01-01"
        }
    ]
}

# Estructura por defecto para clientes
ESTRUCTURA_CLIENTES = {
    "clientes": [
        {
            "id": 1,
            "nombre": "Empresa Demo",
            "nit": "0000-000000-000-0",
            "dui": "00000000-0",
            "email": "demo@empresa.com",
            "telefono": "+503 0000-0000",
            "direccion": "San Salvador, El Salvador",
            "estado": "activo",
            "fecha_registro": "2026-01-01"
        }
    ]
}

# Estructura por defecto para proveedores
ESTRUCTURA_PROVEEDORES = {
    "proveedores": [
        {
            "id": 1,
            "nombre": "Proveedor Demo",
            "nit": "1111-111111-111-1",
            "email": "proveedor@demo.com",
            "telefono": "+503 1111-1111",
            "pais": "El Salvador",
            "estado": "activo",
            "fecha_registro": "2026-01-01"
        }
    ]
}

# Cargar archivos JSON
usuarios_data = cargar_json_seguro(
    str(DATA_DIR / "usuarios.json"),
    ESTRUCTURA_USUARIOS
)
clientes_data = cargar_json_seguro(
    str(DATA_DIR / "clientes.json"),
    ESTRUCTURA_CLIENTES
)
proveedores_data = cargar_json_seguro(
    str(DATA_DIR / "proveedores.json"),
    ESTRUCTURA_PROVEEDORES
)

# ═══════════════════════════════════════════════════════════════
# ESTILOS GLOBALES
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
    div.stButton > button[kind="primary"] {
        background-color: #666D57 !important;
        border: 1px solid #828B70 !important;
        border-radius: 6px;
    }
    div.stButton > button[kind="primary"] * {
        color: #FFFFFF !important;
        font-weight: bold !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #798267 !important;
    }
    .login-container {
        max-width: 500px;
        margin: auto;
        padding: 40px;
        border-radius: 10px;
        border: 1px solid #333333;
        background-color: #0A0A0A;
    }
    .success-box {
        padding: 15px;
        border-radius: 6px;
        background-color: #1a3a1a;
        border-left: 4px solid #00aa00;
        color: #00ff00;
    }
    .error-box {
        padding: 15px;
        border-radius: 6px;
        background-color: #3a1a1a;
        border-left: 4px solid #aa0000;
        color: #ff6666;
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# ESTADO DE SESIÓN
# ═══════════════════════════════════════════════════════════════

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None
if "cliente_activo" not in st.session_state:
    st.session_state.cliente_activo = None

# ═══════════════════════════════════════════════════════════════
# FUNCIONES DE AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════

def verificar_credenciales(usuario: str, password: str) -> dict:
    """
    Verifica las credenciales contra la base de datos.
    
    Args:
        usuario: nombre de usuario
        password: contraseña
    
    Returns:
        dict con datos del usuario si es válido, None si no
    """
    usuarios_lista = usuarios_data.get("usuarios", [])
    
    for u in usuarios_lista:
        if u.get("usuario") == usuario and u.get("password") == password:
            if u.get("activo"):
                return u
    
    return None


def mostrar_registro_login():
    """Renderiza la pantalla de login."""
    st.markdown(
        "<h1 style='text-align:center; color:#666D57; "
        "font-family:Courier New,monospace; letter-spacing:3px;'>YN</h1>",
        unsafe_allow_html=True
    )
    
    st.markdown("<h2 style='text-align:center;'>Learnix Hub</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center; color:#999999;'>"
        "Sistema Inteligente de Extracción de DTE (Documentos Tributarios Electrónicos)"
        "</p>",
        unsafe_allow_html=True
    )
    
    st.divider()
    
    col_empty1, col_form, col_empty2 = st.columns([1, 2, 1])
    
    with col_form:
        st.markdown(
            "<div class='login-container'>",
            unsafe_allow_html=True
        )
        
        st.markdown("<h3 style='text-align:center;'>Iniciar Sesión</h3>", unsafe_allow_html=True)
        
        usuario_input = st.text_input(
            "👤 Usuario",
            placeholder="Ingresa tu usuario",
            key="login_usuario"
        )
        
        password_input = st.text_input(
            "🔐 Contraseña",
            type="password",
            placeholder="Ingresa tu contraseña",
            key="login_password"
        )
        
        if st.button(
            "🔓 Entrar al Hub",
            type="primary",
            use_container_width=True,
            key="btn_login"
        ):
            if not usuario_input or not password_input:
                st.error("⚠️ Por favor completa todos los campos.")
            else:
                usuario_valido = verificar_credenciales(usuario_input, password_input)
                
                if usuario_valido:
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = usuario_valido.get("nombre", usuario_input)
                    st.success(f"✅ Bienvenido, {usuario_valido.get('nombre', usuario_input)}!")
                    st.balloons()
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.divider()
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.info(
            "**Usuarios de Prueba:**\n\n"
            "👤 **admin** / 🔐 admin123\n\n"
            "👤 **contador** / 🔐 contador123"
        )
    
    with col_info2:
        st.info(
            "**Características:**\n\n"
            "✅ Extracción PDF + OCR\n"
            "✅ Importación JSON\n"
            "✅ Validación Gemini 1.5"
        )


def mostrar_dashboard():
    """Renderiza el dashboard principal después del login."""
    st.markdown(
        "<h2 style='font-family:Courier New,monospace; color:#666D57; "
        "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
        unsafe_allow_html=True
    )
    st.title("📊 Dashboard Principal")
    
    # Header con datos del usuario
    col_user1, col_user2, col_user3 = st.columns([2, 1, 1])
    
    with col_user1:
        st.markdown(f"### 👤 Sesión: **{st.session_state.usuario_actual}**")
    
    with col_user2:
        st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
    
    with col_user3:
        if st.button("🚪 Cerrar Sesión", key="btn_logout"):
            st.session_state.autenticado = False
            st.session_state.usuario_actual = None
            st.session_state.cliente_activo = None
            st.rerun()
    
    st.divider()
    
    # ── SELECTOR DE CLIENTE ACTIVO ──
    st.markdown("### 🏢 Seleccionar Cliente Activo")
    
    clientes_lista = clientes_data.get("clientes", [])
    
    if clientes_lista:
        nombres_clientes = {c.get("nombre"): c for c in clientes_lista}
        cliente_seleccionado = st.selectbox(
            "Elige un cliente",
            list(nombres_clientes.keys()),
            key="selector_cliente"
        )
        
        cliente_obj = nombres_clientes[cliente_seleccionado]
        
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            st.text(f"**NIT:** {cliente_obj.get('nit', 'N/A')}")
        with col_c2:
            st.text(f"**DUI:** {cliente_obj.get('dui', 'N/A')}")
        with col_c3:
            st.text(f"**Email:** {cliente_obj.get('email', 'N/A')}")
        
        if st.button("✅ Activar Cliente", type="primary", use_container_width=True):
            st.session_state.cliente_activo = cliente_obj
            st.success(f"✅ Cliente activado: **{cliente_obj.get('nombre')}**")
            st.info("Ahora puedes acceder a los extractores en el menú lateral.")
    else:
        st.warning("⚠️ No hay clientes registrados.")
    
    st.divider()
    
    # ── INFORMACIÓN DEL SISTEMA ──
    st.markdown("### 📈 Módulos Disponibles")
    
    modulos = [
        ("📈 Ventas", "Extrae DTE de ventas (01, 03, 05, 06, 11)", "1_Extractor_DTE_Ventas"),
        ("🛒 Compras", "Extrae DTE de compras (03, 05, 06, 07)", "2_Extractor_DTE_Compras"),
        ("✂️ Retenciones", "Extrae DTE-07 (retenciones 1%)", "3_Extractor_DTE_Retenciones"),
        ("⚖️ Sujetos Excluidos", "Extrae DTE-14 (retenciones 10%)", "4_Extractor_DTE_Sujetos_Excluidos"),
    ]
    
    col1, col2 = st.columns(2)
    
    for idx, (titulo, desc, pagina) in enumerate(modulos):
        col = col1 if idx % 2 == 0 else col2
        with col:
            st.markdown(
                f"**{titulo}**\n\n{desc}\n\n"
                f"*Accede desde el menú lateral →*",
                unsafe_allow_html=False
            )


# ═══════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════

if not st.session_state.autenticado:
    mostrar_registro_login()
else:
    mostrar_dashboard()
