import streamlit as st
import pandas as pd
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from styles import DARK_PRO_CSS

# ─────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Directorio Proveedores", layout="wide", page_icon="🏢")

# ─────────────────────────────────────────────
# 2. SEGURIDAD — Multi-tenant SaaS
# ─────────────────────────────────────────────
from utils.auth_guard import check_auth
check_auth()

# ─────────────────────────────────────────────
# 3. ESTILOS
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 4. IMPORTS DE BD
# ─────────────────────────────────────────────
from utils.supabase_client import (
    cargar_proveedores_db,
    guardar_proveedor_db,
    eliminar_proveedor_db,
    get_supabase,
)

def limpiar_numero(num: str) -> str:
    return re.sub(r'[^0-9]', '', str(num))

# ─────────────────────────────────────────────
# 5. ENCABEZADO
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #6AB040;"
        " letter-spacing: 3px; margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_titulo:
    st.title("🏢 Directorio de Proveedores")

org_nombre = (st.session_state.get("sb_organizacion") or {}).get("nombre", "tu organización")
st.write(
    f"Base de conocimiento de proveedores para **{org_nombre}**. "
    "El extractor de compras consulta esta lista automáticamente al procesar cada DTE."
)
st.divider()

# ─────────────────────────────────────────────
# 6. CARGA DESDE SUPABASE
# ─────────────────────────────────────────────
proveedores: list[dict] = cargar_proveedores_db()
prov_por_id: dict[str, dict] = {p["id"]: p for p in proveedores}

# ─────────────────────────────────────────────
# 7. TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "➕ Agregar / Actualizar",
    "📋 Tu Catálogo Privado",
    "🌐 Catálogo Global",
    "🚀 Carga Masiva",
])

# ── TAB 1: Formulario de alta ────────────────────────────────────────────────
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
            if not nuevo_nit.strip() or not nuevo_nombre.strip():
                st.error("El NIT y el Nombre son obligatorios.")
            else:
                nit_limpio = limpiar_numero(nuevo_nit)
                nrc_limpio = limpiar_numero(nuevo_nrc) if nuevo_nrc else ""
                ok = guardar_proveedor_db(
                    nit    = nit_limpio,
                    nombre = nuevo_nombre.strip(),
                    nrc    = nrc_limpio,
                )
                if ok:
                    st.success(f"✅ **{nuevo_nombre.strip().upper()}** guardado en tu catálogo privado.")
                    st.rerun()
                else:
                    st.error("No se pudo guardar. Intenta de nuevo.")

    st.info(
        "💡 **Alimentación automática:** Al procesar facturas en el Extractor de Compras, "
        "los nuevos proveedores se agregan aquí automáticamente."
    )

# ── TAB 2: Catálogo privado ──────────────────────────────────────────────────
with tab2:
    if proveedores:
        df_prov = pd.DataFrame([
            {
                "NIT / DUI": p.get("nit", ""),
                "NRC":       p.get("nrc", ""),
                "Nombre":    p.get("nombre_comercial", ""),
                "Agregado":  str(p.get("created_at", ""))[:10],
            }
            for p in proveedores
        ])
        st.dataframe(df_prov, use_container_width=True, hide_index=True)
        st.markdown(f"**{len(proveedores)} proveedores** en tu catálogo privado.")
        st.divider()

        # ── Eliminación ─────────────────────────────────────────────────────
        st.markdown("#### 🗑️ Eliminar Proveedor")
        st.caption("Solo administradores pueden eliminar. Acción irreversible.")

        opciones_borrar = {
            f"{p['nit']} · {p['nombre_comercial']}": p["id"]
            for p in proveedores
        }
        sel_borrar = st.selectbox(
            "Selecciona para eliminar:",
            ["-- Ninguno --"] + list(opciones_borrar.keys()),
        )
        if st.button("🗑️ Eliminar", type="secondary") and sel_borrar != "-- Ninguno --":
            id_borrar = opciones_borrar[sel_borrar]
            ok = eliminar_proveedor_db(id_borrar)
            if ok:
                st.success("Proveedor eliminado.")
                st.rerun()
            else:
                st.error("No se pudo eliminar. Verifica que tienes permisos de administrador.")
    else:
        st.info(
            "Tu catálogo privado está vacío. "
            "Se irá poblando automáticamente al procesar DTEs de compras, "
            "o agrégalos manualmente en la pestaña **Agregar / Actualizar**."
        )

