import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import pytesseract
from io import BytesIO
import platform

# --- VERIFICACIÓN DE SEGURIDAD (El Candado) ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

# --- VERIFICACIÓN DEL CLIENTE ACTIVO ---
if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Directorio antes de extraer Ventas.")
    st.stop()

cliente = st.session_state.cliente_activo

# --- CONFIGURACIÓN TÉCNICA ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

st.set_page_config(page_title="Extraer DTE", layout="wide", page_icon="⚖️")

# --- DISEÑO MODO OSCURO, FIRMA YN Y CONTENEDORES SCROLL ---
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
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# --- EXPORTACIÓN EXCEL A MEDIDA (HACIENDA) ---
def to_excel_hacienda(df, anexo_tipo):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False) 
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        fmt_num = workbook.add_format({'num_format': '0.00'})
        fmt_texto = workbook.add_format({'num_format': '@'}) 
        
        def get_max_len(col_idx):
            return max(df.iloc[:, col_idx].astype(str).map(len).max() if not df.empty else 10, 10) + 2

        worksheet.set_column(0, len(df.columns)-1, 10.71) 
        
        if anexo_tipo == "A":
            worksheet.set_column(0, 0, 10) 
            worksheet.set_column(1, 1, 1, fmt_texto) 
            worksheet.set_column(2, 2, 2) 
            for col_idx in [3, 4, 5, 8]: worksheet.set_column(col_idx, col_idx, get_max_len(col_idx))
            worksheet.set_column(6, 6, 10.71) 
            worksheet.set_column(7, 7, 14)    
            for col_idx in [17, 18, 19]: worksheet.set_column(col_idx, col_idx, 1, fmt_texto)
            for i in range(9, 16): worksheet.set_column(i, i, None, fmt_num)
                
        elif anexo_tipo == "B":
            worksheet.set_column(0, 0, 10) 
            worksheet.set_column(1, 1, 1, fmt_texto) 
            worksheet.set_column(2, 2, 2) 
            for col_idx in [7, 8]: worksheet.set_column(col_idx, col_idx, get_max_len(col_idx))
            for col_idx in [20, 21, 22]: worksheet.set_column(col_idx, col_idx, 1, fmt_texto)
            for i in range(10, 20): worksheet.set_column(i, i, None, fmt_num)

    return output.getvalue()

def clasificar_tipo_ingreso(actividad):
    if not actividad: return "3"
    act = actividad.lower()
    if any(w in act for w in ['médico', 'abogado', 'contad', 'ingeniero', 'profesiones', 'auditor']): return "1"
    if any(w in act for w in ['servicio', 'mantenimiento', 'transporte', 'flete', 'taller']): return "2"
    if any(w in act for w in ['industria', 'fabricación', 'manufactura']): return "4"
    if any(w in act for w in ['agro', 'ganadería', 'agricultura']): return "5"
    if any(w in act for w in ['export']): return "7"
    return "3"

def limpiar_monto(monto_str):
    monto_str = monto_str.replace(' ', '').replace('$', '')
    if ',' in monto_str and '.' in monto_str:
        return float(monto_str.replace(',', ''))
    elif ',' in monto_str:
        return float(monto_str.replace(',', '.'))
    return float(monto_str)

