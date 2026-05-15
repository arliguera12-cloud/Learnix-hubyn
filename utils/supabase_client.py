"""
Supabase client — singleton compartido por toda la app.
Lee credenciales exclusivamente desde st.secrets (nunca desde la UI).
"""
from __future__ import annotations
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase() -> Client:
    """Retorna el cliente Supabase. Se inicializa una sola vez por proceso."""
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


# ── Auth helpers ──────────────────────────────────────────────────────────────

def login(email: str, password: str) -> tuple[bool, str]:
    """
    Intenta iniciar sesión con Supabase Auth.
    Devuelve (éxito, mensaje_error).
    En caso de éxito guarda sesión y usuario en st.session_state.
    """
    sb = get_supabase()
    try:
        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["autenticado"]       = True
        st.session_state["sb_session"]        = resp.session
        st.session_state["sb_user"]           = resp.user
        st.session_state["sb_user_email"]     = resp.user.email
        st.session_state["intentos_login"]    = 0
        st.session_state["bloqueado_hasta"]   = 0
        return True, ""
    except Exception as e:
        msg = str(e)
        if "Invalid login credentials" in msg or "invalid_credentials" in msg:
            return False, "Correo o contraseña incorrectos."
        if "Email not confirmed" in msg:
            return False, "Confirma tu correo antes de ingresar."
        return False, "Error de conexión. Intenta de nuevo."


def logout() -> None:
    """Cierra sesión en Supabase y limpia el session_state."""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    conservar = {"intentos_login", "bloqueado_hasta"}
    for k in [k for k in st.session_state if k not in conservar]:
        del st.session_state[k]


def session_activa() -> bool:
    """True si hay sesión válida en st.session_state."""
    return bool(st.session_state.get("autenticado") and st.session_state.get("sb_session"))


# ── DB helpers ────────────────────────────────────────────────────────────────

def cargar_clientes_db() -> list[dict]:
    """Carga los clientes del usuario autenticado desde Supabase."""
    try:
        sb = get_supabase()
        resp = sb.table("clientes").select("*").order("nombre_comercial").execute()
        return resp.data or []
    except Exception:
        return []


def guardar_cliente_db(nit: str, nombre: str, nrc: str = "", dui: str = "", actividad: str = "") -> bool:
    """Inserta o actualiza un cliente. Retorna True si éxito."""
    try:
        sb = get_supabase()
        user_id = st.session_state["sb_user"].id
        sb.table("clientes").upsert({
            "user_id":          user_id,
            "nit":              nit,
            "nombre_comercial": nombre.strip().upper(),
            "nrc":              nrc,
            "dui":              dui,
            "actividad":        actividad.strip().upper(),
        }, on_conflict="user_id,nit").execute()
        return True
    except Exception:
        return False


def eliminar_cliente_db(cliente_id: str) -> bool:
    """Elimina un cliente por su UUID. Retorna True si éxito."""
    try:
        get_supabase().table("clientes").delete().eq("id", cliente_id).execute()
        return True
    except Exception:
        return False


def guardar_dte_db(cliente_id: str, row: dict) -> bool:
    """Persiste un DTE procesado en dte_procesados. Retorna True si éxito."""
    try:
        sb = get_supabase()
        user_id = st.session_state["sb_user"].id
        sb.table("dte_procesados").insert({
            "user_id":        user_id,
            "cliente_id":     cliente_id,
            "tipo_dte":       str(row.get("tipo", "")),
            "fecha_emision":  str(row.get("fecha", "")),
            "numero_control": str(row.get("num_control", "")),
            "sello":          str(row.get("sello", "")),
            "uuid_dte":       str(row.get("gen", "")),
            "nit_emisor":     str(row.get("nit_emi", row.get("nit_prov", ""))),
            "nit_receptor":   str(row.get("nit_rec", row.get("nit_cli", ""))),
            "monto_total":    float(row.get("tot", 0)),
            "monto_gravado":  float(row.get("gra", 0)),
            "monto_exento":   float(row.get("exe", 0)),
            "monto_iva":      float(row.get("iva", 0)),
            "monto_retencion":float(row.get("ret", 0)),
            "json_data":      row,
            "archivo_nombre": str(row.get("archivo", "")),
        }).execute()
        return True
    except Exception:
        return False
