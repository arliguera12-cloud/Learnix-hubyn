import streamlit as st
import json
import os
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# 🔐 VERIFICACIÓN DE SEGURIDAD (CRÍTICA)
# ═══════════════════════════════════════════════════════════════
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

# ═══════════════════════════════════════════════════════════════
# 🎨 ESTILOS GLOBALES
# ═══════════════════════════════════════════════════════════════
estilo_custom = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #000000 !important;
    }
    
    [data-testid="stSidebar"] {
        background-color: #161616 !important;
        border-right: 1px solid #333333 !important;
    }
    
    h1, h2, h3, h4, h5, h6, p, label, span, div {
        color: #F7F5EE !important;
    }
    
    .stSelectbox label {
        display: none !important;
    }
    
    .modulo-card {
        background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%);
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #333;
        border-left: 4px solid #4DA8DA;
        height: 100%;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        position: relative;
        overflow: hidden;
    }
    
    .modulo-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(77, 168, 218, 0.1), transparent);
        transition: left 0.5s;
    }
    
    .modulo-card:hover {
        border-color: #4DA8DA;
        border-left-color: #00E5FF;
        box-shadow: 0 8px 24px rgba(77, 168, 218, 0.15);
        transform: translateY(-4px);
    }
    
    .modulo-card:hover::before {
        left: 100%;
    }
    
    .modulo-icon {
        font-size: 2.5rem;
        margin-bottom: 15px;
        display: inline-block;
        animation: float 3s ease-in-out infinite;
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-8px); }
    }
    
    .modulo-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin-bottom: 12px;
        color: #F7F5EE;
        letter-spacing: 0.5px;
    }
    
    .modulo-desc {
        font-size: 0.95rem;
        color: #999;
        line-height: 1.6;
        margin: 0;
    }
    
    [data-testid="stAlert"] {
        border-radius: 8px;
        padding: 16px;
        margin: 12px 0;
    }
    
    hr {
        border-color: #333 !important;
        margin: 24px 0 !important;
    }
