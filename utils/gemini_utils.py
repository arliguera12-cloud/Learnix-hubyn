"""
Learnix Hub — Gemini Vision v1.0 (multimodal PDF → DTE extraction).

Sends raw PDF bytes as base64 inlineData directly to gemini-2.5-flash Vision.
Primary extraction path — eliminates the need to extract text with pdfplumber
before calling Gemini. Falls back gracefully if the API is unavailable.

Roles per DTE type:
  ventas          → EMISOR = cliente activo; extraer datos del RECEPTOR (comprador)
  compras         → RECEPTOR = cliente activo; extraer datos del EMISOR (proveedor)
  retenciones     → AGENTE RETENEDOR = cliente activo; extraer datos del SUJETO RETENIDO
  sujetos_excluidos → COMPRADOR = cliente activo; extraer datos del SUJETO EXCLUIDO
"""
import base64
import json
import logging
import os
import re

import requests
import streamlit as st

log = logging.getLogger(__name__)

_GEMINI_MODEL = "gemini-2.5-flash"
_GEMINI_URL   = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{_GEMINI_MODEL}:generateContent"
)
_TIMEOUT = 60  # Vision requests take longer than text-only calls

_ultimo_error: str = ""


# ─── API key ─────────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    try:
        return st.secrets["gemini"]["api_key"]
    except Exception:
        pass
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        return env_key
    return st.session_state.get("gemini_api_key", "")


def vision_disponible() -> bool:
    return bool(_get_api_key())


def vision_ultimo_error() -> str:
    return _ultimo_error


# ─── Sub-schemas compartidos ──────────────────────────────────────────────────

def _sub_razonamiento() -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "layout_detectado": {"type": "STRING"},
            "bloque_emisor"   : {"type": "STRING"},
            "bloque_receptor" : {"type": "STRING"},
            "autovalidacion"  : {"type": "STRING"},
        },
        "required": ["autovalidacion"],
    }


def _sub_auditoria() -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "modelo_utilizado"    : {"type": "STRING"},
            "confianza_extraccion": {"type": "INTEGER"},
            "notas"               : {"type": "STRING"},
        },
        "required": ["modelo_utilizado", "confianza_extraccion", "notas"],
    }


# ─── Schemas por tipo de DTE ──────────────────────────────────────────────────

