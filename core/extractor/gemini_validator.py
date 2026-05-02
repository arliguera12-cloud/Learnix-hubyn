"""
Validador con Google Gemini 1.5 Flash.
Se activa automaticamente cuando la confianza del motor nativo es baja.

Reglas de activacion:
- confianza_nit < UMBRAL  → NIT dudoso
- confianza_rs  < UMBRAL  → Razon social dudosa
- gra == 0 pero tot > 0   → Montos incompletos
- Configurado via GEMINI_API_KEY en st.secrets o variable de entorno
"""

import json
import re
import os

import streamlit as st

try:
    import google.generativeai as genai
    GENAI_DISPONIBLE = True
except ImportError:
    GENAI_DISPONIBLE = False


# ═══════════════════════════════════════════════════════════════
# CONFIGURACION
# ═══════════════════════════════════════════════════════════════

UMBRAL_CONFIANZA = 0.80

_MAPA_CONFIANZA = {
    "alta":  1.00,
    "cache": 0.95,
    "tabla": 0.88,
    "media": 0.70,
    "ocr":   0.65,
    "baja":  0.40,
}

_PROMPT_CCF = """
Eres un experto en documentos tributarios electronicos de El Salvador (DTE).
Analiza el siguiente texto de un Comprobante de Credito Fiscal (CCF / DTE-03)
o documento similar y extrae con precision los datos solicitados.

Reglas criticas:
- NIT del EMISOR: 14 digitos continuos (puede venir como XXXX-XXXXXX-XXX-X)
- Razon Social EMISOR: nombre legal de quien EMITE el documento
- Monto Gravado: subtotal ANTES del IVA
- IVA: debe ser exactamente el 13% del monto gravado
- Total: Gravado + IVA + Exento
- UUID / Codigo de Generacion: formato XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX

Datos ya extraidos por el motor nativo (pueden tener errores):
{datos_previos}

Texto completo del documento (primeros 3000 caracteres):
---
{texto_pdf}
---

Responde UNICAMENTE en JSON valido, sin texto adicional, sin markdown:
{{
  "nit_prov": "14 digitos sin guiones o vacio",
  "nom_prov": "RAZON SOCIAL EN MAYUSCULAS",
  "fecha": "DD/MM/YYYY",
  "gra": 0.00,
  "iva": 0.00,
  "exe": 0.00,
  "tot": 0.00,
  "gen": "UUID con guiones",
  "ctrl": "DTE-XX-XXXXXX-XXXXXXXXXX",
  "confianza_gemini": "alta o media o baja",
  "observaciones": "breve descripcion de correcciones realizadas"
}}
"""

_PROMPT_FACTURA = """
Eres un experto en documentos tributarios electronicos de El Salvador.
Analiza el texto de una Factura (DTE-01) o Factura de Exportacion (DTE-11).

Datos previos del sistema:
{datos_previos}

Texto del documento:
---
{texto_pdf}
---

Responde SOLO en JSON valido:
{{
  "nit": "NIT receptor (14 digitos) o vacio si es consumidor final",
  "nom": "NOMBRE RECEPTOR EN MAYUSCULAS",
  "fecha": "DD/MM/YYYY",
  "gra": 0.00,
  "exe": 0.00,
  "nos": 0.00,
  "tot": 0.00,
  "gen": "UUID",
  "ctrl": "DTE-01-...",
  "exp_serv": 0.00,
  "confianza_gemini": "alta o media o baja",
  "observaciones": "breve descripcion"
}}
"""

_PROMPT_RETENCION = """
Eres experto en Comprobantes de Retencion (DTE-07) de El Salvador.
La retencion es del 1% (uno por ciento) del monto sujeto.

Datos previos:
{datos_previos}

Texto:
---
{texto_pdf}
---

Responde solo en JSON:
{{
  "nit_contraparte": "NIT de quien recibe la retencion",
  "nom_contraparte": "NOMBRE EN MAYUSCULAS",
  "monto_sujeto": 0.00,
  "monto_retenido": 0.00,
  "fecha": "DD/MM/YYYY",
  "gen": "UUID",
  "sello": "codigo sello recepcion",
  "confianza_gemini": "alta o media o baja",
  "observaciones": "descripcion"
}}
"""

