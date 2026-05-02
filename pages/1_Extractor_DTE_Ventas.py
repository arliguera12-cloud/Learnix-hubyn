# pages/1_Extractor_DTE_Ventas.py
"""
EXTRACTOR DTE VENTAS v2.0
Soporta: PDF (Nativo + OCR) y JSON (Ministerio Hacienda)
Incluye validación con Gemini 1.5 Flash
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
    validar_con_gemini,
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
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Ventas.")
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
    page_title="Extractor DTE Ventas",
    layout="wide",
    page_icon="📈"
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
    .alerta-activo {
        padding: 10px;
        border-radius: 6px;
        border-left: 4px solid #666D57;
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
        color: #666D57 !important;
        border-bottom-color: #666D57 !important;
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

def clasificar_tipo_ingreso(actividad: str) -> str:
    """Clasifica el tipo de ingreso según la actividad económica."""
    if not actividad:
        return "3"

    act = str(actividad).lower()

    clasificaciones = {
        "1": ["médico", "abogado", "contador", "ingeniero", "profesiones", "auditor"],
        "2": ["servicio", "mantenimiento", "transporte", "flete", "taller"],
        "4": ["industria", "fabricación", "manufactura"],
        "5": ["agro", "ganadería", "agricultura"],
        "7": ["export"],
    }

    for tipo_ing, palabras in clasificaciones.items():
        if any(palabra in act for palabra in palabras):
            return tipo_ing

    return "3"


def separar_zonas_pdf(pagina) -> tuple:
    """
    Separa la página en zona EMISOR (izquierda) y RECEPTOR (derecha).
    Evita que pdfplumber mezcle datos de ambas partes.
    """
    ancho = pagina.width
    alto = pagina.height
    alto_header = alto * 0.60

    zona_emisor = pagina.crop((0, 0, ancho * 0.47, alto_header))
    zona_receptor = pagina.crop((ancho * 0.47, 0, ancho, alto_header))

    texto_emisor = zona_emisor.extract_text(x_tolerance=4) or ""
    texto_receptor = zona_receptor.extract_text(x_tolerance=4) or ""

    return texto_emisor, texto_receptor


def extraer_dte_avanzado(archivo, cliente_activo: dict) -> dict:
    """
    Motor de extracción de DTE de Ventas (El Salvador).
    Soporta DTE: 01 (Factura), 03 (CCF), 05 (NC), 06 (ND), 11 (Exportación).
    
    Retorna:
        dict con datos extraídos o error
    """
    motor = "Nativo"

    try:
        # Leer bytes y resetear cursor
        if hasattr(archivo, 'seek'):
            archivo.seek(0)
        file_bytes = archivo.read()
        archivo.seek(0)

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            pagina = pdf.pages[0]
            texto_prueba = pagina.extract_text() or ""

            # Decisión: NATIVO vs OCR
            if len(texto_prueba.strip()) < 100:
                # PDF imagen → OCR
                motor = "OCR"
                img = pagina.to_image(resolution=300)
                texto_raw = pytesseract.image_to_string(img.original, lang='spa')
                texto_receptor = ""
                try:
                    caja_receptor = (pagina.width * 0.47, 0, pagina.width, pagina.height * 0.60)
                    img_receptor = pagina.crop(caja_receptor).to_image(resolution=300)
                    texto_receptor = pytesseract.image_to_string(img_receptor.original, lang='spa')
                except Exception:
                    pass
            else:
                # PDF nativo
                texto_emisor_coord, texto_receptor = separar_zonas_pdf(pagina)
                texto_raw = texto_prueba

            t_clean = re.sub(r'\s+', ' ', texto_raw)
            t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        # ── VALIDACIÓN DE CLIENTE ACTIVO (ESCUDO ANTI-INTRUSOS) ──
        nit_emisor = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
        dui_emisor = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))

        patron_ids = (
            r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b"
            r"|\b\d{14}\b"
            r"|\b\d{8}-?\d{1}\b"
            r"|\b\d{9}\b"
        )

        nits_en_doc = [re.sub(r'[^0-9]', '', n) for n in re.findall(patron_ids, t_clean)]

        es_valido = (
            nit_emisor == "00000000000000"
            or nit_emisor in nits_en_doc
            or (dui_emisor and dui_emisor in nits_en_doc)
        )

        if not es_valido:
            return {"error": f"Documento ajeno al emisor activo ({cliente_activo.get('nombre', 'N/A')})."}

        # ── EXTRACCIÓN DE IDENTIFICADORES ──
        tipo_m = re.search(r"DTE-(\d{2})-", t_clean)
        tipo = tipo_m.group(1) if tipo_m else "01"

        ctrl_m = re.search(r"(DTE-\d{2}-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)", t_clean)
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

        # ── EXTRACCIÓN DEL RECEPTOR ──
        patron_nit = r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b|\b\d{8}-?\d{1}\b"
        nit_m = re.search(
            r"N\s*[I1l|]?\s*T\s*[:]?\s*([\d\-\s]{9,20})",
            texto_receptor, re.I
        )

        if not nit_m:
            nit_m = re.search(f"({patron_nit})", texto_receptor)

        nit_receptor = re.sub(r'[^0-9]', '', nit_m.group(1)) if nit_m else ""

        # Nombre del receptor
        bloque_nombre = ""
        if "RECEPTOR" in texto_receptor.upper():
            bloque_nombre = texto_receptor.split("RECEPTOR", 1)[-1]
        elif "Generacion" in texto_receptor or "Generación" in texto_receptor:
            sep = "Generacion" if "Generacion" in texto_receptor else "Generación"
            bloque_nombre = texto_receptor.split(sep, 1)[-1]
        else:
            bloque_nombre = texto_receptor

        bloque_lineal = bloque_nombre.replace('\n', ' ')

        nom_m = re.search(
            r"(.*?)(?=\bN\s*[I|1l]\s*T\b|\bN\s*R\s*C\b|\bActividad\b|" + patron_nit + r")",
            bloque_lineal, re.I
        )

        if nom_m:
            nombre_sucio = nom_m.group(1)
            nombre = re.sub(
                r"(Nombre\s+o\s+raz[oó]n\s+social|Nombre|Raz[oó]n\s+social)\s*[:]?\s*",
                "", nombre_sucio, flags=re.I
            ).strip()
            nombre = re.sub(r"\|", "I", nombre).strip()
            nombre = re.sub(r"^[^A-Za-z0-9]+", "", nombre).strip()
        else:
            nombre = ""

        # ── EXTRACCIÓN DE ACTIVIDAD ECONÓMICA ──
        act_m = re.search(
            r"Actividad\s+econ[oó]mica\s*[:]?\s*(.*?)(?=\s+Direcci[oó]n)",
            t_clean, re.I
        )
        t_ing = clasificar_tipo_ingreso(act_m.group(1) if act_m else "")

        # ── BÚSQUEDA DE MONTOS ──
        def buscar_montos(texto_buscar: str, tipo_dte: str) -> tuple:
            """Extrae montos usando patrones."""
            nos, exe, gra, iva, tot, exp_serv = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            iva_calculado = False
            encontrado = False

            if tipo_dte == "11":
                # Exportación
                exp_m = re.search(
                    r"(?:Total de Operaciones Afectas|Monto Total de la Operaci[oó]n)"
                    r"\s*[:]?\s*\$?\s*([\d,]+\.\d{2})",
                    texto_buscar, re.I
                )
                if exp_m:
                    exp_serv = limpiar_monto(exp_m.group(1))
                    tot = exp_serv
                    encontrado = True
            else:
                # CCF/Facturas normales
                sum_m = re.search(
                    r"(?:Suma de Ventas|Ventas afectas):?\s*\$?\s*([\d,.]*)\s*([\d,.]*)\s*([\d,.]*)",
                    texto_buscar
                )
                if sum_m:
                    nos = limpiar_monto(sum_m.group(1) or "0")
                    exe = limpiar_monto(sum_m.group(2) or "0")
                    gra = limpiar_monto(sum_m.group(3) or "0")
                    encontrado = True

                # IVA
                iva_m = re.search(
                    r"(?:Impuesto al Valor Agregado 13%|IVA 13%|IVA)\s*[:]?\s*\$?\s*([\d,]+\.\d{2})",
                    texto_buscar, re.I
                )
                if iva_m:
                    iva = limpiar_monto(iva_m.group(1))
                elif gra > 0:
                    iva = round(gra * 0.13, 2)
                    iva_calculado = True

                # Total
                tot_m = re.search(
                    r"(?:Total a Pagar|Monto Total)[\s$]*([\d,]+\.\d{2})",
                    texto_buscar, re.I
                )
                tot = limpiar_monto(tot_m.group(1)) if tot_m else (gra + iva + exe + nos)

            return nos, exe, gra, iva, tot, exp_serv, encontrado, iva_calculado

        nos, exe, gra, iva, tot, exp_serv, exito_ventas, flag_iva = buscar_montos(
            t_clean, tipo
        )

        return {
            "fecha": fecha,
            "nit": nit_receptor,
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
            "iva_calculado": flag_iva,
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
# HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:Courier New,monospace; color:#666D57; "
    "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("📈 Extractor DTE - Ventas")

st.markdown(f"""
<div class="alerta-activo">
    <strong>EMISOR ACTUAL (Cliente Activo):</strong><br>
    {cliente.get('nombre', 'N/A')} (NIT: {cliente.get('nit', 'N/A')})