_SCHEMAS: dict[str, dict] = {
    "ventas": {
        "type": "OBJECT",
        "properties": {
            "tipo_documento"   : {"type": "STRING",  "nullable": True},
            "fecha"            : {"type": "STRING",  "nullable": True},
            "num_control"      : {"type": "STRING",  "nullable": True},
            "codigo_generacion": {"type": "STRING",  "nullable": True},
            "sello_recepcion"  : {"type": "STRING",  "nullable": True},
            "nom_receptor"     : {"type": "STRING",  "nullable": True},
            "nit_receptor"     : {"type": "STRING",  "nullable": True},
            "dui_receptor"     : {"type": "STRING",  "nullable": True},
            "gravadas"         : {"type": "NUMBER",  "nullable": True},
            "exentas"          : {"type": "NUMBER",  "nullable": True},
            "no_sujetas"       : {"type": "NUMBER",  "nullable": True},
            "iva"              : {"type": "NUMBER",  "nullable": True},
            "total"            : {"type": "NUMBER",  "nullable": True},
            "iva_correcto"     : {"type": "BOOLEAN", "nullable": True},
            "alertas_fiscales" : {"type": "ARRAY",   "items": {"type": "STRING"}},
            "razonamiento"     : _sub_razonamiento(),
            "auditoria_ia"     : _sub_auditoria(),
        },
        "required": ["alertas_fiscales", "razonamiento", "auditoria_ia"],
    },
    "compras": {
        "type": "OBJECT",
        "properties": {
            "tipo_documento"   : {"type": "STRING",  "nullable": True},
            "fecha"            : {"type": "STRING",  "nullable": True},
            "num_control"      : {"type": "STRING",  "nullable": True},
            "codigo_generacion": {"type": "STRING",  "nullable": True},
            "sello_recepcion"  : {"type": "STRING",  "nullable": True},
            "nom_emisor"       : {"type": "STRING",  "nullable": True},
            "nit_emisor"       : {"type": "STRING",  "nullable": True},
            "gravadas"         : {"type": "NUMBER",  "nullable": True},
            "exentas"          : {"type": "NUMBER",  "nullable": True},
            "no_sujetas"       : {"type": "NUMBER",  "nullable": True},
            "iva"              : {"type": "NUMBER",  "nullable": True},
            "total"            : {"type": "NUMBER",  "nullable": True},
            "iva_correcto"     : {"type": "BOOLEAN", "nullable": True},
            "alertas_fiscales" : {"type": "ARRAY",   "items": {"type": "STRING"}},
            "razonamiento"     : _sub_razonamiento(),
            "auditoria_ia"     : _sub_auditoria(),
        },
        "required": ["alertas_fiscales", "razonamiento", "auditoria_ia"],
    },
    "retenciones": {
        "type": "OBJECT",
        "properties": {
            "tipo_documento"    : {"type": "STRING",  "nullable": True},
            "fecha"             : {"type": "STRING",  "nullable": True},
            "num_control"       : {"type": "STRING",  "nullable": True},
            "codigo_generacion" : {"type": "STRING",  "nullable": True},
            "sello_recepcion"   : {"type": "STRING",  "nullable": True},
            "nom_retenido"      : {"type": "STRING",  "nullable": True},
            "nit_retenido"      : {"type": "STRING",  "nullable": True},
            "monto_sujeto"      : {"type": "NUMBER",  "nullable": True},
            "iva_retenido"      : {"type": "NUMBER",  "nullable": True},
            "retencion_correcta": {"type": "BOOLEAN", "nullable": True},
            "alertas_fiscales"  : {"type": "ARRAY",   "items": {"type": "STRING"}},
            "razonamiento"      : _sub_razonamiento(),
            "auditoria_ia"      : _sub_auditoria(),
        },
        "required": ["alertas_fiscales", "razonamiento", "auditoria_ia"],
    },
    "sujetos_excluidos": {
        "type": "OBJECT",
        "properties": {
            "tipo_documento"    : {"type": "STRING",  "nullable": True},
            "fecha"             : {"type": "STRING",  "nullable": True},
            "num_control"       : {"type": "STRING",  "nullable": True},
            "codigo_generacion" : {"type": "STRING",  "nullable": True},
            "sello_recepcion"   : {"type": "STRING",  "nullable": True},
            "nom_sujeto"        : {"type": "STRING",  "nullable": True},
            "nit_sujeto"        : {"type": "STRING",  "nullable": True},
            "dui_sujeto"        : {"type": "STRING",  "nullable": True},
            "base_compras"      : {"type": "NUMBER",  "nullable": True},
            "retencion_renta"   : {"type": "NUMBER",  "nullable": True},
            "retencion_correcta": {"type": "BOOLEAN", "nullable": True},
            "alertas_fiscales"  : {"type": "ARRAY",   "items": {"type": "STRING"}},
            "razonamiento"      : _sub_razonamiento(),
            "auditoria_ia"      : _sub_auditoria(),
        },
        "required": ["alertas_fiscales", "razonamiento", "auditoria_ia"],
    },
}


# ─── Prompt construction ──────────────────────────────────────────────────────

_CONTEXTO_FISCAL = """
MARCO LEGAL — SISTEMA DTE EL SALVADOR (DGII / Ministerio de Hacienda)
  DTE-01  Factura              → Venta a consumidor final (receptor usa DUI, no NIT)
  DTE-03  CCF                  → Comprobante de Crédito Fiscal entre contribuyentes IVA
  DTE-05  Nota de Crédito      → Reducción o anulación de DTE-03
  DTE-06  Nota de Débito       → Cargo adicional sobre DTE-03
  DTE-07  Comprobante Retención → Agente retiene 1% de IVA sobre monto sujeto
  DTE-14  Comprobante Liquid.  → Sujeto excluido, retención de renta 10%

IDENTIFICADORES FISCALES:
  NIT : EXACTAMENTE 14 dígitos (ej: 0614-270815-107-7 o 06142708151077)
  DUI : EXACTAMENTE  9 dígitos  (ej: 04581234-7 o 045812347)
  NRC : 1-7 dígitos (solo contribuyentes inscritos en IVA)
  UUID: formato XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX (32 hex con guiones)

REGLAS MATEMÁTICAS CRÍTICAS:
  IVA (DTE-03/05/06) = Ventas Gravadas × 13%   (tolerancia ±$0.02)
  Retención (DTE-07) = Monto Sujeto × 1%        (tolerancia ±$0.02)
  Retención (DTE-14) = Base Compras × 10%        (tolerancia ±$0.02)
"""

