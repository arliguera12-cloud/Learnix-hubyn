"""
Learnix DTE Hub — Sistema de Diseño Profesional
Tema: Midnight Forest Dark
"""

DARK_PRO_CSS = """
<style>
  /* ═══════════════════════════════════════
     FONDOS
  ═══════════════════════════════════════ */
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"]          { background-color: #080C09 !important; }
  [data-testid="stSidebar"]         { background-color: #0D1410 !important;
                                      border-right: 1px solid #1E3020 !important; }

  /* ═══════════════════════════════════════
     TIPOGRAFÍA
  ═══════════════════════════════════════ */
  h1                                { color: #A8E870 !important; font-weight: 700 !important;
                                      letter-spacing: -0.3px; line-height: 1.3; }
  h2                                { color: #8CC850 !important; font-weight: 600 !important; }
  h3                                { color: #7CC84A !important; font-weight: 600 !important; }
  h4, h5, h6                        { color: #68B040 !important; font-weight: 600 !important; }
  p, label, span, li                { color: #E0EED8 !important; }
  [data-testid="stDataFrame"] span  { color: inherit !important; }
  [data-testid="stMarkdownContainer"] a { color: #7CC84A !important; }
  small, .small                     { color: #6AB040 !important; font-size: 0.82rem !important; }

  /* ═══════════════════════════════════════
     MÉTRICAS
  ═══════════════════════════════════════ */
  [data-testid="stMetricValue"]  { color: #A8E870 !important; }
  [data-testid="stMetricLabel"]  { color: #7AA068 !important; font-size: 0.82rem !important; }
  [data-testid="metric-container"] {
    background: linear-gradient(145deg, #111E12, #0C1810) !important;
    border: 1px solid #1E3020 !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
  }

  /* ═══════════════════════════════════════
     BOTONES
  ═══════════════════════════════════════ */
  div.stButton > button[kind="primary"],
  div.stDownloadButton > button[kind="primary"] {
    background: linear-gradient(135deg, #3E7018 0%, #4E8820 100%) !important;
    border: 1px solid #5A9830 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 8px rgba(78,136,32,0.30) !important;
  }
  div.stButton > button[kind="primary"]:hover,
  div.stDownloadButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #4E8820 0%, #5EA830 100%) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(94,168,48,0.35) !important;
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #FFFFFF !important; font-weight: 600 !important;
  }
  div.stButton > button[kind="secondary"] {
    background-color: transparent !important;
    border: 1px solid #2E4828 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
  }
  div.stButton > button[kind="secondary"]:hover {
    background-color: #152015 !important;
    border-color: #4A7838 !important;
  }
  div.stButton > button[kind="secondary"] * { color: #7CC84A !important; }

  /* ═══════════════════════════════════════
     INPUTS
  ═══════════════════════════════════════ */
  div[data-testid="stTextInput"] input,
  div[data-testid="stNumberInput"] input {
    background-color: #0C1810 !important;
    border: 1px solid #2E4828 !important;
    border-radius: 8px !important;
    color: #E0EED8 !important;
    caret-color: #7CC84A;
  }
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stNumberInput"] input:focus {
    border-color: #4E8820 !important;
    box-shadow: 0 0 0 3px rgba(78,136,32,0.20) !important;
  }
  div[data-testid="stTextInput"] input::placeholder { color: #3A5830 !important; }

  /* ═══════════════════════════════════════
     SELECTBOX / MULTISELECT
  ═══════════════════════════════════════ */
  div[data-testid="stSelectbox"] > div > div {
    background-color: #0C1810 !important;
    border: 1px solid #2E4828 !important;
    border-radius: 8px !important;
    color: #E0EED8 !important;
  }
  [data-testid="stMultiSelect"] > div > div {
    background-color: #0C1810 !important;
    border: 1px solid #2E4828 !important;
    border-radius: 8px !important;
  }

  /* ═══════════════════════════════════════
     DATE INPUT
  ═══════════════════════════════════════ */
  div[data-testid="stDateInput"] input {
    background-color: #0C1810 !important;
    border: 1px solid #2E4828 !important;
    border-radius: 8px !important;
    color: #E0EED8 !important;
  }

  /* ═══════════════════════════════════════
     TABS
  ═══════════════════════════════════════ */
  button[data-baseweb="tab"]                       { color: #3A5830 !important; font-weight: 500 !important; }
  button[data-baseweb="tab"]:hover                 { color: #7CC84A !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom: 2px solid #5EA830 !important;
    color: #A8E870 !important;
    font-weight: 600 !important;
  }

  /* ═══════════════════════════════════════
     ALERTAS / EXPANDERS
  ═══════════════════════════════════════ */
  div[data-testid="stAlert"]          { border-radius: 8px !important; display: flex; align-items: center; }
  details > summary                   { color: #7CC84A !important; }

  /* ═══════════════════════════════════════
     SEPARADOR / SCROLLBAR
  ═══════════════════════════════════════ */
  hr { border-color: #1E3020 !important; opacity: 0.6; }
  ::-webkit-scrollbar       { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: #0D1410; }
  ::-webkit-scrollbar-thumb { background: #2E4828; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #4A7838; }

  /* ═══════════════════════════════════════
     SIDEBAR NAVEGACIÓN
  ═══════════════════════════════════════ */
  [data-testid="stSidebarNavLink"] {
    color: #6AB040 !important;
    border-radius: 6px !important;
    transition: all 0.15s ease !important;
  }
  [data-testid="stSidebarNavLink"]:hover              { background-color: #152015 !important; }
  [data-testid="stSidebarNavLink"][aria-current]      {
    background-color: #1A2C18 !important;
    border-left: 3px solid #5EA830 !important;
    color: #A8E870 !important;
  }

  /* ═══════════════════════════════════════
     DATAFRAME
  ═══════════════════════════════════════ */
  [data-testid="stDataFrame"] th {
    background-color: #111E12 !important;
    color: #6AB040 !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid #2E4828 !important;
  }

  /* ═══════════════════════════════════════
     COMPONENTES CARD
  ═══════════════════════════════════════ */
  .card-emisor {
    padding: 14px 18px;
    border-radius: 10px;
    background: linear-gradient(145deg, #111E12, #0C1810);
    border: 1px solid #1E3020;
    border-left: 3px solid #5EA830;
    margin-bottom: 20px;
    font-size: 14px;
    line-height: 1.7;
  }
  .card-emisor .label  { font-size: 0.7rem; color: #3A5830 !important; letter-spacing: 1.5px; text-transform: uppercase; }
  .card-emisor .nombre { color: #A8E870 !important; font-weight: 700; font-size: 1.05rem; }
  .card-emisor .nit    { color: #6AB040 !important; font-size: 0.85rem; }
  .card-emisor strong  { color: #A8E870 !important; }

  /* ═══════════════════════════════════════
     PANEL DE FILTROS
  ═══════════════════════════════════════ */
  .filter-panel {
    background: linear-gradient(145deg, #0D1410, #0C1810);
    border: 1px solid #1E3020;
    border-radius: 12px;
    padding: 16px 18px 12px;
    margin-bottom: 14px;
  }
  .filter-title {
    font-size: 0.72rem;
    color: #3A5830 !important;
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
    background: #111E12;
    border: 1px solid #2E4828;
    border-radius: 20px;
    padding: 5px 16px;
    font-size: 0.82rem;
    color: #6AB040 !important;
    margin: 6px 0 14px;
  }
  .results-badge .cnt  { font-weight: 700; color: #A8E870 !important; }
  .active-filters       { font-size: 0.75rem; color: #5EA830 !important; }

  /* ═══════════════════════════════════════
     TARJETAS DE MÓDULOS (dashboard)
  ═══════════════════════════════════════ */
  .modulo-card {
    background: linear-gradient(145deg, #111E12, #0C1810);
    padding: 24px 22px;
    border-radius: 12px;
    border: 1px solid #1E3020;
    height: 100%;
    min-height: 140px;
    transition: all 0.25s ease;
  }
  .modulo-card:hover {
    border-color: #5EA830;
    box-shadow: 0 4px 28px rgba(94,168,48,0.14);
    transform: translateY(-2px);
  }
  .modulo-icon  { font-size: 2.2rem; margin-bottom: 10px; display: block; }
  .modulo-title { font-size: 1.05rem; font-weight: 700; color: #A8E870 !important; margin-bottom: 8px; }
  .modulo-desc  { font-size: 0.875rem; color: #6AB040 !important; line-height: 1.6; }
  .modulo-badge {
    display: inline-block;
    margin-top: 10px;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.7rem;
    background-color: #1A2C18;
    color: #8CC850 !important;
    border: 1px solid #2E4828;
    letter-spacing: 0.5px;
  }

  /* ═══════════════════════════════════════
     KPI CARDS (dashboard)
  ═══════════════════════════════════════ */
  .kpi-pro {
    background: linear-gradient(145deg, #111E12, #0C1810);
    border: 1px solid #1E3020;
    border-radius: 12px;
    padding: 20px 18px;
    text-align: center;
    transition: all 0.25s ease;
  }
  .kpi-pro:hover { border-color: #4A7838; box-shadow: 0 4px 20px rgba(74,120,56,0.12); }
  .kpi-pro .value { font-size: 1.9rem; font-weight: 700; color: #A8E870 !important; line-height: 1.2; }
  .kpi-pro .label { font-size: 0.78rem; color: #6AB040 !important; margin-top: 6px; }
  .kpi-pro .sub   { font-size: 0.7rem; color: #3A5830 !important; margin-top: 3px; }

  /* ═══════════════════════════════════════
     BIENVENIDA
  ═══════════════════════════════════════ */
  .bienvenida-titulo {
    text-align: center; font-size: 2rem; font-weight: 700;
    color: #A8E870 !important; letter-spacing: -0.5px; margin-bottom: 4px;
  }
  .bienvenida-sub {
    text-align: center; font-size: 0.95rem;
    color: #4E7040 !important; margin-bottom: 0;
  }

  /* ═══════════════════════════════════════
     CLIENTE ACTIVO CARD
  ═══════════════════════════════════════ */
  .card-cliente-activo {
    padding: 14px 18px;
    border-radius: 10px;
    background: linear-gradient(145deg, #111E12, #0C1810);
    border: 1px solid #1E3020;
    border-left: 4px solid #5EA830;
    margin-bottom: 8px;
    font-size: 14px;
    line-height: 1.7;
  }
  .card-cliente-activo .label  { font-size: 0.7rem; color: #3A5830 !important; letter-spacing: 1px; text-transform: uppercase; }
  .card-cliente-activo .nombre { color: #A8E870 !important; font-weight: bold; font-size: 1rem; }
  .card-cliente-activo .nit    { color: #6AB040 !important; font-size: 0.85rem; }

  /* ═══════════════════════════════════════
     MISC
  ═══════════════════════════════════════ */
  .scroll-list {
    max-height: 200px; overflow-y: auto; padding: 8px 12px;
    background-color: #0C1810; border-radius: 8px;
    border: 1px solid #1E3020; font-family: monospace;
    font-size: 12px; color: #6AB040; line-height: 1.8;
  }
  .inbox-revision {
    background: linear-gradient(145deg, #111E12, #0C1810);
    border: 1px solid #5EA830; border-radius: 12px;
    padding: 22px; margin: 20px 0;
  }
  .inbox-revision h3 { color: #A8E870 !important; margin-top: 0; }
  .inbox-revision p  { color: #6AB040 !important; }
  .resumen-box {
    background: #111E12; border: 1px solid #1E3020;
    border-radius: 8px; padding: 14px 20px;
    margin: 12px 0; font-size: 14px; line-height: 2;
  }
  .debug-box {
    background-color: #090E09; border: 1px solid #1E3020;
    border-radius: 6px; padding: 10px 14px;
    font-family: monospace; font-size: 11px;
    color: #4E7040; line-height: 1.7; margin-top: 8px;
  }
  .badge-03 { background:#061A06; color:#4ADE80; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
  .badge-01 { background:#060E18; color:#60A5FA; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
  .badge-05 { background:#1A1406; color:#FBBF24; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
  .badge-06 { background:#180606; color:#F87171; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }

  /* ═══════════════════════════════════════
     LOGIN
  ═══════════════════════════════════════ */
  .login-box {
    background: linear-gradient(145deg, #111E12, #0D1410);
    padding: 48px 42px;
    border-radius: 16px;
    border: 1px solid #1E3020;
    box-shadow: 0 20px 60px rgba(0,0,0,0.7), 0 0 0 1px rgba(94,168,48,0.08);
  }
  .login-logo {
    text-align: center;
    font-family: 'Courier New', monospace;
    font-size: 3rem; font-weight: 900;
    letter-spacing: 10px; color: #A8E870 !important;
    margin-bottom: 2px;
    text-shadow: 0 0 40px rgba(168,232,112,0.3);
    line-height: 1;
  }
  .login-badge {
    display: block; text-align: center;
    background: #152015; border: 1px solid #2E4828;
    border-radius: 20px; padding: 3px 16px;
    font-size: 0.7rem; color: #5EA830 !important;
    letter-spacing: 3px; text-transform: uppercase;
    margin: 8px auto 18px; width: fit-content;
  }
  .login-title  { text-align: center; color: #E0EED8 !important; font-size: 1.1rem; font-weight: 500; margin: 0 0 4px; }
  .login-sub    { text-align: center; color: #3A5830 !important; font-size: 0.85rem; margin-bottom: 20px; }
  .login-footer { text-align: center; font-size: 0.7rem; color: #1E3020 !important; margin-top: 28px; }
  .intentos-badge {
    display: inline-block; background: #1A0808;
    border: 1px solid #5A2020; border-radius: 8px;
    padding: 6px 14px; font-size: 0.8rem;
    color: #F87171 !important; margin-top: 8px;
  }

  /* ═══════════════════════════════════════
     ZONA PELIGRO / SISTEMA
  ═══════════════════════════════════════ */
  .zona-peligro {
    background: linear-gradient(145deg, #1A0808, #140606);
    border: 1px solid #5A2020; border-radius: 10px; padding: 20px;
  }
  .badge-sistema {
    display: inline-block; background: #152015;
    border: 1px solid #2E4828; border-radius: 20px;
    padding: 3px 14px; font-size: 0.7rem;
    color: #5EA830 !important; letter-spacing: 2px;
  }
</style>
"""
