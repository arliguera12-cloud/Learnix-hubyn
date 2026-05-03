import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import os
import gc
from io import BytesIO

# --- VERIFICACIÓN DE SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if "cliente_activo" not in st.session_state or not st.session_state.cliente_activo:
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Ventas.")
    st.stop()

cliente = st.session_state.cliente_activo

st.set_page_config(page_title="Extraer DTE Ventas", layout="wide", page_icon="📈")

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    [data-testid="stDataFrame"] span { color: inherit !important; }
    div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] { background-color: #003057 !important; border: 1px solid #00407A !important; border-radius: 6px; transition: 0.3s; }
    div.stButton > button[kind="primary"] *, div.stDownloadButton > button[kind="primary"] * { color: #FFFFFF !important; font-weight: bold !important; }
    div[data-testid="stAlert"] { min-height: 80px; display: flex; align-items: center; }
    .alerta-activo { padding: 10px; border-radius: 6px; border-left: 4px solid #00407A; background-color: #111111; color: white; margin-bottom: 15px; font-size: 14px; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] { min-width: 45% !important; flex: 1 1 45% !important; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

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

def extraer_ventas_nativo(file_bytes, cliente_activo):
    try:
        texto_completo = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                texto_completo += (page.extract_text() or "") + "\n"
                
        if len(texto_completo.strip()) < 50: return {"error": "El PDF parece ser una imagen."}

        t_clean = re.sub(r'\s+', ' ', texto_completo)
        t_no_spaces = re.sub(r'\s+', '', t_clean).upper()

        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_spaces)
        tipo = "01"
        if m_ctrl:
            ctrl = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo: tipo = m_tipo.group(1)
        else: return {"error_tipo": "No es un DTE válido."}
            
        gen = ""
        m_gen_raw = re.search(r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})", t_no_spaces)
        if m_gen_raw:
            limpio = m_gen_raw.group(1).replace("-", "")
            gen = f"{limpio[:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:]}"

        m_fecha = re.search(r"\b(20[2-3]\d)\s*[\-\/]\s*(0[1-9]|1[0-2])\s*[\-\/]\s*([0-2]\d|3[0-1])\b", t_clean)
        fecha = f"{int(m_fecha.group(3)):02d}/{int(m_fecha.group(2)):02d}/{m_fecha.group(1)}" if m_fecha else ""

        nit_emisor_limpio = re.sub(r'[^0-9]', '', cliente_activo['nit'])
        dui_emisor_limpio = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))

        nit_cliente = ""
        nom_cliente = "CONSUMIDOR FINAL" if tipo in ["01"] else "⚠️ CLIENTE NO DETECTADO"

        # Buscar el NIT del receptor (excluyendo el del emisor)
        if tipo in ["03", "05", "06", "11"]:
            patron_identificadores = r"\b\d{4}\s*[-]?\s*\d{6}\s*[-]?\s*\d{3}\s*[-]?\s*\d{1}\b|\b\d{14}\b|\b\d{8}\s*[-]?\s*\d{1}\b|\b\d{9}\b"
            nits_encontrados = re.findall(patron_identificadores, texto_completo)
            nits_limpios = list(dict.fromkeys([re.sub(r'[^0-9]', '', n) for n in nits_encontrados]))
            nits_candidatos = [n for n in nits_limpios if n != nit_emisor_limpio and n != dui_emisor_limpio]
            
            if nits_candidatos: nit_cliente = nits_candidatos[0]

            # Buscar nombre del receptor (Cazador)
            if nit_cliente:
                regex_nombre = r"(?:Nombre[:\s]+|Nombre o raz[oó]n social[:\s]+|Raz[oó]n Social[:\s]+)(.*?)(?:NIT|NRC|Giro|Actividad|Direcci[oó]n|$)"
                # Aislar la parte inferior de la factura (donde suele estar el receptor)
                texto_receptor = re.split(r"(?i)\b(?:RECEPTOR|CLIENTE:|CLIENTE\s)\b", texto_completo)
                if len(texto_receptor) > 1:
                    m_nombre = re.search(regex_nombre, texto_receptor[1], re.I)
                    if m_nombre:
                        candidato = m_nombre.group(1).strip()
                        if len(candidato) > 5 and not any(bad in candidato.upper() for bad in ["@", "EMAIL", "CORREO", ".COM"]):
                            nom_cliente = re.sub(r"^[-_.,:]+", "", candidato.upper()).strip()

        # Montos
        e, g, i, ret, t = 0.0, 0.0, 0.0, 0.0, 0.0
        montos_brutos = re.findall(r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean)
        valores = sorted(list(set([limpiar_monto(m) for m in montos_brutos])), reverse=True)
        valores = [v for v in valores if v > 0] 
        
        m_ret = re.search(r"(?:Retenido|Retenci.n)[^0-9]*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
        if m_ret: ret = limpiar_monto(m_ret.group(1))
        
        m_exe = re.search(r"(?:Ventas Exentas|Total Exento)[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
        if m_exe: e = limpiar_monto(m_exe.group(1))

        encontrado = False
        for val_t in valores:
            if encontrado: break
            for val_g in valores:
                if val_g >= val_t: continue
                for val_i in valores:
                    if val_i >= val_g: continue
                    if abs(round(val_g * 0.13, 2) - round(val_i, 2)) <= 0.05:
                        if abs(round((val_g + val_i + e - ret), 2) - round(val_t, 2)) <= 0.05:
                            g, i, t = val_g, val_i, val_t
                            encontrado = True
                            break

        if not encontrado:
            m_t = re.search(r"(?:TOTAL A PAGAR|MONTO TOTAL|TOTAL OPERACI.N|VENTA TOTAL)[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_t: t = limpiar_monto(m_t.group(1))
            m_i = re.search(r"(?:IVA|13% IVA|I\.V\.A)[^\d]{0,30}?(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,4})", t_clean, re.I)
            if m_i: i = limpiar_monto(m_i.group(1))
            
            if t > 0 and i > 0: g = round(t - i - e + ret, 2)
            elif t > 0 and i == 0 and tipo in ["03"]:
                g = round((t + ret - e) / 1.13, 2)
                i = round(t + ret - e - g, 2)

        return {
            "fecha": fecha, "nit_cli": nit_cliente, "nom_cli": nom_cliente, "tipo": tipo, "gen": gen, 
            "exe": e, "gra": g, "iva": i, "ret": ret, "tot": t, "estado": "✅ OK"
        }
    except Exception as err: 
        return {"error": str(err)}

st.markdown("<h2 style='font-family: Courier New, monospace; color: #003057; letter-spacing: 2px; margin-bottom: 0px; padding-bottom: 0px;'>YN</h2>", unsafe_allow_html=True)
st.title("📈 Extractor DTE (Ventas)")

st.markdown(f"""
<div class="alerta-activo">
    <strong>EMISOR ACTUAL (Cliente Activo):</strong> {cliente['nombre']} (NIT: {cliente['nit']})
</div>
""", unsafe_allow_html=True)

if 'db_ventas' not in st.session_state: st.session_state.db_ventas = pd.DataFrame()
if 'archivos_ven' not in st.session_state: st.session_state.archivos_ven = set()

with st.sidebar:
    st.header("Carga de Ventas")
    archivos = st.file_uploader("Arrastra CCF o Facturas (PDF)", type="pdf", accept_multiple_files=True)
    
    if archivos and st.button("🚀 Procesar Ventas", type="primary", use_container_width=True):
        extracted = []
        nuevos_archivos = [f for f in archivos if f.name not in st.session_state.archivos_ven]

        if nuevos_archivos:
            bar, txt_progreso = st.progress(0), st.empty()
            total = len(nuevos_archivos)
            for idx, f in enumerate(nuevos_archivos):
                res = extraer_ventas_nativo(f.read(), cliente)
                if "error" not in res and "error_tipo" not in res:
                    res["archivo"] = f.name
                    extracted.append(res)
                st.session_state.archivos_ven.add(f.name)
                bar.progress((idx + 1) / total)
            txt_progreso.success(f"✅ ¡{total} facturas escaneadas!")
            
            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_ventas.empty: st.session_state.db_ventas = new_df
                else: st.session_state.db_ventas = pd.concat([st.session_state.db_ventas, new_df], ignore_index=True)

    if st.button("🧹 Limpiar Memoria", type="secondary", use_container_width=True):
        if 'db_ventas' in st.session_state: del st.session_state['db_ventas']
        if 'archivos_ven' in st.session_state: del st.session_state['archivos_ven']
        st.rerun()

if not st.session_state.db_ventas.empty:
    df = st.session_state.db_ventas.copy()
    
    tab1, tab2 = st.tabs(["📊 F-07 Ventas", "🔍 Auditoría"])
    
    with tab1:
        df_h = pd.DataFrame()
        df_h["A. Fecha Emisión"] = df["fecha"]
        df_h["B. Clase Doc"] = "4"
        df_h["C. Tipo Doc"] = df["tipo"]
        df_h["D. Num Resolucion"] = df["gen"]
        df_h["E. Serie"] = df["gen"]
        df_h["F. NIT/DUI Cliente"] = df["nit_cli"]
        df_h["G. Nombre Cliente"] = df["nom_cli"]
        df_h["H. Ventas Exentas"] = df["exe"]
        df_h["I. Ventas Internas Exentas"] = 0.00
        df_h["J. Ventas No Sujetas"] = 0.00
        df_h["K. Ventas Gravadas Locales"] = df["gra"]
        df_h["L. Debito Fiscal"] = df["iva"]
        df_h["M. Ventas a CTA Terceros"] = 0.00
        df_h["N. Debito a CTA Terceros"] = 0.00
        df_h["O. IVA Retenido"] = df["ret"]
        df_h["P. IVA Percibido"] = 0.00
        df_h["Q. Total"] = df["tot"]
        df_h["R. Num Anexo"] = "1"

        st.dataframe(df_h.style.format({col: "{:.2f}" for col in df_h.columns[7:17]}), hide_index=True, use_container_width=True)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_h.to_excel(writer, index=False, sheet_name='Ventas_F07')
        st.download_button("📥 Descargar Excel Anexo", data=output.getvalue(), file_name="F07_Ventas.xlsx", type="primary")

    with tab2: st.dataframe(df, use_container_width=True)
