"""
Pilar 2 — Aislamiento de datos por NIT.
Evita que documentos de un cliente se mezclen con otro.
"""
from __future__ import annotations
import re
import streamlit as st


def _limpiar_nit(raw: str) -> str:
    return re.sub(r"[^0-9]", "", str(raw or ""))


def nits_coinciden(nit_doc: str, nit_cliente: str) -> bool:
    return _limpiar_nit(nit_doc) == _limpiar_nit(nit_cliente)


def filtrar_por_nit(
    resultados: list[dict],
    nit_cliente_activo: str,
    campo_nit: str,
) -> tuple[list[dict], list[dict]]:
    """
    Separa documentos en aceptados / rechazados según si el NIT extraído
    coincide con el del cliente activo.

    Args:
        resultados:         Lista de dicts devueltos por el extractor.
        nit_cliente_activo: NIT del cliente seleccionado en st.session_state.
        campo_nit:          Clave del dict que contiene el NIT a comparar
                            ('nit_rec' para ventas, 'nit_emi' para compras).

    Returns:
        (aceptados, rechazados) — ambas listas de dicts.
        Los rechazados incluyen 'razon_rechazo'.
    """
    nit_ref = _limpiar_nit(nit_cliente_activo)
    aceptados:  list[dict] = []
    rechazados: list[dict] = []

    for doc in resultados:
        if doc.get("error") or doc.get("error_extraccion"):
            rechazados.append({**doc, "razon_rechazo": "Error de extracción"})
            continue

        nit_doc = _limpiar_nit(doc.get(campo_nit, ""))

        if not nit_doc:
            rechazados.append({
                **doc,
                "razon_rechazo": f"NIT no encontrado en campo '{campo_nit}'",
            })
        elif nit_doc == nit_ref:
            aceptados.append(doc)
        else:
            rechazados.append({
                **doc,
                "razon_rechazo": (
                    f"NIT extraído '{nit_doc}' ≠ NIT cliente '{nit_ref}' — "
                    f"Archivo: {doc.get('archivo', '—')}"
                ),
            })

    return aceptados, rechazados


def mostrar_rechazados(rechazados: list[dict]) -> None:
    """
    Renderiza en Streamlit la lista de documentos rechazados por NIT.
    Llama después de filtrar_por_nit() si rechazados no está vacío.
    """
    if not rechazados:
        return
    with st.expander(f"🚫 {len(rechazados)} documento(s) rechazados — NIT no coincide", expanded=True):
        for doc in rechazados:
            archivo = doc.get("archivo", doc.get("archivo_nombre", "—"))
            razon   = doc.get("razon_rechazo", "Motivo desconocido")
            st.markdown(
                f'<div style="padding:6px 10px; margin:4px 0; border-left:3px solid #F85149;'
                f' background:#1a0a0a; border-radius:4px; font-size:0.82rem;">'
                f'📄 <code>{archivo}</code><br>'
                f'<span style="color:#F85149;">{razon}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
