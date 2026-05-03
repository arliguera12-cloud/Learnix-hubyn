import streamlit as st
import time

# --- CONFIGURACIÓN DE PÁGINA (Debe ser la primera línea) ---
st.set_page_config(page_title="Learnix DTE Hub", layout="centered", page_icon="⚡")

# --- ESTILOS VISUALES DEL LOGIN ---
estilo_login = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    h1, h2, h3, p, label { color: #F7F5EE !important; }
    div.stButton > button[kind="primary"] { background-color: #4DA8DA !important; border: none !important; border-radius: 6px; width: 100%; color: black !important; font-weight: bold !important;}
    div.stButton > button[kind="primary"]:hover { background-color: #3B8BB8 !important; }
    .login-box { background-color: #161616; padding: 40px; border-radius: 12px; border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
</style>
"""
st.markdown(estilo_login, unsafe_allow_html=True)

# --- SISTEMA DE AUTENTICACIÓN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #4DA8DA !important; font-family: Courier New, monospace; letter-spacing: 2px;'>YN</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Acceso al Sistema</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888 !important;'>Ingresa tus credenciales para continuar.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            usuario = st.text_input("Usuario", placeholder="admin")
            clave = st.text_input("Contraseña", type="password", placeholder="••••••••")
            
            if st.form_submit_button("Iniciar Sesión", type="primary"):
                # AQUI DEFINES TU USUARIO Y CONTRASEÑA OFICIALES
                if usuario.lower() == "admin" and clave == "learnix2026":
                    st.session_state["autenticado"] = True
                    st.success("Acceso concedido. Cargando entorno...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop() # Detiene la ejecución para que no cargue el resto del menú si no hay login

# --- NAVEGACIÓN Y MENÚ LATERAL (Solo se ejecuta si está autenticado) ---

# Definimos las páginas apuntando a los archivos en la carpeta 'pages'
page_dashboard = st.Page("pages/0_Dashboard_Inicio.py", title="Dashboard Hub", icon="🏠")
page_ventas = st.Page("pages/1_Extractor_DTE_Ventas.py", title="Extractor DTE Ventas", icon="📈")
page_compras = st.Page("pages/2_Extraer_DTE_Compras.py", title="Extractor DTE Compras", icon="🛒")
page_retenciones = st.Page("pages/3_Extractor_DTE_Retenciones.py", title="Extractor DTE Retenciones", icon="✂️")
page_sujetos = st.Page("pages/4_Extractor_DTE_Sujetos_Excluidos.py", title="Extractor DTE Sujetos Excluidos", icon="⚖️")
page_clientes = st.Page("pages/5_Directorio_Clientes.py", title="Directorio Clientes", icon="👥")
page_proveedores = st.Page("pages/6_Directorio_Proveedores.py", title="Directorio Proveedores", icon="🏢")

# Agrupamos las páginas en secciones para que el menú se vea profesional
secciones_menu = {
    "🚀 Inicio": [page_dashboard],
    "⚙️ Módulos de Procesamiento": [page_ventas, page_compras, page_retenciones, page_sujetos],
    "📁 Administración": [page_clientes, page_proveedores]
}

# Inicializamos el orquestador de navegación
nav = st.navigation(secciones_menu)

# Logo y botón de cerrar sesión en la barra lateral
st.sidebar.markdown("<h2 style='font-family: Courier New, monospace; color: #4DA8DA; letter-spacing: 2px; text-align: center;'>YN</h2>", unsafe_allow_html=True)
st.sidebar.divider()

# Ejecutamos la página seleccionada
nav.run()

# Botón de Cerrar Sesión al final del menú
st.sidebar.divider()
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.clear()
    st.rerun()
