import streamlit as st
import json
import os
import pandas as pd
import re

# ─────────────────────────────────────────────
# 1. PAGE CONFIG — SIEMPRE PRIMERO
# ─────────────────────────────────────────────
st.set_page_config(page_title="Directorio Clientes", layout="wide", page_icon="👥")

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

  /* ── Botón primario (guardar) ── */
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

  /* ── Botón secundario (acciones neutras) ── */
  div.stButton > button[kind="secondary"] {
    background-color : transparent !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    transition       : 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover { background-color: #1A2008 !important; }
  div.stButton > button[kind="secondary"] *     { color: #C8D87A !important; }

  /* ── Inputs ── */
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

  /* ── Selectbox ── */
  div[data-testid="stSelectbox"] > div > div {
    background-color : #1A2008 !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    color            : #F0EDD8 !important;
  }

  div[data-testid="stAlert"] { display: flex; align-items: center; }
  hr                         { border-color: #4A5520 !important; opacity: 0.4; }

  /* ── Zona de peligro ── */
  .zona-peligro {
    background-color : #200A08;
    border           : 1px solid #6B2020;
    border-radius    : 8px;
    padding          : 14px 16px;
    margin-top       : 12px;
  }
  .zona-peligro-titulo {
    color       : #E08060 !important;
    font-weight : bold;
    font-size   : 0.9rem;
    margin-bottom: 8px;
  }
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
ARCHIVO_CLIENTES = "data/clientes.json"

def cargar_clientes() -> dict:
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(ARCHIVO_CLIENTES):
        with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    with open(ARCHIVO_CLIENTES, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def guardar_clientes(db: dict) -> None:
    with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
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
    st.title("👥 Directorio de Clientes")
st.write("Administra las empresas que auditas. Estos datos se usarán en el Dashboard principal.")

# ─────────────────────────────────────────────
# 6. ESTADO DE CLIENTE ACTIVO
# ─────────────────────────────────────────────
db_clientes = cargar_clientes()

cliente_activo     = st.session_state.get("cliente_activo")
cliente_activo_nit = cliente_activo.get("nit") if isinstance(cliente_activo, dict) else None

if cliente_activo_nit and cliente_activo_nit in db_clientes:
    nombre_activo = db_clientes[cliente_activo_nit]['nombre']
    st.success(f"✅ **Cliente Activo:** {nombre_activo} (NIT: {cliente_activo_nit})")
else:
    st.info("No hay ningún cliente activo. Ve al Dashboard para seleccionar uno.")

st.divider()

# ─────────────────────────────────────────────
# 7. FORMULARIO + TABLA
# ─────────────────────────────────────────────
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.markdown("### ➕ Agregar Nueva Empresa")
    with st.form("form_nuevo_cliente", clear_on_submit=True):
        f_nit      = st.text_input("NIT (sin guiones)*", placeholder="06141234567890")
        f_dui      = st.text_input("DUI (opcional, sin guiones)", placeholder="01234567-8")
        f_nrc      = st.text_input("NRC (opcional)", placeholder="123456-7")
        f_nombre   = st.text_input("Razón Social / Nombre*", placeholder="EMPRESA S.A. DE C.V.")
        f_actividad= st.text_input("Giro o Actividad Económica (opcional)")

        if st.form_submit_button("💾 Guardar en Portafolio", type="primary", use_container_width=True):
            if not f_nit or not f_nombre:
                st.error("El NIT y la Razón Social son obligatorios.")
            else:
                nit_limpio = limpiar_numero(f_nit)
                if len(nit_limpio) not in (9, 14):
                    st.warning("⚠️ El NIT debe tener 9 o 14 dígitos. Verifica el formato.")
                else:
                    db_clientes[nit_limpio] = {
                        "nit"      : nit_limpio,
                        "nombre"   : f_nombre.strip().upper(),
                        "dui"      : limpiar_numero(f_dui),
                        "nrc"      : limpiar_numero(f_nrc),
                        "actividad": f_actividad.strip().upper()
                    }
                    guardar_clientes(db_clientes)
                    st.success(f"✅ {f_nombre.upper()} guardada correctamente.")
                    st.rerun()

with col2:
    st.markdown("### 📋 Tu Portafolio Actual")
    if db_clientes:
        lista_mostrar = [
            {
                "NIT"      : nit,
                "Nombre"   : datos.get("nombre", ""),
                "NRC"      : datos.get("nrc", ""),
                "DUI"      : datos.get("dui", ""),
                "Actividad": datos.get("actividad", "")
            }
            for nit, datos in db_clientes.items()
        ]
        df_clientes = pd.DataFrame(lista_mostrar)
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)

        # Zona de eliminación
        st.markdown('<div class="zona-peligro">', unsafe_allow_html=True)
        st.markdown('<p class="zona-peligro-titulo">🗑️ Zona de Peligro — Eliminar Empresa</p>', unsafe_allow_html=True)
        st.caption("Borrar una empresa no eliminará sus facturas procesadas, pero ya no aparecerá en el menú.")

        nit_borrar = st.selectbox(
            "Selecciona la empresa a eliminar:",
            ["-- Ninguno --"] + list(db_clientes.keys()),
            format_func=lambda x: (
                f"{x} · {db_clientes[x]['nombre']}" if x != "-- Ninguno --" else x
            )
        )
        if st.button("🗑️ Eliminar Definitivamente", type="secondary"):
            if nit_borrar != "-- Ninguno --":
                del db_clientes[nit_borrar]
                guardar_clientes(db_clientes)
                if st.session_state.get("cliente_activo", {}).get("nit") == nit_borrar:
                    st.session_state.cliente_activo = None
                st.success("Empresa eliminada del portafolio.")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.info("Tu portafolio está vacío. Agrega tu primera empresa a la izquierda.")
