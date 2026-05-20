"""
Supabase client v2.0 — Multi-tenant SaaS.

Cambios sobre v1.0:
  - Sesión persistente via cookies (streamlit-cookies-controller).
    Si el paquete no está instalado, degrada sin errores.
  - Carga de perfil + organización al hacer login.
  - Todos los helpers de DB ahora usan organizacion_id (multi-tenant).
"""
from __future__ import annotations
import logging
import streamlit as st
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ── Cliente Supabase por sesión de usuario ─────────────────────────────────────
#
# IMPORTANTE: NO usar @st.cache_resource aquí.
# cache_resource crea UN SOLO objeto compartido entre todos los usuarios.
# Eso significa que el token JWT de un usuario sobreescribe el del otro,
# rompiendo el aislamiento multi-tenant.
#
# La solución es guardar el cliente en st.session_state, que es
# independiente por cada conexión de navegador (por usuario).
#
def get_supabase() -> Client:
    """Retorna el cliente Supabase autenticado de la sesión actual."""
    if "sb_client" not in st.session_state:
        st.session_state["sb_client"] = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"],
        )
    return st.session_state["sb_client"]


# ── Persistencia de sesión via cookies ────────────────────────────────────────

_COOKIE_REFRESH = "lx_refresh_token"   # 7 días, se renueva en cada carga
_COOKIE_ACCESS  = "lx_access_token"    # 1 hora


def _cookie_ctrl():
    """Retorna CookieController o None si el paquete no está disponible."""
    try:
        from streamlit_cookies_controller import CookieController
        return CookieController()
    except Exception:
        return None


def _guardar_tokens(session) -> None:
    ctrl = _cookie_ctrl()
    if ctrl is None:
        return
    try:
        ctrl.set(_COOKIE_ACCESS,  session.access_token,  max_age=3_600)
        ctrl.set(_COOKIE_REFRESH, session.refresh_token, max_age=7 * 24 * 3_600)
    except Exception as exc:
        logger.debug("No se guardaron cookies de sesión: %s", exc)


def _limpiar_tokens() -> None:
    ctrl = _cookie_ctrl()
    if ctrl is None:
        return
    try:
        ctrl.remove(_COOKIE_ACCESS)
        ctrl.remove(_COOKIE_REFRESH)
    except Exception:
        pass


def restaurar_sesion_desde_cookie() -> bool:
    """
    Intenta restaurar la sesión del usuario desde el refresh_token guardado
    en su navegador. Llama esto UNA SOLA VEZ al inicio de app.py.

    Retorna True si la sesión fue restaurada.
    """
    if st.session_state.get("autenticado"):
        return True                 # Ya hay sesión activa en esta pestaña

    ctrl = _cookie_ctrl()
    if ctrl is None:
        return False

    try:
        refresh_token = ctrl.get(_COOKIE_REFRESH)
        if not refresh_token:
            return False

        resp = get_supabase().auth.refresh_session(refresh_token)
        if resp and resp.session:
            _poblar_session_state(resp.session, resp.user)
            _guardar_tokens(resp.session)   # Renovar tiempos de expiración
            return True
    except Exception as exc:
        # Token expirado o revocado — comportamiento normal tras 7 días
        logger.info("Restauración de sesión no disponible: %s", exc)
        _limpiar_tokens()

    return False


# ── Session state helpers ──────────────────────────────────────────────────────

def _poblar_session_state(session, user) -> None:
    """Guarda sesión, usuario y datos de org en st.session_state."""
    st.session_state["autenticado"]     = True
    st.session_state["sb_session"]      = session
    st.session_state["sb_user"]         = user
    st.session_state["sb_user_email"]   = user.email
    st.session_state["intentos_login"]  = 0
    st.session_state["bloqueado_hasta"] = 0
    _cargar_perfil_y_org(user.id)


