import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import pytesseract
import json
import os
import gc
import base64
from io import BytesIO
import platform

# --- VERIFICACIÓN DE SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Directorio antes de extraer Compras.")
    st.stop()

cliente = st.session_state.cliente_activo

# --- CONFIGURACIÓN TÉCNICA ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

st.set_page_config(page_title="Extraer DTE Compras", layout="wide", page_icon="🛒")

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] { background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; transition: 0.3s; }
    div.stButton > button[kind="primary"] *, div.stDownloadButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="primary"]:hover, div.stDownloadButton > button[kind="primary"]:hover { background-color: #00407A !important; }
    div.stButton > button[kind="secondary"] { background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; }
    div.stButton > button[kind="secondary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div[data-testid="stAlert"] { min-height: 80px; display: flex; align-items: center; }
    .stAlert * { color: inherit !important; }
    .scroll-list { max-height: 150px; overflow-y: auto; padding: 10px; background-color: #111111; border-radius: 5px; border: 1px solid #333; font-family: monospace; font-size: 13px; color: #66ff66; }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { color: #4DA8DA !important; border-bottom-color: #4DA8DA !important; }
    .stTabs [data-baseweb="tab-list"] button { color: #777777 !important; }
    [data-testid="stStatusWidget"], [data-testid="stExpander"] { background-color: #161616 !important; border: 1px solid #444444 !important; border-radius: 6px; }
    .alerta-activo { padding: 10px; border-radius: 6px; border-left: 4px solid #00407A; background-color: #111111; color: white; margin-bottom: 15px; font-size: 14px; }
    .inbox-revision { background-color: #1a1a1a; border: 1px solid #ffaa00; border-radius: 10px; padding: 20px; margin-top: 20px; margin-bottom: 20px; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

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

def to_excel_hacienda_compras(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Compras_F07')
        workbook = writer.book
        worksheet = writer.sheets['Compras_F07']
        fmt_texto = workbook.add_format({'num_format': '@'}) 
        fmt_num_izq = workbook.add_format({'num_format': '0.00', 'align': 'left'})
        def get_max_len(col_idx): return max(df.iloc[:, col_idx].astype(str).map(len).max() if not df.empty else 15, 15) + 2
        worksheet.set_column(0, 0, 10, fmt_texto)
        worksheet.set_column(1, 1, 1, fmt_texto)
        worksheet.set_column(2, 2, 2, fmt_texto)
        worksheet.set_column(3, 3, get_max_len(3), fmt_texto)
        worksheet.set_column(4, 4, 14, fmt_texto)
        worksheet.set_column(5, 5, get_max_len(5), fmt_texto)
        worksheet.set_column(6, 14, 10.71, fmt_num_izq)
        worksheet.set_column(15, 15, 9, fmt_texto)
        worksheet.set_column(16, 20, 1, fmt_texto)
    return output.getvalue()

def limpiar_monto(monto_str):
    monto_str = re.sub(r'[^\d.,]', '', str(monto_str))
    if not monto_str: return 0.0
    m_sep = re.search(r'([.,])(\d{1,2})$', monto_str)
    if m_sep:
        decimales = m_sep.group(2)
        enteros = re.sub(r'[^\d]', '', monto_str[:m_sep.start()])
        if not enteros: enteros = "0"
        return float(f"{enteros}.{decimales}")
    else:
        return float(re.sub(r'[^\d]', '', monto_str))

def extraer_y_formatear_fecha(texto):
    m_expl = re.search(r"(?:FECHA\s*DE\s*EMISI[OÓ]N|FECHA\s*DE\s*GENERACI[OÓ]N|FECHA)[^\d]*(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})", texto, re.I)
    if m_expl: return f"{int(m_expl.group(1)):02d}/{int(m_expl.group(2)):02d}/{m_expl.group(3)}"
    m_hacienda = re.search(r"\b(20[2-3]\d)\s*[\-\/]\s*(0[1-9]|1[0-2])\s*[\-\/]\s*([0-2]\d|3[0-1])\b", texto)
    if m_hacienda: return f"{int(m_hacienda.group(3)):02d}/{int(m_hacienda.group(2)):02d}/{m_hacienda.group(1)}"
    m_suelto = re.search(r"\b(0[1-9]|[12]\d|3[01])\s*[\/\-\.]\s*(0[1-9]|1[0-2])\s*[\/\-\.]\s*(20[2-3]\d)\b", texto)
    if m_suelto: return f"{int(m_suelto.group(1)):02d}/{int(m_suelto.group(2)):02d}/{m_suelto.group(3)}"
    return ""

def extraer_compras_nativo_pro(file_bytes, cliente_activo):
    motor = "Nativo"
    try:
        texto_completo = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                texto_pagina = page.extract_text(layout=False) # Layout false evita mezclar columnas en algunos casos
                texto_completo += (texto_pagina or "") + "\n"
                
        if len(texto_completo.strip()) < 50: return {"error": "El PDF parece ser una imagen sin texto incrustado."}

        t_clean = re.sub(r'\s+', ' ', texto_completo)
        t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
        tipo = "01"
        if m_ctrl:
            ctrl = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo: tipo = m_tipo.group(1)
        else: ctrl = ""
            
        if not ctrl: return {"error_tipo": "No se detectó un Número de Control DTE válido."}
        if tipo not in ["03", "05", "06"]: return {"error_tipo": f"El documento es DTE-{tipo}. Solo se admiten 03, 05 y 06."}

        nit_receptor_limpio = re.sub(r'[^0-9]', '', cliente_activo['nit'])
        dui_receptor_limpio = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))
        
        # --- NUEVA EXTRACCIÓN DE UUID AGRESIVA ---
        gen = ""
        m_url_gen = re.search(r"CODGEN=([A-F0-9-]+)", t_no_spaces)
        if m_url_gen:
            gen = m_url_gen.group(1).upper()
        else:
            # Busca exactamente 32 caracteres hexadecimales, ignorando guiones intermedios
            m_gen_raw = re.search(r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})", t_no_spaces)
            if m_gen_raw:
                limpio = m_gen_raw.group(1).replace("-", "")
                gen = f"{limpio[:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:]}"

        fecha = extraer_y_formatear_fecha(t_clean)

        # --- SEPARACIÓN EMISOR/RECEPTOR MEJORADA ---
        nit_prov = ""
        dui_prov = ""
        nom_prov = "⚠️ PROVEEDOR NUEVO"
        es_nuevo = True

        patron_identificadores = r"\b\d{4}\s*-\s*\d{6}\s*-\s*\d{3}\s*-\s*\d{1}\b|\b\d{14}\b|\b\d{8}\s*-\s*\d{1}\b|\b\d{9}\b"
        nits_encontrados = re.findall(patron_identificadores, texto_completo)
        nits_limpios = list(dict.fromkeys([re.sub(r'[^0-9]', '', n) for n in nits_encontrados]))

        # Eliminamos el NIT/DUI del receptor activo para que JAMÁS lo confunda con el proveedor
        nits_candidatos = [n for n in nits_limpios if n != nit_receptor_limpio and n != dui_receptor_limpio]

        proveedores_json = cargar_proveedores_json()

        # 1. Buscar en el cerebro central primero
        for n in nits_candidatos:
            if n in proveedores_json:
                nit_prov = n; nom_prov = proveedores_json[n]; es_nuevo = False; break

        # 2. Si no lo conoce, agarra el primer NIT que no sea el cliente
        if not nit_prov and nits_candidatos:
            nit_prov = nits_candidatos[0]

        if len(nit_prov) == 9: dui_prov = nit_prov

        if es_nuevo and nit_prov:
            palabras_basura = [
                "DOCUMENTO", "TRIBUTARIO", "ELECTRÓNICO", "ELECTRONICO", "REPRESENTACIÓN", "RECEPTOR", "CLIENTE", "EMISOR",
                "FACTURA", "CONSUMIDOR", "FACTURACION", "COMPROBANTE", "DIRECC", "CÓDIGO", "SELLO", "VERSIÓN", 
                "TRANSMISIÓN", "MODELO", "MINISTERIO", "HACIENDA", "COLONIA", "BOULEVARD", "CALLE", "AVENIDA", 
                "MUNICIPIO", "GIRO:", "GIRO", "ACTIVIDAD", "ECONOMICA", "ECONÓMICA", "TIPO ESTABLECIMIENTO", 
                "SUCURSAL", "AGENCIA", "PAGO DE", "TARJETA", "EFECTIVO", "FECHA", "HORA", "EMISIÓN", "GENERACIÓN", "TELÉFONO"
            ]
            
            lineas = texto_completo.split('\n')
            for L in lineas[:25]: # Buscar en las primeras líneas
                L = L.strip().upper()
                if len(L) < 5 or sum(c.isdigit() for c in L) / len(L) > 0.3: continue
                if any(b in L for b in palabras_basura): continue
                
                es_comercial = any(w in L for w in ["S.A.", "SA ", "C.V.", "CV ", "LTDA", "SOCIEDAD", "DISTRIBUIDORA", "FARMACIA", "GRUPO"])
                if es_comercial or (len(L) > 10 and "NIT" not in L and "NRC" not in L):
                    clean_name = re.split(r'\s{4,}|NIT|NRC', L)[0].strip()
                    if clean_name: 
                        nom_prov = clean_name
                        break

            if len(nom_prov) > 60 or nom_prov == "⚠️ PROVEEDOR NUEVO" or "ACTIVIDAD" in nom_prov: 
                nom_prov = "ESCRIBE EL NOMBRE AQUÍ"

        e, g, i, ret, perc, t = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        iva_calculado = False
        
        m_t = re.search(r"(?:Total a Pagar|Venta Total|Monto total|TOTAL|SUMA DE VENTAS)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
        if m_t: t = limpiar_monto(m_t.group(1))

        if t > 0:
            m_i = re.search(r"(?:Impuesto.*Agregado|IVA|13% IVA|20-Impuesto|I\.V\.A)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_i: i = limpiar_monto(m_i.group(1))
            
            m_ret = re.search(r"(?:Retenido|Retenci.n)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_ret: ret = limpiar_monto(m_ret.group(1))

            if i == 0.0 and tipo == "03":
                g = round(t / 1.13, 2)
                i = round(t - g, 2)
                iva_calculado = True
            elif i > 0:
                g = round(t - i + ret, 2)

        return {
            "fecha": fecha, "nit_prov": nit_prov, "dui_prov": dui_prov, "nom_prov": nom_prov, "tipo": tipo, "gen": gen, 
            "exe": e, "gra": g, "iva": i, "ret": ret, "perc": perc, "tot": t, "estado": "✅ OK", "iva_calc": iva_calculado,
            "es_nuevo": es_nuevo, "nit_nuevo": nit_prov, "motor": motor
        }
    except Exception as err: 
        return {"error": str(err)}

@st.dialog("⚠️ Seguro de Calidad de Compras")
def ventana_descarga_compras(df_resultados, nombre_archivo):
    st.write("Asegúrate de haber procesado únicamente los comprobantes que deseas declarar en el anexo de Compras antes de descargar.")
    st.download_button(label="📥 Confirmar y Descargar Anexo F-07", data=to_excel_hacienda_compras(df_resultados), file_name=nombre_archivo, type="primary")

# --- UI PRINCIPAL ---
st.markdown("<h2 style='font-family: Courier New, monospace; color: #003057; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("🛒 Extractor DTE (Compras)")

st.markdown(f"""
<div class="alerta-activo">
    <strong>RECEPTOR ACTUAL (Cliente Activo):</strong> {cliente['nombre']} (NIT/DUI: {cliente['nit']})
</div>
""", unsafe_allow_html=True)

if 'cola_revision' not in st.session_state: st.session_state.cola_revision = []
if 'comp_uploader_key' not in st.session_state: st.session_state.comp_uploader_key = str(time.time())
if 'db_compras' not in st.session_state: st.session_state.db_compras = pd.DataFrame()
if 'archivos_comp' not in st.session_state: st.session_state.archivos_comp = set()
if 'reporte_compras' not in st.session_state: st.session_state.reporte_compras = None

with st.sidebar:
    st.header("Carga de Compras")
    archivos = st.file_uploader("Arrastra facturas de proveedores (PDF)", type="pdf", accept_multiple_files=True, key=st.session_state.comp_uploader_key)
    
    if archivos and st.button("🚀 Procesar Compras", type="primary", use_container_width=True):
        extracted, duplicados, iva_calculado_files, intrusos, invalidos, corruptos = [], [], [], [], [], []
        nuevos_proveedores = {}
        nuevos_archivos = [f for f in archivos if f.name not in st.session_state.archivos_comp]

        if nuevos_archivos:
            with st.container():
                bar, txt_progreso = st.progress(0), st.empty()
                t_inicio, total = time.time(), len(nuevos_archivos)
                
                for idx, f in enumerate(nuevos_archivos):
                    if idx > 0 and idx % 50 == 0: gc.collect()

                    if idx > 0:
                        m, s = divmod(int(((time.time() - t_inicio) / idx) * (total - idx)), 60)
                        txt_progreso.markdown(f"📄 **Procesando:** {idx+1} de {total}<br>⏳ **Restante:** {m:02d}:{s:02d}", unsafe_allow_html=True)
                    else:
                        txt_progreso.markdown(f"📄 **Procesando:** 1 de {total}<br>⏳ Extrayendo datos...", unsafe_allow_html=True)
                    
                    file_bytes = f.read()
                    
                    # Verificación rápida de archivo PDF de 0 KB o dañado
                    if len(file_bytes) < 1024:
                        corruptos.append(f.name)
                        st.session_state.archivos_comp.add(f.name)
                        continue

                    res = extraer_compras_nativo_pro(file_bytes, cliente)
                    
                    codigo_gen = res.get('gen', '')
                    es_duplicado_memoria = not st.session_state.db_compras.empty and codigo_gen != "" and (st.session_state.db_compras['gen'] == codigo_gen).any()
                    es_duplicado_lote = any(d.get('gen') == codigo_gen for d in extracted) if codigo_gen != "" else False
                    
                    if "error_intruso" in res:
                        intrusos.append(f.name)
                        st.session_state.archivos_comp.add(f.name)
                    elif "error_tipo" in res:
                        invalidos.append(f.name)
                        st.session_state.archivos_comp.add(f.name)
                    elif es_duplicado_memoria or es_duplicado_lote:
                        duplicados.append(f.name)
                        st.session_state.archivos_comp.add(f.name)
                    elif "error" not in res:
                        fecha_str = str(res.get('fecha', '')).strip()
                        nom_prov_str = str(res.get('nom_prov', '')).strip()
                        
                        if res.get('tot', 0.0) == 0.0 or not res.get('gen') or not fecha_str or nom_prov_str == "ESCRIBE EL NOMBRE AQUÍ" or nom_prov_str == "": 
                            st.session_state.cola_revision.append({
                                "archivo": f.name,
                                "bytes": file_bytes,
                                "datos": res
                            })
                        else:
                            if res.get('iva_calc'): iva_calculado_files.append(f.name)
                            if res.get("es_nuevo") and res.get("nit_nuevo"): nuevos_proveedores[res["nit_nuevo"]] = res["nom_prov"]
                            res["archivo"] = f.name
                            extracted.append(res)
                        
                        st.session_state.archivos_comp.add(f.name)
                    else:
                        corruptos.append(f.name)
                        st.session_state.archivos_comp.add(f.name)
                        
                    bar.progress((idx + 1) / total)
                
                txt_progreso.success(f"✅ ¡{total} facturas escaneadas!")
            
            st.session_state.reporte_compras = {
                "intrusos": intrusos, "invalidos": invalidos, "duplicados": duplicados, 
                "iva_calc": iva_calculado_files, "nuevos_proveedores": nuevos_proveedores,
                "corruptos": corruptos
            }
            
            if extracted: 
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_compras.empty: st.session_state.db_compras = new_df
                else: st.session_state.db_compras = pd.concat([st.session_state.db_compras, new_df], ignore_index=True)

    st.divider()
    if st.button("🧹 Limpiar Memoria Compras", type="secondary", use_container_width=True):
        for key in ['db_compras', 'archivos_comp', 'reporte_compras', 'cola_revision']:
            if key in st.session_state: del st.session_state[key]
        st.session_state.comp_uploader_key = str(time.time()); st.rerun()

# --- 🚨 MÓDULO HITL CON VISOR NATIVO Y MENTE COLMENA 🚨 ---
if st.session_state.cola_revision:
    st.markdown("""
    <div class="inbox-revision">
        <h3 style="margin-top:0px; color:#ffaa00;">📥 Bandeja de Revisión Manual</h3>
        <p style="color:#aaa; margin-bottom:0px;">La Inteligencia Artificial encontró datos borrosos o incompletos. Selecciona el texto del PDF y pégalo aquí.</p>
    </div>
    """, unsafe_allow_html=True)
    
    total_cola = len(st.session_state.cola_revision)
    st.info(f"Quedan **{total_cola}** documento(s) por revisar.")
    
    item_actual = st.session_state.cola_revision[0]
    datos_actuales = item_actual["datos"]
    
    col_img, col_form = st.columns([1.5, 1]) # Columnas más anchas para el PDF
    
    with col_img:
        try:
            with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                # 1. Mostramos la imagen nítida (A prueba de bloqueos de Chrome)
                img = pdf.pages[0].to_image(resolution=300).original
                st.image(img, caption=f"📄 Vista Previa: {item_actual['archivo']}", use_container_width=True)
                
                # 2. Extraemos el texto crudo para que el contador pueda COPIAR y PEGAR
                texto_crudo = ""
                for page in pdf.pages:
                    texto_crudo += (page.extract_text(layout=False) or "") + "\n"
                
                st.markdown("📝 **Texto extraído (Selecciona y copia lo que necesites):**")
                # Esta caja permite seleccionar texto libremente
                st.text_area("Texto de la factura", value=texto_crudo.strip(), height=200, label_visibility="collapsed")
                
        except Exception as e:
            st.error("No se pudo cargar la vista previa de la imagen.")
            
    with col_form:
        st.markdown("### ✍️ Corrección Rápida")
        with st.form(key=f"form_revision_{item_actual['archivo']}"):
            f_fecha = st.text_input("📅 Fecha (DD/MM/YYYY) *", value=datos_actuales.get("fecha", ""))
            f_gen = st.text_input("🔑 Código de Generación (UUID) *", value=datos_actuales.get("gen", ""))
            
            nom_sugerido = datos_actuales.get("nom_prov", "")
            if nom_sugerido == "ESCRIBE EL NOMBRE AQUÍ" or "ACTIVIDAD" in nom_sugerido: nom_sugerido = ""
            f_nom = st.text_input("🏢 Razón Social del Proveedor *", value=nom_sugerido)
            
            f_tot = st.number_input("💰 Total a Pagar ($) *", value=float(datos_actuales.get("tot", 0.0)), format="%.2f")
            
            st.markdown("<br>", unsafe_allow_html=True)
            c_btn1, c_btn2 = st.columns(2)
            
            with c_btn1:
                if st.form_submit_button("✅ Aprobar y Guardar", type="primary", use_container_width=True):
                    if not f_fecha or not f_gen or not f_nom or f_tot <= 0:
                        st.error("Rellena todos los campos con (*) para continuar.")
                    else:
                        # Guardar el nombre en el cerebro central si es nuevo
                        nit_actual = datos_actuales.get("nit_prov", "")
                        if nit_actual: guardar_proveedor_rapido(nit_actual, f_nom.upper())

                        # --- LA MENTE COLMENA (Actualización en Cascada) ---
                        if nit_actual:
                            for i in range(1, len(st.session_state.cola_revision)):
                                if st.session_state.cola_revision[i]["datos"].get("nit_prov") == nit_actual:
                                    st.session_state.cola_revision[i]["datos"]["nom_prov"] = f_nom.upper()

                        datos_actuales["fecha"] = f_fecha
                        datos_actuales["gen"] = f_gen.upper()
                        datos_actuales["nom_prov"] = f_nom.upper()
                        datos_actuales["tot"] = f_tot
                        
                        if f_tot > 0 and datos_actuales["iva"] == 0:
                            datos_actuales["gra"] = round(f_tot / 1.13, 2)
                            datos_actuales["iva"] = round(f_tot - datos_actuales["gra"], 2)
                            datos_actuales["iva_calc"] = True
                            
                        datos_actuales["archivo"] = item_actual["archivo"]
                        
                        nuevo_df = pd.DataFrame([datos_actuales])
                        if st.session_state.db_compras.empty: st.session_state.db_compras = nuevo_df
                        else: st.session_state.db_compras = pd.concat([st.session_state.db_compras, nuevo_df], ignore_index=True)
                        
                        st.session_state.cola_revision.pop(0)
                        st.rerun()
                        
            with c_btn2:
                if st.form_submit_button("🗑️ Descartar Archivo", use_container_width=True):
                    st.session_state.cola_revision.pop(0)
                    st.rerun()
                    
    st.stop() 

# --- DASHBOARD DE RESULTADOS ---
if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### 📋 Alertas de Procesamiento Automático")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if rep.get("corruptos"):
            st.error(f"💀 **{len(rep['corruptos'])} Dañados** (PDFs rotos).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["corruptos"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Dañados**.")
    with c2:
        if rep.get("intrusos"):
            st.error(f"🚫 **{len(rep['intrusos'])} Ajenos** (Otro NIT).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["intrusos"]])}</div>', unsafe_allow_html=True)
        elif rep.get("invalidos"):
            st.error(f"⚠️ **{len(rep['invalidos'])} Ignorados** (No F-07).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["invalidos"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Rechazados**.")
    with c3:
        if rep["duplicados"]:
            st.error(f"🛑 **{len(rep['duplicados'])} Omitidos** (Duplicados).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["duplicados"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Omitidos**.")
    with c4:
        if rep["iva_calc"]:
            st.info(f"🧮 **{len(rep['iva_calc'])} IVA Calc.** (Al 13%).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["iva_calc"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 IVA Calc.** (Nativo).")
    st.divider()

    if rep.get("nuevos_proveedores"):
        st.markdown("### ✨ Guardado Rápido de Proveedores")
        st.info("Revisa el nombre, corrígelo si es necesario y guárdalo para actualizar la tabla al instante.")
        
        for nit, nombre_sug in list(rep["nuevos_proveedores"].items()):
            col1, col2, col3 = st.columns([2, 5, 2])
            with col1: st.text_input("NIT / DUI", value=nit, disabled=True, key=f"lbl_{nit}")
            with col2: nuevo_nom = st.text_input("Nombre Oficial", value=nombre_sug, key=f"nom_{nit}")
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Guardar y Actualizar", key=f"btn_{nit}", type="primary"):
                    guardar_proveedor_rapido(nit, nuevo_nom)
                    df = st.session_state.db_compras
                    mask = (df['nit_prov'] == nit) | (df['dui_prov'] == nit)
                    df.loc[mask, 'nom_prov'] = nuevo_nom.strip().upper()
                    st.session_state.db_compras = df
                    del st.session_state.reporte_compras["nuevos_proveedores"][nit]
                    st.rerun()
        st.divider()

# --- TABLAS DE RESULTADOS Y FILTROS DE BÚSQUEDA ---
if not st.session_state.db_compras.empty:
    df = st.session_state.db_compras.copy()
    
    st.markdown("### 🔍 Filtros de Auditoría Rápida")
    col_f1, col_f2 = st.columns([2, 1])
    
    with col_f1:
        busqueda_texto = st.text_input("Buscar Proveedor (Nombre, NIT, DUI o UUID) 🔎", placeholder="Ej. FREUND, 0614...")
    with col_f2:
        filtro_tipo = st.multiselect("Filtrar por Tipo DTE 📄", options=df['tipo'].unique(), default=df['tipo'].unique())
        
    df_filtrado = df.copy()
    if busqueda_texto:
        termino = busqueda_texto.upper()
        mask = (
            df_filtrado['nom_prov'].str.contains(termino, case=False, na=False) |
            df_filtrado['nit_prov'].str.contains(termino, na=False) |
            df_filtrado['dui_prov'].str.contains(termino, na=False) |
            df_filtrado['gen'].str.contains(termino, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask]
        
    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]
    
    st.divider()

    tab1, tab2 = st.tabs(["📊 F-07 Compras a Contribuyentes", "🔍 Auditoría Total"])
    
    with tab1:
        df_hacienda = pd.DataFrame()
        df_hacienda["A. Fecha Emisión"] = df_filtrado["fecha"]
        df_hacienda["B. Clase"] = "4"
        df_hacienda["C. Tipo Doc"] = df_filtrado["tipo"]
        df_hacienda["D. Num Documento"] = df_filtrado["gen"]
        df_hacienda["E. NIT/NRC Prov"] = df_filtrado["nit_prov"]
        df_hacienda["F. Nombre Prov"] = df_filtrado["nom_prov"]
        df_hacienda["G. Compra Ext/NS"] = df_filtrado["exe"]
        df_hacienda["H. Internacion Ext/NS"] = 0.00
        df_hacienda["I. Importacion Ext/NS"] = 0.00
        df_hacienda["J. Compra Gravada"] = df_filtrado["gra"]
        df_hacienda["K. Inter. Gravada Bienes"] = 0.00
        df_hacienda["L. Impor. Gravada Bienes"] = 0.00
        df_hacienda["M. Impor. Gravada Serv"] = 0.00
        df_hacienda["N. Crédito Fiscal (IVA)"] = df_filtrado["iva"]
        df_hacienda["O. Total Compras"] = df_filtrado["tot"]
        df_hacienda["P. DUI Prov"] = df_filtrado["dui_prov"]
        df_hacienda["Q. Tipo Operacion"] = "1"
        df_hacienda["R. Clasificacion"] = "1"
        df_hacienda["S. Sector"] = "1"
        df_hacienda["T. Tipo Costo/Gasto"] = "1"
        df_hacienda["U. Num Anexo"] = "3"

        st.dataframe(df_hacienda.style.format({col: "{:.2f}" for col in df_hacienda.columns[6:15]}), hide_index=True, use_container_width=True)
        
        if st.button("📥 Generar Excel para Hacienda (Resultados Filtrados)", type="primary"): 
            ventana_descarga_compras(df_hacienda, "F07_Compras_Proveedores.xlsx")
            
    with tab2:
        st.write(f"📊 Registros listos: **{len(df_filtrado)}** de **{len(df)}** procesados.")
        st.dataframe(df_filtrado, use_container_width=True)
