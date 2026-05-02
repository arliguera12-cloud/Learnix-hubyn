# core/extractores/filtros.py
"""
Sistema de filtros reutilizable para todos los extractores.
Soporta: fuente (PDF/JSON), rango de fechas, montos, tipo DTE.
"""

import streamlit as st
import pandas as pd
import json
import re
from .utils import normalizar_nit


def render_panel_filtros(df: pd.DataFrame, key_prefix: str = "filtro") -> pd.DataFrame:
    """
    Renderiza un panel de filtros interactivo.
    
    Args:
        df: DataFrame con los datos extraídos
        key_prefix: prefijo único para evitar colisiones de keys de Streamlit
    
    Returns:
        DataFrame filtrado según los criterios del usuario
    """
    if df.empty:
        st.info("No hay datos para filtrar aún.")
        return df

    with st.expander("🔍 Filtros de Extracción", expanded=False):
        col1, col2, col3 = st.columns(3)

        # ── Filtro por Fuente (PDF / JSON) ────────────────────────
        with col1:
            fuentes_disp = ["Todos"]
            if "fuente" in df.columns:
                fuentes_unicas = df["fuente"].dropna().unique().tolist()
                fuentes_disp += sorted(fuentes_unicas)
            else:
                fuentes_disp += ["PDF", "JSON"]

            filtro_fuente = st.selectbox(
                "📄 Fuente de datos",
                fuentes_disp,
                key=f"{key_prefix}_fuente",
                help="Filtrar por origen del documento"
            )

        # ── Filtro por Tipo de Documento ──────────────────────────
        with col2:
            if "tipo" in df.columns:
                tipos_unicas = sorted(df["tipo"].dropna().unique().tolist())
                tipos_disp = ["Todos"] + [f"DTE-{t}" for t in tipos_unicas]
                filtro_tipo_display = st.selectbox(
                    "📋 Tipo de Documento",
                    tipos_disp,
                    key=f"{key_prefix}_tipo",
                    help="Filtrar por tipo de DTE"
                )
                filtro_tipo = "Todos" if filtro_tipo_display == "Todos" else filtro_tipo_display.replace("DTE-", "")
            else:
                filtro_tipo = "Todos"
                st.selectbox(
                    "📋 Tipo de Documento",
                    ["Todos"],
                    key=f"{key_prefix}_tipo",
                    disabled=True
                )

        # ── Filtro por Motor de Extracción ─────────────────────────
        with col3:
            if "motor" in df.columns:
                motores_unicas = sorted(df["motor"].dropna().unique().tolist())
                motores_disp = ["Todos"] + motores_unicas
                filtro_motor = st.selectbox(
                    "⚙️ Motor de Extracción",
                    motores_disp,
                    key=f"{key_prefix}_motor",
                    help="Nativo, OCR, JSON-Parser, Gemini"
                )
            else:
                filtro_motor = "Todos"
                st.selectbox(
                    "⚙️ Motor de Extracción",
                    ["Todos"],
                    key=f"{key_prefix}_motor",
                    disabled=True
                )

        st.markdown("---")
        col4, col5, col6 = st.columns(3)

        # ── Filtro por Rango de Montos ────────────────────────────
        col_tot = None
        if "tot" in df.columns:
            col_tot = "tot"
        elif "G_Monto" in df.columns:
            col_tot = "G_Monto"
        elif "monto" in df.columns:
            col_tot = "monto"

        with col4:
            monto_min = st.number_input(
                "💵 Monto mínimo ($)",
                value=0.0,
                min_value=0.0,
                format="%.2f",
                key=f"{key_prefix}_monto_min"
            )

        with col5:
            if col_tot and not df[col_tot].empty:
                try:
                    max_val = float(df[col_tot].apply(
                        lambda x: float(x) if x else 0.0
                    ).max())
                except Exception:
                    max_val = 999999.99
            else:
                max_val = 999999.99

            monto_max = st.number_input(
                "💵 Monto máximo ($)",
                value=max_val,
                min_value=0.0,
                format="%.2f",
                key=f"{key_prefix}_monto_max"
            )

        # ── Filtro por Estado/Confianza ─────────────────────────────
        with col6:
            if "confianza_gemini" in df.columns:
                filtro_gemini = st.selectbox(
                    "🤖 Validado Gemini",
                    ["Todos", "✅ Validado", "⏳ Pendiente"],
                    key=f"{key_prefix}_gemini",
                    help="Documentos procesados con Gemini"
                )
            else:
                filtro_gemini = "Todos"

    # ═══════════════════════════════════════════════════════════════
    # APLICAR FILTROS
    # ═══════════════════════════════════════════════════════════════

    df_filtrado = df.copy()

    # Filtro por fuente
    if filtro_fuente != "Todos" and "fuente" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["fuente"] == filtro_fuente]

    # Filtro por tipo
    if filtro_tipo != "Todos" and "tipo" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["tipo"] == filtro_tipo]

    # Filtro por motor
    if filtro_motor != "Todos" and "motor" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["motor"] == filtro_motor]

    # Filtro por monto
    if col_tot:
        try:
            df_filtrado = df_filtrado[
                df_filtrado[col_tot].apply(
                    lambda x: monto_min <= float(x if x else 0) <= monto_max
                )
            ]
        except Exception:
            pass

    # Filtro por Gemini
    if filtro_gemini != "Todos" and "confianza_gemini" in df_filtrado.columns:
        if filtro_gemini == "✅ Validado":
            df_filtrado = df_filtrado[df_filtrado["confianza_gemini"].notna()]
        elif filtro_gemini == "⏳ Pendiente":
            df_filtrado = df_filtrado[df_filtrado["confianza_gemini"].isna()]

    return df_filtrado


