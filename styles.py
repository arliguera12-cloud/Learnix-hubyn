"""
Learnix DTE Hub — Sistema de Diseño v2.0
Tema: Teal Navy Pro · Modo Oscuro Corporativo
Paleta: #BDD1BD · #85B093 · #568F7C · #326D6C · #173C4C · #07142B · #000009
"""

DARK_PRO_CSS = """
<style>
  /* ════════════════════════════════════════════
     VARIABLES DE COLOR
  ════════════════════════════════════════════ */
  :root {
    --bg-canvas:      #000009;
    --bg-surface:     #07142B;
    --bg-card:        #0D1F35;
    --bg-elevated:    #112540;
    --bg-input:       #060F20;
    --border:         #173C4C;
    --border-muted:   #0D2538;
    --border-accent:  #326D6C;
    --text:           #BDD1BD;
    --text-muted:     #85B093;
    --text-faint:     #568F7C;
    --accent:         #568F7C;
    --accent-hover:   #326D6C;
    --accent-bright:  #85B093;
    --accent-light:   #BDD1BD;
    --accent-blue:    #5BA3C9;
    --accent-warn:    #C9952A;
    --accent-danger:  #E05A52;
    --accent-purple:  #8A7FC8;
    --shadow-sm:      0 1px 4px rgba(0,0,9,0.60);
    --shadow-md:      0 4px 20px rgba(0,0,9,0.70);
    --shadow-lg:      0 8px 40px rgba(0,0,9,0.80);
    --shadow-glow:    0 0 30px rgba(86,143,124,0.12);
    --radius:         8px;
    --radius-lg:      12px;
    --radius-xl:      16px;
  }

  /* ════════════════════════════════════════════
     CHROME DE STREAMLIT — OCULTAR RUIDO
  ════════════════════════════════════════════ */
  footer                              { display: none !important; }
  [data-testid="stStatusWidget"]      { display: none !important; }
  [data-testid="stDeployButton"]      { display: none !important; }
  [data-testid="stMainMenuButton"]    { display: none !important; }
  .stDecoration                       { display: none !important; }
  #MainMenu                           { display: none !important; }
  [data-testid="stHeader"]            { background: transparent !important; }
  /* Quitar fondo blanco de los contenedores de columna */
  [data-testid="column"],
  [data-testid="stVerticalBlock"]     { background: transparent !important; }
  /* Quitar fondo del stForm que genera el cuadro molesto */
  [data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
  }

  /* ════════════════════════════════════════════
     FONDOS GLOBALES
  ════════════════════════════════════════════ */
  [data-testid="stAppViewContainer"],
  .stApp,
  [data-testid="stMain"] {
    background-color: var(--bg-canvas) !important;
  }
  [data-testid="stSidebar"] {
    background-color: var(--bg-surface) !important;
    border-right: 1px solid var(--border-muted) !important;
  }
  [data-testid="stSidebarContent"] {
    background-color: var(--bg-surface) !important;
  }

  /* ════════════════════════════════════════════
     TIPOGRAFÍA
  ════════════════════════════════════════════ */
  body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter",
                 Helvetica, Arial, sans-serif !important;
    color: var(--text) !important;
  }
  h1 {
    color: var(--accent-light) !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px;
    line-height: 1.25;
    font-size: 1.75rem !important;
  }
  h2 { color: var(--accent-bright) !important; font-weight: 600 !important; font-size: 1.35rem !important; }
  h3 { color: var(--accent)        !important; font-weight: 600 !important; font-size: 1.1rem  !important; }
  h4, h5, h6 { color: var(--text-muted) !important; font-weight: 600 !important; }
  p, label, span, li { color: var(--text) !important; }
  [data-testid="stDataFrame"] span { color: inherit !important; }
  [data-testid="stMarkdownContainer"] a { color: var(--accent-blue) !important; }
  small, .small { color: var(--text-muted) !important; font-size: 0.82rem !important; }
  code {
    background: var(--bg-card) !important;
    color: var(--accent-bright) !important;
    padding: 1px 6px !important;
    border-radius: 4px !important;
    font-size: 0.85em !important;
    border: 1px solid var(--border-muted) !important;
  }

  /* ════════════════════════════════════════════
     SIDEBAR — NAVEGACIÓN PROFESIONAL
  ════════════════════════════════════════════ */
  [data-testid="stSidebarNavLink"] {
    color: var(--text-muted) !important;
    border-radius: var(--radius) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    transition: all 0.18s ease !important;
    padding: 8px 12px !important;
    margin: 2px 0 !important;
    border-left: 3px solid transparent !important;
  }
  [data-testid="stSidebarNavLink"]:hover {
    background-color: rgba(86,143,124,0.10) !important;
    color: var(--accent-bright) !important;
    border-left-color: var(--accent) !important;
  }
  [data-testid="stSidebarNavLink"][aria-current] {
    background-color: rgba(86,143,124,0.15) !important;
    border-left: 3px solid var(--accent-bright) !important;
    color: var(--accent-light) !important;
    font-weight: 600 !important;
  }
  /* Encabezados de sección del sidebar */
  [data-testid="stSidebarNavSeparator"] {
    color: var(--text-faint) !important;
    font-size: 0.65rem !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    margin: 14px 0 4px !important;
    opacity: 0.7 !important;
  }

  /* ════════════════════════════════════════════
     MÉTRICAS
  ════════════════════════════════════════════ */
  [data-testid="stMetricValue"] {
    color: var(--accent-bright) !important;
    font-weight: 700 !important;
  }
  [data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-size: 0.80rem !important;
  }
  [data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-muted) !important;
    border-top: 2px solid var(--accent) !important;
    border-radius: var(--radius-lg) !important;
    padding: 16px 18px !important;
    transition: all 0.2s ease !important;
  }
  [data-testid="metric-container"]:hover {
    box-shadow: var(--shadow-md), var(--shadow-glow) !important;
    border-top-color: var(--accent-bright) !important;
  }

  /* ════════════════════════════════════════════
     BOTONES
  ════════════════════════════════════════════ */
  div.stButton > button[kind="primary"],
  div.stDownloadButton > button[kind="primary"] {
    background: var(--accent-hover) !important;
    border: 1px solid var(--accent) !important;
    border-radius: var(--radius) !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    letter-spacing: 0.3px !important;
    transition: all 0.18s ease !important;
    box-shadow: 0 1px 6px rgba(86,143,124,0.30) !important;
  }
  div.stButton > button[kind="primary"]:hover,
  div.stDownloadButton > button[kind="primary"]:hover {
    background: var(--accent) !important;
    border-color: var(--accent-bright) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(86,143,124,0.40) !important;
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #000009 !important;
    font-weight: 700 !important;
  }
  div.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    transition: all 0.18s ease !important;
    color: var(--text-muted) !important;
  }
  div.stButton > button[kind="secondary"]:hover {
    background: var(--bg-elevated) !important;
    border-color: var(--accent) !important;
    color: var(--accent-bright) !important;
  }
  div.stButton > button[kind="secondary"] * { color: var(--text-muted) !important; }

  /* ════════════════════════════════════════════
     INPUTS
  ════════════════════════════════════════════ */
  div[data-testid="stTextInput"] input,
  div[data-testid="stNumberInput"] input,
  div[data-testid="stDateInput"] input {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    caret-color: var(--accent-bright);
    font-size: 0.9rem !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
  }
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stNumberInput"] input:focus,
  div[data-testid="stDateInput"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(86,143,124,0.20) !important;
    outline: none !important;
  }
  div[data-testid="stTextInput"] input::placeholder,
  div[data-testid="stNumberInput"] input::placeholder {
    color: var(--text-faint) !important;
    opacity: 0.8 !important;
  }

  /* ════════════════════════════════════════════
     SELECTBOX / MULTISELECT
  ════════════════════════════════════════════ */
  div[data-testid="stSelectbox"] > div > div,
  [data-testid="stMultiSelect"] > div > div {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    transition: border-color 0.15s ease !important;
  }
  div[data-testid="stSelectbox"] > div > div:focus-within,
  [data-testid="stMultiSelect"] > div > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(86,143,124,0.18) !important;
  }

  /* ════════════════════════════════════════════
     CHECKBOX / RADIO
  ════════════════════════════════════════════ */
  [data-testid="stCheckbox"] label { color: var(--text) !important; }
  [data-testid="stCheckbox"] svg   { color: var(--accent) !important; }

  /* ════════════════════════════════════════════
     TABS
  ════════════════════════════════════════════ */
  button[data-baseweb="tab"] {
    color: var(--text-faint) !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    transition: color 0.15s ease !important;
    background: transparent !important;
  }
  button[data-baseweb="tab"]:hover { color: var(--text-muted) !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom: 2px solid var(--accent-bright) !important;
    color: var(--accent-bright) !important;
    font-weight: 600 !important;
  }
  [data-testid="stTabs"] { border-bottom: 1px solid var(--border-muted) !important; }

  /* ════════════════════════════════════════════
     ALERTAS
  ════════════════════════════════════════════ */
  div[data-testid="stAlert"] {
    border-radius: var(--radius) !important;
    border-left-width: 3px !important;
    font-size: 0.9rem !important;
  }
  div[data-testid="stAlert"][data-type="success"] { border-left-color: var(--accent) !important; }
  div[data-testid="stAlert"][data-type="error"]   { border-left-color: var(--accent-danger) !important; }
  div[data-testid="stAlert"][data-type="warning"] { border-left-color: var(--accent-warn) !important; }
  div[data-testid="stAlert"][data-type="info"]    { border-left-color: var(--accent-blue) !important; }
  details > summary { color: var(--accent-bright) !important; cursor: pointer; }

  /* ════════════════════════════════════════════
     PROGRESS BAR
  ════════════════════════════════════════════ */
  [data-testid="stProgress"] > div > div > div {
    background-color: var(--accent) !important;
    border-radius: 4px !important;
  }
  [data-testid="stProgress"] > div > div {
    background-color: var(--border) !important;
    border-radius: 4px !important;
  }

  /* ════════════════════════════════════════════
     SEPARADOR / SCROLLBAR
  ════════════════════════════════════════════ */
  hr { border-color: var(--border-muted) !important; opacity: 0.8; }
  ::-webkit-scrollbar       { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: var(--bg-canvas); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--accent) ; }

  /* ════════════════════════════════════════════
     FILE UPLOADER
  ════════════════════════════════════════════ */
  [data-testid="stFileUploader"] {
    background: var(--bg-card) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: var(--radius-lg) !important;
    transition: border-color 0.2s ease !important;
  }
  [data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
  }

  /* ════════════════════════════════════════════
     DATAFRAME / TABLA
  ════════════════════════════════════════════ */
  [data-testid="stDataFrame"] th {
    background-color: var(--bg-card) !important;
    color: var(--text-muted) !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid var(--border) !important;
  }
  [data-testid="stDataFrame"] td {
    color: var(--text) !important;
    font-size: 0.85rem !important;
    border-bottom: 1px solid var(--border-muted) !important;
  }

  /* ════════════════════════════════════════════
     LOGIN — PANTALLA COMPLETA
  ════════════════════════════════════════════ */
  /* Fuerza fondo negro en la página de login */
  [data-testid="stAppViewContainer"] > [data-testid="stMain"] > div {
    background: var(--bg-canvas) !important;
  }
  /* Elimina cualquier fondo de contenedor de columna en login */
  [data-testid="stHorizontalBlock"] [data-testid="column"] {
    background: transparent !important;
  }
  .login-box {
    background: var(--bg-surface);
    padding: 48px 44px 40px;
    border-radius: var(--radius-xl);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-lg), var(--shadow-glow);
    width: 100%;
    position: relative;
  }
  /* Línea de acento superior del login */
  .login-box::before {
    content: '';
    position: absolute;
    top: 0; left: 10%; right: 10%;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
  }
  .login-logo {
    text-align: center;
    font-family: 'Courier New', monospace;
    font-size: 3rem; font-weight: 900;
    letter-spacing: 10px;
    color: var(--accent-bright) !important;
    margin-bottom: 4px;
    line-height: 1;
    text-shadow: 0 0 40px rgba(86,143,124,0.35);
  }
  .login-badge {
    display: block; text-align: center;
    background: rgba(86,143,124,0.10);
    border: 1px solid rgba(86,143,124,0.25);
    border-radius: 20px; padding: 4px 20px;
    font-size: 0.68rem; color: var(--accent) !important;
    letter-spacing: 4px; text-transform: uppercase;
    margin: 8px auto 28px; width: fit-content;
  }
  .login-title {
    text-align: center;
    color: var(--text) !important;
    font-size: 1.10rem; font-weight: 600; margin: 0 0 6px;
    letter-spacing: -0.2px;
  }
  .login-sub {
    text-align: center;
    color: var(--text-faint) !important;
    font-size: 0.85rem; margin-bottom: 28px;
    line-height: 1.5;
  }
  .login-footer {
    text-align: center; font-size: 0.68rem;
    color: var(--text-faint) !important; margin-top: 28px;
    opacity: 0.55; letter-spacing: 0.5px;
  }
  .intentos-badge {
    display: flex; align-items: center; gap: 8px;
    background: rgba(224,90,82,0.08);
    border: 1px solid rgba(224,90,82,0.25);
    border-radius: var(--radius);
    padding: 9px 14px; font-size: 0.83rem;
    color: var(--accent-danger) !important;
    margin: 0 0 14px;
  }

  /* ════════════════════════════════════════════
     CLIENTE ACTIVO (sidebar)
  ════════════════════════════════════════════ */
  .card-cliente-activo {
    padding: 12px 16px;
    border-radius: var(--radius);
    background: rgba(86,143,124,0.08);
    border: 1px solid rgba(86,143,124,0.20);
    border-left: 3px solid var(--accent) !important;
    margin-bottom: 8px;
    font-size: 13px;
    line-height: 1.6;
  }
  .card-cliente-activo .label  { font-size: 0.63rem; color: var(--text-faint) !important; letter-spacing: 2px; text-transform: uppercase; }
  .card-cliente-activo .nombre { color: var(--accent-bright) !important; font-weight: 700; font-size: 0.95rem; }
  .card-cliente-activo .nit    { color: var(--text-muted)    !important; font-size: 0.82rem; }

  /* ════════════════════════════════════════════
     TARJETAS DE MÓDULOS (dashboard)
  ════════════════════════════════════════════ */
  .modulo-card {
    background: var(--bg-card);
    padding: 26px 24px;
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-muted);
    height: 100%;
    min-height: 150px;
    transition: all 0.22s ease;
  }
  .modulo-card:hover {
    border-color: var(--accent);
    box-shadow: 0 6px 24px rgba(86,143,124,0.15), var(--shadow-glow);
    transform: translateY(-2px);
  }
  .modulo-icon  { font-size: 2rem; margin-bottom: 12px; display: block; }
  .modulo-title { font-size: 1rem; font-weight: 700; color: var(--text) !important; margin-bottom: 6px; }
  .modulo-desc  { font-size: 0.85rem; color: var(--text-muted) !important; line-height: 1.65; }
  .modulo-badge {
    display: inline-block;
    margin-top: 12px; padding: 3px 10px;
    border-radius: 12px; font-size: 0.70rem;
    background-color: rgba(86,143,124,0.12);
    color: var(--accent-bright) !important;
    border: 1px solid rgba(86,143,124,0.25);
    letter-spacing: 0.5px;
  }

  /* ════════════════════════════════════════════
     KPI CARDS
  ════════════════════════════════════════════ */
  .kpi-pro {
    background: var(--bg-card);
    border: 1px solid var(--border-muted);
    border-radius: var(--radius-lg);
    padding: 20px 18px; text-align: center;
    transition: all 0.22s ease;
  }
  .kpi-pro:hover {
    border-color: var(--accent);
    box-shadow: 0 4px 20px rgba(86,143,124,0.12);
  }
  .kpi-pro .value { font-size: 1.8rem; font-weight: 700; color: var(--accent-bright) !important; line-height: 1.2; }
  .kpi-pro .label { font-size: 0.78rem; color: var(--text-muted) !important; margin-top: 6px; }
  .kpi-pro .sub   { font-size: 0.70rem; color: var(--text-faint) !important; margin-top: 3px; }

  /* ════════════════════════════════════════════
     TARJETA EMISOR/RECEPTOR
  ════════════════════════════════════════════ */
  .card-emisor {
    padding: 14px 18px;
    border-radius: var(--radius-lg);
    background: var(--bg-card);
    border: 1px solid var(--border-muted);
    border-left: 3px solid var(--accent);
    margin-bottom: 20px;
    font-size: 14px;
    line-height: 1.7;
  }
  .card-emisor strong { color: var(--accent-bright) !important; }
  .card-emisor span   { color: var(--text-muted)    !important; font-size: 0.85rem; }

  /* ════════════════════════════════════════════
     PANEL DE FILTROS
  ════════════════════════════════════════════ */
  .filter-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-muted);
    border-radius: var(--radius-lg);
    padding: 16px 18px 12px;
    margin-bottom: 14px;
  }
  .filter-title {
    font-size: 0.68rem; color: var(--text-faint) !important;
    letter-spacing: 2px; text-transform: uppercase;
    font-weight: 600; margin-bottom: 10px; display: block;
  }
  .results-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 20px; padding: 5px 16px;
    font-size: 0.82rem; color: var(--text-muted) !important;
    margin: 6px 0 14px;
  }
  .results-badge .cnt { font-weight: 700; color: var(--accent-bright) !important; }
  .active-filters { font-size: 0.75rem; color: var(--accent) !important; }

  /* ════════════════════════════════════════════
     BIENVENIDA
  ════════════════════════════════════════════ */
  .bienvenida-titulo {
    text-align: center; font-size: 1.9rem; font-weight: 700;
    color: var(--text) !important; letter-spacing: -0.5px; margin-bottom: 4px;
  }
  .bienvenida-sub {
    text-align: center; font-size: 0.95rem;
    color: var(--text-muted) !important; margin-bottom: 0;
  }

  /* ════════════════════════════════════════════
     ZONA DE PELIGRO / BADGES DE SISTEMA
  ════════════════════════════════════════════ */
  .zona-peligro {
    background: rgba(224,90,82,0.06);
    border: 1px solid rgba(224,90,82,0.22);
    border-radius: var(--radius); padding: 20px;
  }
  .zona-peligro-titulo {
    font-size: 0.85rem; font-weight: 600;
    color: var(--accent-danger) !important; margin: 0 0 6px;
  }
  .badge-sistema {
    display: inline-block;
    background: rgba(86,143,124,0.10);
    border: 1px solid rgba(86,143,124,0.22);
    border-radius: 20px; padding: 3px 16px;
    font-size: 0.68rem; color: var(--accent-bright) !important;
    letter-spacing: 2px; text-transform: uppercase;
  }

  /* ════════════════════════════════════════════
     BADGES DE TIPO DTE
  ════════════════════════════════════════════ */
  .badge-03 { background:rgba(86,143,124,0.15);  color:#85B093; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:600; border:1px solid rgba(86,143,124,0.30); }
  .badge-01 { background:rgba(91,163,201,0.12);  color:#5BA3C9; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:600; border:1px solid rgba(91,163,201,0.25); }
  .badge-05 { background:rgba(201,149,42,0.12);  color:#C9952A; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:600; border:1px solid rgba(201,149,42,0.25); }
  .badge-06 { background:rgba(224,90,82,0.12);   color:#E05A52; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:600; border:1px solid rgba(224,90,82,0.25); }

  /* ════════════════════════════════════════════
     ALERTA MATEMÁTICA
  ════════════════════════════════════════════ */
  .math-warn {
    background: rgba(201,149,42,0.08);
    border: 1px solid rgba(201,149,42,0.30);
    border-left: 3px solid var(--accent-warn);
    border-radius: var(--radius); padding: 10px 14px;
    font-size: 0.85rem; color: var(--accent-warn) !important;
    margin: 8px 0;
  }

  /* ════════════════════════════════════════════
     MISC
  ════════════════════════════════════════════ */
  .scroll-list {
    max-height: 200px; overflow-y: auto; padding: 8px 12px;
    background-color: var(--bg-canvas); border-radius: var(--radius);
    border: 1px solid var(--border-muted); font-family: 'Courier New', monospace;
    font-size: 12px; color: var(--text-muted); line-height: 1.9;
  }
  .inbox-revision {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-top: 2px solid var(--accent-warn);
    border-radius: var(--radius-lg); padding: 22px; margin: 20px 0;
  }
  .inbox-revision h3 { color: var(--text) !important; margin-top: 0; }
  .inbox-revision p  { color: var(--text-muted) !important; }
  .resumen-box {
    background: var(--bg-card); border: 1px solid var(--border-muted);
    border-radius: var(--radius); padding: 14px 20px;
    margin: 12px 0; font-size: 14px; line-height: 2;
  }
  .debug-box {
    background-color: var(--bg-canvas); border: 1px solid var(--border-muted);
    border-radius: var(--radius); padding: 10px 14px;
    font-family: 'Courier New', monospace; font-size: 11px;
    color: var(--text-faint); line-height: 1.7; margin-top: 8px;
  }
</style>
"""
