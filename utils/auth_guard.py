"""
auth_guard.py — Protección de rutas simplificada (sin Supabase).
"""
from __future__ import annotations
import streamlit as st


def check_auth(rol=None, verificar_suscripcion: bool = False) -> None:
    if not st.session_state.get("autenticado"):
        st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.error("⛔ Sesión no iniciada")
            st.markdown(
                "<p style='text-align:center;color:#8B949E'>Vuelve al inicio e ingresa tu contraseña.</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<div style='text-align:center;margin-top:8px'>"
                "<a href='/' target='_self' style='"
                "display:inline-block;width:100%;padding:10px 0;"
                "background:#21262D;color:#C9D1D9;text-decoration:none;"
                "border:1px solid #30363D;border-radius:6px;font-size:14px'>"
                "← Ir al inicio</a></div>",
                unsafe_allow_html=True,
            )
        st.stop()


def check_limite_dtes() -> bool:
    return True
