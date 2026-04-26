import streamlit as st
import json
import os
import pandas as pd

# --- SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión.")
    st.stop()

st.set_page_config(page_title="Directorio Clientes", layout="wide", page_icon="👥")

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    div.stButton > button[kind="primary"] { background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; }
    div.stButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="primary"]:hover { background-color: #00407A !important; }
    .alerta-activo { padding: 15px; border-radius: 8px; border-left: 5px solid #00E5FF; background-color: #111111; margin-bottom: 20px; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

st.markdown("<h2 style='font-family: Courier New, monospace; color: #003057; letter-spacing: 2px; margin-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("👥 Directorio de Clientes (Portafolio)")
st.write("Administra las empresas que auditas. Estos datos se usarán en el Dashboard principal.")

# --- MANEJO DE BASE DE DATOS SEGURA ---
ARCHIVO_CLIENTES = "data/clientes.json"

def cargar_clientes():
    db_segura = {}
    if os.path.exists(ARCHIVO_CLIENTES):
        try:
            with open(ARCHIVO_CLIENTES, "r", encoding="utf-8") as f:
                raw_db = json.load(f)
                for key, val in raw_db.items():
                    if isinstance(val, dict): db_segura[key] = val
                    elif isinstance(val, str): db_segura[key] = {"nombre": val, "nit": key, "dui": ""}
                return db_segura
        except: pass
    return {}

def guardar_clientes(db):
    if not os.path.exists("data"): os.makedirs("data")
    with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

clientes = cargar_clientes()

# --- MOSTRAR CLIENTE ACTIVO CON LECTURA SEGURA ---
c_activo = st.session_state.get('cliente_activo')
if c_activo:
    # Usamos .get() para evitar KeyErrors si el JSON es viejo
    nombre_seguro = c_activo.get('nombre', 'Sin Nombre')
    nit_seguro = c_activo.get('nit', 'N/A')
    dui_seguro = c_activo.get('dui', 'N/A')
    
    st.markdown(f"""
    <div class="alerta-activo">
        <h4 style="margin:0; color:#00E5FF;">🏢 Cliente Seleccionado Actualmente</h4>
        <p style="margin:5px 0 0 0; color:#aaa;"><strong>Nombre:</strong> {nombre_seguro}</p>
        <p style="margin:0; color:#aaa;"><strong>NIT:</strong> {nit_seguro} &nbsp;&nbsp;|&nbsp;&nbsp; <strong>DUI:</strong> {dui_seguro}</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("No hay ningún cliente activo. Ve al Dashboard para seleccionar uno.")

st.divider()

# --- UI GESTIÓN DE PORTAFOLIO ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("➕ Agregar Nueva Empresa")
    with st.form("form_nuevo_cliente", clear_on_submit=True):
        nuevo_nit = st.text_input("NIT (Sin guiones, ej: 06141234567890)*")
        nuevo_dui = st.text_input("DUI (Opcional, sin guiones)")
        nuevo_nombre = st.text_input("Razón Social o Nombre Completo*")
        
        if st.form_submit_button("Guardar en Portafolio", type="primary", use_container_width=True):
            if not nuevo_nit or not nuevo_nombre:
                st.error("El NIT y el Nombre son obligatorios.")
            else:
                clientes[nuevo_nit] = {
                    "nombre": nuevo_nombre.strip().upper(),
                    "nit": nuevo_nit.strip(),
                    "dui": nuevo_dui.strip()
                }
                guardar_clientes(clientes)
                st.success(f"Empresa '{nuevo_nombre}' agregada con éxito.")
                st.rerun()

with col2:
    st.subheader("📋 Tu Portafolio Actual")
    if clientes:
        # Convertimos a DataFrame para verlo bonito
        df_clientes = pd.DataFrame.from_dict(clientes, orient='index')
        st.dataframe(df_clientes, use_container_width=True)
        
        with st.expander("🗑️ Zona de Peligro (Eliminar Empresa)"):
            nit_eliminar = st.selectbox("Selecciona el NIT a eliminar:", options=[""] + list(clientes.keys()))
            if st.button("Eliminar Permanentemente", type="secondary"):
                if nit_eliminar:
                    del clientes[nit_eliminar]
                    guardar_clientes(clientes)
                    if c_activo and c_activo.get('nit') == nit_eliminar:
                        st.session_state.cliente_activo = None
                    st.success("Empresa eliminada del portafolio.")
                    st.rerun()
    else:
        st.info("Tu portafolio está vacío. Agrega tu primera empresa a la izquierda.")
