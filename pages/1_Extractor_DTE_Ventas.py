"""
Extractor DTE Ventas — Learnix Hub
Soporta: DTE-01, DTE-03, DTE-05, DTE-06, DTE-11
Fuentes: PDF (motor nativo + OCR) | JSON (formato Hacienda)
Validacion: Gemini 1.5 Flash (activacion automatica por confianza baja)
"""

import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import gc
import pytesseract
import json
import os
import sys
import platform
from io import BytesIO

# ═══════════════════════════════════════════════════════════════
# PATH PARA MODULOS CORE
# ═══════════════════════════════════════════════════════════════

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ═══════════════════════════════════════════════════════════════
# IMPORTAR MODULOS CORE
# ═══════════════════════════════════════════════════════════════

try:
    from core.extractor.gemini_validator import (
        necesita_gemini, validar_con_gemini,
        aplicar_correcciones_gemini, gemini_disponible
    )
    from core.extractor.filtros import render_panel_filtros
    from core.extractor.json_parser import parsear_json_dte, parsear_multiples_json
    CORE_DISPONIBLE = True
except ImportError as _e:
    CORE_DISPONIBLE = False

# ═══════════════════════════════════════════════════════════════
# VERIFICACION DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════

if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("Acceso denegado. Por favor, inicia sesion en la pagina principal.")
    st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("Debes seleccionar un Cliente Activo antes de extraer Ventas.")
    st.stop()

if not isinstance(st.session_state.cliente_activo, dict):
    st.warning("El cliente activo no es valido. Regresa al Dashboard y vuelve a seleccionarlo.")
    st.stop()

cliente = st.session_state.cliente_activo

# ═══════════════════════════════════════════════════════════════
# CONFIGURACION TECNICA
# ═══════════════════════════════════════════════════════════════

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ═══════════════════════════════════════════════════════════════
# ESTILOS
# ═══════════════════════════════════════════════════════════════

