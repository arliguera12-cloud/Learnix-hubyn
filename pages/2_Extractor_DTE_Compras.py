import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import pytesseract
import json
import os
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

# --- DISEÑO MODO OSCURO Y PESTAÑAS (ESTILO VENTAS) ---
estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    
    div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] { 
        background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; transition: 0.3s;
    }
    div.stButton > button[kind="primary"] *, div.stDownloadButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="primary"]:hover, div.stDownloadButton > button[kind="primary"]:hover { background-color: #00407A !important; }
    
    div.stButton > button[kind="secondary"] { background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; }
    div.stButton > button[kind="secondary"] * { color: #FFFFFF !important; font-weight: bold !important; }

    div[data-testid="stAlert"] { min-height: 80px; display: flex; align-items: center; }
    .stAlert * { color: inherit !important; }
    
    .scroll-list {
        max-height: 150px; overflow-y: auto; padding: 10px;
        background-color: #111111; border-radius: 5px; border: 1px solid #333;
        font-family: monospace; font-size: 13px; color: #66ff66;
    }
    
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { color: #4DA8DA !important; border-bottom-color: #4DA8DA !important; }
    .stTabs [data-baseweb="tab-list"] button { color: #777777 !important; }
    [data-testid="stStatusWidget"], [data-testid="stExpander"] { background-color: #161616 !important; border: 1px solid #444444 !important; border-radius: 6px; }

    .alerta-activo { padding: 10px; border-radius: 6px; border-left: 4px solid #00407A; background-color: #111111; color: white; margin-bottom: 15px; font-size: 14px; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# --- MEGA-DICCIONARIO DE PROVEEDORES ---
PROVEEDORES_RESPALDO = {
    "06141603991030": "PRICESMART EL SALVADOR, S.A. DE C.V.",
    "06142810921030": "SERVICIOS FINANCIEROS, S.A. DE C.V.",
    "06142108061015": "MAK MEATS, S.A. DE C.V.",
    "06141512201045": "DELIVERY HERO EL SALVADOR (PEDIDOSYA)",
    "06141905991030": "UNIGAS DE EL SALVADOR, S.A DE C.V.",
    "06142904720020": "TIENDA MORENA S.A DE C.V.",
    "06143008161116": "MARZAURI, S.A. DE C.V. (PUERTO PLAZA)",
    "06142609111020": "DISTRIBUIDORA AXBEN, S.A. DE C.V.",
    "05092506721016": "PEDRO RAMIREZ RAMIREZ",
    "05090706851019": "FRANCISCO MELARA (LACTEOS CARMENCITA)",
    "06142101881394": "KARLA GUADALUPE VASQUEZ HERNANDEZ",
    "06142308031030": "PAPELERA SALVADOREÑA RZ, S.A. DE C.V.",
    "05092209761017": "ROBERTO CARLOS BOLAÑOS BONILLA",
    "06141101690011": "CALLEJA, S.A. DE C.V. (SUPER SELECTOS)",
    "06142704071095": "BELCA EL SALVADOR, S.A. DE C.V.",
    "06140607101084": "DISTRIBUCION SALVADOREÑA, S.A. DE C.V.",
    "06141503071023": "GRUHERCA SA DE CV",
    "06140902840024": "LACTEOS DEL CORRAL, S.A. DE C.V.",
    "02040305560017": "GIRON SANTOS RICARDO ERNESTO (SHELL)",
    "06141106071025": "FARMACIAS EUROPEAS, S.A. DE C.V. (FARMAVALUE)",
    "06142310750039": "HOSPITAL DE DIAGNOSTICO S.A DE C.V.",
    "06142709760012": "OMNISPORT, S.A. DE C.V.",
    "06140905981011": "SERVICIOS TECNICOS MEDICOS, S.A. DE C.V.",
    "06142801031030": "SALON & BEAUTY CONCEPTS, S.A. DE C.V.",
    "06143107971090": "OPERADORA DEL SUR S.A. DE C.V. (DESPENSA DE DON JUAN)",
    "06141909001034": "RAMIREZ VENTURA S.A. DE C.V.",
    "96422206810012": "TROPIGAS DE EL SALVADOR, S.A.", 
    "06142206810012": "TROPIGAS DE EL SALVADOR, S.A.",
    "06141811971019": "MULTI-TECNOLOGIA, S.A. DE C.V.",
    "06140702231050": "BEBIDAS EXCLUSIVAS, S.A. DE C.V.",
    "06142307091063": "CENTROAMERICA COMERCIAL S.A. DE C.V. (DOLLARCITY)",
    "06142212650014": "FARMACIA SAN NICOLAS S.A DE C.V.",
    "0614167951013": "DISTRIBUIDORA DE ELECTRICIDAD DEL SUR, S.A DE C.V. (DELSUR)",
    "06142008011037": "COMERCIALIZADORA INTERAMERICANA S.A. DE C.V. (CBC/PEPSI)",
    "06142511041016": "COMERCIAL POZUELO EL SALVADOR, S.A. DE C.V.",
    "06142702061050": "GOOD PRICE, S.A. DE C.V.",
    "05112811590018": "BENJAMIN MOLINA VILANOVA (TEXACO)",
    "06142803730056": "ASEGURADORA AGRICOLA COMERCIAL, S.A. (ACSA)",
    "06142212991016": "ASEGURADORA ABANK, S.A., SEGUROS DE PERSONAS",
    "06142811081044": "ASSA COMPAÑIA DE SEGUROS, S.A.",
    "06142903850011": "SEGUROS ATLANTIDA, S.A."
}

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
        
        def get_max_len(col_idx):
            return max(df.iloc[:, col_idx].astype(str).map(len).max() if not df.empty else 15, 15) + 2

        worksheet.set_column(0, 0, 10, fmt_texto)               # A: Fecha
        worksheet.set_column(1, 1, 1, fmt_texto)                # B: Clase
        worksheet.set_column(2, 2, 2, fmt_texto)                # C: Tipo Doc
        worksheet.set_column(3, 3, get_max_len(3), fmt_texto)   # D: Num Doc
        worksheet.set_column(4, 4, 14, fmt_texto)               # E: NIT
        worksheet.set_column(5, 5, get_max_len(5), fmt_texto)   # F: Nombre Prov
        worksheet.set_column(6, 14, 10.71, fmt_num_izq)         # G a O: Montos
        worksheet.set_column(15, 15, 9, fmt_texto)              # P: DUI
        worksheet.set_column(16, 20, 1, fmt_texto)              # Q a U: Fijas

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

# --- MOTOR PRINCIPAL AUTÓNOMO ---
def extraer_compras_v3(file_bytes, cliente_activo):
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

        # 1. FILTRO DE NÚMERO DE CONTROL Y TIPO
        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
        tipo = "01"
        if m_ctrl:
            ctrl = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo: tipo = m_tipo.group(1)
        else: ctrl = ""
            
        if not ctrl: return {"error_tipo": "No se detectó un Número de Control DTE válido."}
        if tipo not in ["03", "05", "06"]: return {"error_tipo": f"El documento es tipo DTE-{tipo}. Solo se admiten 03, 05 y 06 para el Anexo F-07."}

        # 2. VERIFICAR INTRUSOS
        nit_receptor_limpio = re.sub(r'[^0-9]', '', cliente_activo['nit'])
        dui_receptor_limpio = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))
        texto_solo_numeros = re.sub(r'[^0-9]', '', t_clean)
        
        es_documento_valido = False
        if nit_receptor_limpio == "00000000000000": es_documento_valido = True
        elif len(nit_receptor_limpio) >= 9 and nit_receptor_limpio in texto_solo_numeros: es_documento_valido = True
        elif len(dui_receptor_limpio) >= 8 and dui_receptor_limpio in texto_solo_numeros: es_documento_valido = True
            
        if not es_documento_valido: return {"error_intruso": f"Este documento no le pertenece al cliente activo."}

        # 3. IDENTIFICADORES Y FECHA
        gen = ""
        gen_m = re.search(r"(?:C[OÓ]DIGO\s*DE\s*GENERACI[OÓ]N|C[OÓ]D\.\s*GENERACI[OÓ]N)[^\w]*([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})", texto_completo, re.I)
        if gen_m:
            raw_gen = gen_m.group(1).upper().replace("-", "")
            gen = f"{raw_gen[:8]}-{raw_gen[8:12]}-{raw_gen[12:16]}-{raw_gen[16:20]}-{raw_gen[20:]}"
        else:
            uuids = re.findall(r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})", t_no_spaces)
            if uuids:
                 for u in uuids:
                     if not re.search(r"SELLO.*?RECEPC.*?{}".format(u), t_no_spaces):
                         raw_gen = u.replace("-", "")
                         gen = f"{raw_gen[:8]}-{raw_gen[8:12]}-{raw_gen[12:16]}-{raw_gen[16:20]}-{raw_gen[20:]}"
                         break
                 if not gen:
                     raw_gen = uuids[0].replace("-", "")
                     gen = f"{raw_gen[:8]}-{raw_gen[8:12]}-{raw_gen[12:16]}-{raw_gen[16:20]}-{raw_gen[20:]}"

        fecha = extraer_y_formatear_fecha(t_clean)
        if not fecha:
            try:
                with pdfplumber.open(BytesIO(file_bytes)) as pdf_temp:
                    if len(pdf_temp.pages) > 0:
                        p0 = pdf_temp.pages[0]
                        crop_box = (0, 0, p0.width, p0.height * 0.50)
                        top_img = p0.crop(crop_box).to_image(resolution=300)
                        config_ocr = r'--oem 3 --psm 6'
                        ocr_top = pytesseract.image_to_string(top_img.original, lang='spa', config=config_ocr)
                        ocr_top_clean = re.sub(r'\s+', ' ', ocr_top)
                        fecha = extraer_y_formatear_fecha(ocr_top_clean)
                        if fecha and motor == "Nativo": motor = "Nativo + OCR Fecha"
            except: pass

        # --- ESCUDO ANTI-RECEPTOR: AISLAR LA MITAD SUPERIOR (EL EMISOR) ---
        texto_emisor = re.split(r"(?i)\b(?:RECEPTOR|CLIENTE)\b", texto_completo)[0]
        if len(texto_emisor) < 50: 
            texto_emisor = texto_completo

        # 4. EXTRACCIÓN PROVEEDOR (LÓGICA CON PRIORIDAD DE BASE DE DATOS)
        nit_prov = ""
        dui_prov = ""
        nom_prov = "⚠️ PROVEEDOR NUEVO"
        es_nuevo = True

        patron_identificadores = r"\b\d{4}\s*-\s*\d{6}\s*-\s*\d{3}\s*-\s*\d{1}\b|\b\d{14}\b|\b\d{8}\s*-\s*\d{1}\b|\b\d{9}\b"
        
        # Buscar en el bloque del Emisor primero
        nits_encontrados = re.findall(patron_identificadores, texto_emisor)
        if not nits_encontrados: 
            nits_encontrados = re.findall(patron_identificadores, texto_completo)
            
        nits_limpios = list(dict.fromkeys([re.sub(r'[^0-9]', '', n) for n in nits_encontrados]))

        proveedores_json = cargar_proveedores_json()

        for n in nits_limpios:
            if n in proveedores_json:
                nit_prov = n; nom_prov = proveedores_json[n]; es_nuevo = False; break
            elif n in PROVEEDORES_RESPALDO:
                nit_prov = n; nom_prov = PROVEEDORES_RESPALDO[n]; es_nuevo = False; break

        if not nit_prov:
            m_emisor = re.search(r"EMISOR[\s\S]{1,250}?(?:NIT|N\s*I\s*T|N\.I\.T)[^\d]*([\d\-\s]{9,17})", texto_emisor, re.I)
            if m_emisor:
                posible_nit = re.sub(r'[^0-9]', '', m_emisor.group(1))
                if len(posible_nit) in [9, 14] and posible_nit != nit_receptor_limpio: nit_prov = posible_nit

        if not nit_prov:
            m_nits = re.finditer(r"(?:NIT|N\s*I\s*T)[^\d]*([\d\-\s]{9,17})", texto_emisor, re.I)
            for m in m_nits:
                posible_nit = re.sub(r'[^0-9]', '', m.group(1))
                if len(posible_nit) in [9, 14]:
                    if nit_receptor_limpio == "00000000000000": nit_prov = posible_nit; break
                    elif posible_nit != nit_receptor_limpio and posible_nit != dui_receptor_limpio: nit_prov = posible_nit; break

        if not nit_prov and nits_limpios:
            if nit_receptor_limpio == "00000000000000": nit_prov = nits_limpios[0]
            else:
                for n in nits_limpios:
                    if n != nit_receptor_limpio and n != dui_receptor_limpio: nit_prov = n; break

        if len(nit_prov) == 9: dui_prov = nit_prov

        if es_nuevo and nit_prov:
            nom_prov = "⚠️ PROVEEDOR NUEVO"
            nombres_receptor = [n for n in cliente_activo['nombre'].split() if len(n) > 3]
            
            # --- 1. LISTA NEGRA EXTREMA (ANTI-METADATOS Y DIRECCIONES) ---
            palabras_basura = [
                "DOCUMENTO", "CREDITO", "CRÉDITO", "FISCAL", "TRIBUTARIO", "RECEPTOR", "CLIENTE", "EMISOR", 
                "FACTURACION", "FACTURACIÓN", "COMPROBANTE", "RECEP", "DIRECC", "A QUIEN INTERESE", 
                "NÚMERO DE CONTROL", "NUMERO DE CONTROL", "CÓDIGO", "SELLO", "VERSIÓ", "VERSIÓN", "TIPO DE", 
                "TRANSMISIÓN", "TRANSMISION", "MODELO", "NÚM.", "NUM.", "INFORMACIÓN", "INFORMACION", 
                "AQUI CONTENIDA", "AQUÍ CONTENIDA", "VÁLIDO", "VALIDO", "MINISTERIO", "HACIENDA", "PORTAL",
                "COLONIA", "BOULEVARD", "BLVD", "CALLE", "AVENIDA", "RESIDENCIAL", "BARRIO", "EDIFICIO", "LOCAL", 
                "KILOMETRO", "KM", "CARR.", "CARRETERA", "PANAMERICAN", "CENTRO COMERCIAL", "PLAZA", "DEPARTAMENTO", "MUNICIPIO",
                "GIRO:", "GIRO", "TIPO ESTABLECIMIENTO", "ORDEN DE COMPRA", "TASA MUNICIPAL", "CARGO",
                "CASA MATRIZ", "SUCURSAL", "AGENCIA", "PAGO DE", "CONCEPTO DE", "COMPAÑIA DE SEGUROS",
                "PREVIO", "NORMAL", "ANULADO", "SUJETO EXCLUIDO", "EXCLUIDO",
                "CAJERO", "TERMINAL", "EFECTIVO", "VUELTO", "CAMBIO", "CONTADO", "TARJETA", "VISA", "MASTERCARD", "CAJA", "VENTA",
                "FECHA", "HORA", "EMISIÓN", "EMISION", "GENERACIÓN", "GENERACION", "AM", "PM",
                "RESOLUCION", "RESOLUCIÓN", "AUTORIZACION", "AUTORIZACIÓN", "CORRELATIVO", "RANGO", "DEL", "AL",
                "PAGINA", "PÁGINA", "WWW", "HTTP", ".COM", "EMAIL", "CORREO", "TELÉFONO", "TELEFONO", "CELULAR", "PBX", "FAX"
            ]
            
            # --- 2. CAZADOR DE ETIQUETAS EXACTAS (PRIORIDAD 1) ---
            regex_nombres = r"(?:Nombre, denominaci[oó]n o raz[oó]n social|Nombre o raz[oó]n social|Raz[oó]n social|Nombre comercial|Nombre)\s*[:]?\s*([^\n]+)"
            m_nombre_exacto = re.search(regex_nombres, texto_emisor, re.I)
            
            if m_nombre_exacto:
                clean_name = m_nombre_exacto.group(1).strip()
                clean_name = re.split(r'\s{4,}|NIT|NRC|Registro|Giro', clean_name, flags=re.I)[0].strip()
                if clean_name and len(clean_name) > 3 and not any(b in clean_name.upper() for b in palabras_basura):
                    nom_prov = clean_name.upper()
            
            # --- 3. BÚSQUEDA LÓGICA POR LÍNEAS (PRIORIDAD 2 - Si no hay etiqueta) ---
            if nom_prov == "⚠️ PROVEEDOR NUEVO":
                lineas = texto_emisor.split('\n')
                nit_line_idx = -1
                for i, L in enumerate(lineas):
                    if nit_prov in re.sub(r'[^0-9]', '', L):
                        nit_line_idx = i; break
                
                start_idx = max(0, nit_line_idx - 4) if nit_line_idx != -1 else 0
                end_idx = min(len(lineas), nit_line_idx + 5) if nit_line_idx != -1 else len(lineas)
                
                for i in range(start_idx, end_idx):
                    L = lineas[i].strip().upper()
                    if not L or len(L) < 5: continue
                    
                    # Ignorar si es UUID, tiene formato de fecha/hora, o es 80% números (Ej. Teléfonos largos)
                    if re.search(r"[A-F0-9]{8}-?[A-F0-9]{4}-?", L, re.I): continue
                    if re.search(r"\d{2}/\d{2}/\d{4}|\d{2}:\d{2}:\d{2}", L): continue 
                    num_count = sum(c.isdigit() for c in L)
                    if num_count / len(L) > 0.5: continue
                    
                    if any(b in L for b in palabras_basura) or any(n in L for n in nombres_receptor): continue
                    
                    es_comercial = any(w in L for w in ["S.A.", "SA ", "C.V.", "CV ", "LTDA", "SOCIEDAD", "DISTRIBUIDORA", "SEGUROS", "FARMACIA", "ASOCIACION"])
                    
                    if re.search(r'[A-Z]{5,}', L) and "NIT:" not in L and "NRC:" not in L:
                        clean_name = re.split(r'\s{4,}|NIT|NRC', L)[0].strip()
                        
                        if es_comercial and len(clean_name) < 25 and i > 0:
                            prev_L = lineas[i-1].strip().upper()
                            if len(prev_L) > 3 and not any(b in prev_L for b in palabras_basura) and not re.search(r"[A-F0-9]{8}-|\d{2}:\d{2}", prev_L):
                                clean_name = f"{prev_L} {clean_name}"
                        
                        if clean_name and es_comercial:
                            nom_prov = clean_name; break
                        elif clean_name and nom_prov == "⚠️ PROVEEDOR NUEVO":
                            nom_prov = clean_name

            # --- LIMPIEZA FINAL DE PUNTUACIÓN EXTREMA ---
            if nom_prov != "⚠️ PROVEEDOR NUEVO":
                nom_prov = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", nom_prov).strip()

            if len(nom_prov) > 60 or nom_prov == "⚠️ PROVEEDOR NUEVO": 
                nom_prov = "ESCRIBE EL NOMBRE AQUÍ"

        nit_nuevo = nit_prov

        # 5. CEREBRO MATEMÁTICO AUTÓNOMO
        e, g, i, ret, perc, t = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        iva_calculado = False
        
        m_ret = re.search(r"(?:Retenido|Retenci.n)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
        if m_ret: ret = limpiar_monto(m_ret.group(1))
        
        m_perc = re.search(r"(?:Percibido|Percepci.n)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
        if m_perc: perc = limpiar_monto(m_perc.group(1))

        fovial, cotrans = 0.0, 0.0
        m_fovial_line = re.search(r"Fovial.{0,60}", texto_completo, re.I)
        if m_fovial_line:
            nums = re.findall(r"\d+\.\d{2,4}", m_fovial_line.group(0))
            if nums: fovial = max([float(n) for n in nums]) 
            
        m_cotrans_line = re.search(r"Cotrans.{0,60}", texto_completo, re.I)
        if m_cotrans_line:
            nums = re.findall(r"\d+\.\d{2,4}", m_cotrans_line.group(0))
            if nums: cotrans = max([float(n) for n in nums])
            
        e = fovial + cotrans 

        montos_brutos = re.findall(r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean)
        valores = sorted(list(set([limpiar_monto(m) for m in montos_brutos])), reverse=True)
        valores = [v for v in valores if v > 0] 
        
        encontrado = False
        for val_t in valores:
            if encontrado: break
            for val_g in valores:
                if val_g >= val_t: continue
                for val_i in valores:
                    if val_i >= val_g: continue
                    if abs(round(val_g * 0.13, 2) - round(val_i, 2)) <= 0.05:
                        if abs(round((val_g + val_i + e + perc - ret), 2) - round(val_t, 2)) <= 0.05:
                            g, i, t = val_g, val_i, val_t
                            encontrado = True
                            break

        if not encontrado:
            m_g = re.search(r"(?:Suma Total de Operaciones|Sub-Total|Sub Total|Sumatoria de ventas|Ventas Gravadas|Subtotal-?)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_g: g = limpiar_monto(m_g.group(1))
            
            m_i = re.search(r"(?:Impuesto.*Agregado|IVA|13% IVA|20-Impuesto|I\.V\.A)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_i: i = limpiar_monto(m_i.group(1))
                
            m_t = re.search(r"(?:Total a Pagar|Venta Total|Monto total|TOTAL|SUMA DE VENTAS)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_t: t = limpiar_monto(m_t.group(1))

            if t > 0 and i > 0 and (g == 0.0 or abs(round(g * 0.13, 2) - round(i, 2)) > 0.05):
                g = round(t - i - e - perc + ret, 2)
                
            if t > 0 and i == 0.0 and tipo == "03":
                g = round((t - e + ret - perc) / 1.13, 2)
                i = round(t - e + ret - perc - g, 2)
                iva_calculado = True

        return {
            "fecha": fecha, "nit_prov": nit_prov, "dui_prov": dui_prov, "nom_prov": nom_prov, "tipo": tipo, "gen": gen, 
            "exe": e, "gra": g, "iva": i, "ret": ret, "perc": perc, "tot": t, "estado": "✅ OK", "iva_calc": iva_calculado,
            "es_nuevo": es_nuevo, "nit_nuevo": nit_nuevo, "motor": motor
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

if 'comp_uploader_key' not in st.session_state: st.session_state.comp_uploader_key = str(time.time())
if 'db_compras' not in st.session_state: st.session_state.db_compras = pd.DataFrame()
if 'archivos_comp' not in st.session_state: st.session_state.archivos_comp = set()
if 'reporte_compras' not in st.session_state: st.session_state.reporte_compras = None

with st.sidebar:
    st.header("Carga de Compras")
    archivos = st.file_uploader("Arrastra facturas de proveedores (PDF)", type="pdf", accept_multiple_files=True, key=st.session_state.comp_uploader_key)
    
    if archivos and st.button("🚀 Procesar Compras", type="primary", width="stretch"):
        extracted, vacios_deteccion, duplicados, iva_calculado_files, intrusos, invalidos = [], [], [], [], [], []
        nuevos_proveedores = {}
        nuevos_archivos = [f for f in archivos if f.name not in st.session_state.archivos_comp]

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
                    res = extraer_compras_v3(file_bytes, cliente)
                    
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
                        if res.get('tot', 0.0) == 0.0 or not res.get('gen') or not fecha_str: 
                            vacios_deteccion.append(f.name)
                            
                        if res.get('iva_calc'): iva_calculado_files.append(f.name)
                        
                        if res.get("es_nuevo") and res.get("nit_nuevo"):
                            nuevos_proveedores[res["nit_nuevo"]] = res["nom_prov"]
                            
                        res["archivo"] = f.name
                        extracted.append(res)
                        st.session_state.archivos_comp.add(f.name)
                    else:
                        st.sidebar.error(f"❌ {res['error']} ({f.name})")
                        
                    bar.progress((idx + 1) / total)
                
                txt_progreso.success(f"✅ ¡{total} facturas procesadas!")
            
            st.session_state.reporte_compras = {
                "intrusos": intrusos, "invalidos": invalidos, "duplicados": duplicados, 
                "vacios": vacios_deteccion, "iva_calc": iva_calculado_files,
                "nuevos_proveedores": nuevos_proveedores
            }
            
            if extracted: 
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_compras.empty: st.session_state.db_compras = new_df
                else: st.session_state.db_compras = pd.concat([st.session_state.db_compras, new_df], ignore_index=True)

    st.divider()
    if st.button("🧹 Limpiar Memoria Compras", type="secondary", width="stretch"):
        for key in ['db_compras', 'archivos_comp', 'reporte_compras']:
            if key in st.session_state: del st.session_state[key]
        st.session_state.comp_uploader_key = str(time.time()); st.rerun()

# --- DASHBOARD ---
if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### 📋 Alertas de Procesamiento")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if rep.get("intrusos"):
            st.error(f"🚫 **{len(rep['intrusos'])} Ajenos** (DTE de otra empresa).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["intrusos"]])}</div>', unsafe_allow_html=True)
        elif rep.get("invalidos"):
            st.error(f"⚠️ **{len(rep['invalidos'])} Ignorados** (No son F-07).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["invalidos"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Rechazados**.")
    with c2:
        if rep["vacios"]:
            st.error(f"🚨 **{len(rep['vacios'])} Incompletos** (Falta Fecha, Total o Código).")
            with st.expander("Ver lista"): st.markdown(f'<div class="scroll-list">{"".join([f"• {a}<br>" for a in rep["vacios"]])}</div>', unsafe_allow_html=True)
        else: st.success("✅ **0 Incompletos**.")
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
        st.markdown("### ✨ Guardado Rápido de Proveedores (Modo Aprendizaje)")
        st.info("Hemos detectado proveedores nuevos en esta carga. Revisa el nombre, corrígelo si es necesario y guárdalo para actualizar la tabla al instante.")
        
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
        
    # --- APLICACIÓN EN TIEMPO REAL DE LOS FILTROS ---
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

        st.dataframe(df_hacienda.style.format({col: "{:.2f}" for col in df_hacienda.columns[6:15]}), hide_index=True, width="stretch")
        
        # El Excel descargará únicamente lo que el usuario haya filtrado visualmente
        if st.button("📥 Generar Excel para Hacienda (Resultados Filtrados)", type="primary"): 
            ventana_descarga_compras(df_hacienda, "F07_Compras_Proveedores.xlsx")
            
    with tab2:
        st.write(f"📊 Registros mostrados: **{len(df_filtrado)}** de **{len(df)}** en memoria.")
        st.dataframe(df_filtrado, width="stretch")
