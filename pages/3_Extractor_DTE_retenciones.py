import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import pytesseract
import json
import os
from io import BytesIO

# --- VERIFICACIÓN DE SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Directorio antes de extraer Retenciones.")
    st.stop()

cliente = st.session_state.cliente_activo

import platform

# --- CONFIGURACIÓN TÉCNICA ---
# Detecta si estamos en Windows (Local) o en Linux (Nube)
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# En la nube (Linux), Tesseract se vincula automáticamente gracias a packages.txt

st.set_page_config(page_title="Extraer DTE Retenciones", layout="wide", page_icon="✂️")

# --- DISEÑO MODO OSCURO Y PESTAÑAS ---
estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    
    div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] { 
        background-color: #8C52FF !important; border: 1px solid #5E17EB !important; border-radius: 6px; transition: 0.3s;
    }
    div.stButton > button[kind="primary"] *, div.stDownloadButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="primary"]:hover, div.stDownloadButton > button[kind="primary"]:hover { background-color: #5E17EB !important; }
    
    div.stButton > button[kind="secondary"] { background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; }
    div.stButton > button[kind="secondary"] * { color: #FFFFFF !important; font-weight: bold !important; }

    div[data-testid="stAlert"] { min-height: 80px; display: flex; align-items: center; }
    .stAlert * { color: inherit !important; }
    
    .scroll-list { max-height: 150px; overflow-y: auto; padding: 10px; background-color: #111111; border-radius: 5px; border: 1px solid #333; font-family: monospace; font-size: 13px; color: #CB6CE6; }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { color: #8C52FF !important; border-bottom-color: #8C52FF !important; }
    .stTabs [data-baseweb="tab-list"] button { color: #777777 !important; }
    [data-testid="stStatusWidget"], [data-testid="stExpander"] { background-color: #161616 !important; border: 1px solid #444444 !important; border-radius: 6px; }

    .alerta-activo { padding: 10px; border-radius: 6px; border-left: 4px solid #8C52FF; background-color: #111111; color: white; margin-bottom: 15px; font-size: 14px; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# --- MEGA-DICCIONARIO ---
def cargar_proveedores_json():
    archivo = "data/proveedores.json"
    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def guardar_proveedor_rapido(nit, nombre):
    archivo = "data/proveedores.json"
    if not os.path.exists("data"): os.makedirs("data")
    db = cargar_proveedores_json()
    db[nit] = nombre.strip().upper()
    with open(archivo, "w", encoding="utf-8") as f: json.dump(db, f, indent=4, ensure_ascii=False)

def to_excel_hacienda_retenciones(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Retenciones_F14')
        workbook = writer.book
        worksheet = writer.sheets['Retenciones_F14']
        
        fmt_texto = workbook.add_format({'num_format': '@'}) 
        fmt_num_hacienda = workbook.add_format({'num_format': '0.00', 'align': 'left'})
        
        worksheet.set_column(0, 0, 15, fmt_texto)               # A: NIT Agente (14)
        worksheet.set_column(1, 1, 12, fmt_texto)               # B: Fecha (10)
        worksheet.set_column(2, 2, 5, fmt_texto)                # C: Tipo Doc (2)
        worksheet.set_column(3, 3, 42, fmt_texto)               # D: Serie/Sello (40)
        worksheet.set_column(4, 4, 38, fmt_texto)               # E: Num Doc/UUID (36)
        worksheet.set_column(5, 6, 12, fmt_num_hacienda)        # F y G: Montos (10, Sin comas)
        worksheet.set_column(7, 7, 12, fmt_texto)               # H: DUI (9)
        worksheet.set_column(8, 8, 5, fmt_texto)                # I: Anexo (1)

    return output.getvalue()

def limpiar_monto(monto_str):
    monto_str = re.sub(r'[^\d.,]', '', str(monto_str))
    if not monto_str: return 0.0
    if ',' in monto_str and '.' in monto_str: return float(monto_str.replace(',', ''))
    elif ',' in monto_str: return float(monto_str.replace(',', '.'))
    return float(monto_str)

# --- CAZADOR DE FECHAS SUPREMO ---
def extraer_y_formatear_fecha(texto):
    meses = {'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04', 'MAY': '05', 'JUN': '06',
             'JUL': '07', 'AGO': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'}
    
    alfa_matches = re.finditer(r"\b(\d{1,2})\s*(?:de\s*|/|-)?\s*([a-zA-Z]{3,})\s*(?:de\s*|/|-)?\s*(\d{4})\b", texto, re.I)
    for m_alfa in alfa_matches:
        d, mes_str, y = m_alfa.groups()
        if int(y) < 2023: continue 
        for key, value in meses.items():
            if mes_str.upper().startswith(key): return f"{int(d):02d}/{value}/{y}"

    num_matches = re.finditer(r"\b(\d{1,4})\s*[\/\-\.]\s*(\d{1,2})\s*[\/\-\.]\s*(\d{1,4})\b", texto)
    for m_num in num_matches:
        p1, p2, p3 = m_num.groups()
        if len(p1) == 4: y, m, d = p1, p2, p3
        elif len(p3) == 4 or len(p3) == 2: 
            d, m, y = p1, p2, p3
            if len(y) == 2: y = f"20{y}"
            if int(m) > 12 and int(d) <= 12: m, d = d, m
        else: continue
        
        if int(y) < 2023: continue 
        if int(m) > 12 or int(d) > 31: continue 
        return f"{int(d):02d}/{int(m):02d}/{y}"

    nums = re.findall(r"\b\d{1,4}\b", texto)
    for i, n in enumerate(nums):
        if len(n) == 4 and 2023 <= int(n) <= 2030:
            vecinos = nums[max(0, i-4):i] + nums[i+1:i+5]
            dm = [v for v in vecinos if len(v) in [1, 2] and 0 < int(v) <= 31]
            if len(dm) >= 2:
                n1, n2 = dm[0], dm[1]
                if int(n1) > 12: d, m = n1, n2
                elif int(n2) > 12: d, m = n2, n1
                else: d, m = n1, n2
                return f"{int(d):02d}/{int(m):02d}/{n}"
    return ""

# --- MOTOR PRINCIPAL AUTÓNOMO (RETENCIONES) ---
def extraer_retenciones(file_bytes, cliente_activo):
    motor = "Nativo"
    try:
        texto_completo = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                texto_pagina = page.extract_text()
                if not texto_pagina or len(texto_pagina.strip()) < 50:
                    img = page.to_image(resolution=300)
                    texto_pagina = pytesseract.image_to_string(img.original, lang='spa')
                    motor = "ICR (OCR)"
                texto_completo += (texto_pagina or "") + "\n"
                
        t_clean = re.sub(r'\s+', ' ', texto_completo)
        t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        # 1. FILTRO DE TIPO DTE (SOLO 07)
        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
        tipo = "01"
        if m_ctrl:
            ctrl = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo: tipo = m_tipo.group(1)
        else: ctrl = ""
            
        if not ctrl: return {"error_tipo": "No se detectó un Número de Control DTE válido."}
        if tipo not in ["07"]: return {"error_tipo": f"El documento es tipo DTE-{tipo}. Este módulo solo admite Comprobantes de Retención (07)."}

        # 2. VERIFICAR INTRUSOS
        nit_cliente = re.sub(r'[^0-9]', '', cliente_activo['nit'])
        texto_solo_numeros = re.sub(r'[^0-9]', '', t_clean)
        
        es_documento_valido = False
        if nit_cliente == "00000000000000": es_documento_valido = True
        elif len(nit_cliente) >= 9 and nit_cliente in texto_solo_numeros: es_documento_valido = True
            
        if not es_documento_valido: return {"error_intruso": f"Este documento no le pertenece al cliente activo."}

        # 3. IDENTIFICADORES (UUID Y SELLO MISIL)
        gen = ""
        gen_m = re.search(r"(?:C[OÓ]DIGO\s*DE\s*GENERACI[OÓ]N|C[OÓ]D\.\s*GENERACI[OÓ]N)[^\w]*([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})", texto_completo, re.I)
        if gen_m:
            gen = gen_m.group(1).upper().replace("-", "")
        else:
            uuids = re.findall(r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})", t_no_spaces)
            if uuids:
                 for u in uuids:
                     if not re.search(r"SELLO.*?RECEPC.*?{}".format(u), t_no_spaces):
                         gen = u.upper().replace("-", "")
                         break
                 if not gen:
                     gen = uuids[0].upper().replace("-", "")

        # --- SELLO DE RECEPCIÓN (Cazador Infalible de 40 Caracteres) ---
        sello = ""
        # 1er intento: Búsqueda con etiqueta
        m_sello_exacto = re.search(r"Sello de Recepci.n\s*[:]?\s*([A-Z0-9]{40})", t_clean, re.I)
        if m_sello_exacto:
            sello = m_sello_exacto.group(1)
        else:
            # 2do intento: Busca en el texto sin espacios CUALQUIER cadena de 40 caracteres que empiece con "202" (Ej. 2024, 2025, 2026)
            sellos_huerfanos = re.findall(r"(202[3-9][A-Z0-9]{36})", t_no_spaces)
            if sellos_huerfanos:
                sello = sellos_huerfanos[0]

        fecha = extraer_y_formatear_fecha(t_clean)
        
        # 4. EXTRACCIÓN DE LA CONTRAPARTE
        nit_contraparte = ""
        nom_contraparte = "⚠️ CONTRAPARTE NUEVA"
        es_nuevo = True

        patron_identificadores = r"\b\d{4}\s*-\s*\d{6}\s*-\s*\d{3}\s*-\s*\d{1}\b|\b\d{14}\b|\b\d{8}\s*-\s*\d{1}\b|\b\d{9}\b"
        nits_encontrados = re.findall(patron_identificadores, texto_completo)
        nits_limpios = list(dict.fromkeys([re.sub(r'[^0-9]', '', n) for n in nits_encontrados]))

        proveedores_json = cargar_proveedores_json()

        for n in nits_limpios:
            if n in proveedores_json and n != nit_cliente:
                nit_contraparte = n; nom_contraparte = proveedores_json[n]; es_nuevo = False; break

        if not nit_contraparte and nits_limpios:
            if nit_cliente == "00000000000000": 
                nit_contraparte = nits_limpios[0] if len(nits_limpios) > 0 else ""
            else:
                for n in nits_limpios:
                    if n != nit_cliente:
                        nit_contraparte = n; break

        if es_nuevo and nit_contraparte:
            nom_contraparte = "ESCRIBE EL NOMBRE AQUÍ" 

        # 5. CEREBRO MATEMÁTICO DEL 1% (DEDUCCIÓN VS FORZADO)
        monto_sujeto = 0.0
        monto_retenido = 0.0
        ret_calculada = False # Solo se activa si el sistema inventa un número matemático
        
        m_sujeto = re.search(r"(?:Total Monto Sujeto|Monto Sujeto a Retenci.n|Monto Sujeto|Sujeto a Retenci.n|Base Imponible)[^\d]*?(\d{1,5}(?:[.,]\d{3})*[.,]\d{2})", t_clean, re.I)
        if m_sujeto: monto_sujeto = limpiar_monto(m_sujeto.group(1))
            
        m_retenido = re.search(r"(?:Total IVA(?: 1%)? Retenido|IVA Retenido|Retenci.n(?: del)? 1%|Impuesto Retenido)[^\d]*?(\d{1,5}(?:[.,]\d{3})*[.,]\d{2})", t_clean, re.I)
        if m_retenido: monto_retenido = limpiar_monto(m_retenido.group(1))

        # --- VALIDACIÓN LÓGICA ---
        es_logico = False
        if monto_sujeto > 0 and monto_retenido > 0:
            if abs(round(monto_sujeto * 0.01, 2) - round(monto_retenido, 2)) <= 0.05:
                es_logico = True

        # --- DEDUCCIÓN (Si falló el texto pero los números están en el papel) ---
        if not es_logico:
            montos_brutos = re.findall(r"(?:US\$?|\$)?\s*(\d{1,5}(?:[.,]\d{3})*[.,]\d{2})", t_clean)
            valores = sorted(list(set([limpiar_monto(m) for m in montos_brutos])), reverse=True)
            valores = [v for v in valores if v > 0]
            
            encontrado = False
            for val_s in valores:
                if encontrado: break
                for val_r in valores:
                    if val_r >= val_s: continue
                    # Pareja del 1% hallada en el papel
                    if abs(round(val_s * 0.01, 2) - round(val_r, 2)) <= 0.05:
                        monto_sujeto = val_s
                        monto_retenido = val_r
                        es_logico = True
                        encontrado = True
                        break

        # --- ÚLTIMO RECURSO (Cálculo Matemático Forzado) ---
        if not es_logico:
            if monto_retenido > 0 and monto_sujeto == 0.0:
                monto_sujeto = round(monto_retenido / 0.01, 2)
                ret_calculada = True
            elif monto_sujeto > 0 and monto_retenido == 0.0:
                monto_retenido = round(monto_sujeto * 0.01, 2)
                ret_calculada = True

        return {
            "fecha": fecha, "nit_contraparte": nit_contraparte, "nom_contraparte": nom_contraparte, 
            "tipo": tipo, "gen": gen, "sello": sello, "monto_sujeto": monto_sujeto, "monto_retenido": monto_retenido, 
            "estado": "✅ OK", "es_nuevo": es_nuevo, "motor": motor, "ret_calc": ret_calculada
        }
    except Exception as err: 
        return {"error": str(err)}

@st.dialog("⚠️ Seguro de Calidad de Retenciones")
def ventana_descarga_retenciones(df_resultados, nombre_archivo):
    st.write("Asegúrate de haber revisado los montos extraídos antes de descargar tu anexo. El Excel generado cumplirá exactamente con las especificaciones de Hacienda para carga masiva (sin encabezados).")
    st.download_button(label="📥 Confirmar y Descargar Anexo F-14", data=to_excel_hacienda_retenciones(df_resultados), file_name=nombre_archivo, type="primary")

# --- UI PRINCIPAL ---
st.markdown("<h2 style='font-family: Courier New, monospace; color: #5E17EB; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("✂️ Extractor DTE (Retenciones)")

st.markdown(f"""
<div class="alerta-activo">
    <strong>CLIENTE ACTUAL:</strong> {cliente['nombre']} (NIT: {cliente['nit']})
</div>
""", unsafe_allow_html=True)

if 'ret_uploader_key' not in st.session_state: st.session_state.ret_uploader_key = str(time.time())
if 'db_retenciones' not in st.session_state: st.session_state.db_retenciones = pd.DataFrame()
if 'archivos_ret' not in st.session_state: st.session_state.archivos_ret = set()
if 'reporte_retenciones' not in st.session_state: st.session_state.reporte_retenciones = None

with st.sidebar:
    st.header("Carga de Retenciones")
    archivos = st.file_uploader("Arrastra Comprobantes de Retención (07)", type="pdf", accept_multiple_files=True, key=st.session_state.ret_uploader_key)
    
    if archivos and st.button("🚀 Procesar Retenciones", type="primary"):
        extracted, vacios_deteccion, duplicados, intrusos, invalidos, calculados = [], [], [], [], [], []
        nuevos_proveedores = {}
        nuevos_archivos = [f for f in archivos if f.name not in st.session_state.archivos_ret]

        if nuevos_archivos:
            with st.container():
                bar, txt_progreso = st.progress(0), st.empty()
                t_inicio, total = time.time(), len(nuevos_archivos)
                
                for idx, f in enumerate(nuevos_archivos):
                    if idx > 0:
                        m, s = divmod(int(((time.time() - t_inicio) / idx) * (total - idx)), 60)
                        txt_progreso.markdown(f"📄 **Procesando:** {idx+1} de {total}<br>⏳ **Restante:** {m:02d}:{s:02d}", unsafe_allow_html=True)
                    else:
                        txt_progreso.markdown(f"📄 **Procesando:** 1 de {total}<br>⏳ Calculando...", unsafe_allow_html=True)
                    
                    file_bytes = f.read()
                    res = extraer_retenciones(file_bytes, cliente)
                    
                    codigo_gen = res.get('gen', '')
                    es_duplicado_memoria = not st.session_state.db_retenciones.empty and codigo_gen != "" and (st.session_state.db_retenciones['gen'] == codigo_gen).any()
                    es_duplicado_lote = any(d.get('gen') == codigo_gen for d in extracted) if codigo_gen != "" else False
                    
                    if "error_intruso" in res:
                        intrusos.append(f.name)
                        st.session_state.archivos_ret.add(f.name)
                    elif "error_tipo" in res:
                        invalidos.append(f.name)
                        st.session_state.archivos_ret.add(f.name)
                    elif es_duplicado_memoria or es_duplicado_lote:
                        duplicados.append(f.name)
                        st.session_state.archivos_ret.add(f.name)
                    elif "error" not in res:
                        fecha_str = str(res.get('fecha', '')).strip()
                        
                        # --- ALERTA DE INCOMPLETOS (INCLUYE EL SELLO) ---
                        if res.get('monto_retenido', 0.0) == 0.0 or res.get('monto_sujeto', 0.0) == 0.0 or not res.get('gen') or not res.get('sello') or not fecha_str: 
                            vacios_deteccion.append(f.name)
                        
                        if res.get("es_nuevo") and res.get("nit_contraparte"):
                            nuevos_proveedores[res["nit_contraparte"]] = res["nom_contraparte"]
                            
                        # Almacenamos los que fueron calculados por fuerza bruta (Último Recurso)
                        if res.get("ret_calc"):
                            calculados.append(f.name)
                            
                        res["archivo"] = f.name
                        extracted.append(res)
                        st.session_state.archivos_ret.add(f.name)
                    else:
                        st.sidebar.error(f"❌ {res['error']} ({f.name})")
                        
                    bar.progress((idx + 1) / total)
                
                txt_progreso.success(f"✅ ¡{total} retenciones procesadas!")
            
            st.session_state.reporte_retenciones = {
                "intrusos": intrusos, "invalidos": invalidos, "duplicados": duplicados, 
                "vacios": vacios_deteccion, "nuevos_proveedores": nuevos_proveedores,
                "calculados": calculados
            }
            
            if extracted: 
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_retenciones.empty: st.session_state.db_retenciones = new_df
                else: st.session_state.db_retenciones = pd.concat([st.session_state.db_retenciones, new_df], ignore_index=True)

    st.divider()
    if st.button("🧹 Limpiar Memoria Retenciones", type="secondary"):
        for key in ['db_retenciones', 'archivos_ret', 'reporte_retenciones']:
            if key in st.session_state: del st.session_state[key]
        st.session_state.ret_uploader_key = str(time.time()); st.rerun()

# --- DASHBOARD ---
if st.session_state.reporte_retenciones:
    rep = st.session_state.reporte_retenciones
    st.markdown("### 📋 Alertas de Procesamiento")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        if rep.get("invalidos"):
            st.error(f"⚠️ **{len(rep['invalidos'])} Ignorados** (No son DTE 07).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["invalidos"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Ignorados**.")
    with c2:
        if rep.get("vacios"):
            st.error(f"🚨 **{len(rep['vacios'])} Incompletos** (Falta Fecha, Sello o Montos).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["vacios"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Incompletos**.")
    with c3:
        if rep.get("duplicados"):
            st.error(f"🛑 **{len(rep['duplicados'])} Omitidos** (Duplicados).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["duplicados"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Omitidos**.")
    with c4:
        if rep.get("calculados"):
            st.info(f"🧮 **{len(rep['calculados'])} Calc. (1%)** (Forzado).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["calculados"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Calc. (1%)** (Lectura directa).")
    st.divider()

    if rep.get("nuevos_proveedores"):
        st.markdown("### ✨ Guardado Rápido de Contrapartes")
        st.info("Estas empresas/personas interactuaron con retenciones en este lote. Escribe su nombre oficial para que el sistema lo memorice.")
        
        for nit, nombre_sug in list(rep["nuevos_proveedores"].items()):
            col1, col2, col3 = st.columns([2, 5, 2])
            with col1: st.text_input("NIT", value=nit, disabled=True, key=f"lbl_{nit}")
            with col2: nuevo_nom = st.text_input("Nombre Oficial", value=nombre_sug, key=f"nom_{nit}")
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Guardar y Actualizar", key=f"btn_{nit}", type="primary"):
                    guardar_proveedor_rapido(nit, nuevo_nom)
                    df = st.session_state.db_retenciones
                    mask = (df['nit_contraparte'] == nit)
                    df.loc[mask, 'nom_contraparte'] = nuevo_nom.strip().upper()
                    st.session_state.db_retenciones = df
                    del st.session_state.reporte_retenciones["nuevos_proveedores"][nit]
                    st.rerun()
        st.divider()

# --- TABLAS DE RESULTADOS ---
if not st.session_state.db_retenciones.empty:
    df = st.session_state.db_retenciones.copy()
    tab1, tab2 = st.tabs(["📊 Retenciones F-14 (Vista Previa)", "🔍 Auditoría Total"])
    
    with tab1:
        # Preparamos el DataFrame con la estructura estricta del F-14
        df_hacienda = pd.DataFrame()
        
        # Regla Excluyente de Hacienda: Si es DUI (9), NIT queda vacío. Si es NIT (14), DUI queda vacío.
        df_hacienda["A. NIT Agente"] = df["nit_contraparte"].apply(lambda x: x if len(x) == 14 else "")
        df_hacienda["B. Fecha Emisión"] = df["fecha"]
        df_hacienda["C. Tipo Documento"] = df["tipo"]
        df_hacienda["D. Serie"] = df["sello"]
        df_hacienda["E. Número Documento"] = df["gen"]
        df_hacienda["F. Monto Sujeto"] = df["monto_sujeto"]
        df_hacienda["G. Monto Retención 1%"] = df["monto_retenido"]
        df_hacienda["H. DUI Agente"] = df["nit_contraparte"].apply(lambda x: x if len(x) == 9 else "")
        df_hacienda["I. Número Anexo"] = "7"

        # Añadimos la columna F de nombre al final SOLO PARA VISTA PREVIA (No se exportará a Excel)
        df_vista_previa = df_hacienda.copy()
        df_vista_previa["(Solo Visual) Nombre"] = df["nom_contraparte"]

        st.info("💡 En esta tabla verás el nombre para tu auditoría, pero al descargar el Excel para Hacienda, la columna del Nombre se eliminará y no llevará encabezados, tal como exige el manual F-14.")
        st.dataframe(df_vista_previa.style.format({col: "{:.2f}" for col in ["F. Monto Sujeto", "G. Monto Retención 1%"]}), hide_index=True, width="stretch")
        
        if st.button("📥 Generar Excel para F-14", type="primary"): 
            ventana_descarga_retenciones(df_hacienda, "F14_Retenciones.xlsx")
            
    with tab2:
        st.write(f"📊 Registros en memoria: **{len(df)}**")
        st.dataframe(df, width="stretch")