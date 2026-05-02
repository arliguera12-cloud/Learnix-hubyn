# pages/3_Extractor_DTE_Retenciones.py
"""
EXTRACTOR DTE RETENCIONES v2.0 (DTE-07)
Soporta: PDF (Nativo + OCR) y JSON (Ministerio Hacienda)
Especializado en retenciones de IVA (1%)
"""

import streamlit as st
import pandas as pd
import pdfplumber
import pytesseract
import json
import re
import time
import gc
import platform
from io import BytesIO
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# IMPORTS DE CORE
# ═══════════════════════════════════════════════════════════════
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.extractores import (
    necesita_gemini,
    validar_retenciones_con_gemini,
    render_panel_filtros,
    parsear_json_dte,
    limpiar_monto,
    extraer_y_formatear_fecha,
    formatear_uuid,
)

# ═══════════════════════════════════════════════════════════════
# VERIFICACIÓN DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════

if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Retenciones.")
    st.stop()

if not isinstance(st.session_state.cliente_activo, dict):
    st.warning("⚠️ El cliente activo no es válido. Regresa al Dashboard y vuelve a seleccionarlo.")
    st.stop()

cliente = st.session_state.cliente_activo

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN TÉCNICA
# ═══════════════════════════════════════════════════════════════

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

st.set_page_config(
    page_title="Extractor DTE Retenciones",
    layout="wide",
    page_icon="✂️"
)