</div>
""", unsafe_allow_html=True)

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
            "Arrastra tus PDFs (DTE 01, 03, 05, 06, 11)",
            type="pdf",
            accept_multiple_files=True,
            key=st.session_state.uploader_key_v,
            help="Soporta múltiples archivos PDF de DTE"
        )

        usar_gemini = False
        if st.secrets.get("GEMINI_API_KEY"):
            usar_gemini = st.checkbox(
                "🤖 Activar Validación Gemini",
                value=False,
                help="Si la confianza es baja, Gemini intentará corregir los datos"
            )

        if archivos_pdf and st.button(
            "▶️ Procesar PDFs",
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

            nuevos = [
                f for f in archivos_pdf
                if f.name not in st.session_state.archivos_procesados_v
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
                    res = extraer_dte_avanzado(f, cliente)
                    st.session_state.archivos_procesados_v.add(f.name)

                    if "error" in res:
                        archivos_rechazados.append(f"{f.name} — {res['error']}")
                    else:
                        # ── GEMINI: validación si confianza baja ──
                        if usar_gemini and st.secrets.get("GEMINI_API_KEY"):
                            c_nit = res.get("confianza_nit", "media")
                            c_rs = res.get("confianza_rs", "media")
                            gra = float(res.get("gra", 0))
                            tot = float(res.get("tot", 0))

                            if necesita_gemini(c_nit, c_rs, gra, tot):
                                try:
                                    f.seek(0)
                                    with pdfplumber.open(f) as pdf:
                                        texto_pdf = "".join(
                                            (p.extract_text() or "") for p in pdf.pages[:2]
                                        )
                                    
                                    gemini_res = validar_con_gemini(
                                        texto_pdf,
                                        res,
                                        "CCF" if res.get("tipo") == "03" else "Factura"
                                    )
                                    
                                    if gemini_res.get("_exito"):
                                        # Aplicar correcciones
                                        for campo in ["nit", "nom", "gra", "iva", "exe", "tot", "gen"]:
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
                                "" in [
                                    res.get("fecha", ""), res.get("nit", ""),
                                    res.get("nom", ""), res.get("ctrl", "")
                                ]
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

                txt_progreso.success(f"✅ {total} documentos procesados")

                st.session_state.reporte_ventas = {
                    "rechazados": archivos_rechazados,
                    "vacios": vacios_deteccion,
                    "duplicados_gen": duplicados_gen,
                    "iva_calc": iva_calculado_files,
                    "gemini": gemini_validados,
                }

                if extracted:
                    new_df = pd.DataFrame(extracted)
                    st.session_state.db_ventas = (
                        new_df if st.session_state.db_ventas.empty
                        else pd.concat([st.session_state.db_ventas, new_df], ignore_index=True)
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
            "Arrastra JSONs (DTE 01, 03, 05, 06, 11)",
            type=["json"],
            accept_multiple_files=True,
            key=st.session_state.json_key_v
        )

        if archivos_json and st.button(
            "▶️ Procesar JSONs",
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

                    if "error" in res:
                        errores_json.append(f"{f.name} — {res['error']}")
                        continue

                    # Validar tipo DTE
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
                st.session_state.db_ventas = (
                    new_df if st.session_state.db_ventas.empty
                    else pd.concat([st.session_state.db_ventas, new_df], ignore_index=True)
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

            if rechazados_tipo:
                with st.expander("Ver rechazados"):
                    for r in rechazados_tipo:
                        st.warning(r)

            gc.collect()
            st.rerun()

    # ── Botón Limpiar ──
    st.divider()
    if st.button("🧹 Limpiar Memoria", type="secondary", use_container_width=True):
        for var in ["db_ventas", "archivos_procesados_v", "reporte_ventas"]:
            st.session_state.pop(var, None)
        st.session_state.uploader_key_v = str(time.time())
        st.session_state.json_key_v = str(time.time()) + "_json"
        gc.collect()
        st.rerun()

    if not st.session_state.db_ventas.empty:
        st.divider()
        total_pdf = len(
            st.session_state.db_ventas[
                st.session_state.db_ventas.get("fuente", pd.Series()) == "PDF"
            ]
        ) if "fuente" in st.session_state.db_ventas.columns else len(st.session_state.db_ventas)

        total_json = len(
            st.session_state.db_ventas[
                st.session_state.db_ventas.get("fuente", pd.Series()) == "JSON"
            ]
        ) if "fuente" in st.session_state.db_ventas.columns else 0

        st.caption(f"📊 Total: {len(st.session_state.db_ventas)} | PDF: {total_pdf} | JSON: {total_json}")

# ═══════════════════════════════════════════════════════════════
# REPORTE DE EXTRACCIÓN
# ═══════════════════════════════════════════════════════════════

if st.session_state.reporte_ventas:
    rep = st.session_state.reporte_ventas
    st.markdown("### 📋 Reporte de Extracción")

    col1, col2, col3, col4 = st.columns(4)

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

    with col4:
        n = len(rep.get("iva_calc", []))
        if n:
            st.info(f"🧮 **{n} IVA Calc**")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join([f"• {a}<br>" for a in rep["iva_calc"]])
                    + '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ **0 IVA Calc**")

    if rep.get("gemini"):
        st.info(f"🤖 **{len(rep['gemini'])} Validados con Gemini**")

    st.divider()

# ═══════════════════════════════════════════════════════════════
# TABLA DE RESULTADOS CON FILTROS
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_ventas.empty:
    st.markdown("### 📊 Datos Extraídos")

    # Aplicar filtros
    df_filtrado = render_panel_filtros(st.session_state.db_ventas, "ventas_v")

    if not df_filtrado.empty:
        # Mostrar tabla
        st.dataframe(
            df_filtrado[
                ["fecha", "nit", "nom", "tipo", "gra", "iva", "tot", "motor", "fuente"]
            ],
            use_container_width=True,
            hide_index=True
        )

        # Estadísticas
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("📊 Registros", len(df_filtrado))
        with col_stat2:
            total_gra = df_filtrado["gra"].apply(lambda x: float(x) if x else 0.0).sum()
            st.metric("💵 Total Gravado", f"${total_gra:,.2f}")
        with col_stat3:
            total_general = df_filtrado["tot"].apply(lambda x: float(x) if x else 0.0).sum()
            st.metric("🎯 Total General", f"${total_general:,.2f}")
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