</style>
"""
st.markdown(estilo_custom, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 💾 FUNCIONES DE DATOS
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def cargar_clientes():
    """Carga clientes desde JSON con validación."""
    ruta = "data/clientes.json"
    
    if not os.path.exists("data"):
        os.makedirs("data")
    
    if not os.path.exists(ruta):
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        clientes_validados = {}
        for nit, cliente in data.items():
            if isinstance(cliente, dict) and cliente.get("nombre"):
                clientes_validados[nit] = {
                    "nit": nit,
                    "nombre": cliente.get("nombre", "Desconocido").upper(),
                    "dui": cliente.get("dui", ""),
                    "nrc": cliente.get("nrc", ""),
                    "actividad": cliente.get("actividad", "")
                }
        
        return clientes_validados
    
    except json.JSONDecodeError:
        st.error("❌ Error: clientes.json está corrupto.")
        return {}
    except Exception as e:
        st.error(f"❌ Error al cargar clientes: {str(e)}")
        return {}


def obtener_nombre_usuario():
    """Obtiene el nombre del usuario autenticado."""
    usuario = st.session_state.get("usuario_actual", "Usuario")
    return usuario.split("@")[0].title() if usuario else "Usuario"


def obtener_cliente_activo_seguro():
    """Obtiene el cliente activo con validación segura."""
    cliente = st.session_state.get("cliente_activo")
    
    if not isinstance(cliente, dict):
        return None
    
    nit = cliente.get("nit")
    if not nit:
        return None
    
    return cliente


# ═══════════════════════════════════════════════════════════════
# 📱 HEADER PRINCIPAL
# ═══════════════════════════════════════════════════════════════
col_header1, col_header2, col_header3 = st.columns([1, 2, 1])

with col_header1:
    st.markdown(
        "<h2 style='font-family: Courier New; color: #4DA8DA; letter-spacing: 2px; margin: 0;'>YN</h2>",
        unsafe_allow_html=True
    )

with col_header2:
    usuario = obtener_nombre_usuario()
    st.markdown(f"<h1 style='text-align: center; margin: 0;'>Bienvenido, {usuario} 👋</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; color: #888; margin: 0;'>Selecciona tu empresa para comenzar</p>",
        unsafe_allow_html=True
    )

with col_header3:
    hora_actual = datetime.now().strftime("%H:%M")
    st.markdown(
        f"<p style='text-align: right; color: #666; margin: 0;'>⏰ {hora_actual}</p>",
        unsafe_allow_html=True
    )

st.divider()

# ═══════════════════════════════════════════════════════════════
# 🏢 SELECTOR DE EMPRESA
# ═══════════════════════════════════════════════════════════════

db_clientes = cargar_clientes()
cliente_activo = obtener_cliente_activo_seguro()

col_sel1, col_sel2, col_sel3 = st.columns([1, 2, 1])

with col_sel2:
    if not db_clientes:
        st.warning(
            "⚠️ **Tu Directorio de Clientes está vacío**\n\n"
            "👉 Ve a **🏢 Directorio Clientes** en el menú lateral para agregar tu primera empresa."
        )
        st.session_state.cliente_activo = None
    else:
        opciones = ["-- Selecciona una empresa --"]
        mapa_opciones = {}
        
        for nit, datos in db_clientes.items():
            nombre = datos.get("nombre", "Desconocido")
            label = f"📌 {nombre} (NIT: {nit})"
            opciones.append(label)
            mapa_opciones[label] = datos
        
        indice_actual = 0
        if cliente_activo and "nit" in cliente_activo:
            for idx, label in enumerate(opciones[1:], 1):
                if mapa_opciones[label]["nit"] == cliente_activo["nit"]:
                    indice_actual = idx
                    break
        
        seleccion_idx = st.selectbox(
            "Seleccionar Empresa",
            range(len(opciones)),
            format_func=lambda i: opciones[i],
            index=indice_actual,
            key="selector_empresa"
        )
        
        if seleccion_idx > 0:
            empresa_seleccionada = mapa_opciones[opciones[seleccion_idx]]
            
            if not cliente_activo or cliente_activo.get("nit") != empresa_seleccionada["nit"]:
                st.session_state.cliente_activo = empresa_seleccionada
                st.success(f"✅ Entorno configurado para: **{empresa_seleccionada['nombre']}**")
                st.balloons()
        else:
            st.info("👆 Selecciona una empresa para continuar")
            st.session_state.cliente_activo = None

st.divider()

# ═══════════════════════════════════════════════════════════════
# 📊 ESTADO ACTUAL DE LA EMPRESA
# ═══════════════════════════════════════════════════════════════

if cliente_activo:
    col_info1, col_info2, col_info3, col_info4 = st.columns(4)
    
    with col_info1:
        st.metric("🏢 Empresa", cliente_activo.get("nombre", "N/A")[:20])
    
    with col_info2:
        st.metric("🆔 NIT", cliente_activo.get("nit", "N/A"))
    
    with col_info3:
        nrc = cliente_activo.get("nrc", "N/A")
        st.metric("📋 NRC", nrc if nrc else "—")
    
    with col_info4:
        actividad = cliente_activo.get("actividad", "N/A")[:15]
        st.metric("🏭 Actividad", actividad if actividad else "—")
    
    st.divider()

# ═══════════════════════════════════════════════════════════════
# 🔧 MÓDULOS DISPONIBLES
# ═══════════════════════════════════════════════════════════════

st.markdown("### 🚀 Módulos de Procesamiento")
st.write("Selecciona un módulo en el menú lateral para comenzar")

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div class="modulo-card">
        <div class="modulo-icon">📈</div>
        <div class="modulo-title">Extractor de Ventas</div>
        <div class="modulo-desc">
            Procesa DTE 03, 05, 06, 01 y 11.<br>
            Genera automáticamente el Anexo F-07 con ventas a contribuyentes y consumidores finales.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="modulo-card">
        <div class="modulo-icon">🛒</div>
        <div class="modulo-title">Extractor de Compras</div>
        <div class="modulo-desc">
            Digitaliza compras DTE 03, 05, 06.<br>
            Motor OCR incluido. Detección automática de intrusos (anti-fraude).
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col3, col4 = st.columns(2, gap="large")

with col3:
    st.markdown("""
    <div class="modulo-card">
        <div class="modulo-icon">✂️</div>
        <div class="modulo-title">Retenciones 1%</div>
        <div class="modulo-desc">
            Procesa DTE 07 (Comprobantes de Retención).<br>
            Estructura automática del Anexo F-14 con cálculos del 1%.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="modulo-card">
        <div class="modulo-icon">⚖️</div>
        <div class="modulo-title">Sujetos Excluidos</div>
        <div class="modulo-desc">
            Extrae DTE 14 para Casilla 66 (Compras).<br>
            Retenciones del 10% automáticas para F-14.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════
# 📊 ESTADÍSTICAS Y RECOMENDACIONES
# ═══════════════════════════════════════════════════════════════

if cliente_activo:
    st.markdown("### 📊 Estado del Entorno")
    
    col_stats1, col_stats2, col_stats3 = st.columns(3)
    
    with col_stats1:
        st.metric("✅ Estado", "Listo")
    
    with col_stats2:
        st.metric("🔒 Autenticación", "Segura")
    
    with col_stats3:
        st.metric("📁 Directorio", "Configurado")
    
    with st.expander("💡 Próximos Pasos Recomendados"):
        st.markdown("""
        1. **Agregar Proveedores** — Ve a **🏢 Directorio Proveedores** para crear tu base maestra
        2. **Procesar Ventas** — Sube PDFs de facturas en el módulo de Ventas
        3. **Procesar Compras** — Sube comprobantes de tus proveedores
        4. **Validar Retenciones** — Revisa y exporta el Anexo F-14
        5. **Exportar a Hacienda** — Genera los Excel listos para enviar
        """)
else:
    st.info("💡 Selecciona una empresa arriba para ver el estado del entorno")

# ═══════════════════════════════════════════════════════════════
# 🔑 FOOTER
# ═══════════════════════════════════════════════════════════════

st.divider()
col_footer1, col_footer2, col_footer3 = st.columns(3)

with col_footer1:
    st.caption(f"👤 Usuario: {obtener_nombre_usuario()}")

with col_footer2:
    st.caption("🏢 Learnix Hub v1.0")

with col_footer3:
    st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
