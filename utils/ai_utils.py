"""
Learnix Hub — AI Utils v5.0 (Groq motor único + Google AI opcional).

Motor PRINCIPAL: Groq Cloud
  - Texto  : llama-3.3-70b-versatile
  - Visión : meta-llama/llama-4-scout-17b-16e-instruct
  - Circuit breaker INDEPENDIENTE para Groq

Motor OPCIONAL (Google AI): se activa si GEMINI_API_KEY / VERTEX_API_KEY está
configurada Y el SDK google-genai está instalado. Si falla al inicializarse o
en cualquier llamada, se deshabilita silenciosamente SIN afectar el CB de Groq.
"""
from __future__ import annotations
import base64
import json
import logging
import os
import re
import threading
import time

import streamlit as st
from groq import Groq

log = logging.getLogger(__name__)

_GROQ_MODEL        = "llama-3.3-70b-versatile"
_GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_MAX_RETRIES       = 3
_BACKOFF_DELAYS    = [2, 4, 8]

# ─── Configuración Vertex AI (motor prioritario) ─────────────────────────────
_VERTEX_PROJECT  = "nomadic-sprite-440003-r7"
_VERTEX_LOCATION = "us-central1"
# Modelo configurable vía secrets (VERTEX_MODEL) para poder probar versiones sin
# redeploy. Default a la versión GA explícita, más estable en Vertex Express.
_VERTEX_MODEL_DEFAULT = "gemini-2.0-flash"   # modelo GA en Vertex AI real

# Umbral de confianza por debajo del cual se levanta una alerta de revisión.
_VISION_CONF_MIN   = 70

# ─── Estado del módulo ────────────────────────────────────────────────────────
_ultimo_error: str = ""
_ultimo_audit: dict = {}
_audit_lock = threading.Lock()

# ─── Circuit Breaker (solo Groq) ─────────────────────────────────────────────
# Los errores de Google AI NO afectan este CB — tienen su propio contador.
_CB_THRESHOLD  = 5
_CB_TIMEOUT    = 60

_cb_lock   = threading.Lock()
_cb_state  = {
    "errors"    : 0,
    "open"      : False,
    "open_until": 0.0,
}


def _cb_is_open() -> bool:
    with _cb_lock:
        if not _cb_state["open"]:
            return False
        if time.time() >= _cb_state["open_until"]:
            _cb_state["open"] = False
            _cb_state["errors"] = 0
            log.info("Circuit breaker Groq → HALF-OPEN, permitiendo prueba")
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
                "Circuit breaker Groq → OPEN tras %d errores. Pausa de %ds.",
                _cb_state["errors"], _CB_TIMEOUT,
            )


def circuit_breaker_status() -> dict:
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
        N[UÚ]MERO\s+DE\s+CONTROL|
        SELLO\s+DE|SELLO\s*:|
        TIPO\s+DE|TIPO\s+DTE|
        RAZ[OÓ]N\s+SOCIAL\s*:|
        NOMBRE\s+(?:COMERCIAL|DEL\s+(?:EMISOR|RECEPTOR|PROVEEDOR|CLIENTE))\s*:|
        NIT\s*:|NRC\s*:|DUI\s*:|
        AMBIENTE\s*:|ESTADO\s*:|MONEDA\s*:|CONDICI[OÓ]N\s+DE\s+OPERACI|
        \d{2}[/\-]\d{2}[/\-]\d{4}
    )""",
    re.I | re.X,
)
_PAT_FECHA_STR  = re.compile(r'\d{2}[/\-]\d{2}[/\-]\d{4}')
_PAT_HORA       = re.compile(r'\b\d{2}:\d{2}:\d{2}\b')
_PAT_META       = re.compile(r'\b(?:PROCESADO|MODELO\s+FACTURACI|GENERACI[OÓ]N\s*:)', re.I)
_PAT_DDMMYYYY   = re.compile(r'^\d{2}/\d{2}/20\d{2}$')
_PAT_SOLO_NUMS  = re.compile(r'^\d[\d\-]{5,}$')        # solo dígitos/guiones → es un ID no un nombre
_PAT_UUID_LIKE  = re.compile(r'[A-F0-9]{8}-[A-F0-9]{4}', re.I)  # fragmento UUID

_ANTIPATRONES_NOMBRE = re.compile(
    r'\b(?:'
    r'RAZ[OÓ]N\s+SOCIAL|NOMBRE\s+O\s+RAZ|NOMBRE\s+COMERCIAL|'
    r'NIT\s*:|NRC\s*:|DUI\s*:|COD\.\s*GEN|CODIGO\s+DE\s+GENERACION|'
    r'DTE-\d{2}|FACTURA\s+(?:CAMBIARIA|DE\s+EXPORTACI[OÓ]N|CONSUMIDOR)|'
    r'COMPROBANTE\s+DE\s+CR[EÉ]DITO|COMPROBANTE\s+DE\s+(?:RETENCI[OÓ]N|LIQUIDACI[OÓ]N)|'
    r'DOCUMENTO\s+TRIBUTARIO|SELLO\s+DE\s+RECEP|NUMERO\s+DE\s+CONTROL|'
    r'DATOS\s+DEL\s+(?:EMISOR|RECEPTOR|PROVEEDOR|CLIENTE)|'
    r'ACTIVIDAD\s+ECON[OÓ]MICA|TIPO\s+(?:DE\s+)?ESTABLECIMIENTO|'
    r'DIRECCI[OÓ]N|MUNICIPIO|DEPARTAMENTO|CASA\s+MATRIZ|SUCURSAL\s*\d|'
    r'TEL[EÉ]FONO|CORREO\s+ELECTR[OÓ]NICO|P[AÁ]GINA\s+WEB'
    r')\b',
    re.I,
)


def es_nombre_sospechoso(nombre: str) -> bool:
    if not nombre:
        return False
    n = nombre.strip().upper()
    # Demasiado corto para ser un nombre de empresa real
    if len(n) < 3:
        return True
    if _SOSPECHOSO.match(n):
        return True
    if _PAT_FECHA_STR.search(n) or _PAT_HORA.search(n) or _PAT_META.search(n):
        return True
    if _ANTIPATRONES_NOMBRE.search(n):
        return True
    # Fragmento de UUID incrustado
    if _PAT_UUID_LIKE.search(n):
        return True
    # Solo dígitos/guiones → es un ID, no un nombre
    if _PAT_SOLO_NUMS.match(n):
        return True
    # Cadena hex larga sin espacios (hash o código de generación)
    if re.search(r'[A-F0-9]{20,}', n) and ' ' not in n:
        return True
    # Más del 40% son dígitos → probablemente un campo numérico
    if len(n) > 5 and sum(c.isdigit() for c in n) / len(n) > 0.40:
        return True
    # Contiene @ o URLs
    if re.search(r'@|https?://|www\.', n, re.I):
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
  modelo_utilizado      = "llama-3.3-70b-versatile"
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
    try:
        from utils.training_examples import cargar_ejemplos_prompt
        _ejemplos = cargar_ejemplos_prompt("compras", max_ejemplos=3)
    except Exception:
        _ejemplos = ""
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
{texto_pdf[:6000]}

{_ejemplos}
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
  "auditoria_ia": {{"modelo_utilizado": "llama-3.3-70b-versatile", "confianza_extraccion": 0, "notas_de_razonamiento": "..."}}
}}"""


