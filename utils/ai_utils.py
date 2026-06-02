"""
Learnix Hub — AI Utils v2.0 (Groq Cloud / llama3-8b-8192).

Mejoras sobre v1.0:
  - Circuit breaker: pausa envíos si error_rate supera el umbral (evita thundering herd)
  - Misma interfaz pública que gemini_utils.py (compatibilidad total)
"""
from __future__ import annotations
import json
import logging
import os
import re
import threading
import time

import streamlit as st
from groq import Groq

log = logging.getLogger(__name__)

_GROQ_MODEL     = "llama3-8b-8192"
_MAX_RETRIES    = 3
_BACKOFF_DELAYS = [2, 4, 8]

# ─── Estado del módulo ────────────────────────────────────────────────────────
_ultimo_error: str = ""
_ultimo_audit: dict = {}
_audit_lock = threading.Lock()

# ─── Circuit Breaker ──────────────────────────────────────────────────────────
# Evita que múltiples hilos sigan golpeando la API cuando está caída.
_CB_THRESHOLD  = 5     # errores consecutivos antes de abrir el circuito
_CB_TIMEOUT    = 60    # segundos en estado OPEN antes de intentar de nuevo

_cb_lock   = threading.Lock()
_cb_state  = {
    "errors"    : 0,
    "open"      : False,
    "open_until": 0.0,
}


def _cb_is_open() -> bool:
    """Retorna True si el circuito está abierto (no enviar requests)."""
    with _cb_lock:
        if not _cb_state["open"]:
            return False
        if time.time() >= _cb_state["open_until"]:
            # Half-open: deja pasar UN intento de prueba
            _cb_state["open"] = False
            _cb_state["errors"] = 0
            log.info("Circuit breaker → HALF-OPEN, permitiendo prueba")
            return False
        return True


def _cb_on_success() -> None:
    with _cb_lock:
        _cb_state["errors"] = 0
        _cb_state["open"]   = False


def _cb_on_failure() -> None:
    with _cb_lock:
        _cb_state["errors"] += 1
        if _cb_state["errors"] >= _CB_THRESHOLD:
            _cb_state["open"]       = True
            _cb_state["open_until"] = time.time() + _CB_TIMEOUT
            log.warning(
                "Circuit breaker → OPEN tras %d errores. Pausa de %ds.",
                _cb_state["errors"], _CB_TIMEOUT,
            )


def circuit_breaker_status() -> dict:
    """Estado actual del circuit breaker (para mostrar en sidebar/UI)."""
    with _cb_lock:
        return {
            "open"      : _cb_state["open"],
            "errors"    : _cb_state["errors"],
            "open_until": _cb_state["open_until"],
            "threshold" : _CB_THRESHOLD,
        }


# ─── API key & disponibilidad ─────────────────────────────────────────────────

def _get_api_key() -> str:
    try:
        return st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "")


def gemini_disponible() -> bool:
    """Retorna True si la API key de Groq está configurada y el circuito está cerrado."""
    return bool(_get_api_key()) and not _cb_is_open()


def groq_disponible() -> bool:
    """Alias explícito de gemini_disponible()."""
    return gemini_disponible()


def gemini_ultimo_error() -> str:
    return _ultimo_error


def gemini_ultimo_audit() -> dict:
    return _ultimo_audit


# ─── Validadores de calidad de nombre ────────────────────────────────────────

_SOSPECHOSO = re.compile(
    r"""^(?:
        FECHA\s+(?:Y\s+HORA|PROCESADO|DE\s+EMISION|EMISION)|
        M[OÓ]DULO\s+DE|
        MODELO\s+(?:DE\s+)?FACTURACI[OÓ]N|
        C[OÓ]DIGO\s+(?:DE\s+)?GENERACI[OÓ]N|
        NUMERO\s+DE\s+CONTROL|
        SELLO|TIPO\s+DE|
        RAZ[OÓ]N\s+SOCIAL\s*:|
        NIT\s*:|NRC\s*:|
        \d{2}[/\-]\d{2}[/\-]\d{4}
    )""",
    re.I | re.X,
)
_PAT_FECHA_STR = re.compile(r'\d{2}[/\-]\d{2}[/\-]\d{4}')
_PAT_HORA      = re.compile(r'\b\d{2}:\d{2}:\d{2}\b')
_PAT_META      = re.compile(r'\b(?:PROCESADO|MODELO\s+FACTURACI|GENERACI[OÓ]N\s*:)', re.I)
_PAT_DDMMYYYY  = re.compile(r'^\d{2}/\d{2}/20\d{2}$')