def _cargar_perfil_y_org(user_id: str) -> None:
    """
    Carga el perfil + la organización del usuario y los guarda en session_state.
    Usa 2 queries separadas en lugar de un JOIN para ser robusto ante esquemas
    parcialmente migrados (columna organizacion_id podría no existir aún).
    Siempre garantiza que 'organizacion_id' queda definido en session_state.
    """
    sb = get_supabase()

    # ── Paso 1: cargar el perfil (sin JOIN) ───────────────────────────────────
    perfil: dict = {}
    org_id: str | None = None
    try:
        resp_p = (
            sb.table("perfiles")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        perfil = resp_p.data or {}
        org_id = perfil.get("organizacion_id")   # None si columna no existe o es NULL
    except Exception as exc:
        logger.error("Error cargando perfil de user %s: %s", user_id, exc)

    # ── Paso 1.5: auto-reparar si el usuario no tiene org asignada ───────────
    # Ocurre con cuentas pre-migración o cuando el trigger falló silenciosamente.
    if not org_id:
        try:
            resp_fix = sb.rpc("reparar_perfil_sin_org", {}).execute()
            if resp_fix.data:
                org_id = resp_fix.data
                resp_p2 = (
                    sb.table("perfiles")
                    .select("*")
                    .eq("id", user_id)
                    .single()
                    .execute()
                )
                perfil = resp_p2.data or perfil
                logger.info("Org auto-creada para user %s: %s", user_id, org_id)
        except Exception as exc:
            logger.warning("Auto-reparación de org fallida para user %s: %s", user_id, exc)

    # ── Paso 2: cargar la organización (solo si tenemos el ID) ────────────────
    org: dict = {}
    if org_id:
        try:
            resp_o = (
                sb.table("organizaciones")
                .select("*")
                .eq("id", org_id)
                .single()
                .execute()
            )
            org = resp_o.data or {}
        except Exception as exc:
            logger.error("Error cargando org %s para user %s: %s", org_id, user_id, exc)

    # ── Siempre escribir todas las claves (nunca dejar KeyError pendiente) ────
    st.session_state["sb_perfil"]       = perfil
    st.session_state["sb_organizacion"] = org
    st.session_state["sb_rol"]          = perfil.get("rol", "contador")
    st.session_state["sb_org_activa"]   = org.get("estado_activa", True)
    st.session_state["organizacion_id"] = org_id   # puede ser None → check_auth lo captura


# ── Auth helpers ───────────────────────────────────────────────────────────────

def login(email: str, password: str) -> tuple[bool, str]:
    """
    Inicia sesión con Supabase Auth y popula el session_state.
    Retorna (éxito: bool, mensaje_error: str).
    """
    try:
        resp = get_supabase().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        _poblar_session_state(resp.session, resp.user)
        _guardar_tokens(resp.session)
        return True, ""

    except Exception as exc:
        msg = str(exc)
        if "Invalid login credentials" in msg or "invalid_credentials" in msg:
            return False, "Correo o contraseña incorrectos."
        if "Email not confirmed" in msg:
            return False, "Confirma tu correo antes de ingresar."
        if "banned" in msg.lower() or "User is banned" in msg:
            return False, "Esta cuenta ha sido suspendida. Contacta a soporte."
        logger.error("Error de login inesperado: %s", msg)
        return False, "Error de conexión. Verifica tu internet e intenta de nuevo."


def logout() -> None:
    """Cierra sesión en Supabase, borra cookies y limpia st.session_state."""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    _limpiar_tokens()
    conservar = {"intentos_login", "bloqueado_hasta"}
    for k in [k for k in st.session_state if k not in conservar]:
        del st.session_state[k]


def session_activa() -> bool:
    """True si hay sesión autenticada válida en st.session_state."""
    return bool(
        st.session_state.get("autenticado")
        and st.session_state.get("sb_session")
    )


# ── Org helpers ────────────────────────────────────────────────────────────────

def get_org_info() -> dict:
    """Retorna el dict de la organización activa (desde session_state o BD)."""
    org = st.session_state.get("sb_organizacion")
    if org:
        return org
    user = st.session_state.get("sb_user")
    if user:
        _cargar_perfil_y_org(user.id)
    return st.session_state.get("sb_organizacion", {})


def get_organizacion_id() -> str | None:
    """Retorna el UUID de la organización activa o None."""
    return get_org_info().get("id")


def _org_id() -> str:
    """
    Helper interno: organizacion_id garantizado.
    Lanza ValueError si no hay org asignada (no debería ocurrir en producción).
    """
    oid = get_organizacion_id()
    if not oid:
        raise ValueError(
            "El usuario no tiene organización asignada. "
            "Verifica que el trigger handle_new_user creó el perfil correctamente."
        )
    return oid


# ── DB helpers — Multi-tenant ──────────────────────────────────────────────────

def cargar_clientes_db() -> list[dict]:
    """Carga todos los clientes de la organización activa."""
    try:
        return (
            get_supabase()
            .table("clientes")
            .select("*")
            .eq("organizacion_id", _org_id())
            .order("nombre_comercial")
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.error("cargar_clientes_db: %s", exc)
        return []


def guardar_cliente_db(
    nit: str,
    nombre: str,
    nrc: str = "",
    dui: str = "",
    actividad: str = "",
) -> bool:
    """Inserta o actualiza un cliente dentro de la organización activa."""
    try:
        get_supabase().table("clientes").upsert(
            {
                "organizacion_id":  _org_id(),
                "user_id":          st.session_state["sb_user"].id,
                "nit":              nit,
                "nombre_comercial": nombre.strip().upper(),
                "nrc":              nrc,
                "dui":              dui,
                "actividad":        actividad.strip().upper(),
            },
            on_conflict="organizacion_id,nit",
        ).execute()
        return True
    except Exception as exc:
        logger.error("guardar_cliente_db: %s", exc)
        return False


def eliminar_cliente_db(cliente_id: str) -> bool:
    """
    Elimina un cliente por UUID.
    El RLS asegura que solo admins de la misma org pueden ejecutar esta acción.
    """
    try:
        get_supabase().table("clientes").delete().eq("id", cliente_id).execute()
        return True
    except Exception as exc:
        logger.error("eliminar_cliente_db: %s", exc)
        return False


def guardar_dte_db(cliente_id: str, row: dict) -> bool:
    """
    Persiste un DTE procesado vinculado a la organización activa.
    El trigger incrementar_dtes_mes() actualiza el contador mensual automáticamente.
    """
    try:
        get_supabase().table("dte_procesados").insert(
            {
                "organizacion_id":  _org_id(),
                "user_id":          st.session_state["sb_user"].id,
                "cliente_id":       cliente_id,
                "tipo_dte":         str(row.get("tipo",        "")),
                "fecha_emision":    str(row.get("fecha",       "")),
                "numero_control":   str(row.get("num_control", "")),
                "sello":            str(row.get("sello",       "")),
                "uuid_dte":         str(row.get("gen",         "")),
                "nit_emisor":       str(row.get("nit_emi",     row.get("nit_prov", ""))),
                "nit_receptor":     str(row.get("nit_rec",     row.get("nit_cli",  ""))),
                "monto_total":      float(row.get("tot",  0)),
                "monto_gravado":    float(row.get("gra",  0)),
                "monto_exento":     float(row.get("exe",  0)),
                "monto_iva":        float(row.get("iva",  0)),
                "monto_retencion":  float(row.get("ret",  0)),
                "json_data":        row,
                "archivo_nombre":   str(row.get("archivo", "")),
            }
        ).execute()
        return True
    except Exception as exc:
        logger.error("guardar_dte_db: %s", exc)
        return False


def puede_procesar_mas_dtes() -> bool:
    """
    Verifica con la BD si la organización no ha superado su límite mensual.
    Útil como guard antes de procesar lotes grandes.
    """
    try:
        resp = (
            get_supabase()
            .rpc("puede_procesar_dte", {"p_organizacion_id": _org_id()})
            .execute()
        )
        return bool(resp.data)
    except Exception as exc:
        logger.warning("puede_procesar_mas_dtes falló, permitiendo por defecto: %s", exc)
        return True


# ── DB helpers — Proveedores (sistema híbrido) ─────────────────────────────────

def cargar_proveedores_db() -> list[dict]:
    """Carga los proveedores privados de la organización activa."""
    try:
        return (
            get_supabase()
            .table("proveedores")
            .select("*")
            .eq("organizacion_id", _org_id())
            .order("nombre_comercial")
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.error("cargar_proveedores_db: %s", exc)
        return []


def guardar_proveedor_db(nit: str, nombre: str, nrc: str = "") -> bool:
    """Inserta o actualiza un proveedor en el catálogo privado de la org activa."""
    try:
        get_supabase().table("proveedores").upsert(
            {
                "organizacion_id":  _org_id(),
                "nit":              nit,
                "nombre_comercial": nombre.strip().upper(),
                "nrc":              nrc,
            },
            on_conflict="organizacion_id,nit",
        ).execute()
        return True
    except Exception as exc:
        logger.error("guardar_proveedor_db: %s", exc)
        return False


def eliminar_proveedor_db(proveedor_id: str) -> bool:
    """Elimina un proveedor por UUID (solo admins, forzado por RLS)."""
    try:
        get_supabase().table("proveedores").delete().eq("id", proveedor_id).execute()
        return True
    except Exception as exc:
        logger.error("eliminar_proveedor_db: %s", exc)
        return False


def buscar_proveedor_por_nit(nit: str) -> dict | None:
    """
    Búsqueda inteligente en 2 niveles:
      1. Catálogo privado: tabla `proveedores` (org activa, prioridad alta)
      2. Catálogo global:  tabla `proveedores_globales` (lectura para todos)

    Retorna {"nombre": str, "nrc": str, "fuente": "privado"|"global"} o None.
    """
    if not nit:
        return None
    sb = get_supabase()

    # Nivel 1: catálogo privado de la organización
    try:
        resp = (
            sb.table("proveedores")
            .select("nombre_comercial, nrc")
            .eq("organizacion_id", _org_id())
            .eq("nit", nit)
            .limit(1)
            .execute()
        )
        if resp.data:
            row = resp.data[0]
            return {
                "nombre": row["nombre_comercial"],
                "nrc":    row.get("nrc", ""),
                "fuente": "privado",
            }
    except Exception as exc:
        logger.warning("buscar_proveedor_por_nit (privado): %s", exc)

    # Nivel 2: catálogo maestro global
    try:
        resp = (
            sb.table("proveedores_globales")
            .select("nombre_comercial")
            .eq("nit", nit)
            .limit(1)
            .execute()
        )
        if resp.data:
            return {
                "nombre": resp.data[0]["nombre_comercial"],
                "nrc":    "",
                "fuente": "global",
            }
    except Exception as exc:
        logger.warning("buscar_proveedor_por_nit (global): %s", exc)

    return None


def auto_registrar_proveedor(nit: str, nombre: str, nrc: str = "") -> bool:
    """
    Registra el proveedor en el catálogo privado SOLO si no existe ya.
    Llámalo después de extraer un DTE: la BD se alimenta sola con cada factura.
    Si ya existe en el catálogo privado, no hace nada (evita escrituras innecesarias).
    """
    if not nit or not nombre.strip():
        return False
    existente = buscar_proveedor_por_nit(nit)
    if existente and existente["fuente"] == "privado":
        return True  # Ya está registrado, no tocar
    return guardar_proveedor_db(nit=nit, nombre=nombre, nrc=nrc)


def cargar_proveedores_combinados() -> dict:
    """
    Retorna dict {nit: {nombre, nrc}} con el catálogo combinado.
    Globales como base, privados encima (mayor prioridad).
    Formato compatible con el extractor de compras.
    """
    combinado: dict = {}

    # Base: globales (prioridad baja)
    try:
        resp = (
            get_supabase()
            .table("proveedores_globales")
            .select("nit, nombre_comercial")
            .execute()
        )
        for row in (resp.data or []):
            combinado[row["nit"]] = {"nombre": row["nombre_comercial"], "nrc": ""}
    except Exception as exc:
        logger.warning("cargar_proveedores_combinados (global): %s", exc)

    # Encima: privados de la org (prioridad alta, sobreescriben)
    for p in cargar_proveedores_db():
        combinado[p["nit"]] = {
            "nombre": p.get("nombre_comercial", ""),
            "nrc":    p.get("nrc", ""),
        }

    return combinado
