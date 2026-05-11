"""
Learnix Hub — Gemini utility v3.0 (REST, sin SDK).
Arquitectura: Chain-of-Thought + Auto-Validación + Trazabilidad de IA.

Modelo: gemini-2.5-flash  (gemini-1.5-flash fue retirado — HTTP 404)
Técnicas:
  • CoT  — 4 pasos explícitos de razonamiento dentro del JSON de salida.
  • Auto-Revisión — validación contra anti-patrones fiscales antes de responder.
  • responseSchema estricto — garantiza JSON válido y completo en cada llamada.
  • auditoria_ia — trazabilidad modelo/confianza/notas por documento.
"""
import os
import re
import json
import logging
import threading
import time
import requests
import streamlit as st

log = logging.getLogger(__name__)

# ─── Modelo ───────────────────────────────────────────────────────────────────
_GEMINI_MODEL = "gemini-2.5-flash"
_GEMINI_URL   = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{_GEMINI_MODEL}:generateContent"
)
_TIMEOUT        = 25
_MAX_RETRIES    = 3
_BACKOFF_DELAYS = [2, 4, 8]   # seconds per retry attempt

# ─── Estado del módulo ────────────────────────────────────────────────────────
_ultimo_error: str = ""
_ultimo_audit: dict = {}          # audit del último documento procesado
_audit_lock   = threading.Lock()  # protege escrituras concurrentes al audit log


# ─── API key & disponibilidad ─────────────────────────────────────────────────

def _get_api_key() -> str:
    try:
        return st.secrets["gemini"]["api_key"]
    except Exception:
        pass
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        return env_key
    return st.session_state.get("gemini_api_key", "")


def gemini_disponible() -> bool:
    return bool(_get_api_key())


def gemini_ultimo_error() -> str:
    """Último mensaje de error Gemini (vacío = sin error)."""
    return _ultimo_error


def gemini_ultimo_audit() -> dict:
    """Devuelve el audit del último documento procesado con Gemini."""
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

# Anti-patrones de nombre: palabras que indican que se capturó una etiqueta
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
    # Cadenas hex largas sin espacios (UUIDs, códigos) de más de 20 caracteres
    if re.search(r'[A-F0-9]{20,}', n) and ' ' not in n:
        return True
    # Más del 40% dígitos → probablemente un código, no un nombre
    if len(n) > 5 and sum(c.isdigit() for c in n) / len(n) > 0.40:
        return True
    return False


# ─── JSON Schemas estrictos (Gemini OpenAPI format) ───────────────────────────

def _sub_razonamiento() -> dict:
    """Sub-schema del bloque de cadena de pensamiento (CoT)."""
    return {
        "type": "OBJECT",
        "properties": {
            "ubicacion_seccion" : {"type": "STRING"},
            "etiqueta_vs_valor" : {"type": "STRING"},
            "limpieza_aplicada" : {"type": "STRING"},
            "autovalidacion"    : {"type": "STRING"},
        },
        "required": ["ubicacion_seccion", "etiqueta_vs_valor", "autovalidacion"],
    }


def _sub_auditoria() -> dict:
    """Sub-schema del bloque de trazabilidad de IA."""
    return {
        "type": "OBJECT",
        "properties": {
            "modelo_utilizado"     : {"type": "STRING"},
            "confianza_extraccion" : {"type": "INTEGER"},
            "notas_de_razonamiento": {"type": "STRING"},
        },
        "required": ["modelo_utilizado", "confianza_extraccion", "notas_de_razonamiento"],
    }