_ANTIPATRONES_NOMBRE = re.compile(
    r'\b(?:RAZ[OÓ]N\s+SOCIAL|NOMBRE\s+O\s+RAZ|NOMBRE\s+COMERCIAL|'
    r'NIT\s*:|NRC\s*:|COD\.\s*GEN|CODIGO\s+DE\s+GENERACION|'
    r'DTE-\d{2}|FACTURA\s+CAMBIARIA|COMPROBANTE\s+DE\s+CR[EÉ]DITO|'
    r'DOCUMENTO\s+TRIBUTARIO|SELLO\s+DE\s+RECEP|NUMERO\s+DE\s+CONTROL)\b',
    re.I,
)


def es_nombre_sospechoso(nombre: str) -> bool:
    if not nombre:
        return False
    n = nombre.strip().upper()
    if _SOSPECHOSO.match(n):
        return True
    if _PAT_FECHA_STR.search(n) or _PAT_HORA.search(n) or _PAT_META.search(n):
        return True
    if _ANTIPATRONES_NOMBRE.search(n):
        return True
    if re.search(r'[A-F0-9]{20,}', n) and ' ' not in n:
        return True
    if len(n) > 5 and sum(c.isdigit() for c in n) / len(n) > 0.40:
        return True
    return False


# ─── Contexto fiscal y reglas CoT ────────────────────────────────────────────

_CONTEXTO_FISCAL = """
╔══════════════════════════════════════════════════════════════════════╗
║  MARCO LEGAL — MANUAL DE IVA DGII / SISTEMA DTE EL SALVADOR         ║
╠══════════════════════════════════════════════════════════════════════╣
║  DTE-01  Factura                        → Venta a consumidor final   ║
║  DTE-03  Comprobante de Crédito Fiscal  → Entre contribuyentes IVA   ║
║  DTE-05  Nota de Crédito               → Reducción/anulación DTE-03 ║
║  DTE-06  Nota de Débito                → Cargo adicional DTE-03      ║
║  DTE-07  Comprobante de Retención      → Agente retiene 1% IVA       ║
║  DTE-11  Factura de Exportación        → Tasa 0%, exportaciones      ║
║  DTE-14  Comprobante de Liquidación    → Sujeto excluido (no IVA)    ║
╠══════════════════════════════════════════════════════════════════════╣
║  NIT  : EXACTAMENTE 14 dígitos  (formato XXXX-XXXXXX-XXX-X)         ║
║  NRC  : 1-7 dígitos, solo contribuyentes inscritos en IVA           ║
║  DUI  : EXACTAMENTE 9 dígitos   (formato XXXXXXXX-X)                ║
║  UUID : XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX (32 hex + guiones)     ║
╚══════════════════════════════════════════════════════════════════════╝
REGLA CRÍTICA: El NIT del EMISOR NUNCA puede ser igual al del RECEPTOR.
REGLAS MATEMÁTICAS DGII:
  IVA (DTE-03/05/06)  = Ventas Gravadas × 13%             (tolerancia ±$0.02)
  Retención (DTE-07)  = Monto Sujeto × 1%                 (tolerancia ±$0.02)
  Retención (DTE-14)  = Base Compras × 10%                 (tolerancia ±$0.02)
IDENTIFICACIÓN DUAL: el emisor/sujeto puede usar DUI (9 dígitos) si es persona natural.
"""

_INSTRUCCIONES_COT = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROCESO DE EXTRACCIÓN — 4 PASOS OBLIGATORIOS (Chain of Thought)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 ▶ LOCALIZA LA SECCIÓN OBJETIVO
  Busca marcadores: "DATOS DEL EMISOR", "EMISOR:", "PROVEEDOR:",
  "DATOS DEL RECEPTOR", "RECEPTOR:", "ADQUIRIENTE:".

