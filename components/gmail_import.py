"""
gmail_import.py — Componente reutilizable para importar facturas desde Gmail.

Se renderiza dentro de una pestaña en los extractores (Compras, Ventas, ...).
Busca adjuntos PDF/JSON por remitente / texto y devuelve los seleccionados como
objetos `GmailFile`, que se inyectan en el mismo pipeline que el `file_uploader`.

Uso:
    from components.gmail_import import render_gmail_import
    gmail_files = render_gmail_import("comp")   # prefijo único por extractor
    archivos = (archivos or []) + gmail_files
"""
from __future__ import annotations

import streamlit as st

from utils.gmail_utils import GmailError, a_gmail_files, buscar_adjuntos


def _secret(clave: str, defecto: str = "") -> str:
    try:
        return st.secrets.get(clave, defecto)
    except Exception:  # noqa: BLE001
        return defecto


def render_gmail_import(prefix: str) -> list:
    """
    Dibuja el panel de importación desde Gmail y devuelve la lista de GmailFile
    seleccionados para procesar (vacía si no hay ninguno).
    """
    k_email = f"{prefix}_gmail_email"
    k_pass = f"{prefix}_gmail_pass"
    k_res = f"{prefix}_gmail_results"

    st.markdown(
        "<small style='color:#6AB040'>Descarga facturas adjuntas (PDF/JSON) "
        "directamente desde tu correo.</small>",
        unsafe_allow_html=True,
    )

    with st.expander("ℹ️ ¿Cómo conectar?", expanded=False):
        st.markdown(
            "1. Activa la **verificación en 2 pasos** en tu cuenta Google.\n"
            "2. Genera una **Contraseña de aplicación** en "
            "[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).\n"
            "3. Pega esa contraseña de 16 caracteres aquí (no tu contraseña normal).\n\n"
            "_Tu contraseña solo se usa para esta conexión y no se guarda en disco._"
        )

    correo = st.text_input(
        "Correo de Gmail",
        value=st.session_state.get(k_email, _secret("GMAIL_EMAIL")),
        key=k_email,
        placeholder="tucorreo@gmail.com",
    )
    clave = st.text_input(
        "Contraseña de aplicación",
        value=st.session_state.get(k_pass, _secret("GMAIL_APP_PASSWORD")),
        key=k_pass,
        type="password",
        placeholder="xxxx xxxx xxxx xxxx",
    )

    remitente = st.text_input(
        "Remitente(s) (opcional)",
        key=f"{prefix}_gmail_remitente",
        placeholder="facturacion@proveedor.com",
        help="Uno o varios correos separados por espacio o coma.",
    )
    texto = st.text_input(
        "Texto a buscar (opcional)",
        key=f"{prefix}_gmail_texto",
        placeholder="factura, DTE, CCF...",
        help="Busca en asunto y cuerpo, igual que la barra de Gmail.",
    )

    col_d, col_m = st.columns(2)
    with col_d:
        dias = st.number_input(
            "Últimos días", min_value=1, max_value=365, value=30, step=1,
            key=f"{prefix}_gmail_dias",
        )
    with col_m:
        max_correos = st.number_input(
            "Máx. correos", min_value=1, max_value=200, value=50, step=10,
            key=f"{prefix}_gmail_max",
        )

    if st.button("🔎 Buscar en Gmail", use_container_width=True, key=f"{prefix}_gmail_btn"):
        if not correo or not clave:
            st.warning("Ingresa el correo y la contraseña de aplicación.")
        else:
            with st.spinner("Conectando con Gmail y buscando facturas..."):
                try:
                    resultados = buscar_adjuntos(
                        correo,
                        clave,
                        remitente=remitente,
                        texto=texto,
                        dias=int(dias),
                        max_correos=int(max_correos),
                    )
                    st.session_state[k_res] = resultados
                    if not resultados:
                        st.info("No se encontraron adjuntos con esos filtros.")
                    else:
                        st.success(f"Se encontraron {len(resultados)} adjunto(s).")
                except GmailError as e:
                    st.session_state[k_res] = []
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.session_state[k_res] = []
                    st.error(f"Error inesperado al buscar en Gmail: {e}")

    resultados = st.session_state.get(k_res, [])
    if not resultados:
        return []

    opciones = list(range(len(resultados)))

    def _label(i: int) -> str:
        a = resultados[i]
        kb = a["size"] / 1024
        rem = (a.get("remitente") or "").split("<")[0].strip()[:32]
        return f"📄 {a['filename']} · {rem} · {a.get('fecha', '')} · {kb:.0f} KB"

    seleccion = st.multiselect(
        "Adjuntos a procesar",
        options=opciones,
        default=opciones,
        format_func=_label,
        key=f"{prefix}_gmail_sel",
    )

    elegidos = [resultados[i] for i in seleccion]
    if elegidos:
        st.caption(f"✅ {len(elegidos)} archivo(s) listos para procesar con el botón de arriba.")
    return a_gmail_files(elegidos)
