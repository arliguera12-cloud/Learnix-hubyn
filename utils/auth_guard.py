"""
auth_guard.py — Protección de rutas para Learnix DTE Hub SaaS.

Uso al inicio de cada página Streamlit:

    from utils.auth_guard import check_auth

    check_auth()                        # Auth + org activa (cualquier rol)
    check_auth(rol="admin")             # Solo admins
    check_auth(rol=["admin","contador"])# Admin o contador
"""
from __future__ import annotations
import streamlit as st
from utils.supabase_client import session_activa, get_org_info


def check_auth(
    rol: str | list[str] | None = None,
    verificar_suscripcion: bool = True,
) -> None:
    """
    Verifica autenticación, suscripción de la org y rol del usuario.
    Llama a st.stop() si alguna verificación falla.

    Args:
        rol: Rol requerido o lista de roles aceptados.
             None permite cualquier rol.
        verificar_suscripcion: Si True, bloquea cuando la org está inactiva.
    """
    # 1) Sesión activa
    if not session_activa():
        _bloquear(
            "⛔ Sesión expirada",
            "Tu sesión ha finalizado. Vuelve al inicio e ingresa de nuevo.",
        )

    # 2) Suscripción de la organización
    if verificar_suscripcion:
        org = get_org_info()
        if org and not org.get("estado_activa", True):
            _bloquear(
                "🔒 Suscripción inactiva",
                "Tu plan ha sido suspendido. Contacta a soporte para reactivarlo.",
                enlace_soporte=True,
            )

    # 3) Rol del usuario
    if rol is not None:
        roles_ok = [rol] if isinstance(rol, str) else list(rol)
        rol_actual = st.session_state.get("sb_rol", "contador")
        if rol_actual not in roles_ok:
            _bloquear(
                "🚫 Acceso restringido",
                f"Esta sección requiere el rol: **{' o '.join(roles_ok)}**. "
                f"Tu rol actual es **{rol_actual}**.",
            )


def check_limite_dtes() -> bool:
    """
    Verifica si la organización puede procesar más DTEs este mes.
    Muestra advertencia si está cerca del límite.
    Retorna False (y llama st.stop()) si el límite fue alcanzado.
    """
    org = get_org_info()
    if not org:
        return True

    procesados = org.get("dtes_procesados_mes", 0)
    limite     = org.get("limite_dtes_mes", 500)
    uso_pct    = (procesados / limite * 100) if limite > 0 else 0

    if procesados >= limite:
        _bloquear(
            "📊 Límite mensual alcanzado",
            f"Tu organización ha procesado **{procesados}/{limite} DTEs** este mes. "
            "Actualiza tu plan para continuar.",
            enlace_soporte=True,
        )

    if uso_pct >= 80:
        st.warning(
            f"⚠️ Llevas **{procesados}/{limite} DTEs** procesados este mes "
            f"({uso_pct:.0f}% del límite de tu plan **{org.get('plan_suscripcion','starter').upper()}**)."
        )

    return True


# ── helpers internos ───────────────────────────────────────────────────────────

def _bloquear(titulo: str, mensaje: str, enlace_soporte: bool = False) -> None:
    """Renderiza pantalla de bloqueo y detiene la ejecución de la página."""
    st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.error(titulo)
        st.markdown(
            f"<p style='text-align:center; color:#8B949E; margin:12px 0'>{mensaje}</p>",
            unsafe_allow_html=True,
        )
        if enlace_soporte:
            st.markdown(
                "<p style='text-align:center'>"
                "📧 <a href='mailto:soporte@learnix.sv'>soporte@learnix.sv</a>"
                "</p>",
                unsafe_allow_html=True,
            )
        if st.button("← Volver al inicio", use_container_width=True):
            st.switch_page("app.py")
    st.stop()