PASO 2 ▶ DISTINGUE ETIQUETAS DE VALORES REALES
  ETIQUETA = texto fijo que describe el campo, termina en ":"
  VALOR    = el texto que viene INMEDIATAMENTE DESPUÉS del ":"

PASO 3 ▶ LIMPIA EL VALOR BRUTO
  Elimina: prefijos residuales, UUIDs, horas, marcas de versión.

PASO 4 ▶ AUTO-VALIDACIÓN
  Inválido si: nombre contiene etiquetas/metadata, NIT no tiene 14 dígitos,
  DUI no tiene 9 dígitos, fecha fuera de rango 2020-2030.

ESCALA DE CONFIANZA (auditoria_ia.confianza_extraccion):
  95-100: valor extraído directamente, sin ambigüedad
  80-94 : extracción con alta certeza, limpieza menor
  60-79 : valor inferido, posible revisión manual
  0-59  : alta incertidumbre — se recomienda revisión manual

SIEMPRE completa auditoria_ia con:
  modelo_utilizado      = "llama3-8b-8192"
  confianza_extraccion  = número entero 0-100
  notas_de_razonamiento = resumen en 1-2 oraciones
"""

_FORMATO_JSON_BASE = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO DE RESPUESTA — JSON ESTRICTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Responde ÚNICAMENTE con un objeto JSON válido.
NO incluyas texto introductorio, saludos, ni bloques de código Markdown (```json).
Usa null (sin comillas) para campos que ya están correctos o no encontraste.
"""


# ─── Constructores de prompt por tipo de DTE ─────────────────────────────────

def _prompt_compras(texto_pdf, campos, nit_receptor, nom_receptor) -> str:
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL: El RECEPTOR es el cliente activo (comprador). El EMISOR es el proveedor — verifica sus datos.

RECEPTOR (comprador):
  NIT   : {nit_receptor}
  Nombre: {nom_receptor}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision : "{campos.get('fecha', '')}"
  nit_emisor    : "{campos.get('nit_prov', '')}"
  nombre_emisor : "{campos.get('nom_prov', '')}"

TEXTO DEL PDF:
{texto_pdf[:3500]}

