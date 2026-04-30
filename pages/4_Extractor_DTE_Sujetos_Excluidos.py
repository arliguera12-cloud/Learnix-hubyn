import streamlit as st
import pdfplumber
import pandas as pd
import pytesseract
import re
import time
import os
import json
import platform
import gc
from io import BytesIO

# ═══════════════════════════════════════════════════════════════
# VERIFICACION DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("Acceso denegado. Por favor, inicia sesion en la pagina principal.")
    st.stop()

# ═══════════════════════════════════════════════════════════════
# FIX CRITICO: Verificar cliente activo de forma segura
# ═══════════════════════════════════════════════════════════════

def obtener_cliente_activo():
    """
    Obtiene el cliente activo con validacion de seguridad.
    Prioridad: session_state > fallback (NO busca archivos locales inseguros).
    """
    if "cliente_activo" in st.session_state:
        cliente = st.session_state["cliente_activo"]
        if isinstance(cliente, dict) and cliente.get("nit"):
            return cliente
    return None


cliente = obtener_cliente_activo()

if not cliente:
    st.warning("Debes seleccionar un Cliente Activo en el Directorio antes de extraer Sujetos Excluidos.")
    st.stop()


# ═══════════════════════════════════════════════════════════════
# CONFIGURACION TECNICA
# ═══════════════════════════════════════════════════════════════
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

st.set_page_config(
    page_title="Extractor DTE Sujetos Excluidos",
    layout="wide",
    page_icon="S"
)