_PROMPT_DTE14 = """
Eres experto en Comprobantes de Sujeto Excluido (DTE-14) de El Salvador.
La retencion de renta es del 10% del monto total.

Datos previos:
{datos_previos}

Texto:
---
{texto_pdf}
---

Responde solo en JSON:
{{
  "nombre": "NOMBRE O RAZON SOCIAL EN MAYUSCULAS",
  "documento": "NIT 14 digitos o DUI 9 digitos",
  "fecha": "DD/MM/YYYY",
  "codigo": "UUID del documento",
  "sello": "sello de recepcion",
  "monto": 0.00,
  "retencion": 0.00,
  "confianza_gemini": "alta o media o baja",
  "observaciones": "descripcion"
}}
"""


# ═══════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════

def _obtener_api_key() -> str:
    """Obtiene la API key de Streamlit Secrets o variable de entorno."""
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


def _confianza_numerica(confianza_str: str) -> float:
    return _MAPA_CONFIANZA.get(str(confianza_str).lower().strip(), 0.50)


def _limpiar_json_response(texto: str) -> str:
    """Elimina bloques markdown y espacios del response de Gemini."""
    texto = texto.strip()
    texto = re.sub(r'^```(?:json)?\s*', '', texto)
    texto = re.sub(r'\s*```$', '', texto)
    return texto.strip()


def _llamar_gemini(prompt: str) -> dict:
    """Llamada centralizada a Gemini 1.5 Flash con manejo de errores."""
    if not GENAI_DISPONIBLE:
        return {"error": "google-generativeai no esta instalado."}

    api_key = _obtener_api_key()
    if not api_key:
        return {"error": "GEMINI_API_KEY no configurado en secrets."}

    try:
        genai.configure(api_key=api_key)
        model   = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        texto    = _limpiar_json_response(response.text)
        resultado = json.loads(texto)
        resultado["_fuente"] = "gemini-1.5-flash"
        return resultado
    except json.JSONDecodeError:
        return {"error": "Gemini retorno JSON invalido.", "_fuente": "gemini-error"}
    except Exception as e:
        return {"error": str(e), "_fuente": "gemini-error"}


# ═══════════════════════════════════════════════════════════════
# LOGICA DE ACTIVACION
# ═══════════════════════════════════════════════════════════════

def necesita_gemini(
    confianza_nit: str = "media",
    confianza_rs:  str = "media",
    gra:   float = 0.0,
    tot:   float = 0.0,
    iva:   float = 0.0,
) -> bool:
    """
    Decide si el documento necesita validacion adicional con Gemini.
    Retorna True si alguna condicion de baja confianza se cumple.
    """
    c_nit = _confianza_numerica(confianza_nit)
    c_rs  = _confianza_numerica(confianza_rs)

    if c_nit < UMBRAL_CONFIANZA:
        return True
    if c_rs < UMBRAL_CONFIANZA:
        return True
    # Montos inconsistentes: hay total pero no gravado
    if tot > 0 and gra == 0.0:
        return True
    # IVA no cuadra con el gravado
    if gra > 0 and iva > 0:
        diferencia = abs(round(gra * 0.13, 2) - round(iva, 2))
        if diferencia > 2.00:
            return True
    return False


def gemini_disponible() -> bool:
    """Verifica si Gemini esta configurado y disponible."""
    return GENAI_DISPONIBLE and bool(_obtener_api_key())


# ═══════════════════════════════════════════════════════════════
# VALIDADORES POR TIPO DE DOCUMENTO
# ═══════════════════════════════════════════════════════════════

