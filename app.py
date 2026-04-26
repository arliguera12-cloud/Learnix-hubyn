import streamlit as st
import time
import json
import os
import hashlib

# --- 1. CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="Learnix Hub", page_icon="🏢", layout="centered")

# --- 2. ESTILOS GLOBALES ---
estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    div.stButton > button[kind="primary"] { 
        background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; 
    }
    div.stButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="primary"]:hover { background-color: #00407A !important; }
    
    /* Estilos extra para las pestañas de Login/Registro */
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { color: #4DA8DA !important; border-bottom-color: #4DA8DA !important; }
    .stTabs [data-baseweb="tab-list"] button { color: #777777 !important; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# --- 3. FASE 1: GESTOR DE BASE DE DATOS Y SEGURIDAD ---
DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER): 
    os.makedirs(DATA_FOLDER)

def hash_password(password):
    """Encripta la contraseña por seguridad antes de guardarla."""
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
            return False # El usuario ya existe
        # Creamos la estructura del nuevo contador/despacho
        usuarios[username] = {
            "password": hash_password(password), 
            "clientes": [] # Aquí guardaremos su portafolio de empresas
        }
        with open(archivo, "w", encoding="utf-8") as f: 
            json.dump(usuarios, f, indent=4, ensure_ascii=False)
        return True
    
    if accion == "login":
        if username in usuarios and usuarios[username]["password"] == hash_password(password):
            return True
        return False

# --- 4. CONTROL DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None

# --- 5. FASE 2: UI DE LOGIN Y REGISTRO ---
def mostrar_registro_login():
    st.markdown("<h1 style='text-align: center; color: #00E5FF !important;'>Learnix Hub</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888888 !important;'>Plataforma Inteligente de Auditoría Tributaria</p>", unsafe_allow_html=True)
    st.write("")
    
    # Sistema de Pestañas (Tabs)
    tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta"])
    
    with tab_login:
        with st.form("login_form"):
            user = st.text_input("Usuario / Email")
            pw = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Entrar al Hub", type="primary", use_container_width=True)
            
            if submit_login:
                if gestionar_usuarios("login", user, pw):
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_actual"] = user
                    st.success("✅ Acceso concedido. Iniciando módulos...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")

    with tab_reg:
        with st.form("reg_form"):
            new_user = st.text_input("Elige un nombre de usuario")
            new_pw = st.text_input("Crea una contraseña segura", type="password")
            confirm_pw = st.text_input("Confirma tu contraseña", type="password")
            submit_reg = st.form_submit_button("Registrarme", type="primary", use_container_width=True)
            
            if submit_reg:
                if not new_user or not new_pw:
                    st.warning("⚠️ Por favor, completa todos los campos.")
                elif new_pw != confirm_pw:
                    st.warning("⚠️ Las contraseñas no coinciden.")
                elif gestionar_usuarios("registro", new_user, new_pw):
                    st.success("✅ ¡Cuenta creada con éxito! Ve a la pestaña 'Iniciar Sesión' para entrar.")
                else:
                    st.error("❌ Este usuario ya existe. Por favor elige otro.")

# --- 6. NAVEGACIÓN Y ENRUTAMIENTO ---
if not st.session_state["autenticado"]:
    mostrar_registro_login()
else:
    # Definición de rutas EXACTAS según tu carpeta 'pages'
    page_ventas = st.Page("pages/1_Extractor_DTE_Ventas.py", title="Extractor DTE Ventas", icon="📈")
    page_compras = st.Page("pages/2_Extractor_DTE_Compras.py", title="Extractor DTE Compras", icon="🛒")
    page_retenciones = st.Page("pages/3_Extractor_DTE_retenciones.py", title="Extractor DTE Retenciones", icon="✂️")
    page_sujetos = st.Page("pages/4_Extractor_DTE_Sujetos_Excluidos.py", title="Extractor DTE Sujetos Excluidos", icon="⚖️")
    
    page_clientes = st.Page("pages/5_Directorio_Clientes.py", title="Directorio Clientes", icon="👥")
    page_proveedores = st.Page("pages/6_Directorio_Proveedores.py", title="Directorio Proveedores", icon="🏢")
    
    # Menú lateral organizado por categorías
    nav = st.navigation({
        "⚙️ Módulos de Procesamiento": [
            page_ventas, 
            page_compras,
            page_retenciones,
            page_sujetos
        ],
        "🗄️ Administración": [
            page_clientes, 
            page_proveedores
        ]
    })
    
    # Ejecutamos la página seleccionada
    nav.run()
