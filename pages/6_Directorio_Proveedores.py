import streamlit as st
import pandas as pd
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from styles import DARK_PRO_CSS

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Directorio Proveedores · Learnix", layout="wide", page_icon="🏢")

# ─────────────────────────────────────────────
# SEGURIDAD
# ─────────────────────────────────────────────
from utils.auth_guard import check_auth
check_auth()

# ─────────────────────────────────────────────
# ESTILOS
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────
from components.ui_components import page_header, section_label, empty_state
from utils.local_db import cargar_proveedores_db, guardar_proveedor_db, eliminar_proveedor_db


def limpiar_numero(num: str) -> str:
    return re.sub(r"[^0-9]", "", str(num))


# ─────────────────────────────────────────────
# ENCABEZADO
# ─────────────────────────────────────────────
page_header(
    icon="🏢",
    title="Directorio de Proveedores",
    subtitle="Base de conocimiento de proveedores. El extractor de compras consulta esta lista al procesar cada DTE.",
    badge="Local",
)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CARGA
# ─────────────────────────────────────────────
proveedores: list[dict] = cargar_proveedores_db()
prov_por_id: dict[str, dict] = {p["id"]: p for p in proveedores}

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "➕ Agregar / Actualizar",
    f"📋 Catálogo ({len(proveedores)})",
    "🚀 Carga Masiva",
])

# ── TAB 1: Formulario ────────────────────────────────────────────────────────
with tab1:
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    with st.form("form_proveedor", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 4])
        with col1:
            nuevo_nit = st.text_input("NIT o DUI*", placeholder="06141234567890")
        with col2:
            nuevo_nrc = st.text_input("NRC (opcional)", placeholder="123456-7")
        with col3:
            nuevo_nombre = st.text_input("Razón Social Oficial*", placeholder="PROVEEDOR S.A. DE C.V.")

        if st.form_submit_button("💾 Guardar Proveedor", type="primary", use_container_width=True):
            if not nuevo_nit.strip() or not nuevo_nombre.strip():
                st.error("El NIT/DUI y el Nombre son obligatorios.")
            else:
                nit_limpio = limpiar_numero(nuevo_nit)
                nrc_limpio = limpiar_numero(nuevo_nrc) if nuevo_nrc else ""
                if not nit_limpio:
                    st.error("El NIT/DUI debe contener dígitos.")
                else:
                    ok = guardar_proveedor_db(
                        nit    = nit_limpio,
                        nombre = nuevo_nombre.strip(),
                        nrc    = nrc_limpio,
                    )
                    if ok:
                        st.success(f"✅ **{nuevo_nombre.strip().upper()}** guardado en el catálogo.")
                        st.rerun()
                    else:
                        st.error("No se pudo guardar. Intenta de nuevo.")

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    st.info(
        "💡 **Alimentación automática:** Al procesar comprobantes en el Extractor de Compras, "
        "los nuevos proveedores se agregan aquí automáticamente."
    )

# ── TAB 2: Catálogo ──────────────────────────────────────────────────────────
with tab2:
    if proveedores:
        df_prov = pd.DataFrame([
            {
                "NIT / DUI": p.get("nit", ""),
                "NRC":       p.get("nrc", ""),
                "Nombre":    p.get("nombre_comercial", ""),
            }
            for p in proveedores
        ])
        st.dataframe(df_prov, use_container_width=True, hide_index=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="zona-peligro">', unsafe_allow_html=True)
        st.markdown('<p class="zona-peligro-titulo">🗑️ Eliminar Proveedor</p>', unsafe_allow_html=True)

        opciones_borrar = {
            f"{p['nit']} · {p['nombre_comercial']}": p["id"]
            for p in proveedores
        }
        sel_borrar = st.selectbox(
            "Proveedor a eliminar:",
            ["-- Ninguno --"] + list(opciones_borrar.keys()),
            label_visibility="collapsed",
        )
        if st.button("🗑️ Eliminar", type="secondary", use_container_width=True):
            if sel_borrar != "-- Ninguno --":
                ok = eliminar_proveedor_db(opciones_borrar[sel_borrar])
                if ok:
                    st.success("Proveedor eliminado del catálogo.")
                    st.rerun()
                else:
                    st.error("No se pudo eliminar.")
            else:
                st.warning("Selecciona un proveedor para eliminar.")

        st.markdown("</div>", unsafe_allow_html=True)

    else:
        empty_state(
            icon="🏭",
            title="Catálogo vacío",
            subtitle=(
                "Se poblará automáticamente al procesar DTEs de compras, "
                "o agrégalos manualmente en la pestaña Agregar."
            ),
        )

# ── TAB 3: Carga masiva ───────────────────────────────────────────────────────
with tab3:
    section_label("Importar desde Excel o CSV", "🚀")
    st.write("Sube tu catálogo completo. Mapea las columnas y el sistema los importa en lote.")

    archivo_subido = st.file_uploader(
        "Selecciona archivo Excel o CSV",
        type=["xlsx", "csv"],
        label_visibility="collapsed",
    )

    if archivo_subido:
        try:
            if archivo_subido.name.endswith(".csv"):
                df_import = pd.read_csv(archivo_subido)
            else:
                df_import = pd.read_excel(archivo_subido)

            st.write("**Mapea las columnas de tu archivo:**")
            c1, c2, c3 = st.columns(3)
            with c1:
                col_nits = st.selectbox("Columna NIT / DUI", df_import.columns)
            with c2:
                col_nrcs = st.selectbox("Columna NRC (opcional)", ["-- Ninguna --"] + list(df_import.columns))
            with c3:
                col_noms = st.selectbox("Columna Nombre", df_import.columns)

            st.dataframe(df_import.head(5), use_container_width=True)
            st.caption(f"{len(df_import)} filas detectadas en el archivo.")

            if st.button("🚀 Importar al Catálogo", type="primary", use_container_width=True):
                agregados   = 0
                errores     = 0
                progreso    = st.progress(0, text="Importando…")
                total_filas = len(df_import)

                for i, (_, row) in enumerate(df_import.iterrows()):
                    if pd.isna(row[col_nits]) or pd.isna(row[col_noms]):
                        continue
                    nit_raw = str(row[col_nits])
                    nom_raw = str(row[col_noms])
                    nrc_raw = str(row[col_nrcs]) if col_nrcs != "-- Ninguna --" else ""

                    nit_cln = limpiar_numero(nit_raw)
                    nrc_cln = limpiar_numero(nrc_raw)

                    if nit_cln and nom_raw and nom_raw.lower() not in ("nan", "none", ""):
                        ok = guardar_proveedor_db(nit=nit_cln, nombre=nom_raw.strip(), nrc=nrc_cln)
                        agregados += 1 if ok else 0
                        errores   += 0 if ok else 1

                    progreso.progress(min((i + 1) / total_filas, 1.0), text=f"Fila {i+1} / {total_filas}…")

                progreso.empty()
                if agregados:
                    st.success(f"🎉 **{agregados}** proveedores importados correctamente.")
                if errores:
                    st.warning(f"⚠️ {errores} filas no pudieron importarse.")
                if agregados:
                    st.rerun()

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.markdown(
    "<p class='app-footer'>"
    "<strong>Learnix DTE Hub</strong> &nbsp;·&nbsp; Directorio Local</p>",
    unsafe_allow_html=True,
)