def _prompt_ventas(texto_pdf, campos, nit_emisor, nom_emisor) -> str:
    try:
        from utils.training_examples import cargar_ejemplos_prompt
        _ejemplos = cargar_ejemplos_prompt("ventas", max_ejemplos=3)
    except Exception:
        _ejemplos = ""
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
{texto_pdf[:6000]}

{_ejemplos}
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
  "auditoria_ia": {{"modelo_utilizado": "llama-3.3-70b-versatile", "confianza_extraccion": 0, "notas_de_razonamiento": "..."}}
}}"""


def _prompt_retenciones(texto_pdf, campos, nit_cliente, nom_cliente) -> str:
    try:
        from utils.training_examples import cargar_ejemplos_prompt
        _ejemplos = cargar_ejemplos_prompt("ret", max_ejemplos=3)
    except Exception:
        _ejemplos = ""
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL (DTE-07): El AGENTE RETENEDOR es el cliente activo. El SUJETO RETENIDO es el proveedor.

AGENTE RETENEDOR:
  NIT   : {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX (pueden tener errores):
  fecha_emision  : "{campos.get('fecha', '')}"
  nit_proveedor  : "{campos.get('nit_prov', '')}"
  nombre_sujeto  : "{campos.get('nom_prov', '')}"

TEXTO DEL PDF:
{texto_pdf[:6000]}

{_ejemplos}
{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR:
  • fecha   : Fecha de EMISIÓN en formato DD/MM/YYYY
  • nit_prov: NIT del SUJETO RETENIDO (14 dígitos); NO puede ser {nit_cliente}
  • nom_prov: Razón social del SUJETO RETENIDO; NO puede ser "{nom_cliente}" ni metadata
{_FORMATO_JSON_BASE}
Estructura requerida:
{{
  "razonamiento": {{"ubicacion_seccion": "...", "etiqueta_vs_valor": "...", "limpieza_aplicada": "...", "autovalidacion": "..."}},
  "fecha": "DD/MM/YYYY o null",
  "nit_prov": "14 dígitos o null",
  "nom_prov": "nombre del sujeto retenido o null",
  "correcciones": ["descripción de cada campo modificado"],
  "auditoria_ia": {{"modelo_utilizado": "llama-3.3-70b-versatile", "confianza_extraccion": 0, "notas_de_razonamiento": "..."}}
}}"""


def _prompt_sujetos_excluidos(texto_pdf, campos, nit_cliente, nom_cliente) -> str:
    try:
        from utils.training_examples import cargar_ejemplos_prompt
        _ejemplos = cargar_ejemplos_prompt("sujetos", max_ejemplos=3)
    except Exception:
        _ejemplos = ""
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
{texto_pdf[:6000]}

