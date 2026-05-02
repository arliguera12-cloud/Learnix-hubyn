# pages/1_Extractor_DTE_Ventas.py
"""
Extractor de DTE Ventas (Tipos 01, 03, 05, 06, 11)
Soporta PDF y JSON del Ministerio de Hacienda.
Con validación Gemini y filtros avanzados.
"""

import streamlit as st
import pandas as pd
import json
import time
import gc
import re
from io import BytesIO
import pdfplumber
import pytesseract
import platform
import os
import sys

# ═══════════════════════════════════════════════════════════════
# IMPORTACIONES LOCALES
# ═══════════════════════════════════════════════════════════════

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.extractores import (
        necesita_gemini,
        validar_con_gemini,
        render_panel_filtros,
        parsear_json_dte,
        limpiar_monto,
        extraer_y_formatear_fecha,
        formatear_uuid
    )
    GEMINI_DISPONIBLE = True
except ImportError as e:
    GEMINI_DISPONIBLE = False
    st.warning(f"⚠️ Módulos avanzados no disponibles: {str(e)}")

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN TÉCNICA
# ═══════════════════════════════════════════════════════════════

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ═══════════════════════════════════════════════════════════════
# SEGURIDAD Y VALIDACIÓN
# ═══════════════════════════════════════════════════════════════

if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Ventas.")
    st.stop()

if not isinstance(st.session_state.cliente_activo, dict):
    st.warning("⚠️ El cliente activo no es válido. Regresa al Dashboard y vuelve a seleccionarlo.")
    st.stop()

cliente = st.session_state.cliente_activo