_INSTRUCCIONES_ESPACIALES = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANÁLISIS VISUAL — 4 PASOS OBLIGATORIOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 — IDENTIFICAR LAYOUT VISUAL
  Los DTEs de El Salvador pueden tener estos formatos:
  • TICKET      : datos en columna única, "etiqueta: valor" en la misma línea
  • 2-COLUMNAS  : EMISOR (izquierda) y RECEPTOR (derecha) en el encabezado
  • ENCABEZADO  : bloque EMISOR arriba, bloque RECEPTOR separado por línea
  Registra el formato en razonamiento.layout_detectado.

PASO 2 — LOCALIZAR BLOQUES EMISOR / RECEPTOR
  Busca marcadores: "DATOS DEL EMISOR", "EMISOR:", "DATOS DEL RECEPTOR",
  "RECEPTOR:", "ADQUIRIENTE:", "CLIENTE:", "PROVEEDOR:", "SUJETO RETENIDO:".
  En formato 2-columnas: EMISOR está arriba-izquierda, RECEPTOR arriba-derecha.
  Registra en razonamiento.bloque_emisor y razonamiento.bloque_receptor.

PASO 3 — EXTRAER VALORES (NUNCA ETIQUETAS)
  ⚠️ REGLA ABSOLUTA: el VALOR es lo que aparece DESPUÉS del ":" en cada campo.
  ✅ "Nombre o Razón Social: GRANJA SAN DIEGO S.A." → extrae "GRANJA SAN DIEGO S.A."
  ❌ Nunca extraer "Nombre o Razón Social" como valor — eso es la ETIQUETA
  ❌ Nunca extraer texto que contenga: "NIT:", "NRC:", "COD.", "DTE-", "SELLO",
     "GENERACIÓN", "CONTROL", "COMPROBANTE", "DOCUMENTO TRIBUTARIO"

  Para NÚMEROS: solo dígitos y punto decimal. Elimina "$", "US", comas de miles.
  Para FECHAS: formato DD/MM/YYYY (ej: "15/03/2025"). Busca "Fecha de Emisión:".
  Para SELLO/UUID: cadenas alfanuméricas largas (sello: 30-40 chars sin guiones;
    UUID: 36 chars con guiones en formato XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX).
  Para NUM_CONTROL: formato DTE-XX-XXXX-XXXXXXXXX (con guiones).

PASO 4 — AUTO-VALIDAR Y GENERAR ALERTAS
  Verifica cada campo extraído:
  • NIT ≠ 14 dígitos → alerta "NIT inválido: {valor extraído}"
  • DUI ≠  9 dígitos → alerta "DUI inválido: {valor extraído}"
  • Nombre contiene texto de etiqueta → alerta "Nombre parece etiqueta: {valor}"
  • IVA del doc ≠ gravadas × 13% (±$0.02) → alerta "IVA no coincide: doc={X} calc={Y}"
  • Retención DTE-07 ≠ base × 1% (±$0.02) → alerta "Retención 1% incorrecta"
  • Retención DTE-14 ≠ base × 10% (±$0.02) → alerta "Retención renta 10% incorrecta"
  Registra en razonamiento.autovalidacion y en alertas_fiscales.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ESCALA DE CONFIANZA (auditoria_ia.confianza_extraccion):
  95-100 : Extracción directa de etiqueta explícita, sin ambigüedad
  80- 94 : Alta certeza, limpieza menor aplicada
  60- 79 : Certeza moderada, posible revisión manual
   0- 59 : Alta incertidumbre — requiere revisión manual
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

