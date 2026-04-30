import streamlit as st
import json
import os
import pandas as pd
import re
import time

st.set_page_config(page_title="Directorio Clientes", layout="wide", page_icon="👥")

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    div.stButton > button[kind="primary"] { background-color: #FF4B4B !important; border: 1px solid #FF4B4B !important; border-radius: 6px; }
    div.stButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="secondary"] { background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

ARCHIVO_CLIENTES = "data/clientes.json"

def cargar_clientes():
    if not os.path.exists("data"): 
        os.makedirs("data")
    if not os.path.exists(ARCHIVO_CLIENTES):
        with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    
    with open(ARCHIVO_CLIENTES, "r", encoding="utf-8") as f:
        try: 
            return json.load(f)
        except: return {}

def guardar_clientes(db):
    with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def limpiar_numero(num):
    return re.sub(r'[^0-9]', '', str(num))

db_clientes = cargar_clientes()

st.title("👥 Directorio de Clientes (Portafolio)")
st.write("Administra las empresas que auditas. Estos datos se usarán en el Dashboard principal.")

# --- ALERTA DE CLIENTE ACTIVO ---
cliente_activo_nit = st.session_state.get("cliente_activo", {}).get("nit", None)
if cliente_activo_nit and cliente_activo_nit in db_clientes:
    nombre_activo = db_clientes[cliente_activo_nit]['nombre']
    st.success(f"✅ **Cliente Activo actual:** {nombre_activo} (NIT: {cliente_activo_nit})")
else:
    st.info("No hay ningún cliente activo. Ve al Dashboard para seleccionar uno.")

st.divider()

col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.markdown("### ➕ Agregar Nueva Empresa")
    with st.form("form_nuevo_cliente", clear_on_submit=True):
        f_nit = st.text_input("NIT (Sin guiones, ej: 06141234567890)*")
        f_dui = st.text_input("DUI (Opcional, sin guiones)")
        f_nrc = st.text_input("NRC (Opcional)")
        f_nombre = st.text_input("Razón Social o Nombre Completo*")
        f_actividad = st.text_input("Giro o Actividad Económica (Opcional)")
        
        if st.form_submit_button("Guardar en Portafolio", type="primary", use_container_width=True):
            if not f_nit or not f_nombre:
                st.error("El NIT y la Razón Social son obligatorios.")
            else:
                nit_limpio = limpiar_numero(f_nit)
                db_clientes[nit_limpio] = {
                    "nit": nit_limpio,
                    "nombre": f_nombre.strip().upper(),
                    "dui": limpiar_numero(f_dui),
                    "nrc": limpiar_numero(f_nrc),
                    "actividad": f_actividad.strip().upper()
                }
                guardar_clientes(db_clientes)
                st.success(f"Empresa {f_nombre.upper()} guardada.")
                time.sleep(1)
                st.rerun()

with col2:
    st.markdown("### 📋 Tu Portafolio Actual")
    if db_clientes:
        lista_mostrar = []
        for nit, datos in db_clientes.items():
            lista_mostrar.append({
                "NIT": nit,
                "Nombre": datos.get("nombre", ""),
                "NRC": datos.get("nrc", ""),
                "DUI": datos.get("dui", ""),
                "Actividad": datos.get("actividad", "")
            })
        
        df_clientes = pd.DataFrame(lista_mostrar)
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)
        
        with st.expander("🗑️ Zona de Peligro (Eliminar Empresa)"):
            st.warning("Borrar una empresa no eliminará sus facturas, pero ya no aparecerá en el menú.")
            nit_borrar = st.selectbox("Selecciona la empresa a eliminar:", ["-- Ninguno --"] + list(db_clientes.keys()), format_func=lambda x: f"{x} - {db_clientes[x]['nombre']}" if x != "-- Ninguno --" else x)
            if st.button("Eliminar Definitivamente", type="secondary"):
                if nit_borrar != "-- Ninguno --":
                    del db_clientes[nit_borrar]
                    guardar_clientes(db_clientes)
                    if st.session_state.get("cliente_activo", {}).get("nit") == nit_borrar:
                        st.session_state.cliente_activo = None
                    st.success("Empresa eliminada del portafolio.")
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("Tu portafolio está vacío. Agrega tu primera empresa a la izquierda.")