# --- MOTOR PRINCIPAL DE EXTRACCIÓN ---
def extraer_dte_avanzado(f, cliente_activo):
    motor = "Nativo"
    try:
        with pdfplumber.open(f) as pdf:
            pagina = pdf.pages[0]
            texto_prueba = pagina.extract_text() or ""
            
            ancho = pagina.width
            alto = pagina.height
            
            # --- DETECCIÓN OCR GLOBAL ---
            if len(texto_prueba.strip()) < 100:
                motor = "ICR (OCR)"
                caja_receptor = (ancho * 0.48, 0, ancho, alto * 0.65)
                img_receptor = pagina.crop(caja_receptor).to_image(resolution=300)
                texto_receptor = pytesseract.image_to_string(img_receptor.original, lang='spa')
                
                img_completa = pagina.to_image(resolution=300)
                texto_raw = pytesseract.image_to_string(img_completa.original, lang='spa')
                t_clean = re.sub(r'\s+', ' ', texto_raw)
            else:
                caja_receptor = (ancho * 0.48, 0, ancho, alto * 0.65)
                pagina_receptor = pagina.crop(caja_receptor)
                texto_receptor = pagina_receptor.extract_text(x_tolerance=4) or ""
                texto_raw = texto_prueba
                t_clean = re.sub(r'\s+', ' ', texto_raw)

            # --- VALIDACIÓN DE CLIENTE ACTIVO (ESCUDO ANTI-INTRUSOS) ---
            nit_emisor_limpio = re.sub(r'[^0-9]', '', cliente_activo['nit'])
            dui_emisor_limpio = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))
            
            patron_identificadores = r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b|\b\d{14}\b|\b\d{8}-?\d{1}\b|\b\d{9}\b"
            nits_encontrados = re.findall(patron_identificadores, t_clean)
            nits_limpios = [re.sub(r'[^0-9]', '', n) for n in nits_encontrados]
            
            es_documento_valido = False
            
            if nit_emisor_limpio == "00000000000000":
                es_documento_valido = True
            elif nit_emisor_limpio in nits_limpios: 
                es_documento_valido = True
            elif dui_emisor_limpio and dui_emisor_limpio in nits_limpios: 
                es_documento_valido = True
                
            if not es_documento_valido:
                return {"error": f"Documento ajeno al emisor activo ({cliente_activo['nombre']})."}

            # --- EXTRACCIÓN DEL RECEPTOR ---
            patron_nit_num = r"\b\d{4}-?\d{6}-?\d{3}-?\d{1}\b|\b\d{8}-?\d{1}\b"
            nit_m = re.search(r"N\s*[I1l\|]?\s*T\s*[:]?\s*([\d\-\s]{9,20})", texto_receptor, re.I)
            if not nit_m: 
                nit_m = re.search(r"(" + patron_nit_num + r")", texto_receptor)
                
            nit = re.sub(r'[^0-9]', '', nit_m.group(1)) if nit_m else ""
            
            if "RECEPTOR" in texto_receptor:
                bloque_nombre = texto_receptor.split("RECEPTOR", 1)[1]
            elif "Generación:" in texto_receptor:
                bloque_nombre = texto_receptor.split("Generación:", 1)[1]
                bloque_nombre = re.sub(r"^\s*\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}", "", bloque_nombre).strip()
            else:
                bloque_nombre = texto_receptor

            bloque_lineal = bloque_nombre.replace('\n', ' ')
            
            nom_m = re.search(r"(.*?)(?=\bN\s*[I\|1l]\s*T\b|\bN\s*R\s*C\b|\bA\s*c\s*t\s*i\s*v\s*i\s*d\s*a\s*d\b|" + patron_nit_num + r")", bloque_lineal, re.I)
            
            if nom_m:
                nombre_sucio = nom_m.group(1)
                nombre = re.sub(r"(Nombre o razón social|Nombre|Razón social)\s*[:]?\s*", "", nombre_sucio, flags=re.I).strip()
                nombre = re.sub(r"\|", "I", nombre).strip()
            else:
                nombre = ""

            # --- IDENTIFICADORES ---
            tipo_m = re.search(r"DTE-(\d{2})-", t_clean)
            tipo = tipo_m.group(1) if tipo_m else "01"
            
            ctrl_m = re.search(r"(DTE-\d{2}-[A-Z0-9-]+)", t_clean)
            ctrl = ctrl_m.group(1) if ctrl_m else ""
            
            gen_m = re.search(r"Generación\s*[:]?\s*([A-Z0-9-]{30,})", t_clean, re.I)
            gen = gen_m.group(1) if gen_m else ""
            
            sello_m = re.search(r"Sello de Recepción\s*[:]?\s*([A-Z0-9]{10,})", t_clean, re.I)
            sello = sello_m.group(1) if sello_m else ""
            
            f_m = re.search(r"(\d{4}-\d{2}-\d{2})", t_clean)
            fecha = f"{f_m.group(1).split('-')[2]}/{f_m.group(1).split('-')[1]}/{f_m.group(1).split('-')[0]}" if f_m else ""

            act_m = re.search(r"Actividad económica\s*[:]?\s*(.*?)(?=\s+Dirección)", t_clean, re.I)
            t_ing = clasificar_tipo_ingreso(act_m.group(1) if act_m else "")

            # --- BÚSQUEDA DE VENTAS ---
            def buscar_montos(texto_a_buscar, tipo_dte, pdf_page_obj=None):
                n, e, g, i, t, x = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                encontrado = False
                iva_calculado = False
                
                if tipo_dte == "11":
                    exp_m = re.search(r"(?:Total de Operaciones Afectas|Monto Total de la Operación)\s*[:]?\s*\$?\s*([\d,]+\.\d{2})", texto_a_buscar, re.I)
                    if exp_m:
                        x = float(exp_m.group(1).replace(',', ''))
                        t = x
                        encontrado = True
                else:
                    sum_m = re.search(r"(?:Suma de Ventas|Ventas afectas):?\s*\$?\s*([\d,.]*)\s*([\d,.]*)\s*([\d,.]*)", texto_a_buscar)
                    if sum_m:
                        try: n = float(sum_m.group(1).replace(',', '') or 0)
                        except: pass
                        try: e = float(sum_m.group(2).replace(',', '') or 0)
                        except: pass
                        try: g = float(sum_m.group(3).replace(',', '') or 0)
                        except: pass
                        encontrado = True
                    
                    iva_m = re.search(r"(?:Impuesto al Valor Agregado 13%|IVA 13%|IVA)\s*[:]?\s*\$?\s*([\d,]+\.\d{2})", texto_a_buscar, re.I)
                    if iva_m: i = float(iva_m.group(1).replace(',', ''))
                        
                    tot_m = re.search(r"(?:Total a Pagar|Monto Total)[\s$]*([\d,]+\.\d{2})", texto_a_buscar, re.I)
                    t = float(tot_m.group(1).replace(',', '')) if tot_m else (g + i + e + n)

                if g == 0.0 and pdf_page_obj:
                    try:
                        w = pdf_page_obj.width
                        h = pdf_page_obj.height
                        caja_totales = (w * 0.40, h * 0.60, w, h)
                        img_totales = pdf_page_obj.crop(caja_totales).to_image(resolution=300)
                        
                        texto_totales_ocr = pytesseract.image_to_string(img_totales.original, lang='spa')
                        texto_totales_limpio = re.sub(r'\s+', ' ', texto_totales_ocr)

                        m_g = re.search(r"(?:Suma Total de Operaciones|Sub-Total|Sub Total|Ventas Gravadas)[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", texto_totales_limpio, re.I)
                        if m_g:
                            try: g = limpiar_monto(m_g.group(1)); encontrado = True
                            except: pass

                        if i == 0.0 and not iva_m:
                            m_i = re.search(r"(?:Agregado 13%|IVA 13%|IVA)[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", texto_totales_limpio, re.I)
                            if m_i:
                                try: i = limpiar_monto(m_i.group(1))
                                except: pass
                            elif g > 0 and tipo_dte == "03":
                                i = round(g * 0.13, 2)
                                iva_calculado = True

                        if t == 0.0 and not tot_m:
                            m_t = re.search(r"(?:Total a Pagar|Monto Total)[^\d]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", texto_totales_limpio, re.I)
                            if m_t:
                                try: t = limpiar_monto(m_t.group(1))
                                except: t = g + i + e + n
                            else:
                                t = g + i + e + n
                        elif t == 0.0 and tot_m:
                            t = g + i + e + n
                    except Exception as ocr_err:
                        pass
                    
                return n, e, g, i, t, x, encontrado, iva_calculado

            nos, exe, gra, iva, tot, exp_serv, exito_ventas, flag_iva = buscar_montos(t_clean, tipo, pagina)

            if not exito_ventas and len(pdf.pages) > 1:
                pagina2 = pdf.pages[1]
                if "OCR" in motor:
                    t_clean_p2 = re.sub(r'\s+', ' ', pytesseract.image_to_string(pagina2.to_image(resolution=300).original, lang='spa'))
                else:
                    t_clean_p2 = re.sub(r'\s+', ' ', pagina2.extract_text() or "")
                
                nos2, exe2, gra2, iva2, tot2, exp_serv2, exito_ventas2, flag_iva2 = buscar_montos(t_clean_p2, tipo, pagina2)
                if exito_ventas2:
                    nos, exe, gra, iva, tot, exp_serv, flag_iva = nos2, exe2, gra2, iva2, tot2, exp_serv2, flag_iva2

            return {
                "fecha": fecha, "nit": nit, "nom": nombre, "tipo": tipo, "ctrl": ctrl, 
                "gen": gen, "sello": sello, "nos": nos, "exe": exe, "gra": gra, 
                "iva": iva, "exp_serv": exp_serv, "tot": tot, "t_ing": t_ing, "motor": motor,
                "iva_calculado": flag_iva
            }
    except Exception as e:
        return {"error": f"Error de lectura: {str(e)}"}