{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR:
  • fecha    : Fecha de EMISIÓN en formato DD/MM/YYYY
  • nit_prov : NIT del EMISOR (14 dígitos); NO puede ser {nit_receptor}
  • nom_prov : Razón social del EMISOR; NO puede ser "{nom_receptor}" ni metadata
{_FORMATO_JSON_BASE}
Estructura requerida:
{{
  "razonamiento": {{"ubicacion_seccion": "...", "etiqueta_vs_valor": "...", "limpieza_aplicada": "...", "autovalidacion": "..."}},
  "fecha": "DD/MM/YYYY o null",
  "nit_prov": "14 dígitos o null",
  "nom_prov": "nombre del emisor o null",
  "correcciones": ["descripción de cada campo modificado"],
  "auditoria_ia": {{"modelo_utilizado": "llama3-8b-8192", "confianza_extraccion": 0, "notas_de_razonamiento": "..."}}
}}"""


def _prompt_ventas(texto_pdf, campos, nit_emisor, nom_emisor) -> str:
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL: El EMISOR es el cliente activo (vendedor). El RECEPTOR es el comprador — verifica sus datos.

EMISOR (vendedor):
  NIT   : {nit_emisor}
  Nombre: {nom_emisor}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision  : "{campos.get('fecha', '')}"
  nit_receptor   : "{campos.get('nit_cli', '')}"
  dui_receptor   : "{campos.get('dui_cli', '')}"
  nombre_receptor: "{campos.get('nom_cli', '')}"

TEXTO DEL PDF:
{texto_pdf[:3500]}

{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR:
  • fecha   : Fecha de EMISIÓN en formato DD/MM/YYYY
  • nom_cli : Nombre del RECEPTOR; NO puede ser "{nom_emisor}"
  • nit_cli : NIT del receptor (14 dígitos); null si es consumidor final con DUI
  • dui_cli : DUI del receptor (9 dígitos); solo si es persona natural
{_FORMATO_JSON_BASE}
Estructura requerida:
{{
  "razonamiento": {{"ubicacion_seccion": "...", "etiqueta_vs_valor": "...", "limpieza_aplicada": "...", "autovalidacion": "..."}},
  "fecha": "DD/MM/YYYY o null",
  "nit_cli": "14 dígitos o null",
  "dui_cli": "9 dígitos o null",
  "nom_cli": "nombre del receptor o null",
  "correcciones": ["descripción de cada campo modificado"],
  "auditoria_ia": {{"modelo_utilizado": "llama3-8b-8192", "confianza_extraccion": 0, "notas_de_razonamiento": "..."}}
}}"""


def _prompt_retenciones(texto_pdf, campos, nit_cliente, nom_cliente) -> str:
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL (DTE-07): El AGENTE RETENEDOR es el cliente activo. El SUJETO RETENIDO es el proveedor.

AGENTE RETENEDOR:
  NIT   : {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision : "{campos.get('fecha', '')}"
  nit_proveedor : "{campos.get('nit_prov', '')}"

TEXTO DEL PDF:
{texto_pdf[:3500]}

{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR:
  • fecha   : Fecha de EMISIÓN en formato DD/MM/YYYY
  • nit_prov: NIT del SUJETO RETENIDO (14 dígitos); NO puede ser {nit_cliente}
{_FORMATO_JSON_BASE}
Estructura requerida:
{{
  "razonamiento": {{"ubicacion_seccion": "...", "etiqueta_vs_valor": "...", "limpieza_aplicada": "...", "autovalidacion": "..."}},
  "fecha": "DD/MM/YYYY o null",
  "nit_prov": "14 dígitos o null",
  "correcciones": ["descripción de cada campo modificado"],
  "auditoria_ia": {{"modelo_utilizado": "llama3-8b-8192", "confianza_extraccion": 0, "notas_de_razonamiento": "..."}}
}}"""


def _prompt_sujetos_excluidos(texto_pdf, campos, nit_cliente, nom_cliente) -> str:
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL (DTE-14): El COMPRADOR es el cliente activo. El SUJETO EXCLUIDO no está inscrito en IVA.

COMPRADOR:
  NIT   : {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision : "{campos.get('fecha', '')}"
  nit_sujeto    : "{campos.get('nit_sujeto', '')}"
  dui_sujeto    : "{campos.get('dui_sujeto', '')}"
  nombre_sujeto : "{campos.get('nom_sujeto', '')}"

TEXTO DEL PDF:
{texto_pdf[:3500]}

{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR:
  • fecha      : Fecha de EMISIÓN en formato DD/MM/YYYY
  • nom_sujeto : Nombre del sujeto excluido; NO puede ser "{nom_cliente}"
  • nit_sujeto : NIT (14 dígitos) si es persona jurídica; null si no aplica
  • dui_sujeto : DUI (9 dígitos) si es persona natural; null si no aplica
{_FORMATO_JSON_BASE}
Estructura requerida:
{{
  "razonamiento": {{"ubicacion_seccion": "...", "etiqueta_vs_valor": "...", "limpieza_aplicada": "...", "autovalidacion": "..."}},
  "fecha": "DD/MM/YYYY o null",
  "nit_sujeto": "14 dígitos o null",
  "dui_sujeto": "9 dígitos o null",
  "nom_sujeto": "nombre del sujeto o null",
  "correcciones": ["descripción de cada campo modificado"],
  "auditoria_ia": {{"modelo_utilizado": "llama3-8b-8192", "confianza_extraccion": 0, "notas_de_razonamiento": "..."}}
}}"""


# ─── Llamada central a Groq (con circuit breaker) ────────────────────────────

def _llamar_groq(prompt: str) -> dict | None:
    global _ultimo_error
    api_key = _get_api_key()
    if not api_key:
        _ultimo_error = "GROQ_API_KEY no configurada en secrets.toml o variables de entorno."
        log.warning("Groq: API key ausente")
        return None

    if _cb_is_open():
        secs = int(_cb_state["open_until"] - time.time())
        _ultimo_error = f"Groq temporalmente suspendido (circuit breaker abierto, ~{secs}s restantes)."
        log.warning("Groq call blocked by circuit breaker")
        return None

    client = Groq(api_key=api_key)

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un extractor de datos fiscales. "
                            "Responde ÚNICAMENTE con JSON válido, sin texto adicional, "
                            "sin bloques de código Markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content or ""
            raw = raw.strip()
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
            raw = re.sub(r'\s*```\s*$', '', raw)

            resultado = json.loads(raw)
            _cb_on_success()
            _ultimo_error = ""
            return resultado

        except json.JSONDecodeError as e:
            _ultimo_error = f"Groq devolvió JSON inválido: {e}"
            log.warning("Groq JSON error: %s", e)
            _cb_on_failure()
            return None

        except Exception as exc:
            msg = str(exc)
            if "rate_limit" in msg.lower() or "429" in msg:
                _ultimo_error = "Límite de tasa de Groq alcanzado."
                _cb_on_failure()
                if attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_DELAYS[attempt]
                    log.warning("Groq rate limit (attempt %d/%d), waiting %ds", attempt + 1, _MAX_RETRIES, wait)
                    time.sleep(wait)
                    continue
                _ultimo_error += f" (tras {_MAX_RETRIES} intentos)"
            elif "authentication" in msg.lower() or "401" in msg:
                _ultimo_error = "API key de Groq inválida (401). Verifica en console.groq.com."
                _cb_on_failure()
                return None
            elif "timeout" in msg.lower():
                _ultimo_error = "Timeout esperando respuesta de Groq."
                _cb_on_failure()
                return None
            elif "connection" in msg.lower():
                _ultimo_error = "Sin conexión a Internet para llamar a Groq."
                _cb_on_failure()
                return None
            else:
                _ultimo_error = f"Error inesperado de Groq: {msg[:120]}"
                _cb_on_failure()
                log.error("Groq unexpected error: %s", msg)
                return None

    return None


# ─── Normalización de montos ──────────────────────────────────────────────────

def normalizar_monto_ia(raw) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", ""):
        return None
    if "," in s and "." in s:
        if s.index(".") < s.index(","):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ─── Validadores de campos post-respuesta ────────────────────────────────────

def _validar_fecha(nueva, actual: str) -> str | None:
    if not nueva or str(nueva).lower() == "null":
        return None
    nueva = str(nueva).strip()
    if _PAT_DDMMYYYY.match(nueva) and nueva != actual:
        return nueva
    return None


def _validar_nombre(nuevo, actual: str, excluir_prefijo: str = "") -> str | None:
    if not nuevo or str(nuevo).lower() == "null":
        return None
    nuevo_str = str(nuevo).strip().upper()
    if not nuevo_str:
        return None
    if (
        nuevo_str != actual.upper()
        and not es_nombre_sospechoso(nuevo_str)
        and 3 <= len(nuevo_str) <= 120
        and (not excluir_prefijo or not nuevo_str.startswith(excluir_prefijo[:12]))
    ):
        return nuevo_str
    return None


def _validar_nit(nuevo, actual: str, excluir: set | None = None) -> str | None:
    if not nuevo or str(nuevo).lower() == "null":
        return None
    nuevo  = re.sub(r'[^0-9]', '', str(nuevo))
    excluir = excluir or set()
    if nuevo and nuevo != actual and nuevo not in excluir and len(nuevo) in (9, 14):
        return nuevo
    return None


def _extraer_campos_corregidos(resultado: dict, campos_actuales: dict, tipo_dte: str, nit_contexto: str) -> dict:
    global _ultimo_audit
    campos_corr: dict = {}
    excluir = {nit_contexto} if nit_contexto else set()

    auditoria    = resultado.get("auditoria_ia", {})
    razonamiento = resultado.get("razonamiento", {})
    audit_entry  = {**auditoria, "razonamiento": razonamiento, "tipo_dte": tipo_dte}

    with _audit_lock:
        global _ultimo_audit
        _ultimo_audit = audit_entry
        try:
            if "gemini_audit_log" not in st.session_state:
                st.session_state.gemini_audit_log = []
            st.session_state.gemini_audit_log.append(audit_entry)
            if len(st.session_state.gemini_audit_log) > 50:
                st.session_state.gemini_audit_log = st.session_state.gemini_audit_log[-50:]
        except Exception:
            pass

    fecha_ok = _validar_fecha(resultado.get("fecha"), campos_actuales.get("fecha", ""))
    if fecha_ok:
        campos_corr["fecha"] = fecha_ok

    if tipo_dte == "ventas":
        nom = _validar_nombre(resultado.get("nom_cli"), campos_actuales.get("nom_cli", ""), excluir_prefijo=nit_contexto)
        if nom:
            campos_corr["nom_cli"] = nom
        nit = _validar_nit(resultado.get("nit_cli"), campos_actuales.get("nit_cli", ""), excluir)
        if nit and len(nit) == 14:
            campos_corr["nit_cli"] = nit
        dui = _validar_nit(resultado.get("dui_cli"), campos_actuales.get("dui_cli", ""), excluir)
        if dui and len(dui) == 9:
            campos_corr["dui_cli"] = dui

    elif tipo_dte == "compras":
        nom = _validar_nombre(resultado.get("nom_prov"), campos_actuales.get("nom_prov", ""))
        if nom:
            campos_corr["nom_prov"] = nom
        nit = _validar_nit(resultado.get("nit_prov"), campos_actuales.get("nit_prov", ""), excluir)
        if nit and len(nit) == 14:
            campos_corr["nit_prov"] = nit
        elif nit and len(nit) == 9:
            campos_corr["nit_prov"] = nit

    elif tipo_dte == "retenciones":
        nit = _validar_nit(resultado.get("nit_prov"), campos_actuales.get("nit_prov", ""), excluir)
        if nit and len(nit) == 14:
            campos_corr["nit_prov"] = nit

    elif tipo_dte == "sujetos_excluidos":
        nom = _validar_nombre(resultado.get("nom_sujeto"), campos_actuales.get("nom_sujeto", ""))
        if nom:
            campos_corr["nom_sujeto"] = nom
        nit = _validar_nit(resultado.get("nit_sujeto"), campos_actuales.get("nit_sujeto", ""), excluir)
        if nit and len(nit) == 14:
            campos_corr["nit_sujeto"] = nit
        dui = _validar_nit(resultado.get("dui_sujeto"), campos_actuales.get("dui_sujeto", ""), excluir)
        if dui and len(dui) == 9:
            campos_corr["dui_sujeto"] = dui

    return campos_corr


# ─── UI Helper: visualización del audit ──────────────────────────────────────

def mostrar_audit_gemini(archivo: str = "", container=None) -> None:
    audit = gemini_ultimo_audit()
    if not audit:
        return

    target = container or st
    titulo = f"🔬 Trazabilidad IA — Auditoría de Extracción{f': {archivo}' if archivo else ''}"

    with target.expander(titulo, expanded=False):
        modelo    = audit.get("modelo_utilizado", _GROQ_MODEL)
        confianza = int(audit.get("confianza_extraccion", 0))
        notas     = audit.get("notas_de_razonamiento", "—")
        tipo_dte  = audit.get("tipo_dte", "—")
        razon     = audit.get("razonamiento", {})

        col1, col2, col3 = target.columns([3, 2, 2])
        col1.metric("Modelo IA", modelo)
        col2.metric("Tipo DTE", tipo_dte.upper())
        col3.metric("Confianza", f"{confianza}%")

        if confianza >= 85:
            bar_color, nivel_txt = "#6AB040", "Alta confianza"
        elif confianza >= 65:
            bar_color, nivel_txt = "#F0A500", "Confianza moderada — revisar si hay dudas"
        else:
            bar_color, nivel_txt = "#E53935", "Baja confianza — se recomienda revisión manual"

        target.markdown(
            f"""<div style="background:#1A2C18;border-radius:6px;padding:4px 10px;margin:4px 0">
            <div style="background:{bar_color};width:{confianza}%;height:8px;border-radius:4px"></div>
            <small style="color:{bar_color}">{nivel_txt}</small></div>""",
            unsafe_allow_html=True,
        )
        target.info(f"📝 **Notas de razonamiento:** {notas}")

        if razon:
            with target.expander("📊 Cadena de Razonamiento (CoT)"):
                if razon.get("ubicacion_seccion"):
                    target.markdown(f"**🔍 Paso 1 — Localización:** {razon['ubicacion_seccion']}")
                if razon.get("etiqueta_vs_valor"):
                    target.markdown(f"**🏷️ Paso 2 — Etiqueta vs Valor:** {razon['etiqueta_vs_valor']}")
                if razon.get("limpieza_aplicada"):
                    target.markdown(f"**🧹 Paso 3 — Limpieza:** {razon['limpieza_aplicada']}")
                if razon.get("autovalidacion"):
                    autoval = razon["autovalidacion"]
                    fn = target.success if "VÁLIDO" in autoval.upper() else target.warning
                    fn(f"**✅ Paso 4 — Auto-Validación:** {autoval}")

        audit_log = []
        try:
            audit_log = st.session_state.get("gemini_audit_log", [])
        except Exception:
            pass
        if len(audit_log) > 1:
            target.caption(f"📋 Esta sesión tiene **{len(audit_log)} documentos** procesados con IA.")


# ─── Función pública universal ────────────────────────────────────────────────

def procesar_dte_con_gemini(
    texto_pdf: str,
    tipo_dte: str,
    campos_actuales: dict,
    contexto_receptor: dict,
) -> tuple[dict, list[str]]:
    """
    Verificador universal de DTEs con Groq (llama3-8b-8192).
    Mantiene la misma firma que la versión original para compatibilidad total.
    """
    if not gemini_disponible():
        return {}, []

    nit_ctx = re.sub(r'[^0-9]', '', str(contexto_receptor.get("nit", "")))
    nom_ctx = str(contexto_receptor.get("nombre", "")).strip().upper()

    _prompt_builders = {
        "ventas"           : _prompt_ventas,
        "compras"          : _prompt_compras,
        "retenciones"      : _prompt_retenciones,
        "sujetos_excluidos": _prompt_sujetos_excluidos,
    }

    build_prompt = _prompt_builders.get(tipo_dte)
    if not build_prompt:
        log.warning("procesar_dte_con_gemini: tipo_dte desconocido '%s'", tipo_dte)
        return {}, []

    prompt    = build_prompt(texto_pdf, campos_actuales, nit_ctx, nom_ctx)
    resultado = _llamar_groq(prompt)

    if resultado is None:
        return {}, []

    correcciones = [str(c) for c in resultado.get("correcciones", []) if c]
    campos_corr  = _extraer_campos_corregidos(resultado, campos_actuales, tipo_dte, nit_ctx)
    return campos_corr, correcciones


# ─── Compatibilidad con versión anterior ─────────────────────────────────────

def necesita_verificacion(campos: dict, nit_receptor: str) -> tuple[bool, list[str]]:
    razones = []
    if campos.get("nit_prov") and nit_receptor and campos["nit_prov"] == nit_receptor:
        razones.append("NIT del emisor coincide con el del receptor")
    if not campos.get("nom_prov", "").strip():
        razones.append("Nombre del emisor vacío")
    elif es_nombre_sospechoso(campos.get("nom_prov", "")):
        razones.append(f"Nombre extraído es metadata: {campos['nom_prov'][:40]}")
    if not campos.get("fecha", "").strip():
        razones.append("Fecha de emisión no encontrada")
    if not campos.get("nit_prov", "").strip():
        razones.append("NIT del emisor no encontrado")
    return bool(razones), razones


def verificar_compra_con_gemini(
    texto_pdf: str,
    campos: dict,
    nit_receptor: str,
    nom_receptor: str,
) -> tuple[dict, list[str]]:
    """Wrapper de compatibilidad — delega a procesar_dte_con_gemini."""
    return procesar_dte_con_gemini(
        texto_pdf         = texto_pdf,
        tipo_dte          = "compras",
        campos_actuales   = campos,
        contexto_receptor = {"nit": nit_receptor, "nombre": nom_receptor},
    )


def limpiar_cache_gemini() -> None:
    pass
