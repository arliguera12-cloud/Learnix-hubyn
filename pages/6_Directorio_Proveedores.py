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

# Proveedores base para iniciar la base de datos
PROVEEDORES_INICIALES = {
    "06141603991030": "PRICESMART EL SALVADOR, S.A. DE C.V.",
    "06142810921030": "SERVICIOS FINANCIEROS, S.A. DE C.V.",
    "06142108061015": "MAK MEATS, S.A. DE C.V.",
    "06141512201045": "DELIVERY HERO EL SALVADOR (PEDIDOSYA)",
    "06141905991030": "UNIGAS DE EL SALVADOR, S.A DE C.V.",
    "06142904720020": "TIENDA MORENA S.A DE C.V.",
    "06143008161116": "MARZAURI, S.A. DE C.V. (PUERTO PLAZA)",
    "06142609111020": "DISTRIBUIDORA AXBEN, S.A. DE C.V.",
    "05092506721016": "PEDRO RAMIREZ RAMIREZ",
    "05090706851019": "FRANCISCO MELARA (LACTEOS CARMENCITA)",
    "06142101881394": "KARLA GUADALUPE VASQUEZ HERNANDEZ",
    "06142308031030": "PAPELERA SALVADOREÑA RZ, S.A. DE C.V.",
    "05092209761017": "ROBERTO CARLOS BOLAÑOS BONILLA",
    "06141101690011": "CALLEJA, S.A. DE C.V. (SUPER SELECTOS)",
    "06142704071095": "BELCA EL SALVADOR, S.A. DE C.V.",
    "06140607101084": "DISTRIBUCION SALVADOREÑA, S.A. DE C.V.",
    "06141503071023": "GRUHERCA SA DE CV",
    "06140902840024": "LACTEOS DEL CORRAL, S.A. DE C.V."
}

def cargar_proveedores():
    if not os.path.exists("data"): os.makedirs("data")
    if not os.path.exists(ARCHIVO_PROVEEDORES):
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump(PROVEEDORES_INICIALES, f, indent=4, ensure_ascii=False)
        return PROVEEDORES_INICIALES.copy()
    
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

tab1, tab2 = st.tabs(["➕ Agregar / Actualizar", "📋 Ver Base de Datos"])

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

with tab2:
    if db_proveedores:
        df_prov = pd.DataFrame(list(db_proveedores.items()), columns=["NIT / DUI", "Nombre Registrado"])
        # REEMPLAZO APLICADO AQUÍ
        st.dataframe(df_prov, width="stretch", hide_index=True)
        
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
        st.info("No hay proveedores.")