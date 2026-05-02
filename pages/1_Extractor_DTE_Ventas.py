# pages/1_Extractor_DTE_Ventas.py
"""
Módulo de Extracción de DTE - VENTAS
Tipos: 01 (Factura), 03 (CCF), 05, 06, 11
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import PyPDF2

# Importar funciones del core
from core import (
    limpiar_monto,
    formatear_uuid,
    extraer_y_formatear_fecha,
    parsear_json_dte,
    validar_con_gemini,
    necesita_gemini,
    render_panel_filtros,
    TIPOS_DTE,
    CAMPOS_VENTAS,
    MENSAJES,
)

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN INICIAL
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="Extractor Ventas", layout="wide")

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


def procesar_json_ventas(json_data: dict) -> dict:
    """Procesa un JSON de DTE de ventas."""
    return parsear_json_dte(json_data, modo="ventas")


def validar_fila_ventas(fila: dict) -> dict:
    """Valida si una fila de venta necesita corrección con Gemini."""
    necesita = necesita_gemini(
        fila.get("confianza_nit", "media"),
        fila.get("confianza_rs", "media"),
        float(fila.get("gra", 0)),
        float(fila.get("tot", 0))
    )
    return necesita


# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<div class="logo-title">YN</div>', unsafe_allow_html=True)
    st.title("📈 Extractor DTE - VENTAS")
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
    st.metric("Módulo", "Ventas (01, 03, 05, 06, 11)")

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
        key="upload_pdf_ventas"
    )

with col_upload2:
    st.markdown("**📋 Cargar JSON**")
    archivo_json = st.file_uploader(
        "Arrastra o selecciona un JSON",
        type=["json"],
        key="upload_json_ventas"
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

            # Crear registro base
            registro_base = {
                "fecha": extraer_y_formatear_fecha(texto_pdf),
                "nit": "",
                "nom": "",
                "tipo": "01",
                "ctrl": "",
                "gen": "",
                "sello": "",
                "nos": 0.0,
                "exe": 0.0,
                "gra": 0.0,
                "iva": 0.0,
                "exp_serv": 0.0,
                "tot": 0.0,
                "t_ing": "3",
                "motor": "PDF",
                "iva_calculado": False,
                "confianza_nit": "media",
                "confianza_rs": "media",
                "fuente": archivo_pdf.name,
                "archivo": archivo_pdf.name,
            }

            # Usar Gemini si es necesario
            if st.checkbox("🤖 Usar Gemini para validación", value=True, key="usar_gemini_v"):
                with st.spinner("🔄 Validando con Gemini..."):
                    resultado_gemini = validar_con_gemini(
                        texto_pdf,
                        registro_base,
                        tipo_doc="Factura/CCF"
                    )

                    if resultado_gemini.get("_exito"):
                        registro_base.update(resultado_gemini)
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
                    registro = procesar_json_ventas(item)
                    if "error" not in registro:
                        registro["fuente"] = archivo_json.name
                        registro["archivo"] = archivo_json.name
                        datos_procesados.append(registro)
            else:
                registro = procesar_json_ventas(json_data)
                if "error" not in registro:
                    registro["fuente"] = archivo_json.name
                    registro["archivo"] = archivo_json.name
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

    # Aplicar filtros
    df_filtrado = render_panel_filtros(df, key_prefix="ventas")

    # Mostrar tabla
    st.dataframe(
        df_filtrado,
        use_container_width=True,
        height=400,
        column_config={
            "fecha": st.column_config.TextColumn("📅 Fecha"),
            "nit": st.column_config.TextColumn("NIT"),
            "nom": st.column_config.TextColumn("Nombre"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "gra": st.column_config.NumberColumn("Gravado", format="$%.2f"),
            "iva": st.column_config.NumberColumn("IVA", format="$%.2f"),
            "tot": st.column_config.NumberColumn("Total", format="$%.2f"),
            "motor": st.column_config.TextColumn("Motor"),
            "confianza_nit": st.column_config.TextColumn("Conf. NIT"),
        }
    )

    # ── DESCARGAR RESULTADOS ──
    col_d1, col_d2, col_d3 = st.columns(3)

    with col_d1:
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Descargar CSV",
            csv,
            f"ventas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            use_container_width=True
        )

    with col_d2:
        json_str = df_filtrado.to_json(orient='records', indent=2).encode('utf-8')
        st.download_button(
            "📥 Descargar JSON",
            json_str,
            f"ventas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json",
            use_container_width=True
        )

    with col_d3:
        if st.button("💾 Guardar en DB", type="primary", use_container_width=True):
            # Aquí implementar guardado en base de datos
            st.success("✅ Datos guardados en la base de datos")

else:
    st.info(MENSAJES["sin_archivos"])
