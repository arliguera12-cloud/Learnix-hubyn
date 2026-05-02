"""
Sistema de filtros reutilizable para todos los extractores del Hub.

Uso:
    from core.extractor.filtros import render_panel_filtros

    df_filtrado = render_panel_filtros(df, key_prefix="ventas")
"""

import streamlit as st
import pandas as pd


# ═══════════════════════════════════════════════════════════════
# RENDER PANEL FILTROS — COMPONENTE PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def render_panel_filtros(df: pd.DataFrame, key_prefix: str = "filtro") -> pd.DataFrame:
    """
    Renderiza un panel de filtros encima de la tabla y retorna
    el DataFrame filtrado segun la seleccion del usuario.

    Filtros disponibles:
    - Fuente de datos (PDF / JSON)
    - Tipo de Documento DTE
    - Motor de Extraccion
    - Rango de montos
    - Confianza (validado por Gemini o no)
    - Busqueda de texto libre

    Args:
        df:         DataFrame con datos extraidos
        key_prefix: prefijo unico por modulo (evita colisiones de keys)

    Returns:
        DataFrame filtrado
    """
    if df.empty:
        return df

    st.markdown("### Filtros de Extraccion")

    with st.expander("Abrir filtros", expanded=False):

        row1_c1, row1_c2, row1_c3, row1_c4 = st.columns(4)

        # ── Fuente (PDF / JSON) ─────────────────────────────────
        with row1_c1:
            if "fuente" in df.columns:
                fuentes_unicas = sorted(df["fuente"].dropna().unique().tolist())
            else:
                fuentes_unicas = ["PDF"]
            opciones_fuente = ["Todos"] + fuentes_unicas
            filtro_fuente = st.selectbox(
                "Fuente",
                opciones_fuente,
                key=f"{key_prefix}_fuente"
            )

        # ── Tipo DTE ────────────────────────────────────────────
        with row1_c2:
            col_tipo = _detectar_columna_tipo(df)
            if col_tipo:
                tipos_unicos = sorted(df[col_tipo].dropna().unique().tolist())
                opciones_tipo = ["Todos"] + tipos_unicos
                filtro_tipo = st.selectbox(
                    "Tipo DTE",
                    opciones_tipo,
                    key=f"{key_prefix}_tipo"
                )
            else:
                filtro_tipo = "Todos"

        # ── Motor ───────────────────────────────────────────────
        with row1_c3:
            if "motor" in df.columns:
                motores_unicos = sorted(df["motor"].dropna().unique().tolist())
                opciones_motor = ["Todos"] + motores_unicos
                filtro_motor = st.selectbox(
                    "Motor",
                    opciones_motor,
                    key=f"{key_prefix}_motor"
                )
            else:
                filtro_motor = "Todos"

        # ── Validado por Gemini ─────────────────────────────────
        with row1_c4:
            if "confianza_gemini" in df.columns:
                filtro_gemini = st.selectbox(
                    "Gemini",
                    ["Todos", "Validado", "Sin validar"],
                    key=f"{key_prefix}_gemini"
                )
            else:
                filtro_gemini = "Todos"

        st.divider()
        row2_c1, row2_c2, row2_c3 = st.columns([2, 1, 1])

        # ── Busqueda texto libre ────────────────────────────────
        with row2_c1:
            texto_busqueda = st.text_input(
                "Buscar (NIT, Nombre, UUID...)",
                placeholder="Escribe para filtrar...",
                key=f"{key_prefix}_busqueda"
            )

        # ── Rango de montos ─────────────────────────────────────
        col_monto = _detectar_columna_total(df)

        with row2_c2:
            monto_min = st.number_input(
                "Monto minimo ($)",
                value=0.0,
                min_value=0.0,
                format="%.2f",
                key=f"{key_prefix}_monto_min"
            )

        with row2_c3:
            if col_monto:
                max_val = float(
                    df[col_monto]
                    .apply(lambda x: float(x) if x else 0.0)
                    .max()
                )
            else:
                max_val = 999999.99
            monto_max = st.number_input(
                "Monto maximo ($)",
                value=max(max_val, monto_min),
                min_value=0.0,
                format="%.2f",
                key=f"{key_prefix}_monto_max"
            )

    # ── Aplicar Filtros ──────────────────────────────────────────
    df_f = df.copy()

    if filtro_fuente != "Todos" and "fuente" in df_f.columns:
        df_f = df_f[df_f["fuente"] == filtro_fuente]

    if filtro_tipo != "Todos" and col_tipo in df_f.columns:
        df_f = df_f[df_f[col_tipo] == filtro_tipo]

    if filtro_motor != "Todos" and "motor" in df_f.columns:
        df_f = df_f[df_f["motor"] == filtro_motor]

    if filtro_gemini == "Validado" and "confianza_gemini" in df_f.columns:
        df_f = df_f[df_f["confianza_gemini"].notna()]
    elif filtro_gemini == "Sin validar" and "confianza_gemini" in df_f.columns:
        df_f = df_f[df_f["confianza_gemini"].isna()]

    if col_monto in df_f.columns:
        df_f = df_f[
            df_f[col_monto].apply(
                lambda x: monto_min <= float(x if x else 0) <= monto_max
            )
        ]

    if texto_busqueda.strip():
        termino = texto_busqueda.strip().upper()
        cols_texto = _detectar_columnas_texto(df_f)
        if cols_texto:
            mascara = pd.Series([False] * len(df_f), index=df_f.index)
            for col in cols_texto:
                mascara = mascara | (
                    df_f[col]
                    .astype(str)
                    .str.upper()
                    .str.contains(termino, na=False)
                )
            df_f = df_f[mascara]

    # Indicador de resultados
    total_original = len(df)
    total_filtrado  = len(df_f)
    if total_filtrado < total_original:
        st.caption(
            f"Mostrando **{total_filtrado}** de **{total_original}** registros "
            f"({total_original - total_filtrado} filtrados)"
        )

    return df_f


# ═══════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════

def _detectar_columna_tipo(df: pd.DataFrame) -> str | None:
    """Detecta la columna de tipo de documento DTE."""
    for nombre in ["tipo", "C. Tipo Doc", "Tipo"]:
        if nombre in df.columns:
            return nombre
    return None


def _detectar_columna_total(df: pd.DataFrame) -> str | None:
    """Detecta la columna de total."""
    for nombre in ["tot", "G_Monto", "monto", "O. Total Compras",
                   "monto_sujeto", "F. Monto Sujeto"]:
        if nombre in df.columns:
            return nombre
    return None


def _detectar_columnas_texto(df: pd.DataFrame) -> list:
    """Detecta columnas de texto utiles para busqueda."""
    candidatas = [
        "nom", "nom_prov", "nom_contraparte", "nombre",
        "nit", "nit_prov", "nit_contraparte", "documento",
        "gen", "ctrl", "codigo", "archivo",
        "E. NIT/NRC Prov", "F. Nombre Prov", "D. Num Documento"
    ]
    return [c for c in candidatas if c in df.columns]