# ═══════════════════════════════════════════════════════════════
# ESTILOS PERSONALIZADOS
# ═══════════════════════════════════════════════════════════════

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { 
        background-color: #000000 !important; 
    }
    [data-testid="stSidebar"] { 
        background-color: #161616 !important; 
        border-right: 1px solid #333333; 
    }
    h1, h2, h3, h4, h5, h6, p, label, span { 
        color: #F7F5EE !important; 
    }
    [data-testid="stDataFrame"] span { 
        color: inherit !important; 
    }
    div.stButton > button[kind="primary"],
    div.stDownloadButton > button[kind="primary"] {
        background-color: #666D57 !important;
        border: 1px solid #828B70 !important;
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
        background-color: #798267 !important;
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
    div[data-testid="stAlert"] {
        min-height: 80px;
        display: flex;
        align-items: center;
    }
    .stAlert * { 
        color: inherit !important; 
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
        color: #666D57 !important;
        border-bottom-color: #666D57 !important;
    }
    .stTabs [data-baseweb="tab-list"] button { 
        color: #777777 !important; 
    }
    [data-testid="stExpander"] {
        background-color: #161616 !important;
        border: 1px solid #444444 !important;
        border-radius: 6px;
    }
    .alerta-activo {
        padding: 10px;
        border-radius: 6px;
        border-left: 4px solid #666D57;
        background-color: #111111;
        color: white;
        margin-bottom: 15px;
        font-size: 14px;
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# FUNCIONES ESPECIALIZADAS PARA VENTAS
# ═══════════════════════════════════════════════════════════════

def clasificar_tipo_ingreso(actividad: str) -> str:
    """Clasifica el tipo de ingreso según la actividad económica."""
    if not actividad:
        return "3"
    
    act = actividad.lower()
    
    patrones = {
        "1": ['médico', 'abogado', 'contad', 'ingeniero', 'profesiones', 'auditor'],
        "2": ['servicio', 'mantenimiento', 'transporte', 'flete', 'taller'],
        "4": ['industria', 'fabricación', 'manufactura'],
        "5": ['agro', 'ganadería', 'agricultura'],
        "7": ['export'],
    }
    
    for codigo, palabras in patrones.items():
        if any(palabra in act for palabra in palabras):
            return codigo
    
    return "3"


def extraer_dte_pdf_avanzado(f, cliente_activo) -> dict:
    """
    Motor avanzado de extracción de DTE desde PDF.
    Soporta DTE 01, 03, 05, 06, 11.
    """
    motor = "Nativo"
    
    try:
        f.seek(0)
        
        with pdfplumber.open(f) as pdf:
            pagina = pdf.pages[0]
            texto_prueba = pagina.extract_text() or ""
            
            # Decisión: Nativo vs OCR
            if len(texto_prueba.strip()) < 100:
                motor = "OCR"
                img_completa = pagina.to_image(resolution=300)
                texto_raw = pytesseract.image_to_string(img_completa.original, lang='spa')
            else:
                texto_raw = texto_prueba
            
            t_clean = re.sub(r'\s+', ' ', texto_raw)
            
            # ── VALIDACIÓN DE CLIENTE (Anti-intrusos) ──
            nit_emisor = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
            dui_emisor = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))
            
            patron_ids = r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b|\b\d{14}\b|\b\d{8}-?\d{1}\b|\b\d{9}\b"
            nits_encontrados = [re.sub(r'[^0-9]', '', n) for n in re.findall(patron_ids, t_clean)]
            
            es_valido = (
                nit_emisor == "00000000000000"
                or nit_emisor in nits_encontrados
                or (dui_emisor and dui_emisor in nits_encontrados)
            )
            
            if not es_valido:
                return {"error": f"Documento ajeno al emisor activo ({cliente_activo['nombre']})."}
            
            # ── EXTRACCIÓN DE CAMPOS ──
            
            # Tipo y Control
            tipo_m = re.search(r"DTE-(\d{2})", t_clean)
            tipo = tipo_m.group(1) if tipo_m else "01"
            
            ctrl_m = re.search(r"(DTE-\d{2}-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)", t_clean)
            ctrl = ctrl_m.group(1) if ctrl_m else ""
            
            # Generación
            gen = formatear_uuid(re.sub(r'[^A-F0-9-]', '', 
                re.search(r"(?:Generación|Código de Generación)\s*[:]?\s*([A-Z0-9-]{30,})", t_clean, re.I).group(1) 
                if re.search(r"(?:Generación|Código de Generación)\s*[:]?\s*([A-Z0-9-]{30,})", t_clean, re.I) else ""))
            
            # Sello
            sello_m = re.search(r"Sello de Recepción\s*[:]?\s*([A-Z0-9]{20,})", t_clean, re.I)
            sello = sello_m.group(1)[:40] if sello_m else ""
            
            # Fecha
            fecha = extraer_y_formatear_fecha(t_clean)
            
            # Receptor/Cliente
            texto_lineas = texto_raw.split('\n')
            idx_receptor = next((i for i, l in enumerate(texto_lineas) if 'RECEPTOR' in l.upper()), -1)
            
            if idx_receptor >= 0:
                bloque_receptor = '\n'.join(texto_lineas[idx_receptor:idx_receptor+10])
            else:
                bloque_receptor = texto_raw[-2000:]
            
            nit_m = re.search(r"N\s*[I1l|]?\s*T\s*[:]?\s*([\d\-]{9,20})", bloque_receptor, re.I)
            nit = re.sub(r'[^0-9]', '', nit_m.group(1)) if nit_m else ""
            
            nom_m = re.search(
                r"(?:Nombre|Razón Social)\s*[:]?\s*([A-Za-z0-9\s\.\-]{4,60}?)(?=\n|NIT|NRC|$)",
                bloque_receptor, re.I
            )
            nombre = nom_m.group(1).strip() if nom_m else ""
            
            # Actividad económica
            act_m = re.search(r"Actividad\s+econ[oó]mica\s*[:]?\s*(.*?)(?=\n|Dirección)", t_clean, re.I)
            t_ing = clasificar_tipo_ingreso(act_m.group(1) if act_m else "")
            
            # ── MONTOS ──
            nos = 0.0
            exe = 0.0
            gra = 0.0
            iva = 0.0
            tot = 0.0
            exp_serv = 0.0
            
            # Búsqueda de montos en líneas
            for patron, var_name in [
                (r"No Sujetas?\s*[:]?\s*([\d,]+\.?\d*)", "nos"),
                (r"(?:Ventas|Monto)\s+Exent[ao]s?\s*[:]?\s*([\d,]+\.?\d*)", "exe"),
                (r"(?:Ventas|Monto)\s+Gravad[ao]s?\s*[:]?\s*([\d,]+\.?\d*)", "gra"),
                (r"(?:IVA|Impuesto.*?13%)\s*[:]?\s*([\d,]+\.?\d*)", "iva"),
                (r"(?:Total|Monto Total)\s*[:]?\s*([\d,]+\.?\d*)", "tot"),
                (r"(?:Exportación|Export)\s+Servicios?\s*[:]?\s*([\d,]+\.?\d*)", "exp_serv"),
            ]:
                m = re.search(patron, t_clean, re.I)
                if m:
                    monto = limpiar_monto(m.group(1))
                    if var_name == "nos":
                        nos = monto
                    elif var_name == "exe":
                        exe = monto
                    elif var_name == "gra":
                        gra = monto
                    elif var_name == "iva":
                        iva = monto
                    elif var_name == "tot":
                        tot = monto
                    elif var_name == "exp_serv":
                        exp_serv = monto
            
            # ── VALIDACIONES Y CÁLCULOS ──
            iva_calculado = False
            if gra > 0 and iva == 0.0:
                iva = round(gra * 0.13, 2)
                iva_calculado = True
            
            if tot == 0.0 and (gra > 0 or exe > 0):
                tot = gra + iva + exe + nos
            
            return {
                "fecha": fecha,
                "nit": nit,
                "nom": nombre,
                "tipo": tipo,
                "ctrl": ctrl,
                "gen": gen,
                "sello": sello,
                "nos": nos,
                "exe": exe,
                "gra": gra,
                "iva": iva,
                "exp_serv": exp_serv,
                "tot": tot,
                "t_ing": t_ing,
                "motor": motor,
                "iva_calculado": iva_calculado,
                "fuente": "PDF",
                "confianza_nit": "alta",
                "confianza_rs": "alta",
            }

    except Exception as e:
        return {"error": f"Error al procesar PDF: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
# INICIALIZACIÓN DE ESTADO
# ═══════════════════════════════════════════════════════════════

if 'uploader_key_v' not in st.session_state:
    st.session_state.uploader_key_v = str(time.time())
if 'json_key_v' not in st.session_state:
    st.session_state.json_key_v = str(time.time()) + "_json"
if 'db_ventas' not in st.session_state:
    st.session_state.db_ventas = pd.DataFrame()
if 'archivos_procesados_v' not in st.session_state:
    st.session_state.archivos_procesados_v = set()
if 'reporte_ventas' not in st.session_state:
    st.session_state.reporte_ventas = None

# ═══════════════════════════════════════════════════════════════
# HEADER PRINCIPAL
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:Courier New,monospace; color:#666D57; "
    "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("📈 Extractor DTE - Ventas")

st.markdown(f"""
<div class="alerta-activo">
    <strong>EMISOR ACTUAL (Cliente Activo):</strong>
    {cliente.get('nombre', 'N/A')} (NIT: {cliente.get('nit', 'N/A')})
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# SIDEBAR: CARGA PDF + JSON
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("📤 Carga de Datos")
    st.caption(f"Cliente: {cliente.get('nombre', 'N/A')}")
    st.divider()

    tab_pdf, tab_json = st.tabs(["📄 PDF", "📋 JSON"])

    # ─────────────────────────────────────────────────────────
    # TAB: PDF
    # ─────────────────────────────────────────────────────────
    with tab_pdf:
        archivos_pdf = st.file_uploader(
            "Arrastra tus PDFs (DTE 01, 03, 05, 06, 11)",
            type="pdf",
            accept_multiple_files=True,
            key=st.session_state.uploader_key_v
        )

        usar_gemini = False
        if GEMINI_DISPONIBLE:
            usar_gemini = st.checkbox(
                "🤖 Activar Gemini (datos dudosos)",
                value=False,
                help="Valida datos con confianza baja"
            )

        if archivos_pdf and st.button(
            "🚀 Procesar PDFs",
            type="primary",
            use_container_width=True,
            key="btn_procesar_pdf_v"
        ):
            extracted = []
            duplicados_gen = []
            vacios_deteccion = []
            iva_calculado_files = []
            archivos_rechazados = []
            gemini_validados = []

            nuevos = [f for f in archivos_pdf
                      if f.name not in st.session_state.archivos_procesados_v]

            if nuevos:
                bar = st.progress(0)
                txt_progreso = st.empty()
                t_inicio = time.time()
                total = len(nuevos)

                for idx, f in enumerate(nuevos):
                    if idx > 0 and idx % 30 == 0:
                        gc.collect()

                    if idx > 0:
                        elapsed = time.time() - t_inicio
                        eta = int((elapsed / idx) * (total - idx))
                        m, s = divmod(eta, 60)
                        txt_progreso.markdown(
                            f"📄 Procesando: **{idx+1}** de **{total}** "
                            f"| ⏳ Restante: {m:02d}:{s:02d}"
                        )
                    else:
                        txt_progreso.markdown(f"📄 Procesando: **1** de **{total}** | ⏳ Calculando...")

                    # Leer bytes para Gemini
                    f.seek(0)
                    file_bytes = f.read()
                    f.seek(0)

                    res = extraer_dte_pdf_avanzado(f, cliente)
                    st.session_state.archivos_procesados_v.add(f.name)

                    if "error" in res:
                        archivos_rechazados.append(f"{f.name} — {res['error']}")
                    else:
                        # ── GEMINI: Si confianza baja ──
                        if usar_gemini and GEMINI_DISPONIBLE:
                            c_nit = res.get("confianza_nit", "media")
                            c_rs = res.get("confianza_rs", "media")
                            gra = float(res.get("gra", 0))
                            tot = float(res.get("tot", 0))

                            if necesita_gemini(c_nit, c_rs, gra, tot):
                                try:
                                    with pdfplumber.open(f) as pdf_temp:
                                        texto_pdf = "\n".join(
                                            p.extract_text() or "" for p in pdf_temp.pages[:3]
                                        )
                                    gemini_res = validar_con_gemini(
                                        texto_pdf, res, "Factura" if res.get("tipo") == "01" else "CCF"
                                    )
                                    if gemini_res.get("_exito"):
                                        # Aplicar correcciones solo si existen
                                        for campo in ["nit", "nom", "gra", "iva", "exe", "tot", "gen", "fecha"]:
                                            if gemini_res.get(campo) and not res.get(campo):
                                                res[campo] = gemini_res[campo]
                                        res["confianza_gemini"] = gemini_res.get("confianza_gemini")
                                        res["gemini_obs"] = gemini_res.get("observaciones")
                                        gemini_validados.append(f.name)
                                except Exception:
                                    pass

                        # Validar campos
                        tot_val = float(res.get("tot", 0) or 0)
                        if res.get("tipo") in ["01", "11"]:
                            incompleto = (
                                "" in [res.get("fecha", ""), res.get("ctrl", "")]
                                or tot_val == 0.0
                            )
                        else:
                            incompleto = (
                                "" in [res.get("fecha", ""), res.get("nit", ""),
                                       res.get("nom", ""), res.get("ctrl", "")]
                                or tot_val == 0.0
                            )

                        if incompleto:
                            vacios_deteccion.append(f.name)
                        if res.get("iva_calculado"):
                            iva_calculado_files.append(f.name)

                        # Deduplicación
                        codigo_gen = res.get("gen", "")
                        dup_mem = (
                            not st.session_state.db_ventas.empty
                            and codigo_gen != ""
                            and (st.session_state.db_ventas["gen"] == codigo_gen).any()
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

                txt_progreso.success(f"✅ {total} archivos procesados.")

                st.session_state.reporte_ventas = {
                    "rechazados": archivos_rechazados,
                    "vacios": vacios_deteccion,
                    "duplicados_gen": duplicados_gen,
                    "iva_calc": iva_calculado_files,
                    "gemini": gemini_validados,
                }

                if extracted:
                    new_df = pd.DataFrame(extracted)
                    if st.session_state.db_ventas.empty:
                        st.session_state.db_ventas = new_df
                    else:
                        st.session_state.db_ventas = pd.concat(
                            [st.session_state.db_ventas, new_df], ignore_index=True
                        )

                gc.collect()
                time.sleep(0.3)
                st.rerun()

    # ─────────────────────────────────────────────────────────
    # TAB: JSON
    # ─────────────────────────────────────────────────────────
    with tab_json:
        st.caption("📋 Ministerio de Hacienda (DTE formato oficial)")

        archivos_json = st.file_uploader(
            "Arrastra tus JSONs (DTE 01, 03, 05, 06, 11)",
            type=["json"],
            accept_multiple_files=True,
            key=st.session_state.json_key_v
        )

        if archivos_json and st.button(
            "🚀 Procesar JSONs",
            type="primary",
            use_container_width=True,
            key="btn_procesar_json_v"
        ):
            extracted_json = []
            duplicados_json = []
            errores_json = []
            rechazados_tipo = []

            for f in archivos_json:
                if f.name in st.session_state.archivos_procesados_v:
                    continue

                try:
                    datos = json.load(f)
                    res = parsear_json_dte(datos, "ventas")

                    if "error" in res or not res.get("_exito", True):
                        errores_json.append(f"{f.name} — {res.get('error', 'Error desconocido')}")
                        continue

                    # Validar tipo
                    tipo = res.get("tipo", "01")
                    if tipo not in ["01", "03", "05", "06", "11"]:
                        rechazados_tipo.append(f"{f.name} (DTE-{tipo} no soportado)")
                        continue

                    # Deduplicación
                    codigo_gen = res.get("gen", "")
                    dup = (
                        not st.session_state.db_ventas.empty
                        and codigo_gen != ""
                        and (st.session_state.db_ventas["gen"] == codigo_gen).any()
                    )

                    if dup:
                        duplicados_json.append(f.name)
                    else:
                        res["archivo"] = f.name
                        extracted_json.append(res)

                    st.session_state.archivos_procesados_v.add(f.name)

                except json.JSONDecodeError:
                    errores_json.append(f"{f.name} — JSON inválido")
                except Exception as e:
                    errores_json.append(f"{f.name} — {str(e)}")

            if extracted_json:
                new_df = pd.DataFrame(extracted_json)
                if st.session_state.db_ventas.empty:
                    st.session_state.db_ventas = new_df
                else:
                    st.session_state.db_ventas = pd.concat(
                        [st.session_state.db_ventas, new_df], ignore_index=True
                    )

            # Resumen
            resumen = []
            if extracted_json:
                resumen.append(f"✅ {len(extracted_json)} importados")
            if duplicados_json:
                resumen.append(f"⏭️ {len(duplicados_json)} duplicados")
            if errores_json:
                resumen.append(f"❌ {len(errores_json)} errores")
            if rechazados_tipo:
                resumen.append(f"⚠️ {len(rechazados_tipo)} tipo incorrecto")

            if resumen:
                st.success(" | ".join(resumen))
            if errores_json:
                with st.expander("Ver errores"):
                    for e in errores_json:
                        st.error(e)

            gc.collect()
            st.rerun()

    # Botón Limpiar
    st.divider()
    if st.button("🧹 Limpiar Memoria", type="secondary", use_container_width=True):
        st.session_state.db_ventas = pd.DataFrame()
        st.session_state.archivos_procesados_v = set()
        st.session_state.reporte_ventas = None
        st.session_state.uploader_key_v = str(time.time())
        st.session_state.json_key_v = str(time.time()) + "_json"
        gc.collect()
        st.rerun()

    if not st.session_state.db_ventas.empty:
        st.divider()
        st.caption(f"📊 {len(st.session_state.db_ventas)} registros en memoria")

# ═══════════════════════════════════════════════════════════════
# DASHBOARD PRINCIPAL
# ═══════════════════════════════════════════════════════════════

if st.session_state.reporte_ventas:
    rep = st.session_state.reporte_ventas
    st.markdown("### 📊 Reporte de Extracción")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if rep.get("rechazados"):
            st.error(f"🚫 **{len(rep['rechazados'])} Rechazados**")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">' +
                    "".join([f"• {a}<br>" for a in rep["rechazados"]]) +
                    '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ **0 Rechazados**")

    with c2:
        if rep.get("vacios"):
            st.error(f"🚨 **{len(rep['vacios'])} Incompletos**")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">' +
                    "".join([f"• {a}<br>" for a in rep["vacios"]]) +
                    '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ **0 Incompletos**")

    with c3:
        if rep.get("duplicados_gen"):
            st.error(f"🛑 **{len(rep['duplicados_gen'])} Omitidos**")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">' +
                    "".join([f"• {a}<br>" for a in rep["duplicados_gen"]]) +
                    '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ **0 Omitidos**")

    with c4:
        if rep.get("iva_calc"):
            st.info(f"🧮 **{len(rep['iva_calc'])} IVA Calc.**")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">' +
                    "".join([f"• {a}<br>" for a in rep["iva_calc"]]) +
                    '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ **0 IVA Calc.**")

    if rep.get("gemini"):
        st.divider()
        st.info(f"🤖 **{len(rep['gemini'])} documentos validados con Gemini**")

    st.divider()

# ═══════════════════════════════════════════════════════════════
# TABLAS DE RESULTADOS CON FILTROS
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_ventas.empty:
    st.markdown("### 📋 Datos Extraídos")

    # Aplicar filtros
    df_filtrado = render_panel_filtros(st.session_state.db_ventas, "ventas")

    if not df_filtrado.empty:
        tab1, tab2, tab3 = st.tabs([
            "📊 Resumen Ejecutivo",
            "📋 Tabla Detallada",
            "🔍 Auditoría"
        ])

        with tab1:
            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

            with col_kpi1:
                total_docs = len(df_filtrado)
                st.metric("📄 Total Documentos", total_docs)

            with col_kpi2:
                try:
                    total_gravado = float(df_filtrado["gra"].sum())
                    st.metric("💵 Total Gravado", f"${total_gravado:,.2f}")
                except Exception:
                    st.metric("💵 Total Gravado", "Error")

            with col_kpi3:
                try:
                    total_iva = float(df_filtrado["iva"].sum())
                    st.metric("📊 Total IVA", f"${total_iva:,.2f}")
                except Exception:
                    st.metric("📊 Total IVA", "Error")

            with col_kpi4:
                try:
                    total_general = float(df_filtrado["tot"].sum())
                    st.metric("💰 Total General", f"${total_general:,.2f}")
                except Exception:
                    st.metric("💰 Total General", "Error")

            st.divider()

            # Gráficos
            col_grafico1, col_grafico2 = st.columns(2)

            with col_grafico1:
                try:
                    tipo_counts = df_filtrado["tipo"].value_counts()
                    st.bar_chart(tipo_counts, use_container_width=True)
                except Exception:
                    st.info("No hay datos suficientes para gráfico")

            with col_grafico2:
                try:
                    motor_counts = df_filtrado["motor"].value_counts()
                    st.pie_chart(motor_counts, use_container_width=True)
                except Exception:
                    st.info("No hay datos suficientes para gráfico")

        with tab2:
            # Columnas a mostrar
            cols_mostrar = ["archivo", "fecha", "tipo", "nit", "nom", "gra", "iva", "tot", "motor", "fuente"]
            cols_existentes = [c for c in cols_mostrar if c in df_filtrado.columns]

            st.dataframe(
                df_filtrado[cols_existentes],
                use_container_width=True,
                hide_index=True
            )

        with tab3:
            st.subheader("Estado de Validación")

            col_val1, col_val2 = st.columns(2)

            with col_val1:
                iva_calc_count = df_filtrado["iva_calculado"].sum() if "iva_calculado" in df_filtrado.columns else 0
                st.metric("🧮 IVA Calculados", int(iva_calc_count))

            with col_val2:
                gemini_count = df_filtrado["confianza_gemini"].notna().sum() if "confianza_gemini" in df_filtrado.columns else 0
                st.metric("🤖 Validados Gemini", int(gemini_count))

    else:
        st.info("No hay registros que coincidan con los filtros aplicados.")

else:
    st.info("📭 Sube archivos PDF o JSON para comenzar la extracción.")
