# core/gemini_validator.py
"""
Validación y complementación de datos usando Gemini 1.5 Flash
"""

import re
import json
import streamlit as st
from .constantes import GEMINI_MODEL


def necesita_gemini(confianza_nit: str, confianza_rs: str, gra: float, tot: float) -> bool:
    """
    Determina si un documento necesita validación con Gemini.
    """
    if confianza_nit in ["baja", "nula"]:
        return True
    if confianza_rs in ["baja", "nula"]:
        return True
    if gra == 0.0 and tot == 0.0:
        return True
    return False


def validar_con_gemini(texto_pdf: str, datos_extraidos: dict, tipo_doc: str = "CCF") -> dict:
    """
    Valida y complementa datos usando Gemini 1.5 Flash.
    """
    try:
        import google.generativeai as genai

        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"_exito": False, "error": "API Key no configurada"}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        prompt = f"""
Eres un experto en documentos tributarios electrónicos (DTE) de El Salvador.
Analiza el siguiente {tipo_doc} y extrae/corrige estos campos:

TEXTO DEL DOCUMENTO:
{texto_pdf[:3000]}

DATOS YA EXTRAÍDOS:
{json.dumps(datos_extraidos, indent=2, ensure_ascii=False)}

INSTRUCCIONES:
1. Identifica y corrige: NIT, nombre, montos (gravado, IVA, total)
2. Formato NIT: XXXX-XXXXXX-XXX-X (14 dígitos)
3. Montos: decimales con punto (1234.56)
4. Si un campo no existe, deja el valor original

RESPONDE SOLO en JSON (sin markdown):
{{
  "nit": "...",
  "nom": "...",
  "gra": 0.00,
  "iva": 0.00,
  "exe": 0.00,
  "tot": 0.00,
  "confianza_gemini": "alta|media|baja",
  "observaciones": "..."
}}
"""
        respuesta = model.generate_content(prompt)
        texto_resp = respuesta.text.strip()

        json_match = re.search(r'\{.*\}', texto_resp, re.DOTALL)
        if json_match:
            resultado = json.loads(json_match.group())
            resultado["_exito"] = True
            return resultado

        return {"_exito": False, "error": "No se pudo parsear respuesta Gemini"}

    except Exception as e:
        return {"_exito": False, "error": str(e)}


def validar_retenciones_con_gemini(texto_pdf: str, datos_extraidos: dict) -> dict:
    """
    Valida retenciones DTE-07 usando Gemini.
    """
    try:
        import google.generativeai as genai

        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"_exito": False}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        prompt = f"""
Eres un experto en DTE de El Salvador. Analiza este Comprobante de Retención (DTE-07).

TEXTO:
{texto_pdf[:2000]}

DATOS ACTUALES:
{json.dumps(datos_extraidos, indent=2)}

Extrae: NIT, nombre, monto sujeto a retención, monto retenido.

RESPONDE SOLO en JSON:
{{
  "nit_contraparte": "...",
  "nom_contraparte": "...",
  "monto_sujeto": 0.00,
  "monto_retenido": 0.00,
  "confianza_gemini": "alta|media|baja",
  "observaciones": "..."
}}
"""
        respuesta = model.generate_content(prompt)
        texto_resp = respuesta.text.strip()

        json_match = re.search(r'\{.*\}', texto_resp, re.DOTALL)
        if json_match:
            resultado = json.loads(json_match.group())
            resultado["_exito"] = True
            return resultado

        return {"_exito": False}

    except Exception as e:
        return {"_exito": False, "error": str(e)}
