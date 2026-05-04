import streamlit as st
import json
import os
import pandas as pd
import re

# ─────────────────────────────────────────────
# 1. PAGE CONFIG — SIEMPRE PRIMERO
# ─────────────────────────────────────────────
st.set_page_config(page_title="Directorio Proveedores", layout="wide", page_icon="🏢")

# ─────────────────────────────────────────────
# 2. ESTILOS — VERDE OLIVA UNIFICADO
# ─────────────────────────────────────────────
ESTILO = """
<style>
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"]          { background-color: #0D0F07 !important; }
  [data-testid="stSidebar"]         { background-color: #141A08 !important;
                                      border-right: 1px solid #4A5520 !important; }

  h1, h2, h3, h4, h5, h6           { color: #C8D87A !important; letter-spacing: 0.5px; }
  p, label, span, li                { color: #F0EDD8 !important; }
  [data-testid="stDataFrame"] span  { color: inherit !important; }

  div.stButton > button[kind="primary"],
  div.stDownloadButton > button[kind="primary"] {
    background-color : #6B7A2A !important;
    border           : 1px solid #8A9A35 !important;
    border-radius    : 6px !important;
    transition       : background-color 0.25s ease, transform 0.1s ease;
  }
  div.stButton > button[kind="primary"]:hover,
  div.stDownloadButton > button[kind="primary"]:hover {
    background-color : #8A9A35 !important;
    transform        : scale(1.02);
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #FFFFFF !important; font-weight: bold !important;
  }

  div.stButton > button[kind="secondary"] {
    background-color : transparent !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    transition       : 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover { background-color: #1A2008 !important; }
  div.stButton > button[kind="secondary"] *     { color: #C8D87A !important; }

  div[data-testid="stTextInput"] input {
    background-color : #1A2008 !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    color            : #F0EDD8 !important;
    caret-color      : #C8D87A;
  }
  div[data-testid="stTextInput"] input:focus {
    border-color : #8A9A35 !important;
    box-shadow   : 0 0 0 2px rgba(138,154,53,0.25) !important;
  }

  div[data-testid="stSelectbox"] > div > div {
    background-color : #1A2008 !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    color            : #F0EDD8 !important;
  }

  button[data-baseweb="tab"]                       { color: #8A9A35 !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom : 2px solid #8A9A35 !important;
    color         : #F0EDD8 !important;
  }

  div[data-testid="stAlert"] { display: flex; align-items: center; }
  hr                         { border-color: #4A5520 !important; opacity: 0.4; }
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. VERIFICACIÓN DE SEGURIDAD
# ─────────────────────────────────────────────
if not st.session_state.get("autenticado"):
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

# ─────────────────────────────────────────────
# 4. FUNCIONES
# ─────────────────────────────────────────────
ARCHIVO_PROVEEDORES = "data/proveedores.json"

def cargar_proveedores() -> dict:
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(ARCHIVO_PROVEEDORES):
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    with open(ARCHIVO_PROVEEDORES, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            # Migración automática: string → dict
            for k, v in data.items():
                if isinstance(v, str):
                    data[k] = {"nombre": v, "nrc": ""}
            return data
        except Exception:
            return {}

def guardar_proveedores(db: dict) -> None:
    with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def limpiar_numero(num: str) -> str:
    return re.sub(r'[^0-9]', '', str(num))

# ─────────────────────────────────────────────
# 5. ENCABEZADO
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #8A9A35;"
        " letter-spacing: 3px; margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_titulo:
    st.title("🏢 Directorio de Proveedores")

st.write(
    "Base de datos maestra (Vendor Master Data). "
    "Los extractores usarán esta lista para identificar automáticamente a los proveedores."
)
st.divider()

db_proveedores = cargar_proveedores()

# ─────────────────────────────────────────────
# 6. TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["➕ Agregar / Actualizar", "📋 Ver Base de Datos", "🚀 Carga Masiva"])

with tab1:
    with st.form("form_proveedor", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 4])
        with col1:
            nuevo_nit = st.text_input("NIT o DUI*", placeholder="06141234567890")
        with col2:
            nuevo_nrc = st.text_input("NRC (opcional)", placeholder="123456-7")
        with col3:
            nuevo_nombre = st.text_input("Razón Social Oficial*", placeholder="PROVEEDOR S.A. DE C.V.")

        if st.form_submit_button("💾 Guardar Proveedor", type="primary"):
            if not nuevo_nit or not nuevo_nombre:
                st.error("El NIT y el Nombre son obligatorios.")
            else:
                nit_limpio = limpiar_numero(nuevo_nit)
                nrc_limpio = limpiar_numero(nuevo_nrc) if nuevo_nrc else ""
                db_proveedores[nit_limpio] = {
                    "nombre": nuevo_nombre.strip().upper(),
                    "nrc"   : nrc_limpio
                }
                guardar_proveedores(db_proveedores)
                st.success(f"✅ {nuevo_nombre.upper()} guardado correctamente.")
                st.rerun()

with tab2:
    if db_proveedores:
        lista_prov = [
            {
                "NIT / DUI"       : k,
                "NRC"             : v.get("nrc", ""),
                "Nombre Registrado": v.get("nombre", "")
            }
            for k, v in db_proveedores.items()
        ]
        df_prov = pd.DataFrame(lista_prov)
        st.dataframe(df_prov, use_container_width=True, hide_index=True)

        st.markdown(f"**Total de proveedores registrados:** `{len(db_proveedores)}`")
        st.divider()
        st.markdown("#### 🗑️ Eliminar Proveedor")
        nit_borrar = st.selectbox(
            "Selecciona para eliminar:",
            ["-- Ninguno --"] + list(db_proveedores.keys()),
            format_func=lambda x: (
                f"{x} · {db_proveedores[x].get('nombre','')}" if x != "-- Ninguno --" else x
            )
        )
        if st.button("🗑️ Eliminar", type="secondary") and nit_borrar != "-- Ninguno --":
            del db_proveedores[nit_borrar]
            guardar_proveedores(db_proveedores)
            st.success("Proveedor eliminado correctamente.")
            st.rerun()
    else:
        st.info("No hay proveedores registrados aún.")

with tab3:
    st.subheader("Carga Masiva desde Excel o CSV")
    st.write("Sube un archivo con tu catálogo completo. El sistema extraerá NITs, NRCs y Nombres.")

    archivo_subido = st.file_uploader("Selecciona tu archivo", type=["xlsx", "csv"])

    if archivo_subido:
        try:
            if archivo_subido.name.endswith('.csv'):
                df_import = pd.read_csv(archivo_subido)
            else:
                df_import = pd.read_excel(archivo_subido)

            st.write("**Mapea las columnas de tu archivo:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                col_nits = st.selectbox("Columna NIT", df_import.columns)
            with col2:
                col_nrcs = st.selectbox("Columna NRC (Opcional)", ["-- Ninguna --"] + list(df_import.columns))
            with col3:
                col_noms = st.selectbox("Columna Nombre", df_import.columns)

            st.write(f"Vista previa: **{len(df_import)} filas** detectadas.")
            st.dataframe(df_import.head(5), use_container_width=True)

            if st.button("🚀 Inyectar al Directorio", type="primary"):
                agregados = 0
                for _, row in df_import.iterrows():
                    if pd.isna(row[col_nits]) or pd.isna(row[col_noms]):
                        continue
                    nit_raw = str(row[col_nits])
                    nom_raw = str(row[col_noms])
                    nrc_raw = str(row[col_nrcs]) if col_nrcs != "-- Ninguna --" else ""

                    nit_cln = limpiar_numero(nit_raw)
                    nrc_cln = limpiar_numero(nrc_raw)

                    if nit_cln and nom_raw and nom_raw.lower() != "nan":
                        db_proveedores[nit_cln] = {
                            "nombre": nom_raw.strip().upper(),
                            "nrc"   : nrc_cln
                        }
                        agregados += 1

                guardar_proveedores(db_proveedores)
                st.success(f"🎉 Se inyectaron/actualizaron **{agregados}** proveedores correctamente.")
                st.rerun()

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
