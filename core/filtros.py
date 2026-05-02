# core/filtros.py
"""
Panel de filtros reutilizable para DataFrames
"""

import streamlit as st
import pandas as pd
from datetime import datetime


def render_panel_filtros(df: pd.DataFrame, key_prefix: str = "filtro") -> pd.DataFrame:
    """
    Renderiza un panel de filtros interactivos para DataFrame.
    
    Args:
        df: DataFrame con datos extraídos
        key_prefix: Prefijo único para keys
    
    Returns:
        DataFrame filtrado
    """
    if df.empty:
        st.warning("📁 No hay datos para filtrar")
        return df

    with st.expander("🔍 Filtros de Búsqueda", expanded=False):
        col1, col2, col3 = st.columns(3)
        df_filtrado = df.copy()

        # ── FILTRO: TIPO DTE ──
        if "tipo" in df.columns:
            with col1:
                tipos_disponibles = ["Todos"] + sorted(
                    df["tipo"].dropna().unique().tolist()
                )
                tipo_sel = st.selectbox(
                    "Tipo DTE",
                    tipos_disponibles,
                    key=f"{key_prefix}_tipo"
                )
                if tipo_sel != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["tipo"] == tipo_sel]

        # ── FILTRO: FECHAS ──
        if "fecha" in df.columns:
            with col2:
                fechas_validas = df_filtrado["fecha"].dropna()
                fechas_validas = fechas_validas[fechas_validas != ""]

                if not fechas_validas.empty:
                    try:
                        fecha_min_str = fechas_validas.min()
                        fecha_max_str = fechas_validas.max()

                        fecha_min = datetime.strptime(fecha_min_str, "%Y-%m-%d").date()
                        fecha_max = datetime.strptime(fecha_max_str, "%Y-%m-%d").date()

                        fecha_desde = st.date_input(
                            "Desde",
                            value=fecha_min,
                            key=f"{key_prefix}_fecha_desde"
                        )
                        fecha_hasta = st.date_input(
                            "Hasta",
                            value=fecha_max,
                            key=f"{key_prefix}_fecha_hasta"
                        )

                        def en_rango(f):
                            try:
                                fd = datetime.strptime(str(f), "%Y-%m-%d").date()
                                return fecha_desde <= fd <= fecha_hasta
                            except Exception:
                                return True

                        df_filtrado = df_filtrado[df_filtrado["fecha"].apply(en_rango)]
                    except Exception:
                        pass

        # ── FILTRO: MOTOR ──
        if "motor" in df.columns:
            with col3:
                motores_disponibles = ["Todos"] + sorted(
                    df_filtrado["motor"].dropna().unique().tolist()
                )
                motor_sel = st.selectbox(
                    "Motor",
                    motores_disponibles,
                    key=f"{key_prefix}_motor"
                )
                if motor_sel != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["motor"] == motor_sel]

        # ── FILTRO: FUENTE ──
        if "fuente" in df.columns:
            col4, col5 = st.columns(2)
            with col4:
                fuentes_disponibles = ["Todos"] + sorted(
                    df_filtrado["fuente"].dropna().unique().tolist()
                )
                fuente_sel = st.selectbox(
                    "Fuente",
                    fuentes_disponibles,
                    key=f"{key_prefix}_fuente"
                )
                if fuente_sel != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["fuente"] == fuente_sel]

        # ── BÚSQUEDA POR TEXTO ──
        with st.container():
            busqueda = st.text_input(
                "🔎 Buscar por nombre o NIT",
                placeholder="Ej: 0614-123456...",
                key=f"{key_prefix}_busqueda"
            )
            if busqueda:
                campos_texto = [
                    "nom", "nit", "nom_prov", "nit_prov",
                    "nombre", "nom_contraparte", "nit_contraparte"
                ]
                campos_validos = [c for c in campos_texto if c in df_filtrado.columns]

                if campos_validos:
                    mascara = df_filtrado[campos_validos].apply(
                        lambda col: col.astype(str).str.contains(
                            busqueda, case=False, na=False
                        )
                    ).any(axis=1)
                    df_filtrado = df_filtrado[mascara]

    return df_filtrado