def parsear_json_dte(datos_json: dict, tipo_extractor: str) -> dict:
    """
    Parsea un JSON de DTE (formato oficial Ministerio de Hacienda)
    y lo convierte al formato interno del sistema.
    
    Args:
        datos_json: dict con estructura DTE JSON del Ministerio
        tipo_extractor: "ventas", "compras", "retenciones", "sujetos_excluidos"
    
    Returns:
        dict con campos normalizados
    """
    resultado = {"fuente": "JSON", "motor": "JSON-Parser"}

    try:
        # ── Acceder a estructura DTE ──────────────────────────────
        dte_json = datos_json.get("dteJson", {})
        encabezado = dte_json.get("encabezado", {})
        cuerpo = dte_json.get("cuerpo", [{}])
        item_cuerpo = cuerpo[0] if cuerpo else {}

        identificacion = encabezado.get("identificacion", {})
        emisor = encabezado.get("emisor", {})
        receptor = encabezado.get("receptor", {})
        resumen = encabezado.get("resumen", {})

        # ── Campos comunes ────────────────────────────────────────
        resultado["tipo"] = str(identificacion.get("tipoDte", "01")).zfill(2)
        resultado["ctrl"] = identificacion.get("numeroControl", "")
        resultado["gen"]  = identificacion.get("codigoGeneracion", "")
        resultado["sello"] = datos_json.get("selloRecibido", "")

        # Fecha (formato YYYY-MM-DD → DD/MM/YYYY)
        fecha_raw = identificacion.get("fecEmi", "")
        if fecha_raw:
            try:
                partes = str(fecha_raw).split("-")
                if len(partes) == 3:
                    resultado["fecha"] = f"{partes[2]}/{partes[1]}/{partes[0]}"
                else:
                    resultado["fecha"] = fecha_raw
            except Exception:
                resultado["fecha"] = ""
        else:
            resultado["fecha"] = ""

        # ── Procesamiento por tipo de extractor ────────────────────
        if tipo_extractor == "ventas":
            # Receptor es el comprador (cliente)
            nit_receptor = receptor.get("nit", "") or receptor.get("numDocumento", "")
            resultado["nit"]  = normalizar_nit(nit_receptor)
            resultado["nom"]  = receptor.get("nombre", "").upper()
            resultado["nos"]  = float(resumen.get("totalNoSuj", 0) or 0)
            resultado["exe"]  = float(resumen.get("totalExenta", 0) or 0)
            resultado["gra"]  = float(resumen.get("totalGravada", 0) or 0)
            resultado["iva"]  = float(resumen.get("totalIva", 0) or 0)
            resultado["tot"]  = float(resumen.get("totalPagar", 0) or 0)
            resultado["t_ing"] = "3"
            resultado["exp_serv"] = float(resumen.get("totalExportacion", 0) or 0)
            resultado["iva_calculado"] = False

        elif tipo_extractor == "compras":
            # Emisor es el proveedor
            nit_prov = emisor.get("nit", "") or emisor.get("numDocumento", "")
            nit_limpio = normalizar_nit(nit_prov)
            
            resultado["nit_prov"] = nit_limpio
            resultado["nom_prov"] = emisor.get("nombre", "").upper()
            resultado["dui_prov"] = nit_limpio if len(nit_limpio) == 9 else ""
            resultado["exe"]  = float(resumen.get("totalExenta", 0) or 0)
            resultado["gra"]  = float(resumen.get("totalGravada", 0) or 0)
            resultado["iva"]  = float(resumen.get("totalIva", 0) or 0)
            resultado["ret"]  = float(resumen.get("reteRenta", 0) or 0)
            resultado["tot"]  = float(resumen.get("totalPagar", 0) or 0)
            resultado["perc"] = 0.0
            resultado["iva_calc"] = False
            resultado["es_nuevo"] = True
            resultado["nit_nuevo"] = nit_limpio
            resultado["confianza_nit"] = "alta"
            resultado["confianza_rs"]  = "alta"
            resultado["estado"] = "OK"

        elif tipo_extractor == "retenciones":
            # DTE-07: Comprobantes de retención
            nit_contra = emisor.get("nit", "") or emisor.get("numDocumento", "")
            resultado["nit_contraparte"] = normalizar_nit(nit_contra)
            resultado["nom_contraparte"] = emisor.get("nombre", "CONTRAPARTE JSON").upper()
            
            monto_sujeto = float(
                item_cuerpo.get("montoSujetoGrav", 0)
                or resumen.get("totalSujetoRetencion", 0)
                or resumen.get("totalPagar", 0)
                or 0
            )
            monto_retenido = float(resumen.get("ivaRete1", 0) or 0)

            resultado["monto_sujeto"]   = monto_sujeto
            resultado["monto_retenido"] = monto_retenido if monto_retenido > 0 else round(monto_sujeto * 0.01, 2)
            resultado["es_nuevo"]  = False
            resultado["ret_calc"]  = monto_retenido == 0 and monto_sujeto > 0
            resultado["estado"]    = "OK"

        elif tipo_extractor == "sujetos_excluidos":
            # DTE-14: Sujetos excluidos
            nit_doc = emisor.get("nit", "") or emisor.get("numDocumento", "")
            nit_limpio = normalizar_nit(nit_doc)
            dui_limpio = nit_limpio if len(nit_limpio) == 9 else ""
            
            resultado["nombre"]    = emisor.get("nombre", "").upper()
            resultado["documento"] = nit_limpio
            resultado["nit"]  = nit_limpio if len(nit_limpio) == 14 else ""
            resultado["dui"]  = dui_limpio
            resultado["monto"] = float(resumen.get("totalPagar", 0) or 0)
            resultado["retencion"] = float(resumen.get("reteRenta", 0) or 0)
            
            if resultado["retencion"] == 0 and resultado["monto"] > 0:
                resultado["retencion"] = round(resultado["monto"] * 0.10, 2)
                resultado["retencion_calculada"] = True
            else:
                resultado["retencion_calculada"] = False
                
            resultado["codigo"] = resultado["gen"]
            resultado["sello_doc"] = resultado["sello"]
            resultado["valido"] = True
            resultado["tipo_doc_compras"] = (
                "1" if resultado["nit"] else ("2" if dui_limpio else "3")
            )

        return resultado

    except Exception as e:
        return {
            "error": f"Error al parsear JSON: {str(e)}",
            "fuente": "JSON",
            "_exito": False
        }