def validar_con_gemini(
    texto_pdf:      str,
    datos_extraidos: dict,
    tipo_documento: str = "CCF"
) -> dict:
    """
    Valida y corrige datos de CCF (DTE-03) o Factura (DTE-01/11).

    Args:
        texto_pdf:       texto extraido del PDF
        datos_extraidos: dict con datos del motor nativo
        tipo_documento:  'CCF' | 'Factura' | 'Exportacion'

    Returns:
        dict con campos corregidos o {'error': ...}
    """
    datos_str = json.dumps(datos_extraidos, ensure_ascii=False, indent=2)
    texto_corto = texto_pdf[:3000]

    if tipo_documento in ("CCF", "03", "05", "06"):
        prompt = _PROMPT_CCF.format(
            datos_previos=datos_str,
            texto_pdf=texto_corto
        )
    else:
        prompt = _PROMPT_FACTURA.format(
            datos_previos=datos_str,
            texto_pdf=texto_corto
        )

    return _llamar_gemini(prompt)


def validar_retenciones_con_gemini(
    texto_pdf: str,
    datos:     dict
) -> dict:
    """Validacion especializada para DTE-07 (retenciones 1%)."""
    prompt = _PROMPT_RETENCION.format(
        datos_previos=json.dumps(datos, ensure_ascii=False, indent=2),
        texto_pdf=texto_pdf[:2500]
    )
    return _llamar_gemini(prompt)


def validar_sujeto_excluido_con_gemini(
    texto_pdf: str,
    datos:     dict
) -> dict:
    """Validacion especializada para DTE-14 (sujetos excluidos)."""
    prompt = _PROMPT_DTE14.format(
        datos_previos=json.dumps(datos, ensure_ascii=False, indent=2),
        texto_pdf=texto_pdf[:2500]
    )
    return _llamar_gemini(prompt)


# ═══════════════════════════════════════════════════════════════
# APLICADOR DE CORRECCIONES
# ═══════════════════════════════════════════════════════════════

def aplicar_correcciones_gemini(
    res_original: dict,
    res_gemini:   dict,
    campos_numericos: list = None
) -> dict:
    """
    Aplica las correcciones de Gemini al resultado original.
    Solo sobreescribe campos vacios o con valor 0.
    Agrega metadatos de Gemini al resultado.

    Args:
        res_original:     dict del motor nativo
        res_gemini:       dict de Gemini
        campos_numericos: lista de campos float a corregir

    Returns:
        dict combinado
    """
    if "error" in res_gemini:
        return res_original

    if campos_numericos is None:
        campos_numericos = ["gra", "iva", "exe", "tot", "nos", "exp_serv",
                            "monto_sujeto", "monto_retenido", "monto"]

    resultado = dict(res_original)

    # Campos texto: sobreescribir solo si el original esta vacio
    for campo in ["nit_prov", "nom_prov", "nit", "nom", "nit_contraparte",
                  "nom_contraparte", "nombre", "documento", "fecha",
                  "gen", "ctrl", "sello", "codigo"]:
        val_orig = str(resultado.get(campo, "")).strip()
        val_gem  = str(res_gemini.get(campo, "")).strip()
        if not val_orig and val_gem:
            resultado[campo] = val_gem

    # Campos numericos: sobreescribir solo si el original es 0
    for campo in campos_numericos:
        try:
            val_orig = float(resultado.get(campo, 0) or 0)
            val_gem  = float(res_gemini.get(campo, 0) or 0)
            if val_orig == 0.0 and val_gem > 0:
                resultado[campo] = round(val_gem, 2)
        except (TypeError, ValueError):
            pass

    # Metadatos Gemini
    resultado["confianza_gemini"] = res_gemini.get("confianza_gemini", "media")
    resultado["gemini_obs"]       = res_gemini.get("observaciones", "")

    return resultado
