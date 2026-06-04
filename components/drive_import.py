"""
drive_import.py — Componente reutilizable para importar facturas desde una
carpeta de Google Drive compartida con enlace público.

Se renderiza dentro de una pestaña en los extractores y devuelve los archivos
seleccionados como `DriveFile`, que se inyectan en el mismo pipeline que el
`file_uploader`.

Uso:
    from components.drive_import import render_drive_import
    drive_files = render_drive_import("comp")
    archivos = (archivos or []) + drive_files
"""
from __future__ import annotations

import streamlit as st

from utils.drive_utils import (
    DriveError,
    descargar_como_drivefiles,
    listar_archivos,
)


def _secret(clave: str, defecto: str = "") -> str:
    try:
        return st.secrets.get(clave, defecto)
    except Exception:  # noqa: BLE001
        return defecto


def render_drive_import(prefix: str) -> list:
    """
    Dibuja el panel de importación desde Google Drive y devuelve la lista de
    DriveFile seleccionados para procesar (vacía si no hay ninguno).
    """
    k_key = f"{prefix}_drive_key"
    k_url = f"{prefix}_drive_url"
    k_res = f"{prefix}_drive_results"

    st.markdown(
        "<small style='color:#6AB040'>Importa los PDF/JSON de una carpeta de "
        "Drive compartida (incluye subcarpetas).</small>",
        unsafe_allow_html=True,
    )

    with st.expander("ℹ️ ¿Cómo conectar?", expanded=False):
        st.markdown(
            "1. La carpeta debe estar compartida como **'Cualquiera con el "
            "enlace → Lector'**.\n"
            "2. Crea una **API Key** en "
            "[console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) "
            "con la **API de Google Drive** habilitada.\n"
            "3. Pega la API Key y el enlace de la carpeta aquí.\n\n"
            "_La API Key solo se usa para leer la carpeta; no se guarda en disco._"
        )

    api_key = st.text_input(
        "API Key de Google",
        value=st.session_state.get(k_key, _secret("GDRIVE_API_KEY")),
        key=k_key,
        type="password",
        placeholder="AIza...",
    )
    url = st.text_input(
        "Enlace o ID de la carpeta",
        value=st.session_state.get(k_url, ""),
        key=k_url,
        placeholder="https://drive.google.com/drive/folders/...",
    )

    col_r, col_m = st.columns(2)
    with col_r:
        recursivo = st.checkbox(
            "Incluir subcarpetas", value=True, key=f"{prefix}_drive_rec"
        )
    with col_m:
        max_archivos = st.number_input(
            "Máx. archivos", min_value=1, max_value=500, value=200, step=50,
            key=f"{prefix}_drive_max",
        )

    if st.button("🔎 Listar carpeta", use_container_width=True, key=f"{prefix}_drive_btn"):
        if not api_key or not url:
            st.warning("Ingresa la API Key y el enlace de la carpeta.")
        else:
            with st.spinner("Recorriendo la carpeta de Drive..."):
                try:
                    resultados = listar_archivos(
                        api_key,
                        url,
                        recursivo=recursivo,
                        max_archivos=int(max_archivos),
                    )
                    st.session_state[k_res] = resultados
                    if not resultados:
                        st.info("No se encontraron PDF/JSON en esa carpeta.")
                    else:
                        st.success(f"Se encontraron {len(resultados)} archivo(s).")
                except DriveError as e:
                    st.session_state[k_res] = []
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.session_state[k_res] = []
                    st.error(f"Error inesperado al leer Drive: {e}")

    resultados = st.session_state.get(k_res, [])
    if not resultados:
        return []

    opciones = list(range(len(resultados)))

    def _label(i: int) -> str:
        a = resultados[i]
        try:
            kb = int(a.get("size", 0)) / 1024
            tam = f"{kb:.0f} KB"
        except (TypeError, ValueError):
            tam = ""
        return f"📄 {a['name']} · {a.get('carpeta', '')}{(' · ' + tam) if tam else ''}"

    seleccion = st.multiselect(
        "Archivos a procesar",
        options=opciones,
        default=opciones,
        format_func=_label,
        key=f"{prefix}_drive_sel",
    )

    if not seleccion:
        return []

    if st.button(
        f"⬇️ Descargar {len(seleccion)} archivo(s)",
        use_container_width=True,
        key=f"{prefix}_drive_dl",
    ):
        elegidos = [resultados[i] for i in seleccion]
        bar = st.progress(0.0, text=f"Descargando 0/{len(elegidos)}...")

        def _prog(hechos: int, total: int):
            bar.progress(hechos / total, text=f"Descargando {hechos}/{total}...")

        try:
            archivos_ok, errores = descargar_como_drivefiles(
                api_key, elegidos, progreso=_prog
            )
            bar.empty()
            st.session_state[f"{prefix}_drive_files"] = archivos_ok
            if archivos_ok:
                st.success(
                    f"✅ {len(archivos_ok)} archivo(s) listos. "
                    "Usa el botón 'Procesar' de arriba."
                )
            if errores:
                st.warning(
                    f"⚠️ {len(errores)} archivo(s) no se pudieron descargar."
                )
                with st.expander("Ver archivos con error"):
                    for nombre, msg in errores[:50]:
                        st.caption(f"• {nombre} — {msg}")
            if not archivos_ok and not errores:
                st.info("No se descargó ningún archivo.")
        except DriveError as e:
            bar.empty()
            st.error(str(e))
        except Exception as e:  # noqa: BLE001
            bar.empty()
            st.error(f"Error al descargar de Drive: {e}")

    return st.session_state.get(f"{prefix}_drive_files", [])
