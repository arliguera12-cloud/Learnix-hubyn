import streamlit as st
import json
import os
import pandas as pd
import re
import time
from io import StringIO

# st.set_page_config() ya ejecutado en app.py

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    div.stButton > button[kind="primary"] { background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; }
    div.stButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="secondary"] { background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; }
    .vendor-card { background-color: #1a1a1a; border-left: 3px solid #003057; padding: 12px; margin: 8px 0; border-radius: 4px; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 📋 CONSTANTES Y UTILIDADES
# ═══════════════════════════════════════════════════════════════

ARCHIVO_PROVEEDORES = "data/proveedores.json"


def crear_directorio():
    """Asegura que existe data/."""
    if not os.path.exists("data"):
        os.makedirs("data")


def cargar_proveedores():
    """Carga y migra automáticamente el formato."""
    crear_directorio()

    if not os.path.exists(ARCHIVO_PROVEEDORES):
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}

    try:
        with open(ARCHIVO_PROVEEDORES, "r", encoding="utf-8") as f:
            data = json.load(f)

            # MIGRACIÓN: string → dict con NRC
            for k, v in data.items():
                if isinstance(v, str):
                    data[k] = {"nombre": v, "nrc": ""}

            return data
    except json.JSONDecodeError:
        st.error("⚠️ Error: proveedores.json está corrupto.")
        return {}
    except Exception as e:
        st.error(f"⚠️ Error al cargar proveedores: {e}")
        return {}


def guardar_proveedores(db):
    """Guarda con validación."""
    crear_directorio()
    try:
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Error al guardar: {e}")


def limpiar_numero(num):
    """Extrae solo números."""
    return re.sub(r'[^0-9]', '', str(num))


def validar_nit(nit):
    """Valida NIT/DUI."""
    nit_limpio = limpiar_numero(nit)
    if len(nit_limpio) not in [9, 14]:
        return False, "NIT/DUI debe tener 9 o 14 dígitos"
    return True, nit_limpio


# ═══════════════════════════════════════════════════════════════
# 📊 CARGAR DATOS
# ═══════════════════════════════════════════════════════════════

db_proveedores = cargar_proveedores()

# ═══════════════════════════════════════════════════════════════
# 📱 HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family: Courier New, monospace; color: #003057; letter-spacing: 2px;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("🏢 Directorio de Proveedores")
st.write(
    "**Vendor Master Data** — Base maestra de proveedores que usarán automáticamente los extractores."
)
st.divider()

# ═══════════════════════════════════════════════════════════════
# 📑 TABS
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3 = st.tabs([
    "➕ Agregar / Actualizar",
    "📋 Base de Datos",
    "🚀 Carga Masiva (Excel)"
])

# ╔═══════════════════════════════════════════════════════════════╗
# ║ TAB 1: AGREGAR INDIVIDUAL                                     ║
# ╚═══════════════════════════════════════════════════════════════╝

with tab1:
    st.subheader("Agregar Proveedor Individual")

    with st.form("form_proveedor", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 4])

        with col1:
            nuevo_nit = st.text_input("NIT o DUI*", placeholder="06141234567890")
        with col2:
            nuevo_nrc = st.text_input("NRC (Opcional)", placeholder="123456")
        with col3:
            nuevo_nombre = st.text_input("Razón Social*", placeholder="Proveedor Oficial S.A.")

        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            submit_guardar = st.form_submit_button(
                "💾 Guardar Proveedor",
                type="primary",
                use_container_width=True
            )

        if submit_guardar:
            if not nuevo_nit or not nuevo_nombre:
                st.error("🚫 NIT y Nombre son **obligatorios**.")
            else:
                es_valido, nit_limpio = validar_nit(nuevo_nit)

                if not es_valido:
                    st.error(f"❌ {nit_limpio}")
                else:
                    nrc_limpio = limpiar_numero(nuevo_nrc) if nuevo_nrc else ""
                    db_proveedores[nit_limpio] = {
                        "nombre": nuevo_nombre.strip().upper(),
                        "nrc": nrc_limpio
                    }
                    guardar_proveedores(db_proveedores)
                    st.success(f"✅ Proveedor {nuevo_nombre.upper()} guardado.")
                    time.sleep(1)
                    st.rerun()

# ╔═══════════════════════════════════════════════════════════════╗
# ║ TAB 2: VER BASE DE DATOS                                      ║
# ╚═══════════════════════════════════════════════════════════════╝

