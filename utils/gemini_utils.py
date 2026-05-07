"""
Learnix Hub — Gemini utility (REST, sin SDK).
Verificador universal de DTEs alineado con el Manual de IVA DGII El Salvador.

PUNTO DE FALLA ORIGINAL:
    El modelo 'gemini-1.5-flash' fue retirado del proyecto de esta API key (HTTP 404).
    Se migró a 'gemini-2.5-flash', que es el modelo activo disponible.
"""
import os
import re
import json
import logging
import requests
import streamlit as st

log = logging.getLogger(__name__)

# ─── Modelo y URL ─────────────────────────────────────────────────────────────
# gemini-1.5-flash fue retirado → 404 NOT_FOUND en esta API key.
# gemini-2.5-flash es el modelo flash más reciente y disponible.
_GEMINI_MODEL = "gemini-2.5-flash"
_GEMINI_URL   = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{_GEMINI_MODEL}:generateContent"
)
_TIMEOUT      = 25  # segundos — 2.5-flash puede tardar un poco más en razonar

# Estado del último error (expuesto a la UI)
_ultimo_error: str = ""


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
    """Devuelve el último mensaje de error de Gemini (vacío = sin error)."""
    return _ultimo_error


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


def es_nombre_sospechoso(nombre: str) -> bool:
    if not nombre:
        return False
    n = nombre.strip().upper()
    if _SOSPECHOSO.match(n):
        return True
    if _PAT_FECHA_STR.search(n) or _PAT_HORA.search(n) or _PAT_META.search(n):
        return True
    return False


# ─── Llamada HTTP central ─────────────────────────────────────────────────────

def _llamar_gemini(prompt: str, max_tokens: int = 512) -> dict | None:
    """
    Envía un prompt a Gemini y retorna el JSON parseado.
    Ante cualquier fallo retorna None y registra el error en _ultimo_error.
    """
    global _ultimo_error
    api_key = _get_api_key()
    if not api_key:
        _ultimo_error = "API key de Gemini no configurada en .streamlit/secrets.toml."
        log.warning("Gemini: API key ausente")
        return None

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature"     : 0.0,
            "maxOutputTokens" : max_tokens,
            "responseMimeType": "application/json",  # fuerza salida JSON puro
            # gemini-2.5-flash habilita thinking por defecto (hasta 8192 tokens).
            # Para extracción estructurada de DTEs no se necesita razonamiento
            # extendido; desactivarlo evita que consuma el presupuesto de salida.
            "thinkingConfig"  : {"thinkingBudget": 0},
        },
    }

    try:
        resp = requests.post(
            _GEMINI_URL,
            params={"key": api_key},
            json=payload,
            timeout=_TIMEOUT,
        )

        # Errores HTTP específicos con mensajes claros
        if resp.status_code == 400:
            _ultimo_error = f"Gemini rechazó la solicitud (400): {resp.text[:200]}"
            log.error("Gemini 400: %s", resp.text[:500])
            return None
        if resp.status_code == 403:
            _ultimo_error = "API key inválida o sin permiso (403). Verifica tu key en Google AI Studio."
            log.error("Gemini 403")
            return None
        if resp.status_code == 404:
            _ultimo_error = (
                f"Modelo '{_GEMINI_MODEL}' no encontrado (404). "
                "La key puede no tener acceso a este modelo."
            )
            log.error("Gemini 404 — modelo no disponible para esta API key")
            return None
        if resp.status_code == 429:
            _ultimo_error = "Cuota de Gemini agotada (429). Espera un momento e intenta de nuevo."
            log.warning("Gemini 429 quota")
            return None

        resp.raise_for_status()

        # Parsear respuesta — gemini-2.5-flash puede devolver partes múltiples
        # (p. ej. una parte de "pensamiento" invisible y otra de texto)
        # Buscamos la primera parte que sea texto no vacío.
        candidates = resp.json().get("candidates", [])
        if not candidates:
            _ultimo_error = "Gemini devolvió una respuesta sin candidatos."
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        raw = ""
        for part in parts:
            txt = part.get("text", "").strip()
            if txt:
                raw = txt
                break

        if not raw:
            _ultimo_error = "Gemini devolvió una respuesta vacía."
            return None

        # Limpiar markdown fences si Gemini los incluyó a pesar del responseMimeType
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
        raw = re.sub(r'\s*```\s*$', '', raw)

        resultado = json.loads(raw)
        _ultimo_error = ""
        return resultado

    except requests.exceptions.Timeout:
        _ultimo_error = f"Timeout ({_TIMEOUT}s) al llamar a Gemini. Verifica tu conexión."
        log.warning("Gemini timeout")
        return None
    except requests.exceptions.ConnectionError:
        _ultimo_error = "Sin conexión a Internet para llamar a Gemini."
        log.warning("Gemini connection error")
        return None
    except json.JSONDecodeError as e:
        _ultimo_error = f"Gemini devolvió JSON inválido: {e}"
        log.warning("Gemini JSON parse error: %s | raw=%s", e, raw[:200] if raw else "")
        return None
    except Exception as e:
        _ultimo_error = f"Error inesperado en Gemini: {e}"
        log.error("Gemini unexpected error", exc_info=True)
        return None


