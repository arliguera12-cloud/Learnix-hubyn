import streamlit as st
import json
import os

# ─────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title = "Dashboard · Learnix DTE Hub",
    layout     = "wide",        # ✅ Consistente con app.py y demás páginas
    page_icon  = "🏠"
)

# ─────────────────────────────────────────────
# 2. VERIFICACIÓN DE SEGURIDAD
# ─────────────────────────────────────────────
if not st.session_state.get("autenticado"):
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

# ─────────────────────────────────────────────
# 3. ESTILOS — VERDE OLIVA ARMONIZADO
# ─────────────────────────────────────────────
ESTILO = """
<style>
  /* ── Fondos ── */
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"]          { background-color: #0D0F07 !important; }
  [data-testid="stSidebar"]         { background-color: #141A08 !important;
                                      border-right: 1px solid #4A5520 !important; }

  /* ── Tipografía ── */
  h1, h2, h3, h4, h5, h6           { color: #C8D87A !important; }
  p, label, span, li                { color: #F0EDD8 !important; }
  [data-testid="stDataFrame"] span  { color: inherit !important; }

  /* ── Selectbox ── */
  div[data-testid="stSelectbox"] > label { display: none; }
  div[data-testid="stSelectbox"] > div > div {
    background-color : #1A2008 !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 8px !important;
    color            : #F0EDD8 !important;
  }

  /* ── Botones ── */
  div.stButton > button[kind="primary"] {
    background-color : #6B7A2A !important;
    border           : 1px solid #8A9A35 !important;
    border-radius    : 6px !important;
    transition       : 0.25s;
  }
  div.stButton > button[kind="primary"]:hover {
    background-color : #8A9A35 !important;
    transform        : scale(1.02);
  }
  div.stButton > button[kind="primary"] * {
    color: #FFFFFF !important; font-weight: bold !important;
  }

  /* ── Alertas ── */
  div[data-testid="stAlert"] { display: flex; align-items: center; }

  /* ── Separador ── */
  hr { border-color: #4A5520 !important; opacity: 0.4; }

  /* ── Tarjetas de módulos ── */
  .modulo-card {
    background-color : #141A08;
    padding          : 24px 20px;
    border-radius    : 12px;
    border           : 1px solid #2A3010;
    height           : 100%;
    min-height       : 130px;
    transition       : border-color 0.25s ease, box-shadow 0.25s ease,
                       transform 0.2s ease;
    cursor           : default;
  }
  .modulo-card:hover {
    border-color : #8A9A35;                          /* ✅ Oliva, no azul */
    box-shadow   : 0 0 16px rgba(138, 154, 53, 0.2);
    transform    : translateY(-2px);
  }
  .modulo-icon  {
    font-size     : 2.2rem;
    margin-bottom : 10px;
    display       : block;
  }
  .modulo-title {
    font-size   : 1.1rem;
    font-weight : bold;
    color       : #C8D87A !important;
    margin-bottom: 8px;
  }
  .modulo-desc  {
    font-size   : 0.875rem;
    color       : #8A9A35 !important;
    line-height : 1.5;
  }
  .modulo-badge {
    display          : inline-block;
    margin-top       : 10px;
    padding          : 2px 10px;
    border-radius    : 12px;
    font-size        : 0.72rem;
    background-color : #2A3010;
    color            : #A8BB45 !important;
    border           : 1px solid #4A5520;
    letter-spacing   : 0.5px;
  }

  /* ── Card cliente activo ── */
  .card-cliente-activo {
    padding          : 14px 18px;
    border-radius    : 10px;
    border-left      : 4px solid #8A9A35;
    background-color : #1A2008;
    margin-bottom    : 8px;
    font-size        : 14px;
    line-height      : 1.7;
  }
  .card-cliente-activo .label {
    font-size   : 0.72rem;
    color       : #6B7A2A !important;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .card-cliente-activo .nombre { color: #C8D87A !important; font-weight: bold; font-size: 1rem; }
  .card-cliente-activo .nit    { color: #8A9A35 !important; font-size: 0.85rem; }

  /* ── KPI Cards ── */
  .kpi-card {
    background-color : #1A2008;
    border           : 1px solid #2A3010;
    border-radius    : 10px;
    padding          : 16px 18px;
    text-align       : center;
  }
  .kpi-valor  { font-size: 1.8rem; font-weight: bold; color: #C8D87A !important; }
  .kpi-label  { font-size: 0.8rem;  color: #6B7A2A !important; margin-top: 4px; }

  /* ── Header de bienvenida ── */
  .bienvenida-titulo {
    text-align    : center;
    font-size     : 1.9rem;
    font-weight   : bold;
    color         : #C8D87A !important;
    letter-spacing: 1px;
    margin-bottom : 4px;
  }
  .bienvenida-sub {
    text-align : center;
    font-size  : 0.95rem;
    color      : #6B7A2A !important;
    margin-bottom: 0;
  }
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 4. CARGA DE CLIENTES
# ─────────────────────────────────────────────
def cargar_clientes() -> dict:
    """Carga la base de datos de clientes con manejo explícito de errores."""
    archivo = "data/clientes.json"
    if not os.path.exists(archivo):
        return {}
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ El archivo de clientes tiene un error de formato JSON: {e}")
        return {}
    except Exception as e:
        st.warning(f"⚠️ No se pudo cargar el directorio de clientes: {e}")
        return {}

# ─────────────────────────────────────────────
# 5. ENCABEZADO DE BIENVENIDA
# ─────────────────────────────────────────────
col_logo, col_hdr, _ = st.columns([1, 6, 1])
with col_logo:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #8A9A35;"
        " letter-spacing: 3px; margin-top:12px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_hdr:
    st.markdown("<div class='bienvenida-titulo'>Bienvenido al Hub DTE 👋</div>", unsafe_allow_html=True)
    st.markdown("<p class='bienvenida-sub'>Selecciona tu espacio de trabajo para comenzar a procesar documentos.</p>", unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# 6. SELECTOR DE EMPRESA
# ─────────────────────────────────────────────
db_clientes = cargar_clientes()

_, col_sel, _ = st.columns([1, 2, 1])
with col_sel:
    if not db_clientes:
        # ✅ No sobreescribir cliente_activo si el JSON está vacío temporalmente
        st.warning("⚠️ El Directorio de Clientes está vacío. Agrégalos desde el menú lateral.")

    else:
        # ✅ Construir opciones con NIT incluido en los datos del mapa
        opciones = ["— Selecciona una empresa —"]
        mapa: dict[str, dict] = {}

        for nit, datos in db_clientes.items():
            nombre = datos.get("nombre", "Sin nombre")
            label  = f"{nombre}  ·  {nit}"
            mapa[label] = {**datos, "nit": nit}   # ✅ NIT siempre presente en el objeto
            opciones.append(label)

        # ✅ Recuperar selección previa si existe
        cliente_previo = st.session_state.get("cliente_activo")
        idx_previo = 0
        if cliente_previo:
            label_previo = f"{cliente_previo.get('nombre','')}  ·  {cliente_previo.get('nit','')}"
            if label_previo in opciones:
                idx_previo = opciones.index(label_previo)

        seleccion = st.selectbox(
            "Empresa",
            opciones,
            index=idx_previo,
            help="Selecciona la empresa para la cual procesarás los DTE"
        )

        if seleccion != "— Selecciona una empresa —":
            cliente_sel = mapa[seleccion]
            # ✅ Solo actualizar si cambió el cliente
            if (
                not st.session_state.get("cliente_activo")
                or st.session_state["cliente_activo"].get("nit") != cliente_sel.get("nit")
            ):
                st.session_state["cliente_activo"] = cliente_sel

            # Card del cliente activo
            st.markdown(f"""
            <div class="card-cliente-activo">
                <div class="label">Espacio de Trabajo Activo</div>
                <div class="nombre">{cliente_sel.get('nombre', '—')}</div>
                <div class="nit">NIT: {cliente_sel.get('nit', '—')}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("👆 Selecciona una empresa para activar los módulos de procesamiento.")