with tab2:
    st.subheader("Base de Datos Completa")

    if db_proveedores:
        # Tabla principal
        lista_prov = []
        for nit, datos in db_proveedores.items():
            lista_prov.append({
                "NIT / DUI": nit,
                "NRC": datos.get("nrc", ""),
                "Nombre Registrado": datos.get("nombre", "")
            })

        df_prov = pd.DataFrame(lista_prov).sort_values("Nombre Registrado")
        st.dataframe(df_prov, use_container_width=True, hide_index=True)

        # Búsqueda rápida
        st.write("---")
        st.subheader("🔍 Búsqueda Rápida")
        termino_busqueda = st.text_input("Busca por NIT o Nombre:")

        if termino_busqueda:
            termino_upper = termino_busqueda.upper()
            resultados = [
                {"NIT": nit, "Nombre": v.get("nombre", ""), "NRC": v.get("nrc", "")}
                for nit, v in db_proveedores.items()
                if termino_upper in nit or termino_upper in v.get("nombre", "").upper()
            ]

            if resultados:
                st.dataframe(pd.DataFrame(resultados), use_container_width=True, hide_index=True)
            else:
                st.info("❌ No se encontraron resultados.")

        # Eliminar proveedor
        st.write("---")
        st.subheader("🗑️ Eliminar Proveedor")

        opciones_eliminar = ["-- Selecciona --"] + list(db_proveedores.keys())
        formato_elim = lambda x: (
            f"{x} → {db_proveedores[x]['nombre']}"
            if x != "-- Selecciona --"
            else x
        )

        nit_borrar = st.selectbox(
            "Selecciona para eliminar:",
            opciones_eliminar,
            format_func=formato_elim,
            key="sel_borrar_prov"
        )

        if st.button("🗑️ Eliminar", type="secondary", use_container_width=True):
            if nit_borrar != "-- Selecciona --":
                nombre_borrado = db_proveedores[nit_borrar]["nombre"]
                del db_proveedores[nit_borrar]
                guardar_proveedores(db_proveedores)
                st.success(f"✅ Proveedor '{nombre_borrado}' eliminado.")
                time.sleep(1)
                st.rerun()
    else:
        st.info("📭 No hay proveedores registrados aún.")

# ╔═══════════════════════════════════════════════════════════════╗
# ║ TAB 3: CARGA MASIVA                                           ║
# ╚═══════════════════════════════════════════════════════════════╝

with tab3:
    st.subheader("Inyectar Catálogo desde Excel/CSV")
    st.write("Sube un archivo con múltiples proveedores. El sistema los mapará automáticamente.")

    archivo_subido = st.file_uploader("Selecciona archivo", type=["xlsx", "csv"])

    if archivo_subido:
        try:
            if archivo_subido.name.endswith('.csv'):
                df_import = pd.read_csv(archivo_subido)
            else:
                df_import = pd.read_excel(archivo_subido)

            st.write(f"📊 Archivo cargado: **{len(df_import)}** filas")
            st.dataframe(df_import.head(10), use_container_width=True)

            st.write("---")
            st.subheader("Mapeo de Columnas")

            col1, col2, col3 = st.columns(3)
            with col1:
                col_nits = st.selectbox("Columna NIT/DUI", df_import.columns, key="col_nits")
            with col2:
                col_nrcs = st.selectbox(
                    "Columna NRC (Opcional)",
                    ["-- Ninguna --"] + list(df_import.columns),
                    key="col_nrcs"
                )
            with col3:
                col_noms = st.selectbox("Columna Nombre", df_import.columns, key="col_noms")

            if st.button("🚀 Inyectar al Sistema", type="primary", use_container_width=True):
                nuevos_agregados = 0
                duplicados = 0
                errores = []

                for index, row in df_import.iterrows():
                    try:
                        nit_raw = str(row[col_nits]) if pd.notna(row[col_nits]) else ""
                        nom_raw = str(row[col_noms]) if pd.notna(row[col_noms]) else ""
                        nrc_raw = (
                            str(row[col_nrcs])
                            if col_nrcs != "-- Ninguna --" and pd.notna(row[col_nrcs])
                            else ""
                        )

                        if not nit_raw or not nom_raw or nom_raw.lower() == "nan":
                            continue

                        nit_cln = limpiar_numero(nit_raw)
                        nrc_cln = limpiar_numero(nrc_raw)

                        if not nit_cln:
                            errores.append(f"Fila {index+2}: NIT vacío")
                            continue

                        if nit_cln in db_proveedores:
                            duplicados += 1
                        else:
                            nuevos_agregados += 1

                        db_proveedores[nit_cln] = {
                            "nombre": nom_raw.strip().upper(),
                            "nrc": nrc_cln
                        }
                    except Exception as e:
                        errores.append(f"Fila {index+2}: {str(e)}")

                guardar_proveedores(db_proveedores)

                # Resumen
                st.success("✅ **Inyección completada!**")
                col_res1, col_res2, col_res3 = st.columns(3)
                with col_res1:
                    st.metric("✨ Agregados", nuevos_agregados)
                with col_res2:
                    st.metric("♻️ Actualizados", duplicados)
                with col_res3:
                    st.metric("❌ Errores", len(errores))

                if errores:
                    with st.expander("Ver errores"):
                        for err in errores:
                            st.warning(err)

                time.sleep(2)
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error al procesar archivo: {e}")

# ═══════════════════════════════════════════════════════════════
# 📊 ESTADÍSTICAS (Bottom)
# ═══════════════════════════════════════════════════════════════

st.divider()
col_stat1, col_stat2, col_stat3 = st.columns(3)

with col_stat1:
    st.metric("Total de Proveedores", len(db_proveedores))

with col_stat2:
    prov_con_nrc = sum(1 for p in db_proveedores.values() if p.get("nrc"))
    st.metric("Con NRC Registrado", prov_con_nrc)

with col_stat3:
    st.metric("Estado", "✅ Sincronizado")