# ─── Contexto fiscal común (inyectado en todos los prompts) ──────────────────

_CONTEXTO_FISCAL = """
MARCO LEGAL — MANUAL DE IVA DGII EL SALVADOR:
• DTE-01  Factura                        → Venta a consumidor final. Sin crédito fiscal.
• DTE-03  Comprobante de Crédito Fiscal  → Entre contribuyentes IVA. Débito/Crédito 13%.
• DTE-05  Nota de Crédito               → Reducción/anulación sobre DTE-03 previo.
• DTE-06  Nota de Débito                → Cargo adicional sobre DTE-03 previo.
• DTE-07  Comprobante de Retención      → Agente retenedor descuenta 1% IVA al sujeto.
• DTE-11  Factura de Exportación        → Operación de exportación, tasa 0%.
• DTE-14  Comprobante de Liquidación    → Pago a sujeto excluido (no inscrito en IVA).

IDENTIFICADORES SALVADOREÑOS:
• NIT (Número de Identificación Tributaria): EXACTAMENTE 14 dígitos (formato: XXXX-XXXXXX-XXX-X).
• NRC (Número de Registro de Contribuyente): 1-7 dígitos, solo contribuyentes IVA.
• DUI (Documento Único de Identidad): EXACTAMENTE 9 dígitos (formato: XXXXXXXX-X).
• UUID / Código de Generación: formato XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX (hexadecimal).
• Número de Control: formato DTE-XX-XXXXXXXXXX-XXXXXXXXXXXXXX.

REGLA CRITICA: El NIT del EMISOR nunca puede ser igual al NIT del RECEPTOR.
REGLA CRITICA: Los montos gravados se calculan SIN IVA; el IVA es siempre el 13%.
"""


# ─── Constructores de prompt por tipo de DTE ──────────────────────────────────

def _prompt_ventas(
    texto_pdf: str,
    campos: dict,
    nit_emisor: str,
    nom_emisor: str,
) -> str:
    return f"""Eres un auditor fiscal experto en el sistema DTE de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL: El EMISOR de este DTE es el cliente activo del sistema (quien vende).
     El RECEPTOR es el comprador/adquiriente cuyo nombre y NIT debemos verificar.

EMISOR (vendedor — nuestro cliente activo):
  NIT  : {nit_emisor}
  Nombre: {nom_emisor}

CAMPOS EXTRAÍDOS POR REGEX (pueden contener errores de OCR o parsing):
  fecha_emision  : "{campos.get('fecha', '')}"
  nit_receptor   : "{campos.get('nit_cli', '')}"
  dui_receptor   : "{campos.get('dui_cli', '')}"
  nombre_receptor: "{campos.get('nom_cli', '')}"

TEXTO DEL PDF:
{texto_pdf[:3500]}

TAREA DE VERIFICACIÓN:
1. FECHA: Debe ser DD/MM/YYYY y corresponder a la fecha de emisión del DTE.
   Busca en el texto si el campo está vacío, tiene formato incorrecto o es una fecha de vencimiento.
2. NOMBRE RECEPTOR: Razón social o nombre completo del COMPRADOR.
   - NO puede ser el mismo que el emisor: "{nom_emisor}".
   - Si dice "SIN NOMBRE" o está vacío, extrae el nombre real del bloque RECEPTOR del texto.
   - Devuelve en MAYÚSCULAS, sin caracteres especiales redundantes.
3. NIT RECEPTOR (14 dígitos): Identifica al comprador contribuyente.
   - NO puede ser igual al NIT del emisor ({nit_emisor}).
   - Si es vacío o incorrecto, busca en la sección RECEPTOR del texto.
4. DUI RECEPTOR (9 dígitos): Solo aplica para consumidor final (DTE-01/02).
   - Si el receptor tiene DUI y no NIT, el campo nit_cli debe quedar vacío.

Devuelve ÚNICAMENTE este JSON (sin markdown, sin texto adicional):
{{"fecha": "DD/MM/YYYY o null", "nom_cli": "NOMBRE EN MAYUSCULAS o null", "nit_cli": "14 digitos o null", "dui_cli": "9 digitos o null", "correcciones": ["descripcion breve de cada campo que cambiaste"]}}

IMPORTANTE: Usa null (sin comillas) cuando el campo ya está correcto. La lista correcciones debe estar vacía [] si no cambiaste nada."""