_ROLES: dict[str, str] = {
    "ventas": (
        "El EMISOR es el cliente activo del sistema (quien vende y emite el DTE).\n"
        "El RECEPTOR es el COMPRADOR — extrae sus datos: nombre, NIT o DUI.\n"
        "• Para DTE-01 (consumidor final): receptor tiene DUI (9 dígitos), NO NIT.\n"
        "• Para DTE-03/05/06: receptor tiene NIT (14 dígitos).\n"
        "• Si el receptor es 'CONSUMIDOR FINAL' o similar → nom_receptor='CONSUMIDOR FINAL', "
        "nit_receptor=null, dui_receptor=null."
    ),
    "compras": (
        "El RECEPTOR es el cliente activo del sistema (quien compra y recibe el crédito).\n"
        "El EMISOR es el PROVEEDOR/VENDEDOR — extrae su nombre y NIT.\n"
        "• El NIT del emisor NUNCA puede ser igual al NIT del cliente activo.\n"
        "• Si nom_emisor coincide con el nombre del receptor → está mal extraído."
    ),
    "retenciones": (
        "El AGENTE RETENEDOR (quien emite el DTE-07) es el cliente activo.\n"
        "El SUJETO RETENIDO es el proveedor sobre quien se aplica la retención — "
        "extrae su nombre y NIT.\n"
        "• monto_sujeto: base monetaria sobre la que se retiene.\n"
        "• iva_retenido: monto de la retención (debe ser ≈1% del monto_sujeto)."
    ),
    "sujetos_excluidos": (
        "El COMPRADOR (quien emite el DTE-14) es el cliente activo.\n"
        "El SUJETO EXCLUIDO presta el servicio y NO está inscrito en IVA — "
        "extrae su nombre e identificación.\n"
        "• Personas naturales → DUI (9 dígitos). Personas jurídicas → NIT (14 dígitos).\n"
        "• base_compras: sumatoria de ventas / sub-total del documento.\n"
        "• retencion_renta: retención Pago a Cuenta (≈10% de base_compras, Art. 72 C.T.)."
    ),
}

_CAMPOS: dict[str, str] = {
    "ventas": (
        "• tipo_documento    : '01'|'03'|'05'|'06'\n"
        "• fecha             : DD/MM/YYYY (campo 'Fecha de Emisión')\n"
        "• num_control       : Número de control DTE (DTE-XX-XXXX-XXXXXXXXX)\n"
        "• codigo_generacion : UUID del documento (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)\n"
        "• sello_recepcion   : Sello del MH (cadena alfanumérica 30-40 chars, sin guiones)\n"
        "• nom_receptor      : Nombre/Razón social del COMPRADOR\n"
        "• nit_receptor      : NIT del receptor (14 dígitos, si aplica)\n"
        "• dui_receptor      : DUI del receptor (9 dígitos, consumidores finales)\n"
        "• gravadas, exentas, no_sujetas, iva, total : montos numéricos en dólares\n"
        "• iva_correcto       : true si iva ≈ gravadas × 13% (±$0.02)"
    ),
    "compras": (
        "• tipo_documento    : '03'|'05'|'06'\n"
        "• fecha             : DD/MM/YYYY\n"
        "• num_control       : Número de control DTE\n"
        "• codigo_generacion : UUID del documento\n"
        "• sello_recepcion   : Sello del MH\n"
        "• nom_emisor        : Nombre/Razón social del PROVEEDOR (EMISOR del DTE)\n"
        "• nit_emisor        : NIT del PROVEEDOR (14 dígitos)\n"
        "• gravadas, exentas, no_sujetas, iva, total : montos en dólares\n"
        "• iva_correcto       : true si iva ≈ gravadas × 13% (±$0.02)"
    ),
    "retenciones": (
        "• tipo_documento    : '07'\n"
        "• fecha             : DD/MM/YYYY\n"
        "• num_control       : Número de control\n"
        "• codigo_generacion : UUID del documento\n"
        "• sello_recepcion   : Sello del MH\n"
        "• nom_retenido      : Nombre del SUJETO RETENIDO\n"
        "• nit_retenido      : NIT del sujeto retenido (14 dígitos)\n"
        "• monto_sujeto      : Base monetaria sujeta a retención ($)\n"
        "• iva_retenido      : Monto retenido ($ — debe ser ≈1% de monto_sujeto)\n"
        "• retencion_correcta: true si iva_retenido ≈ monto_sujeto × 1% (±$0.02)"
    ),
    "sujetos_excluidos": (
        "• tipo_documento    : '14'\n"
        "• fecha             : DD/MM/YYYY\n"
        "• num_control       : Número de control\n"
        "• codigo_generacion : UUID del documento\n"
        "• sello_recepcion   : Sello del MH\n"
        "• nom_sujeto        : Nombre del SUJETO EXCLUIDO\n"
        "• nit_sujeto        : NIT del sujeto (14 dígitos, si es persona jurídica)\n"
        "• dui_sujeto        : DUI del sujeto (9 dígitos, si es persona natural)\n"
        "• base_compras      : Sumatoria de compras / sub-total ($)\n"
        "• retencion_renta   : Retención renta Pago a Cuenta ($ — debe ser ≈10% de base)\n"
        "• retencion_correcta: true si retencion_renta ≈ base_compras × 10% (±$0.02)"
    ),
}