# --- FUNCIÓN DE VENTANA EMERGENTE (MODAL) ---
@st.dialog("⚠️ Seguro de Calidad de Datos")
def ventana_descarga(df_resultados, tipo_anexo, nombre_archivo):
    st.write("Recuerda revisar las alertas de **campos vacíos**, **rechazados** o **cálculos manuales** en el Dashboard para mayor seguridad en tus datos antes de enviarlos a Hacienda.")
    st.download_button(
        label=f"📥 Confirmar y Descargar Anexo {tipo_anexo}",
        data=to_excel_hacienda(df_resultados, tipo_anexo),
        file_name=nombre_archivo,
        type="primary"
    )

# --- TÍTULO Y FIRMA ---
st.markdown("<h2 style='font-family: Courier New, monospace; color: #666D57; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("⚖️ Extractor DTE (Ventas)")

st.markdown(f"""
<div class="alerta-activo">
    <strong>EMISOR ACTUAL (Cliente Activo):</strong> {cliente['nombre']} (NIT: {cliente['nit']})
</div>
""", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = str(time.time())
if 'db' not in st.session_state: st.session_state.db = pd.DataFrame()
if 'archivos_procesados' not in st.session_state: st.session_state.archivos_procesados = set()
if 'reporte_actual' not in st.session_state: st.session_state.reporte_actual = None

with st.sidebar:
    st.header("Carga de Datos")
    archivos = st.file_uploader("Arrastra tus PDFs aquí", type="pdf", accept_multiple_files=True, key=st.session_state.uploader_key)
    
    if archivos and st.button("🚀 Procesar Documentos", type="primary", width="stretch"):
        extracted, duplicados_generacion, vacios_deteccion, iva_calculado_files, archivos_rechazados = [], [], [], [], []
        nuevos_archivos = [f for f in archivos if f.name not in st.session_state.archivos_procesados]

        if nuevos_archivos:
            with st.container():
                bar, txt_progreso = st.progress(0), st.empty()
                t_inicio, total_archivos = time.time(), len(nuevos_archivos)
                
                for i, f in enumerate(nuevos_archivos):
                    if i > 0:
                        m, s = divmod(int(((time.time() - t_inicio) / i) * (total_archivos - i)), 60)
                        txt_progreso.markdown(f"📄 **Procesando:** {i+1} de {total_archivos}<br>⏳ **Restante:** {m:02d}:{s:02d}", unsafe_allow_html=True)
                    else:
                        txt_progreso.markdown(f"📄 **Procesando:** 1 de {total_archivos}<br>⏳ Calculando...", unsafe_allow_html=True)
                    
                    res = extraer_dte_avanzado(f, cliente)
                    
                    # --- AQUÍ GUARDAMOS LOS RECHAZADOS EN MEMORIA PARA EL DASHBOARD ---
                    if "error" in res:
                        archivos_rechazados.append(f"{f.name} - {res['error']}")
                        st.session_state.archivos_procesados.add(f.name)
                    else:
                        campos_criticos = [res['fecha'], res['ctrl'], res['tot']] if res['tipo'] in ["01", "11"] else [res['fecha'], res['nit'], res['nom'], res['ctrl'], res['tot']]
                        if "" in campos_criticos or 0.0 == res['tot']: vacios_deteccion.append(f.name)
                        if res.get('iva_calculado'): iva_calculado_files.append(f.name)
                        
                        codigo_gen = res.get('gen', '')
                        
                        es_duplicado_memoria = not st.session_state.db.empty and codigo_gen != "" and (st.session_state.db['gen'] == codigo_gen).any()
                        es_duplicado_lote = any(d.get('gen') == codigo_gen for d in extracted) if codigo_gen != "" else False
                        
                        if es_duplicado_memoria or es_duplicado_lote:
                            duplicados_generacion.append(f.name)
                            st.session_state.archivos_procesados.add(f.name) 
                        else:
                            res["archivo"] = f.name
                            extracted.append(res)
                            st.session_state.archivos_procesados.add(f.name)

                    bar.progress((i + 1) / total_archivos)
                txt_progreso.success(f"✅ ¡{total_archivos} procesados!")
            
            # --- GUARDAMOS TODO EN EL ESTADO GLOBAL ---
            st.session_state.reporte_actual = {
                "duplicados_gen": duplicados_generacion, 
                "vacios": vacios_deteccion, 
                "iva_calc": iva_calculado_files,
                "rechazados": archivos_rechazados
            }
            if extracted: st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame(extracted)], ignore_index=True)
            time.sleep(0.5)
            st.rerun()

    st.divider()
    if st.button("🧹 Limpiar Memoria y Reiniciar", type="secondary", width="stretch"):
        variables_a_borrar = ['db', 'archivos_procesados', 'reporte_actual']
        for var in variables_a_borrar:
            if var in st.session_state:
                del st.session_state[var]
        
        st.session_state.uploader_key = str(time.time())
        st.rerun()

