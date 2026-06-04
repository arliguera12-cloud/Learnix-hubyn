"""
Learnix DTE Hub — Sistema de Diseño v3.1
Tema: Stellar Dark Corporate · Modo Oscuro Profesional
Paleta: Navy oscuro + Teal (#1DB8AA) + Acentos suaves
"""

DARK_PRO_CSS = """
<style>
/* ═══════════════════════════════════════════════════════
   IMPORTAR FUENTE INTER
═══════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ═══════════════════════════════════════════════════════
   VARIABLES DEL SISTEMA DE DISEÑO — DARK MODE
═══════════════════════════════════════════════════════ */
:root {
  /* Canvas & Superficies */
  --bg-canvas:        #0A1628;
  --bg-surface:       #0F1F3A;
  --bg-card:          #122544;
  --bg-card-hover:    #16294D;
  --bg-elevated:      #1A2F58;
  --bg-input:         #0C1B33;

  /* Sidebar (un poco más oscuro que el canvas para destacar) */
  --sidebar-bg:       #07101F;
  --sidebar-surface:  #0E1A30;
  --sidebar-border:   rgba(255,255,255,0.07);
  --sidebar-text:     rgba(255,255,255,0.72);
  --sidebar-text-act: #FFFFFF;
  --sidebar-accent:   #1DB8AA;

  /* Acento Teal */
  --accent:           #1DB8AA;
  --accent-hover:     #2DD4BF;
  --accent-dark:      #0E8C80;
  --accent-light:     rgba(29,184,170,0.12);
  --accent-glow:      rgba(29,184,170,0.30);

  /* Navy */
  --navy:             #1A2B4A;
  --navy-light:       #243B64;
  --navy-muted:       #3D5580;

  /* Texto */
  --text-primary:     #E2E8F0;
  --text-secondary:   #B6C2D2;
  --text-muted:       #8A99AE;
  --text-faint:       #5B6B82;

  /* Bordes */
  --border:           #1F3358;
  --border-muted:     #152544;
  --border-accent:    rgba(29,184,170,0.40);

  /* Estados */
  --success:          #34D399;
  --success-bg:       rgba(52,211,153,0.10);
  --success-border:   rgba(52,211,153,0.35);
  --warning:          #FBBF24;
  --warning-bg:       rgba(251,191,36,0.10);
  --warning-border:   rgba(251,191,36,0.35);
  --error:            #F87171;
  --error-bg:         rgba(248,113,113,0.10);
  --error-border:     rgba(248,113,113,0.35);
  --info:             #60A5FA;
  --info-bg:          rgba(96,165,250,0.10);
  --info-border:      rgba(96,165,250,0.35);

  /* Sombras */
  --shadow-xs:        0 1px 2px rgba(0,0,0,0.30);
  --shadow-sm:        0 2px 6px rgba(0,0,0,0.35), 0 1px 2px rgba(0,0,0,0.25);
  --shadow-md:        0 6px 20px rgba(0,0,0,0.45), 0 2px 6px rgba(0,0,0,0.25);
  --shadow-lg:        0 12px 40px rgba(0,0,0,0.55), 0 4px 12px rgba(0,0,0,0.30);
  --shadow-accent:    0 4px 24px rgba(29,184,170,0.30);
  --shadow-glow:      0 0 30px rgba(29,184,170,0.20);

  /* Bordes redondeados */
  --radius-sm:        6px;
  --radius:           10px;
  --radius-lg:        14px;
  --radius-xl:        20px;

  /* Tipografía */
  --font:             'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

  /* Transiciones */
  --transition:       all 0.22s cubic-bezier(0.4,0,0.2,1);
  --transition-fast:  all 0.14s cubic-bezier(0.4,0,0.2,1);
}

/* ═══════════════════════════════════════════════════════
   RESET & BASE STREAMLIT
═══════════════════════════════════════════════════════ */
footer                               { display: none !important; }
[data-testid="stStatusWidget"]       { display: none !important; }
[data-testid="stDeployButton"]       { display: none !important; }
[data-testid="stMainMenuButton"]     { display: none !important; }
.stDecoration                        { display: none !important; }
#MainMenu                            { display: none !important; }
[data-testid="stHeader"]             { background: transparent !important; }
[data-testid="stToolbar"]            { right: 0 !important; }

[data-testid="column"],
[data-testid="stVerticalBlock"]      { background: transparent !important; }

[data-testid="stForm"] {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

/* ═══════════════════════════════════════════════════════
   PRESERVAR FUENTES DE ICONOS (Material Symbols / Font Awesome)
   IMPORTANTE: estas reglas DEBEN ir antes de las reglas que
   tocan la tipografía global de spans/labels.
═══════════════════════════════════════════════════════ */
[class*="material-symbols"],
[class*="material-icons"],
.material-icons,
.material-icons-outlined,
.material-icons-round,
.material-symbols-rounded,
.material-symbols-outlined,
.material-symbols-sharp,
[data-testid="stIconMaterial"],
[data-testid="stIcon"],
[data-testid="stExpanderToggleIcon"],
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stSidebarCollapsedControl"] span,
[data-testid="stSidebarNavSeparator"] span,
.stMarkdown svg,
i.icon,
.fa, .fas, .far, .fab, .fal {
  font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
               'Material Icons', 'Material Icons Outlined',
               'Font Awesome 6 Free', 'Font Awesome 5 Free',
               'codicon', sans-serif !important;
  font-feature-settings: 'liga' !important;
  -webkit-font-feature-settings: 'liga' !important;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24 !important;
}

/* ═══════════════════════════════════════════════════════
   CANVAS PRINCIPAL
═══════════════════════════════════════════════════════ */
[data-testid="stAppViewContainer"],
.stApp {
  background: var(--bg-canvas) !important;
  font-family: var(--font) !important;
  color: var(--text-primary) !important;
}

[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
  background: var(--bg-canvas) !important;
  padding-top: 1.5rem !important;
}

/* ═══════════════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
  background: var(--sidebar-bg) !important;
  border-right: 1px solid var(--sidebar-border) !important;
  box-shadow: 4px 0 24px rgba(0,0,0,0.40) !important;
}
[data-testid="stSidebarContent"] {
  background: var(--sidebar-bg) !important;
  padding: 0 !important;
}
[data-testid="stSidebarCollapsedControl"] {
  background: var(--sidebar-bg) !important;
  border-color: var(--sidebar-border) !important;
}

/* Botón de colapsar/expandir sidebar */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapsedControl"] button {
  background: var(--sidebar-surface) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  color: rgba(255,255,255,0.80) !important;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0 !important;
  transition: var(--transition-fast) !important;
}
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="stSidebarCollapsedControl"] button:hover {
  background: var(--accent) !important;
  color: #FFFFFF !important;
  border-color: var(--accent) !important;
}

/* Links de navegación en sidebar */
[data-testid="stSidebarNavLink"] {
  color: var(--sidebar-text) !important;
  border-radius: var(--radius-sm) !important;
  font-size: 0.855rem !important;
  font-weight: 500 !important;
  transition: var(--transition-fast) !important;
  padding: 9px 14px !important;
  margin: 1px 8px !important;
  border-left: 3px solid transparent !important;
  letter-spacing: 0.01em !important;
}
[data-testid="stSidebarNavLink"]:hover {
  background: rgba(29,184,170,0.12) !important;
  color: #FFFFFF !important;
  border-left-color: var(--accent) !important;
  transform: translateX(2px) !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: rgba(29,184,170,0.18) !important;
  border-left: 3px solid var(--accent) !important;
  color: #FFFFFF !important;
  font-weight: 600 !important;
}

/* Separadores de sección del sidebar */
[data-testid="stSidebarNavSeparator"] {
  color: rgba(255,255,255,0.40) !important;
  font-size: 0.62rem !important;
  font-weight: 700 !important;
  letter-spacing: 2.5px !important;
  text-transform: uppercase !important;
  margin: 18px 0 6px 14px !important;
  opacity: 1 !important;
}

/* Texto general en sidebar */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div:not([class*="material"]):not([class*="Icon"]) {
  color: var(--sidebar-text);
}

/* Divider en sidebar */
[data-testid="stSidebar"] hr {
  border-color: var(--sidebar-border) !important;
  margin: 12px 0 !important;
}

/* Botones en sidebar */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
  background: rgba(255,255,255,0.06) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  color: rgba(255,255,255,0.80) !important;
  border-radius: var(--radius-sm) !important;
  transition: var(--transition) !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
  background: rgba(29,184,170,0.18) !important;
  color: #FFFFFF !important;
  border-color: var(--accent) !important;
}

/* Expander en sidebar */
[data-testid="stSidebar"] [data-testid="stExpander"] {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--sidebar-border) !important;
  border-radius: var(--radius-sm) !important;
}

/* ═══════════════════════════════════════════════════════
   TIPOGRAFÍA GLOBAL
   Aplicamos color a contenedores de texto pero NO tocamos
   font-family de los <span> para no romper los íconos.
═══════════════════════════════════════════════════════ */
body, .stApp {
  font-family: var(--font) !important;
  color: var(--text-primary) !important;
  -webkit-font-smoothing: antialiased !important;
  -moz-osx-font-smoothing: grayscale !important;
}

h1 {
  color: #FFFFFF !important;
  font-weight: 800 !important;
  letter-spacing: -0.03em !important;
  line-height: 1.2 !important;
  font-size: 1.75rem !important;
}
h2 {
  color: #F1F5F9 !important;
  font-weight: 700 !important;
  letter-spacing: -0.02em !important;
  font-size: 1.35rem !important;
}
h3 {
  color: var(--accent) !important;
  font-weight: 600 !important;
  font-size: 1.1rem !important;
}
h4, h5, h6 {
  color: var(--text-secondary) !important;
  font-weight: 600 !important;
}
p, label, li {
  color: var(--text-primary) !important;
}
[data-testid="stDataFrame"] span { color: inherit !important; }
[data-testid="stMarkdownContainer"] a {
  color: var(--accent) !important;
  text-decoration: none !important;
  font-weight: 500 !important;
}
[data-testid="stMarkdownContainer"] a:hover {
  color: var(--accent-hover) !important;
  text-decoration: underline !important;
}
code {
  background: var(--bg-elevated) !important;
  color: var(--accent-hover) !important;
  padding: 2px 7px !important;
  border-radius: 4px !important;
  font-size: 0.84em !important;
  border: 1px solid var(--border) !important;
  font-weight: 500 !important;
}

/* ═══════════════════════════════════════════════════════
   BOTONES
═══════════════════════════════════════════════════════ */
[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: var(--radius) !important;
  font-weight: 600 !important;
  font-size: 0.875rem !important;
  letter-spacing: 0.01em !important;
  box-shadow: var(--shadow-accent) !important;
  transition: var(--transition) !important;
  padding: 10px 20px !important;
}
[data-testid="stBaseButton-primary"]:hover {
  background: linear-gradient(135deg, var(--accent-hover) 0%, var(--accent) 100%) !important;
  box-shadow: 0 8px 32px rgba(29,184,170,0.45) !important;
  transform: translateY(-1px) !important;
}
[data-testid="stBaseButton-primary"]:active {
  transform: translateY(0px) !important;
  box-shadow: var(--shadow-accent) !important;
}

[data-testid="stBaseButton-secondary"] {
  background: var(--bg-card) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  font-weight: 500 !important;
  font-size: 0.875rem !important;
  transition: var(--transition) !important;
}
[data-testid="stBaseButton-secondary"]:hover {
  background: var(--bg-card-hover) !important;
  border-color: var(--accent) !important;
  color: var(--accent-hover) !important;
  box-shadow: var(--shadow-sm) !important;
}

/* ═══════════════════════════════════════════════════════
   INPUTS & FORMULARIOS
═══════════════════════════════════════════════════════ */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
  background: var(--bg-input) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius) !important;
  color: var(--text-primary) !important;
  font-family: var(--font) !important;
  font-size: 0.9rem !important;
  padding: 10px 14px !important;
  transition: var(--transition-fast) !important;
  box-shadow: var(--shadow-xs) !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-glow) !important;
  outline: none !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
  color: var(--text-faint) !important;
}
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label {
  color: var(--text-secondary) !important;
  font-size: 0.82rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.02em !important;
  text-transform: uppercase !important;
  margin-bottom: 6px !important;
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
  background: var(--bg-input) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius) !important;
  color: var(--text-primary) !important;
  transition: var(--transition-fast) !important;
}
[data-testid="stSelectbox"] > div > div:hover,
[data-baseweb="select"] > div:hover {
  border-color: var(--accent) !important;
}
[data-baseweb="popover"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow-lg) !important;
}
[data-baseweb="menu"] li:hover {
  background: var(--bg-card-hover) !important;
  color: var(--accent-hover) !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
  background: var(--bg-card) !important;
  border: 2px dashed var(--border) !important;
  border-radius: var(--radius-lg) !important;
  transition: var(--transition) !important;
  padding: 8px !important;
}
[data-testid="stFileUploader"]:hover {
  border-color: var(--accent) !important;
  background: var(--accent-light) !important;
}
[data-testid="stFileUploaderDropzone"] {
  background: transparent !important;
  border: none !important;
  padding: 16px !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
  color: var(--text-secondary) !important;
}

/* ═══════════════════════════════════════════════════════
   MÉTRICAS
═══════════════════════════════════════════════════════ */
[data-testid="stMetric"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-lg) !important;
  padding: 16px 20px !important;
  box-shadow: var(--shadow-sm) !important;
  transition: var(--transition) !important;
}
[data-testid="stMetric"]:hover {
  box-shadow: var(--shadow-md) !important;
  border-color: var(--border-accent) !important;
}
[data-testid="stMetricValue"] {
  color: #FFFFFF !important;
  font-weight: 800 !important;
  font-size: 1.75rem !important;
  letter-spacing: -0.03em !important;
  line-height: 1.1 !important;
}
[data-testid="stMetricLabel"] {
  color: var(--text-secondary) !important;
  font-size: 0.78rem !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
}
[data-testid="stMetricDelta"] {
  font-size: 0.8rem !important;
  font-weight: 600 !important;
}

/* ═══════════════════════════════════════════════════════
   DATAFRAME / TABLA
═══════════════════════════════════════════════════════ */
[data-testid="stDataFrame"],
[data-testid="stDataEditor"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-lg) !important;
  overflow: hidden !important;
  box-shadow: var(--shadow-sm) !important;
  background: var(--bg-card) !important;
}
[data-testid="stDataFrame"] thead th,
[data-testid="stDataEditor"] thead th {
  background: var(--bg-elevated) !important;
  color: var(--text-secondary) !important;
  font-weight: 700 !important;
  font-size: 0.75rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  border-bottom: 2px solid var(--border) !important;
  padding: 12px 16px !important;
}
[data-testid="stDataFrame"] tbody tr:nth-child(even) {
  background: var(--bg-elevated) !important;
}
[data-testid="stDataFrame"] tbody tr:hover {
  background: var(--accent-light) !important;
}
[data-testid="stDataFrame"] tbody td {
  color: var(--text-primary) !important;
  font-size: 0.875rem !important;
  padding: 10px 16px !important;
  border-bottom: 1px solid var(--border-muted) !important;
}

/* ═══════════════════════════════════════════════════════
   ALERTAS & MENSAJES
═══════════════════════════════════════════════════════ */
[data-testid="stAlert"][data-baseweb="notification"] {
  border-radius: var(--radius) !important;
  border-left-width: 4px !important;
  font-size: 0.875rem !important;
}
[data-testid="stAlertContainer"][kind="info"] {
  background: var(--info-bg) !important;
  border-color: var(--info) !important;
  color: var(--info) !important;
}
[data-testid="stAlertContainer"][kind="success"] {
  background: var(--success-bg) !important;
  border-color: var(--success) !important;
  color: var(--success) !important;
}
[data-testid="stAlertContainer"][kind="warning"] {
  background: var(--warning-bg) !important;
  border-color: var(--warning) !important;
  color: var(--warning) !important;
}
[data-testid="stAlertContainer"][kind="error"] {
  background: var(--error-bg) !important;
  border-color: var(--error) !important;
  color: var(--error) !important;
}
[data-testid="stAlertContainer"] p,
[data-testid="stAlertContainer"] span,
[data-testid="stAlertContainer"] div {
  color: inherit !important;
}

/* ═══════════════════════════════════════════════════════
   EXPANDER
═══════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow-xs) !important;
  overflow: hidden !important;
}
[data-testid="stExpander"] summary {
  color: var(--text-primary) !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
  padding: 14px 16px !important;
  transition: var(--transition-fast) !important;
}
[data-testid="stExpander"] summary:hover {
  background: var(--bg-card-hover) !important;
  color: var(--accent-hover) !important;
}
[data-testid="stExpander"] > div[data-testid="stExpanderDetails"] {
  background: var(--bg-card) !important;
  border-top: 1px solid var(--border-muted) !important;
  padding: 16px !important;
}

/* ═══════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════ */
[data-testid="stTabs"] [role="tablist"] {
  background: var(--bg-surface) !important;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0 !important;
  padding: 6px 8px 0 !important;
  border-bottom: 2px solid var(--border) !important;
  gap: 2px !important;
}
[data-testid="stTabs"] [role="tab"] {
  color: var(--text-muted) !important;
  font-weight: 500 !important;
  font-size: 0.845rem !important;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
  padding: 9px 18px !important;
  transition: var(--transition-fast) !important;
  border: none !important;
  background: transparent !important;
  border-bottom: 2px solid transparent !important;
  margin-bottom: -2px !important;
  letter-spacing: 0.01em !important;
}
[data-testid="stTabs"] [role="tab"]:hover {
  color: var(--text-primary) !important;
  background: rgba(29,184,170,0.07) !important;
  background: rgba(29,184,170,0.07) !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  background: transparent !important;
  color: var(--accent) !important;
  font-weight: 700 !important;
  border-bottom: 2px solid var(--accent) !important;
  margin-bottom: -2px !important;
}
[data-testid="stTabs"] [role="tabpanel"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-top: none !important;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg) !important;
  padding: 20px !important;
}

/* ═══════════════════════════════════════════════════════
   PROGRESS BAR
═══════════════════════════════════════════════════════ */
[data-testid="stProgressBar"] > div > div {
  background: linear-gradient(90deg, var(--accent) 0%, var(--accent-hover) 100%) !important;
  border-radius: 99px !important;
}
[data-testid="stProgressBar"] > div {
  background: var(--border) !important;
  border-radius: 99px !important;
  height: 6px !important;
}

/* ═══════════════════════════════════════════════════════
   DIVIDER
═══════════════════════════════════════════════════════ */
hr {
  border: none !important;
  border-top: 1px solid var(--border) !important;
  margin: 16px 0 !important;
}

/* ═══════════════════════════════════════════════════════
   SPINNER
═══════════════════════════════════════════════════════ */
[data-testid="stSpinner"] {
  color: var(--accent) !important;
}

/* ═══════════════════════════════════════════════════════
   CHECKBOX & RADIO
═══════════════════════════════════════════════════════ */
[data-testid="stCheckbox"] label span,
[data-testid="stRadio"] label span {
  color: var(--text-primary) !important;
  font-size: 0.9rem !important;
}

/* ═══════════════════════════════════════════════════════
   SCROLLBAR PERSONALIZADO
═══════════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-canvas); }
::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 99px;
  transition: background 0.2s;
}
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* ═══════════════════════════════════════════════════════
   ──────  COMPONENTES PERSONALIZADOS  ──────
═══════════════════════════════════════════════════════ */

/* ── LOGO SIDEBAR ─────────────────────────────────────── */
.sidebar-logo-wrap {
  padding: 20px 16px 4px;
  text-align: center;
}
.sidebar-logo-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
  border-radius: 12px;
  font-family: 'Courier New', monospace;
  font-weight: 800;
  font-size: 1.1rem;
  color: #FFFFFF;
  letter-spacing: 1px;
  box-shadow: 0 4px 16px rgba(29,184,170,0.35);
  margin-bottom: 8px;
}
.sidebar-logo-name {
  display: block;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.45) !important;
  margin-top: 4px;
}

/* ── CARD USUARIO SIDEBAR ─────────────────────────────── */
.sidebar-user-card {
  margin: 10px 10px 6px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.09);
  border-radius: 12px;
  padding: 12px 14px;
}
.sidebar-user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(29,184,170,0.20);
  border: 2px solid var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.05rem;
  flex-shrink: 0;
}
.sidebar-user-name {
  color: #FFFFFF !important;
  font-weight: 600;
  font-size: 0.83rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sidebar-user-role {
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}
.sidebar-org-name {
  color: rgba(255,255,255,0.85) !important;
  font-size: 0.81rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sidebar-org-label {
  color: rgba(255,255,255,0.35) !important;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
}
.sidebar-plan-badge {
  display: inline-block;
  font-size: 0.60rem;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 2px 9px;
  border-radius: 99px;
}
.sidebar-quota-track {
  background: rgba(255,255,255,0.10);
  border-radius: 99px;
  height: 4px;
  overflow: hidden;
  margin-top: 4px;
}
.sidebar-quota-fill {
  height: 100%;
  border-radius: 99px;
  transition: width 0.5s ease;
}
.sidebar-divider {
  border-top: 1px solid rgba(255,255,255,0.07) !important;
  margin: 8px 0 !important;
}

/* ── CARD CLIENTE ACTIVO ──────────────────────────────── */
.card-cliente-activo {
  margin: 6px 10px;
  background: rgba(29,184,170,0.10);
  border: 1px solid rgba(29,184,170,0.30);
  border-radius: 10px;
  padding: 11px 14px;
}
.card-cliente-activo .label {
  color: var(--accent) !important;
  font-size: 0.58rem !important;
  font-weight: 700 !important;
  letter-spacing: 2.5px !important;
  text-transform: uppercase !important;
  display: block;
  margin-bottom: 3px;
}
.card-cliente-activo .nombre {
  color: #FFFFFF !important;
  font-weight: 700 !important;
  font-size: 0.84rem !important;
  display: block;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-cliente-activo .nit {
  color: rgba(255,255,255,0.55) !important;
  font-size: 0.68rem !important;
  display: block;
  font-family: 'Courier New', monospace !important;
}

/* ── VERSIÓN FOOTER SIDEBAR ───────────────────────────── */
.sidebar-version {
  text-align: center;
  font-size: 0.60rem;
  color: rgba(255,255,255,0.20) !important;
  padding: 8px 0 4px;
  letter-spacing: 1px;
}

/* ═══════════════════════════════════════════════════════
   PANTALLA DE LOGIN
═══════════════════════════════════════════════════════ */
.login-box {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  padding: 40px 36px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.50), 0 8px 24px rgba(0,0,0,0.35);
  border: 1px solid var(--border);
  position: relative;
  overflow: hidden;
}
.login-box::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--accent) 0%, var(--accent-hover) 100%);
}
.login-logo {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Courier New', monospace;
  font-weight: 800;
  font-size: 1.2rem;
  color: #FFFFFF;
  letter-spacing: 1px;
  margin: 0 auto 14px;
  box-shadow: 0 8px 24px rgba(29,184,170,0.40);
}
.login-badge {
  display: block;
  text-align: center;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: var(--accent) !important;
  margin-bottom: 20px;
}
.login-title {
  text-align: center;
  font-size: 1.45rem !important;
  font-weight: 800 !important;
  color: #FFFFFF !important;
  letter-spacing: -0.03em !important;
  margin-bottom: 6px !important;
  line-height: 1.2 !important;
}
.login-sub {
  text-align: center;
  font-size: 0.875rem !important;
  color: var(--text-secondary) !important;
  margin-bottom: 24px !important;
  line-height: 1.5 !important;
}
.intentos-badge {
  background: var(--warning-bg);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius);
  padding: 8px 14px;
  font-size: 0.82rem;
  color: var(--warning) !important;
  margin-bottom: 14px;
  text-align: center;
}
.login-footer {
  text-align: center;
  font-size: 0.72rem !important;
  color: var(--text-muted) !important;
  margin-top: 20px !important;
}

/* ═══════════════════════════════════════════════════════
   ENCABEZADO DE PÁGINAS
═══════════════════════════════════════════════════════ */
.page-header {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-surface) 100%);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  gap: 16px;
}
.page-header-icon {
  width: 48px;
  height: 48px;
  background: var(--accent-light);
  border: 1px solid var(--border-accent);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  flex-shrink: 0;
}
.page-header-title {
  font-size: 1.3rem !important;
  font-weight: 800 !important;
  color: #FFFFFF !important;
  letter-spacing: -0.02em !important;
  margin: 0 !important;
  line-height: 1.2 !important;
}
.page-header-sub {
  font-size: 0.825rem !important;
  color: var(--text-secondary) !important;
  margin: 3px 0 0 !important;
  line-height: 1.4 !important;
}

/* ── BADGE DE VERSIÓN/PLAN ────────────────────────────── */
.version-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--accent-light);
  border: 1px solid var(--border-accent);
  border-radius: 99px;
  padding: 4px 14px;
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--accent-hover) !important;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

/* ═══════════════════════════════════════════════════════
   TARJETAS KPI (DASHBOARD)
═══════════════════════════════════════════════════════ */
.kpi-pro {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
  box-shadow: var(--shadow-sm);
  transition: var(--transition);
  position: relative;
  overflow: hidden;
}
.kpi-pro::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--accent) 0%, var(--accent-hover) 100%);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}
.kpi-pro:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--border-accent);
  transform: translateY(-2px);
}
.kpi-pro .value {
  font-size: 2rem;
  font-weight: 800;
  color: #FFFFFF !important;
  letter-spacing: -0.04em;
  line-height: 1.1;
  margin-bottom: 6px;
}
.kpi-pro .label {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-secondary) !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 2px;
}
.kpi-pro .sub {
  font-size: 0.72rem;
  color: var(--text-muted) !important;
}

/* KPI con acento de color variable */
.kpi-pro.accent-green::after  { background: linear-gradient(90deg,#34D399,#10B981); }
.kpi-pro.accent-blue::after   { background: linear-gradient(90deg,#60A5FA,#3B82F6); }
.kpi-pro.accent-amber::after  { background: linear-gradient(90deg,#FBBF24,#F59E0B); }
.kpi-pro.accent-purple::after { background: linear-gradient(90deg,#A78BFA,#8B5CF6); }
.kpi-pro.accent-rose::after   { background: linear-gradient(90deg,#FB7185,#F43F5E); }

/* ─── KPI ICON ───────────────────────────────────────── */
.kpi-icon {
  width: 36px; height: 36px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
  margin-bottom: 12px;
  background: var(--accent-light);
  border: 1px solid var(--border-accent);
}

/* ═══════════════════════════════════════════════════════
   TARJETAS DE MÓDULOS
═══════════════════════════════════════════════════════ */
.modulo-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 22px 24px;
  box-shadow: var(--shadow-sm);
  transition: var(--transition);
  height: 100%;
  position: relative;
  overflow: hidden;
}
.modulo-card:hover {
  box-shadow: var(--shadow-lg);
  border-color: var(--border-accent);
  transform: translateY(-3px);
  background: var(--bg-card-hover);
}
.modulo-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 4px; height: 100%;
  background: linear-gradient(180deg, var(--accent) 0%, var(--accent-dark) 100%);
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
}
.modulo-icon {
  font-size: 1.8rem;
  display: block;
  margin-bottom: 12px;
  filter: drop-shadow(0 2px 6px rgba(29,184,170,0.30));
}
.modulo-title {
  font-size: 1rem !important;
  font-weight: 700 !important;
  color: #FFFFFF !important;
  letter-spacing: -0.01em !important;
  margin-bottom: 8px !important;
  line-height: 1.3 !important;
}
.modulo-desc {
  font-size: 0.83rem !important;
  color: var(--text-secondary) !important;
  line-height: 1.55 !important;
  margin-bottom: 14px !important;
}
.modulo-badge {
  display: inline-block;
  background: var(--accent-light);
  border: 1px solid var(--border-accent);
  color: var(--accent-hover) !important;
  font-size: 0.65rem !important;
  font-weight: 700 !important;
  letter-spacing: 1px !important;
  text-transform: uppercase !important;
  padding: 3px 10px !important;
  border-radius: 99px !important;
}

/* ═══════════════════════════════════════════════════════
   SELECTOR DE EMPRESA (DASHBOARD)
═══════════════════════════════════════════════════════ */
.selector-empresa-wrap {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 6px;
}
.selector-label {
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  color: var(--text-secondary) !important;
  letter-spacing: 2.5px !important;
  text-transform: uppercase !important;
  margin-bottom: 10px !important;
  display: flex;
  align-items: center;
  gap: 8px;
}
.selector-label::before {
  content: '';
  display: inline-block;
  width: 8px; height: 8px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 0 12px var(--accent);
}

/* ═══════════════════════════════════════════════════════
   SECCIÓN LABEL
═══════════════════════════════════════════════════════ */
.section-label {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.70rem !important;
  font-weight: 700 !important;
  color: var(--text-secondary) !important;
  letter-spacing: 2.5px !important;
  text-transform: uppercase !important;
  margin-bottom: 14px !important;
}
.section-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

/* ═══════════════════════════════════════════════════════
   ZONA DRAG & DROP
═══════════════════════════════════════════════════════ */
.dropzone-wrap {
  background: var(--bg-card);
  border: 2px dashed var(--border);
  border-radius: var(--radius-lg);
  padding: 32px 24px;
  text-align: center;
  transition: var(--transition);
  cursor: pointer;
  position: relative;
  overflow: hidden;
}
.dropzone-wrap:hover,
.dropzone-wrap.drag-over {
  border-color: var(--accent);
  background: var(--accent-light);
}
.dropzone-wrap.drag-over::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--accent-glow);
  animation: dropzone-pulse 1s ease infinite alternate;
}
@keyframes dropzone-pulse {
  from { opacity: 0.4; }
  to   { opacity: 0.9; }
}
.dropzone-icon {
  font-size: 2.5rem;
  margin-bottom: 10px;
  display: block;
  transition: transform 0.3s ease;
}
.dropzone-wrap:hover .dropzone-icon {
  transform: translateY(-4px);
}
.dropzone-title {
  font-size: 1rem !important;
  font-weight: 700 !important;
  color: #FFFFFF !important;
  margin-bottom: 4px !important;
}
.dropzone-sub {
  font-size: 0.8rem !important;
  color: var(--text-muted) !important;
}
.dropzone-formats {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.format-chip {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 99px;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--text-secondary) !important;
  letter-spacing: 1px;
  padding: 3px 10px;
  text-transform: uppercase;
}

/* ═══════════════════════════════════════════════════════
   PANEL DE FILTROS
═══════════════════════════════════════════════════════ */
.filter-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 20px 14px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-xs);
}
.filter-title {
  display: inline-block;
  font-size: 0.68rem !important;
  font-weight: 700 !important;
  color: var(--text-muted) !important;
  letter-spacing: 2px !important;
  text-transform: uppercase !important;
  margin-bottom: 12px !important;
}
.active-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.filter-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: var(--accent-light);
  border: 1px solid var(--border-accent);
  color: var(--accent-hover) !important;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 99px;
  letter-spacing: 0.5px;
}

/* ── LISTA DE ARCHIVOS SIDEBAR ────────────────────────── */
.scroll-list {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-right: 4px;
}
.scroll-list-item {
  background: var(--bg-elevated);
  border: 1px solid var(--border-muted);
  border-radius: var(--radius-sm);
  padding: 7px 12px;
  font-size: 0.78rem;
  color: var(--text-secondary) !important;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background 0.15s;
}
.scroll-list-item:hover {
  background: var(--bg-card-hover);
  color: var(--text-primary) !important;
}

/* ── ADVERTENCIA MATEMÁTICA ──────────────────────────── */
.math-warn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: var(--warning-bg);
  border: 1px solid var(--warning-border);
  color: var(--warning) !important;
  font-size: 0.70rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 99px;
  letter-spacing: 0.3px;
}

/* ── CARD EMISOR (datos del proveedor) ───────────────── */
.card-emisor {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius);
  padding: 14px 18px;
  box-shadow: var(--shadow-xs);
  margin-bottom: 12px;
}
.card-emisor-title {
  font-size: 0.60rem !important;
  font-weight: 700 !important;
  color: var(--accent) !important;
  letter-spacing: 2.5px !important;
  text-transform: uppercase !important;
  margin-bottom: 6px !important;
}
.card-emisor-nombre {
  font-size: 0.92rem !important;
  font-weight: 700 !important;
  color: #FFFFFF !important;
  margin-bottom: 3px !important;
}
.card-emisor-nit {
  font-size: 0.73rem !important;
  color: var(--text-muted) !important;
  font-family: 'Courier New', monospace !important;
}

/* ── BANDEJA DE REVISIÓN MANUAL ──────────────────────── */
.inbox-revision {
  background: var(--bg-card);
  border: 1px solid var(--warning-border);
  border-top: 3px solid var(--warning);
  border-radius: var(--radius-lg);
  padding: 16px 18px;
  box-shadow: var(--shadow-sm);
}
.inbox-revision-header {
  font-size: 0.68rem !important;
  font-weight: 700 !important;
  color: var(--warning) !important;
  letter-spacing: 2px !important;
  text-transform: uppercase !important;
  margin-bottom: 12px !important;
  display: flex;
  align-items: center;
  gap: 8px;
}
.inbox-revision-item {
  background: var(--bg-elevated);
  border: 1px solid var(--border-muted);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  margin-bottom: 8px;
  font-size: 0.84rem;
  color: var(--text-primary) !important;
  cursor: pointer;
  transition: var(--transition-fast);
}
.inbox-revision-item:hover {
  background: var(--bg-card-hover);
  border-color: var(--warning-border);
}

/* ── FILAS DE ALERTA EN TABLA ─────────────────────────── */
.alert-detail-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 14px;
  transition: background 0.15s;
}
.alert-detail-card:hover {
  background: var(--bg-card-hover);
}
.alert-detail-card.warn {
  border-left: 3px solid var(--warning);
  background: rgba(251,191,36,0.04);
}
.alert-detail-card.error {
  border-left: 3px solid var(--error);
  background: rgba(248,113,113,0.04);
}

/* ── MÉTRICAS — BARRA SUPERIOR DE COLOR ──────────────── */
[data-testid="stMetric"] {
  position: relative !important;
  overflow: hidden !important;
}
[data-testid="stMetric"]::before {
  content: '' !important;
  position: absolute !important;
  top: 0; left: 0; right: 0 !important;
  height: 3px !important;
  background: linear-gradient(90deg, var(--accent) 0%, var(--accent-hover) 100%) !important;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0 !important;
}

/* ── COLUMNAS DE ALERTAS — ALTURA UNIFORME ───────────── */
/* Fuerza que las columnas hermanas de un grupo de alertas
   estiren su contenido a la misma altura */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stMarkdownContainer"] > div[style*="min-height:80px"]) {
  align-items: stretch !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stMarkdownContainer"] > div[style*="min-height:80px"])
  > [data-testid="stColumn"] {
  display: flex !important;
  flex-direction: column !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stMarkdownContainer"] > div[style*="min-height:80px"])
  > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {
  flex: 1 !important;
}

/* ── PUNTO PULSANTE DE ESTADO ─────────────────────────── */
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.5; transform: scale(0.75); }
}
.pulse-dot {
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  animation: pulse-dot 2s ease infinite;
  vertical-align: middle;
}
.pulse-dot.green  { background: var(--success); box-shadow: 0 0 6px var(--success); }
.pulse-dot.amber  { background: var(--warning); box-shadow: 0 0 6px var(--warning); }
.pulse-dot.red    { background: var(--error);   box-shadow: 0 0 6px var(--error); }
.pulse-dot.teal   { background: var(--accent);  box-shadow: 0 0 6px var(--accent); }

/* ═══════════════════════════════════════════════════════
   BANDEJA QA / VALIDACIÓN
═══════════════════════════════════════════════════════ */
.qa-banner {
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 12px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 0.875rem;
  border-left: 4px solid;
}
.qa-banner.success { background: var(--success-bg); border-color: var(--success); color: var(--success) !important; }
.qa-banner.warning { background: var(--warning-bg); border-color: var(--warning); color: var(--warning) !important; }
.qa-banner.error   { background: var(--error-bg);   border-color: var(--error);   color: var(--error)   !important; }
.qa-icon { font-size: 1.1rem; flex-shrink: 0; margin-top: 1px; }

/* Badge de estado DTE */
.field-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  color: var(--error) !important;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 99px;
  letter-spacing: 0.5px;
  margin: 2px;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.70rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 99px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.status-badge.ok       { background: var(--success-bg); color: var(--success) !important; border: 1px solid var(--success-border); }
.status-badge.warn     { background: var(--warning-bg); color: var(--warning) !important; border: 1px solid var(--warning-border); }
.status-badge.error    { background: var(--error-bg);   color: var(--error)   !important; border: 1px solid var(--error-border); }
.status-badge.vision   { background: var(--info-bg);    color: var(--info)    !important; border: 1px solid var(--info-border); }
.status-badge.manual   { background: rgba(167,139,250,0.10); color: #C4B5FD !important; border: 1px solid rgba(167,139,250,0.35); }

/* ═══════════════════════════════════════════════════════
   PERIODO FISCAL
═══════════════════════════════════════════════════════ */
.periodo-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.periodo-icon {
  width: 34px; height: 34px;
  background: var(--accent-light);
  border: 1px solid var(--border-accent);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
}
.periodo-label {
  font-size: 0.68rem !important;
  font-weight: 700 !important;
  color: var(--text-muted) !important;
  text-transform: uppercase !important;
  letter-spacing: 1.5px !important;
  display: block;
}
.periodo-value {
  font-size: 0.92rem !important;
  font-weight: 700 !important;
  color: #FFFFFF !important;
}

/* ═══════════════════════════════════════════════════════
   TABLA DE RESULTADOS CON FILTRO JS
═══════════════════════════════════════════════════════ */
.results-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.results-count {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-secondary) !important;
  background: var(--bg-elevated);
  padding: 4px 12px;
  border-radius: 99px;
  border: 1px solid var(--border);
  white-space: nowrap;
}
.filter-input {
  flex: 1;
  min-width: 200px;
  padding: 7px 12px 7px 32px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--font);
  font-size: 0.875rem;
  color: var(--text-primary);
  background: var(--bg-input);
  outline: none;
  transition: border-color 0.2s;
}
.filter-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

/* ═══════════════════════════════════════════════════════
   BIENVENIDA / ENCABEZADO DEL DASHBOARD
═══════════════════════════════════════════════════════ */
.bienvenida-titulo {
  font-size: 1.55rem !important;
  font-weight: 800 !important;
  color: #FFFFFF !important;
  letter-spacing: -0.03em !important;
  line-height: 1.2 !important;
  margin-bottom: 4px !important;
}
.bienvenida-sub {
  font-size: 0.875rem !important;
  color: var(--text-secondary) !important;
  line-height: 1.5 !important;
}

/* ═══════════════════════════════════════════════════════
   ESTADO VACÍO
═══════════════════════════════════════════════════════ */
.empty-state {
  text-align: center;
  padding: 52px 24px;
  background: var(--bg-surface);
  border: 1px dashed var(--border);
  border-radius: var(--radius-lg);
  margin-top: 16px;
  transition: var(--transition);
}
.empty-state:hover {
  border-color: var(--border-accent);
  background: var(--bg-card);
}
.empty-state-icon { font-size: 2.5rem; margin-bottom: 12px; display: block; }
.empty-state-title {
  font-size: 1rem !important;
  font-weight: 700 !important;
  color: #FFFFFF !important;
  margin-bottom: 6px !important;
}
.empty-state-sub {
  font-size: 0.84rem !important;
  color: var(--text-secondary) !important;
  max-width: 360px;
  margin: 0 auto !important;
  line-height: 1.5 !important;
}

/* ═══════════════════════════════════════════════════════
   FOOTER
═══════════════════════════════════════════════════════ */
.app-footer {
  text-align: center;
  font-size: 0.72rem !important;
  color: var(--text-muted) !important;
  padding: 12px 0 4px !important;
}
.app-footer strong {
  color: var(--accent) !important;
  font-weight: 700 !important;
}

/* Zona de peligro (Directorio Clientes) */
.zona-peligro {
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: var(--radius);
  padding: 14px 16px;
  margin-top: 16px;
}
.zona-peligro-titulo {
  font-size: 0.82rem !important;
  font-weight: 700 !important;
  color: var(--error) !important;
  margin: 0 0 6px !important;
}

/* ═══════════════════════════════════════════════════════
   ANIMACIONES
═══════════════════════════════════════════════════════ */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.animate-fade-in     { animation: fadeIn 0.35s ease both; }
.animate-fade-in-up  { animation: fadeInUp 0.4s ease both; }
.animate-delay-1     { animation-delay: 0.05s; }
.animate-delay-2     { animation-delay: 0.10s; }
.animate-delay-3     { animation-delay: 0.15s; }
.animate-delay-4     { animation-delay: 0.20s; }
.animate-delay-5     { animation-delay: 0.25s; }

[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"]:first-child {
  animation: fadeInUp 0.4s ease both;
}

/* ═══════════════════════════════════════════════════════
   TOOLTIP
═══════════════════════════════════════════════════════ */
[data-testid="stTooltipIcon"] {
  color: var(--text-muted) !important;
}

/* ═══════════════════════════════════════════════════════
   RESPONSIVE
═══════════════════════════════════════════════════════ */
@media (max-width: 768px) {
  .kpi-pro .value { font-size: 1.5rem; }
  .login-box { padding: 28px 20px; }
  .bienvenida-titulo { font-size: 1.2rem !important; }
}
</style>
"""
