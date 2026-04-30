import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import pytesseract
import json
import os
import gc
import platform
from io import BytesIO

# ═══════════════════════════════════════════════════════════════
# 🔐 VERIFICACIÓN DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("⚠️ Debes seleccionar un Cliente Activo antes de extraer Retenciones.")
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
        background-color: #8C52FF !important;
        border: 1px solid #5E17EB !important;
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
        background-color: #5E17EB !important;
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
        color: #CB6CE6;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #8C52FF !important;
        border-bottom-color: #8C52FF !important;
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
        border-left: 4px solid #8C52FF;
        background-color: #111111;
        color: white;
        margin-bottom: 15px;
        font-size: 14px;
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 📋 CONSTANTES
# ═══════════════════════════════════════════════════════════════
ARCHIVO_PROVEEDORES = "data/proveedores.json"
CONTRAPARTE_NUEVA = "CONTRAPARTE NUEVA"

# ═══════════════════════════════════════════════════════════════
# 💾 BASE DE DATOS DE PROVEEDORES
# ═══════════════════════════════════════════════════════════════

def cargar_proveedores_json():
    """Carga el directorio de proveedores con migración automática."""
    if not os.path.exists(ARCHIVO_PROVEEDORES):
        return {}
    try:
        with open(ARCHIVO_PROVEEDORES, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = {"nombre": v, "nrc": ""}
        return data
    except Exception:
        return {}


def obtener_nombre_proveedor(prov_db, nit):
    """Extrae el nombre de forma segura del directorio."""
    entrada = prov_db.get(nit)
    if entrada is None:
        return None
    if isinstance(entrada, dict):
        return entrada.get("nombre", "")
    if isinstance(entrada, str):
        return entrada
    return None


def guardar_proveedor_rapido(nit, nombre):
    """Guarda en formato dict correcto."""
    if not os.path.exists("data"):
        os.makedirs("data")
    db = cargar_proveedores_json()
    nrc_existente = db.get(nit, {}).get("nrc", "") if isinstance(db.get(nit), dict) else ""
    db[nit] = {"nombre": nombre.strip().upper(), "nrc": nrc_existente}
    try:
        with open(ARCHIVO_PROVEEDORES, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as err:
        st.error(f"Error al guardar proveedor: {err}")

# ═══════════════════════════════════════════════════════════════
# 📊 EXPORTACIÓN EXCEL HACIENDA F-14
# ═══════════════════════════════════════════════════════════════

def to_excel_hacienda_retenciones(df):
    """Exporta al formato exacto de Hacienda El Salvador para F-14 Retenciones."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Retenciones_F14')
        workbook = writer.book
        worksheet = writer.sheets['Retenciones_F14']

        fmt_texto = workbook.add_format({'num_format': '@'})
        fmt_num_hacienda = workbook.add_format({'num_format': '0.00', 'align': 'left'})

        worksheet.set_column(0, 0, 15, fmt_texto)
        worksheet.set_column(1, 1, 12, fmt_texto)
        worksheet.set_column(2, 2, 5, fmt_texto)
        worksheet.set_column(3, 3, 42, fmt_texto)
        worksheet.set_column(4, 4, 38, fmt_texto)
        worksheet.set_column(5, 6, 12, fmt_num_hacienda)
        worksheet.set_column(7, 7, 12, fmt_texto)
        worksheet.set_column(8, 8, 5, fmt_texto)

    output.seek(0)
    return output.getvalue()

# ═══════════════════════════════════════════════════════════════
# 🔧 FUNCIONES UTILITARIAS
# ═══════════════════════════════════════════════════════════════

def limpiar_monto(monto_str):
    """Convierte string de monto a float de forma segura."""
    try:
        s = re.sub(r'[^\d.,]', '', str(monto_str)).strip()
        if not s:
            return 0.0
        if ',' in s and '.' in s:
            return round(float(s.replace(',', '')), 2)
        elif ',' in s:
            return round(float(s.replace(',', '.')), 2)
        return round(float(s), 2)
    except (ValueError, AttributeError):
        return 0.0


def extraer_y_formatear_fecha(texto):
    """Extractor de fechas en cascada."""
    meses = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }

    for m in re.finditer(
        r"\b(\d{1,2})\s*(?:de\s*|/|-)?\s*([a-zA-Z]{3,})\s*(?:de\s*|/|-)?\s*(\d{4})\b",
        texto, re.I
    ):
        d, mes_str, y = m.groups()
        if int(y) < 2023:
            continue
        for key, value in meses.items():
            if mes_str.upper().startswith(key):
                return f"{int(d):02d}/{value}/{y}"

    for m in re.finditer(
        r"\b(\d{1,4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,4})\b",
        texto
    ):
        p1, p2, p3 = m.groups()
        y = d = mo = None

        if len(p1) == 4:
            y, mo, d = p1, p2, p3
        elif len(p3) in [2, 4]:
            d, mo, y = p1, p2, p3
            if len(y) == 2:
                y = f"20{y}"
            if int(mo) > 12 and int(d) <= 12:
                mo, d = d, mo
        else:
            continue

        try:
            if int(y) < 2023 or int(mo) > 12 or int(d) > 31:
                continue
            return f"{int(d):02d}/{int(mo):02d}/{y}"
        except ValueError:
            continue

    nums = re.findall(r"\b\d{1,4}\b", texto)
    for idx, n in enumerate(nums):
        if len(n) == 4 and 2023 <= int(n) <= 2030:
            vecinos = nums[max(0, idx-4):idx] + nums[idx+1:idx+5]
            dm = [v for v in vecinos if len(v) in [1, 2] and 0 < int(v) <= 31]
            if len(dm) >= 2:
                n1, n2 = dm[0], dm[1]
                if int(n1) > 12:
                    d, mo = n1, n2
                elif int(n2) > 12:
                    d, mo = n2, n1
                else:
                    d, mo = n1, n2
                return f"{int(d):02d}/{int(mo):02d}/{n}"

    return ""


def formatear_uuid(raw_str):
    """Convierte un UUID sin guiones al formato estándar con guiones."""
    limpio = re.sub(r'[^A-F0-9]', '', raw_str.upper())
    if len(limpio) >= 32:
        return f"{limpio[:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:32]}"
    return raw_str.upper()

# ═══════════════════════════════════════════════════════════════
# 🔧 MOTOR DE EXTRACCIÓN DTE-07
# ═══════════════════════════════════════════════════════════════

def extraer_retenciones(file_bytes, cliente_activo, prov_cache=None):
    """Motor de extracción de Comprobantes de Retención DTE-07 (El Salvador)."""
    motor = "Nativo"

    try:
        texto_completo = ""

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                texto_pagina = page.extract_text()

                if not texto_pagina or len(texto_pagina.strip()) < 50:
                    motor = "OCR"
                    img = page.to_image(resolution=300)
                    texto_pagina = pytesseract.image_to_string(img.original, lang='spa')

                texto_completo += (texto_pagina or "") + "\n"

        if len(texto_completo.strip()) < 30:
            return {"error": "PDF sin contenido legible."}

        t_clean = re.sub(r'\s+', ' ', texto_completo)
        t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
        tipo = "01"
        ctrl = ""

        if m_ctrl:
            ctrl = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo:
                tipo = m_tipo.group(1)

        if not ctrl:
            return {"error_tipo": "No se detectó un Número de Control DTE válido."}
        if tipo != "07":
            return {"error_tipo": f"El documento es DTE-{tipo}. Solo se admiten DTE-07 (Retención)."}

        nit_cliente = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
        texto_nums = re.sub(r'[^0-9]', '', t_clean)

        es_valido = (
            nit_cliente == "00000000000000"
            or (len(nit_cliente) >= 9 and nit_cliente in texto_nums)
        )
        if not es_valido:
            return {"error_intruso": "Este documento no le pertenece al cliente activo."}

        gen = ""
        m_gen_etiqueta = re.search(
            r"(?:C[OO]DIGO\s*DE\s*GENERACI[OO]N|C[OO]D\.\s*GENERACI[OO]N)"
            r"[^\w]*([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
            texto_completo, re.I
        )
        if m_gen_etiqueta:
            gen = formatear_uuid(m_gen_etiqueta.group(1))
        else:
            uuids_encontrados = re.findall(
                r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
                t_no_spaces
            )
            for u in uuids_encontrados:
                if not re.search(r"SELLO.*?RECEPC", t_no_spaces[:t_no_spaces.find(u)] if u in t_no_spaces else ""):
                    gen = formatear_uuid(u)
                    break
            if not gen and uuids_encontrados:
                gen = formatear_uuid(uuids_encontrados[0])

        sello = ""
        m_sello = re.search(
            r"Sello\s*de\s*Recepci[oo]n\s*[:]?\s*([A-Z0-9]{38,45})",
            t_clean, re.I
        )
        if m_sello:
            sello = m_sello.group(1)[:40].strip()
        else:
            sellos_huerfanos = re.findall(r"(202[3-9][A-Z0-9]{36})", t_no_spaces)
            if sellos_huerfanos:
                sello = sellos_huerfanos[0][:40]

        fecha = extraer_y_formatear_fecha(t_clean)

        nit_contraparte = ""
        nom_contraparte = CONTRAPARTE_NUEVA
        es_nuevo = True

        patron_ids = (
            r"\b\d{4}\s*-\s*\d{6}\s*-\s*\d{3}\s*-\s*\d{1}\b"
            r"|\b\d{14}\b"
            r"|\b\d{8}\s*-\s*\d{1}\b"
            r"|\b\d{9}\b"
        )
        nits_raw = re.findall(patron_ids, texto_completo)
        nits_limpios = list(dict.fromkeys([re.sub(r'[^0-9]', '', n) for n in nits_raw]))

        prov_db = prov_cache if prov_cache is not None else cargar_proveedores_json()

        for n in nits_limpios:
            if n == nit_cliente:
                continue
            nombre_encontrado = obtener_nombre_proveedor(prov_db, n)
            if nombre_encontrado is not None:
                nit_contraparte = n
                nom_contraparte = nombre_encontrado
                es_nuevo = False
                break

        if not nit_contraparte:
            for n in nits_limpios:
                if n != nit_cliente:
                    nit_contraparte = n
                    break

        if es_nuevo and nit_contraparte:
            nom_contraparte = CONTRAPARTE_NUEVA

        monto_sujeto = 0.0
        monto_retenido = 0.0
        ret_calculada = False

        m_sujeto = re.search(
            r"(?:Total\s+Monto\s+Sujeto|Monto\s+Sujeto\s+a\s+Retenci[oo]n|"
            r"Monto\s+Sujeto|Sujeto\s+a\s+Retenci[oo]n|Base\s+Imponible)"
            r"[^\d]*?(\d{1,5}(?:[.,]\d{3})*[.,]\d{2})",
            t_clean, re.I
        )
        if m_sujeto:
            monto_sujeto = limpiar_monto(m_sujeto.group(1))

        m_retenido = re.search(
            r"(?:Total\s+IVA(?:\s+1%)?\s+Retenido|IVA\s+Retenido|"
            r"Retenci[oo]n(?:\s+del)?\s+1%|Impuesto\s+Retenido)"
            r"[^\d]*?(\d{1,5}(?:[.,]\d{3})*[.,]\d{2})",
            t_clean, re.I
        )
        if m_retenido:
            monto_retenido = limpiar_monto(m_retenido.group(1))

        es_logico = (
            monto_sujeto > 0
            and monto_retenido > 0
            and abs(round(monto_sujeto * 0.01, 2) - round(monto_retenido, 2)) <= 0.05
        )

        if not es_logico:
            montos_raw = re.findall(
                r"(?:US\$?|\$)?\s*(\d{1,5}(?:[.,]\d{3})*[.,]\d{2})",
                t_clean
            )
            valores = sorted(
                list(set(limpiar_monto(m) for m in montos_raw)),
                reverse=True
            )
            valores = [v for v in valores if v > 0.01]

            for val_s in valores:
                if es_logico:
                    break
                for val_r in valores:
                    if val_r >= val_s:
                        continue
                    if abs(round(val_s * 0.01, 2) - round(val_r, 2)) <= 0.05:
                        monto_sujeto = val_s
                        monto_retenido = val_r
                        es_logico = True
                        break

        if not es_logico:
            if monto_retenido > 0 and monto_sujeto == 0.0:
                monto_sujeto = round(monto_retenido / 0.01, 2)
                ret_calculada = True
            elif monto_sujeto > 0 and monto_retenido == 0.0:
                monto_retenido = round(monto_sujeto * 0.01, 2)
                ret_calculada = True

        return {
            "fecha": fecha,
            "nit_contraparte": nit_contraparte,
            "nom_contraparte": nom_contraparte,
            "tipo": tipo,
            "ctrl": ctrl,
            "gen": gen,
            "sello": sello,
            "monto_sujeto": monto_sujeto,
            "monto_retenido": monto_retenido,
            "estado": "OK",
            "es_nuevo": es_nuevo,
            "motor": motor,
            "ret_calc": ret_calculada
        }

    except Exception as err:
        return {"error": str(err)}

# ═══════════════════════════════════════════════════════════════
# 📱 MODAL DE DESCARGA
# ═══════════════════════════════════════════════════════════════

@st.dialog("Seguro de Calidad de Retenciones")
def ventana_descarga_retenciones(df_resultados, nombre_archivo):
    st.write(
        "Asegúrate de haber revisado los montos extraídos antes de descargar. "
        "El Excel generado cumple exactamente con las especificaciones de Hacienda "
        "para carga masiva del F-14 (sin encabezados)."
    )
    st.download_button(
        label="Confirmar y Descargar Anexo F-14",
        data=to_excel_hacienda_retenciones(df_resultados),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True
    )

# ═══════════════════════════════════════════════════════════════
# 📱 HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:Courier New,monospace; color:#5E17EB; "
    "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("Extractor DTE - Retenciones (DTE-07)")

st.markdown(f"""
<div class="alerta-activo">
    <strong>CLIENTE ACTUAL:</strong>
    {cliente.get('nombre', 'N/A')} (NIT: {cliente.get('nit', 'N/A')})
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 🔄 INICIALIZACIÓN DE ESTADO
# ═══════════════════════════════════════════════════════════════

if 'ret_uploader_key' not in st.session_state:
    st.session_state.ret_uploader_key = str(time.time())
if 'db_retenciones' not in st.session_state:
    st.session_state.db_retenciones = pd.DataFrame()
if 'archivos_ret' not in st.session_state:
    st.session_state.archivos_ret = set()
if 'reporte_retenciones' not in st.session_state:
    st.session_state.reporte_retenciones = None

# ═══════════════════════════════════════════════════════════════
# 📂 SIDEBAR - CARGA Y PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("Carga de Retenciones")
    st.caption(f"Cliente: {cliente.get('nombre', 'N/A')}")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra Comprobantes de Retención (DTE-07)",
        type="pdf",
        accept_multiple_files=True,
        key=st.session_state.ret_uploader_key
    )

    if archivos and st.button("Procesar Retenciones", type="primary", use_container_width=True):

        extracted = []
        vacios_deteccion = []
        duplicados = []
        intrusos = []
        invalidos = []
        calculados = []
        nuevos_proveedores = {}

        nuevos = [f for f in archivos if f.name not in st.session_state.archivos_ret]

        if nuevos:
            bar = st.progress(0)
            txt_progreso = st.empty()
            t_inicio = time.time()
            total = len(nuevos)

            prov_cache = cargar_proveedores_json()

            for idx, f in enumerate(nuevos):

                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                if idx > 0:
                    elapsed = time.time() - t_inicio
                    eta = int((elapsed / idx) * (total - idx))
                    m_t, s = divmod(eta, 60)
                    txt_progreso.markdown(
                        f"Procesando: **{idx+1}** de **{total}** "
                        f"| Restante: {m_t:02d}:{s:02d}"
                    )
                else:
                    txt_progreso.markdown(f"Procesando: **1** de **{total}** | Calculando...")

                file_bytes = f.read()

                res = extraer_retenciones(file_bytes, cliente, prov_cache)

                codigo_gen = res.get('gen', '')
                dup_memoria = (
                    not st.session_state.db_retenciones.empty
                    and codigo_gen != ""
                    and (st.session_state.db_retenciones['gen'] == codigo_gen).any()
                )
                dup_lote = (
                    codigo_gen != ""
                    and any(d.get('gen') == codigo_gen for d in extracted)
                )

                st.session_state.archivos_ret.add(f.name)

                if "error_intruso" in res:
                    intrusos.append(f.name)

                elif "error_tipo" in res:
                    invalidos.append(f.name)

                elif dup_memoria or dup_lote:
                    duplicados.append(f.name)

                elif "error" in res:
                    invalidos.append(f"{f.name} ({res['error'][:50]})")

                else:
                    fecha_str = str(res.get('fecha', '')).strip()

                    try:
                        monto_ret = float(res.get('monto_retenido', 0.0))
                        monto_suj = float(res.get('monto_sujeto', 0.0))
                    except (TypeError, ValueError):
                        monto_ret = monto_suj = 0.0

                    incompleto = (
                        monto_ret == 0.0
                        or monto_suj == 0.0
                        or not res.get('gen')
                        or not res.get('sello')
                        or not fecha_str
                    )
                    if incompleto:
                        vacios_deteccion.append(f.name)

                    if res.get("es_nuevo") and res.get("nit_contraparte"):
                        nit_np = res["nit_contraparte"]
                        nom_np = res["nom_contraparte"]
                        nuevos_proveedores[nit_np] = nom_np
                        prov_cache[nit_np] = {"nombre": nom_np, "nrc": ""}

                    if res.get("ret_calc"):
                        calculados.append(f.name)

                    res["archivo"] = f.name
                    extracted.append(res)

                bar.progress((idx + 1) / total)

            txt_progreso.success(f"{total} retenciones procesadas correctamente.")

            st.session_state.reporte_retenciones = {
                "intrusos": intrusos,
                "invalidos": invalidos,
                "duplicados": duplicados,
                "vacios": vacios_deteccion,
                "nuevos_proveedores": nuevos_proveedores,
                "calculados": calculados
            }

            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_retenciones.empty:
                    st.session_state.db_retenciones = new_df
                else:
                    st.session_state.db_retenciones = pd.concat(
                        [st.session_state.db_retenciones, new_df], ignore_index=True
                    )

            gc.collect()
            time.sleep(0.3)
            st.rerun()

    st.divider()

    if st.button("Limpiar Memoria Retenciones", type="secondary", use_container_width=True):
        for key in ['db_retenciones', 'archivos_ret', 'reporte_retenciones']:
            st.session_state.pop(key, None)
        st.session_state.ret_uploader_key = str(time.time())
        gc.collect()
        st.rerun()

    if not st.session_state.db_retenciones.empty:
        st.divider()
        st.caption(f"Registros: {len(st.session_state.db_retenciones)}")

# ═══════════════════════════════════════════════════════════════
# 📊 DASHBOARD DE ALERTAS
# ═══════════════════════════════════════════════════════════════

if st.session_state.reporte_retenciones:
    rep = st.session_state.reporte_retenciones
    st.markdown("### 🚨 Alertas de Procesamiento")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        n = len(rep.get("invalidos", []))
        if n:
            st.error(f"**{n} Ignorados** (No son DTE-07).")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in rep["invalidos"])
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 Ignorados.**")

    with c2:
        n = len(rep.get("vacios", []))
        if n:
            st.error(f"**{n} Incompletos** (Falta Fecha, Sello o Montos).")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in rep["vacios"])
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 Incompletos.**")

    with c3:
        n = len(rep.get("duplicados", []))
        if n:
            st.error(f"**{n} Omitidos** (Duplicados).")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in rep["duplicados"])
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 Omitidos.**")

    with c4:
        n = len(rep.get("calculados", []))
        if n:
            st.info(f"**{n} Calc. (1%)** (Forzado matemático).")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in rep["calculados"])
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 Calc. (1%)** (Lectura directa).")

    st.divider()

    if rep.get("nuevos_proveedores"):
        st.markdown("### Guardado Rápido de Contrapartes")
        st.info(
            "Estas empresas o personas aparecen como nuevas en este lote. "
            "Escribe su nombre oficial para que el sistema lo memorice."
        )

        for nit, nombre_sug in list(rep["nuevos_proveedores"].items()):

            valor_inicial = "" if nombre_sug == CONTRAPARTE_NUEVA else nombre_sug

            col1, col2, col3 = st.columns([2, 5, 2])

            with col1:
                st.text_input(
                    "NIT",
                    value=nit,
                    disabled=True,
                    key=f"lbl_ret_{nit}"
                )
            with col2:
                nuevo_nom = st.text_input(
                    "Nombre Oficial",
                    value=valor_inicial,
                    placeholder="Empresa Proveedora S.A. de C.V.",
                    key=f"nom_ret_{nit}"
                )
            with col3:
                st.write("")
                if st.button(
                    "Guardar",
                    key=f"btn_ret_{nit}",
                    type="primary",
                    use_container_width=True
                ):
                    if nuevo_nom.strip():
                        guardar_proveedor_rapido(nit, nuevo_nom)

                        df_actual = st.session_state.db_retenciones
                        mask = df_actual['nit_contraparte'] == nit
                        df_actual.loc[mask, 'nom_contraparte'] = nuevo_nom.strip().upper()
                        st.session_state.db_retenciones = df_actual

                        del st.session_state.reporte_retenciones["nuevos_proveedores"][nit]
                        st.success(f"Guardado: {nuevo_nom.upper()}")
                        time.sleep(0.8)
                        st.rerun()
                    else:
                        st.warning("Escribe un nombre antes de guardar.")

        st.divider()

