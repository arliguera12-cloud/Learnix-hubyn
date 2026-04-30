import streamlit as st
import json
import os
import pandas as pd
import re
import time

# st.set_page_config() ya ejecutado en app.py

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

# ═══════════════════════════════════════════════════════════════
# 📋 CONSTANTES Y UTILIDADES
# ═══════════════════════════════════════════════════════════════

ARCHIVO_CLIENTES = "data/clientes.json"


def crear_directorio():
    """Asegura que existe la carpeta data."""
    if not os.path.exists("data"):
        os.makedirs("data")


def cargar_clientes():
    """Carga clientes con manejo de errores robusto."""
    crear_directorio()

    if not os.path.exists(ARCHIVO_CLIENTES):
        with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}

    try:
        with open(ARCHIVO_CLIENTES, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Validar estructura
            for nit, cliente in data.items():
                if not isinstance(cliente, dict):
                    data[nit] = {
                        "nit": nit,
                        "nombre": str(cliente),
                        "dui": "",
                        "nrc": "",
                        "actividad": ""
                    }
            return data
    except json.JSONDecodeError:
        st.error("⚠️ Error al leer clientes.json. Archivo corrupto.")
        return {}
    except Exception as e:
        st.error(f"⚠️ Error inesperado: {e}")
        return {}


def guardar_clientes(db):
    """Guarda clientes con validación."""
    crear_directorio()
    try:
        with open(ARCHIVO_CLIENTES, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Error al guardar: {e}")


def limpiar_numero(num):
    """Extrae solo números de un string."""
    return re.sub(r'[^0-9]', '', str(num))


def validar_nit(nit):
    """Valida formato NIT salvadoreño."""
    nit_limpio = limpiar_numero(nit)
    if len(nit_limpio) not in [9, 14]:
        return False, "El NIT debe tener 9 (DUI) o 14 dígitos"
    return True, nit_limpio


# ═══════════════════════════════════════════════════════════════
# 📊 CARGAR DATOS
# ═══════════════════════════════════════════════════════════════

db_clientes = cargar_clientes()

# ═══════════════════════════════════════════════════════════════
# 📱 HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family: Courier New, monospace; color: #FF4B4B; letter-spacing: 2px;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("👥 Directorio de Clientes (Portafolio)")
st.write("Administra las empresas que auditas. Estos datos se usarán en el Dashboard principal.")

# ═══════════════════════════════════════════════════════════════
# 🟢 CLIENTE ACTIVO (Con blindaje contra None)
# ═══════════════════════════════════════════════════════════════

cliente_activo = st.session_state.get("cliente_activo")
if isinstance(cliente_activo, dict) and cliente_activo.get("nit") in db_clientes:
    nombre_activo = db_clientes[cliente_activo["nit"]]['nombre']
    st.success(f"✅ **Cliente Activo:** {nombre_activo} (NIT: {cliente_activo['nit']})")
else:
    st.info("💡 No hay cliente activo. Ve al Dashboard para seleccionar uno.")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 📐 LAYOUT: 2 COLUMNAS
# ═══════════════════════════════════════════════════════════════

col1, col2 = st.columns([1, 2], gap="large")

# ╔═══════════════════════════════════════════════════════════════╗
# ║ COLUMNA 1: AGREGAR CLIENTE                                    ║
# ╚═══════════════════════════════════════════════════════════════╝

with col1:
    st.markdown("### ➕ Agregar Nueva Empresa")
    with st.form("form_nuevo_cliente", clear_on_submit=True):
        f_nit = st.text_input(
            "NIT o DUI*",
            placeholder="06141234567890 o 12345678-1"
        )
        f_nombre = st.text_input(
            "Razón Social*",
            placeholder="Mi Empresa S.A. de C.V."
        )
        f_dui = st.text_input(
            "DUI (Opcional)",
            placeholder="12345678-1"
        )
        f_nrc = st.text_input(
            "NRC (Opcional)",
            placeholder="123456"
        )
        f_actividad = st.text_input(
            "Giro/Actividad (Opcional)",
            placeholder="Comercio minorista"
        )

        if st.form_submit_button("💾 Guardar en Portafolio", type="primary", use_container_width=True):
            if not f_nit.strip() or not f_nombre.strip():
                st.error("🚫 El NIT y la Razón Social son **obligatorios**.")
            else:
                es_valido, nit_limpio = validar_nit(f_nit)

                if not es_valido:
                    st.error(f"❌ {nit_limpio}")
                elif nit_limpio in db_clientes:
                    st.warning(f"⚠️ La empresa con NIT {nit_limpio} ya existe. Actualiza en la derecha.")
                else:
                    db_clientes[nit_limpio] = {
                        "nit": nit_limpio,
                        "nombre": f_nombre.strip().upper(),
                        "dui": limpiar_numero(f_dui),
                        "nrc": limpiar_numero(f_nrc),
                        "actividad": f_actividad.strip().upper()
                    }
                    guardar_clientes(db_clientes)
                    st.success(f"✅ Empresa {f_nombre.upper()} guardada correctamente.")
                    time.sleep(1.5)
                    st.rerun()

# ╔═══════════════════════════════════════════════════════════════╗
# ║ COLUMNA 2: VER Y GESTIONAR                                    ║
# ╚═══════════════════════════════════════════════════════════════╝

with col2:
    st.markdown("### 📋 Tu Portafolio Actual")

    if db_clientes:
        # Tabla de clientes
        lista_mostrar = []
        for nit, datos in db_clientes.items():
            lista_mostrar.append({
                "NIT": nit,
                "Nombre": datos.get("nombre", ""),
                "DUI": datos.get("dui", ""),
                "NRC": datos.get("nrc", ""),
                "Actividad": datos.get("actividad", "")
            })

        df_clientes = pd.DataFrame(lista_mostrar)
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)

        # Zona de peligro
        st.write("---")
        with st.expander("🗑️ Zona de Peligro — Eliminar Empresa", expanded=False):
            st.warning(
                "⚠️ Esta acción no se puede deshacer. Las facturas se mantendrán "
                "pero la empresa desaparecerá del menú."
            )

            opciones_borrar = ["-- Selecciona para eliminar --"] + list(db_clientes.keys())
            formato = lambda x: (
                f"{x} → {db_clientes[x]['nombre']}"
                if x != "-- Selecciona para eliminar --"
                else x
            )

            nit_borrar = st.selectbox(
                "Selecciona empresa a eliminar:",
                opciones_borrar,
                format_func=formato,
                key="sel_borrar_cliente"
            )

            if st.button("🗑️ Eliminar Definitivamente", type="secondary", use_container_width=True):
                if nit_borrar != "-- Selecciona para eliminar --":
                    nombre_borrado = db_clientes[nit_borrar]["nombre"]
                    del db_clientes[nit_borrar]
                    guardar_clientes(db_clientes)

                    # Limpiar sesión si era el activo
                    if st.session_state.get("cliente_activo", {}).get("nit") == nit_borrar:
                        st.session_state.cliente_activo = None

                    st.success(f"✅ Empresa '{nombre_borrado}' eliminada del portafolio.")
                    time.sleep(1.5)
                    st.rerun()
    else:
        st.info("📭 Tu portafolio está vacío. Agrega tu primera empresa a la izquierda.")

# ═══════════════════════════════════════════════════════════════
# 📊 ESTADÍSTICAS RÁPIDAS (Bottom)
# ═══════════════════════════════════════════════════════════════

st.divider()
col_stats1, col_stats2, col_stats3 = st.columns(3)

with col_stats1:
    st.metric("Total de Empresas", len(db_clientes))

with col_stats2:
    cliente_activo_count = (
        1
        if isinstance(cliente_activo, dict) and cliente_activo.get("nit") in db_clientes
        else 0
    )
    st.metric("Con Cliente Activo", cliente_activo_count)

with col_stats3:
    st.metric("Últimas 24h", "Espera sincronización", delta=None)