# ═══════════════════════════════════════════════════════════════
# ESTILOS GLOBALES
# ═══════════════════════════════════════════════════════════════

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #000000 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #161616 !important;
        border-right: 1px solid #333333 !important;
    }
    h1, h2, h3, h4, h5, h6, p, label, span, div {
        color: #F7F5EE !important;
    }
    [data-testid="stDataFrame"] span {
        color: inherit !important;
    }
    div.stButton > button[kind="primary"],
    div.stDownloadButton > button[kind="primary"] {
        background-color: #8B6D47 !important;
        border: 1px solid #B39A7A !important;
        border-radius: 6px;
        transition: 0.3s;
    }
    div.stButton > button[kind="primary"] *,
    div.stDownloadButton > button[kind="primary"] * {
        color: #FFFFFF !important;
        font-weight: bold !important;
    }
    div.stButton > button[kind="primary"]:hover,
    div.stDownloadButton > button[kind="primary"]:hover {
        background-color: #9A7C56 !important;
    }
    div.stButton > button[kind="secondary"] {
        background-color: #2A2A2A !important;
        border: 1px solid #555555 !important;
        border-radius: 6px;
    }
    div.stButton > button[kind="secondary"] * {
        color: #FFFFFF !important;
        font-weight: bold !important;
    }
    .alerta-activo {
        padding: 10px;
        border-radius: 6px;
        border-left: 4px solid #8B6D47;
        background-color: #111111;
        color: white;
        margin-bottom: 15px;
        font-size: 14px;
    }
    .scroll-list {
        max-height: 150px;
        overflow-y: auto;
        padding: 10px;
        background-color: #111111;
        border-radius: 5px;
        border: 1px solid #333;
        font-family: monospace;
        font-size: 13px;
        color: #66ff66;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #8B6D47 !important;
        border-bottom-color: #8B6D47 !important;
    }
    .stTabs [data-baseweb="tab-list"] button {
        color: #777777 !important;
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# FUNCIONES DE EXTRACCIÓN PDF
# ═══════════════════════════════════════════════════════════════

def extraer_dte_retenciones(archivo, cliente_activo: dict) -> dict:
    """
    Motor de extracción de DTE de Retenciones (DTE-07).
    Especializado en retenciones de IVA (1%).
    
    Retorna:
        dict con datos extraídos o error
    """
    motor = "Nativo"

    try:
        # Leer bytes
        if hasattr(archivo, 'seek'):
            archivo.seek(0)
        file_bytes = archivo.read()
        archivo.seek(0)

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            pagina = pdf.pages[0]
            texto_prueba = pagina.extract_text() or ""

            # Decisión: NATIVO vs OCR
            if len(texto_prueba.strip()) < 100:
                motor = "OCR"
                img = pagina.to_image(resolution=300)
                texto_raw = pytesseract.image_to_string(img.original, lang='spa')
            else:
                texto_raw = texto_prueba

            t_clean = re.sub(r'\s+', ' ', texto_raw)
            t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        # ── VALIDACIÓN BÁSICA DE TIPO DTE ──
        if "DTE-07" not in t_clean and "Comprobante de Retenci" not in t_clean:
            return {"error": "Este no parece ser un DTE-07 (Comprobante de Retención)."}

        # ── EXTRACCIÓN DE IDENTIFICADORES ──
        tipo = "07"

        ctrl_m = re.search(r"(DTE-07-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)", t_clean)
        ctrl = ctrl_m.group(1) if ctrl_m else ""

        gen = formatear_uuid(
            re.search(
                r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
                t_no_spaces
            ).group(1) if re.search(
                r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
                t_no_spaces
            ) else ""
        )

        sello_m = re.search(r"Sello de Recepci[oó]n\s*[:]?\s*([A-Z0-9]{20,})", t_clean, re.I)
        sello = sello_m.group(1) if sello_m else ""

        # Fecha
        fecha = extraer_y_formatear_fecha(t_clean)

        # ── EXTRACCIÓN DE DATOS DE RETENCIÓN ──
        patron_nit = r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b|\b\d{8}-?\d{1}\b"

        # NIT de la contraparte (quien retiene)
        nit_m = re.search(
            r"N\s*[I1l|]?\s*T\s*[:]?\s*([\d\-\s]{9,20})",
            t_clean, re.I
        )
        if not nit_m:
            nit_m = re.search(f"({patron_nit})", t_clean)

        nit_contraparte = re.sub(r'[^0-9]', '', nit_m.group(1)) if nit_m else ""

        # Nombre
        bloque_nombre = t_clean
        if "EMISOR" in t_clean.upper():
            bloque_nombre = t_clean.split("EMISOR", 1)[-1]

        nom_m = re.search(
            r"(.*?)(?=\bN\s*[I|1l]\s*T\b|DTE-07|Actividad\b|" + patron_nit + r")",
            bloque_nombre, re.I
        )

        if nom_m:
            nombre_sucio = nom_m.group(1)
            nombre = re.sub(
                r"(Nombre|Raz[oó]n\s+social)\s*[:]?\s*",
                "", nombre_sucio, flags=re.I
            ).strip()
            nombre = re.sub(r"\|", "I", nombre).strip()
            nombre = re.sub(r"^[^A-Za-z0-9]+", "", nombre).strip()
        else:
            nombre = ""

        # ── BÚSQUEDA DE MONTOS ──
        # Monto sujeto a retención
        monto_sujeto_m = re.search(
            r"(?:Monto Sujeto|Monto de Operaci[oó]n|Total Operaci[oó]n)\s*[:]?\s*\$?\s*([\d,]+\.\d{2})",
            t_clean, re.I
        )
        monto_sujeto = limpiar_monto(monto_sujeto_m.group(1)) if monto_sujeto_m else 0.0

        # Monto retenido (1% del sujeto)
        monto_retenido_m = re.search(
            r"(?:Monto Retenido|Retenci[oó]n|Monto a Retener)\s*[:]?\s*\$?\s*([\d,]+\.\d{2})",
            t_clean, re.I
        )
        monto_retenido = limpiar_monto(monto_retenido_m.group(1)) if monto_retenido_m else 0.0

        # Si no encontró monto retenido, calcularlo (1%)
        ret_calc = False
        if monto_retenido == 0.0 and monto_sujeto > 0:
            monto_retenido = round(monto_sujeto * 0.01, 2)
            ret_calc = True

        return {
            "fecha": fecha,
            "nit_contraparte": nit_contraparte,
            "nom_contraparte": nombre,
            "tipo": tipo,
            "ctrl": ctrl,
            "gen": gen,
            "sello": sello,
            "monto_sujeto": monto_sujeto,
            "monto_retenido": monto_retenido,
            "ret_calc": ret_calc,
            "motor": motor,
            "es_nuevo": False,
            "estado": "OK",
            "confianza_nit": "media",
            "confianza_rs": "media",
            "fuente": "PDF",
            "archivo": archivo.name if hasattr(archivo, 'name') else "documento.pdf"
        }

    except Exception as e:
        return {"error": f"Error de lectura: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
# ESTADO DE SESIÓN
# ═══════════════════════════════════════════════════════════════

if 'uploader_key_ret' not in st.session_state:
    st.session_state.uploader_key_ret = str(time.time())
if 'json_key_ret' not in st.session_state:
    st.session_state.json_key_ret = str(time.time()) + "_json_ret"
if 'db_retenciones' not in st.session_state:
    st.session_state.db_retenciones = pd.DataFrame()
if 'archivos_procesados_ret' not in st.session_state:
    st.session_state.archivos_procesados_ret = set()
if 'reporte_retenciones' not in st.session_state:
    st.session_state.reporte_retenciones = None

# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:Courier New,monospace; color:#8B6D47; "
    "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("✂️ Extractor DTE - Retenciones")

st.markdown(f"""
<div class="alerta-activo">
    <strong>AGENTE DE RETENCIÓN (Cliente Activo):</strong><br>
    {cliente.get('nombre', 'N/A')} (NIT: {cliente.get('nit', 'N/A')})
</div>
""", unsafe_allow_html=True)

st.info("📌 Especializado en DTE-07 (Comprobantes de Retención de IVA 1%)")

# ═══════════════════════════════════════════════════════════════
# SIDEBAR: CARGA PDF Y JSON
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("📂 Carga de Datos")
    st.caption(f"Cliente: {cliente.get('nombre', 'N/A')}")
    st.divider()

    # TABS: PDF | JSON
    tab_pdf, tab_json = st.tabs(["📄 PDF", "📋 JSON"])

    # ───────────────────────────────────────────────────────────
    # TAB PDF
    # ───────────────────────────────────────────────────────────
    with tab_pdf:
        st.subheader("Carga de Documentos PDF")
        
        archivos_pdf = st.file_uploader(
            "Arrastra tus PDFs (DTE-07)",
            type="pdf",
            accept_multiple_files=True,
            key=st.session_state.uploader_key_ret,
            help="Comprobantes de retención de IVA"
        )

        usar_gemini = False
        if st.secrets.get("GEMINI_API_KEY"):
            usar_gemini = st.checkbox(
                "🤖 Activar Validación Gemini",
                value=False,
                help="Validar montos con Gemini si hay dudas"
            )

        if archivos_pdf and st.button(
            "▶️ Procesar PDFs",
            type="primary",
            use_container_width=True,
            key="btn_procesar_pdf_ret"
        ):
            extracted = []
            duplicados_gen = []
            vacios_deteccion = []
            archivos_rechazados = []
            gemini_validados = []

            nuevos = [
                f for f in archivos_pdf
                if f.name not in st.session_state.archivos_procesados_ret
            ]

            if nuevos:
                bar = st.progress(0)
                txt_progreso = st.empty()
                t_inicio = time.time()
                total = len(nuevos)

                for idx, f in enumerate(nuevos):
                    if idx > 0 and idx % 30 == 0:
                        gc.collect()

                    # Progress
                    if idx > 0:
                        elapsed = time.time() - t_inicio
                        eta = int((elapsed / idx) * (total - idx))
                        m, s = divmod(eta, 60)
                        txt_progreso.markdown(
                            f"▶️ **{idx+1}** de **{total}** | ⏳ {m:02d}:{s:02d}",
                            unsafe_allow_html=True
                        )
                    else:
                        txt_progreso.markdown("▶️ **1** de **{total}** | Analizando...")

                    # Procesar PDF
                    res = extraer_dte_retenciones(f, cliente)
                    st.session_state.archivos_procesados_ret.add(f.name)

                    if "error" in res:
                        archivos_rechazados.append(f"{f.name} — {res['error']}")
                    else:
                        # ── GEMINI: validación si confianza baja ──
                        if usar_gemini and st.secrets.get("GEMINI_API_KEY"):
                            try:
                                f.seek(0)
                                with pdfplumber.open(f) as pdf:
                                    texto_pdf = "".join(
                                        (p.extract_text() or "") for p in pdf.pages[:2]
                                    )
                                
                                gemini_res = validar_retenciones_con_gemini(
                                    texto_pdf,
                                    res
                                )
                                
                                if gemini_res.get("_exito"):
                                    for campo in ["nit_contraparte", "nom_contraparte", "monto_sujeto", "monto_retenido"]:
                                        if gemini_res.get(campo) and not res.get(campo):
                                            res[campo] = gemini_res[campo]
                                    res["confianza_gemini"] = gemini_res.get("confianza_gemini")
                                    res["gemini_obs"] = gemini_res.get("observaciones")
                                    gemini_validados.append(f.name)
                            except Exception:
                                pass

                        # Validar campos
                        incompleto = (
                            "" in [
                                res.get("fecha", ""), res.get("nit_contraparte", ""),
                                res.get("nom_contraparte", ""), res.get("ctrl", "")
                            ]
                            or float(res.get("monto_sujeto", 0)) == 0.0
                        )

                        if incompleto:
                            vacios_deteccion.append(f.name)

                        # Deduplicación
                        codigo_gen = res.get("gen", "")
                        dup_mem = (
                            not st.session_state.db_retenciones.empty
                            and codigo_gen != ""
                            and (st.session_state.db_retenciones["gen"] == codigo_gen).any()
                        )
                        dup_lote = (
                            codigo_gen != ""
                            and any(d.get("gen") == codigo_gen for d in extracted)
                        )

                        if dup_mem or dup_lote:
                            duplicados_gen.append(f.name)
                        else:
                            res["archivo"] = f.name
                            extracted.append(res)

                    bar.progress((idx + 1) / total)

                txt_progreso.success(f"✅ {total} documentos procesados")

                st.session_state.reporte_retenciones = {
                    "rechazados": archivos_rechazados,
                    "vacios": vacios_deteccion,
                    "duplicados_gen": duplicados_gen,
                    "gemini": gemini_validados,
                }

                if extracted:
                    new_df = pd.DataFrame(extracted)
                    st.session_state.db_retenciones = (
                        new_df if st.session_state.db_retenciones.empty
                        else pd.concat([st.session_state.db_retenciones, new_df], ignore_index=True)
                    )

                gc.collect()
                time.sleep(0.3)
                st.rerun()

    # ───────────────────────────────────────────────────────────
    # TAB JSON
    # ───────────────────────────────────────────────────────────
    with tab_json:
        st.subheader("Carga desde JSON (Ministerio)")
        st.caption("Soporta archivos JSON del formato oficial de Hacienda")

        archivos_json = st.file_uploader(
            "Arrastra JSONs (DTE-07)",
            type=["json"],
            accept_multiple_files=True,
            key=st.session_state.json_key_ret
        )

        if archivos_json and st.button(
            "▶️ Procesar JSONs",
            type="primary",
            use_container_width=True,
            key="btn_procesar_json_ret"
        ):
            extracted_json = []
            duplicados_json = []
            errores_json = []
            rechazados_tipo = []

            for f in archivos_json:
                if f.name in st.session_state.archivos_procesados_ret:
                    continue

                try:
                    datos = json.load(f)
                    res = parsear_json_dte(datos, "retenciones")

                    if "error" in res:
                        errores_json.append(f"{f.name} — {res['error']}")
                        continue

                    # Validar tipo DTE
                    tipo = res.get("tipo", "07")
                    if tipo != "07":
                        rechazados_tipo.append(f"{f.name} (DTE-{tipo}, esperaba DTE-07)")
                        continue

                    # Deduplicación
                    codigo_gen = res.get("gen", "")
                    dup = (
                        not st.session_state.db_retenciones.empty
                        and codigo_gen != ""
                        and (st.session_state.db_retenciones["gen"] == codigo_gen).any()
                    )

                    if dup:
                        duplicados_json.append(f.name)
                    else:
                        res["archivo"] = f.name
                        extracted_json.append(res)

                    st.session_state.archivos_procesados_ret.add(f.name)

                except json.JSONDecodeError:
                    errores_json.append(f"{f.name} — JSON inválido")
                except Exception as e:
                    errores_json.append(f"{f.name} — {str(e)}")

            if extracted_json:
                new_df = pd.DataFrame(extracted_json)
                st.session_state.db_retenciones = (
                    new_df if st.session_state.db_retenciones.empty
                    else pd.concat([st.session_state.db_retenciones, new_df], ignore_index=True)
                )

            # Resumen
            resumen = []
            if extracted_json:
                resumen.append(f"✅ {len(extracted_json)} importados")
            if duplicados_json:
                resumen.append(f"🔄 {len(duplicados_json)} duplicados")
            if rechazados_tipo:
                resumen.append(f"⚠️ {len(rechazados_tipo)} tipo incorrecto")
            if errores_json:
                resumen.append(f"❌ {len(errores_json)} errores")

            if resumen:
                st.success(" | ".join(resumen))

            if errores_json:
                with st.expander("Ver errores JSON"):
                    for e in errores_json:
                        st.error(e)

            gc.collect()
            st.rerun()

    # ── Botón Limpiar ──
    st.divider()
    if st.button("🧹 Limpiar Memoria", type="secondary", use_container_width=True):
        for var in ["db_retenciones", "archivos_procesados_ret", "reporte_retenciones"]:
            st.session_state.pop(var, None)
        st.session_state.uploader_key_ret = str(time.time())
        st.session_state.json_key_ret = str(time.time()) + "_json_ret"
        gc.collect()
        st.rerun()

    if not st.session_state.db_retenciones.empty:
        st.divider()
        total_pdf = len(
            st.session_state.db_retenciones[
                st.session_state.db_retenciones.get("fuente", pd.Series()) == "PDF"
            ]
        ) if "fuente" in st.session_state.db_retenciones.columns else len(st.session_state.db_retenciones)

        total_json = len(
            st.session_state.db_retenciones[
                st.session_state.db_retenciones.get("fuente", pd.Series()) == "JSON"
            ]
        ) if "fuente" in st.session_state.db_retenciones.columns else 0

        st.caption(f"📊 Total: {len(st.session_state.db_retenciones)} | PDF: {total_pdf} | JSON: {total_json}")

# ═══════════════════════════════════════════════════════════════
# REPORTE DE EXTRACCIÓN
# ═══════════════════════════════════════════════════════════════

if st.session_state.reporte_retenciones:
    rep = st.session_state.reporte_retenciones
    st.markdown("### 📋 Reporte de Extracción")

    col1, col2, col3 = st.columns(3)

    with col1:
        n = len(rep.get("rechazados", []))
        if n:
            st.error(f"🚫 **{n} Rechazados**")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join([f"• {a}<br>" for a in rep["rechazados"]])
                    + '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ **0 Rechazados**")

    with col2:
        n = len(rep.get("vacios", []))
        if n:
            st.error(f"🚨 **{n} Incompletos**")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join([f"• {a}<br>" for a in rep["vacios"]])
                    + '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ **0 Incompletos**")

    with col3:
        n = len(rep.get("duplicados_gen", []))
        if n:
            st.error(f"🔄 **{n} Duplicados**")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join([f"• {a}<br>" for a in rep["duplicados_gen"]])
                    + '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ **0 Duplicados**")

    if rep.get("gemini"):
        st.info(f"🤖 **{len(rep['gemini'])} Validados con Gemini**")

    st.divider()

# ═══════════════════════════════════════════════════════════════
# TABLA DE RESULTADOS CON FILTROS
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_retenciones.empty:
    st.markdown("### 📊 Datos Extraídos")

    # Aplicar filtros
    df_filtrado = render_panel_filtros(st.session_state.db_retenciones, "retenciones_ret")

    if not df_filtrado.empty:
        # Mostrar tabla
        st.dataframe(
            df_filtrado[
                ["fecha", "nit_contraparte", "nom_contraparte", "monto_sujeto", "monto_retenido", "motor", "fuente"]
            ],
            use_container_width=True,
            hide_index=True
        )

        # Estadísticas
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("📊 Registros", len(df_filtrado))
        with col_stat2:
            total_sujeto = df_filtrado["monto_sujeto"].apply(lambda x: float(x) if x else 0.0).sum()
            st.metric("💵 Monto Sujeto", f"${total_sujeto:,.2f}")
        with col_stat3:
            total_ret = df_filtrado["monto_retenido"].apply(lambda x: float(x) if x else 0.0).sum()
            st.metric("✂️ Total Retenido", f"${total_ret:,.2f}")
    else:
        st.info("No hay registros que coincidan con los filtros aplicados.")

else:
    st.info("📤 Carga archivos PDF o JSON en el panel lateral para comenzar.")

st.divider()

# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    st.caption(f"👤 Usuario: {st.session_state.get('usuario_actual', 'N/A')}")

with col_f2:
    st.caption("🏢 Learnix Hub v2.0")

with col_f3:
    st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
