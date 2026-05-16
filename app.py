import streamlit as st
import time
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from styles import DARK_PRO_CSS
from utils.supabase_client import (
    login, logout, session_activa,
    restaurar_sesion_desde_cookie, get_org_info,
)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Learnix DTE Hub",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# ESTILOS GLOBALES
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE — valores por defecto
# ─────────────────────────────────────────────
defaults = {
    "autenticado":      False,
    "intentos_login":   0,
    "bloqueado_hasta":  0,
    "confirmar_logout": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# RESTAURAR SESIÓN DESDE COOKIE (si la hay)
# Esto permite que al cerrar y reabrir la pestaña
# el usuario no tenga que volver a ingresar su clave.
# ─────────────────────────────────────────────
if not st.session_state["autenticado"]:
    restaurar_sesion_desde_cookie()

# ─────────────────────────────────────────────
# PANTALLA DE LOGIN
# ─────────────────────────────────────────────
if not st.session_state["autenticado"]:

    st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])

    with col:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)

        # Logo + branding
        st.markdown('<div class="login-logo">YN</div>', unsafe_allow_html=True)
        st.markdown('<span class="login-badge">LEARNIX &nbsp;·&nbsp; DTE HUB</span>', unsafe_allow_html=True)
        st.markdown('<p class="login-title">Bienvenido de nuevo</p>', unsafe_allow_html=True)
        st.markdown('<p class="login-sub">Ingresa tu correo y contraseña para acceder al sistema.</p>', unsafe_allow_html=True)

        # Estado de bloqueo / intentos
        ahora        = time.time()
        bloqueado    = st.session_state["bloqueado_hasta"] > ahora
        seg_rest     = int(st.session_state["bloqueado_hasta"] - ahora)
        intentos_act = st.session_state["intentos_login"]

        if bloqueado:
            st.error(
                f"⛔ Cuenta bloqueada temporalmente. "
                f"Vuelve a intentarlo en **{seg_rest} segundos**.",
                icon="🔒"
            )
        else:
            if intentos_act > 0:
                restantes = max(0, 5 - intentos_act)
                color = "#F85149" if restantes <= 1 else "#D29922"
                icono = "🔴" if restantes <= 1 else "⚠️"
                st.markdown(
                    f'<div class="intentos-badge">'
                    f'{icono} Intento {intentos_act} de 5 &nbsp;·&nbsp; '
                    f'<strong style="color:{color}">{restantes} restante{"s" if restantes != 1 else ""}</strong>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            with st.form("login_form", clear_on_submit=False):
                email = st.text_input(
                    "Correo electrónico",
                    placeholder="contador@firma.com",
                    label_visibility="visible"
                )
                clave = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="••••••••••",
                    label_visibility="visible"
                )

                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

                submitted = st.form_submit_button(
                    "Iniciar sesión →",
                    type="primary",
                    use_container_width=True
                )

                if submitted:
                    if not email.strip():
                        st.error("El correo electrónico es obligatorio.")
                    elif not clave:
                        st.error("La contraseña es obligatoria.")
                    else:
                        exito, msg_error = login(email.strip(), clave)
                        if exito:
                            st.session_state["confirmar_logout"] = False
                            st.rerun()
                        else:
                            st.session_state["intentos_login"] += 1
                            n = st.session_state["intentos_login"]
                            if n >= 5:
                                st.session_state["bloqueado_hasta"] = time.time() + 60
                                st.error("⛔ Demasiados intentos. Sistema bloqueado **60 segundos**.")
                            else:
                                restantes = 5 - n
                                st.error(
                                    f"{msg_error} "
                                    f"{'Último intento disponible.' if restantes == 1 else f'({restantes} intentos restantes)'}"
                                )

        st.markdown(
            '<p class="login-footer">'
            'Learnix DTE Hub &nbsp;·&nbsp; El Salvador &nbsp;·&nbsp; '
            'Sistema Tributario Electrónico'
            '</p>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

# ─────────────────────────────────────────────
# PÁGINAS (solo si autenticado)
# ─────────────────────────────────────────────
page_dashboard   = st.Page("pages/0_Dashboard_Inicio.py",                title="Dashboard Hub",               icon="🏠")
page_ventas      = st.Page("pages/1_Extractor_DTE_Ventas.py",            title="Extractor DTE Ventas",        icon="📈")
page_compras     = st.Page("pages/2_Extractor_DTE_Compras.py",           title="Extractor DTE Compras",       icon="🛒")
page_retenciones = st.Page("pages/3_Extractor_DTE_retenciones.py",       title="Extractor DTE Retenciones",   icon="✂️")
page_sujetos     = st.Page("pages/4_Extractor_DTE_Sujetos_Excluidos.py", title="Extractor Sujetos Excluidos", icon="⚖️")
page_clientes    = st.Page("pages/5_Directorio_Clientes.py",             title="Directorio Clientes",         icon="👥")
page_proveedores = st.Page("pages/6_Directorio_Proveedores.py",          title="Directorio Proveedores",      icon="🏢")

nav = st.navigation({
    "Inicio":                    [page_dashboard],
    "Módulos de Procesamiento":  [page_ventas, page_compras, page_retenciones, page_sujetos],
    "Administración":            [page_clientes, page_proveedores],
})

# ─────────────────────────────────────────────
# SIDEBAR — LOGO + CLIENTE ACTIVO
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h2 style='font-family:Courier New,monospace; color:#56D364;"
        " letter-spacing:6px; text-align:center; margin:12px 0 2px; font-size:1.6rem;'>YN</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center; font-size:0.60rem; color:#6E7681;"
        " letter-spacing:3px; margin:0 0 12px; text-transform:uppercase;'>LEARNIX DTE HUB</p>",
        unsafe_allow_html=True
    )
    st.divider()

    # ── Card: usuario conectado + organización ───────────────────────────────
    org     = get_org_info()
    perfil  = st.session_state.get("sb_perfil", {})
    _nombre_contador = perfil.get("nombre_contador") or st.session_state.get("sb_user_email", "—")
    _rol             = st.session_state.get("sb_rol", "contador")
    _rol_label       = {"admin": "Administrador", "contador": "Contador", "viewer": "Visor"}.get(_rol, _rol.title())
    _rol_color       = {"admin": "#E3B341", "contador": "#58A6FF", "viewer": "#8B949E"}.get(_rol, "#8B949E")

    if org:
        _plan       = org.get("plan_suscripcion", "starter").upper()
        _activa     = org.get("estado_activa", True)
        _dtes       = org.get("dtes_procesados_mes", 0)
        _limite     = org.get("limite_dtes_mes", 500)
        _nombre_org = org.get("nombre", "Mi Firma")
        _uso_pct    = int(_dtes / _limite * 100) if _limite else 0

        _plan_color   = {"STARTER": "#58A6FF", "PROFESIONAL": "#56D364", "ENTERPRISE": "#E3B341"}.get(_plan, "#8B949E")
        _estado_color = "#56D364" if _activa else "#F85149"
        _estado_txt   = "Activa" if _activa else "Suspendida"
        _barra_color  = "#56D364" if _uso_pct < 80 else ("#E3B341" if _uso_pct < 100 else "#F85149")

        st.markdown(
            # ── Card contador ────────────────────────────────────────────────
            f"<div style='background:#07142B; border:1px solid #21262D; border-radius:8px;"
            f" padding:11px 13px; margin-bottom:8px;'>"

            f"<div style='display:flex; align-items:center; gap:9px; margin-bottom:8px;'>"
            f"  <div style='width:34px; height:34px; border-radius:50%; background:#0D2137;"
            f"    border:2px solid {_rol_color}; display:flex; align-items:center;"
            f"    justify-content:center; font-size:1rem; flex-shrink:0;'>👤</div>"
            f"  <div style='min-width:0;'>"
            f"    <div style='color:#E6EDF3; font-weight:600; font-size:0.82rem;"
            f"      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>"
            f"      {_nombre_contador}</div>"
            f"    <div style='color:{_rol_color}; font-size:0.65rem; font-weight:700;"
            f"      letter-spacing:1px; text-transform:uppercase;'>{_rol_label}</div>"
            f"  </div>"
            f"</div>"

            # ── Separador ────────────────────────────────────────────────────
            f"<div style='border-top:1px solid #21262D; margin:0 -1px 8px;'></div>"

            # ── Card firma ───────────────────────────────────────────────────
            f"<div style='display:flex; align-items:center; gap:8px; margin-bottom:7px;'>"
            f"  <span style='font-size:0.9rem;'>🏢</span>"
            f"  <div style='min-width:0;'>"
            f"    <div style='color:#8B949E; font-size:0.60rem; letter-spacing:2px;"
            f"      text-transform:uppercase;'>FIRMA CONTABLE</div>"
            f"    <div style='color:#E6EDF3; font-size:0.80rem; font-weight:600;"
            f"      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{_nombre_org}</div>"
            f"  </div>"
            f"</div>"

            f"<div style='display:flex; justify-content:space-between; align-items:center;"
            f" margin-bottom:6px;'>"
            f"  <span style='color:{_plan_color}; font-size:0.65rem; font-weight:700;"
            f"    letter-spacing:1px;'>● {_plan}</span>"
            f"  <span style='color:{_estado_color}; font-size:0.65rem;'>● {_estado_txt}</span>"
            f"</div>"

            # ── Barra de uso DTEs ─────────────────────────────────────────────
            f"<div style='font-size:0.65rem; color:#8B949E; margin-bottom:4px;'>"
            f"  DTEs este mes: <strong style='color:#E6EDF3;'>{_dtes}</strong> / {_limite}"
            f"</div>"
            f"<div style='background:#0D2137; border-radius:4px; height:5px; overflow:hidden;'>"
            f"  <div style='background:{_barra_color}; width:{min(_uso_pct,100)}%; height:100%;"
            f"    border-radius:4px; transition:width 0.3s;'></div>"
            f"</div>"

            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        # Fallback si la org aún no cargó
        st.markdown(
            f"<div style='background:#07142B; border:1px solid #21262D; border-radius:8px;"
            f" padding:10px 13px; margin-bottom:8px; font-size:0.78rem;'>"
            f"<div style='color:#E6EDF3; font-weight:600;'>{_nombre_contador}</div>"
            f"<div style='color:{_rol_color}; font-size:0.65rem;'>{_rol_label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if st.session_state.get("cliente_activo"):
        cliente = st.session_state.cliente_activo
        st.markdown(
            f"<div class='card-cliente-activo'>"
            f"<span class='label'>CLIENTE ACTIVO</span><br>"
            f"<span class='nombre'>{cliente.get('nombre','—')}</span><br>"
            f"<span class='nit'>NIT: {cliente.get('nit','—')}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── Gemini API Key (fallback de extracción) ───────────────────────────────
    try:
        _gemini_secret = st.secrets.get("gemini", {}).get("api_key", "")
    except Exception:
        _gemini_secret = ""
    if not _gemini_secret:
        with st.expander("⚡ IA · Gemini", expanded=False):
            gemini_key = st.text_input(
                "API Key Gemini 2.5 Flash",
                type="password",
                value=st.session_state.get("gemini_api_key", ""),
                placeholder="AIza...",
                help="Mejora la extracción de nombres cuando el PDF tiene formato inusual.",
                label_visibility="collapsed",
            )
            if gemini_key != st.session_state.get("gemini_api_key", ""):
                st.session_state["gemini_api_key"] = gemini_key
                st.rerun()
            if st.session_state.get("gemini_api_key"):
                st.success("Gemini activo", icon="⚡")
            else:
                st.caption("Sin clave — extracción solo con regex.")

# ─────────────────────────────────────────────
# EJECUTAR NAVEGACIÓN
# ─────────────────────────────────────────────
nav.run()

# ─────────────────────────────────────────────
# CIERRE DE SESIÓN
# ─────────────────────────────────────────────
with st.sidebar:
    st.divider()

    if not st.session_state["confirmar_logout"]:
        if st.button("↩ Cerrar sesión", use_container_width=True, type="secondary"):
            st.session_state["confirmar_logout"] = True
            st.rerun()
    else:
        st.warning("¿Confirmas cerrar sesión?")
        c_si, c_no = st.columns(2)
        with c_si:
            if st.button("Sí, salir", type="primary", use_container_width=True):
                logout()
                st.rerun()
        with c_no:
            if st.button("Cancelar", use_container_width=True):
                st.session_state["confirmar_logout"] = False
                st.rerun()

    st.markdown(
        "<p style='text-align:center; font-size:0.62rem; color:#30363D;"
        " margin-top:10px;'>v4.0 SaaS &nbsp;·&nbsp; El Salvador</p>",
        unsafe_allow_html=True
    )
