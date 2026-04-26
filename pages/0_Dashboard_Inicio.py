import streamlit as st

# --- SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión.")
    st.stop()

# --- DISEÑO DEL HUB ---
usuario = st.session_state.get("usuario_actual", "Contador")

st.markdown(f"<h1 style='text-align: center; color: #F7F5EE; margin-bottom: 0px;'>Bienvenido, {usuario} 👋</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888888; font-size: 18px;'>Selecciona un módulo en el menú lateral o explora tus herramientas:</p>", unsafe_allow_html=True)
st.divider()

# --- CSS PARA LAS TARJETAS (ESTILO ILOVEPDF DARK) ---
css = """
<style>
    .grid-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
        padding: 20px 0px;
    }
    .card {
        background-color: #161616;
        border: 1px solid #333333;
        border-radius: 12px;
        padding: 25px;
        transition: all 0.3s ease;
        text-align: left;
    }
    .card:hover {
        transform: translateY(-6px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.6);
    }
    /* Colores de Hover personalizados por módulo */
    .card.ventas:hover { border-color: #4DA8DA; }
    .card.compras:hover { border-color: #00E5FF; }
    .card.retenciones:hover { border-color: #8C52FF; }
    .card.sujetos:hover { border-color: #666D57; }
    
    .card-icon {
        font-size: 40px;
        margin-bottom: 15px;
    }
    .card-title {
        color: #FFFFFF;
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 10px;
        letter-spacing: 0.5px;
    }
    .card-desc {
        color: #888888;
        font-size: 14px;
        line-height: 1.5;
    }
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# --- ESTRUCTURA HTML DE LAS TARJETAS ---
html_tarjetas = """
<div class="grid-container">
    <div class="card ventas">
        <div class="card-icon">📈</div>
        <div class="card-title">Extractor de Ventas</div>
        <div class="card-desc">Procesa CCF y Facturas. Genera el Anexo F-07 automatizando las ventas a contribuyentes y consumidores finales.</div>
    </div>
    
    <div class="card compras">
        <div class="card-icon">🛒</div>
        <div class="card-title">Extractor de Compras</div>
        <div class="card-desc">Digitaliza las compras del Anexo F-07. Incluye motor OCR, cálculos matemáticos IA y detección de intrusos.</div>
    </div>
    
    <div class="card retenciones">
        <div class="card-icon">✂️</div>
        <div class="card-title">Retenciones 1%</div>
        <div class="card-desc">Lee DTE 07 y estructura el Anexo F-14 calculando automáticamente las bases y los montos retenidos.</div>
    </div>
    
    <div class="card sujetos">
        <div class="card-icon">⚖️</div>
        <div class="card-title">Sujetos Excluidos</div>
        <div class="card-desc">Extrae datos de DTE 14 para la Casilla 66 (Compras) y Retenciones del 10% para el formulario F-14.</div>
    </div>
</div>
"""
st.markdown(html_tarjetas, unsafe_allow_html=True)

st.markdown("<br><p style='text-align: center; color: #555555; font-size: 14px;'>👈 Utiliza el panel izquierdo para seleccionar a tu cliente activo y navegar a las herramientas.</p>", unsafe_allow_html=True)