{_ejemplos}
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
  "auditoria_ia": {{"modelo_utilizado": "llama-3.3-70b-versatile", "confianza_extraccion": 0, "notas_de_razonamiento": "..."}}
}}"""


# ─── Motor PRIORITARIO: Vertex AI (Agent Platform) ───────────────────────────
# Vertex AI es el primer intento porque fuerza temperature=0.0 y
# response_mime_type=application/json, lo que maximiza la precisión matemática
# y garantiza un JSON estructurado válido. Si la cuota de Google falla o el SDK
# no está instalado, procesar_dte_con_gemini() recae automáticamente en Groq.

_ultimo_error_vertex: str = ""

# Cliente google-genai en modo Vertex AI Express (lazy, una sola vez).
#   None  → aún no se intentó construir
#   False → SDK ausente, sin API key o init fallido
#   <obj> → cliente listo
_vertex_client = None
_vertex_lock = threading.Lock()


def _vertex_api_key() -> str:
    """API key de Vertex AI Express. Busca en secrets y variables de entorno."""
    for nombre in ("VERTEX_API_KEY", "VERTEX_EXPRESS_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        try:
            v = st.secrets.get(nombre, "")
        except Exception:
            v = ""
        if not v:
            v = os.environ.get(nombre, "")
        if v:
            return v
    return ""


def _vertex_model() -> str:
    """Modelo de Vertex AI a usar. Configurable vía secrets/env VERTEX_MODEL."""
    try:
        v = st.secrets.get("VERTEX_MODEL", "")
    except Exception:
        v = ""
    if not v:
        v = os.environ.get("VERTEX_MODEL", "")
    return v or _VERTEX_MODEL_DEFAULT

# System prompt común a TODOS los extractores. Refuerza el mapeo milimétrico de
# campos y deja la estructura JSON exacta en manos del prompt por tipo de DTE.
_VERTEX_SYSTEM_PROMPT = (
    "Eres un AUDITOR FISCAL SENIOR y extractor de datos de DTEs de El Salvador "
    "(Documentos Tributarios Electrónicos, Manual de IVA DGII). Tu única salida "
    "es un objeto JSON válido, sin texto adicional ni bloques Markdown.\n"
    "REGLAS DE PRECISIÓN MILIMÉTRICA:\n"
    "  1. Mapea cada campo EXACTAMENTE a la etiqueta correcta del documento; "
    "nunca confundas EMISOR con RECEPTOR ni proveedor con cliente.\n"
    "  2. NIT: 14 dígitos sin guiones ni espacios. DUI: 9 dígitos. Si un "
    "identificador no cumple el largo exacto, devuélvelo como null.\n"
    "  3. Fechas SIEMPRE en formato DD/MM/YYYY.\n"
    "  4. Montos: usa punto decimal, sin separador de miles, máxima precisión "
    "matemática; copia los dígitos literalmente, no redondees ni inventes.\n"
    "  5. Si un valor no aparece o es ilegible, devuelve null; NUNCA inventes "
    "datos ni reutilices los del cliente activo para el contraparte.\n"
    "  6. Respeta al pie de la letra la estructura JSON que se solicita a "
    "continuación, incluyendo todos los nombres de clave."
)


def _get_sa_credentials():
    """
    Lee las credenciales de service account desde st.secrets[google_credentials].
    Devuelve un objeto google.oauth2.service_account.Credentials o None.
    """
    try:
        import json as _json
        from google.oauth2 import service_account
        sa = st.secrets.get("google_credentials", {})
        if not sa:
            return None
        sa_dict = dict(sa)
        creds = service_account.Credentials.from_service_account_info(
            sa_dict,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return creds
    except Exception as exc:
        log.warning("No se pudieron cargar las credenciales de SA: %s", exc)
        return None


def _get_vertex_client():
    """
    Construye (una sola vez) el cliente google-genai para Vertex AI.

    Prioridad de autenticación:
      1. [google_credentials] en secrets → service account → Vertex AI real
         (usa los créditos de Google Cloud, project=nomadic-sprite-440003-r7)
      2. VERTEX_API_KEY / GEMINI_API_KEY en secrets → Gemini Developer API
      3. Sin credenciales → False (recae en Groq)
    """
    global _vertex_client, _ultimo_error_vertex
    if _vertex_client is not None:
        return _vertex_client

    with _vertex_lock:
        if _vertex_client is not None:
            return _vertex_client

        for _ev in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION",
                    "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_APPLICATION_CREDENTIALS"):
            os.environ.pop(_ev, None)

        try:
            from google import genai

            # 1) Service account → Vertex AI real con project/location
            creds = _get_sa_credentials()
            if creds:
                _vertex_client = genai.Client(
                    vertexai=True,
                    project=_VERTEX_PROJECT,
                    location=_VERTEX_LOCATION,
                    credentials=creds,
                )
                log.info("Vertex AI inicializado con SA (proyecto=%s, modelo=%s)",
                         _VERTEX_PROJECT, _vertex_model())
                return _vertex_client

            # 2) API key → Gemini Developer API
            api_key = _vertex_api_key()
            if api_key:
                for _ev in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION",
                            "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_APPLICATION_CREDENTIALS"):
                    os.environ.pop(_ev, None)
                _vertex_client = genai.Client(api_key=api_key)
                log.info("Gemini Developer API inicializada (modelo=%s)", _vertex_model())
                return _vertex_client

            # 3) Sin credenciales
            _vertex_client = False
            _ultimo_error_vertex = "Sin credenciales de Google AI (SA ni API key)."
            log.info("Google AI no disponible: sin credenciales")
        except ImportError:
            _vertex_client = False
            _ultimo_error_vertex = "SDK google-genai no instalado — usando Groq."
            log.info("Google AI no disponible: SDK ausente")
        except Exception as exc:
            _vertex_client = False
            _ultimo_error_vertex = f"Google AI init falló: {str(exc)[:120]}"
            log.warning("Google AI init falló: %s", exc)
    return _vertex_client


def _vertex_disponible() -> bool:
    """True si el cliente Vertex AI Express está operativo."""
    return bool(_get_vertex_client())


def vertex_disponible() -> bool:
    """True si Vertex AI Express está configurado y operativo."""
    return _vertex_disponible()


def vertex_ultimo_error() -> str:
    return _ultimo_error_vertex


def _vertex_genconfig():
    """GenerateContentConfig con system prompt, temperature=0 y salida JSON."""
    from google.genai import types
    return types.GenerateContentConfig(
        system_instruction=_VERTEX_SYSTEM_PROMPT,
        temperature=0.0,                       # máxima precisión matemática
        response_mime_type="application/json",
    )


def _vertex_parse(response) -> dict | None:
    """Extrae y parsea el JSON de una respuesta de google-genai."""
    raw = (getattr(response, "text", None) or "").strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
    raw = re.sub(r'\s*```\s*$', '', raw)
    m = re.search(r'\{.*\}', raw, re.S)
    if m:
        raw = m.group(0)
    return json.loads(raw)


def _vertex_set_error(exc) -> None:
    """Registra el error de Google AI y deshabilita el cliente si es auth/config."""
    global _ultimo_error_vertex, _vertex_client
    msg = str(exc)
    _ultimo_error_vertex = f"Google AI no disponible: {msg[:120]}"
    log.warning("Google AI error (no afecta CB de Groq): %s", msg)
    # Deshabilita permanentemente si es error de autenticación o configuración
    # para no reintentar en cada PDF y no ensuciar los logs.
    if any(k in msg for k in ("401", "403", "404", "UNAUTHENTICATED",
                               "PERMISSION_DENIED", "NOT_FOUND",
                               "ACCESS_TOKEN_TYPE_UNSUPPORTED")):
        _vertex_client = False
        log.warning("Google AI deshabilitado permanentemente (error de auth/config).")


def _llamar_vertex(prompt: str) -> dict | None:
    """Llama a Google AI; devuelve None sin tocar el CB de Groq si falla."""
    global _ultimo_error_vertex
    client = _get_vertex_client()
    if not client:
        return None
    try:
        response = client.models.generate_content(
            model=_vertex_model(),
            contents=prompt,
            config=_vertex_genconfig(),
        )
        resultado = _vertex_parse(response)
        _ultimo_error_vertex = ""
        return resultado
    except json.JSONDecodeError as e:
        _ultimo_error_vertex = f"Google AI devolvió JSON inválido: {e}"
        log.warning("Google AI JSON error: %s", e)
        return None
    except Exception as exc:
        _vertex_set_error(exc)
        return None


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
                max_tokens=2048,
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
            log.warning("Groq JSON error (intento %d/%d): %s", attempt + 1, _MAX_RETRIES, e)
            _cb_on_failure()
            if attempt < _MAX_RETRIES - 1:
                wait = _BACKOFF_DELAYS[attempt]
                log.info("Reintentando en %ds...", wait)
                time.sleep(wait)
                continue
            return None

        except Exception as exc:
            msg = str(exc)
            if "rate_limit" in msg.lower() or "429" in msg:
                _ultimo_error = "Límite de tasa de Groq alcanzado."
                # Rate limits are transient — don't penalize the circuit breaker
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
        _ultimo_audit = audit_entry
        try:
            if "ai_audit_log" not in st.session_state:
                st.session_state.ai_audit_log = []
            st.session_state.ai_audit_log.append(audit_entry)
            if len(st.session_state.ai_audit_log) > 50:
                st.session_state.ai_audit_log = st.session_state.ai_audit_log[-50:]
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
            campos_corr["dui_prov"] = nit

    elif tipo_dte == "retenciones":
        nom = _validar_nombre(resultado.get("nom_prov"), campos_actuales.get("nom_prov", ""))
        if nom:
            campos_corr["nom_prov"] = nom
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
            audit_log = st.session_state.get("ai_audit_log", [])
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
    Verificador universal de DTEs.

    Motor PRIORITARIO: Vertex AI (gemini-2.0-flash, temperature=0.0, JSON mode)
    del proyecto "nomadic-sprite-440003-r7", para máxima precisión.
    Motor de RESPALDO: Groq (llama-3.3-70b-versatile) con circuit breaker, que
    se usa solo si Vertex AI no está disponible o falla (p. ej. cuota agotada).

    Mantiene la misma firma que la versión original para compatibilidad total.
    """
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

    prompt = build_prompt(texto_pdf, campos_actuales, nit_ctx, nom_ctx)

    # 1) Intento prioritario con Vertex AI.
    resultado = None
    motor_usado = ""
    if _vertex_disponible():
        resultado = _llamar_vertex(prompt)
        if resultado is not None:
            motor_usado = "vertex-ai/gemini-2.0-flash"
        else:
            log.info("Vertex AI no devolvió resultado, recayendo en Groq: %s",
                     _ultimo_error_vertex)

    # 2) Fallback a Groq (con circuit breaker) si Vertex no estuvo disponible
    #    o devolvió un resultado vacío/erróneo.
    if resultado is None:
        if not gemini_disponible():
            return {}, []
        resultado = _llamar_groq(prompt)
        if resultado is not None:
            motor_usado = f"groq/{_GROQ_MODEL}"

    if resultado is None:
        return {}, []

    # Forzar en la auditoría el motor REALMENTE usado (los prompts traen el
    # nombre del modelo hardcodeado, lo que ocultaría si corrió Vertex o Groq).
    if motor_usado:
        resultado.setdefault("auditoria_ia", {})
        resultado["auditoria_ia"]["modelo_utilizado"] = motor_usado

    correcciones = [str(c) for c in resultado.get("correcciones", []) if c]
    campos_corr  = _extraer_campos_corregidos(resultado, campos_actuales, tipo_dte, nit_ctx)
    return campos_corr, correcciones