_SCHEMAS: dict[str, dict] = {
    "compras": {
        "type": "OBJECT",
        "properties": {
            "razonamiento": _sub_razonamiento(),
            "fecha"       : {"type": "STRING", "nullable": True},
            "nit_prov"    : {"type": "STRING", "nullable": True},
            "nom_prov"    : {"type": "STRING", "nullable": True},
            "correcciones": {"type": "ARRAY", "items": {"type": "STRING"}},
            "auditoria_ia": _sub_auditoria(),
        },
        "required": ["razonamiento", "correcciones", "auditoria_ia"],
    },
    "ventas": {
        "type": "OBJECT",
        "properties": {
            "razonamiento": _sub_razonamiento(),
            "fecha"       : {"type": "STRING", "nullable": True},
            "nit_cli"     : {"type": "STRING", "nullable": True},
            "dui_cli"     : {"type": "STRING", "nullable": True},
            "nom_cli"     : {"type": "STRING", "nullable": True},
            "correcciones": {"type": "ARRAY", "items": {"type": "STRING"}},
            "auditoria_ia": _sub_auditoria(),
        },
        "required": ["razonamiento", "correcciones", "auditoria_ia"],
    },
    "retenciones": {
        "type": "OBJECT",
        "properties": {
            "razonamiento": _sub_razonamiento(),
            "fecha"       : {"type": "STRING", "nullable": True},
            "nit_prov"    : {"type": "STRING", "nullable": True},
            "correcciones": {"type": "ARRAY", "items": {"type": "STRING"}},
            "auditoria_ia": _sub_auditoria(),
        },
        "required": ["razonamiento", "correcciones", "auditoria_ia"],
    },
    "sujetos_excluidos": {
        "type": "OBJECT",
        "properties": {
            "razonamiento": _sub_razonamiento(),
            "fecha"       : {"type": "STRING", "nullable": True},
            "nit_sujeto"  : {"type": "STRING", "nullable": True},
            "dui_sujeto"  : {"type": "STRING", "nullable": True},
            "nom_sujeto"  : {"type": "STRING", "nullable": True},
            "correcciones": {"type": "ARRAY", "items": {"type": "STRING"}},
            "auditoria_ia": _sub_auditoria(),
        },
        "required": ["razonamiento", "correcciones", "auditoria_ia"],
    },
}


# ─── Llamada HTTP central ─────────────────────────────────────────────────────