# --- ÁREA PRINCIPAL: DASHBOARD HORIZONTAL ---
if st.session_state.reporte_actual:
    rep = st.session_state.reporte_actual
    st.markdown("### 📋 Reporte de Extracción")
    
    # --- CUATRO COLUMNAS (Incluyendo la nueva de Rechazados) ---
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        if rep.get("rechazados"):
            st.error(f"🚫 **{len(rep['rechazados'])} Rechazados** (No pertenecen).")
            with st.expander("Ver lista"):
                st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["rechazados"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Rechazados**.")

    with c2:
        if rep.get("vacios"):
            st.error(f"🚨 **{len(rep['vacios'])} Incompletos** (Faltan datos).")
            with st.expander("Ver lista"):
                st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["vacios"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Incompletos**.")
            
    with c3:
        if rep.get("duplicados_gen"):
            st.error(f"🛑 **{len(rep['duplicados_gen'])} Omitidos** (Duplicados).")
            with st.expander("Ver lista"):
                st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["duplicados_gen"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Omitidos**.")
            
    with c4:
        if rep.get("iva_calc"):
            st.info(f"🧮 **{len(rep['iva_calc'])} IVA Calc.** (Al 13%).")
            with st.expander("Ver lista"):
                st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["iva_calc"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 IVA Calc.**.")
    st.divider()

# --- TABLAS DE RESULTADOS ---
if not st.session_state.db.empty:
    df = st.session_state.db
    tab1, tab2, tab3 = st.tabs(["📊 F-07 Ventas a Contribuyentes (CCF)", "📑 F-07 Ventas Consumidor (Facturas)", "🔍 Auditoría Total"])

    with tab1:
        df_a = df[df["tipo"].isin(["03", "05", "06"])].copy()
        if not df_a.empty:
            df_a["clase"], df_a["ctrl_vacio"], df_a["v_terc"], df_a["d_terc"], df_a["dui"], df_a["t_op"], df_a["n_anexo"] = "4", "", 0.00, 0.00, "", "1", "1"
            cols = ["fecha", "clase", "tipo", "ctrl", "sello", "gen", "ctrl_vacio", "nit", "nom", "exe", "nos", "gra", "iva", "v_terc", "d_terc", "tot", "dui", "t_op", "t_ing", "n_anexo"]
            res_a = df_a[cols].sort_values(by="ctrl")
            res_a.columns = ["1.Fecha", "2.Clase", "3.Tipo", "4.Num Control", "5.Sello", "6.Generación", "7.Num Control", "8.NIT/NRC", "9.Razón Social", "10.Exentas", "11.No Sujetas", "12.Gravadas", "13.Débito", "14.V. Terceros", "15.D. Terceros", "16.Total", "17.DUI", "18.Tipo Op", "19.Tipo Ing", "20.Anexo"]
            st.dataframe(res_a.style.format({col: "{:.2f}" for col in ["10.Exentas", "11.No Sujetas", "12.Gravadas", "13.Débito", "14.V. Terceros", "15.D. Terceros", "16.Total"]}), hide_index=True, width="stretch")
            if st.button("📥 Preparar Excel CCF", type="primary"): ventana_descarga(res_a, "A", "F07_Ventas_Contribuyentes.xlsx")

    with tab2:
        df_b = df[df["tipo"].isin(["01", "11"])].copy()
        if not df_b.empty:
            df_b["clase"], df_b["res"], df_b["ser"], df_b["int"], df_b["maq"], df_b["pre_ctrl"], df_b["vtas_int_exe_no_suj"], df_b["n_anexo"] = "4", "N/A", "N/A", "N/A", "", "N/A", 0.00, "2"
            df_b["exp_ca"], df_b["exp_fca"], df_b["v_zf"], df_b["v_ter"], df_b["t_op"] = 0.00, 0.00, 0.00, 0.00, "1"
            if "exp_serv" not in df_b.columns: df_b["exp_serv"] = 0.00
            cols = ["fecha", "clase", "tipo", "res", "ser", "int", "pre_ctrl", "ctrl", "gen", "maq", "exe", "nos", "vtas_int_exe_no_suj", "gra", "exp_ca", "exp_fca", "exp_serv", "v_zf", "v_ter", "tot", "t_op", "t_ing", "n_anexo"]
            res_b = df_b[cols].sort_values(by="ctrl")
            res_b.columns = ["1.Fecha", "2.Clase", "3.Tipo", "4.Resolución", "5.Serie", "6.Interno", "7.Pre-Control", "8.Num Control", "9.Generación", "10.Máquina", "11.Exentas", "12.No Sujetas", "13.Vtas Int Exe No Suj Prop", "14.Gravadas", "15.Exp CA", "16.Exp Fuera CA", "17.Exp Serv", "18.ZF y DPA", "19.V. Terceros", "20.Total", "21.Tipo Op", "22.Tipo Ing", "23.Anexo"]
            st.dataframe(res_b.style.format({col: "{:.2f}" for col in ["11.Exentas", "12.No Sujetas", "13.Vtas Int Exe No Suj Prop", "14.Gravadas", "15.Exp CA", "16.Exp Fuera CA", "17.Exp Serv", "18.ZF y DPA", "19.V. Terceros", "20.Total"]}), hide_index=True, width="stretch")
            if st.button("📥 Preparar Excel Facturas", type="primary"): ventana_descarga(res_b, "B", "F07_Ventas_Consumidor.xlsx")
            
    with tab3:
        st.write(f"📊 Registros en memoria: **{len(df)}**")
        st.dataframe(df, width="stretch")
