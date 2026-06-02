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
st.set_page_config(page_title="Directorio Clientes · Learnix", layout="wide", page_icon="👥")

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
from utils.local_db import cargar_clientes_db, guardar_cliente_db, eliminar_cliente_db


def limpiar_numero(num: str) -> str:
    return re.sub(r"[^0-9]", "", str(num))


# ─────────────────────────────────────────────
# ENCABEZADO
# ─────────────────────────────────────────────
page_header(
    icon="👥",
    title="Directorio de Clientes",
    subtitle="Administra las empresas que auditas. Los datos se guardan localmente en el sistema.",
    badge="Local",
)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CARGA
# ─────────────────────────────────────────────
clientes: list[dict] = cargar_clientes_db()
clientes_por_id: dict[str, dict] = {c["id"]: c for c in clientes}

# ─────────────────────────────────────────────
# CLIENTE ACTIVO
# ─────────────────────────────────────────────
cliente_activo     = st.session_state.get("cliente_activo")
cliente_activo_nit = cliente_activo.get("nit") if isinstance(cliente_activo, dict) else None
cliente_activo_db  = next((c for c in clientes if c.get("nit") == cliente_activo_nit), None)

if cliente_activo_db:
    st.markdown(
        f"""
        <div style="background:var(--success-bg);border:1px solid var(--success-border);
                    border-radius:var(--radius);padding:10px 16px;margin-bottom:12px;
                    display:flex;align-items:center;gap:10px;font-size:0.88rem;">
          <span style="color:var(--success);font-size:1.1rem;">✅</span>
          <span style="color:var(--text-primary);">
            <strong>Cliente activo:</strong>&nbsp;
            {cliente_activo_db['nombre_comercial']}
            &nbsp;&nbsp;<code style="font-size:0.78rem;color:var(--text-secondary);">
            NIT&nbsp;{cliente_activo_db['nit']}</code>
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# LAYOUT: FORMULARIO + TABLA
# ─────────────────────────────────────────────
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    section_label("Agregar Empresa", "➕")
    with st.form("form_nuevo_cliente", clear_on_submit=True):
        f_nit       = st.text_input("NIT (sin guiones)*",               placeholder="06141234567890")
        f_nombre    = st.text_input("Razón Social / Nombre*",           placeholder="EMPRESA S.A. DE C.V.")
        f_nrc       = st.text_input("NRC (opcional)",                   placeholder="123456-7")
        f_dui       = st.text_input("DUI representante (opcional)",     placeholder="012345678")
        f_actividad = st.text_input("Giro o Actividad Económica (opcional)")

        submitted = st.form_submit_button(
            "💾 Guardar Empresa",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not f_nit.strip() or not f_nombre.strip():
                st.error("El NIT y la Razón Social son obligatorios.")
            else:
                nit_limpio = limpiar_numero(f_nit)
                if len(nit_limpio) not in (9, 14):
                    st.warning("⚠️ El NIT debe tener 9 o 14 dígitos. Verifica el formato.")
                else:
                    ok, err_msg = guardar_cliente_db(
                        nit       = nit_limpio,
                        nombre    = f_nombre.strip(),
                        nrc       = limpiar_numero(f_nrc),
                        dui       = limpiar_numero(f_dui),
                        actividad = f_actividad.strip(),
                    )
                    if ok:
                        st.success(f"✅ **{f_nombre.strip().upper()}** guardada correctamente.")
                        st.rerun()
                    else:
                        st.error(f"No se pudo guardar.{' ' + err_msg if err_msg else ''}")

with col2:
    section_label(f"Portafolio ({len(clientes)} empresa{'s' if len(clientes) != 1 else ''})", "📋")

    if clientes:
        df_clientes = pd.DataFrame([
            {
                "NIT":       c.get("nit", ""),
                "Nombre":    c.get("nombre_comercial", ""),
                "NRC":       c.get("nrc", ""),
                "DUI":       c.get("dui", ""),
                "Actividad": c.get("actividad", ""),
            }
            for c in clientes
        ])
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)

        # ── Zona de eliminación ──────────────────────────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="zona-peligro">', unsafe_allow_html=True)
        st.markdown(
            '<p class="zona-peligro-titulo">🗑️ Eliminar Empresa</p>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Borrar una empresa la elimina del portafolio, "
            "pero no afecta los DTEs ya procesados en sesión."
        )

        opciones_borrar = {
            f"{c['nit']} · {c['nombre_comercial']}": c["id"]
            for c in clientes
        }
        seleccion_borrar = st.selectbox(
            "Empresa a eliminar:",
            ["-- Ninguno --"] + list(opciones_borrar.keys()),
            label_visibility="collapsed",
        )

        if st.button("🗑️ Eliminar Definitivamente", type="secondary", use_container_width=True):
            if seleccion_borrar != "-- Ninguno --":
                id_borrar = opciones_borrar[seleccion_borrar]
                ok = eliminar_cliente_db(id_borrar)
                if ok:
                    ca = st.session_state.get("cliente_activo", {})
                    if ca and clientes_por_id.get(id_borrar, {}).get("nit") == ca.get("nit"):
                        st.session_state["cliente_activo"] = None
                    st.success("Empresa eliminada del portafolio.")
                    st.rerun()
                else:
                    st.error("No se pudo eliminar.")
            else:
                st.warning("Selecciona una empresa para eliminar.")

        st.markdown("</div>", unsafe_allow_html=True)

    else:
        empty_state(
            icon="🏢",
            title="Portafolio vacío",
            subtitle="Agrega tu primera empresa usando el formulario de la izquierda.",
            action_hint="→ Completa el formulario con NIT y Razón Social",
        )

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.markdown(
    "<p class='app-footer'>"
    "<strong>Learnix DTE Hub</strong> &nbsp;·&nbsp; Directorio Local</p>",
    unsafe_allow_html=True,
)
