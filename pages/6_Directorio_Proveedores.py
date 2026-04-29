import streamlit as st
import json
import os
import pandas as pd
import re
import time

st.set_page_config(page_title="Directorio Proveedores", layout="wide", page_icon="🏢")

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    div.stButton > button[kind="primary"] { background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; }
    div.stButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="secondary"] { background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

ARCHIVO_PROVEEDORES = "data/proveedores.json"

def cargar_proveedores():
    if not os.path.exists("data"): 
        os.makedirs("data")
    if not os.path.exists(ARCHIVO_PROVEEDORES):
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    
    with open(ARCHIVO_PROVEEDORES, "r", encoding="utf-8") as f:
        try: 
            data = json.load(f)
            # MIGRACIÓN AUTOMÁTICA: Pasa del formato viejo al nuevo con NRC
            for k, v in data.items():
                if isinstance(v, str):
                    data[k] = {"nombre": v, "nrc": ""}
            return data
        except: return {}

def guardar_proveedores(db):
    with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def limpiar_numero(num):
    return re.sub(r'[^0-9]', '', str(num))

db_proveedores = cargar_proveedores()

st.markdown("<h2 style='font-family: Courier New, monospace; color: #003057; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("🏢 Directorio de Proveedores")
st.write("Base de datos maestra (Vendor Master Data). Los extractores usarán esta lista para bautizar automáticamente a los proveedores.")
st.divider()

tab1, tab2, tab3 = st.tabs(["➕ Agregar / Actualizar", "📋 Ver Base de Datos", "🚀 Carga Masiva"])

with tab1:
    with st.form("form_proveedor", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 4])
        with col1:
            nuevo_nit = st.text_input("NIT o DUI (Obligatorio)*")
        with col2:
            nuevo_nrc = st.text_input("NRC (Opcional)")
        with col3:
            nuevo_nombre = st.text_input("Razón Social Oficial (Obligatorio)*")
            
        if st.form_submit_button("💾 Guardar Proveedor", type="primary"):
            if not nuevo_nit or not nuevo_nombre:
                st.error("El NIT y el Nombre son obligatorios.")
            else:
                nit_limpio = limpiar_numero(nuevo_nit)
                nrc_limpio = limpiar_numero(nuevo_nrc) if nuevo_nrc else ""
                db_proveedores[nit_limpio] = {"nombre": nuevo_nombre.strip().upper(), "nrc": nrc_limpio}
                guardar_proveedores(db_proveedores)
                st.success(f"✅ ¡Proveedor {nuevo_nombre.upper()} guardado!")
                time.sleep(1)
                st.rerun()

with tab2:
    if db_proveedores:
        lista_prov = []
        for k, v in db_proveedores.items():
            lista_prov.append({"NIT / DUI": k, "NRC": v.get("nrc", ""), "Nombre Registrado": v.get("nombre", "")})
            
        df_prov = pd.DataFrame(lista_prov)
        st.dataframe(df_prov, use_container_width=True, hide_index=True)
        
        st.write("---")
        st.markdown("#### 🗑️ Eliminar Proveedor")
        nit_borrar = st.selectbox("Selecciona para eliminar:", ["-- Ninguno --"] + list(db_proveedores.keys()))
        if st.button("Eliminar", type="secondary") and nit_borrar != "-- Ninguno --":
            del db_proveedores[nit_borrar]
            guardar_proveedores(db_proveedores)
            st.success("Proveedor eliminado.")
            time.sleep(1)
            st.rerun()
    else:
        st.info("No hay proveedores registrados.")

with tab3:
    st.subheader("Subir Catálogo Completo desde tu Despacho")
    st.write("Sube un Excel. El sistema extraerá los NITs, NRCs y Nombres.")
    archivo_subido = st.file_uploader("Selecciona tu archivo", type=["xlsx", "csv"])
    
    if archivo_subido:
        try:
            if archivo_subido.name.endswith('.csv'): df_import = pd.read_csv(archivo_subido)
            else: df_import = pd.read_excel(archivo_subido)
            
            st.write("Mapea las columnas de tu Excel:")
            col1, col2, col3 = st.columns(3)
            with col1: col_nits = st.selectbox("Columna NIT", df_import.columns)
            with col2: col_nrcs = st.selectbox("Columna NRC (Opcional)", ["-- Ninguna --"] + list(df_import.columns))
            with col3: col_noms = st.selectbox("Columna Nombre", df_import.columns)
            
            if st.button("🚀 Inyectar al Cerebro Central", type="primary"):
                nuevos_agregados = 0
                for index, row in df_import.iterrows():
                    nit_raw = str(row[col_nits])
                    nom_raw = str(row[col_noms])
                    nrc_raw = str(row[col_nrcs]) if col_nrcs != "-- Ninguna --" else ""
                    
                    if pd.isna(row[col_nits]) or pd.isna(row[col_noms]): continue
                        
                    nit_cln = limpiar_numero(nit_raw)
                    nrc_cln = limpiar_numero(nrc_raw)
                    if nit_cln and nom_raw and nom_raw.lower() != "nan":
                        db_proveedores[nit_cln] = {"nombre": nom_raw.strip().upper(), "nrc": nrc_cln}
                        nuevos_agregados += 1
                
                guardar_proveedores(db_proveedores)
                st.success(f"🎉 ¡Éxito! Se inyectaron/actualizaron {nuevos_agregados} proveedores.")
                time.sleep(2)
                st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