st.markdown("""
<style>
    [data-testid="stAppViewContainer"],[data-testid="stHeader"]{background-color:#000!important}
    [data-testid="stSidebar"]{background-color:#161616!important;border-right:1px solid #333}
    h1,h2,h3,h4,h5,h6,p,label,span{color:#F7F5EE!important}
    [data-testid="stDataFrame"] span{color:inherit!important}
    div.stButton>button[kind="primary"],div.stDownloadButton>button[kind="primary"]{
        background-color:#666D57!important;border:1px solid #828B70!important;border-radius:6px;transition:.3s}
    div.stButton>button[kind="primary"]*,div.stDownloadButton>button[kind="primary"]*{
        color:#fff!important;font-weight:700!important}
    div.stButton>button[kind="primary"]:hover,div.stDownloadButton>button[kind="primary"]:hover{
        background-color:#798267!important}
    div.stButton>button[kind="secondary"]{
        background-color:#2A2A2A!important;border:1px solid #555!important;border-radius:6px}
    div.stButton>button[kind="secondary"]*{color:#fff!important;font-weight:700!important}
    div[data-testid="stAlert"]{min-height:80px;display:flex;align-items:center}
    .stAlert *{color:inherit!important}
    .scroll-list{max-height:150px;overflow-y:auto;padding:10px;background:#111;
        border-radius:5px;border:1px solid #333;font-family:monospace;font-size:13px;color:#66ff66}
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]{
        color:#666D57!important;border-bottom-color:#666D57!important}
    .stTabs [data-baseweb="tab-list"] button{color:#777!important}
    [data-testid="stExpander"]{background-color:#161616!important;border:1px solid #444!important;border-radius:6px}
    .alerta-activo{padding:10px;border-radius:6px;border-left:4px solid #666D57;
        background:#111;color:#fff;margin-bottom:15px;font-size:14px}
    .badge-gemini{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;
        font-weight:700;background:#1a3a1a;color:#4CAF50;border:1px solid #2e7d32;margin-left:6px}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# FUNCIONES UTILITARIAS
# ═══════════════════════════════════════════════════════════════

def limpiar_monto(monto_str) -> float:
    try:
        s = str(monto_str).replace(" ", "").replace("$", "").strip()
        if not s:
            return 0.0
        if "," in s and "." in s:
            return float(s.replace(",", ""))
        if "," in s and "." not in s:
            return float(s.replace(",", "."))
        return float(s)
    except (ValueError, AttributeError):
        return 0.0


def clasificar_tipo_ingreso(actividad: str) -> str:
    if not actividad:
        return "3"
    act = actividad.lower()
    if any(w in act for w in ["medico", "abogado", "contad", "ingeniero", "profesiones", "auditor"]):
        return "1"
    if any(w in act for w in ["servicio", "mantenimiento", "transporte", "flete", "taller"]):
        return "2"
    if any(w in act for w in ["industria", "fabricacion", "manufactura"]):
        return "4"
    if any(w in act for w in ["agro", "ganaderia", "agricultura"]):
        return "5"
    if any(w in act for w in ["export"]):
        return "7"
    return "3"


def separar_zonas_pdf(pagina):
    ancho = pagina.width
    alto  = pagina.height * 0.60
    zona_emisor   = pagina.crop((0,           0, ancho * 0.47, alto))
    zona_receptor = pagina.crop((ancho * 0.47, 0, ancho,       alto))
    return (
        zona_emisor.extract_text(x_tolerance=4)   or "",
        zona_receptor.extract_text(x_tolerance=4) or ""
    )


def extraer_uuid_limpio(texto: str) -> str:
    m = re.search(
        r"([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})",
        texto, re.I
    )
    if m:
        return m.group(1).upper()
    m2 = re.search(r"\b([A-F0-9]{32})\b", texto, re.I)
    if m2:
        r = m2.group(1).upper()
        return f"{r[:8]}-{r[8:12]}-{r[12:16]}-{r[16:20]}-{r[20:]}"
    return ""


# ═══════════════════════════════════════════════════════════════
# EXPORTACION EXCEL HACIENDA
# ═══════════════════════════════════════════════════════════════

def to_excel_hacienda(df: pd.DataFrame, anexo_tipo: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=False, sheet_name="Sheet1")
        wb  = writer.book
        ws  = writer.sheets["Sheet1"]
        fmt_num  = wb.add_format({"num_format": "0.00"})
        fmt_text = wb.add_format({"num_format": "@"})

        def col_width(ci):
            try:
                return max(df.iloc[:, ci].astype(str).map(len).max() if not df.empty else 10, 10) + 2
            except Exception:
                return 12

        ws.set_column(0, len(df.columns) - 1, 10.71)

        if anexo_tipo == "A":
            ws.set_column(0, 0, 10)
            ws.set_column(1, 1, 1,  fmt_text)
            ws.set_column(2, 2, 2)
            for ci in [3, 4, 5, 8]:
                ws.set_column(ci, ci, col_width(ci))
            ws.set_column(6, 6, 10.71)
            ws.set_column(7, 7, 14)
            for ci in [17, 18, 19]:
                ws.set_column(ci, ci, 1, fmt_text)
            for ci in range(9, 16):
                ws.set_column(ci, ci, None, fmt_num)

        elif anexo_tipo == "B":
            ws.set_column(0, 0, 10)
            ws.set_column(1, 1, 1,  fmt_text)
            ws.set_column(2, 2, 2)
            for ci in [7, 8]:
                ws.set_column(ci, ci, col_width(ci))
            for ci in [20, 21, 22]:
                ws.set_column(ci, ci, 1, fmt_text)
            for ci in range(10, 20):
                ws.set_column(ci, ci, None, fmt_num)

    output.seek(0)
    return output.getvalue()


# ═══════════════════════════════════════════════════════════════
# MOTOR DE EXTRACCION PDF
# ═══════════════════════════════════════════════════════════════

def extraer_dte_avanzado(f, cliente_activo: dict) -> dict:
    motor = "Nativo"
    try:
        if hasattr(f, "seek"):
            f.seek(0)

        with pdfplumber.open(f) as pdf:
            pagina       = pdf.pages[0]
            texto_prueba = pagina.extract_text() or ""
            ancho        = pagina.width
            alto         = pagina.height

            # Decidir: Nativo vs OCR
            if len(texto_prueba.strip()) < 100:
                motor    = "OCR"
                img_full = pagina.to_image(resolution=300)
                texto_raw = pytesseract.image_to_string(img_full.original, lang="spa")
                t_clean   = re.sub(r"\s+", " ", texto_raw)

                caja_rec = (ancho * 0.47, 0, ancho, alto * 0.60)
                img_rec  = pagina.crop(caja_rec).to_image(resolution=300)
                texto_receptor = pytesseract.image_to_string(img_rec.original, lang="spa")
            else:
                _, texto_receptor = separar_zonas_pdf(pagina)
                texto_raw = texto_prueba
                t_clean   = re.sub(r"\s+", " ", texto_raw)

            # Escudo anti-intrusos
            nit_emisor = re.sub(r"[^0-9]", "", cliente_activo.get("nit", ""))
            dui_emisor = re.sub(r"[^0-9]", "", cliente_activo.get("dui", ""))
            patron_ids = (
                r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b"
                r"|\b\d{14}\b|\b\d{8}-?\d{1}\b|\b\d{9}\b"
            )
            nits_en_doc = [re.sub(r"[^0-9]", "", n) for n in re.findall(patron_ids, t_clean)]

            es_valido = (
                nit_emisor == "00000000000000"
                or nit_emisor in nits_en_doc
                or (dui_emisor and dui_emisor in nits_en_doc)
            )
            if not es_valido:
                return {"error": f"Documento ajeno al emisor activo ({cliente_activo.get('nombre','N/A')})."}

            # Extraer NIT receptor
            patron_nit = r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b|\b\d{8}-?\d{1}\b"
            nit_m = re.search(r"N\s*[I1l|]?\s*T\s*[:]?\s*([\d\-\s]{9,20})", texto_receptor, re.I)
            if not nit_m:
                nit_m = re.search(r"(" + patron_nit + r")", texto_receptor)
            nit = re.sub(r"[^0-9]", "", nit_m.group(1)) if nit_m else ""

            # Nombre receptor
            if "RECEPTOR" in texto_receptor.upper():
                bloque = texto_receptor.split("RECEPTOR", 1)[-1]
            else:
                bloque = texto_receptor
            bloque = re.sub(r"^\s*\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}", "", bloque).strip()
            bloque_lineal = bloque.replace("\n", " ")
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

            # Identificadores del documento
            tipo_m = re.search(r"DTE-(\d{2})-", t_clean)
            tipo   = tipo_m.group(1) if tipo_m else "01"
            ctrl_m = re.search(r"(DTE-\d{2}-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)", t_clean)
            ctrl   = ctrl_m.group(1) if ctrl_m else ""
            gen    = extraer_uuid_limpio(t_clean)
            sello_m = re.search(r"Sello de Recepci[oó]n\s*[:]?\s*([A-Z0-9]{20,})", t_clean, re.I)
            sello   = sello_m.group(1) if sello_m else ""
            f_m   = re.search(r"(\d{4}-\d{2}-\d{2})", t_clean)
            fecha = ""
            if f_m:
                p = f_m.group(1).split("-")
                fecha = f"{p[2]}/{p[1]}/{p[0]}"
            act_m = re.search(r"Actividad\s+econ[oó]mica\s*[:]?\s*(.*?)(?=\s+Direcci[oó]n)", t_clean, re.I)
            t_ing = clasificar_tipo_ingreso(act_m.group(1) if act_m else "")

            # Buscar montos
            def buscar_montos(texto_b, tipo_dte, pdf_page=None):
                n, e, g, i, t, x = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                encontrado   = False
                iva_calculado = False

                if tipo_dte == "11":
                    exp_m = re.search(
                        r"(?:Total de Operaciones Afectas|Monto Total de la Operaci[oó]n)"
                        r"\s*[:]?\s*\$?\s*([\d,]+\.\d{2})",
                        texto_b, re.I
                    )
                    if exp_m:
                        x = limpiar_monto(exp_m.group(1))
                        t = x
                        encontrado = True
                else:
                    sum_m = re.search(
                        r"(?:Suma de Ventas|Ventas afectas):?\s*\$?\s*([\d,.]*)\s*([\d,.]*)\s*([\d,.]*)",
                        texto_b
                    )
                    if sum_m:
                        n = limpiar_monto(sum_m.group(1) or "0")
                        e = limpiar_monto(sum_m.group(2) or "0")
                        g = limpiar_monto(sum_m.group(3) or "0")
                        encontrado = True

                    iva_local = re.search(
                        r"(?:Impuesto al Valor Agregado 13%|IVA 13%|IVA)\s*[:]?\s*\$?\s*([\d,]+\.\d{2})",
                        texto_b, re.I
                    )
                    if iva_local:
                        i = limpiar_monto(iva_local.group(1))

                    tot_local = re.search(
                        r"(?:Total a Pagar|Monto Total)[\s$]*([\d,]+\.\d{2})",
                        texto_b, re.I
                    )
                    t = limpiar_monto(tot_local.group(1)) if tot_local else (g + i + e + n)

                # Fallback OCR zona totales
                if g == 0.0 and pdf_page:
                    try:
                        w = pdf_page.width
                        h = pdf_page.height
                        img_tot = pdf_page.crop((w * 0.40, h * 0.60, w, h)).to_image(resolution=300)
                        t_ocr   = re.sub(r"\s+", " ", pytesseract.image_to_string(img_tot.original, lang="spa"))

                        m_g = re.search(
                            r"(?:Suma Total de Operaciones|Sub-?Total|Ventas Gravadas)"
                            r"[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                            t_ocr, re.I
                        )
                        if m_g:
                            g = limpiar_monto(m_g.group(1))
                            encontrado = True

                        if i == 0.0:
                            m_i = re.search(
                                r"(?:Agregado 13%|IVA 13%|IVA)[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                                t_ocr, re.I
                            )
                            if m_i:
                                i = limpiar_monto(m_i.group(1))

                        if g > 0 and i == 0.0 and tipo_dte == "03":
                            i = round(g * 0.13, 2)
                            iva_calculado = True

                        if t == 0.0:
                            m_t = re.search(
                                r"(?:Total a Pagar|Monto Total)[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                                t_ocr, re.I
                            )
                            t = limpiar_monto(m_t.group(1)) if m_t else (g + i + e + n)
                    except Exception:
                        pass

                return n, e, g, i, t, x, encontrado, iva_calculado

            nos, exe, gra, iva, tot, exp_serv, exito, flag_iva = buscar_montos(t_clean, tipo, pagina)

            if not exito and len(pdf.pages) > 1:
                pagina2 = pdf.pages[1]
                if "OCR" in motor:
                    t_p2 = re.sub(r"\s+", " ", pytesseract.image_to_string(
                        pagina2.to_image(resolution=300).original, lang="spa"
                    ))
                else:
                    t_p2 = re.sub(r"\s+", " ", pagina2.extract_text() or "")
                n2, e2, g2, i2, t2, x2, ok2, fiva2 = buscar_montos(t_p2, tipo, pagina2)
                if ok2:
                    nos, exe, gra, iva, tot, exp_serv, flag_iva = n2, e2, g2, i2, t2, x2, fiva2

            return {
                "fecha": fecha, "nit": nit, "nom": nombre, "tipo": tipo,
                "ctrl": ctrl, "gen": gen, "sello": sello,
                "nos": nos, "exe": exe, "gra": gra, "iva": iva,
                "exp_serv": exp_serv, "tot": tot, "t_ing": t_ing,
                "motor": motor, "iva_calculado": flag_iva,
                "confianza_nit": "media", "confianza_rs": "media",
                "fuente": "PDF",
            }

    except Exception as err:
        return {"error": f"Error de lectura: {str(err)}"}


# ═══════════════════════════════════════════════════════════════
# MODAL DE DESCARGA
# ═══════════════════════════════════════════════════════════════

@st.dialog("Seguro de Calidad de Datos")
def ventana_descarga(df_resultados: pd.DataFrame, tipo_anexo: str, nombre_archivo: str):
    st.write(
        "Recuerda revisar las alertas de campos vacios, rechazados o "
        "calculos manuales antes de enviar a Hacienda."
    )
    st.download_button(
        label=f"Confirmar y Descargar Anexo {tipo_anexo}",
        data=to_excel_hacienda(df_resultados, tipo_anexo),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True
    )


# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:Courier New,monospace;color:#666D57;"
    "letter-spacing:2px;margin-bottom:0;padding-bottom:0'>YN</h2>",
    unsafe_allow_html=True
)
st.title("Extractor DTE - Ventas")
st.markdown(f"""
<div class="alerta-activo">
    <strong>EMISOR ACTUAL:</strong>
    {cliente.get('nombre','N/A')} (NIT: {cliente.get('nit','N/A')})
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# INICIALIZACION DE ESTADO
# ═══════════════════════════════════════════════════════════════

for _k, _v in [
    ("uploader_key_v",         str(time.time())),
    ("json_key_v",             str(time.time()) + "_j"),
    ("db_ventas",              pd.DataFrame()),
    ("archivos_procesados_v",  set()),
    ("reporte_ventas",         None),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ═══════════════════════════════════════════════════════════════
# SIDEBAR — CARGA PDF + JSON
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("Carga de Datos")
    st.caption(f"Cliente: {cliente.get('nombre','N/A')}")
    st.divider()

    tab_pdf, tab_json = st.tabs(["PDF", "JSON"])

    # ─── TAB PDF ───────────────────────────────────────────────
    with tab_pdf:
        usar_gemini = False
        if CORE_DISPONIBLE and gemini_disponible():
            usar_gemini = st.checkbox(
                "Activar Gemini 1.5 Flash",
                value=False,
                help="Valida documentos con datos dudosos usando IA."
            )
        elif CORE_DISPONIBLE:
            st.caption("Gemini: configura GEMINI_API_KEY en secrets.")

        archivos_pdf = st.file_uploader(
            "PDFs de Ventas (DTE 01,03,05,06,11)",
            type="pdf",
            accept_multiple_files=True,
            key=st.session_state.uploader_key_v
        )

        if archivos_pdf and st.button("Procesar PDFs", type="primary",
                                       use_container_width=True, key="btn_pdf_v"):
            extracted           = []
            duplicados_gen      = []
            vacios_deteccion    = []
            iva_calculado_files = []
            archivos_rechazados = []
            gemini_validados    = []
            nuevos = [f for f in archivos_pdf
                      if f.name not in st.session_state.archivos_procesados_v]

            if nuevos:
                bar          = st.progress(0)
                txt          = st.empty()
                t_ini        = time.time()
                total        = len(nuevos)

                for idx, f in enumerate(nuevos):
                    if idx > 0 and idx % 30 == 0:
                        gc.collect()

                    if idx > 0:
                        elapsed = time.time() - t_ini
                        eta     = int((elapsed / idx) * (total - idx))
                        m, s    = divmod(eta, 60)
                        txt.markdown(f"Procesando: **{idx+1}/{total}** | Restante: {m:02d}:{s:02d}")
                    else:
                        txt.markdown(f"Procesando: **1/{total}** | Calculando...")

                    f.seek(0)
                    file_bytes = f.read()
                    f.seek(0)

                    res = extraer_dte_avanzado(f, cliente)
                    st.session_state.archivos_procesados_v.add(f.name)

                    if "error" in res:
                        archivos_rechazados.append(f"{f.name} — {res['error']}")
                    else:
                        # Gemini si aplica
                        if usar_gemini and CORE_DISPONIBLE:
                            c_nit = res.get("confianza_nit", "media")
                            c_rs  = res.get("confianza_rs",  "media")
                            gra   = float(res.get("gra", 0) or 0)
                            tot   = float(res.get("tot", 0) or 0)
                            iva   = float(res.get("iva", 0) or 0)
                            if necesita_gemini(c_nit, c_rs, gra, tot, iva):
                                try:
                                    with pdfplumber.open(BytesIO(file_bytes)) as _pdf:
                                        texto_pdf = "".join(
                                            (p.extract_text() or "") for p in _pdf.pages
                                        )
                                    tipo_doc = "CCF" if res.get("tipo") == "03" else "Factura"
                                    gem_res  = validar_con_gemini(texto_pdf, res, tipo_doc)
                                    if "error" not in gem_res:
                                        res = aplicar_correcciones_gemini(res, gem_res)
                                        gemini_validados.append(f.name)
                                except Exception:
                                    pass

                        res["fuente"] = "PDF"
                        tot_val = float(res.get("tot", 0) or 0)
                        incompleto = (
                            ("" in [res.get("fecha",""), res.get("ctrl","")])
                            if res.get("tipo") in ["01","11"]
                            else ("" in [res.get("fecha",""), res.get("nit",""),
                                          res.get("nom",""), res.get("ctrl","")])
                        ) or tot_val == 0.0

                        if incompleto:
                            vacios_deteccion.append(f.name)
                        if res.get("iva_calculado"):
                            iva_calculado_files.append(f.name)

                        codigo_gen = res.get("gen","")
                        dup_mem  = (not st.session_state.db_ventas.empty
                                    and codigo_gen != ""
                                    and "gen" in st.session_state.db_ventas.columns
                                    and (st.session_state.db_ventas["gen"] == codigo_gen).any())
                        dup_lote = (codigo_gen != ""
                                    and any(d.get("gen") == codigo_gen for d in extracted))

                        if dup_mem or dup_lote:
                            duplicados_gen.append(f.name)
                        else:
                            res["archivo"] = f.name
                            extracted.append(res)

                    bar.progress((idx + 1) / total)

                txt.success(f"{total} archivos procesados.")

                st.session_state.reporte_ventas = {
                    "rechazados":     archivos_rechazados,
                    "vacios":         vacios_deteccion,
                    "duplicados_gen": duplicados_gen,
                    "iva_calc":       iva_calculado_files,
                    "gemini":         gemini_validados,
                }
                if extracted:
                    ndf = pd.DataFrame(extracted)
                    st.session_state.db_ventas = (
                        ndf if st.session_state.db_ventas.empty
                        else pd.concat([st.session_state.db_ventas, ndf], ignore_index=True)
                    )
                gc.collect()
                time.sleep(0.3)
                st.rerun()

    # ─── TAB JSON ──────────────────────────────────────────────
    with tab_json:
        st.caption("JSON oficial del Ministerio de Hacienda (DTE 01,03,05,06,11)")
        archivos_json = st.file_uploader(
            "JSONs de Ventas",
            type=["json"],
            accept_multiple_files=True,
            key=st.session_state.json_key_v
        )

        if archivos_json and st.button("Procesar JSONs", type="primary",
                                        use_container_width=True, key="btn_json_v"):
            if CORE_DISPONIBLE:
                nuevos_j = [f for f in archivos_json
                             if f.name not in st.session_state.archivos_procesados_v]

                extracted_j, _, errores_j, rechazados_j = parsear_multiples_json(
                    nuevos_j, "ventas", st.session_state.archivos_procesados_v
                )
                # Deduplicacion
                definitivos = []
                duplicados_j = []
                for res in extracted_j:
                    cg = res.get("gen","")
                    dup = (not st.session_state.db_ventas.empty
                           and cg != ""
                           and "gen" in st.session_state.db_ventas.columns
                           and (st.session_state.db_ventas["gen"] == cg).any())
                    if dup:
                        duplicados_j.append(res.get("archivo","?"))
                    else:
                        definitivos.append(res)

                for f in nuevos_j:
                    st.session_state.archivos_procesados_v.add(f.name)

                if definitivos:
                    ndf = pd.DataFrame(definitivos)
                    st.session_state.db_ventas = (
                        ndf if st.session_state.db_ventas.empty
                        else pd.concat([st.session_state.db_ventas, ndf], ignore_index=True)
                    )

                resumen = []
                if definitivos:   resumen.append(f"{len(definitivos)} importados")
                if duplicados_j:  resumen.append(f"{len(duplicados_j)} duplicados")
                if errores_j:     resumen.append(f"{len(errores_j)} errores")
                if rechazados_j:  resumen.append(f"{len(rechazados_j)} tipo incorrecto")
                if resumen:
                    st.success(" | ".join(resumen))
                if errores_j:
                    with st.expander("Errores JSON"):
                        for e in errores_j:
                            st.error(e)
                if rechazados_j:
                    with st.expander("Tipos incorrectos"):
                        for r in rechazados_j:
                            st.warning(r)
                gc.collect()
                st.rerun()
            else:
                st.error("Modulo core no disponible. Revisa la instalacion.")

    st.divider()
    if st.button("Limpiar Memoria", type="secondary", use_container_width=True, key="btn_limpiar_v"):
        for _var in ["db_ventas", "archivos_procesados_v", "reporte_ventas"]:
            st.session_state.pop(_var, None)
        st.session_state.uploader_key_v = str(time.time())
        st.session_state.json_key_v     = str(time.time()) + "_j"
        gc.collect()
        st.rerun()

    if not st.session_state.db_ventas.empty:
        st.divider()
        df_tmp = st.session_state.db_ventas
        n_pdf  = len(df_tmp[df_tmp.get("fuente","PDF") == "PDF"]) if "fuente" in df_tmp.columns else len(df_tmp)
        n_json = len(df_tmp[df_tmp.get("fuente","PDF") == "JSON"]) if "fuente" in df_tmp.columns else 0
        st.caption(f"Total: {len(df_tmp)} | PDF: {n_pdf} | JSON: {n_json}")

# ═══════════════════════════════════════════════════════════════
# DASHBOARD DE REPORTE
# ═══════════════════════════════════════════════════════════════

if st.session_state.reporte_ventas:
    rep = st.session_state.reporte_ventas
    st.markdown("### Reporte de Extraccion")
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        n = len(rep.get("rechazados",[]))
        if n: st.error(f"**{n} Rechazados**")
        else: st.success("0 Rechazados")
        if n:
            with st.expander("Ver"):
                st.markdown('<div class="scroll-list">'
                            + "".join(f"- {a}<br>" for a in rep["rechazados"])
                            + "</div>", unsafe_allow_html=True)

    with c2:
        n = len(rep.get("vacios",[]))
        if n: st.error(f"**{n} Incompletos**")
        else: st.success("0 Incompletos")
        if n:
            with st.expander("Ver"):
                st.markdown('<div class="scroll-list">'
                            + "".join(f"- {a}<br>" for a in rep["vacios"])
                            + "</div>", unsafe_allow_html=True)

    with c3:
        n = len(rep.get("duplicados_gen",[]))
        if n: st.error(f"**{n} Duplicados**")
        else: st.success("0 Duplicados")
        if n:
            with st.expander("Ver"):
                st.markdown('<div class="scroll-list">'
                            + "".join(f"- {a}<br>" for a in rep["duplicados_gen"])
                            + "</div>", unsafe_allow_html=True)

    with c4:
        n = len(rep.get("iva_calc",[]))
        if n: st.info(f"**{n} IVA Calc.**")
        else: st.success("0 IVA Calc.")
        if n:
            with st.expander("Ver"):
                st.markdown('<div class="scroll-list">'
                            + "".join(f"- {a}<br>" for a in rep["iva_calc"])
                            + "</div>", unsafe_allow_html=True)

    with c5:
        n = len(rep.get("gemini",[]))
        if n: st.success(f"**{n} Gemini**")
        else: st.info("0 Gemini")
        if n:
            with st.expander("Ver"):
                st.markdown('<div class="scroll-list">'
                            + "".join(f"- {a}<br>" for a in rep["gemini"])
                            + "</div>", unsafe_allow_html=True)

    st.divider()

# ═══════════════════════════════════════════════════════════════
# TABLAS DE RESULTADOS
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_ventas.empty:
    df = st.session_state.db_ventas

    # Filtros
    if CORE_DISPONIBLE:
        df = render_panel_filtros(df, key_prefix="ventas")

    tab1, tab2, tab3 = st.tabs([
        "F-07 Ventas a Contribuyentes (CCF)",
        "F-07 Ventas Consumidor (Facturas)",
        "Auditoria Total"
    ])

    # ── TAB 1: CCF ─────────────────────────────────────────────
    with tab1:
        df_a = df[df["tipo"].isin(["03","05","06"])].copy() if "tipo" in df.columns else pd.DataFrame()

        if df_a.empty:
            st.info("No hay CCF procesados. Carga DTE tipo 03, 05 o 06.")
        else:
            df_a["clase"]      = "4"
            df_a["ctrl_vacio"] = ""
            df_a["v_terc"]     = 0.00
            df_a["d_terc"]     = 0.00
            df_a["dui"]        = ""
            df_a["t_op"]       = "1"
            df_a["n_anexo"]    = "1"
            # nos puede no existir en JSON
            for col in ["nos","exe","gra","iva"]:
                if col not in df_a.columns:
                    df_a[col] = 0.0

            cols = ["fecha","clase","tipo","ctrl","sello","gen","ctrl_vacio",
                    "nit","nom","exe","nos","gra","iva","v_terc","d_terc",
                    "tot","dui","t_op","t_ing","n_anexo"]
            cols_ok = [c for c in cols if c in df_a.columns]
            res_a   = df_a[cols_ok].sort_values(by="ctrl").copy()
            etiquetas = {
                "fecha":"1.Fecha","clase":"2.Clase","tipo":"3.Tipo",
                "ctrl":"4.Num Control","sello":"5.Sello","gen":"6.Generacion",
                "ctrl_vacio":"7.Num Control 2","nit":"8.NIT/NRC","nom":"9.Razon Social",
                "exe":"10.Exentas","nos":"11.No Sujetas","gra":"12.Gravadas",
                "iva":"13.Debito","v_terc":"14.V. Terceros","d_terc":"15.D. Terceros",
                "tot":"16.Total","dui":"17.DUI","t_op":"18.Tipo Op",
                "t_ing":"19.Tipo Ing","n_anexo":"20.Anexo"
            }
            res_a = res_a.rename(columns={k:v for k,v in etiquetas.items() if k in res_a.columns})
            cols_num = [v for k,v in etiquetas.items()
                        if k in ["exe","nos","gra","iva","v_terc","d_terc","tot"] and v in res_a.columns]

            st.dataframe(
                res_a.style.format({c:"{:.2f}" for c in cols_num}),
                hide_index=True, use_container_width=True
            )
            col_b1, col_b2 = st.columns([2,1])
            with col_b1:
                st.info(f"Registros CCF: **{len(res_a)}**")
            with col_b2:
                if st.button("Preparar Excel CCF", type="primary", use_container_width=True):
                    ventana_descarga(res_a, "A", "F07_Ventas_Contribuyentes.xlsx")

    # ── TAB 2: Facturas ────────────────────────────────────────
    with tab2:
        df_b = df[df["tipo"].isin(["01","11"])].copy() if "tipo" in df.columns else pd.DataFrame()

        if df_b.empty:
            st.info("No hay Facturas procesadas. Carga DTE tipo 01 o 11.")
        else:
            df_b["clase"]               = "4"
            df_b["res"]                 = "N/A"
            df_b["ser"]                 = "N/A"
            df_b["int"]                 = "N/A"
            df_b["maq"]                 = ""
            df_b["pre_ctrl"]            = "N/A"
            df_b["vtas_int_exe_no_suj"] = 0.00
            df_b["n_anexo"]             = "2"
            df_b["exp_ca"]              = 0.00
            df_b["exp_fca"]             = 0.00
            df_b["v_zf"]                = 0.00
            df_b["v_ter"]               = 0.00
            df_b["t_op"]                = "1"
            for col in ["exp_serv","exe","nos","gra"]:
                if col not in df_b.columns:
                    df_b[col] = 0.0

            cols = ["fecha","clase","tipo","res","ser","int","pre_ctrl",
                    "ctrl","gen","maq","exe","nos","vtas_int_exe_no_suj","gra",
                    "exp_ca","exp_fca","exp_serv","v_zf","v_ter","tot","t_op","t_ing","n_anexo"]
            cols_ok = [c for c in cols if c in df_b.columns]
            res_b   = df_b[cols_ok].sort_values(by="ctrl").copy()
            etiquetas_b = {
                "fecha":"1.Fecha","clase":"2.Clase","tipo":"3.Tipo",
                "res":"4.Resolucion","ser":"5.Serie","int":"6.Interno",
                "pre_ctrl":"7.Pre-Control","ctrl":"8.Num Control","gen":"9.Generacion",
                "maq":"10.Maquina","exe":"11.Exentas","nos":"12.No Sujetas",
                "vtas_int_exe_no_suj":"13.Vtas Int Exe No Suj Prop","gra":"14.Gravadas",
                "exp_ca":"15.Exp CA","exp_fca":"16.Exp Fuera CA","exp_serv":"17.Exp Serv",
                "v_zf":"18.ZF y DPA","v_ter":"19.V. Terceros","tot":"20.Total",
                "t_op":"21.Tipo Op","t_ing":"22.Tipo Ing","n_anexo":"23.Anexo"
            }
            res_b    = res_b.rename(columns={k:v for k,v in etiquetas_b.items() if k in res_b.columns})
            num_cols_b = [v for k,v in etiquetas_b.items()
                          if k in ["exe","nos","vtas_int_exe_no_suj","gra","exp_ca",
                                   "exp_fca","exp_serv","v_zf","v_ter","tot"] and v in res_b.columns]
            st.dataframe(
                res_b.style.format({c:"{:.2f}" for c in num_cols_b}),
                hide_index=True, use_container_width=True
            )
            col_b3, col_b4 = st.columns([2,1])
            with col_b3:
                st.info(f"Registros Facturas: **{len(res_b)}**")
            with col_b4:
                if st.button("Preparar Excel Facturas", type="primary", use_container_width=True):
                    ventana_descarga(res_b, "B", "F07_Ventas_Consumidor.xlsx")

    # ── TAB 3: Auditoria ───────────────────────────────────────
    with tab3:
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        with col_a1:
            st.metric("Total Registros", len(df))
        with col_a2:
            tot_sum = df["tot"].apply(lambda x: float(x) if x else 0.0).sum() if "tot" in df.columns else 0
            st.metric("Total Facturado", f"${tot_sum:,.2f}")
        with col_a3:
            n_pdf_t  = len(df[df["fuente"]=="PDF"])  if "fuente" in df.columns else len(df)
            st.metric("Desde PDF",  n_pdf_t)
        with col_a4:
            n_json_t = len(df[df["fuente"]=="JSON"]) if "fuente" in df.columns else 0
            st.metric("Desde JSON", n_json_t)

        st.divider()
        cols_mostrar = [c for c in df.columns if c not in ["_debug","gemini_obs"]]
        st.dataframe(df[cols_mostrar], use_container_width=True, hide_index=True)