# ═══════════════════════════════════════════════════════════════
# 📊 TABLAS DE RESULTADOS
# ═══════════════════════════════════════════════════════════════

if not st.session_state.db_retenciones.empty:
    df = st.session_state.db_retenciones.copy()

    tab1, tab2 = st.tabs([
        "Retenciones F-14 (Vista Previa)",
        "Auditoría Total"
    ])

    with tab1:
        st.info(
            "La columna Nombre es solo visual para tu auditoría. "
            "Al descargar el Excel para Hacienda, se eliminará y no llevará "
            "encabezados, tal como exige el manual F-14."
        )

        def asignar_nit(x):
            x = str(x)
            return x if len(x) == 14 else ""

        def asignar_dui(x):
            x = str(x)
            return x if len(x) == 9 else ""

        df_hacienda = pd.DataFrame({
            "A. NIT Agente": df["nit_contraparte"].apply(asignar_nit),
            "B. Fecha Emisión": df["fecha"],
            "C. Tipo Documento": df["tipo"],
            "D. Serie (Sello)": df["sello"],
            "E. Num Doc (UUID)": df["gen"],
            "F. Monto Sujeto": pd.to_numeric(df["monto_sujeto"], errors='coerce').fillna(0.0),
            "G. Monto Retención": pd.to_numeric(df["monto_retenido"], errors='coerce').fillna(0.0),
            "H. DUI Agente": df["nit_contraparte"].apply(asignar_dui),
            "I. Número Anexo": "7"
        })

        df_vista = df_hacienda.copy()
        df_vista["(Visual) Nombre"] = df["nom_contraparte"]

        cols_num = ["F. Monto Sujeto", "G. Monto Retención"]

        st.dataframe(
            df_vista.style.format({c: "{:.2f}" for c in cols_num}),
            hide_index=True,
            use_container_width=True
        )

        col_k1, col_k2, col_k3 = st.columns(3)
        with col_k1:
            st.metric("Total Registros", len(df_hacienda))
        with col_k2:
            st.metric(
                "Total Monto Sujeto",
                f"${df_hacienda['F. Monto Sujeto'].sum():,.2f}"
            )
        with col_k3:
            st.metric(
                "Total Retenido (1%)",
                f"${df_hacienda['G. Monto Retención'].sum():,.2f}"
            )

        st.write("")
        if st.button("Generar Excel para F-14", type="primary", use_container_width=True):
            ventana_descarga_retenciones(df_hacienda, "F14_Retenciones.xlsx")

    with tab2:
        col_a1, col_a2, col_a3 = st.columns(3)
        with col_a1:
            st.write(f"Total registros: **{len(df)}**")
        with col_a2:
            motores = df['motor'].value_counts().to_dict() if 'motor' in df.columns else {}
            for motor_name, count in motores.items():
                st.write(f"Motor {motor_name}: **{count}**")
        with col_a3:
            calculados_n = df['ret_calc'].sum() if 'ret_calc' in df.columns else 0
            st.write(f"Calculados matemáticamente: **{calculados_n}**")

        st.divider()

        st.dataframe(df, use_container_width=True)
