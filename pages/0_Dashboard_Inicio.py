import streamlit as st
import json
import os

st.set_page_config(page_title="Learnix Hub - Dashboard", layout="centered", page_icon="🚀")

estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #161616 !important; border-right: 1px solid #333333; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #F7F5EE !important; }
    .stSelectbox label { display: none; }
    .modulo-card { background-color: #161616; padding: 20px; border-radius: 10px; border: 1px solid #333; height: 100%; transition: 0.3s;}
    .modulo-card:hover { border-color: #4DA8DA; box-shadow: 0 0 10px rgba(77, 168, 218, 0.2); }
    .modulo-icon { font-size: 2rem; margin-bottom: 10px; }
    .modulo-title { font-size: 1.2rem; font-weight: bold; margin-bottom: 10px; color: #F7F5EE; }
    .modulo-desc { font-size: 0.9rem; color: #888; }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

def cargar_clientes():
    if os.path.exists("data/clientes.json"):
        try:
            with open("data/clientes.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

st.markdown("<h1 style='text-align: center;'>Bienvenido, ADMIN 👋</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #aaa;'>Selecciona tu Espacio de Trabajo para comenzar:</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

db_clientes = cargar_clientes()

col_sel1, col_sel2, col_sel3 = st.columns([1, 2, 1])
with col_sel2:
    if not db_clientes:
        st.warning("⚠️ Tu Directorio de Clientes está vacío. Ve al menú lateral para agregar empresas.")
        st.session_state.cliente_activo = None
    else:
        opciones = ["Selecciona una empresa..."]
        mapa = {}
        for nit, datos in db_clientes.items():
            nombre = datos.get("nombre", "Desconocido")
            label = f"{nombre} (NIT: {nit})"
            opciones.append(label)
            mapa[label] = datos
        
        seleccion = st.selectbox("Seleccionar Empresa", opciones)
        
        if seleccion != "Selecciona una empresa...":
            st.session_state.cliente_activo = mapa[seleccion]
            st.success(f"✅ Entorno configurado para: **{mapa[seleccion]['nombre']}**")
        else:
            st.info("👆 Por favor, selecciona una empresa de tu portafolio.")

st.markdown("<br><br>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown("""
    <div class="modulo-card">
        <div class="modulo-icon">📈</div>
        <div class="modulo-title">Extractor de Ventas</div>
        <div class="modulo-desc">Procesa CCF y Facturas. Genera el Anexo F-07 automatizando las ventas a contribuyentes y consumidores finales.</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="modulo-card">
        <div class="modulo-icon">✂️</div>
        <div class="modulo-title">Retenciones 1%</div>
        <div class="modulo-desc">Lee DTE 07 y estructura el Anexo F-14 calculando automáticamente las bases y los montos retenidos.</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="modulo-card">
        <div class="modulo-icon">🛒</div>
        <div class="modulo-title">Extractor de Compras</div>
        <div class="modulo-desc">Digitaliza las compras del Anexo F-07. Incluye motor OCR, cálculos matemáticos IA y detección de intrusos.</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="modulo-card">
        <div class="modulo-icon">⚖️</div>
        <div class="modulo-title">Sujetos Excluidos</div>
        <div class="modulo-desc">Extrae datos de DTE 14 para la Casilla 66 (Compras) y Retenciones del 10% para el formulario F-14.</div>
    </div>
    """, unsafe_allow_html=True)
