# core/extractores/gemini_validator.py
"""
Validador de datos con Gemini 1.5 Flash.
Se activa cuando la confianza de extracción es baja (<85%).
"""

import google.generativeai as genai
import json
import re
import streamlit as st
import os

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

UMBRAL_CONFIANZA = 0.85

# Configurar API key desde Streamlit Secrets
try:
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
except Exception:
    pass


# ═══════════════════════════════════════════════════════════════
# FUNCIONES DE UTILIDAD
# ═══════════════════════════════════════════════════════════════

def _confianza_numerica(confianza_str: str) -> float:
    """
    Convierte etiqueta de confianza a número.
    
    Args:
        confianza_str: "alta", "media", "baja", "ocr", "tabla", "cache"
    
    Returns:
        float entre 0.0 y 1.0
    """
    mapa = {
        "alta":  1.00,
        "cache": 0.95,
        "tabla": 0.88,
        "media": 0.70,
        "ocr":   0.65,
        "baja":  0.40,
    }
    return mapa.get(str(confianza_str).lower().strip(), 0.50)


def necesita_gemini(confianza_nit: str, confianza_rs: str,
                    gra: float, tot: float) -> bool:
    """
    Decide si enviar a Gemini basado en:
    - Confianza baja en NIT o razón social
    - Monto gravado = 0 pero total > 0 (inconsistencia)
    
    Args:
        confianza_nit: nivel de confianza del NIT extraído
        confianza_rs: nivel de confianza de razón social
        gra: monto gravado
        tot: total
    
    Returns:
        True si debe validar con Gemini
    """
    c_nit = _confianza_numerica(confianza_nit)
    c_rs  = _confianza_numerica(confianza_rs)

    # Activar si confianza baja
    if c_nit < UMBRAL_CONFIANZA:
        return True
    if c_rs < UMBRAL_CONFIANZA:
        return True
    
    # Activar si hay inconsistencia lógica
    if tot > 0 and gra == 0.0:
        return True
    
    return False


# ═══════════════════════════════════════════════════════════════
# VALIDACIÓN CON GEMINI
# ═══════════════════════════════════════════════════════════════

def validar_con_gemini(texto_pdf: str, datos_extraidos: dict,
                       tipo_documento: str = "CCF") -> dict:
    """
    Envía texto del PDF a Gemini 1.5 Flash para validar/corregir datos.
    
    Args:
        texto_pdf: texto extraído del PDF
        datos_extraidos: dict con datos ya extraídos por el motor
        tipo_documento: "CCF", "Factura", "Compra", etc.
    
    Returns:
        dict con campos corregidos y confianza Gemini
    """
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Preparar prompt específico
        prompt = f"""
TAREA: Validar y extraer datos de un documento tributario de El Salvador (DTE).

DOCUMENTO: {tipo_documento}
TIPO: Dependiendo del contexto

INSTRUCCIONES:
1. Analiza el siguiente texto extraído de un {tipo_documento}.
2. Valida la información ya extraída por el sistema.
3. Corrige cualquier error evidente.
4. Responde ÚNICAMENTE en JSON válido.
5. NO uses markdown, NO uses bloques de código, devuelve JSON puro.

DATOS YA EXTRAÍDOS (pueden estar incorrectos):
{json.dumps(datos_extraidos, ensure_ascii=False, indent=2)}

TEXTO DEL DOCUMENTO A ANALIZAR:
---
{texto_pdf[:3000]}
---

CAMPOS A VALIDAR:
- nit_prov: NIT del emisor (14 dígitos: XXXX-XXXXXX-XXX-X o 14 números)
- nom_prov: Razón social del emisor
- fecha: Fecha de emisión (formato DD/MM/YYYY)
- gra: Monto gravado (sin IVA)
- iva: IVA (13% del gravado)
- exe: Monto exento
- tot: Total a pagar
- gen: Código de generación (UUID formato)
- ctrl: Número de control (DTE-XX-...)

IMPORTANTE:
- Si un campo es CLARAMENTE INCORRECTO, corrígelo
- Si NO ESTÁS SEGURO, MANTÉN el valor original del sistema
- IVA debe ser ~13% del monto gravado
- Total = Gravado + IVA + Exento

RESPUESTA (SOLO JSON, SIN MARKDOWN):
{{
  "nit_prov": "...",
  "nom_prov": "...",
  "fecha": "DD/MM/YYYY",
  "gra": 0.00,
  "iva": 0.00,
  "exe": 0.00,
  "tot": 0.00,
  "gen": "UUID",
  "ctrl": "DTE-XX-...",
  "confianza_gemini": "alta",
  "observaciones": "..."
}}
"""

        response = model.generate_content(prompt)
        texto_resp = response.text.strip()

        # Limpiar respuesta (eliminar markdown si viene)
        texto_resp = re.sub(r'^```(?:json)?\s*', '', texto_resp)
        texto_resp = re.sub(r'\s*```$', '', texto_resp)

        # Parsear JSON
        resultado = json.loads(texto_resp)
        resultado["_fuente"] = "gemini-1.5-flash"
        resultado["_exito"] = True
        
        return resultado

    except json.JSONDecodeError as e:
        return {
            "error": f"JSON inválido de Gemini: {str(e)}",
            "_fuente": "gemini-error",
            "_exito": False
        }
    except Exception as e:
        return {
            "error": f"Error Gemini: {str(e)}",
            "_fuente": "gemini-error",
            "_exito": False
        }


def validar_retenciones_con_gemini(texto_pdf: str, datos: dict) -> dict:
    """
    Validación especializada para DTE-07 (retenciones 1%).
    
    Args:
        texto_pdf: texto del PDF
        datos: datos extraídos previamente
    
    Returns:
        dict validado
    """
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
TAREA: Validar datos de retención de IVA (DTE-07) de El Salvador.

INSTRUCCIONES:
1. Extrae del texto: NIT, monto sujeto, monto retenido, fecha, UUID
2. IMPORTANTE: Retención debe ser 1% del monto sujeto
3. Responde SOLO en JSON válido, SIN MARKDOWN

DATOS ACTUALES:
{json.dumps(datos, ensure_ascii=False, indent=2)}

TEXTO:
---
{texto_pdf[:2000]}
---

RESPUESTA (JSON PURO):
{{
  "nit_contraparte": "...",
  "monto_sujeto": 0.00,
  "monto_retenido": 0.00,
  "fecha": "DD/MM/YYYY",
  "gen": "UUID",
  "confianza_gemini": "alta",
  "observaciones": "..."
}}
"""
        response = model.generate_content(prompt)
        texto_resp = response.text.strip()
        
        # Limpiar markdown
        texto_resp = re.sub(r'^```(?:json)?\s*', '', texto_resp)
        texto_resp = re.sub(r'\s*```$', '', texto_resp)
        
        resultado = json.loads(texto_resp)
        resultado["_fuente"] = "gemini-1.5-flash"
        resultado["_exito"] = True
        return resultado

    except Exception as e:
        return {
            "error": str(e),
            "_fuente": "gemini-error",
            "_exito": False
        }
