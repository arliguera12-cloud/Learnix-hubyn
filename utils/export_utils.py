"""
Pilar 3 — Exportación dual universal (Excel + CSV).
Úsala en cualquier página con: render_dual_download(df, "nombre_archivo")
"""
from __future__ import annotations
from io import BytesIO

import pandas as pd
import streamlit as st


def _to_excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")
        ws = writer.sheets["Datos"]
        # Ajuste automático de ancho de columnas
        for col_cells in ws.columns:
            max_len = max(
                (len(str(c.value)) if c.value is not None else 0) for c in col_cells
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 60)
    return buf.getvalue()


def _to_csv(df: pd.DataFrame) -> bytes:
    # utf-8-sig agrega BOM → Excel abre correctamente tildes y ñ
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def render_dual_download(
    df: pd.DataFrame,
    nombre_base: str,
    label: str = "Descargar",
    cols_formato: dict | None = None,
) -> None:
    """
    Renderiza dos botones de descarga (Excel y CSV) para cualquier DataFrame.

    Args:
        df:           DataFrame a exportar.
        nombre_base:  Nombre de archivo sin extensión (ej. "Ventas_Enero").
        label:        Prefijo del botón (ej. "Exportar").
        cols_formato: Diccionario opcional de formato para columnas numéricas
                      (ej. {"Total ($)": "{:,.2f}"}); solo afecta la vista, no la descarga.
    """
    if df.empty:
        st.info("No hay datos para exportar.")
        return

    col_xl, col_csv = st.columns(2)

    with col_xl:
        st.download_button(
            label=f"📊 {label} Excel",
            data=_to_excel(df),
            file_name=f"{nombre_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col_csv:
        st.download_button(
            label=f"📄 {label} CSV",
            data=_to_csv(df),
            file_name=f"{nombre_base}.csv",
            mime="text/csv",
            use_container_width=True,
        )