# ═══════════════════════════════════════════════════════════════════════════
#  CAPA DE VISIÓN — Groq Llama-4 Scout lee el PDF como imagen
# ═══════════════════════════════════════════════════════════════════════════
# A diferencia de la extracción por texto (que hereda el desorden de columnas
# del PDF y los errores de regex), la visión "ve" el documento como un humano:
# distingue las dos columnas EMISOR | RECEPTOR, ubica los montos en su fila y
# lee el sello/UUID aunque estén en cualquier posición. Funciona también con
# PDFs escaneados (imagen pura, sin capa de texto).

_ultimo_error_vision: str = ""

# Caché del chequeo de dependencias (fitz/PIL) para no reimportar en cada PDF.
_vision_deps_ok: bool | None = None


def _vision_deps_disponibles() -> bool:
    global _vision_deps_ok
    if _vision_deps_ok is None:
        try:
            import fitz  # noqa: F401  (PyMuPDF)
            _vision_deps_ok = True
        except Exception:
            _vision_deps_ok = False
            log.info("Visión deshabilitada: PyMuPDF (fitz) no disponible")
    return _vision_deps_ok


def vision_disponible() -> bool:
    """
    True si se puede leer el PDF como imagen. Requiere PyMuPDF para renderizar
    y, al menos, UN motor de visión: Vertex AI (prioritario) o Groq (con el
    circuito cerrado) como respaldo.
    """
    if not _vision_deps_disponibles():
        return False
    if _vertex_disponible():
        return True
    return bool(_get_api_key()) and not _cb_is_open()


