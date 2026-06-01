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
st.set_page_config(page_title="Directorio Clientes", layout="wide", page_icon="👥")

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
from utils.local_db import (
    cargar_clientes_db,
    guardar_cliente_db,
    eliminar_cliente_db,
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
    st.title("👥 Directorio de Clientes")

st.write(
    "Administra las empresas que auditas. "
    "Los datos se guardan localmente en el sistema."
)

# ─────────────────────────────────────────────
# 6. CARGA DESDE SUPABASE
# ─────────────────────────────────────────────
clientes: list[dict] = cargar_clientes_db()
# Índice id → dict para lookups rápidos
clientes_por_id: dict[str, dict] = {c["id"]: c for c in clientes}

# ─────────────────────────────────────────────
# 7. ESTADO DE CLIENTE ACTIVO
# ─────────────────────────────────────────────
cliente_activo     = st.session_state.get("cliente_activo")
cliente_activo_nit = cliente_activo.get("nit") if isinstance(cliente_activo, dict) else None
cliente_activo_db  = next((c for c in clientes if c.get("nit") == cliente_activo_nit), None)

if cliente_activo_db:
    st.success(
        f"✅ **Cliente Activo:** {cliente_activo_db['nombre_comercial']} "
        f"(NIT: {cliente_activo_db['nit']})"
    )
else:
    st.info("No hay ningún cliente activo. Ve al Dashboard para seleccionar uno.")

st.divider()

# ─────────────────────────────────────────────
# 8. FORMULARIO + TABLA
# ─────────────────────────────────────────────
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.markdown("### ➕ Agregar Nueva Empresa")
    with st.form("form_nuevo_cliente", clear_on_submit=True):
        f_nit      = st.text_input("NIT (sin guiones)*",                placeholder="06141234567890")
        f_dui      = st.text_input("DUI (opcional, sin guiones)",        placeholder="01234567-8")
        f_nrc      = st.text_input("NRC (opcional)",                     placeholder="123456-7")
        f_nombre   = st.text_input("Razón Social / Nombre*",             placeholder="EMPRESA S.A. DE C.V.")
        f_actividad= st.text_input("Giro o Actividad Económica (opcional)")

        if st.form_submit_button("💾 Guardar en Portafolio", type="primary", use_container_width=True):
            if not f_nit.strip() or not f_nombre.strip():
                st.error("El NIT y la Razón Social son obligatorios.")
            else:
                nit_limpio = limpiar_numero(f_nit)
                if len(nit_limpio) not in (9, 14):
                    st.warning("⚠️ El NIT debe tener 9 o 14 dígitos. Verifica el formato.")
                else:
                    ok, err_msg = guardar_cliente_db(
                        nit      = nit_limpio,
                        nombre   = f_nombre.strip(),
                        nrc      = limpiar_numero(f_nrc),
                        dui      = limpiar_numero(f_dui),
                        actividad= f_actividad.strip(),
                    )
                    if ok:
                        st.success(f"✅ {f_nombre.strip().upper()} guardada correctamente.")
                        st.rerun()
                    else:
                        st.error(
                            f"No se pudo guardar. "
                            + (f"Detalle: {err_msg}" if err_msg else
                               "Verifica permisos o contacta al administrador.")
                        )

with col2:
    st.markdown("### 📋 Tu Portafolio Actual")
    if clientes:
        df_clientes = pd.DataFrame([
            {
                "NIT"      : c.get("nit", ""),
                "Nombre"   : c.get("nombre_comercial", ""),
                "NRC"      : c.get("nrc", ""),
                "DUI"      : c.get("dui", ""),
                "Actividad": c.get("actividad", ""),
            }
            for c in clientes
        ])
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)

        # ── Zona de eliminación ──────────────────────────────────────────────
        st.markdown('<div class="zona-peligro">', unsafe_allow_html=True)
        st.markdown(
            '<p class="zona-peligro-titulo">🗑️ Zona de Peligro — Eliminar Empresa</p>',
            unsafe_allow_html=True
        )
        st.caption(
            "Borrar una empresa no elimina sus facturas procesadas, "
            "pero ya no aparecerá en el menú. Solo admins pueden realizar esta acción."
        )

        opciones_borrar = {
            f"{c['nit']} · {c['nombre_comercial']}": c["id"]
            for c in clientes
        }
        seleccion_borrar = st.selectbox(
            "Selecciona la empresa a eliminar:",
            ["-- Ninguno --"] + list(opciones_borrar.keys()),
        )

        if st.button("🗑️ Eliminar Definitivamente", type="secondary"):
            if seleccion_borrar != "-- Ninguno --":
                id_borrar = opciones_borrar[seleccion_borrar]
                ok = eliminar_cliente_db(id_borrar)
                if ok:
                    # Limpiar cliente activo si era el eliminado
                    ca = st.session_state.get("cliente_activo", {})
                    if ca and clientes_por_id.get(id_borrar, {}).get("nit") == ca.get("nit"):
                        st.session_state["cliente_activo"] = None
                    st.success("Empresa eliminada del portafolio.")
                    st.rerun()
                else:
                    st.error("No se pudo eliminar. Es posible que no tengas permisos de administrador.")

        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.info("Tu portafolio está vacío. Agrega tu primera empresa a la izquierda.")