# ═══════════════════════════════════════════════════════════════
# ESTILOS
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
    .kpi-box {
        background-color: #0b2612;
        border: 1px solid #16401d;
        border-radius: 8px;
        padding: 15px;
        color: #e6f4ea;
        font-size: 15px;
        min-height: 85px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-check { color: #4CAF50; font-weight: bold; }
    .kpi-error { color: #ff4b4b; font-weight: bold; }
    .kpi-warn { color: #ffeb3b; font-weight: bold; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════
ANEXO_5_CONFIG = {
    "tipo_operacion": "1",
    "clasificacion": "2",
    "sector":        "4",
    "gasto":         "2"
}

F14_CONFIG = {
    "codigo_ingreso": "11",
    "periodo":        "032026"  # MMAAAA
}


# ═══════════════════════════════════════════════════════════════
# EXPORTACION EXCEL HACIENDA
# ═══════════════════════════════════════════════════════════════

def to_excel_hacienda_se(df, tipo_anexo):
    """
    Exporta al formato exacto de Hacienda para Sujetos Excluidos.
    Soporta: "compras" (Anexo 5) y "f14" (F-14 Retenciones).
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False)
        workbook  = writer.book
        worksheet = writer.sheets['Sheet1']

        fmt_num   = workbook.add_format({'num_format': '0.00'})
        fmt_texto = workbook.add_format({'num_format': '@'})

        if tipo_anexo == "compras":
            # Anexo 5: Compras de Sujetos Excluidos (Casilla 66)
            worksheet.set_column(0, 0, 1)              # A: Tipo Doc
            worksheet.set_column(1, 1, 14, fmt_texto)  # B: Num Doc
            worksheet.set_column(2, 2, 45)             # C: Nombre
            worksheet.set_column(3, 3, 10)             # D: Fecha
            worksheet.set_column(4, 5, 45)             # E-F: Serie, UUID
            worksheet.set_column(6, 7, 10.71, fmt_num) # G-H: Montos
            worksheet.set_column(8, 12, 1)             # I-M: Clasificadores

        elif tipo_anexo == "f14":
            # F-14: Retenciones de Sujetos Excluidos (10%)
            worksheet.set_column(0, 0, 1)              # A
            worksheet.set_column(1, 1, 4)              # B
            worksheet.set_column(2, 2, 45)             # C: Nombre
            worksheet.set_column(3, 4, 14, fmt_texto)  # D-E: NIT/DUI
            worksheet.set_column(5, 5, 2)              # F
            worksheet.set_column(6, 17, 10.71, fmt_num) # G-R: Montos
            worksheet.set_column(18, 21, 1)            # S-V: Clasificadores
            worksheet.set_column(22, 22, 6, fmt_texto) # W: Periodo

    # FIX CRITICO: Reiniciar buffer antes de retornar
    output.seek(0)
    return output.getvalue()


# ═══════════════════════════════════════════════════════════════
# MODAL DE DESCARGA
# ═══════════════════════════════════════════════════════════════

@st.dialog("Seguro de Calidad de Datos")
def ventana_descarga(df_resultados, tipo_anexo, nombre_archivo):
    st.write(
        "Recuerda revisar las alertas de campos vacios, documentos invalidos "
        "o retenciones calculadas automaticamente en el Dashboard antes de enviar a Hacienda."
    )
    st.download_button(
        label=f"Confirmar y Descargar {nombre_archivo}",
        data=to_excel_hacienda_se(df_resultados, tipo_anexo),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # FIX
        type="primary",
        use_container_width=True
    )


# ═══════════════════════════════════════════════════════════════
# MOTOR DE EXTRACCION DTE-14
# ═══════════════════════════════════════════════════════════════

def extraer_datos_dte14(pdf_file, anexo5_config, f14_config):
    """
    Extrae datos de DTE-14 (Comprobante de Sujeto Excluido).
    Retorna dict con campos para ambos anexos (Compras + F-14).
    """
    texto_total = ""

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                texto_extraido = page.extract_text()

                if texto_extraido:
                    texto_total += texto_extraido + "\n"
                else:
                    # Fallback OCR si pagina es imagen
                    try:
                        img = page.to_image(resolution=300).original
                        ocr_txt = pytesseract.image_to_string(img, lang='spa')
                        texto_total += ocr_txt + "\n"
                    except Exception:
                        pass

    except Exception as err:
        return {
            "valido": False,
            "archivo": pdf_file.name,
            "error": f"Error de lectura: {str(err)}"
        }

    # Validacion de tipo documento
    texto_upper = texto_total.upper()
    if "SUJETO EXCLUIDO" not in texto_upper and "DTE-14" not in texto_upper:
        return {
            "valido": False,
            "archivo": pdf_file.name,
            "error": "No es un DTE-14 (Sujeto Excluido)"
        }

    # ── EXTRACCION DE CAMPOS ──
    regex_codigo  = r"C[OÓ]DIGO\s*DE\s*GENERACI[OÓ]N:[\s\n]*([A-Z0-9\-]+)"
    regex_sello   = r"Sello\s*de\s*Recepci[OÓ]n:[\s\n]*([A-Z0-9]+)"
    regex_fecha   = r"Fecha\s*y\s*[Hh]ora\s*de\s*[Gg]eneraci[OÓ]n:[\s\n]*(\d{4})-(\d{2})-(\d{2})"
    regex_monto   = r"Sub-?Total:[\s\n]*([\d,]+\.\d{2})"
    regex_retencion = r"Retenci[OÓ]n\s*(?:de\s*)?Renta:[\s\n]*([\d,]+\.\d{2})"

    codigo_gen    = re.search(regex_codigo,  texto_total)
    sello         = re.search(regex_sello,   texto_total)
    fecha_match   = re.search(regex_fecha,   texto_total)
    monto_match   = re.search(regex_monto,   texto_total)
    retencion_match = re.search(regex_retencion, texto_total)

    # ── EXTRACCION DE NOMBRE Y DOCUMENTO ──
    nombre_limpio, doc_limpio = "", ""

    partes_nombre = texto_total.split("Nombre o raz")
    if len(partes_nombre) >= 2:
        bloque = partes_nombre[1]
        # Partir por etiquetas conocidas
        nombre_sucio = re.split(
            r"(?:DUI:|NIT:|N[uú]mero\s+de\s+tel[eé]fono:|Direcci[oó]n:)",
            bloque
        )[0]
        nombre_limpio = nombre_sucio.replace("\n", " ").strip()

        doc_match = re.search(r"(?:NIT|DUI)[\s\n:]*([\d\-]+)", bloque)
        if doc_match:
            doc_limpio = re.sub(r'[^\d]', '', doc_match.group(1)).strip()
    else:
        # Fallback: buscar NIT/DUI en todo el texto
        doc_match = re.search(r"(?:NIT|DUI)[\s\n:]*([\d\-]+)", texto_total)
        if doc_match:
            doc_limpio = re.sub(r'[^\d]', '', doc_match.group(1)).strip()

    # ── PROCESAMIENTO DE DATOS EXTRAIDOS ──
    # FIX: Guardar UUID CON guiones (formato Hacienda)
    codigo_gen_limpio = codigo_gen.group(1).upper().replace(" ", "") if codigo_gen else ""
    sello_limpio      = sello.group(1) if sello else ""

    # Fecha: convertir a DD/MM/YYYY
    if fecha_match:
        y, m, d = fecha_match.groups()
        fecha_limpia = f"{d}/{m}/{y}"
    else:
        fecha_limpia = ""

    # Montos: convertir a float
    try:
        monto_val = float(
            monto_match.group(1).replace(",", "")
        ) if monto_match else 0.0
    except (ValueError, AttributeError):
        monto_val = 0.0

    # Retencion: extraer o calcular al 10%
    retencion_calculada = False
    try:
        if retencion_match:
            retencion_val = float(retencion_match.group(1).replace(",", ""))
        else:
            # FIX: Sujetos Excluidos retienen 10%, no 1%
            retencion_val = round(monto_val * 0.10, 2)
            retencion_calculada = True
    except (ValueError, AttributeError):
        retencion_val = round(monto_val * 0.10, 2)
        retencion_calculada = True

    # ── DETERMINACION DE TIPO DE DOCUMENTO ──
    es_nit = len(doc_limpio) == 14
    es_dui = len(doc_limpio) == 9
    tipo_doc_compras = "1" if es_nit else ("2" if es_dui else "3")

    return {
        "valido":              True,
        "archivo":             pdf_file.name,
        "codigo":              codigo_gen_limpio,
        "sello":               sello_limpio,
        "fecha":               fecha_limpia,
        "nombre":              nombre_limpio,
        "documento":           doc_limpio,
        "nit":                 doc_limpio if es_nit else "",
        "dui":                 doc_limpio if es_dui else "",
        "tipo_doc_compras":    tipo_doc_compras,
        "monto":               monto_val,
        "retencion":           retencion_val,
        "retencion_calculada": retencion_calculada,
        "error":               ""
    }


# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:Courier New,monospace; color:#666D57; "
    "letter-spacing:2px; margin-bottom:0; padding-bottom:0;'>YN</h2>",
    unsafe_allow_html=True
)
st.title("Extractor DTE - Sujetos Excluidos (DTE-14)")

st.markdown(f"""
<div class="alerta-activo">
    <strong>EMISOR ACTUAL (Cliente Activo):</strong>
    {cliente.get('nombre', 'N/A')} (NIT: {cliente.get('nit', 'N/A')})
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# INICIALIZACION DE ESTADO
# ═══════════════════════════════════════════════════════════════

if 'se_uploader_key'        not in st.session_state: st.session_state.se_uploader_key        = str(time.time())
if 'se_db_compras'          not in st.session_state: st.session_state.se_db_compras          = pd.DataFrame()
if 'se_db_f14'              not in st.session_state: st.session_state.se_db_f14              = pd.DataFrame()
if 'se_db_auditoria'        not in st.session_state: st.session_state.se_db_auditoria        = pd.DataFrame()
if 'se_archivos_procesados' not in st.session_state: st.session_state.se_archivos_procesados = set()
if 'se_reporte_actual'      not in st.session_state: st.session_state.se_reporte_actual      = None
if 'se_anexo5_config'       not in st.session_state: st.session_state.se_anexo5_config       = ANEXO_5_CONFIG.copy()
if 'se_f14_config'          not in st.session_state: st.session_state.se_f14_config          = F14_CONFIG.copy()


# ═══════════════════════════════════════════════════════════════
# SIDEBAR — CARGA Y PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("Carga de Datos")
    st.caption(f"Cliente: {cliente.get('nombre', 'N/A')}")
    st.divider()

    # ── CONFIG DE ANEXOS (con cacheo en session_state) ──
    with st.expander("Configuracion de Anexos", expanded=False):
        st.subheader("Anexo 5: Compras")
        st.session_state.se_anexo5_config["tipo_operacion"] = st.selectbox(
            "Tipo Operacion",
            ["1", "2", "3", "4"],
            index=0,
            key="sel_tipo_op_se"
        )
        st.session_state.se_anexo5_config["clasificacion"] = st.selectbox(
            "Clasificacion",
            ["1", "2"],
            index=1,
            key="sel_clasif_se"
        )
        st.session_state.se_anexo5_config["sector"] = st.selectbox(
            "Sector",
            ["1", "2", "3", "4"],
            index=3,
            key="sel_sector_se"
        )
        st.session_state.se_anexo5_config["gasto"] = st.selectbox(
            "Tipo Gasto",
            ["1", "2", "3", "4", "5", "6", "7"],
            index=1,
            key="sel_gasto_se"
        )

        st.divider()
        st.subheader("F-14: Retenciones")
        st.session_state.se_f14_config["codigo_ingreso"] = st.text_input(
            "Codigo de Ingreso",
            value=st.session_state.se_f14_config["codigo_ingreso"],
            key="inp_cod_ing_se"
        )
        st.session_state.se_f14_config["periodo"] = st.text_input(
            "Periodo (MMAAAA)",
            value=st.session_state.se_f14_config["periodo"],
            key="inp_per_se"
        )

    st.divider()

    archivos = st.file_uploader(
        "Arrastra tus PDFs aqui (DTE-14)",
        type=["pdf"],
        accept_multiple_files=True,
        key=st.session_state.se_uploader_key
    )

    # FIX: use_container_width en lugar de width="stretch"
    if archivos and st.button("Procesar Documentos", type="primary", use_container_width=True):

        nuevos = [f for f in archivos if f.name not in st.session_state.se_archivos_procesados]

        if nuevos:
            filas_compras, filas_f14, filas_auditoria = [], [], []
            invalidos, duplicados_gen, vacios, renta_calc = [], [], [], []

            bar          = st.progress(0)
            txt_progreso = st.empty()
            t_inicio     = time.time()
            total_arch   = len(nuevos)

            for idx, f in enumerate(nuevos):

                # GC cada 50 archivos
                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                # Progreso
                if idx > 0:
                    elapsed = time.time() - t_inicio
                    eta     = int((elapsed / idx) * (total_arch - idx))
                    m_t, s  = divmod(eta, 60)
                    txt_progreso.markdown(
                        f"Procesando: **{idx+1}** de **{total_arch}** "
                        f"| Restante: {m_t:02d}:{s:02d}"
                    )
                else:
                    txt_progreso.markdown(f"Procesando: **1** de **{total_arch}** | Extrayendo...")

                # Procesar archivo
                datos = extraer_datos_dte14(
                    f,
                    st.session_state.se_anexo5_config,
                    st.session_state.se_f14_config
                )
                st.session_state.se_archivos_procesados.add(f.name)

                if not datos["valido"]:
                    invalidos.append(f.name)
                    filas_auditoria.append({
                        "Archivo": f.name,
                        "Estado": "Invalido",
                        "Doc": "-",
                        "Nombre": "-",
                        "DTE": "-",
                        "Monto": 0.0
                    })
                    bar.progress((idx + 1) / total_arch)
                    continue

                # Validaciones
                if not datos["documento"] or not datos["nombre"] or not datos["codigo"]:
                    vacios.append(f.name)

                if datos["retencion_calculada"]:
                    renta_calc.append(f.name)

                # Deteccion de duplicados
                codigo_gen = datos["codigo"]
                dup_memoria = (
                    not st.session_state.se_db_compras.empty
                    and codigo_gen != ""
                    and (st.session_state.se_db_compras['F_Num_DTE'] == codigo_gen).any()
                )
                dup_lote = (
                    codigo_gen != ""
                    and any(d.get('F_Num_DTE') == codigo_gen for d in filas_compras)
                )

                if dup_memoria or dup_lote:
                    duplicados_gen.append(f.name)
                    filas_auditoria.append({
                        "Archivo": f.name,
                        "Estado": "Duplicado",
                        "Doc": datos["documento"],
                        "Nombre": datos["nombre"],
                        "DTE": codigo_gen,
                        "Monto": datos["monto"]
                    })
                else:
                    # Registros OK para tablas
                    filas_auditoria.append({
                        "Archivo": f.name,
                        "Estado": "OK",
                        "Doc": datos["documento"],
                        "Nombre": datos["nombre"],
                        "DTE": codigo_gen,
                        "Monto": datos["monto"]
                    })

                    # Anexo 5: Compras de Sujetos Excluidos
                    filas_compras.append({
                        "A_Tipo_Doc":      datos["tipo_doc_compras"],
                        "B_Num_Doc":       datos["documento"],
                        "C_Nombre":        datos["nombre"],
                        "D_Fecha":         datos["fecha"],
                        "E_Serie":         datos["sello"],
                        "F_Num_DTE":       datos["codigo"],
                        "G_Monto":         round(datos["monto"], 2),
                        "H_Retencion_IVA": 0.00,
                        "I_Tipo_Operacion": st.session_state.se_anexo5_config["tipo_operacion"],
                        "J_Clasificacion": st.session_state.se_anexo5_config["clasificacion"],
                        "K_Sector":        st.session_state.se_anexo5_config["sector"],
                        "L_Tipo_Gasto":    st.session_state.se_anexo5_config["gasto"],
                        "M_Num_Anexo":     "5"
                    })

                    # F-14: Retenciones 10% Sujetos Excluidos
                    filas_f14.append({
                        "A": "1",
                        "B": "9300",
                        "C": datos["nombre"],
                        "D": datos["nit"],
                        "E": datos["dui"],
                        "F": st.session_state.se_f14_config["codigo_ingreso"],
                        "G": round(datos["monto"], 2),
                        "H": "",
                        "I": round(datos["retencion"], 2),
                        "J": "",
                        "K": "",
                        "L": 0.00,
                        "M": 0.00,
                        "N": 0.00,
                        "O": 0.00,
                        "P": 0.00,
                        "Q": 0.00,
                        "R": 0.00,
                        "S": st.session_state.se_anexo5_config["tipo_operacion"],
                        "T": st.session_state.se_anexo5_config["clasificacion"],
                        "U": st.session_state.se_anexo5_config["sector"],
                        "V": st.session_state.se_anexo5_config["gasto"],
                        "W": st.session_state.se_f14_config["periodo"]
                    })

                bar.progress((idx + 1) / total_arch)

            txt_progreso.success(f"{total_arch} documentos procesados correctamente.")

            # Guardar reporte y datos
            st.session_state.se_reporte_actual = {
                "vacios":    vacios,
                "duplicados": duplicados_gen,
                "invalidos": invalidos,
                "renta_calc": renta_calc
            }

            if filas_compras:
                new_df_compras = pd.DataFrame(filas_compras)
                if st.session_state.se_db_compras.empty:
                    st.session_state.se_db_compras = new_df_compras
                else:
                    st.session_state.se_db_compras = pd.concat(
                        [st.session_state.se_db_compras, new_df_compras], ignore_index=True
                    )

            if filas_f14:
                new_df_f14 = pd.DataFrame(filas_f14)
                if st.session_state.se_db_f14.empty:
                    st.session_state.se_db_f14 = new_df_f14
                else:
                    st.session_state.se_db_f14 = pd.concat(
                        [st.session_state.se_db_f14, new_df_f14], ignore_index=True
                    )

            if filas_auditoria:
                new_df_audit = pd.DataFrame(filas_auditoria)
                if st.session_state.se_db_auditoria.empty:
                    st.session_state.se_db_auditoria = new_df_audit
                else:
                    st.session_state.se_db_auditoria = pd.concat(
                        [st.session_state.se_db_auditoria, new_df_audit], ignore_index=True
                    )

            gc.collect()
            time.sleep(0.3)

            # FIX: Solo rerun si hay datos
            if filas_compras or filas_f14 or filas_auditoria:
                st.rerun()

    st.divider()

    # FIX: use_container_width en lugar de width="stretch"
    if st.button("Limpiar Memoria y Reiniciar", type="secondary", use_container_width=True):
        for var in [
            'se_db_compras', 'se_db_f14', 'se_db_auditoria',
            'se_archivos_procesados', 'se_reporte_actual'
        ]:
            st.session_state.pop(var, None)
        st.session_state.se_uploader_key = str(time.time())
        gc.collect()
        st.rerun()


# ═══════════════════════════════════════════════════════════════
# DASHBOARD DE ALERTAS
# ═══════════════════════════════════════════════════════════════

if st.session_state.se_reporte_actual:
    rep = st.session_state.se_reporte_actual
    st.markdown("### Reporte de Extraccion")

    c1, c2 = st.columns(2)

    with c1:
        total_problemas = len(rep['vacios']) + len(rep['invalidos'])
        if total_problemas > 0:
            st.error(f"**{total_problemas} problematicos** (Faltan datos o formato incorrecto).")
            with st.expander("Ver lista"):
                lista = rep['vacios'] + rep['invalidos']
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in lista)
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 problematicos** (Datos completos).")

    with c2:
        if rep["duplicados"]:
            st.error(f"**{len(rep['duplicados'])} omitidos** (Codigos duplicados).")
            with st.expander("Ver lista"):
                st.markdown(
                    '<div class="scroll-list">'
                    + "".join(f"• {a}<br>" for a in rep["duplicados"])
                    + '</div>', unsafe_allow_html=True
                )
        else:
            st.success("**0 omitidos** (Sin duplicados).")

    c3, c4, c5 = st.columns(3)

    with c3:
        if len(rep['vacios']) + len(rep['invalidos']) == 0:
            st.markdown(
                '<div class="kpi-box"><span class="kpi-check">OK</span> Sin datos incompletos.</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="kpi-box"><span class="kpi-error">{len(rep["vacios"]) + len(rep["invalidos"])}</span> incompletos.</div>',
                unsafe_allow_html=True
            )

    with c4:
        if not rep['duplicados']:
            st.markdown(
                '<div class="kpi-box"><span class="kpi-check">OK</span> Sin duplicados.</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="kpi-box"><span class="kpi-error">{len(rep["duplicados"])}</span> duplicados.</div>',
                unsafe_allow_html=True
            )

    with c5:
        if not rep['renta_calc']:
            st.markdown(
                '<div class="kpi-box"><span class="kpi-check">OK</span> Retencion extraida.</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="kpi-box"><span class="kpi-warn">{len(rep["renta_calc"])}</span> retencion calc.</div>',
                unsafe_allow_html=True
            )

    st.divider()


# ═══════════════════════════════════════════════════════════════
# TABLAS DE RESULTADOS
# ═══════════════════════════════════════════════════════════════

if not st.session_state.se_db_compras.empty:
    tab1, tab2, tab3 = st.tabs([
        "Anexo 5 Compras (Casilla 66)",
        "Anexo F-14 (Retenciones 10%)",
        "Auditoria Total"
    ])

    with tab1:
        st.dataframe(
            st.session_state.se_db_compras,
            hide_index=True,
            use_container_width=True
        )
        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn2:
            if st.button(
                "Generar Excel Compras",
                type="primary",
                use_container_width=True
            ):
                ventana_descarga(
                    st.session_state.se_db_compras,
                    "compras",
                    "Compras_Casilla66.xlsx"
                )

    with tab2:
        st.dataframe(
            st.session_state.se_db_f14,
            hide_index=True,
            use_container_width=True
        )
        col_btn3, col_btn4 = st.columns([3, 1])
        with col_btn4:
            if st.button(
                "Generar Excel F-14",
                type="primary",
                use_container_width=True
            ):
                ventana_descarga(
                    st.session_state.se_db_f14,
                    "f14",
                    "Retenciones_F14.xlsx"
                )

    with tab3:
        st.write(f"Registros escaneados: **{len(st.session_state.se_db_auditoria)}**")
        st.dataframe(
            st.session_state.se_db_auditoria,
            hide_index=True,
            use_container_width=True
        )