def _llamar_vertex_vision(prompt: str, img_b64: str) -> dict | None:
    """
    Vertex AI (gemini-2.0-flash, multimodal) actúa como AUDITOR: lee el DTE como
    imagen, lo comprende y devuelve los campos rectificados en JSON. Devuelve
    None si falla para que el llamador recaiga en la visión de Groq.
    """
    global _ultimo_error_vision
    client = _get_vertex_client()
    if not client:
        return None
    try:
        from google.genai import types

        imagen = types.Part.from_bytes(
            data=base64.b64decode(img_b64),
            mime_type="image/png",
        )
        response = client.models.generate_content(
            model=_vertex_model(),
            contents=[prompt, imagen],
            config=_vertex_genconfig(),
        )
        resultado = _vertex_parse(response)
        _ultimo_error_vision = ""
        return resultado
    except json.JSONDecodeError as e:
        _ultimo_error_vision = f"Google AI visión devolvió JSON inválido: {e}"
        log.warning("Google AI visión JSON error: %s", e)
        return None
    except Exception as exc:
        msg = str(exc)
        _ultimo_error_vision = f"Google AI visión no disponible: {msg[:120]}"
        log.warning("Google AI visión error (no afecta CB de Groq): %s", msg)
        # Deshabilita permanentemente si es error de auth/config
        if any(k in msg for k in ("401", "403", "404", "UNAUTHENTICATED",
                                   "PERMISSION_DENIED", "NOT_FOUND",
                                   "ACCESS_TOKEN_TYPE_UNSUPPORTED")):
            global _vertex_client
            _vertex_client = False
            log.warning("Google AI deshabilitado permanentemente (visión).")
        return None


def vision_ultimo_error() -> str:
    return _ultimo_error_vision


def _pdf_a_imagen_b64(pdf_bytes: bytes, max_lado: int = 1600) -> str | None:
    """
    Renderiza la PRIMERA página del PDF a PNG y la devuelve en base64.

    El DTE salvadoreño cabe en una sola página: sello, UUID, número de control,
    datos de emisor/receptor y resumen de montos están todos en la página 1.
    Se limita el lado mayor a ~1600px para mantener el base64 holgadamente bajo
    el límite de 4MB de Groq sin perder legibilidad de los dígitos.
    """
    try:
        import fitz
    except Exception:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count == 0:
            doc.close()
            return None
        page = doc[0]
        # Zoom 2x por defecto; reducir si la página renderizada excede max_lado.
        zoom  = 2.0
        rect  = page.rect
        lado  = max(rect.width, rect.height) * zoom
        if lado > max_lado:
            zoom = max_lado / max(rect.width, rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB)
        png = pix.tobytes("png")
        doc.close()
        return base64.b64encode(png).decode("ascii")
    except Exception as exc:
        log.warning("Visión: PDF→imagen falló: %s", exc)
        return None


