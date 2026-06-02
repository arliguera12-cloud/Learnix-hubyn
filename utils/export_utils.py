"""
Pilar 3 — Exportación dual universal (Excel + CSV).
Úsala en cualquier página con: render_dual_download(df, "nombre_archivo")

Mejoras v2.0:
  - Segunda hoja "Metadata" en Excel con audit trail (fecha, modelo IA, cliente activo).
  - Parámetro audit_info para pasar datos de trazabilidad a la exportación.
"""
from __future__ import annotations
from io import BytesIO
import datetime

import pandas as pd
import streamlit as st


def _to_excel(df: pd.DataFrame, audit_info: dict | None = None) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # ── Hoja 1: Datos ─────────────────────────────────────────────────────
        df.to_excel(writer, index=False, sheet_name="Datos")
        ws_datos = writer.sheets["Datos"]
        for col_cells in ws_datos.columns:
            max_len = max(
                (len(str(c.value)) if c.value is not None else 0) for c in col_cells
            )
            ws_datos.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 60)

        # ── Hoja 2: Metadata / Audit Trail ───────────────────────────────────
        audit = audit_info or {}
        try:
            cliente = st.session_state.get("cliente_activo") or {}
            cliente_nombre = cliente.get("nombre", "—")
            cliente_nit    = cliente.get("nit", "—")
        except Exception:
            cliente_nombre = "—"
            cliente_nit    = "—"

        try:
            audit_log = st.session_state.get("gemini_audit_log", [])
            n_docs_ia = len(audit_log)
            confianza_prom = (
                round(sum(e.get("confianza_extraccion", 0) for e in audit_log) / n_docs_ia)
                if n_docs_ia else "N/A"
            )
            modelo_ia = audit_log[-1].get("modelo_utilizado", "—") if audit_log else "—"
        except Exception:
            n_docs_ia = 0
            confianza_prom = "N/A"
            modelo_ia = "—"

        meta_rows = [
            ("Campo", "Valor"),
            ("Fecha de exportación", datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
            ("Sistema", "Learnix DTE Hub v5.0"),
            ("", ""),
            ("Cliente activo", cliente_nombre),
            ("NIT cliente", cliente_nit),
            ("", ""),
            ("Modelo IA", audit.get("modelo", modelo_ia)),
            ("Documentos procesados con IA", audit.get("docs_ia", n_docs_ia)),
            ("Confianza promedio IA (%)", audit.get("confianza_prom", confianza_prom)),
            ("Total documentos exportados", len(df)),
            ("", ""),
            ("Nota", "Los valores con ⚠️ en columna _alerta o Estatus requieren revisión manual."),
        ]

        df_meta = pd.DataFrame(meta_rows[1:], columns=meta_rows[0])
        df_meta.to_excel(writer, index=False, sheet_name="Metadata")
        ws_meta = writer.sheets["Metadata"]
        ws_meta.column_dimensions["A"].width = 35
        ws_meta.column_dimensions["B"].width = 45

    return buf.getvalue()


def _to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def render_dual_download(
    df: pd.DataFrame,
    nombre_base: str,
    label: str = "Descargar",
    cols_formato: dict | None = None,
    audit_info: dict | None = None,
) -> None:
    """
    Renderiza dos botones de descarga (Excel y CSV) para cualquier DataFrame.

    Args:
        df:           DataFrame a exportar.
        nombre_base:  Nombre de archivo sin extensión (ej. "Ventas_Enero").
        label:        Prefijo del botón (ej. "Exportar").
        cols_formato: Diccionario opcional de formato para columnas numéricas.
        audit_info:   Dict con metadata extra para la hoja Metadata del Excel
                      (ej. {"modelo": "llama3-8b-8192", "docs_ia": 15}).
    """
    if df.empty:
        st.info("No hay datos para exportar.")
        return

    col_xl, col_csv = st.columns(2)

    with col_xl:
        st.download_button(
            label=f"📊 {label} Excel",
            data=_to_excel(df, audit_info=audit_info),
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
