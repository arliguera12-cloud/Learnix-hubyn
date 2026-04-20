import streamlit as st
import json
import os
import pandas as pd
import re
import time

st.set_page_config(page_title="Directorio de Clientes", layout="wide", page_icon="👥")

# --- DISEÑO MODO OSCURO ---
estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    
    div.stButton > button[kind="primary"] { 
        background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; transition: 0.3s;
    }
    div.stButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="primary"]:hover { background-color: #00407A !important; }
    
    div.stButton > button[kind="secondary"] { background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; }
    div.stButton > button[kind="secondary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    
    .alerta-activo {
        padding: 15px; border-radius: 8px; border-left: 5px solid #00E5FF;
        background-color: #001f3f; color: white; margin-bottom: 20px;
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# --- RUTAS Y FUNCIONES DE BASE DE DATOS ---
ARCHIVO_CLIENTES = "data/clientes.json"

def cargar_clientes():
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(ARCHIVO_CLIENTES):
        with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(ARCHIVO_CLIENTES, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return {}

def guardar_clientes(clientes):
    with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
        json.dump(clientes, f, indent=4, ensure_ascii=False)

def limpiar_numero(numero_bruto):
    return re.sub(r'[^0-9]', '', str(numero_bruto))

# --- INICIALIZACIÓN DE ESTADO GLOBAL ---
if "cliente_activo" not in st.session_state:
    st.session_state.cliente_activo = None

db_clientes = cargar_clientes()

# --- ENCABEZADO ---
st.markdown("<h2 style='font-family: Courier New, monospace; color: #003057; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("👥 Directorio de Clientes")
st.write("Administra los perfiles fiscales. El cliente activo será usado por los módulos de Ventas y Compras.")

# --- SECCIÓN: CLIENTE ACTIVO ---
if st.session_state.cliente_activo:
    c_activo = st.session_state.cliente_activo
    st.markdown(f"""
    <div class="alerta-activo">
        <h4 style='margin-top:0px; color:#00E5FF;'>🟢 Cliente Activo Actual</h4>
        <strong>Nombre:</strong> {c_activo['nombre']} <br>
        <strong>NIT:</strong> {c_activo['nit']} &nbsp;&nbsp;|&nbsp;&nbsp; <strong>DUI:</strong> {c_activo.get('dui', 'N/A')} &nbsp;&nbsp;|&nbsp;&nbsp; <strong>NRC:</strong> {c_activo['nrc']}
    </div>
    """, unsafe_allow_html=True)
else:
    st.warning("⚠️ No hay ningún cliente activo. Selecciona uno para poder usar los extractores.")

st.divider()

# --- PESTAÑAS DE ADMINISTRACIÓN ---
tab1, tab2, tab3 = st.tabs(["🎯 Seleccionar Cliente", "➕ Nuevo Cliente", "📋 Ver Base de Datos"])

# PESTAÑA 1: SELECCIONAR CLIENTE
with tab1:
    if not db_clientes:
        st.info("La base de datos está vacía. Ve a la pestaña 'Nuevo Cliente'.")
    else:
        st.subheader("Activar Entorno de Trabajo")
        opciones = [f"{datos['nombre']} (NIT: {nit})" for nit, datos in db_clientes.items()]
        seleccion = st.selectbox("Selecciona el cliente que deseas procesar:", ["-- Seleccione --"] + opciones)
        
        if st.button("Activar Cliente", type="primary") and seleccion != "-- Seleccione --":
            nit_seleccionado = seleccion.split("NIT: ")[1].replace(")", "").strip()
            st.session_state.cliente_activo = {
                "nit": nit_seleccionado,
                "nombre": db_clientes[nit_seleccionado]["nombre"],
                "nrc": db_clientes[nit_seleccionado]["nrc"],
                "dui": db_clientes[nit_seleccionado].get("dui", "")
            }
            st.success(f"¡Entorno configurado para: {db_clientes[nit_seleccionado]['nombre']}!")
            time.sleep(0.5)
            st.rerun()

# PESTAÑA 2: AGREGAR CLIENTE
with tab2:
    st.subheader("Crear Nuevo Perfil Fiscal")
    with st.form("form_nuevo_cliente", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nuevo_nit = st.text_input("NIT (Obligatorio)*")
            nuevo_dui = st.text_input("DUI (Si está homologado con el NIT)")
            nuevo_nrc = st.text_input("NRC")
        with col2:
            nuevo_nombre = st.text_input("Nombre Legal o Razón Social (Obligatorio)*")
            nueva_actividad = st.text_input("Actividad Económica")
            
        submit_btn = st.form_submit_button("💾 Guardar Cliente", type="primary")
        
        if submit_btn:
            if not nuevo_nit or not nuevo_nombre:
                st.error("El NIT y el Nombre son obligatorios.")
            else:
                nit_limpio = limpiar_numero(nuevo_nit)
                dui_limpio = limpiar_numero(nuevo_dui)
                
                if nit_limpio in db_clientes:
                    st.error("❌ Este NIT ya existe en la base de datos.")
                else:
                    db_clientes[nit_limpio] = {
                        "nombre": nuevo_nombre.strip().upper(),
                        "nrc": nuevo_nrc.strip(),
                        "dui": dui_limpio,
                        "actividad": nueva_actividad.strip().upper()
                    }
                    guardar_clientes(db_clientes)
                    st.success("✅ ¡Cliente guardado exitosamente!")
                    time.sleep(0.5)
                    st.rerun()

# PESTAÑA 3: VER DIRECTORIO
with tab3:
    st.subheader("Directorio General")
    if db_clientes:
        lista_datos = []
        for nit, datos in db_clientes.items():
            lista_datos.append({
                "NIT": nit,
                "DUI": datos.get("dui", ""),
                "Nombre / Razón Social": datos["nombre"],
                "NRC": datos["nrc"],
                "Actividad": datos["actividad"]
            })
            
        df_clientes = pd.DataFrame(lista_datos)
        # REEMPLAZO APLICADO AQUÍ
        st.dataframe(df_clientes, width="stretch", hide_index=True)
        
        st.write("---")
        st.markdown("#### 🗑️ Zona de Eliminación")
        nit_borrar = st.selectbox("Selecciona un cliente para eliminar:", ["-- Ninguno --"] + list(db_clientes.keys()))
        if st.button("Eliminar Cliente", type="secondary") and nit_borrar != "-- Ninguno --":
            del db_clientes[nit_borrar]
            guardar_clientes(db_clientes)
            if st.session_state.cliente_activo and st.session_state.cliente_activo["nit"] == nit_borrar:
                st.session_state.cliente_activo = None
            st.success("Cliente eliminado del directorio.")
            time.sleep(0.5)
            st.rerun()
    else:
        st.info("No hay clientes registrados aún.")