def _build_prompt(tipo_dte: str, nit_ctx: str, nom_ctx: str) -> str:
    return (
        f"Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador. "
        f"Analiza el documento PDF adjunto usando tus CAPACIDADES DE VISIÓN.\n\n"
        f"{_CONTEXTO_FISCAL}\n"
        f"CLIENTE ACTIVO DEL SISTEMA:\n"
        f"  NIT   : {nit_ctx}\n"
        f"  Nombre: {nom_ctx}\n\n"
        f"ROL EN ESTE DOCUMENTO:\n{_ROLES.get(tipo_dte, '')}\n\n"
        f"{_INSTRUCCIONES_ESPACIALES}\n"
        f"CAMPOS A EXTRAER:\n{_CAMPOS.get(tipo_dte, '')}\n\n"
        f"INSTRUCCIONES DE SALIDA:\n"
        f"  • Devuelve JSON según el responseSchema. Usa null para campos no encontrados.\n"
        f"  • alertas_fiscales: lista todos los problemas de validación; [] si no hay ninguno.\n"
        f"  • auditoria_ia.modelo_utilizado = 'gemini-2.5-flash-vision'\n"
        f"  • auditoria_ia.confianza_extraccion: entero 0-100 según escala definida.\n"
        f"  • auditoria_ia.notas: 1-2 oraciones sobre cómo resolviste ambigüedades."
    )


# ─── HTTP call con inlineData ─────────────────────────────────────────────────

