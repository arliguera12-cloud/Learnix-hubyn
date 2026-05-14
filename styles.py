"""
Learnix DTE Hub — Sistema de Diseño
Tema: Slate Pro Dark
Paleta inspirada en GitHub Dark — suave, de bajo contraste duro,
cómoda para sesiones largas de trabajo.
"""

DARK_PRO_CSS = """
<style>
  /* ════════════════════════════════════════════
     VARIABLES DE COLOR (reusables via CSS var)
  ════════════════════════════════════════════ */
  :root {
    --bg-canvas:      #0D1117;
    --bg-surface:     #161B22;
    --bg-card:        #1C2128;
    --bg-elevated:    #22272E;
    --bg-input:       #0D1117;
    --border:         #30363D;
    --border-muted:   #21262D;
    --border-accent:  #238636;
    --text:           #C9D1D9;
    --text-muted:     #8B949E;
    --text-faint:     #6E7681;
    --accent:         #3FB950;
    --accent-hover:   #2EA043;
    --accent-bright:  #56D364;
    --accent-blue:    #58A6FF;
    --accent-warn:    #D29922;
    --accent-danger:  #F85149;
    --accent-purple:  #BC8CFF;
    --shadow-sm:      0 1px 3px rgba(1,4,9,0.40);
    --shadow-md:      0 4px 16px rgba(1,4,9,0.50);
    --shadow-lg:      0 8px 32px rgba(1,4,9,0.60);
    --radius:         8px;
    --radius-lg:      12px;
  }

  /* ════════════════════════════════════════════
     FONDOS GLOBALES
  ════════════════════════════════════════════ */
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"] {
    background-color: var(--bg-canvas) !important;
  }
  [data-testid="stSidebar"] {
    background-color: var(--bg-surface) !important;
    border-right: 1px solid var(--border-muted) !important;
  }
  [data-testid="stMain"] {
    background-color: var(--bg-canvas) !important;
  }

  /* ════════════════════════════════════════════
     TIPOGRAFÍA
  ════════════════════════════════════════════ */
  body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans",
                 Helvetica, Arial, sans-serif !important;
    color: var(--text) !important;
  }
  h1 {
    color: var(--accent-bright) !important;
    font-weight: 700 !important;
    letter-spacing: -0.4px;
    line-height: 1.25;
    font-size: 1.75rem !important;
  }
  h2 { color: #79C0FF !important; font-weight: 600 !important; font-size: 1.35rem !important; }
  h3 { color: var(--accent)      !important; font-weight: 600 !important; font-size: 1.1rem  !important; }
  h4, h5, h6 { color: var(--text-muted) !important; font-weight: 600 !important; }
  p, label, span, li { color: var(--text) !important; }
  [data-testid="stDataFrame"] span { color: inherit !important; }
  [data-testid="stMarkdownContainer"] a { color: var(--accent-blue) !important; }
  small, .small { color: var(--text-muted) !important; font-size: 0.82rem !important; }
  code {
    background: var(--bg-card) !important;
    color: var(--accent-bright) !important;
    padding: 1px 5px !important;
    border-radius: 4px !important;
    font-size: 0.85em !important;
  }

  /* ════════════════════════════════════════════
     MÉTRICAS
  ════════════════════════════════════════════ */
  [data-testid="stMetricValue"] { color: var(--accent-bright) !important; font-weight: 700 !important; }
  [data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 0.80rem !important; }
  [data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-muted) !important;
    border-top: 2px solid var(--accent) !important;
    border-radius: var(--radius-lg) !important;
    padding: 16px 18px !important;
    transition: box-shadow 0.2s ease !important;
  }
  [data-testid="metric-container"]:hover {
    box-shadow: var(--shadow-md) !important;
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
    letter-spacing: 0.2px !important;
    transition: all 0.18s ease !important;
    box-shadow: 0 1px 4px rgba(63,185,80,0.25) !important;
  }
  div.stButton > button[kind="primary"]:hover,
  div.stDownloadButton > button[kind="primary"]:hover {
    background: var(--accent-bright) !important;
    border-color: var(--accent-bright) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 3px 12px rgba(86,211,100,0.30) !important;
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #0D1117 !important;
    font-weight: 700 !important;
  }
  div.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    transition: all 0.18s ease !important;
  }
  div.stButton > button[kind="secondary"]:hover {
    background: var(--bg-elevated) !important;
    border-color: var(--text-muted) !important;
  }
  div.stButton > button[kind="secondary"] * { color: var(--text-muted) !important; }

  /* ════════════════════════════════════════════
     INPUTS / NUMBER INPUT
  ════════════════════════════════════════════ */
  div[data-testid="stTextInput"] input,
  div[data-testid="stNumberInput"] input {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    caret-color: var(--accent-bright);
    font-size: 0.9rem !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
  }
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stNumberInput"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(63,185,80,0.15) !important;
    outline: none !important;
  }
  div[data-testid="stTextInput"] input::placeholder,
  div[data-testid="stNumberInput"] input::placeholder {
    color: var(--text-faint) !important;
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
  }

  /* ════════════════════════════════════════════
     DATE INPUT
  ════════════════════════════════════════════ */
  div[data-testid="stDateInput"] input {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
  }

  /* ════════════════════════════════════════════
     CHECKBOX
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
  }
  button[data-baseweb="tab"]:hover { color: var(--text) !important; }
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
  details > summary { color: var(--accent) !important; cursor: pointer; }

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
  ::-webkit-scrollbar       { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg-canvas); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--text-faint); }

  /* ════════════════════════════════════════════
     SIDEBAR NAVEGACIÓN
  ════════════════════════════════════════════ */
  [data-testid="stSidebarNavLink"] {
    color: var(--text-muted) !important;
    border-radius: var(--radius) !important;
    font-size: 0.875rem !important;
    transition: all 0.15s ease !important;
    padding: 6px 10px !important;
  }
  [data-testid="stSidebarNavLink"]:hover {
    background-color: var(--bg-card) !important;
    color: var(--text) !important;
  }
  [data-testid="stSidebarNavLink"][aria-current] {
    background-color: rgba(63,185,80,0.12) !important;
    border-left: 3px solid var(--accent) !important;
    color: var(--accent-bright) !important;
    font-weight: 600 !important;
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
     TARJETA DE EMISOR/RECEPTOR
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
    font-size: 0.70rem;
    color: var(--text-faint) !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 10px;
    display: block;
  }
  .results-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 5px 16px;
    font-size: 0.82rem;
    color: var(--text-muted) !important;
    margin: 6px 0 14px;
  }
  .results-badge .cnt { font-weight: 700; color: var(--accent-bright) !important; }
  .active-filters      { font-size: 0.75rem; color: var(--accent) !important; }

  /* ════════════════════════════════════════════
     TARJETAS DE MÓDULOS (dashboard)
  ════════════════════════════════════════════ */
  .modulo-card {
    background: var(--bg-card);
    padding: 24px 22px;
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-muted);
    height: 100%;
    min-height: 140px;
    transition: all 0.22s ease;
  }
  .modulo-card:hover {
    border-color: var(--accent);
    box-shadow: 0 4px 20px rgba(63,185,80,0.12);
    transform: translateY(-2px);
  }
  .modulo-icon  { font-size: 2rem; margin-bottom: 10px; display: block; }
  .modulo-title { font-size: 1rem; font-weight: 700; color: var(--text) !important; margin-bottom: 6px; }
  .modulo-desc  { font-size: 0.85rem; color: var(--text-muted) !important; line-height: 1.6; }
  .modulo-badge {
    display: inline-block;
    margin-top: 10px;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.7rem;
    background-color: rgba(63,185,80,0.10);
    color: var(--accent) !important;
    border: 1px solid rgba(63,185,80,0.20);
    letter-spacing: 0.5px;
  }

  /* ════════════════════════════════════════════
     KPI CARDS
  ════════════════════════════════════════════ */
  .kpi-pro {
    background: var(--bg-card);
    border: 1px solid var(--border-muted);
    border-radius: var(--radius-lg);
    padding: 20px 18px;
    text-align: center;
    transition: all 0.22s ease;
  }
  .kpi-pro:hover {
    border-color: var(--accent);
    box-shadow: 0 4px 16px rgba(63,185,80,0.10);
  }
  .kpi-pro .value { font-size: 1.8rem; font-weight: 700; color: var(--accent-bright) !important; line-height: 1.2; }
  .kpi-pro .label { font-size: 0.78rem; color: var(--text-muted) !important; margin-top: 6px; }
  .kpi-pro .sub   { font-size: 0.70rem; color: var(--text-faint) !important; margin-top: 3px; }

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
     CLIENTE ACTIVO (sidebar)
  ════════════════════════════════════════════ */
  .card-cliente-activo {
    padding: 12px 16px;
    border-radius: var(--radius);
    background: rgba(63,185,80,0.07);
    border: 1px solid rgba(63,185,80,0.18);
    margin-bottom: 8px;
    font-size: 13px;
    line-height: 1.6;
  }
  .card-cliente-activo .label  { font-size: 0.65rem; color: var(--text-faint) !important; letter-spacing: 1.5px; text-transform: uppercase; }
  .card-cliente-activo .nombre { color: var(--accent-bright) !important; font-weight: 700; font-size: 0.95rem; }
  .card-cliente-activo .nit    { color: var(--text-muted)    !important; font-size: 0.82rem; }

  /* ════════════════════════════════════════════
     SCROLL LIST / DEBUG / MISC
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
    border-radius: var(--radius-lg);
    padding: 22px; margin: 20px 0;
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

  /* ════════════════════════════════════════════
     BADGES DE TIPO DTE
  ════════════════════════════════════════════ */
  .badge-03 { background:rgba(46,160,67,0.15);  color:#3FB950; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:600; border:1px solid rgba(46,160,67,0.30); }
  .badge-01 { background:rgba(88,166,255,0.12); color:#58A6FF; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:600; border:1px solid rgba(88,166,255,0.25); }
  .badge-05 { background:rgba(210,153,34,0.12); color:#D29922; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:600; border:1px solid rgba(210,153,34,0.25); }
  .badge-06 { background:rgba(248,81,73,0.12);  color:#F85149; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:600; border:1px solid rgba(248,81,73,0.25); }

  /* ════════════════════════════════════════════
     ALERTA DE VALIDACIÓN MATEMÁTICA
  ════════════════════════════════════════════ */
  .math-warn {
    background: rgba(210,153,34,0.10);
    border: 1px solid rgba(210,153,34,0.35);
    border-left: 3px solid var(--accent-warn);
    border-radius: var(--radius);
    padding: 10px 14px;
    font-size: 0.85rem;
    color: var(--accent-warn) !important;
    margin: 8px 0;
  }

  /* ════════════════════════════════════════════
     LOGIN
  ════════════════════════════════════════════ */
  .login-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 80vh;
  }
  .login-box {
    background: var(--bg-surface);
    padding: 44px 40px 36px;
    border-radius: 16px;
    border: 1px solid var(--border-muted);
    box-shadow: var(--shadow-lg), 0 0 0 1px rgba(63,185,80,0.06);
    width: 100%;
  }
  .login-logo {
    text-align: center;
    font-family: 'Courier New', monospace;
    font-size: 2.8rem; font-weight: 900;
    letter-spacing: 8px;
    color: var(--accent-bright) !important;
    margin-bottom: 4px;
    line-height: 1;
    text-shadow: 0 0 30px rgba(86,211,100,0.25);
  }
  .login-badge {
    display: block; text-align: center;
    background: rgba(63,185,80,0.10);
    border: 1px solid rgba(63,185,80,0.20);
    border-radius: 20px; padding: 3px 18px;
    font-size: 0.68rem; color: var(--accent) !important;
    letter-spacing: 3px; text-transform: uppercase;
    margin: 8px auto 22px; width: fit-content;
  }
  .login-title {
    text-align: center;
    color: var(--text) !important;
    font-size: 1.05rem; font-weight: 500; margin: 0 0 4px;
  }
  .login-sub {
    text-align: center;
    color: var(--text-faint) !important;
    font-size: 0.83rem; margin-bottom: 24px;
  }
  .login-footer {
    text-align: center; font-size: 0.68rem;
    color: var(--text-faint) !important; margin-top: 24px;
    opacity: 0.6;
  }
  .intentos-badge {
    display: flex; align-items: center; gap: 8px;
    background: rgba(248,81,73,0.08);
    border: 1px solid rgba(248,81,73,0.25);
    border-radius: var(--radius);
    padding: 8px 14px; font-size: 0.82rem;
    color: var(--accent-danger) !important;
    margin: 0 0 12px;
  }
  .login-divider {
    display: flex; align-items: center; gap: 12px;
    margin: 20px 0;
    color: var(--text-faint) !important;
    font-size: 0.75rem;
  }
  .login-divider::before,
  .login-divider::after {
    content: ''; flex: 1;
    height: 1px; background: var(--border-muted);
  }

  /* ════════════════════════════════════════════
     ZONA PELIGRO / SISTEMA
  ════════════════════════════════════════════ */
  .zona-peligro {
    background: rgba(248,81,73,0.06);
    border: 1px solid rgba(248,81,73,0.20);
    border-radius: var(--radius); padding: 20px;
  }
  .zona-peligro-titulo {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--accent-danger) !important;
    margin: 0 0 6px;
  }
  .badge-sistema {
    display: inline-block;
    background: rgba(63,185,80,0.08);
    border: 1px solid rgba(63,185,80,0.18);
    border-radius: 20px;
    padding: 3px 14px; font-size: 0.68rem;
    color: var(--accent) !important; letter-spacing: 2px;
    text-transform: uppercase;
  }
</style>
"""