# ── Especificación de campos por tipo de DTE (claves que esperan los extractores)
# Cada entrada: (descripción para el prompt, esquema JSON de salida).
_VISION_SPEC = {
    "compras": {
        "rol": ("El RECEPTOR es el cliente activo (comprador). Verifica los datos "
                "del EMISOR (proveedor), que está en la columna IZQUIERDA."),
        "campos": [
            "fecha           : fecha de EMISIÓN en formato DD/MM/YYYY",
            "nit_prov        : NIT del EMISOR (14 dígitos, sin guiones); NUNCA el del receptor",
            "nom_prov        : razón social del EMISOR (columna izquierda)",
            "num_control     : número de control completo (formato DTE-NN-XXXX-NÚMERO)",
            "sello_recepcion : sello de recepción (~40 caracteres alfanuméricos, sin guiones)",
            "gravadas        : total de ventas/compras gravadas (número)",
            "iva             : impuesto IVA 13% / crédito fiscal (número)",
            "exentas         : ventas exentas o no sujetas (número, 0 si no hay)",
            "total           : total a pagar / monto total de la operación (número)",
        ],
        "json": ('{"fecha": "...", "nit_prov": "...", "nom_prov": "...", '
                 '"num_control": "...", "sello_recepcion": "...", '
                 '"gravadas": 0, "iva": 0, "exentas": 0, "total": 0, '
                 '"confianza": 0}'),
    },
    "ventas": {
        "rol": ("El EMISOR es el cliente activo (vendedor). Verifica los datos del "
                "RECEPTOR (comprador), que está en la columna DERECHA."),
        "campos": [
            "fecha           : fecha de EMISIÓN en formato DD/MM/YYYY",
            "nit_cli         : NIT del RECEPTOR (14 dígitos, sin guiones); null si usa DUI",
            "dui_cli         : DUI del RECEPTOR (9 dígitos, sin guiones); null si usa NIT",
            "nom_cli         : nombre o razón social del RECEPTOR (columna derecha)",
            "num_control     : número de control completo (formato DTE-NN-XXXX-NÚMERO)",
            "sello_recepcion : sello de recepción (~40 caracteres alfanuméricos, sin guiones)",
            "gravadas        : total de ventas gravadas (número)",
            "iva             : débito fiscal / IVA 13% (número)",
            "exentas         : ventas exentas (número, 0 si no hay)",
            "no_sujetas      : ventas no sujetas (número, 0 si no hay)",
            "total           : total a pagar / monto total de la operación (número)",
        ],
        "json": ('{"fecha": "...", "nit_cli": "...", "dui_cli": "...", "nom_cli": "...", '
                 '"num_control": "...", "sello_recepcion": "...", '
                 '"gravadas": 0, "iva": 0, "exentas": 0, "no_sujetas": 0, "total": 0, '
                 '"confianza": 0}'),
    },
    "retenciones": {
        "rol": ("DTE-07. El AGENTE RETENEDOR es el cliente activo. Verifica los datos "
                "del SUJETO RETENIDO (proveedor)."),
        "campos": [
            "fecha           : fecha de EMISIÓN en formato DD/MM/YYYY",
            "nit_prov        : NIT del SUJETO RETENIDO (14 dígitos, sin guiones); NUNCA el del retenedor",
            "base            : monto sujeto a retención (número)",
            "ret             : IVA retenido 1% (número)",
            "num_control     : número de control completo (formato DTE-07-XXXX-NÚMERO)",
            "sello_recepcion : sello de recepción (~40 caracteres alfanuméricos, sin guiones)",
        ],
        "json": ('{"fecha": "...", "nit_prov": "...", "base": 0, "ret": 0, '
                 '"num_control": "...", "sello_recepcion": "...", "confianza": 0}'),
    },
    "sujetos_excluidos": {
        "rol": ("DTE-14. El COMPRADOR es el cliente activo. Verifica los datos del "
                "SUJETO EXCLUIDO (no inscrito en IVA)."),
        "campos": [
            "fecha           : fecha de EMISIÓN en formato DD/MM/YYYY",
            "nom_sujeto      : nombre del SUJETO EXCLUIDO",
            "id_sujeto       : NIT (14 dígitos) o DUI (9 dígitos) del sujeto, sin guiones",
            "base            : monto de la compra / base (número)",
            "ret             : retención de renta 10% (número, 0 si no hay)",
            "num_control     : número de control completo (formato DTE-14-XXXX-NÚMERO)",
            "sello_recepcion : sello de recepción (~40 caracteres alfanuméricos, sin guiones)",
        ],
        "json": ('{"fecha": "...", "nom_sujeto": "...", "id_sujeto": "...", '
                 '"base": 0, "ret": 0, "num_control": "...", '
                 '"sello_recepcion": "...", "confianza": 0}'),
    },
}


def _prompt_vision(tipo_dte: str, nit_ctx: str, nom_ctx: str) -> str:
    spec = _VISION_SPEC[tipo_dte]
    campos_txt = "\n".join(f"  • {c}" for c in spec["campos"])
    return f"""Eres un AUDITOR FISCAL SENIOR de El Salvador. Analiza la IMAGEN de este
Documento Tributario Electrónico (DTE) y extrae sus datos con máxima precisión.
{_CONTEXTO_FISCAL}
{spec['rol']}

CLIENTE ACTIVO (NO confundir con la contraparte):
  NIT   : {nit_ctx}
  Nombre: {nom_ctx}

INSTRUCCIONES:
  1. El DTE tiene DOS columnas: EMISOR (izquierda) y RECEPTOR (derecha).
     Identifica cada dato en su columna correcta; no los mezcles.
  2. Lee los montos del bloque "RESUMEN DEL DOCUMENTO" en su fila exacta.
  3. El sello de recepción y el código de generación pueden estar arriba;
     léelos carácter por carácter sin inventar dígitos.
  4. Si un dato no es legible o no aparece, usa null (no lo adivines).
  5. confianza = entero 0-100 según qué tan seguro estás de la lectura global.

CAMPOS A EXTRAER:
{campos_txt}

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional ni Markdown:
{spec['json']}"""