def _llamar_vision(pdf_bytes: bytes, prompt: str, schema: dict) -> dict | None:
    global _ultimo_error
    api_key = _get_api_key()
    if not api_key:
        _ultimo_error = "API key de Gemini no configurada en secrets.toml."
        return None

    if len(pdf_bytes) > 20 * 1024 * 1024:
        _ultimo_error = "PDF demasiado grande para envío inline (>20 MB)."
        return None

    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    gen_cfg: dict = {
        "temperature"     : 0.0,
        "maxOutputTokens" : 2048,
        "responseMimeType": "application/json",
        "thinkingConfig"  : {"thinkingBudget": 0},
        "responseSchema"  : schema,
    }

    payload = {
        "contents": [{
            "parts": [
                {
                    "inlineData": {
                        "mimeType": "application/pdf",
                        "data"    : pdf_b64,
                    }
                },
                {"text": prompt},
            ]
        }],
        "generationConfig": gen_cfg,
    }

    try:
        resp = requests.post(
            _GEMINI_URL,
            params  = {"key": api_key},
            json    = payload,
            timeout = _TIMEOUT,
        )

        if resp.status_code == 400:
            _ultimo_error = f"Gemini Vision rechazó la solicitud (400): {resp.text[:300]}"
            log.error("Vision 400: %s", resp.text[:600])
            return None
        if resp.status_code == 403:
            _ultimo_error = "API key inválida o sin permiso (403)."
            return None
        if resp.status_code == 404:
            _ultimo_error = f"Modelo '{_GEMINI_MODEL}' no disponible para esta API key (404)."
            return None
        if resp.status_code == 429:
            _ultimo_error = "Cuota de Gemini Vision agotada (429). Espera un momento."
            return None
        if resp.status_code in (500, 502, 503, 504):
            _ultimo_error = f"Gemini Vision no disponible temporalmente ({resp.status_code})."
            log.warning("Vision %s transient error", resp.status_code)
            return None

        resp.raise_for_status()

        candidates = resp.json().get("candidates", [])
        if not candidates:
            _ultimo_error = "Gemini Vision devolvió respuesta sin candidatos."
            return None

        raw = ""
        for part in candidates[0].get("content", {}).get("parts", []):
            txt = part.get("text", "").strip()
            if txt:
                raw = txt
                break

        if not raw:
            _ultimo_error = "Gemini Vision devolvió respuesta vacía."
            return None

        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
        raw = re.sub(r'\s*```\s*$', '', raw)

        resultado = json.loads(raw)
        _ultimo_error = ""
        return resultado

    except requests.exceptions.Timeout:
        _ultimo_error = f"Timeout ({_TIMEOUT}s) al llamar a Gemini Vision."
        log.warning("Vision timeout")
        return None
    except requests.exceptions.ConnectionError:
        _ultimo_error = "Sin conexión a Internet para llamar a Gemini Vision."
        log.warning("Vision connection error")
        return None
    except json.JSONDecodeError as exc:
        _ultimo_error = f"JSON inválido de Gemini Vision: {exc}"
        log.warning("Vision JSON error: %s | raw=%s", exc, (raw or "")[:200])
        return None
    except Exception as exc:
        _ultimo_error = f"Error inesperado en Gemini Vision: {exc}"
        log.error("Vision unexpected error", exc_info=True)
        return None


# ─── Mapeo de campos (vision output → nombres esperados por las páginas) ──────

def _limpio_str(raw) -> str | None:
    if raw is None or str(raw).strip().lower() in ("null", "none", ""):
        return None
    return str(raw).strip() or None


def _limpio_nit(raw) -> str:
    return re.sub(r'[^0-9]', '', str(raw or ""))


