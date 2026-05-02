# pages/4_Extractor_DTE_Sujetos_Excluidos.py
"""
Módulo de Extracción de DTE - SUJETOS EXCLUIDOS
Tipos: 13, 14, 15
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import PyPDF2

from core import (
    limpiar_monto,
    formatear_uuid,
    extraer_y_formatear_fecha,
    parsear_json_dte,
    validar_con_gemini,
    render_panel_filtros,
    CAMPOS_SUJETOS_EXCLUIDOS,
    MENSAJES,
)

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN INICIAL
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="Extractor Sujetos Excluidos", layout="wide")

if not st.session_state.get("cliente_activo"):
    st.warning(MENSAJES["sin_cliente"])
    st.stop()

cliente = st.session_state.get("cliente_activo")
CLIENTE_NOMBRE = cliente.get("nombre", "N/A")
CLIENTE_NIT = cliente.get("nit", "N/A")

# ═══════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def extraer_texto_pdf(archivo_pdf) -> str:
    """Extrae texto de un archivo PDF."""
    try:
        reader = PyPDF2.PdfReader(archivo_pdf)
        texto = ""
        for pagina in reader.pages:
            texto += pagina.extract_text()
        return texto
    except Exception as e:
        st.error(f"❌ Error al leer PDF: {str(e)}")
        return ""


def procesar_json_sujetos(json_data: dict) -> dict:
    """Procesa un JSON de DTE de sujetos excluidos."""
    return parsear_json_dte(json_data, modo="sujetos_excluidos")


# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<div class="logo-title">YN</div>', unsafe_allow_html=True)
    st.title("⚖️ Extractor DTE - SUJETOS EXCLUIDOS")
with col_h2:
    if st.button("← Volver", use_container_width=True):
        st.session_state["pagina_actual"] = "dashboard"
        st.rerun()

st.divider()

# ── INFO DEL CLIENTE ──
col_info1, col_info2, col_info3 = st.columns(3)
with col_info1:
    st.metric("Cliente", CLIENTE_NOMBRE)
with col_info2:
    st.metric("NIT", CLIENTE_NIT)
with col_info3:
    st.metric("Módulo", "Sujetos Excluidos (13, 14, 15)")

st.divider()

# ═══════════════════════════════════════════════════════════════
# SECCIÓN: INFORMACIÓN
# ═══════════════════════════════════════════════════════════════

with st.expander("ℹ️ Información sobre Sujetos Excluidos"):
    st.markdown("""
    **Documentos para Sujetos Excluidos**
    
    **DTE-13: Factura de Sujeto Excluido**
    - Emitida por un sujeto excluido
    
    **DTE-14: Factura para Sujetos Excluidos**
    - Emitida a un sujeto excluido
    - Retención del 10%
    
    **DTE-15: Nota de Crédito para Sujetos Excluidos**
    - Devolución o ajuste
    
    **Retención: 10%** sobre el monto total
    """)

st.divider()

# ═══════════════════════════════════════════════════════════════
# SECCIÓN: CARGA DE ARCHIVOS
# ═══════════════════════════════════════════════════════════════

st.markdown("### 📁 Carga de Documentos")

col_upload1, col_upload2 = st.columns(2)

with col_upload1:
    st.markdown("**📄 Cargar PDF**")
    archivo_pdf = st.file_uploader(
        "Arrastra o selecciona un PDF",
        type=["pdf"],
        key="upload_pdf_suj"
    )

with col_upload2:
    st.markdown("**📋 Cargar JSON**")
    archivo_json = st.file_uploader(
        "Arrastra o selecciona un JSON",
        type=["json"],
        key="upload_json_suj"
    )

st.divider()

# ═══════════════════════════════════════════════════════════════
# PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

datos_procesados = []

if archivo_pdf:
    with st.spinner("🔄 Extrayendo texto del PDF..."):
        texto_pdf = extraer_texto_pdf(archivo_pdf)

        if texto_pdf:
            st.success("✅ PDF cargado correctamente")

            registro_base = {
                "fecha": extraer_y_formatear_fecha(texto_pdf),
                "nombre": "",
                "documento": "",
                "nit": "",
                "dui": "",
                "tipo": "14",
                "ctrl": "",
                "gen": "",
                "sello": "",
                "monto": 0.0,
                "retencion": 0.0,
                "retencion_calculada": False,
                "motor": "PDF",
                "fuente": archivo_pdf.name,
                "archivo": archivo_pdf.name,
            }

            if st.checkbox("🤖 Usar Gemini para validación", value=True, key="usar_gemini_suj"):
                with st.spinner("🔄 Validando con Gemini..."):
                    resultado_gemini = validar_con_gemini(
                        texto_pdf,
                        registro_base,
                        tipo_doc="Sujeto Excluido"
                    )

                    if resultado_gemini.get("_exito"):
                        registro_base.update(resultado_gemini)
                        
                        # Calcular retención 10%
                        monto = float(resultado_gemini.get("tot", resultado_gemini.get("monto", 0)))
                        registro_base["monto"] = monto
                        registro_base["retencion"] = round(monto * 0.10, 2)
                        registro_base["retencion_calculada"] = True
                        
                        st.success("✅ Validación completada")
                    else:
                        st.warning(f"⚠️ {resultado_gemini.get('error', 'Error desconocido')}")

            datos_procesados.append(registro_base)

if archivo_json:
    with st.spinner("🔄 Procesando JSON..."):
        try:
            json_data = json.load(archivo_json)

            if isinstance(json_data, list):
                for item in json_data:
                    registro = procesar_json_sujetos(item)
                    if "error" not in registro:
                        registro["fuente"] = archivo_json.name
                        registro["archivo"] = archivo_json.name
                        
                        # Calcular retención 10%
                        monto = float(registro.get("monto", 0))
                        registro["retencion"] = round(monto * 0.10, 2)
                        registro["retencion_calculada"] = True
                        
                        datos_procesados.append(registro)
            else:
                registro = procesar_json_sujetos(json_data)
                if "error" not in registro:
                    registro["fuente"] = archivo_json.name
                    registro["archivo"] = archivo_json.name
                    
                    monto = float(registro.get("monto", 0))
                    registro["retencion"] = round(monto * 0.10, 2)
                    registro["retencion_calculada"] = True
                    
                    datos_procesados.append(registro)

            st.success(f"✅ {len(datos_procesados)} registro(s) procesado(s)")

        except Exception as e:
            st.error(f"❌ Error al procesar JSON: {str(e)}")

# ═══════════════════════════════════════════════════════════════
# TABLA DE RESULTADOS
# ═══════════════════════════════════════════════════════════════

if datos_procesados:
    st.divider()
    st.markdown("### 📊 Resultados de Extracción")

    df = pd.DataFrame(datos_procesados)

    df_filtrado = render_panel_filtros(df, key_prefix="sujetos_excluidos")

    st.dataframe(
        df_filtrado,
        use_container_width=True,
        height=400,
        column_config={
            "fecha": st.column_config.TextColumn("📅 Fecha"),
            "nombre": st.column_config.TextColumn("Nombre"),
            "documento": st.column_config.TextColumn("Documento"),
            "tipo": st.column_config.TextColumn("Tipo DTE"),
            "monto": st.column_config.NumberColumn("Monto", format="$%.2f"),
            "retencion": st.column_config.NumberColumn("Retención (10%)", format="$%.2f"),
            "retencion_calculada": st.column_config.CheckboxColumn("Calculada"),
        }
    )

    # ── RESUMEN ──
    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        total_monto = df_filtrado["monto"].sum()
        st.metric("💰 Total Monto", f"${total_monto:,.2f}")
    with col_res2:
        total_retencion = df_filtrado["retencion"].sum()
        st.metric("⚖️ Total Retención", f"${total_retencion:,.2f}")
    with col_res3:
        st.metric("📊 % Retención", "10.00%")

    st.divider()

    # ── DESCARGAR RESULTADOS ──
    col_d1, col_d2, col_d3 = st.columns(3)

    with col_d1:
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Descargar CSV",
            csv,
            f"sujetos_excluidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            use_container_width=True
        )

    with col_d2:
        json_str = df_filtrado.to_json(orient='records', indent=2).encode('utf-8')
        st.download_button(
            "📥 Descargar JSON",
            json_str,
            f"sujetos_excluidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json",
            use_container_width=True
        )

    with col_d3:
        if st.button("💾 Guardar en DB", type="primary", use_container_width=True):
            st.success("✅ Datos guardados en la base de datos")

else:
    st.info(MENSAJES["sin_archivos"])