st.markdown("")
st.divider()

# ─────────────────────────────────────────────
# 7. KPIs EN TIEMPO REAL (si hay cliente activo)
# ─────────────────────────────────────────────
cliente_activo = st.session_state.get("cliente_activo")

if cliente_activo:
    # Contadores desde session_state (acumulados durante la sesión)
    n_ventas  = len(st.session_state.get("db_ventas",  __import__("pandas").DataFrame()))
    n_compras = len(st.session_state.get("db_compras", __import__("pandas").DataFrame()))

    tot_ventas  = st.session_state.get("db_ventas",  __import__("pandas").DataFrame())
    tot_compras = st.session_state.get("db_compras", __import__("pandas").DataFrame())

    sum_ventas  = float(tot_ventas["tot"].sum())  if not tot_ventas.empty  and "tot" in tot_ventas.columns  else 0.0
    sum_compras = float(tot_compras["tot"].sum()) if not tot_compras.empty and "tot" in tot_compras.columns else 0.0

    st.markdown("#### 📊 Resumen de Sesión Actual")
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-valor">{n_ventas}</div>
            <div class="kpi-label">📈 DTE Ventas</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-valor">${sum_ventas:,.2f}</div>
            <div class="kpi-label">💰 Total Ventas</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-valor">{n_compras}</div>
            <div class="kpi-label">🛒 DTE Compras</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-valor">${sum_compras:,.2f}</div>
            <div class="kpi-label">🧾 Total Compras</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")
    st.divider()

