import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import gc
import pytesseract
from io import BytesIO
import platform

# ═══════════════════════════════════════════════════════════════
# 🔐 VERIFICACIÓN DE SEGURIDAD
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
# ⚙️ CONFIGURACIÓN TÉCNICA
# ═══════════════════════════════════════════════════════════════
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# st.set_page_config() ya ejecutado en app.py

# ═══════════════════════════════════════════════════════════════
# 🎨 ESTILOS GLOBALES
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
    [data-testid="stDataFrame"] span { color: inherit !important; }

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
    .stAlert * { color: inherit !important; }
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
    .stTabs [data-baseweb="tab-list"] button { color: #777777 !important; }
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
# 💾 FUNCIONES UTILITARIAS
# ═══════════════════════════════════════════════════════════════

def to_excel_hacienda(df, anexo_tipo):
    """Exporta DataFrame al formato exacto de Hacienda El Salvador."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False)
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        fmt_num = workbook.add_format({'num_format': '0.00'})
        fmt_texto = workbook.add_format({'num_format': '@'})

        def get_max_len(col_idx):
            try:
                return max(
                    df.iloc[:, col_idx].astype(str).map(len).max() if not df.empty else 10,
                    10
                ) + 2
            except Exception:
                return 12

        worksheet.set_column(0, len(df.columns) - 1, 10.71)

        if anexo_tipo == "A":
            worksheet.set_column(0, 0, 10)
            worksheet.set_column(1, 1, 1, fmt_texto)
            worksheet.set_column(2, 2, 2)
            for ci in [3, 4, 5, 8]:
                worksheet.set_column(ci, ci, get_max_len(ci))
            worksheet.set_column(6, 6, 10.71)
            worksheet.set_column(7, 7, 14)
            for ci in [17, 18, 19]:
                worksheet.set_column(ci, ci, 1, fmt_texto)
            for ci in range(9, 16):
                worksheet.set_column(ci, ci, None, fmt_num)

        elif anexo_tipo == "B":
            worksheet.set_column(0, 0, 10)
            worksheet.set_column(1, 1, 1, fmt_texto)
            worksheet.set_column(2, 2, 2)
            for ci in [7, 8]:
                worksheet.set_column(ci, ci, get_max_len(ci))
            for ci in [20, 21, 22]:
                worksheet.set_column(ci, ci, 1, fmt_texto)
            for ci in range(10, 20):
                worksheet.set_column(ci, ci, None, fmt_num)

    output.seek(0)
    return output.getvalue()


def clasificar_tipo_ingreso(actividad):
    """Clasifica el tipo de ingreso según la actividad económica."""
    if not actividad:
        return "3"
    act = actividad.lower()
    if any(w in act for w in ['medico', 'abogado', 'contad', 'ingeniero', 'profesiones', 'auditor']):
        return "1"
    if any(w in act for w in ['servicio', 'mantenimiento', 'transporte', 'flete', 'taller']):
        return "2"
    if any(w in act for w in ['industria', 'fabricacion', 'manufactura']):
        return "4"
    if any(w in act for w in ['agro', 'ganaderia', 'agricultura']):
        return "5"
    if any(w in act for w in ['export']):
        return "7"
    return "3"


def limpiar_monto(monto_str):
    """Convierte un string de monto a float de forma segura."""
    try:
        s = str(monto_str).replace(' ', '').replace('$', '').strip()
        if not s:
            return 0.0
        if ',' in s and '.' in s:
            return float(s.replace(',', ''))
        if ',' in s and '.' not in s:
            return float(s.replace(',', '.'))
        return float(s)
    except (ValueError, AttributeError):
        return 0.0


def separar_zonas_pdf(pagina):
    """Separa zonas EMISOR y RECEPTOR usando coordenadas físicas."""
    ancho = pagina.width
    alto = pagina.height
    alto_header = alto * 0.60

    zona_receptor = pagina.crop((ancho * 0.47, 0, ancho, alto_header))
    texto_receptor = zona_receptor.extract_text(x_tolerance=4) or ""

    return texto_receptor


def extraer_uuid_limpio(texto):
    """Extrae y formatea UUID del código de generación DTE."""
    m = re.search(
        r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})',
        texto, re.I
    )
    if m:
        return m.group(1).upper()

    m2 = re.search(r'\b([A-F0-9]{32})\b', texto, re.I)
    if m2:
        raw = m2.group(1).upper()
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

    m3 = re.search(
        r'(?:Generaci[oO]n|C[oO]digo\s*de\s*Generaci[oO]n)\s*[:\s]*([A-F0-9-]{30,})',
        texto, re.I
    )
    if m3:
        raw = re.sub(r'[^A-F0-9]', '', m3.group(1).upper())
        if len(raw) >= 32:
            return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"

    return ""


# ═══════════════════════════════════════════════════════════════
# 🔧 MOTOR DE EXTRACCIÓN DTE
# ═══════════════════════════════════════════════════════════════

def extraer_dte_avanzado(f, cliente_activo):
    """Motor de extracción de DTE de Ventas (El Salvador)."""
    motor = "Nativo"

    try:
        if hasattr(f, 'seek'):
            f.seek(0)

        with pdfplumber.open(f) as pdf:
            pagina = pdf.pages[0]
            texto_prueba = pagina.extract_text() or ""
            ancho = pagina.width
            alto = pagina.height

            if len(texto_prueba.strip()) < 100:
                motor = "OCR"
                img_completa = pagina.to_image(resolution=300)
                texto_raw = pytesseract.image_to_string(img_completa.original, lang='spa')
                t_clean = re.sub(r'\s+', ' ', texto_raw)

                caja_receptor = (ancho * 0.47, 0, ancho, alto * 0.60)
                img_receptor = pagina.crop(caja_receptor).to_image(resolution=300)
                texto_receptor = pytesseract.image_to_string(img_receptor.original, lang='spa')

            else:
                texto_receptor = separar_zonas_pdf(pagina)
                texto_raw = texto_prueba
                t_clean = re.sub(r'\s+', ' ', texto_raw)

            # Validación anti-intrusos
            nit_emisor_limpio = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
            dui_emisor_limpio = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))

            patron_ids = (
                r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b"
                r"|\b\d{14}\b"
                r"|\b\d{8}-?\d{1}\b"
                r"|\b\d{9}\b"
            )
            nits_en_doc = [re.sub(r'[^0-9]', '', n) for n in re.findall(patron_ids, t_clean)]

            es_valido = (
                nit_emisor_limpio == "00000000000000"
                or nit_emisor_limpio in nits_en_doc
                or (dui_emisor_limpio and dui_emisor_limpio in nits_en_doc)
            )

            if not es_valido:
                return {"error": f"Documento ajeno al emisor activo ({cliente_activo.get('nombre', 'N/A')})."}

            # Extracción de receptor
            patron_nit_num = r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b|\b\d{8}-?\d{1}\b"

            nit_m = re.search(r"N\s*[I1l|]?\s*T\s*[:]?\s*([\d\-\s]{9,20})", texto_receptor, re.I)
            if not nit_m:
                nit_m = re.search(r"(" + patron_nit_num + r")", texto_receptor)
            nit = re.sub(r'[^0-9]', '', nit_m.group(1)) if nit_m else ""

            if "RECEPTOR" in texto_receptor.upper():
                bloque_nombre = texto_receptor.split("RECEPTOR", 1)[-1]
            elif "Generacion" in texto_receptor or "Generación" in texto_receptor:
                sep = "Generacion" if "Generacion" in texto_receptor else "Generación"
                bloque_nombre = texto_receptor.split(sep, 1)[-1]
                bloque_nombre = re.sub(r"^\s*\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}", "", bloque_nombre).strip()
            else:
                bloque_nombre = texto_receptor

            bloque_lineal = bloque_nombre.replace('\n', ' ')
            nom_m = re.search(
                r"(.*?)(?=\bN\s*[I|1l]\s*T\b|\bN\s*R\s*C\b|\bActividad\b|" + patron_nit_num + r")",
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
            tipo = tipo_m.group(1) if tipo_m else "01"

            ctrl_m = re.search(r"(DTE-\d{2}-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)", t_clean)
            ctrl = ctrl_m.group(1) if ctrl_m else ""

            gen = extraer_uuid_limpio(t_clean)

            sello_m = re.search(r"Sello de Recepci[oó]n\s*[:]?\s*([A-Z0-9]{20,})", t_clean, re.I)
            sello = sello_m.group(1) if sello_m else ""

            f_m = re.search(r"(\d{4}-\d{2}-\d{2})", t_clean)
            fecha = ""
            if f_m:
                partes = f_m.group(1).split('-')
                fecha = f"{partes[2]}/{partes[1]}/{partes[0]}"

            act_m = re.search(r"Actividad\s+econ[oó]mica\s*[:]?\s*(.*?)(?=\s+Direcci[oó]n)", t_clean, re.I)
            t_ing = clasificar_tipo_ingreso(act_m.group(1) if act_m else "")

            # Extracción de montos
            def buscar_montos(texto_buscar, tipo_dte, pdf_page_obj=None):
                n, e, g, i, t, x = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                encontrado = False
                iva_calculado = False

                if tipo_dte == "11":
                    exp_m = re.search(
                        r"(?:Total de Operaciones Afectas|Monto Total de la Operaci[oó]n)"
                        r"\s*[:]?\s*\$?\s*([\d,]+\.\d{2})",
                        texto_buscar, re.I
                    )
                    if exp_m:
                        x = limpiar_monto(exp_m.group(1))
                        t = x
                        encontrado = True

                else:
                    sum_m = re.search(
                        r"(?:Suma de Ventas|Ventas afectas):?\s*\$?\s*([\d,.]*)\s*([\d,.]*)\s*([\d,.]*)",
                        texto_buscar
                    )
                    if sum_m:
                        n = limpiar_monto(sum_m.group(1) or "0")
                        e = limpiar_monto(sum_m.group(2) or "0")
                        g = limpiar_monto(sum_m.group(3) or "0")
                        encontrado = True

                    iva_local_m = re.search(
                        r"(?:Impuesto al Valor Agregado 13%|IVA 13%|IVA)\s*[:]?\s*\$?\s*([\d,]+\.\d{2})",
                        texto_buscar, re.I
                    )
                    if iva_local_m:
                        i = limpiar_monto(iva_local_m.group(1))

                    tot_local_m = re.search(
                        r"(?:Total a Pagar|Monto Total)[\s$]*([\d,]+\.\d{2})",
                        texto_buscar, re.I
                    )
                    t = limpiar_monto(tot_local_m.group(1)) if tot_local_m else (g + i + e + n)

                if g == 0.0 and pdf_page_obj:
                    try:
                        w = pdf_page_obj.width
                        h = pdf_page_obj.height
                        caja_tot = (w * 0.40, h * 0.60, w, h)
                        img_tot = pdf_page_obj.crop(caja_tot).to_image(resolution=300)
                        texto_ocr_tot = pytesseract.image_to_string(img_tot.original, lang='spa')
                        t_ocr = re.sub(r'\s+', ' ', texto_ocr_tot)

                        m_g = re.search(
                            r"(?:Suma Total de Operaciones|Sub-?Total|Ventas Gravadas)"
                            r"[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                            t_ocr, re.I
                        )
                        if m_g:
                            g = limpiar_monto(m_g.group(1))
                            encontrado = True

                        if i == 0.0:
                            m_i_ocr = re.search(
                                r"(?:Agregado 13%|IVA 13%|IVA)"
                                r"[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                                t_ocr, re.I
                            )
                            if m_i_ocr:
                                i = limpiar_monto(m_i_ocr.group(1))
                            elif g > 0 and tipo_dte == "03":
                                i = round(g * 0.13, 2)
                                iva_calculado = True

                        if t == 0.0:
                            m_t_ocr = re.search(
                                r"(?:Total a Pagar|Monto Total)"
                                r"[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                                t_ocr, re.I
                            )
                            t = limpiar_monto(m_t_ocr.group(1)) if m_t_ocr else (g + i + e + n)

                    except Exception:
                        pass

                return n, e, g, i, t, x, encontrado, iva_calculado

            nos, exe, gra, iva, tot, exp_serv, exito_ventas, flag_iva = buscar_montos(
                t_clean, tipo, pagina
            )

            if not exito_ventas and len(pdf.pages) > 1:
                pagina2 = pdf.pages[1]
                if "OCR" in motor:
                    t_p2 = re.sub(
                        r'\s+', ' ',
                        pytesseract.image_to_string(pagina2.to_image(resolution=300).original, lang='spa')
                    )
                else:
                    t_p2 = re.sub(r'\s+', ' ', pagina2.extract_text() or "")

                nos2, exe2, gra2, iva2, tot2, x2, ok2, iva_f2 = buscar_montos(t_p2, tipo, pagina2)
                if ok2:
                    nos, exe, gra, iva, tot, exp_serv, flag_iva = nos2, exe2, gra2, iva2, tot2, x2, iva_f2

            return {
                "fecha": fecha, "nit": nit, "nom": nombre, "tipo": tipo,
                "ctrl": ctrl, "gen": gen, "sello": sello,
                "nos": nos, "exe": exe, "gra": gra, "iva": iva,
                "exp_serv": exp_serv, "tot": tot, "t_ing": t_ing,
                "motor": motor, "iva_calculado": flag_iva
            }

    except Exception as err:
        return {"error": f"Error de lectura: {str(err)}"}


# ═══════════════════════════════════════════════════════════════
# 📱 MODAL DE DESCARGA
# ═══════════════════════════════════════════════════════════════

@st.dialog("Seguro de Calidad de Datos")
def ventana_descarga(df_resultados, tipo_anexo, nombre_archivo):
    st.write(
        "Recuerda revisar las alertas de **campos vacíos**, **rechazados** o "
        "**cálculos manuales** antes de enviar a Hacienda."
    )
    st.download_button(
        label=f"Confirmar y Descargar Anexo {tipo_anexo}",
        data=to_excel_hacienda(df_resultados, tipo_anexo),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )


# ═══════════════════════════════════════════════════════════════
# 📱 HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:Courier New,monospace; color:#666D57; "
    "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("Extractor DTE - Ventas")

st.markdown(f"""
<div class="alerta-activo">
    <strong>EMISOR ACTUAL:</strong>
    {cliente.get('nombre', 'N/A')} (NIT: {cliente.get('nit', 'N/A')})
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 🔄 INICIALIZACIÓN DE ESTADO
# ═══════════════════════════════════════════════════════════════

if 'uploader_key_v' not in st.session_state:
    st.session_state.uploader_key_v = str(time.time())
if 'db_ventas' not in st.session_state:
    st.session_state.db_ventas = pd.DataFrame()
if 'archivos_procesados_v' not in st.session_state:
    st.session_state.archivos_procesados_v = set()
if 'reporte_ventas' not in st.session_state:
    st.session_state.reporte_ventas = None

# ═══════════════════════════════════════════════════════════════
# 📂 SIDEBAR - CARGA Y PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("Carga de Datos")
    st.caption(f"Cliente: {cliente.get('nombre', 'N/A')}")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra tus PDFs aquí",
        type="pdf",
        accept_multiple_files=True,
        key=st.session_state.uploader_key_v
    )

    if archivos and st.button("Procesar Documentos", type="primary", use_container_width=True):

        extracted = []
        duplicados_gen = []
        vacios_deteccion = []
        iva_calculado_files = []
        archivos_rechazados = []

        nuevos = [f for f in archivos if f.name not in st.session_state.archivos_procesados_v]

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
                        f"Procesando: **{idx+1}** de **{total}** "
                        f"| Restante: {m:02d}:{s:02d}",
                        unsafe_allow_html=True
                    )
                else:
                    txt_progreso.markdown(f"Procesando: **1** de **{total}** | Calculando...")

                res = extraer_dte_avanzado(f, cliente)
                st.session_state.archivos_procesados_v.add(f.name)

                if "error" in res:
                    archivos_rechazados.append(f"{f.name} — {res['error']}")

                else:
                    tot_val = res.get('tot', 0.0)
                    try:
                        tot_float = float(tot_val)
                    except (TypeError, ValueError):
                        tot_float = 0.0

                    if res['tipo'] in ["01", "11"]:
                        campos = [res['fecha'], res['ctrl'], tot_float]
                        incompleto = (
                            "" in [res['fecha'], res['ctrl']]
                            or tot_float == 0.0
                        )
                    else:
                        campos = [res['fecha'], res['nit'], res['nom'], res['ctrl'], tot_float]
                        incompleto = (
                            "" in [res['fecha'], res['nit'], res['nom'], res['ctrl']]
                            or tot_float == 0.0
                        )

                    if incompleto:
                        vacios_deteccion.append(f.name)

                    if res.get('iva_calculado'):
                        iva_calculado_files.append(f.name)

                    codigo_gen = res.get('gen', '')
                    dup_mem = (
                        not st.session_state.db_ventas.empty
                        and codigo_gen != ""
                        and (st.session_state.db_ventas['gen'] == codigo_gen).any()
                    )
                    dup_lote = (
                        codigo_gen != ""
                        and any(d.get('gen') == codigo_gen for d in extracted)
                    )

                    if dup_mem or dup_lote:
                        duplicados_gen.append(f.name)
                    else:
                        res["archivo"] = f.name
                        extracted.append(res)

                bar.progress((idx + 1) / total)

            txt_progreso.success(f"{total} archivos procesados correctamente.")

            st.session_state.reporte_ventas = {
                "rechazados": archivos_rechazados,
                "vacios": vacios_deteccion,
                "duplicados_gen": duplicados_gen,
                "iva_calc": iva_calculado_files
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

    st.divider()

    if st.button("Limpiar Memoria y Reiniciar", type="secondary", use_container_width=True):
        for var in ['db_ventas', 'archivos_procesados_v', 'reporte_ventas']:
            st.session_state.pop(var, None)
        st.session_state.uploader_key_v = str(time.time())
        gc.collect()
        st.rerun()

    if not st.session_state.db_ventas.empty:
        st.divider()
        st.caption(f"Registros en memoria: {len(st.session_state.db_ventas)}")

# ═══════════════════════════════════════════════════════════════
# 📊 REPORTE DE EXTRACCIÓN
# ═══════════════════════════════════════════════════════════════

if st.session_state.reporte_ventas:
    rep = st.session_state.reporte_ventas
    st.markdown("### 📋 Reporte de Extracción")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if rep.get("rechazados"):
            st.error(f"**{len(rep['rechazados'])} Rechazados** (No pertenecen).")
            with st.expander("Ver lista"):
                st.markdown(
                    f'<div class="scroll-list">'
                    + "".join([f"• {a}<br>" for a in rep["rechazados"]])
                    + '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("**0 Rechazados.**")

    with c2:
        if rep.get("vacios"):
            st.error(f"**{len(rep['vacios'])} Incompletos** (Faltan datos).")
            with st.expander("Ver lista"):
                st.markdown(
                    f'<div class="scroll-list">'
                    + "".join([f"• {a}<br>" for a in rep["vacios"]])
                    + '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("**0 Incompletos.**")

    with c3:
        if rep.get("duplicados_gen"):
            st.error(f"**{len(rep['duplicados_gen'])} Omitidos** (Duplicados).")
            with st.expander("Ver lista"):
                st.markdown(
                    f'<div class="scroll-list">'
                    + "".join([f"• {a}<br>" for a in rep["duplicados_gen"]])
                    + '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("**0 Omitidos.**")

    with c4:
        if rep.get("iva_calc"):
            st.info(f"**{len(rep['iva_calc'])} IVA Calc.** (Al 13%).")
            with st.expander("Ver lista"):
                st.markdown(
                    f'<div class="scroll-list">'
                    + "".join([f"• {a}<br>" for a in rep["iva_calc"]])
                    + '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("**0 IVA Calc.**")

    st.divider()

# ═══════════════════════════════════════════════════════════════
# 📊 TABLAS DE RESULTADOS
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_ventas.empty:
    df = st.session_state.db_ventas

    tab1, tab2, tab3 = st.tabs([
        "F-07 Ventas a Contribuyentes (CCF)",
        "F-07 Ventas Consumidor (Facturas)",
        "Auditoría Total"
    ])

    with tab1:
        df_a = df[df["tipo"].isin(["03", "05", "06"])].copy()

        if df_a.empty:
            st.info("No hay CCF procesados aún. Carga DTE tipo 03, 05 o 06.")
        else:
            df_a["clase"] = "4"
            df_a["ctrl_vacio"] = ""
            df_a["v_terc"] = 0.00
            df_a["d_terc"] = 0.00
            df_a["dui"] = ""
            df_a["t_op"] = "1"
            df_a["n_anexo"] = "1"

            cols = [
                "fecha", "clase", "tipo", "ctrl", "sello", "gen",
                "ctrl_vacio", "nit", "nom", "exe", "nos", "gra",
                "iva", "v_terc", "d_terc", "tot", "dui", "t_op", "t_ing", "n_anexo"
            ]
            res_a = df_a[cols].sort_values(by="ctrl").copy()
            res_a.columns = [
                "1.Fecha", "2.Clase", "3.Tipo", "4.Num Control", "5.Sello",
                "6.Generacion", "7.Num Control 2", "8.NIT/NRC", "9.Razon Social",
                "10.Exentas", "11.No Sujetas", "12.Gravadas", "13.Debito",
                "14.V. Terceros", "15.D. Terceros", "16.Total",
                "17.DUI", "18.Tipo Op", "19.Tipo Ing", "20.Anexo"
            ]

            cols_num = ["10.Exentas", "11.No Sujetas", "12.Gravadas", "13.Debito",
                        "14.V. Terceros", "15.D. Terceros", "16.Total"]

            st.dataframe(
                res_a.style.format({c: "{:.2f}" for c in cols_num}),
                hide_index=True,
                use_container_width=True
            )

            col_btn1, col_btn2 = st.columns([2, 1])
            with col_btn1:
                st.info(f"Total registros CCF: **{len(res_a)}**")
            with col_btn2:
                if st.button("Preparar Excel CCF", type="primary", use_container_width=True):
                    ventana_descarga(res_a, "A", "F07_Ventas_Contribuyentes.xlsx")

    with tab2:
        df_b = df[df["tipo"].isin(["01", "11"])].copy()

        if df_b.empty:
            st.info("No hay Facturas procesadas aún. Carga DTE tipo 01 o 11.")
        else:
            df_b["clase"] = "4"
            df_b["res"] = "N/A"
            df_b["ser"] = "N/A"
            df_b["int"] = "N/A"
            df_b["maq"] = ""
            df_b["pre_ctrl"] = "N/A"
            df_b["vtas_int_exe_no_suj"] = 0.00
            df_b["n_anexo"] = "2"
            df_b["exp_ca"] = 0.00
            df_b["exp_fca"] = 0.00
            df_b["v_zf"] = 0.00
            df_b["v_ter"] = 0.00
            df_b["t_op"] = "1"

            if "exp_serv" not in df_b.columns:
                df_b["exp_serv"] = 0.00

            cols = [
                "fecha", "clase", "tipo", "res", "ser", "int", "pre_ctrl",
                "ctrl", "gen", "maq", "exe", "nos", "vtas_int_exe_no_suj",
                "gra", "exp_ca", "exp_fca", "exp_serv", "v_zf", "v_ter",
                "tot", "t_op", "t_ing", "n_anexo"
            ]
            res_b = df_b[cols].sort_values(by="ctrl").copy()
            res_b.columns = [
                "1.Fecha", "2.Clase", "3.Tipo", "4.Resolucion", "5.Serie",
                "6.Interno", "7.Pre-Control", "8.Num Control", "9.Generacion",
                "10.Maquina", "11.Exentas", "12.No Sujetas",
                "13.Vtas Int Exe No Suj Prop", "14.Gravadas",
                "15.Exp CA", "16.Exp Fuera CA", "17.Exp Serv",
                "18.ZF y DPA", "19.V. Terceros", "20.Total",
                "21.Tipo Op", "22.Tipo Ing", "23.Anexo"
            ]

            cols_num_b = [
                "11.Exentas", "12.No Sujetas", "13.Vtas Int Exe No Suj Prop",
                "14.Gravadas", "15.Exp CA", "16.Exp Fuera CA", "17.Exp Serv",
                "18.ZF y DPA", "19.V. Terceros", "20.Total"
            ]

            st.dataframe(
                res_b.style.format({c: "{:.2f}" for c in cols_num_b}),
                hide_index=True,
                use_container_width=True
            )

            col_btn3, col_btn4 = st.columns([2, 1])
            with col_btn3:
                st.info(f"Total registros Facturas: **{len(res_b)}**")
            with col_btn4:
                if st.button("Preparar Excel Facturas", type="primary", use_container_width=True):
                    ventana_descarga(res_b, "B", "F07_Ventas_Consumidor.xlsx")

    with tab3:
        col_aud1, col_aud2, col_aud3 = st.columns(3)
        with col_aud1:
            st.metric("Total Registros", len(df))
        with col_aud2:
            tot_general = df['tot'].apply(lambda x: float(x) if x else 0.0).sum()
            st.metric("Total Facturado", f"${tot_general:,.2f}")
        with col_aud3:
            tipos_unicos = df['tipo'].nunique()
            st.metric("Tipos de DTE", tipos_unicos)

        st.divider()

        st.dataframe(df, use_container_width=True)