def _llamar_groq_vision(prompt: str, img_b64: str) -> dict | None:
    """Llama al modelo de visión de Groq con la imagen del DTE en base64."""
    global _ultimo_error_vision
    api_key = _get_api_key()
    if not api_key:
        _ultimo_error_vision = "GROQ_API_KEY no configurada."
        return None
    if _cb_is_open():
        _ultimo_error_vision = "Visión suspendida (circuit breaker abierto)."
        return None

    client  = Groq(api_key=api_key)
    mensajes = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        ],
    }]

    for attempt in range(_MAX_RETRIES):
        try:
            # Llama-4 en Groq soporta JSON mode; si el endpoint lo rechaza,
            # reintentamos sin response_format y parseamos manualmente.
            kwargs = dict(
                model=_GROQ_VISION_MODEL,
                messages=mensajes,
                temperature=0.1,
                max_tokens=1024,
            )
            try:
                response = client.chat.completions.create(
                    response_format={"type": "json_object"}, **kwargs
                )
            except Exception as exc_fmt:
                if "response_format" in str(exc_fmt).lower() or "json" in str(exc_fmt).lower():
                    response = client.chat.completions.create(**kwargs)
                else:
                    raise

            raw = (response.choices[0].message.content or "").strip()
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
            raw = re.sub(r'\s*```\s*$', '', raw)
            # Aislar el primer objeto JSON por si el modelo añade prosa.
            m = re.search(r'\{.*\}', raw, re.S)
            if m:
                raw = m.group(0)
            resultado = json.loads(raw)
            _cb_on_success()
            _ultimo_error_vision = ""
            return resultado

        except json.JSONDecodeError as e:
            _ultimo_error_vision = f"Visión devolvió JSON inválido: {e}"
            log.warning("Visión JSON error (intento %d/%d): %s", attempt + 1, _MAX_RETRIES, e)
            _cb_on_failure()
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BACKOFF_DELAYS[attempt])
                continue
            return None

        except Exception as exc:
            msg = str(exc)
            if "rate_limit" in msg.lower() or "429" in msg:
                _ultimo_error_vision = "Límite de tasa de Groq (visión)."
                # Rate limits are transient — don't penalize the circuit breaker
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_DELAYS[attempt])
                    continue
            elif "authentication" in msg.lower() or "401" in msg:
                _ultimo_error_vision = "API key de Groq inválida (401)."
                _cb_on_failure()
                return None
            elif "model" in msg.lower() and ("decommission" in msg.lower() or "not found" in msg.lower()):
                _ultimo_error_vision = f"Modelo de visión no disponible: {msg[:80]}"
                _cb_on_failure()
                return None
            else:
                _ultimo_error_vision = f"Error de visión: {msg[:120]}"
                _cb_on_failure()
                log.error("Visión error inesperado: %s", msg)
                return None
    return None


def _normalizar_campos_vision(resultado: dict, tipo_dte: str, nit_ctx: str) -> tuple[dict, int, list[str]]:
    """
    Convierte la respuesta cruda de visión al dict que consumen los extractores,
    saneando identificadores, nombres y montos. Devuelve (campos, confianza, alertas).
    """
    campos: dict   = {}
    alertas: list  = []
    excluir = {nit_ctx} if nit_ctx else set()

    def _id(v, *, longitudes):
        d = re.sub(r'[^0-9]', '', str(v or ""))
        return d if d and d not in excluir and len(d) in longitudes else ""

    def _nom(v):
        s = str(v or "").strip().upper()
        return s if (3 <= len(s) <= 120 and not es_nombre_sospechoso(s)) else ""

    def _monto(v):
        m = normalizar_monto_ia(v)
        return round(m, 2) if (m is not None and m > 0) else None

    # Fecha (común a todos)
    f = str(resultado.get("fecha") or "").strip()
    if f and _PAT_DDMMYYYY.match(f):
        campos["fecha"] = f

    # Número de control y sello (comunes)
    nc = str(resultado.get("num_control") or "").strip().upper()
    if re.match(r'DTE-\d{2}-[A-Z0-9]{1,20}-\d{6,18}', nc):
        campos["num_control"] = nc
    sello = re.sub(r'[^A-Z0-9]', '', str(resultado.get("sello_recepcion") or "").upper())
    if 30 <= len(sello) <= 45:
        campos["sello_recepcion"] = sello

    # Campos específicos por tipo
    if tipo_dte == "compras":
        if (n := _nom(resultado.get("nom_prov"))):       campos["nom_prov"] = n
        if (i := _id(resultado.get("nit_prov"), longitudes=(14,))): campos["nit_prov"] = i
        for k_out, k_in in [("gravadas","gravadas"),("iva","iva"),("exentas","exentas"),("total","total")]:
            if (mm := _monto(resultado.get(k_in))) is not None: campos[k_out] = mm

    elif tipo_dte == "ventas":
        if (n := _nom(resultado.get("nom_cli"))):        campos["nom_cli"] = n
        if (i := _id(resultado.get("nit_cli"), longitudes=(14,))): campos["nit_cli"] = i
        if (d := _id(resultado.get("dui_cli"), longitudes=(9,))):  campos["dui_cli"] = d
        for k in ("gravadas","iva","exentas","no_sujetas","total"):
            if (mm := _monto(resultado.get(k))) is not None: campos[k] = mm

    elif tipo_dte == "retenciones":
        if (i := _id(resultado.get("nit_prov"), longitudes=(14,))): campos["nit_prov"] = i
        for k in ("base","ret"):
            if (mm := _monto(resultado.get(k))) is not None: campos[k] = mm

    elif tipo_dte == "sujetos_excluidos":
        if (n := _nom(resultado.get("nom_sujeto"))):     campos["nom_sujeto"] = n
        if (i := _id(resultado.get("id_sujeto"), longitudes=(9, 14))): campos["id_sujeto"] = i
        for k in ("base","ret"):
            if (mm := _monto(resultado.get(k))) is not None: campos[k] = mm

    # Confianza → alerta de revisión manual
    try:
        conf = int(resultado.get("confianza", 0))
    except (ValueError, TypeError):
        conf = 0
    if conf and conf < _VISION_CONF_MIN:
        alertas.append(f"Confianza de visión baja ({conf}%) — revisar manualmente")

    return campos, conf, alertas