# ─────────────────────────────────────────────
# 8. TARJETAS DE MÓDULOS
# ─────────────────────────────────────────────
st.markdown("#### 🗂️ Módulos Disponibles")
st.markdown("")

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("""
    <div class="modulo-card">
        <span class="modulo-icon">📈</span>
        <div class="modulo-title">Extractor de Ventas</div>
        <div class="modulo-desc">
            Procesa CCF y Facturas en formato PDF nativo. Genera el Anexo F-07
            separando automáticamente ventas a contribuyentes y consumidores finales.
        </div>
        <span class="modulo-badge">DTE 01 · 03 · 05 · 06</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    st.markdown("""
    <div class="modulo-card">
        <span class="modulo-icon">✂️</span>
        <div class="modulo-title">Retenciones 1%</div>
        <div class="modulo-desc">
            Lee documentos DTE-07 y estructura el Anexo F-14 calculando automáticamente
            las bases gravables y los montos retenidos por proveedor.
        </div>
        <span class="modulo-badge">DTE 07 · Anexo F-14</span>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="modulo-card">
        <span class="modulo-icon">🛒</span>
        <div class="modulo-title">Extractor de Compras</div>
        <div class="modulo-desc">
            Digitaliza compras del Anexo F-07 con motor de extracción inteligente.
            Incluye bandeja de revisión manual, detección de duplicados y directorio
            de proveedores persistente.
        </div>
        <span class="modulo-badge">DTE 03 · 05 · 06 · Anexo F-07</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    st.markdown("""
    <div class="modulo-card">
        <span class="modulo-icon">⚖️</span>
        <div class="modulo-title">Sujetos Excluidos</div>
        <div class="modulo-desc">
            Extrae datos de DTE-14 para la Casilla 66 de Compras y calcula automáticamente
            las retenciones del 10% para el formulario F-14.
        </div>
        <span class="modulo-badge">DTE 14 · Casilla 66 · F-14</span>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 9. ESTADO VACÍO — Sin cliente seleccionado
# ─────────────────────────────────────────────
if not cliente_activo and db_clientes:
    st.markdown("")
    st.markdown("""
    <div style="text-align:center; padding: 30px 20px; color:#4A5520;
                border: 1px dashed #2A3010; border-radius: 12px; margin-top: 10px;">
        <p style="font-size:1.5rem; margin-bottom:6px;">☝️</p>
        <p style="color:#6B7A2A !important; font-size:0.95rem;">
            Selecciona una empresa arriba para activar los módulos
            y visualizar el resumen de sesión.
        </p>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 10. FOOTER
# ─────────────────────────────────────────────
st.markdown("")
st.divider()
st.markdown(
    "<p style='text-align:center; font-size:0.75rem; color:#4A5520;'>"
    "Learnix DTE Hub &nbsp;·&nbsp; v2.0 &nbsp;·&nbsp; El Salvador &nbsp;·&nbsp; "
    "Todos los datos se procesan localmente.</p>",
    unsafe_allow_html=True
)