# ── TAB 3: Catálogo global (solo lectura) ────────────────────────────────────
with tab3:
    st.markdown(
        "Lista maestra curada por Learnix. "
        "Estos proveedores están disponibles para **todas las organizaciones** "
        "y el extractor los consulta automáticamente como fallback."
    )
    try:
        resp = get_supabase().table("proveedores_globales").select("*").order("nombre_comercial").execute()
        globales: list[dict] = resp.data or []
    except Exception:
        globales = []

    if globales:
        df_global = pd.DataFrame([
            {
                "NIT":       g.get("nit", ""),
                "Nombre":    g.get("nombre_comercial", ""),
                "Categoría": g.get("categoria", "").title(),
            }
            for g in globales
        ])
        st.dataframe(df_global, use_container_width=True, hide_index=True)
        st.caption(f"{len(globales)} proveedores en el catálogo global.")
    else:
        st.info("El catálogo global aún no tiene entradas.")

    st.markdown(
        "<div style='background:#07142B; border:1px solid #21262D; border-radius:8px;"
        " padding:12px 16px; margin-top:12px; font-size:0.80rem; color:#8B949E;'>"
        "<strong style='color:#E6EDF3;'>¿Cómo funciona la búsqueda híbrida?</strong><br><br>"
        "1. El extractor extrae el NIT del PDF<br>"
        "2. Busca en tu <strong style='color:#58A6FF'>catálogo privado</strong> → nombre exacto de tu experiencia<br>"
        "3. Si no lo encuentra, busca en el <strong style='color:#56D364'>catálogo global</strong> → nombre estándar<br>"
        "4. Si tampoco está, extrae el nombre del texto del PDF y lo guarda en tu catálogo privado"
        "</div>",
        unsafe_allow_html=True,
    )

# ── TAB 4: Carga masiva ───────────────────────────────────────────────────────
with tab4:
    st.subheader("Carga Masiva desde Excel o CSV")
    st.write("Sube tu catálogo completo. El sistema lo importará a tu catálogo privado.")

    archivo_subido = st.file_uploader("Selecciona tu archivo", type=["xlsx", "csv"])

    if archivo_subido:
        try:
            if archivo_subido.name.endswith(".csv"):
                df_import = pd.read_csv(archivo_subido)
            else:
                df_import = pd.read_excel(archivo_subido)

            st.write("**Mapea las columnas de tu archivo:**")
            c1, c2, c3 = st.columns(3)
            with c1:
                col_nits = st.selectbox("Columna NIT", df_import.columns)
            with c2:
                col_nrcs = st.selectbox("Columna NRC (Opcional)", ["-- Ninguna --"] + list(df_import.columns))
            with c3:
                col_noms = st.selectbox("Columna Nombre", df_import.columns)

            st.write(f"Vista previa: **{len(df_import)} filas** detectadas.")
            st.dataframe(df_import.head(5), use_container_width=True)

            if st.button("🚀 Importar al Catálogo Privado", type="primary"):
                agregados   = 0
                errores     = 0
                progreso    = st.progress(0, text="Importando...")
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
                        ok = guardar_proveedor_db(
                            nit    = nit_cln,
                            nombre = nom_raw.strip(),
                            nrc    = nrc_cln,
                        )
                        if ok:
                            agregados += 1
                        else:
                            errores += 1

                    progreso.progress(
                        min((i + 1) / total_filas, 1.0),
                        text=f"Procesando fila {i + 1} de {total_filas}…"
                    )

                progreso.empty()
                if agregados:
                    st.success(f"🎉 **{agregados}** proveedores importados correctamente a tu catálogo privado.")
                if errores:
                    st.warning(f"⚠️ {errores} filas no pudieron importarse.")
                if agregados:
                    st.rerun()

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