def _llamar_gemini(
    prompt: str,
    schema: dict | None = None,
    max_tokens: int = 1024,
) -> dict | None:
    """
    Envía un prompt a Gemini con responseMimeType=application/json.
    Si se provee `schema`, lo adjunta como responseSchema para forzar
    estructura estricta.  Retorna el JSON parseado o None en caso de error.
    """
    global _ultimo_error
    api_key = _get_api_key()
    if not api_key:
        _ultimo_error = "API key de Gemini no configurada en .streamlit/secrets.toml."
        log.warning("Gemini: API key ausente")
        return None

    gen_cfg: dict = {
        "temperature"     : 0.0,
        "maxOutputTokens" : max_tokens,
        "responseMimeType": "application/json",
        # gemini-2.5-flash habilita thinking por defecto (hasta 8192 tokens).
        # Para extracción estructurada de DTEs lo desactivamos; el CoT está
        # integrado en el prompt y en el campo razonamiento del JSON de salida.
        "thinkingConfig"  : {"thinkingBudget": 0},
    }
    if schema:
        gen_cfg["responseSchema"] = schema

    payload = {
        "contents"       : [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }

    for attempt in range(_MAX_RETRIES):
        raw = ""
        try:
            resp = requests.post(
                _GEMINI_URL,
                params={"key": api_key},
                json=payload,
                timeout=_TIMEOUT,
            )

            if resp.status_code == 400:
                _ultimo_error = f"Gemini rechazó la solicitud (400): {resp.text[:200]}"
                log.error("Gemini 400: %s", resp.text[:500])
                return None
            if resp.status_code == 403:
                _ultimo_error = "API key inválida o sin permiso (403). Verifica en Google AI Studio."
                log.error("Gemini 403")
                return None
            if resp.status_code == 404:
                _ultimo_error = (
                    f"Modelo '{_GEMINI_MODEL}' no disponible para esta API key (404)."
                )
                log.error("Gemini 404 — modelo no disponible")
                return None

            if resp.status_code == 429 or resp.status_code in (500, 502, 503, 504):
                _ultimo_error = (
                    f"Cuota de Gemini agotada (429). Espera un momento."
                    if resp.status_code == 429
                    else f"Gemini no disponible temporalmente ({resp.status_code})."
                )
                if attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_DELAYS[attempt]
                    log.warning(
                        "Gemini %s (attempt %d/%d), waiting %ds...",
                        resp.status_code, attempt + 1, _MAX_RETRIES, wait,
                    )
                    time.sleep(wait)
                    continue
                _ultimo_error += f" (tras {_MAX_RETRIES} intentos)"
                log.warning("Gemini %s — all retries exhausted", resp.status_code)
                return None

            resp.raise_for_status()

            # Buscar la primera parte de texto no vacía (ignora thinking parts)
            candidates = resp.json().get("candidates", [])
            if not candidates:
                _ultimo_error = "Gemini devolvió respuesta sin candidatos."
                return None

            for part in candidates[0].get("content", {}).get("parts", []):
                txt = part.get("text", "").strip()
                if txt:
                    raw = txt
                    break

            if not raw:
                _ultimo_error = "Gemini devolvió respuesta vacía."
                return None

            # Limpiar markdown fences residuales
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
            raw = re.sub(r'\s*```\s*$', '', raw)

            resultado = json.loads(raw)
            _ultimo_error = ""
            return resultado

        except requests.exceptions.Timeout:
            _ultimo_error = f"Timeout ({_TIMEOUT}s). Verifica tu conexión a Internet."
            log.warning("Gemini timeout")
            return None
        except requests.exceptions.ConnectionError:
            _ultimo_error = "Sin conexión a Internet para llamar a Gemini."
            log.warning("Gemini connection error")
            return None
        except json.JSONDecodeError as e:
            _ultimo_error = f"Gemini devolvió JSON inválido: {e}"
            log.warning("Gemini JSON error: %s | raw=%s", e, (raw or "")[:200])
            return None
        except Exception as e:
            _ultimo_error = f"Error inesperado: {e}"
            log.error("Gemini unexpected error", exc_info=True)
            return None

    return None


# ─── Normalización de montos de la IA ────────────────────────────────────────

def normalizar_monto_ia(raw) -> float | None:
    """
    Normalizes a monetary string from Gemini JSON output to a clean float.

    Handles ambiguous separators from providers with European/mixed formats:
      "1.500,00"  → 1500.00   (dot=thousands, comma=decimal)
      "1,500.00"  → 1500.00   (comma=thousands, dot=decimal)
      "1500,00"   → 1500.00   (comma as decimal separator)
      "60.177"    → 60.177    (3-decimal warning: possible thousands ambiguity)

    Arithmetic validation: caller should verify gravadas + iva ≈ total (±$0.01).
    If mismatch is detected, re-run extraction treating separators differently.

    Returns None for null/empty/non-numeric input.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", ""):
        return None

    if "," in s and "." in s:
        # Both separators present: determine which is the decimal mark
        # European "1.500,00" → dot before comma → dot=thousands
        if s.index(".") < s.index(","):
            s = s.replace(".", "").replace(",", ".")
        else:
            # American "1,500.00" → comma before dot → comma=thousands
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        # "1,500" (thousands) vs "1500,00" (decimal)
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace(",", "")   # comma is thousands separator
        else:
            s = s.replace(",", ".")  # comma is decimal separator

    try:
        val = float(s)
        # Warn on 3+ decimal places: possible thousands-separator ambiguity
        if "." in s:
            dec_part = s.split(".", 1)[1]
            if len(dec_part) >= 3:
                log.warning(
                    "Monto IA con %d decimales: '%s' → %.4f — "
                    "verifique si el punto es separador de miles",
                    len(dec_part), raw, val,
                )
        return val
    except (ValueError, TypeError):
        return None


# ─── Contexto fiscal y reglas CoT compartidas ────────────────────────────────

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
REGLAS MATEMÁTICAS DGII (Art. 54 IVA / Art. 72 C.T.):
  IVA (DTE-03/05/06)  = Ventas Gravadas × 13%             (tolerancia ±$0.02)
  Retención (DTE-07)  = Monto Sujeto × 1%                 (tolerancia ±$0.02)
  Retención (DTE-14)  = Base Compras × 10%                 (tolerancia ±$0.02)
  Líquido (DTE-14)    = Base Compras − Retención Renta     (= Base × 0.90)
IDENTIFICACIÓN DUAL (Compras / Sujetos Excluidos):
  El emisor/sujeto puede ser persona natural con DUI (9 dígitos) en lugar de NIT (14 dígitos).
  Si no hay NIT de 14 dígitos, busca DUI de 9 dígitos. Nunca dejes la identificación vacía.
"""

_INSTRUCCIONES_COT = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROCESO DE EXTRACCIÓN — 4 PASOS OBLIGATORIOS (Chain of Thought)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 ▶ LOCALIZA LA SECCIÓN OBJETIVO
  Busca marcadores de inicio: "DATOS DEL EMISOR", "EMISOR:", "PROVEEDOR:",
  "DATOS DEL RECEPTOR", "RECEPTOR:", "ADQUIRIENTE:".
  Registra en razonamiento.ubicacion_seccion dónde encontraste cada bloque.

PASO 2 ▶ DISTINGUE ETIQUETAS DE VALORES REALES
  ETIQUETA = texto fijo que describe el campo, termina en ":"
    Ejemplos: "Nombre o Razón Social:", "NIT:", "NRC:", "Fecha de Emisión:"
  VALOR = el texto que viene INMEDIATAMENTE DESPUÉS del ":" de la etiqueta.

  ✅ CORRECTO: "Nombre o Razón Social: GRANJA SAN DIEGO S.A."  →  "GRANJA SAN DIEGO S.A."
  ❌ INCORRECTO: Extraer "Nombre o Razón Social" como valor  →  eso es la ETIQUETA
  ❌ INCORRECTO: Extraer "RAZÓN SOCIAL / FACTURA CAMBIARIA…" → mezcla de etiqueta+ruido

  Registra en razonamiento.etiqueta_vs_valor qué identificaste en el texto.

PASO 3 ▶ LIMPIA EL VALOR BRUTO
  Elimina del valor extraído:
    ✗ Cualquier prefijo de etiqueta residual: "Nombre:", "Razón Social:", "EMISOR:"
    ✗ Texto de campos adjacentes: "NIT:", "NRC:", "Dirección:", "Teléfono:"
    ✗ UUIDs y códigos alfanuméricos largos sin espacios (más de 15 chars)
    ✗ Horas: "08:30:00", "14:25:12"
    ✗ Marcas de versión: "v1", "V14", "2025"
    ✗ Guiones y dos puntos al inicio/final del valor
  Registra en razonamiento.limpieza_aplicada qué eliminaste y el valor resultante.

PASO 4 ▶ AUTO-VALIDACIÓN (si falla, vuelve a buscar)
  El valor es INVÁLIDO si cumple CUALQUIERA de estas condiciones:
    ✗ Nombre contiene: RAZÓN SOCIAL, NOMBRE O RAZ, NIT:, NRC:, COD., DTE-,
                       UUID, GENERACIÓN, CONTROL, FACTURA CAMBIARIA, SELLO,
                       COMPROBANTE, TRIBUTARIO, REPRESENTACIÓN, VERSIÓN
    ✗ Nombre contiene cadena hex de más de 20 chars sin espacios
    ✗ Nombre tiene más del 40% de dígitos en su longitud
    ✗ NIT no tiene EXACTAMENTE 14 dígitos (después de eliminar guiones/espacios)
    ✗ DUI no tiene EXACTAMENTE 9 dígitos
    ✗ Fecha no cumple DD/MM/YYYY con día 1-31, mes 1-12, año 2020-2030
  Validación matemática DGII (cuando aplique):
    ✗ IVA ≠ Gravadas × 0.13 (±$0.02)           → documenta discrepancia
    ✗ Retención DTE-07 ≠ Base × 0.01 (±$0.02)  → documenta discrepancia
    ✗ Retención DTE-14 ≠ Base × 0.10 (±$0.02)  → documenta discrepancia
  Si el valor es inválido, documenta "INVÁLIDO: [razón]" y busca nuevamente.
  Registra el resultado en razonamiento.autovalidacion.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ESCALA DE CONFIANZA para auditoria_ia.confianza_extraccion:
  95-100 : Valor extraído directamente de etiqueta explícita, sin ambigüedad
  80- 94 : Valor extraído con alta certeza, limpieza menor aplicada
  60- 79 : Valor inferido con certeza moderada, posible revisión manual
   0- 59 : Alta incertidumbre — se recomienda revisión manual del documento
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SIEMPRE completa auditoria_ia con:
  modelo_utilizado      = "gemini-2.5-flash"
  confianza_extraccion  = número entero 0-100
  notas_de_razonamiento = resumen en 1-2 oraciones de cómo resolviste ambigüedades
"""


# ─── Constructores de prompt con CoT por tipo de DTE ─────────────────────────

def _prompt_compras(
    texto_pdf: str,
    campos: dict,
    nit_receptor: str,
    nom_receptor: str,
) -> str:
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL EN ESTE DOCUMENTO:
  El RECEPTOR es el cliente activo del sistema (quien compra y recibe el crédito fiscal).
  El EMISOR es el proveedor/vendedor — sus datos son los que debes verificar/corregir.

RECEPTOR (comprador — cliente activo del sistema):
  NIT   : {nit_receptor}
  Nombre: {nom_receptor}

CAMPOS EXTRAÍDOS POR REGEX — PUEDEN CONTENER ERRORES:
  fecha_emision : "{campos.get('fecha', '')}"
  nit_emisor    : "{campos.get('nit_prov', '')}"
  nombre_emisor : "{campos.get('nom_prov', '')}"

  ⚠️  Si nombre_emisor contiene texto como "RAZÓN SOCIAL", "NIT:", "COD.", cadenas largas
      sin espacios, o coincide con el nombre del receptor → ESTÁ MAL EXTRAÍDO.

TEXTO COMPLETO DEL PDF:
{texto_pdf[:3500]}

{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR Y CORREGIR:
  • fecha    : Fecha de EMISIÓN del DTE en formato DD/MM/YYYY
  • nit_prov : NIT del EMISOR (14 dígitos); NO puede ser {nit_receptor}
              Si el emisor es persona natural sin NIT, busca su DUI de 9 dígitos y
              colócalo en nit_prov — nunca dejes la identificación del emisor vacía.
  • nom_prov : Razón social del EMISOR; NO puede ser "{nom_receptor}" ni metadata

Devuelve el JSON siguiendo exactamente el responseSchema definido.
Usa null (sin comillas) para campos que ya están correctos y no necesitan cambio.
La lista correcciones describe brevemente solo los campos que modificaste."""


def _prompt_ventas(
    texto_pdf: str,
    campos: dict,
    nit_emisor: str,
    nom_emisor: str,
) -> str:
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL EN ESTE DOCUMENTO:
  El EMISOR es el cliente activo del sistema (quien vende y emite el DTE).
  El RECEPTOR es el comprador/adquiriente — sus datos son los que debes verificar.

EMISOR (vendedor — cliente activo del sistema):
  NIT   : {nit_emisor}
  Nombre: {nom_emisor}

CAMPOS EXTRAÍDOS POR REGEX — PUEDEN CONTENER ERRORES:
  fecha_emision  : "{campos.get('fecha', '')}"
  nit_receptor   : "{campos.get('nit_cli', '')}"
  dui_receptor   : "{campos.get('dui_cli', '')}"
  nombre_receptor: "{campos.get('nom_cli', '')}"

  ⚠️  Si nombre_receptor dice "SIN NOMBRE", está vacío, o contiene etiquetas/metadata
      → ESTÁ MAL EXTRAÍDO. Busca el nombre real del COMPRADOR en la sección RECEPTOR.
  ⚠️  Para DTE-01 (consumidor final): el receptor tiene DUI (9 dígitos), no NIT.
      En ese caso nit_cli debe quedar null y dui_cli debe tener los 9 dígitos.

TEXTO COMPLETO DEL PDF:
{texto_pdf[:3500]}

{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR Y CORREGIR:
  • fecha   : Fecha de EMISIÓN en formato DD/MM/YYYY
  • nom_cli : Nombre completo del RECEPTOR/COMPRADOR; NO puede ser "{nom_emisor}"
  • nit_cli : NIT del receptor (14 dígitos); vacío si es consumidor final con DUI
  • dui_cli : DUI del receptor (9 dígitos); solo si es persona natural/consumidor final

Devuelve el JSON siguiendo el responseSchema. Usa null para campos ya correctos."""


def _prompt_retenciones(
    texto_pdf: str,
    campos: dict,
    nit_cliente: str,
    nom_cliente: str,
) -> str:
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL EN ESTE DOCUMENTO (DTE-07 — Comprobante de Retención):
  El AGENTE RETENEDOR es el cliente activo que emite la retención del 1% de IVA.
  El SUJETO RETENIDO es el proveedor sobre quien se aplica la retención.

AGENTE RETENEDOR (cliente activo — emite el DTE-07):
  NIT   : {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX — PUEDEN CONTENER ERRORES:
  fecha_emision : "{campos.get('fecha', '')}"
  nit_proveedor : "{campos.get('nit_prov', '')}"

TEXTO COMPLETO DEL PDF:
{texto_pdf[:3500]}

{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR Y CORREGIR:
  • fecha   : Fecha de EMISIÓN en formato DD/MM/YYYY
  • nit_prov: NIT del SUJETO RETENIDO (14 dígitos); NO puede ser {nit_cliente}

Devuelve el JSON siguiendo el responseSchema. Usa null para campos ya correctos."""


def _prompt_sujetos_excluidos(
    texto_pdf: str,
    campos: dict,
    nit_cliente: str,
    nom_cliente: str,
) -> str:
    return f"""Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL EN ESTE DOCUMENTO (DTE-14 — Comprobante de Liquidación / Sujeto Excluido):
  El COMPRADOR es el cliente activo del sistema que paga al sujeto excluido.
  El SUJETO EXCLUIDO es quien presta el servicio — NO está inscrito en el IVA.

COMPRADOR (cliente activo):
  NIT   : {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX — PUEDEN CONTENER ERRORES:
  fecha_emision : "{campos.get('fecha', '')}"
  nit_sujeto    : "{campos.get('nit_sujeto', '')}"
  dui_sujeto    : "{campos.get('dui_sujeto', '')}"
  nombre_sujeto : "{campos.get('nom_sujeto', '')}"

  ⚠️  Los sujetos excluidos suelen ser personas naturales (DUI de 9 dígitos).
      Si el sujeto es persona jurídica, tendrá NIT de 14 dígitos.
  ⚠️  NUNCA dejes la identificación del sujeto vacía: si hay un número de 9 dígitos
      úsalo como dui_sujeto; si hay 14 dígitos úsalo como nit_sujeto.
  ⚠️  Fórmulas DGII para DTE-14 (Art. 72 C.T.):
        Retención ISR = Base Compras × 10%
        Líquido       = Base Compras − Retención ISR  (= Base × 0.90)

TEXTO COMPLETO DEL PDF:
{texto_pdf[:3500]}

{_INSTRUCCIONES_COT}

CAMPOS A VERIFICAR Y CORREGIR:
  • fecha      : Fecha de EMISIÓN en formato DD/MM/YYYY
  • nom_sujeto : Nombre del sujeto excluido; NO puede ser "{nom_cliente}"
  • nit_sujeto : NIT del sujeto (14 dígitos), si es persona jurídica; null si no aplica
  • dui_sujeto : DUI del sujeto (9 dígitos), si es persona natural; null si no aplica
                 Al menos uno de nit_sujeto o dui_sujeto debe estar presente.

Devuelve el JSON siguiendo el responseSchema. Usa null para campos ya correctos."""


# ─── Validadores de campos post-respuesta ────────────────────────────────────

def _validar_fecha(nueva: str | None, actual: str) -> str | None:
    if not nueva or str(nueva).lower() == "null":
        return None
    nueva = str(nueva).strip()
    if _PAT_DDMMYYYY.match(nueva) and nueva != actual:
        return nueva
    return None


def _validar_nombre(nuevo: str | None, actual: str, excluir_prefijo: str = "") -> str | None:
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


def _validar_nit(nuevo: str | None, actual: str, excluir: set | None = None) -> str | None:
    if not nuevo or str(nuevo).lower() == "null":
        return None
    nuevo  = re.sub(r'[^0-9]', '', str(nuevo))
    excluir = excluir or set()
    if nuevo and nuevo != actual and nuevo not in excluir and len(nuevo) in (9, 14):
        return nuevo
    return None


def _extraer_campos_corregidos(
    resultado: dict,
    campos_actuales: dict,
    tipo_dte: str,
    nit_contexto: str,
) -> dict:
    """
    Valida la respuesta de Gemini campo a campo y retorna solo
    los que realmente cambiaron respecto a campos_actuales.
    También guarda audit y razonamiento en el estado del módulo.
    """
    global _ultimo_audit
    campos_corr: dict = {}
    excluir = {nit_contexto} if nit_contexto else set()

    # Guardar audit en estado del módulo y en session_state (thread-safe)
    auditoria = resultado.get("auditoria_ia", {})
    razonamiento = resultado.get("razonamiento", {})
    audit_entry = {
        **auditoria,
        "razonamiento": razonamiento,
        "tipo_dte"    : tipo_dte,
    }
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

    # Validar fecha
    fecha_ok = _validar_fecha(resultado.get("fecha"), campos_actuales.get("fecha", ""))
    if fecha_ok:
        campos_corr["fecha"] = fecha_ok

    if tipo_dte == "ventas":
        nom = _validar_nombre(
            resultado.get("nom_cli"),
            campos_actuales.get("nom_cli", ""),
            excluir_prefijo=nit_contexto,
        )
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
            # DUI fallback: provider is a natural person without NIT
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


# ─── UI Helper: visualización del audit en Streamlit ─────────────────────────

def mostrar_audit_gemini(archivo: str = "", container=None) -> None:
    """
    Renderiza el bloque de trazabilidad IA en la UI de Streamlit.
    Llama a esta función DESPUÉS de procesar un documento con Gemini
    para mostrar el razonamiento y el nivel de confianza.

    Ejemplo de uso en cualquier extractor:
        from utils.gemini_utils import mostrar_audit_gemini
        mostrar_audit_gemini(archivo=f.name)
    """
    audit = gemini_ultimo_audit()
    if not audit:
        return

    target = container or st
    titulo = f"🔬 Trazabilidad IA — Auditoría de Extracción{f': {archivo}' if archivo else ''}"

    with target.expander(titulo, expanded=False):
        modelo     = audit.get("modelo_utilizado", "—")
        confianza  = int(audit.get("confianza_extraccion", 0))
        notas      = audit.get("notas_de_razonamiento", "—")
        tipo_dte   = audit.get("tipo_dte", "—")
        razon      = audit.get("razonamiento", {})

        col1, col2, col3 = target.columns([3, 2, 2])
        col1.metric("Modelo IA", modelo)
        col2.metric("Tipo DTE", tipo_dte.upper())
        col3.metric(
            "Confianza",
            f"{confianza}%",
            delta=None,
            help="Estimación del modelo sobre la certeza de la extracción",
        )

        # Barra de confianza con color según nivel
        if confianza >= 85:
            bar_color = "#6AB040"
            nivel_txt = "Alta confianza"
        elif confianza >= 65:
            bar_color = "#F0A500"
            nivel_txt = "Confianza moderada — revisar si hay dudas"
        else:
            bar_color = "#E53935"
            nivel_txt = "Baja confianza — se recomienda revisión manual"

        target.markdown(
            f"""<div style="background:#1A2C18;border-radius:6px;padding:4px 10px;margin:4px 0">
            <div style="background:{bar_color};width:{confianza}%;height:8px;border-radius:4px"></div>
            <small style="color:{bar_color}">{nivel_txt}</small></div>""",
            unsafe_allow_html=True,
        )

        target.info(f"📝 **Notas de razonamiento:** {notas}")

        # Cadena de razonamiento (CoT steps)
        if razon:
            with target.expander("📊 Cadena de Razonamiento (CoT) — Detalle paso a paso"):
                if razon.get("ubicacion_seccion"):
                    target.markdown(
                        f"**🔍 Paso 1 — Localización de sección:**\n\n"
                        f"> {razon['ubicacion_seccion']}"
                    )
                if razon.get("etiqueta_vs_valor"):
                    target.markdown(
                        f"**🏷️ Paso 2 — Etiqueta vs Valor real:**\n\n"
                        f"> {razon['etiqueta_vs_valor']}"
                    )
                if razon.get("limpieza_aplicada"):
                    target.markdown(
                        f"**🧹 Paso 3 — Limpieza aplicada:**\n\n"
                        f"> {razon['limpieza_aplicada']}"
                    )
                if razon.get("autovalidacion"):
                    autoval = razon["autovalidacion"]
                    fn = target.success if "VÁLIDO" in autoval.upper() else target.warning
                    fn(f"**✅ Paso 4 — Auto-Validación:** {autoval}")

        # Histórico de audits de la sesión (si existen)
        audit_log = []
        try:
            audit_log = st.session_state.get("gemini_audit_log", [])
        except Exception:
            pass
        if len(audit_log) > 1:
            target.caption(
                f"📋 Esta sesión tiene **{len(audit_log)} documentos** procesados con Gemini. "
                "Los logs se conservan en `st.session_state.gemini_audit_log`."
            )


# ─── Función pública universal ────────────────────────────────────────────────

def procesar_dte_con_gemini(
    texto_pdf: str,
    tipo_dte: str,
    campos_actuales: dict,
    contexto_receptor: dict,
) -> tuple[dict, list[str]]:
    """
    Verificador universal de DTEs con Gemini (auditor fiscal DGII).

    Utiliza Chain-of-Thought (4 pasos explícitos dentro del JSON),
    Auto-Validación contra anti-patrones y responseSchema estricto.

    Args:
        texto_pdf        : Texto extraído del PDF.
        tipo_dte         : "ventas" | "compras" | "retenciones" | "sujetos_excluidos"
        campos_actuales  : Campos extraídos por regex (pueden tener errores).
        contexto_receptor: {"nit": "...", "nombre": "..."} — cliente activo del sistema.

    Returns:
        (campos_corregidos, lista_de_correcciones)
        campos_corregidos contiene SOLO las claves cuyos valores cambiaron.
        El audit completo queda en gemini_ultimo_audit() y session_state.gemini_audit_log.
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

    schema    = _SCHEMAS.get(tipo_dte)
    prompt    = build_prompt(texto_pdf, campos_actuales, nit_ctx, nom_ctx)
    resultado = _llamar_gemini(prompt, schema=schema)

    if resultado is None:
        return {}, []

    correcciones = [str(c) for c in resultado.get("correcciones", []) if c]
    campos_corr  = _extraer_campos_corregidos(resultado, campos_actuales, tipo_dte, nit_ctx)
    return campos_corr, correcciones


# ─── Compatibilidad con versión anterior (2_Extractor_DTE_Compras.py) ─────────

def necesita_verificacion(campos: dict, nit_receptor: str) -> tuple[bool, list[str]]:
    """
    Decide si es necesario llamar a Gemini según los campos extraídos.
    Retorna (necesita, [razones]).
    """
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
