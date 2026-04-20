import streamlit as st
import time

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
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# --- 3. CONTROL DE SESIÓN (EL CANDADO) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

def login():
    st.markdown("<h1 style='text-align: center; color: #00E5FF !important;'>Learnix Hub</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #888888 !important;'>Acceso Corporativo</h3>", unsafe_allow_html=True)
    st.write("")
    
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        # --- REEMPLAZO APLICADO AQUÍ ---
        submit = st.form_submit_button("Iniciar Sesión", type="primary", width="stretch")
        
        if submit:
            if usuario == "admin" and password == "admin123":
                st.session_state["autenticado"] = True
                st.success("✅ Acceso concedido. Iniciando módulos...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas.")

# --- 4. NAVEGACIÓN Y ENRUTAMIENTO ---
if not st.session_state["autenticado"]:
    login()
else:
    # Definición de rutas EXACTAS según tu carpeta 'pages'
    page_ventas = st.Page("pages/1_Extractor_DTE_Ventas.py", title="Extractor DTE Ventas", icon="📈")
    page_compras = st.Page("pages/2_Extractor_DTE_Compras.py", title="Extractor DTE Compras", icon="🛒")
    page_retenciones = st.Page("pages/3_Extractor_DTE_retenciones.py", title="Extractor DTE Retenciones", icon="✂️")
    
    # --- NUEVO MÓDULO AGREGADO AQUÍ ---
    page_sujetos = st.Page("pages/4_Extractor_DTE_Sujetos_Excluidos.py", title="Extractor DTE Sujetos Excluidos", icon="⚖️")
    
    # Ajusta los números de los directorios si es necesario (ej. 5_ y 6_)
    page_clientes = st.Page("pages/5_Directorio_Clientes.py", title="Directorio Clientes", icon="👥")
    page_proveedores = st.Page("pages/6_Directorio_Proveedores.py", title="Directorio Proveedores", icon="🏢")
    
    # Menú lateral organizado por categorías
    nav = st.navigation({
        "⚙️ Módulos de Procesamiento": [
            page_ventas, 
            page_compras,
            page_retenciones,
            page_sujetos # Agregado al menú
        ],
        "🗄️ Administración": [
            page_clientes, 
            page_proveedores
        ]
    })
    
    # Ejecutamos la página seleccionada
    nav.run()
    