def _prompt_compras(
    texto_pdf: str,
    campos: dict,
    nit_receptor: str,
    nom_receptor: str,
) -> str:
    return f"""Eres un auditor fiscal experto en el sistema DTE de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL: El RECEPTOR de este DTE es el cliente activo del sistema (quien compra).
     El EMISOR es el proveedor/vendedor cuyos datos debemos verificar y corregir.

RECEPTOR (comprador — nuestro cliente activo):
  NIT  : {nit_receptor}
  Nombre: {nom_receptor}

CAMPOS EXTRAÍDOS POR REGEX (pueden contener errores):
  fecha_emision : "{campos.get('fecha', '')}"
  nit_emisor    : "{campos.get('nit_prov', '')}"
  nombre_emisor : "{campos.get('nom_prov', '')}"

TEXTO DEL PDF:
{texto_pdf[:3500]}

TAREA DE VERIFICACIÓN:
1. FECHA: Debe ser DD/MM/YYYY y ser la fecha de emisión del DTE (no de vencimiento, no de proceso).
2. NOMBRE EMISOR (proveedor/vendedor):
   - NO puede ser el nombre del receptor: "{nom_receptor}".
   - NO puede ser texto de metadata del PDF (fechas, "MÓDULO DE FACTURACIÓN", códigos, etc.).
   - Busca la Razón Social real en la sección EMISOR del documento.
   - Devuelve en MAYÚSCULAS.
3. NIT EMISOR (14 dígitos):
   - NO puede ser igual al NIT del receptor ({nit_receptor}).
   - Busca en la sección EMISOR si está vacío o incorrecto.
   - Ignora NRC, DUI y otros identificadores.

Devuelve ÚNICAMENTE este JSON (sin markdown, sin texto adicional):
{{"fecha": "DD/MM/YYYY o null", "nit_prov": "14 digitos o null", "nom_prov": "NOMBRE EN MAYUSCULAS o null", "correcciones": ["descripcion breve de cada campo que cambiaste"]}}

IMPORTANTE: Usa null cuando el campo ya está correcto. Lista correcciones vacía [] si no cambiaste nada."""


def _prompt_retenciones(
    texto_pdf: str,
    campos: dict,
    nit_cliente: str,
    nom_cliente: str,
) -> str:
    return f"""Eres un auditor fiscal experto en el sistema DTE de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL: Este es un DTE-07 (Comprobante de Retención).
     El AGENTE RETENEDOR es el cliente activo que emite la retención del 1% de IVA.
     El SUJETO RETENIDO es el proveedor sobre quien se aplica la retención.

AGENTE RETENEDOR (cliente activo — emite el DTE-07):
  NIT  : {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX:
  fecha_emision : "{campos.get('fecha', '')}"
  nit_proveedor : "{campos.get('nit_prov', '')}"

TEXTO DEL PDF:
{texto_pdf[:3500]}

TAREA DE VERIFICACIÓN:
1. FECHA: Debe ser DD/MM/YYYY y corresponder a la fecha de emisión del DTE-07.
2. NIT PROVEEDOR (14 dígitos): NIT del SUJETO RETENIDO (proveedor al que se le retiene).
   - NO puede ser igual al NIT del agente retenedor ({nit_cliente}).
   - Busca en el bloque del sujeto retenido si está vacío o es incorrecto.

Devuelve ÚNICAMENTE este JSON (sin markdown, sin texto adicional):
{{"fecha": "DD/MM/YYYY o null", "nit_prov": "14 digitos o null", "correcciones": ["descripcion breve de cada campo que cambiaste"]}}

IMPORTANTE: Usa null cuando el campo ya está correcto. Lista correcciones vacía [] si no cambiaste nada."""


