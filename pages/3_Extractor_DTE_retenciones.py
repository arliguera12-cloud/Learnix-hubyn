import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import json
import os
import gc
from io import BytesIO

# --- VERIFICACIÓN DE SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Retenciones.")
    st.stop()

cliente = st.session_state.cliente_activo

st.set_page_config(page_title="Extraer DTE Retenciones", layout="wide", page_icon="✂️")

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] { background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; transition: 0.3s; }
    div.stButton > button[kind="primary"] *, div.stDownloadButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div.stButton > button[kind="secondary"] { background-color: #2A2A2A !important; border: 1px solid #555555 !important; border-radius: 6px; }
    div.stButton > button[kind="secondary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    .alerta-activo { padding: 10px; border-radius: 6px; border-left: 4px solid #00407A; background-color: #111111; color: white; margin-bottom: 15px; font-size: 14px; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] { min-width: 45% !important; flex: 1 1 45% !important; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

def cargar_proveedores_json():
    if os.path.exists("data/proveedores.json"):
        try:
            with open("data/proveedores.json", "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def limpiar_monto(monto_str):
    monto_str = re.sub(r'[^\d.,]', '', str(monto_str))
    if not monto_str: return 0.0
    m_sep = re.search(r'([.,])(\d{1,2})$', monto_str)
    if m_sep:
        decimales = m_sep.group(2)
        enteros = re.sub(r'[^\d]', '', monto_str[:m_sep.start()])
        if not enteros: enteros = "0"
        return float(f"{enteros}.{decimales}")
    return float(re.sub(r'[^\d]', '', monto_str))

def extraer_y_formatear_fecha(texto):
    m_hacienda = re.search(r"\b(20[2-3]\d)\s*[\-\/]\s*(0[1-9]|1[0-2])\s*[\-\/]\s*([0-2]\d|3[0-1])\b", texto)
    if m_hacienda: return f"{int(m_hacienda.group(3)):02d}/{int(m_hacienda.group(2)):02d}/{m_hacienda.group(1)}"
    m_suelto = re.search(r"\b(\d{1,2})\s*[\/\-\.]\s*(\d{1,2})\s*[\/\-\.]\s*(20[2-3]\d)\b", texto)
    if m_suelto: 
        p1, p2, y = int(m_suelto.group(1)), int(m_suelto.group(2)), m_suelto.group(3)
        if p1 <= 12 and p2 > 12: return f"{p2:02d}/{p1:02d}/{y}"
        elif p2 <= 12 and p1 > 12: return f"{p1:02d}/{p2:02d}/{y}"
        elif p2 <= 12 and p1 <= 31: return f"{p1:02d}/{p2:02d}/{y}"
    return ""

def extraer_retencion_nativa(file_bytes, cliente_activo):
    try:
        texto_completo = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages: texto_completo += (page.extract_text() or "") + "\n"
                
        if len(texto_completo.strip()) < 50: return {"error": "El PDF parece ser una imagen."}

        t_clean = re.sub(r'\s+', ' ', texto_completo)
        t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
        tipo = "07" # Por defecto asumimos DTE-07
        if m_ctrl:
            ctrl = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo: tipo = m_tipo.group(1)
            
        if tipo != "07": return {"error_tipo": f"El documento es DTE-{tipo}. Solo se admiten DTE-07 (Retenciones)."}

        nit_cliente_limpio = re.sub(r'[^0-9]', '', cliente_activo['nit'])
        
        gen = ""
        m_gen_raw = re.search(r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})", t_no_spaces)
        if m_gen_raw:
            limpio = m_gen_raw.group(1).replace("-", "")
            gen = f"{limpio[:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:]}"

        fecha = extraer_y_formatear_fecha(t_clean)

        nit_prov = ""
        nom_prov = "⚠️ RECEPTOR DESCONOCIDO"

        patron_identificadores = r"\b\d{4}\s*[-]?\s*\d{6}\s*[-]?\s*\d{3}\s*[-]?\s*\d{1}\b|\b\d{14}\b"
        nits_encontrados = re.findall(patron_identificadores, texto_completo)
        nits_limpios = list(dict.fromkeys([re.sub(r'[^0-9]', '', n) for n in nits_encontrados]))
        nits_candidatos = [n for n in nits_limpios if n != nit_cliente_limpio]

        proveedores_json = cargar_proveedores_json()
        for n in nits_candidatos:
            if n in proveedores_json:
                nit_prov = n
                nom_prov = proveedores_json[n].get("nombre", "")
                break

        if not nit_prov and nits_candidatos: nit_prov = nits_candidatos[0]

        # Extraer montos: Base Sujeta y Retención (1%)
        base, ret = 0.0, 0.0
        montos_brutos = re.findall(r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean)
        valores = sorted(list(set([limpiar_monto(m) for m in montos_brutos])), reverse=True)
        valores = [v for v in valores if v > 0] 

        for v in valores:
            retencion_calc = round(v * 0.01, 2)
            if any(abs(r - retencion_calc) <= 0.02 for r in valores if r < v):
                base = v
                ret = retencion_calc
                break

        if base == 0.0:
            m_base = re.search(r"(?:Monto Sujeto|Sujeto a Retenci.n)[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_base: base = limpiar_monto(m_base.group(1))
            m_ret = re.search(r"(?:Impuesto Retenido|Retenci.n 1%)[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_ret: ret = limpiar_monto(m_ret.group(1))

        return {
            "fecha": fecha, "nit_prov": nit_prov, "nom_prov": nom_prov, "tipo": tipo, "gen": gen, 
            "base": base, "ret": ret, "estado": "✅ OK"
        }
    except Exception as err: 
        return {"error": str(err)}

st.markdown("<h2 style='font-family: Courier New, monospace; color: #003057; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("✂️ Extractor DTE (Retenciones 1%)")

st.markdown(f"""
<div class="alerta-activo">
    <strong>AGENTE DE RETENCIÓN (Cliente Activo):</strong> {cliente['nombre']} (NIT: {cliente['nit']})
</div>
""", unsafe_allow_html=True)

if 'db_ret' not in st.session_state: st.session_state.db_ret = pd.DataFrame()
if 'archivos_ret' not in st.session_state: st.session_state.archivos_ret = set()

with st.sidebar:
    st.header("Carga DTE 07")
    archivos = st.file_uploader("Arrastra Comprobantes de Retención (PDF)", type="pdf", accept_multiple_files=True)
    
    if archivos and st.button("🚀 Procesar Retenciones", type="primary", use_container_width=True):
        extracted = []
        nuevos_archivos = [f for f in archivos if f.name not in st.session_state.archivos_ret]

        if nuevos_archivos:
            bar, txt_progreso = st.progress(0), st.empty()
            total = len(nuevos_archivos)
            for idx, f in enumerate(nuevos_archivos):
                res = extraer_retencion_nativa(f.read(), cliente)
                if "error" not in res and "error_tipo" not in res:
                    res["archivo"] = f.name
                    extracted.append(res)
                st.session_state.archivos_ret.add(f.name)
                bar.progress((idx + 1) / total)
            txt_progreso.success(f"✅ ¡{total} retenciones procesadas!")
            
            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_ret.empty: st.session_state.db_ret = new_df
                else: st.session_state.db_ret = pd.concat([st.session_state.db_ret, new_df], ignore_index=True)

    if st.button("🧹 Limpiar Memoria", type="secondary", use_container_width=True):
        if 'db_ret' in st.session_state: del st.session_state['db_ret']
        if 'archivos_ret' in st.session_state: del st.session_state['archivos_ret']
        st.rerun()

if not st.session_state.db_ret.empty:
    df = st.session_state.db_ret.copy()
    st.dataframe(df, use_container_width=True)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='F14_Retenciones')
    st.download_button("📥 Descargar Base para F-14", data=output.getvalue(), file_name="Retenciones_F14.xlsx", type="primary")
