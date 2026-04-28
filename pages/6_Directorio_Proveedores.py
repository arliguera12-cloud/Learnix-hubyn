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
        # Si no existe, crea un archivo vacío
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    
    with open(ARCHIVO_PROVEEDORES, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return {}

def guardar_proveedores(db):
    with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def limpiar_numero(num):
    return re.sub(r'[^0-9]', '', str(num))

db_proveedores = cargar_proveedores()

st.markdown("<h2 style='font-family: Courier New, monospace; color: #003057; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("🏢 Directorio de Proveedores")
st.write("Base de datos maestra (Vendor Master Data). Los extractores usarán esta lista para bautizar automáticamente a los proveedores usando su NIT.")
st.divider()

# --- NUEVA ESTRUCTURA DE 3 PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["➕ Agregar / Actualizar", "📋 Ver Base de Datos", "🚀 Carga Masiva (Excel/CSV)"])

# PESTAÑA 1: AGREGAR MANUAL
with tab1:
    with st.form("form_proveedor", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nuevo_nit = st.text_input("NIT o DUI del Proveedor (Obligatorio)*")
        with col2:
            nuevo_nombre = st.text_input("Nombre Oficial para Hacienda (Obligatorio)*")
            
        if st.form_submit_button("💾 Guardar Proveedor", type="primary"):
            if not nuevo_nit or not nuevo_nombre:
                st.error("Ambos campos son obligatorios.")
            else:
                nit_limpio = limpiar_numero(nuevo_nit)
                db_proveedores[nit_limpio] = nuevo_nombre.strip().upper()
                guardar_proveedores(db_proveedores)
                st.success(f"✅ ¡Proveedor {nuevo_nombre.upper()} guardado!")
                time.sleep(1)
                st.rerun()

# PESTAÑA 2: VER Y ELIMINAR
with tab2:
    if db_proveedores:
        df_prov = pd.DataFrame(list(db_proveedores.items()), columns=["NIT / DUI", "Nombre Registrado"])
        # Usamos use_container_width para que se estire correctamente en Streamlit
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

# PESTAÑA 3: CARGA MASIVA (NUEVO)
with tab3:
    st.subheader("Subir Catálogo Completo desde tu Despacho")
    st.write("Sube un archivo **Excel** o **CSV**. El sistema extraerá los NITs y los guardará para que la IA sea más rápida.")
    archivo_subido = st.file_uploader("Selecciona tu archivo", type=["xlsx", "csv"])
    
    if archivo_subido:
        try:
            if archivo_subido.name.endswith('.csv'): 
                df_import = pd.read_csv(archivo_subido)
            else: 
                df_import = pd.read_excel(archivo_subido)
            
            st.write("Vista previa del documento:")
            st.dataframe(df_import.head(), use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                col_nits = st.selectbox("¿Qué columna tiene los NITs?", df_import.columns)
            with col2:
                col_noms = st.selectbox("¿Qué columna tiene los Nombres Comerciales?", df_import.columns)
            
            if st.button("🚀 Inyectar al Cerebro Central", type="primary"):
                nuevos_agregados = 0
                for index, row in df_import.iterrows():
                    nit_raw = str(row[col_nits])
                    nom_raw = str(row[col_noms])
                    
                    if pd.isna(row[col_nits]) or pd.isna(row[col_noms]): 
                        continue
                        
                    nit_cln = limpiar_numero(nit_raw)
                    if nit_cln and nom_raw and nom_raw.lower() != "nan":
                        db_proveedores[nit_cln] = nom_raw.strip().upper()
                        nuevos_agregados += 1
                
                guardar_proveedores(db_proveedores)
                st.success(f"🎉 ¡Éxito! Se inyectaron/actualizaron {nuevos_agregados} proveedores. La IA ahora los reconocerá al instante.")
                time.sleep(2)
                st.rerun()
                
        except Exception as e:
            st.error(f"Ocurrió un error al leer el archivo: {e}")