def _prompt_sujetos_excluidos(
    texto_pdf: str,
    campos: dict,
    nit_cliente: str,
    nom_cliente: str,
) -> str:
    return f"""Eres un auditor fiscal experto en el sistema DTE de El Salvador (Manual de IVA DGII).
{_CONTEXTO_FISCAL}
ROL: Este es un DTE-14 (Comprobante de Liquidación / Sujeto Excluido).
     El COMPRADOR es el cliente activo que paga al sujeto excluido.
     El SUJETO EXCLUIDO es una persona natural o jurídica no inscrita en el IVA.

COMPRADOR (cliente activo — recibe el servicio/producto):
  NIT  : {nit_cliente}
  Nombre: {nom_cliente}

CAMPOS EXTRAÍDOS POR REGEX:
  fecha_emision : "{campos.get('fecha', '')}"
  nit_sujeto    : "{campos.get('nit_sujeto', '')}"
  dui_sujeto    : "{campos.get('dui_sujeto', '')}"
  nombre_sujeto : "{campos.get('nom_sujeto', '')}"

TEXTO DEL PDF:
{texto_pdf[:3500]}

TAREA DE VERIFICACIÓN:
1. FECHA: Debe ser DD/MM/YYYY y ser la fecha de emisión del DTE-14.
2. NOMBRE SUJETO EXCLUIDO: Persona natural o jurídica que presta el servicio.
   - NO puede ser el mismo que el comprador: "{nom_cliente}".
   - Los sujetos excluidos suelen ser personas naturales (personas físicas).
   - Busca en la sección del sujeto excluido del documento.
3. NIT SUJETO (14 dígitos): Si el sujeto es persona jurídica o natural con NIT.
   - NO puede ser igual al NIT del comprador ({nit_cliente}).
4. DUI SUJETO (9 dígitos): Si el sujeto es persona natural con DUI únicamente.
   - Solo aplica si no tiene NIT. El formato es XXXXXXXX-X (9 dígitos).

Devuelve ÚNICAMENTE este JSON (sin markdown, sin texto adicional):
{{"fecha": "DD/MM/YYYY o null", "nom_sujeto": "NOMBRE EN MAYUSCULAS o null", "nit_sujeto": "14 digitos o null", "dui_sujeto": "9 digitos o null", "correcciones": ["descripcion breve de cada campo que cambiaste"]}}

IMPORTANTE: Usa null cuando el campo ya está correcto. Lista correcciones vacía [] si no cambiaste nada."""


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
    nuevo = str(nuevo).strip().upper()
    if (
        nuevo
        and nuevo != actual.upper()
        and not es_nombre_sospechoso(nuevo)
        and 3 <= len(nuevo) <= 120
        and (not excluir_prefijo or not nuevo.startswith(excluir_prefijo[:12]))
    ):
        return nuevo
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
    """Toma la respuesta de Gemini y retorna solo los campos que realmente cambiaron."""
    campos_corr: dict = {}
    excluir = {nit_contexto} if nit_contexto else set()

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


# ─── Función pública universal ────────────────────────────────────────────────

def procesar_dte_con_gemini(
    texto_pdf: str,
    tipo_dte: str,
    campos_actuales: dict,
    contexto_receptor: dict,
) -> tuple[dict, list[str]]:
    """
    Verificador universal de DTEs con Gemini (auditor fiscal DGII El Salvador).

    Args:
        texto_pdf        : Texto extraído del PDF.
        tipo_dte         : "ventas" | "compras" | "retenciones" | "sujetos_excluidos"
        campos_actuales  : Campos extraídos por regex (pueden tener errores).
        contexto_receptor: {"nit": "...", "nombre": "..."} — cliente activo del sistema.

    Returns:
        (campos_corregidos, lista_de_correcciones)
        campos_corregidos contiene SOLO las claves cuyos valores cambiaron.
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
    resultado = _llamar_gemini(prompt)

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
        razones.append(f"Nombre extraído parece metadata: {campos['nom_prov'][:40]}")
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
