import streamlit as st
import json
import os

# --- SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión.")
    st.stop()

# --- LECTOR DE BASE DE DATOS ULTRA SEGURO ---
def cargar_clientes():
    archivo = "data/clientes.json"
    db_segura = {}
    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f: 
                raw_db = json.load(f)
                for key, val in raw_db.items():
                    if isinstance(val, dict):
                        db_segura[key] = val
                    elif isinstance(val, str):
                        db_segura[key] = {"nombre": val, "nit": key, "dui": ""}
                if db_segura: return db_segura
        except: pass
    
    return {
        "00000000000000": {"nombre": "ENTRENO (Modo Pruebas)", "nit": "00000000000000", "dui": ""},
        "06141234567890": {"nombre": "FARMACIA SAN NICOLÁS S.A DE C.V.", "nit": "06141234567890", "dui": ""},
        "06140987654321": {"nombre": "CONSTRUCTORA EL SALVADOR", "nit": "06140987654321", "dui": ""}
    }

clientes_db = cargar_clientes()
lista_opciones = ["Selecciona una empresa..."] + [f"{datos.get('nombre', 'Sin Nombre')} (NIT: {nit})" for nit, datos in clientes_db.items()]

# --- LÓGICA DE MEMORIA PARA EL SELECTOR ---
index_defecto = 0
if "cliente_activo" in st.session_state and st.session_state.cliente_activo:
    nit_memoria = st.session_state.cliente_activo.get("nit", "")
    for i, opcion in enumerate(lista_opciones):
        if f"NIT: {nit_memoria}" in opcion:
            index_defecto = i
            break

# --- DISEÑO DEL HUB ---
usuario = st.session_state.get("usuario_actual", "Contador").upper()

st.markdown(f"<h1 style='text-align: center; color: #F7F5EE; margin-bottom: 0px;'>Bienvenido, {usuario} 👋</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888888; font-size: 16px;'>Selecciona tu Espacio de Trabajo para comenzar:</p>", unsafe_allow_html=True)

# --- SELECTOR DE ESPACIO DE TRABAJO ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    # Ahora le pasamos el "index_defecto" para que no se reinicie
    cliente_seleccionado = st.selectbox("🏢 Cliente Activo:", options=lista_opciones, index=index_defecto, label_visibility="collapsed")
    
    if cliente_seleccionado != "Selecciona una empresa...":
        nit_seleccionado = cliente_seleccionado.split("NIT: ")[1].replace(")", "")
        datos_crudos = clientes_db[nit_seleccionado]
        
        cliente_seguro = {
            "nombre": datos_crudos.get("nombre", "Cliente Desconocido"),
            "nit": datos_crudos.get("nit", nit_seleccionado), 
            "dui": datos_crudos.get("dui", "")
        }
        
        st.session_state.cliente_activo = cliente_seguro
        
        st.markdown(f"""
        <div style="background-color: #003057; border-left: 4px solid #00E5FF; padding: 10px; border-radius: 5px; color: white; text-align: center; font-size: 14px;">
            ✅ Entorno configurado para: <strong>{cliente_seguro['nombre']}</strong>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.session_state.cliente_activo = None
        st.markdown("""
        <div style="background-color: #1a1a1a; border: 1px solid #333; padding: 10px; border-radius: 5px; color: #888; text-align: center; font-size: 14px;">
            👆 Por favor, selecciona una empresa de tu portafolio.
        </div>
        """, unsafe_allow_html=True)

st.divider()

# --- CSS Y ESTRUCTURA DE TARJETAS ---
css = """
<style>
.grid-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    padding: 10px 0px;
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
.card.ventas:hover { border-color: #4DA8DA; }
.card.compras:hover { border-color: #00E5FF; }
.card.retenciones:hover { border-color: #8C52FF; }
.card.sujetos:hover { border-color: #666D57; }
.card-icon { font-size: 40px; margin-bottom: 15px; }
.card-title { color: #FFFFFF; font-size: 18px; font-weight: bold; margin-bottom: 10px; letter-spacing: 0.5px; }
.card-desc { color: #888888; font-size: 14px; line-height: 1.5; }
</style>
"""
st.markdown(css, unsafe_allow_html=True)

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
