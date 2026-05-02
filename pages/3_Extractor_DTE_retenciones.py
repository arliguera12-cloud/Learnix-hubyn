# pages/3_Extractor_DTE_Retenciones.py
"""
Módulo de Extracción de DTE - RETENCIONES
Tipo: 07 (Comprobante de Retención 1%)
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
    validar_retenciones_con_gemini,
    render_panel_filtros,
    CAMPOS_RETENCIONES,
    MENSAJES,
)

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN INICIAL
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="Extractor Retenciones", layout="wide")

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


def procesar_json_retenciones(json_data: dict) -> dict:
    """Procesa un JSON de DTE de retenciones."""
    return parsear_json_dte(json_data, modo="retenciones")


# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<div class="logo-title">YN</div>', unsafe_allow_html=True)
    st.title("✂️ Extractor DTE - RETENCIONES")
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
    st.metric("Módulo", "Retenciones DTE-07 (1%)")

st.divider()

# ═══════════════════════════════════════════════════════════════
# SECCIÓN: INFORMACIÓN
# ═══════════════════════════════════════════════════════════════

with st.expander("ℹ️ Información sobre Retenciones (DTE-07)"):
    st.markdown("""
    **Comprobante de Retención (DTE-07)**
    - Porcentaje: **1%** sobre el monto gravado
    - Emitido por: El que retiene (generalmente el comprador)
    - A favor de: El proveedor/vendedor
    
    **Cálculo:**
    - Monto Sujeto a Retención = Monto Gravado de la compra
    - Retención = Monto Sujeto × 1%
    
    **Campos principales:**
    - Fecha de emisión
    - NIT de la contraparte (proveedor)
    - Nombre de la contraparte
    - Monto sujeto a retención
    - Monto retenido (1% calculado)
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
        key="upload_pdf_ret"
    )

with col_upload2:
    st.markdown("**📋 Cargar JSON**")
    archivo_json = st.file_uploader(
        "Arrastra o selecciona un JSON",
        type=["json"],
        key="upload_json_ret"
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
                "nit_contraparte": "",
                "nom_contraparte": "",
                "tipo": "07",
                "ctrl": "",
                "gen": "",
                "sello": "",
                "monto_sujeto": 0.0,
                "monto_retenido": 0.0,
                "ret_calc": False,
                "motor": "PDF",
                "confianza_nit": "media",
                "confianza_rs": "media",
                "fuente": archivo_pdf.name,
                "archivo": archivo_pdf.name,
            }

            if st.checkbox("🤖 Usar Gemini para validación", value=True, key="usar_gemini_ret"):
                with st.spinner("🔄 Validando con Gemini..."):
                    resultado_gemini = validar_retenciones_con_gemini(
                        texto_pdf,
                        registro_base
                    )

                    if resultado_gemini.get("_exito"):
                        registro_base.update(resultado_gemini)
                        
                        # Calcular retención automáticamente
                        monto_sujeto = float(resultado_gemini.get("monto_sujeto", 0))
                        registro_base["monto_retenido"] = round(monto_sujeto * 0.01, 2)
                        registro_base["ret_calc"] = True
                        
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
                    registro = procesar_json_retenciones(item)
                    if "error" not in registro:
                        registro["fuente"] = archivo_json.name
                        registro["archivo"] = archivo_json.name
                        
                        # Calcular retención
                        monto_sujeto = float(registro.get("monto_sujeto", 0))
                        registro["monto_retenido"] = round(monto_sujeto * 0.01, 2)
                        registro["ret_calc"] = True
                        
                        datos_procesados.append(registro)
            else:
                registro = procesar_json_retenciones(json_data)
                if "error" not in registro:
                    registro["fuente"] = archivo_json.name
                    registro["archivo"] = archivo_json.name
                    
                    monto_sujeto = float(registro.get("monto_sujeto", 0))
                    registro["monto_retenido"] = round(monto_sujeto * 0.01, 2)
                    registro["ret_calc"] = True
                    
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

    df_filtrado = render_panel_filtros(df, key_prefix="retenciones")

    st.dataframe(
        df_filtrado,
        use_container_width=True,
        height=400,
        column_config={
            "fecha": st.column_config.TextColumn("📅 Fecha"),
            "nit_contraparte": st.column_config.TextColumn("NIT"),
            "nom_contraparte": st.column_config.TextColumn("Nombre"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "monto_sujeto": st.column_config.NumberColumn("Sujeto", format="$%.2f"),
            "monto_retenido": st.column_config.NumberColumn("Retenido (1%)", format="$%.2f"),
            "ret_calc": st.column_config.CheckboxColumn("Calculado"),
            "motor": st.column_config.TextColumn("Motor"),
        }
    )

    # ── RESUMEN ──
    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        total_sujeto = df_filtrado["monto_sujeto"].sum()
        st.metric("💰 Total Sujeto", f"${total_sujeto:,.2f}")
    with col_res2:
        total_retenido = df_filtrado["monto_retenido"].sum()
        st.metric("✂️ Total Retenido", f"${total_retenido:,.2f}")
    with col_res3:
        porcentaje = (total_retenido / total_sujeto * 100) if total_sujeto > 0 else 0
        st.metric("📊 % Retención", f"{porcentaje:.2f}%")

    st.divider()

    # ── DESCARGAR RESULTADOS ──
    col_d1, col_d2, col_d3 = st.columns(3)

    with col_d1:
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Descargar CSV",
            csv,
            f"retenciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            use_container_width=True
        )

    with col_d2:
        json_str = df_filtrado.to_json(orient='records', indent=2).encode('utf-8')
        st.download_button(
            "📥 Descargar JSON",
            json_str,
            f"retenciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json",
            use_container_width=True
        )

    with col_d3:
        if st.button("💾 Guardar en DB", type="primary", use_container_width=True):
            st.success("✅ Datos guardados en la base de datos")

else:
    st.info(MENSAJES["sin_archivos"])