def _limpio_num(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _mapear_campos(resultado: dict, tipo_dte: str, nit_ctx: str) -> dict:
    """Maps vision field names to page-expected field names and filters invalid values."""
    out: dict = {}

    # Campos comunes de todos los tipos
    for campo in ("tipo_documento", "fecha", "num_control", "codigo_generacion", "sello_recepcion"):
        v = _limpio_str(resultado.get(campo))
        if v:
            out[campo] = v

    if tipo_dte == "ventas":
        nom = _limpio_str(resultado.get("nom_receptor"))
        if nom and len(nom) >= 3:
            out["nom_cli"] = nom.upper()

        nit = _limpio_nit(resultado.get("nit_receptor"))
        if len(nit) == 14 and nit != nit_ctx:
            out["nit_cli"] = nit

        dui = _limpio_nit(resultado.get("dui_receptor"))
        if len(dui) == 9:
            out["dui_cli"] = dui

        for campo in ("gravadas", "exentas", "no_sujetas", "iva", "total"):
            v = _limpio_num(resultado.get(campo))
            if v is not None:
                out[campo] = v

        if resultado.get("iva_correcto") is not None:
            out["iva_correcto"] = bool(resultado["iva_correcto"])

    elif tipo_dte == "compras":
        nom = _limpio_str(resultado.get("nom_emisor"))
        if nom and len(nom) >= 3:
            out["nom_prov"] = nom.upper()

        nit = _limpio_nit(resultado.get("nit_emisor"))
        if len(nit) == 14 and nit != nit_ctx:
            out["nit_prov"] = nit

        for campo in ("gravadas", "exentas", "no_sujetas", "iva", "total"):
            v = _limpio_num(resultado.get(campo))
            if v is not None:
                out[campo] = v

        if resultado.get("iva_correcto") is not None:
            out["iva_correcto"] = bool(resultado["iva_correcto"])

    elif tipo_dte == "retenciones":
        nom = _limpio_str(resultado.get("nom_retenido"))
        if nom and len(nom) >= 3:
            out["nom_prov"] = nom.upper()

        nit = _limpio_nit(resultado.get("nit_retenido"))
        if len(nit) == 14 and nit != nit_ctx:
            out["nit_prov"] = nit

        base = _limpio_num(resultado.get("monto_sujeto"))
        if base is not None:
            out["base"] = base

        ret = _limpio_num(resultado.get("iva_retenido"))
        if ret is not None:
            out["ret"] = ret

        if resultado.get("retencion_correcta") is not None:
            out["retencion_correcta"] = bool(resultado["retencion_correcta"])

    elif tipo_dte == "sujetos_excluidos":
        nom = _limpio_str(resultado.get("nom_sujeto"))
        if nom and len(nom) >= 3:
            out["nom_sujeto"] = nom.upper()

        nit = _limpio_nit(resultado.get("nit_sujeto"))
        if len(nit) == 14:
            out["id_sujeto"] = nit
        else:
            dui = _limpio_nit(resultado.get("dui_sujeto"))
            if len(dui) == 9:
                out["id_sujeto"] = dui

        base = _limpio_num(resultado.get("base_compras"))
        if base is not None:
            out["base"] = base

        ret = _limpio_num(resultado.get("retencion_renta"))
        if ret is not None:
            out["ret"] = ret

        if resultado.get("retencion_correcta") is not None:
            out["retencion_correcta"] = bool(resultado["retencion_correcta"])

    return out


# ─── Función pública principal ────────────────────────────────────────────────

def extraer_dte_con_vision(
    pdf_bytes: bytes,
    tipo_dte: str,
    contexto: dict,
) -> tuple[dict, list[str], dict]:
    """
    Extrae todos los campos de un DTE enviando el PDF directamente a Gemini Vision.

    Args:
        pdf_bytes: bytes crudos del PDF.
        tipo_dte : "ventas" | "compras" | "retenciones" | "sujetos_excluidos"
        contexto : {"nit": "...", "nombre": "..."} — cliente activo del sistema.

    Returns:
        (campos, alertas, audit)
          campos  : dict con campos extraídos, nombres compatibles con cada página.
          alertas : list[str] con alertas de validación fiscal.
          audit   : {"confianza": int, "notas": str, "layout": str, "tipo_dte": str}
                    Diccionario vacío si Vision no pudo conectarse.
    """
    global _ultimo_error

    if not vision_disponible():
        _ultimo_error = "API key de Gemini no configurada."
        return {}, [], {}

    schema = _SCHEMAS.get(tipo_dte)
    if not schema:
        log.warning("extraer_dte_con_vision: tipo_dte desconocido '%s'", tipo_dte)
        return {}, [], {}

    nit_ctx = _limpio_nit(contexto.get("nit", ""))
    nom_ctx = str(contexto.get("nombre", "")).strip().upper()

    prompt    = _build_prompt(tipo_dte, nit_ctx, nom_ctx)
    resultado = _llamar_vision(pdf_bytes, prompt, schema)

    if resultado is None:
        return {}, [], {}

    alertas   = [str(a) for a in resultado.get("alertas_fiscales", []) if a]
    audit_raw = resultado.get("auditoria_ia", {})
    razon     = resultado.get("razonamiento", {})

    audit: dict = {
        "confianza": int(audit_raw.get("confianza_extraccion", 0)),
        "notas"    : str(audit_raw.get("notas", "")),
        "layout"   : str(razon.get("layout_detectado", "")),
        "tipo_dte" : tipo_dte,
        "modelo"   : str(audit_raw.get("modelo_utilizado", "gemini-2.5-flash-vision")),
    }

    campos = _mapear_campos(resultado, tipo_dte, nit_ctx)
    return campos, alertas, audit
