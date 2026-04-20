import streamlit as st
import pdfplumber
import pandas as pd
import pytesseract
import re
import time
import os
import json
import platform
from io import BytesIO

# --- VERIFICACIÓN DE SEGURIDAD (El Candado) ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

# --- VERIFICACIÓN DEL CLIENTE ACTIVO ---
def cargar_cliente_activo():
    if "cliente_activo" in st.session_state and st.session_state["cliente_activo"]:
        return st.session_state["cliente_activo"]
    if os.path.exists("clientes.json"):
        try:
            with open("clientes.json", "r", encoding="utf-8") as f:
                clientes = json.load(f)
                for c in clientes:
                    if c.get("activo", False) is True or c.get("Activo", False) is True:
                        return c
        except Exception:
            pass
    return None

cliente = cargar_cliente_activo()

if not cliente:
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Directorio antes de extraer Sujetos Excluidos.")
    st.stop()

# --- CONFIGURACIÓN TÉCNICA ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

st.set_page_config(page_title="Extractor DTE", layout="wide", page_icon="⚖️")

# --- DISEÑO MODO OSCURO, FIRMA YN Y CONTENEDORES ---
estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    
    div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] { 
        background-color: #666D57 !important; border: 1px solid #828B70 !important; border-radius: 6px; transition: 0.3s;
    }
    div.stButton > button[kind="primary"] *, div.stDownloadButton > button[kind="primary"] * { 
        color: #FFFFFF !important; font-weight: bold !important; 
    }
    div.stButton > button[kind="primary"]:hover, div.stDownloadButton > button[kind="primary"]:hover { 
        background-color: #798267 !important; 
    }
    
    div.stButton > button[kind="secondary"] { 
        background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; 
    }
    div.stButton > button[kind="secondary"] * { color: #FFFFFF !important; font-weight: bold !important; }

    div[data-testid="stAlert"] { min-height: 80px; display: flex; align-items: center; }
    .stAlert * { color: inherit !important; }
    
    .scroll-list {
        max-height: 150px; overflow-y: auto; padding: 10px;
        background-color: #111111; border-radius: 5px; border: 1px solid #333;
        font-family: monospace; font-size: 13px; color: #66ff66;
    }
    
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { color: #666D57 !important; border-bottom-color: #666D57 !important; }
    .stTabs [data-baseweb="tab-list"] button { color: #777777 !important; }
    [data-testid="stStatusWidget"], [data-testid="stExpander"] { background-color: #161616 !important; border: 1px solid #444444 !important; border-radius: 6px; }
    
    .alerta-activo {
        padding: 10px; border-radius: 6px; border-left: 4px solid #666D57;
        background-color: #111111; color: white; margin-bottom: 15px; font-size: 14px;
    }
    
    /* CAJAS KPI UNIFORMES */
    .kpi-box {
        background-color: #0b2612;
        border: 1px solid #16401d;
        border-radius: 8px;
        padding: 15px;
        color: #e6f4ea;
        font-size: 15px;
        min-height: 85px; /* Garantiza el mismo alto para todas */
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

# --- EXPORTACIÓN EXCEL A MEDIDA (Sujetos Excluidos) ---
def to_excel_hacienda_se(df, tipo_anexo):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False) 
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        fmt_num = workbook.add_format({'num_format': '0.00'})
        fmt_texto = workbook.add_format({'num_format': '@'}) 
        
        if tipo_anexo == "compras":
            worksheet.set_column(0, 0, 1)        # A
            worksheet.set_column(1, 1, 14, fmt_texto) # B (Num Doc)
            worksheet.set_column(2, 2, 45)       # C (Auto/45)
            worksheet.set_column(3, 3, 10)       # D (Fecha)
            worksheet.set_column(4, 5, 45)       # E-F (Serie, DTE)
            worksheet.set_column(6, 7, 10.71, fmt_num) # G-H (Montos)
            worksheet.set_column(8, 12, 1)       # I-M
                
        elif tipo_anexo == "f14":
            worksheet.set_column(0, 0, 1)        # A
            worksheet.set_column(1, 1, 4)        # B
            worksheet.set_column(2, 2, 45)       # C
            worksheet.set_column(3, 4, 14, fmt_texto) # D-E (NIT/DUI)
            worksheet.set_column(5, 5, 2)        # F
            worksheet.set_column(6, 17, 10.71, fmt_num) # G-R
            worksheet.set_column(18, 21, 1)      # S-V
            worksheet.set_column(22, 22, 6, fmt_texto) # W (Periodo)

    return output.getvalue()

# --- FUNCIÓN DE VENTANA EMERGENTE (MODAL) ---
@st.dialog("⚠️ Seguro de Calidad de Datos")
def ventana_descarga(df_resultados, tipo_anexo, nombre_archivo):
    st.write("Recuerda revisar las alertas de **campos vacíos**, **documentos inválidos** o **renta calculada automáticamente** en el Dashboard antes de enviar a Hacienda.")
    st.download_button(
        label=f"📥 Confirmar y Descargar {nombre_archivo}",
        data=to_excel_hacienda_se(df_resultados, tipo_anexo),
        file_name=nombre_archivo,
        type="primary"
    )

# --- MOTOR DE EXTRACCIÓN ---
def extraer_datos_dte14(pdf_file):
    texto_total = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                texto_extraido = page.extract_text()
                if texto_extraido: texto_total += texto_extraido + "\n"
                else:
                    img = page.to_image(resolution=300).original
                    texto_total += pytesseract.image_to_string(img, lang='spa') + "\n"
    except Exception as e:
        return {"error": str(e), "valido": False, "archivo": pdf_file.name}

    texto_upper = texto_total.upper()
    if "SUJETO EXCLUIDO" not in texto_upper and "DTE-14" not in texto_upper:
        return {"valido": False, "archivo": pdf_file.name, "error": "No es un DTE 14"}

    regex_codigo = r"Código de Generación:[\s\n]*([A-Z0-9-]+)"
    regex_sello = r"Sello de Recepción:[\s\n]*([A-Z0-9]+)"
    regex_fecha = r"Fecha y [Hh]ora de [Gg]eneración:[\s\n]*(\d{4})-(\d{2})-(\d{2})"
    regex_monto = r"Sub-Total:[\s\n]*([\d,]+\.\d{2})"
    regex_retencion = r"Retención Renta:[\s\n]*([\d,]+\.\d{2})"

    codigo_gen = re.search(regex_codigo, texto_total)
    sello = re.search(regex_sello, texto_total)
    fecha_match = re.search(regex_fecha, texto_total)
    monto = re.search(regex_monto, texto_total)
    retencion = re.search(regex_retencion, texto_total)

    partes_nombre = texto_total.split("Nombre o razón social:")
    nombre_limpio, doc_limpio = "", ""

    if len(partes_nombre) >= 3:
        bloque_receptor = partes_nombre[2]
        nombre_sucio = re.split(r"(?:DUI:|NIT:|Número de teléfono:|Dirección:)", bloque_receptor)[0]
        nombre_limpio = nombre_sucio.replace("\n", " ").strip()
        doc_match = re.search(r"(?:NIT|DUI)[\s\n:]*([\d-]+)", bloque_receptor)
        if doc_match: doc_limpio = doc_match.group(1).replace("-", "").strip()
    else:
        doc_match = re.search(r"(?:NIT|DUI)[\s\n:]*([\d-]+)", texto_total)
        doc_limpio = doc_match.group(1).replace("-", "").strip() if doc_match else ""

    codigo_gen_limpio = codigo_gen.group(1).replace("-", "") if codigo_gen else ""
    sello_limpio = sello.group(1) if sello else ""
    fecha_limpia = f"{fecha_match.group(3)}/{fecha_match.group(2)}/{fecha_match.group(1)}" if fecha_match else ""
    
    es_nit = len(doc_limpio) == 14
    es_dui = len(doc_limpio) == 9
    tipo_doc_compras = "1" if es_nit else ("2" if es_dui else "3")

    monto_val = float(monto.group(1).replace(",", "")) if monto else 0.00
    
    calculo_automatico = False
    if retencion:
        retencion_val = float(retencion.group(1).replace(",", ""))
    else:
        retencion_val = round(monto_val * 0.10, 2)
        calculo_automatico = True

    return {
        "valido": True, "archivo": pdf_file.name, "codigo": codigo_gen_limpio,
        "sello": sello_limpio, "fecha": fecha_limpia, "nombre": nombre_limpio,
        "tipo_doc_compras": tipo_doc_compras, "documento_crudo": doc_limpio,
        "nit_f14": doc_limpio if es_nit else "", "dui_f14": doc_limpio if es_dui else "",
        "monto": monto_val, "retencion": retencion_val, "calculada": calculo_automatico, "error": ""
    }

# --- TÍTULO Y FIRMA ---
st.markdown("<h2 style='font-family: Courier New, monospace; color: #666D57; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("⚖️ Extractor DTE (Sujetos Excluidos)")

st.markdown(f"""
<div class="alerta-activo">
    <strong>EMISOR ACTUAL (Cliente Activo):</strong> {cliente.get('nombre', '')} (NIT: {cliente.get('nit', '')})
</div>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE MEMORIA ---
if 'se_uploader_key' not in st.session_state: st.session_state.se_uploader_key = str(time.time())
if 'se_db_compras' not in st.session_state: st.session_state.se_db_compras = pd.DataFrame()
if 'se_db_f14' not in st.session_state: st.session_state.se_db_f14 = pd.DataFrame()
if 'se_db_auditoria' not in st.session_state: st.session_state.se_db_auditoria = pd.DataFrame()
if 'se_archivos_procesados' not in st.session_state: st.session_state.se_archivos_procesados = set()
if 'se_reporte_actual' not in st.session_state: st.session_state.se_reporte_actual = None

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Carga de Datos")
    
    with st.expander("⚙️ Conf. Global (Anexos)", expanded=False):
        f14_cod_ingreso = st.text_input("F14: Cód. Ingreso", value="11")
        f14_periodo = st.text_input("F14: Periodo (MMAAAA)", value="032026")
        compras_tipo_oper = st.selectbox("Cmp: Tipo Oper", ["1", "2", "3", "4"], index=0)
        compras_clasif = st.selectbox("Cmp: Clasif", ["1", "2"], index=1)
        compras_sector = st.selectbox("Cmp: Sector", ["1", "2", "3", "4"], index=3)
        compras_gasto = st.selectbox("Cmp: Gasto", ["1", "2", "3", "4", "5", "6", "7"], index=1)

    archivos = st.file_uploader("Arrastra tus PDFs aquí", type=["pdf"], accept_multiple_files=True, key=st.session_state.se_uploader_key)
    
    # REEMPLAZO APLICADO AQUÍ
    if archivos and st.button("🚀 Procesar Documentos", type="primary", width="stretch"):
        nuevos_archivos = [f for f in archivos if f.name not in st.session_state.se_archivos_procesados]
        
        if nuevos_archivos:
            filas_compras, filas_f14, filas_auditoria = [], [], []
            invalidos, duplicados_gen, vacios, renta_calc = [], [], [], []

            with st.container():
                bar, txt_progreso = st.progress(0), st.empty()
                t_inicio, total_archivos = time.time(), len(nuevos_archivos)
                
                for i, f in enumerate(nuevos_archivos):
                    if i > 0:
                        m, s = divmod(int(((time.time() - t_inicio) / i) * (total_archivos - i)), 60)
                        txt_progreso.markdown(f"📄 **Procesando:** {i+1} de {total_archivos}<br>⏳ **Restante:** {m:02d}:{s:02d}", unsafe_allow_html=True)
                    else:
                        txt_progreso.markdown(f"📄 **Procesando:** 1 de {total_archivos}<br>⏳ Calculando...", unsafe_allow_html=True)
                    
                    datos = extraer_datos_dte14(f)
                    st.session_state.se_archivos_procesados.add(f.name)
                    
                    if not datos["valido"]:
                        invalidos.append(f.name)
                        filas_auditoria.append({"Archivo": f.name, "Estado": "❌ Inválido", "Doc": "-", "Nombre": "-", "DTE": "-", "Monto": 0})
                        continue

                    if not datos["documento_crudo"] or not datos["nombre"] or not datos["codigo"]:
                        vacios.append(f.name)
                    
                    if datos["calculada"]:
                        renta_calc.append(f.name)

                    # Validación duplicados
                    codigo_gen = datos["codigo"]
                    es_duplicado_mem = not st.session_state.se_db_compras.empty and codigo_gen != "" and (st.session_state.se_db_compras['F_Num_DTE'] == codigo_gen).any()
                    es_duplicado_lote = any(d.get('F_Num_DTE') == codigo_gen for d in filas_compras) if codigo_gen != "" else False
                    
                    if es_duplicado_mem or es_duplicado_lote:
                        duplicados_gen.append(f.name)
                        filas_auditoria.append({"Archivo": f.name, "Estado": "🛑 Duplicado", "Doc": datos["documento_crudo"], "Nombre": datos["nombre"], "DTE": codigo_gen, "Monto": datos["monto"]})
                    else:
                        filas_auditoria.append({"Archivo": f.name, "Estado": "✅ OK", "Doc": datos["documento_crudo"], "Nombre": datos["nombre"], "DTE": codigo_gen, "Monto": datos["monto"]})
                        
                        filas_compras.append({
                            "A_Tipo_Doc": datos["tipo_doc_compras"], "B_Num_Doc": datos["documento_crudo"],
                            "C_Nombre": datos["nombre"], "D_Fecha": datos["fecha"], "E_Serie": datos["sello"],
                            "F_Num_DTE": datos["codigo"], "G_Monto": f"{datos['monto']:.2f}",
                            "H_Retencion_IVA": "0.00", "I_Tipo_Operacion": compras_tipo_oper,
                            "J_Clasificacion": compras_clasif, "K_Sector": compras_sector,
                            "L_Tipo_Gasto": compras_gasto, "M_Num_Anexo": "5"
                        })

                        filas_f14.append({
                            "A": "1", "B": "9300", "C": datos["nombre"], "D": datos["nit_f14"], "E": datos["dui_f14"],        
                            "F": f14_cod_ingreso, "G": f"{datos['monto']:.2f}", "H": "", "I": f"{datos['retencion']:.2f}", 
                            "J": "", "K": "", "L": "0.00", "M": "0.00", "N": "0.00", "O": "0.00", "P": "0.00",                  
                            "Q": "0.00", "R": "0.00", "S": compras_tipo_oper, "T": compras_clasif,          
                            "U": compras_sector, "V": compras_gasto, "W": f14_periodo              
                        })

                    bar.progress((i + 1) / total_archivos)
                
                txt_progreso.success(f"✅ ¡{total_archivos} procesados!")
            
            st.session_state.se_reporte_actual = {"vacios": vacios, "duplicados": duplicados_gen, "invalidos": invalidos, "renta_calc": renta_calc}
            if filas_compras: st.session_state.se_db_compras = pd.concat([st.session_state.se_db_compras, pd.DataFrame(filas_compras)], ignore_index=True)
            if filas_f14: st.session_state.se_db_f14 = pd.concat([st.session_state.se_db_f14, pd.DataFrame(filas_f14)], ignore_index=True)
            if filas_auditoria: st.session_state.se_db_auditoria = pd.concat([st.session_state.se_db_auditoria, pd.DataFrame(filas_auditoria)], ignore_index=True)
            time.sleep(0.5)
            st.rerun()

    st.divider()
    # REEMPLAZO APLICADO AQUÍ
    if st.button("🧹 Limpiar Memoria y Reiniciar", type="secondary", width="stretch"):
        for var in ['se_db_compras', 'se_db_f14', 'se_db_auditoria', 'se_archivos_procesados', 'se_reporte_actual']:
            if var in st.session_state: del st.session_state[var]
        st.session_state.se_uploader_key = str(time.time())
        st.rerun()

# --- ÁREA PRINCIPAL: DASHBOARD HORIZONTAL ---
if st.session_state.se_reporte_actual:
    rep = st.session_state.se_reporte_actual
    st.markdown("### 📋 Reporte de Extracción")
    
    c1, c2 = st.columns(2)
    with c1:
        total_incompletos = len(rep['vacios']) + len(rep['invalidos'])
        if total_incompletos > 0:
            st.error(f"🚨 **{total_incompletos} incompletos/inválidos** (Faltan datos o formato incorrecto).")
            with st.expander("Ver lista completa"):
                errores_lista = rep['vacios'] + rep['invalidos']
                st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in errores_lista])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 incompletos** (Datos completos y válidos).")
            
    with c2:
        if rep["duplicados"]:
            st.error(f"🛑 **{len(rep['duplicados'])} omitidos** (Cód. DTE duplicado).")
            with st.expander("Ver lista completa"):
                st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["duplicados"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 omitidos** (Sin DTE duplicados).")
    
    c3, c4, c5 = st.columns(3)
    
    with c3:
        if not rep['vacios'] and not rep['invalidos']:
            st.markdown(f'<div class="kpi-box"><span class="kpi-check">✅ 0 incompletos</span> (Datos completos).</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="kpi-box"><span class="kpi-error">🚨 {len(rep["vacios"]) + len(rep["invalidos"])} incompletos</span> (Revisar PDFs).</div>', unsafe_allow_html=True)
            
    with c4:
        if not rep['duplicados']:
            st.markdown(f'<div class="kpi-box"><span class="kpi-check">✅ 0 omitidos</span> (Sin códigos duplicados).</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="kpi-box"><span class="kpi-error">🛑 {len(rep["duplicados"])} omitidos</span> (Duplicados).</div>', unsafe_allow_html=True)
            
    with c5:
        if not rep['renta_calc']:
            st.markdown(f'<div class="kpi-box"><span class="kpi-check">✅ 0 con Renta Calc.</span> (Renta 100% extraída).</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="kpi-box"><span class="kpi-warn">🧮 {len(rep["renta_calc"])} con Renta Calc.</span> (Calculado al 10%).</div>', unsafe_allow_html=True)

    st.divider()

# --- TABLAS DE RESULTADOS ---
if not st.session_state.se_db_compras.empty:
    tab1, tab2, tab3 = st.tabs(["🛒 Anexo 5 Compras (Casilla 66)", "🧾 Anexo F14 (Retenciones)", "🔍 Auditoría Total"])

    with tab1:
        st.dataframe(st.session_state.se_db_compras, hide_index=True, width="stretch")
        if st.button("📥 Preparar Excel Compras (Casilla 66)", type="primary"):
            ventana_descarga(st.session_state.se_db_compras, "compras", "Compras_Casilla66.xlsx")

    with tab2:
        st.dataframe(st.session_state.se_db_f14, hide_index=True, width="stretch")
        if st.button("📥 Preparar Excel F14", type="primary"):
            ventana_descarga(st.session_state.se_db_f14, "f14", "Retenciones_F14.xlsx")
            
    with tab3:
        st.write(f"📊 Registros escaneados: **{len(st.session_state.se_db_auditoria)}**")
        st.dataframe(st.session_state.se_db_auditoria, hide_index=True, width="stretch")