def extraer_dte_con_vision(
    pdf_bytes: bytes,
    tipo_dte: str = "compras",
    contexto_receptor: dict | None = None,
) -> tuple[dict, list[str], dict]:
    """
    Extrae los campos del DTE leyéndolo como IMAGEN con Groq Llama-4 Scout.

    Returns:
      (campos, alertas, audit)
        campos  : dict con las claves que esperan los extractores (ver _VISION_SPEC)
        alertas : list[str] de avisos (p.ej. confianza baja)
        audit   : dict de trazabilidad para la UI
    """
    global _ultimo_audit
    if tipo_dte not in _VISION_SPEC:
        return {}, [], {}
    if not vision_disponible():
        return {}, [], {}

    contexto_receptor = contexto_receptor or {}
    nit_ctx = re.sub(r'[^0-9]', '', str(contexto_receptor.get("nit", "")))
    nom_ctx = str(contexto_receptor.get("nombre", "")).strip().upper()

    img_b64 = _pdf_a_imagen_b64(pdf_bytes)
    if not img_b64:
        return {}, [], {}

    prompt = _prompt_vision(tipo_dte, nit_ctx, nom_ctx)

    # AUDITOR de visión: Vertex AI prioritario, Groq como respaldo.
    resultado   = None
    motor_vision = ""
    if _vertex_disponible():
        resultado = _llamar_vertex_vision(prompt, img_b64)
        if resultado is not None:
            motor_vision = "vertex-ai/gemini-2.0-flash"
        else:
            log.info("Vertex visión sin resultado, recayendo en Groq: %s",
                     _ultimo_error_vision)

    if resultado is None and bool(_get_api_key()) and not _cb_is_open():
        resultado = _llamar_groq_vision(prompt, img_b64)
        if resultado is not None:
            motor_vision = _GROQ_VISION_MODEL

    if resultado is None:
        return {}, [], {}

    campos, conf, alertas = _normalizar_campos_vision(resultado, tipo_dte, nit_ctx)

    audit = {
        "modelo_utilizado"    : motor_vision or _GROQ_VISION_MODEL,
        "confianza_extraccion": conf,
        "notas_de_razonamiento": f"Auditoría por visión ({len(campos)} campos legibles)",
        "tipo_dte"            : tipo_dte,
        "metodo"              : "vision",
    }
    with _audit_lock:
        _ultimo_audit = audit
        try:
            if "ai_audit_log" not in st.session_state:
                st.session_state.ai_audit_log = []
            st.session_state.ai_audit_log.append(audit)
            if len(st.session_state.ai_audit_log) > 50:
                st.session_state.ai_audit_log = st.session_state.ai_audit_log[-50:]
        except Exception:
            pass

    return campos, alertas, audit


# ─── Compatibilidad con versión anterior ─────────────────────────────────────

def necesita_verificacion(campos: dict, nit_receptor: str) -> tuple[bool, list[str]]:
    """
    Decide si vale la pena gastar una llamada de Groq (texto) para verificar.

    Retorna True solo cuando hay algo dudoso/faltante. Así, cuando la capa de
    VISIÓN ya completó fecha, NIT y nombre con datos limpios, esta verificación
    de texto se OMITE (evita una segunda llamada redundante por documento).
    Si la visión falló o dejó huecos, se levanta la verificación como respaldo.
    """
    razones = []
    _nit_p = re.sub(r'[^0-9]', '', str(campos.get("nit_prov") or ""))
    _nit_r = re.sub(r'[^0-9]', '', str(nit_receptor or ""))
    if _nit_p and _nit_r and _nit_p == _nit_r:
        razones.append("NIT del emisor coincide con el del receptor")
    if not campos.get("nom_prov", "").strip():
        razones.append("Nombre del emisor vacío")
    elif es_nombre_sospechoso(campos.get("nom_prov", "")):
        razones.append(f"Nombre extraído es metadata: {campos['nom_prov'][:40]}")
    if not campos.get("fecha", "").strip():
        razones.append("Fecha de emisión no encontrada")
    if not campos.get("nit_prov", "").strip():
        razones.append("NIT del emisor no encontrado")
    # Solo llamar a Groq-texto si quedó algún campo dudoso o vacío.
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
    """Limpia el audit log de la sesión actual."""
    try:
        import streamlit as _st
        _st.session_state.pop("ai_audit_log", None)
        _st.session_state.pop("_cache_extracciones", None)
        _st.session_state.pop("_pdfs_procesados", None)
    except Exception:
        pass
