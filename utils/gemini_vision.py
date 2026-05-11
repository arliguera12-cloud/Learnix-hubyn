"""
Learnix Hub — Gemini Vision v1.1 (multimodal PDF → DTE extraction).

Sends raw PDF bytes as base64 inlineData directly to gemini-2.5-flash Vision.
Primary extraction path — eliminates the need for pdfplumber text extraction.

Fix v1.1:
  • Removed all `nullable: True` and `BOOLEAN` fields from responseSchema
    (these cause HTTP 400 on multimodal inlineData requests).
  • Two-phase call: try with schema; auto-retry without schema on 400/schema errors.
  • Error surfaced via vision_ultimo_error() so the UI can display it.
"""
import base64
import json
import logging
import math
import os
import re
import time
import requests
import streamlit as st

log = logging.getLogger(__name__)

_GEMINI_MODEL = "gemini-2.5-flash"
_GEMINI_URL   = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{_GEMINI_MODEL}:generateContent"
)
_TIMEOUT = 60
_MAX_RETRIES    = 3
_BACKOFF_DELAYS = [2, 4, 8]   # seconds per retry attempt
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


# ─── Sub-schemas (sin nullable, sin BOOLEAN) ──────────────────────────────────
#
# IMPORTANT: nullable:True and BOOLEAN type cause HTTP 400 when combined with
# inlineData multimodal requests in gemini-2.5-flash. Use plain STRING/NUMBER
# types only. Fields not listed in "required" can be absent or null in output.

def _sub_razonamiento() -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "layout_detectado": {"type": "STRING"},
            "bloque_emisor"   : {"type": "STRING"},
            "bloque_receptor" : {"type": "STRING"},
            "autovalidacion"  : {"type": "STRING"},
        },
    }


def _sub_auditoria() -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "modelo_utilizado"    : {"type": "STRING"},
            "confianza_extraccion": {"type": "INTEGER"},
            "notas"               : {"type": "STRING"},
        },
        "required": ["confianza_extraccion"],
    }


# ─── Schemas por tipo de DTE (sin nullable, sin BOOLEAN) ─────────────────────

_SCHEMAS: dict[str, dict] = {
    "ventas": {
        "type": "OBJECT",
        "properties": {
            "tipo_documento"   : {"type": "STRING"},
            "fecha"            : {"type": "STRING"},
            "num_control"      : {"type": "STRING"},
            "codigo_generacion": {"type": "STRING"},
            "sello_recepcion"  : {"type": "STRING"},
            "nom_receptor"     : {"type": "STRING"},
            "nit_receptor"     : {"type": "STRING"},
            "dui_receptor"     : {"type": "STRING"},
            "gravadas"         : {"type": "STRING"},
            "exentas"          : {"type": "STRING"},
            "no_sujetas"       : {"type": "STRING"},
            "iva"              : {"type": "STRING"},
            "total"            : {"type": "STRING"},
            "alertas_fiscales" : {"type": "ARRAY", "items": {"type": "STRING"}},
            "razonamiento"     : _sub_razonamiento(),
            "auditoria_ia"     : _sub_auditoria(),
        },
        "required": ["alertas_fiscales", "auditoria_ia"],
    },
    "compras": {
        "type": "OBJECT",
        "properties": {
            "tipo_documento"   : {"type": "STRING"},
            "fecha"            : {"type": "STRING"},
            "num_control"      : {"type": "STRING"},
            "codigo_generacion": {"type": "STRING"},
            "sello_recepcion"  : {"type": "STRING"},
            "nom_emisor"       : {"type": "STRING"},
            "nit_emisor"       : {"type": "STRING"},
            "dui_emisor"       : {"type": "STRING"},
            "gravadas"         : {"type": "STRING"},
            "exentas"          : {"type": "STRING"},
            "no_sujetas"       : {"type": "STRING"},
            "iva"              : {"type": "STRING"},
            "retencion_iva1"   : {"type": "STRING"},
            "percepcion_iva"   : {"type": "STRING"},
            "retencion_renta"  : {"type": "STRING"},
            "total"            : {"type": "STRING"},
            "fovial"           : {"type": "STRING"},
            "cotrans"          : {"type": "STRING"},
            "alertas_fiscales" : {"type": "ARRAY", "items": {"type": "STRING"}},
            "razonamiento"     : _sub_razonamiento(),
            "auditoria_ia"     : _sub_auditoria(),
        },
        "required": ["alertas_fiscales", "auditoria_ia"],
    },
    "retenciones": {
        "type": "OBJECT",
        "properties": {
            "tipo_documento"    : {"type": "STRING"},
            "fecha"             : {"type": "STRING"},
            "num_control"       : {"type": "STRING"},
            "codigo_generacion" : {"type": "STRING"},
            "sello_recepcion"   : {"type": "STRING"},
            "nom_retenido"      : {"type": "STRING"},
            "nit_retenido"      : {"type": "STRING"},
            "monto_sujeto"      : {"type": "STRING"},
            "iva_retenido"      : {"type": "STRING"},
            "alertas_fiscales"  : {"type": "ARRAY", "items": {"type": "STRING"}},
            "razonamiento"      : _sub_razonamiento(),
            "auditoria_ia"      : _sub_auditoria(),
        },
        "required": ["alertas_fiscales", "auditoria_ia"],
    },
    "sujetos_excluidos": {
        "type": "OBJECT",
        "properties": {
            "tipo_documento"    : {"type": "STRING"},
            "fecha"             : {"type": "STRING"},
            "num_control"       : {"type": "STRING"},
            "codigo_generacion" : {"type": "STRING"},
            "sello_recepcion"   : {"type": "STRING"},
            "nom_sujeto"        : {"type": "STRING"},
            "nit_sujeto"        : {"type": "STRING"},
            "dui_sujeto"        : {"type": "STRING"},
            "base_compras"      : {"type": "STRING"},
            "retencion_renta"   : {"type": "STRING"},
            "alertas_fiscales"  : {"type": "ARRAY", "items": {"type": "STRING"}},
            "razonamiento"      : _sub_razonamiento(),
            "auditoria_ia"      : _sub_auditoria(),
        },
        "required": ["alertas_fiscales", "auditoria_ia"],
    },
}


# ─── Prompt construction ──────────────────────────────────────────────────────

_CONTEXTO_FISCAL = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERES UN AUDITOR CONTABLE EXPERTO EN LA LEY DE IVA Y RENTA DE EL SALVADOR.
APLICA ESTAS REGLAS PARA CUALQUIER DOCUMENTO DTE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CLASIFICACIÓN (TIPOS DTE):
  DTE-01  Factura Consumidor Final → receptor usa DUI. Inválido en módulo Compras (Anexo F-07).
  DTE-03  CCF                     → Comprobante de Crédito Fiscal entre contribuyentes IVA
  DTE-05  Nota de Crédito         → Reducción o anulación de DTE-03
  DTE-06  Nota de Débito          → Cargo adicional sobre DTE-03
  DTE-07  Comprobante Retención   → Agente retiene 1% de IVA sobre monto sujeto
  DTE-14  Sujeto Excluido         → Retención de Renta 10%. El proveedor NO es el Emisor.

IDENTIFICACIÓN (NIT / DUI):
  NIT : EXACTAMENTE 14 dígitos. Puede venir con guiones — quítalos: 0614-270815-107-7 → 06142708151077
  DUI : EXACTAMENTE  9 dígitos. Puede venir con guiones — quítalos: 04581234-7 → 045812347
  NRC : 1-7 dígitos (solo contribuyentes IVA)
  UUID: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX (CON guiones — es el Código de Generación)
  REGLA NIT/DUI: Si el proveedor es Persona Natural y NO tiene NIT, extrae su DUI del campo
    numDocumento o dui. Quítale los guiones. Devuélvelo limpio en el campo correspondiente.
  REGLA DTE-14: El proveedor real NO es el Emisor del documento. Extrae nombre e identificación
    de la sección "Sujeto Excluido" / sujetoExcluido. Busca su monto de Retención de Renta (10%).

DESGLOSE TRIBUTARIO OBLIGATORIO:
  IVA 13%          → código tributo 20 o "Impuesto al Valor Agregado". Si no hay Total IVA
                      explícito, suma los valores de Tributos con código 20.
  Retención IVA 1% → código 22 o "Retención IVA". Devolver en retencion_iva1.
  Percepción IVA   → código 23 o "Percepción IVA" (1% o 2%). Devolver en percepcion_iva.
  FOVIAL ($0.20/gal) → código C3. Solo gasolineras. Devolver en fovial.
  COTRANS ($0.10/gal)→ código 59. Solo gasolineras. Devolver en cotrans.
  Retención Renta 10% → solo DTE-14. Devolver en retencion_renta.

SELLO DE RECEPCIÓN:
  Exactamente ~40 caracteres ALFANUMÉRICOS CONTINUOS SIN guiones (ej: 20264BDE9F3A0C1D...).
  NUNCA es el UUID (tiene guiones). NUNCA empieza con "DTE-" (eso es Número de Control).
  Búscalo en TODO el texto, incluso bajo etiquetas como:
    "Sello de Recepción", "SelloRecibido", "respuestaHacienda.selloRecibido", "responseMH.selloRecibido".
  Devuelve "" si no lo localizas con certeza — NO inventes el valor.

REGLAS MATEMÁTICAS (tolerancia ±$0.05 para redondeos):
  IVA (DTE-03/05/06)  = Ventas Gravadas × 13%
  Retención (DTE-07)  = Monto Sujeto × 1%
  Retención (DTE-14)  = Base Compras × 10%
  Líquido (DTE-14)    = Base Compras − Retención Renta  (= Base × 0.90)
"""

_INSTRUCCIONES_ESPACIALES = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  REGLAS DE ORO — LEE ANTES DE EXTRAER CUALQUIER CAMPO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REGLA DE ORO #1 — CÓDIGO DE GENERACIÓN (UUID):
  EL UUID TIENE EXACTAMENTE 36 CARACTERES CON GUIONES
  (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX).
  ALGUNOS EMISORES (FARMACIAS, ETC.) LO IMPRIMEN PARTIDO EN DOS LÍNEAS CONSECUTIVAS.
  SI VES UN FRAGMENTO QUE PARECE LA PRIMERA MITAD DE UN UUID EN UNA LÍNEA Y LA
  SEGUNDA MITAD EN LA LÍNEA SIGUIENTE, DEBES UNIR AMBAS PARTES ELIMINANDO EL
  SALTO DE LÍNEA PARA RECONSTRUIR EL UUID COMPLETO DE 36 CARACTERES.
  NUNCA DEVUELVAS UN UUID TRUNCADO, PARTIDO O CON SALTOS DE LÍNEA INCRUSTADOS.

REGLA DE ORO #2 — TIPO DE DOCUMENTO (CAMPO CRÍTICO):
  DEVUELVE ÚNICA Y EXCLUSIVAMENTE EL CÓDIGO NUMÉRICO DE 2 DÍGITOS.
  EJEMPLOS CORRECTOS: "03" para CCF, "01" para Factura, "14" para Sujeto Excluido,
  "05" para Nota de Crédito, "06" para Nota de Débito, "07" para Retención, "11" para Factura Exenta.
  ESTÁ PROHIBIDO ESCRIBIR LETRAS, NOMBRES, DESCRIPCIONES O GUIONES EN ESTE CAMPO.
  MAL: "CCF", "03-Comprobante", "3", "Crédito Fiscal" — BIEN: "03"

REGLA DE ORO #3 — NIT/DUI DEL PROVEEDOR (¡PELIGRO DE CONFUSIÓN!):
  EXTRAE EL NIT O DUI ÚNICAMENTE DE LA CAJA SUPERIOR LLAMADA "DATOS DEL EMISOR"
  (O "SUJETO EXCLUIDO" EN DTE-14).
  ESTÁ ESTRICTAMENTE PROHIBIDO EXTRAER NÚMEROS DE DOCUMENTO DE LA SECCIÓN
  INFERIOR DE FIRMAS, RESPONSABLE, EXTENSIÓN O "ENTREGADO POR".
  LOS RESPONSABLES Y FIRMANTES AL FINAL DEL DOCUMENTO TIENEN NIT/DUI PROPIOS
  QUE NO CORRESPONDEN AL PROVEEDOR — IGNÓRALOS COMPLETAMENTE.
  SI HAY UN NÚMERO LARGO DE 14 DÍGITOS AL FINAL DE LA PÁGINA EN UNA SECCIÓN DE
  FIRMAS, NO ES EL NIT DEL EMISOR.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANÁLISIS VISUAL — 4 PASOS OBLIGATORIOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 — IDENTIFICAR LAYOUT VISUAL
  Los DTEs de El Salvador pueden tener estos formatos:
  • TICKET      : datos en columna única, "etiqueta: valor" en la misma línea
  • 2-COLUMNAS  : EMISOR (izquierda) y RECEPTOR (derecha) en el encabezado
  • ENCABEZADO  : bloque EMISOR arriba, bloque RECEPTOR separado por línea
  Analiza la estructura de 2 columnas o encabezado/pie de página para diferenciar
  al Emisor del Receptor por su POSICIÓN FÍSICA en el documento.
  Registra el formato en razonamiento.layout_detectado.

PASO 2 — LOCALIZAR VISUALMENTE LOS RECUADROS DE EMISOR / RECEPTOR
  Analiza visualmente la estructura espacial del documento.
  Identifica los recuadros físicos (bordes, líneas, agrupación espacial) que
  corresponden al EMISOR y al RECEPTOR.
  • Formato 2-COLUMNAS : recuadro EMISOR en la parte superior-izquierda;
                          recuadro RECEPTOR en la parte superior-derecha.
  • Formato ENCABEZADO : bloque EMISOR arriba; RECEPTOR debajo, separado por
                          línea horizontal o espacio en blanco.
  • Formato TICKET     : busca los marcadores textuales "EMISOR:", "RECEPTOR:",
                          "DATOS DEL EMISOR", "DATOS DEL RECEPTOR",
                          "ADQUIRIENTE:", "CLIENTE:", "PROVEEDOR:".

  ⚠️ REGLA ESPACIAL CRÍTICA: Diferencia al Emisor del Receptor por su ubicación
  física en la página, NO por el texto de la etiqueta. Las etiquetas como
  "RAZÓN SOCIAL", "NIT:", "NRC:" son parte del diseño fijo del DTE y jamás son
  el valor a extraer. El valor siempre está DESPUÉS del ":" de cada etiqueta.

  Registra en razonamiento.bloque_emisor y razonamiento.bloque_receptor la
  ubicación detectada y los primeros 80 caracteres del bloque identificado.

PASO 3 — EXTRAER VALORES (NUNCA ETIQUETAS)
  ⚠️ REGLA ABSOLUTA: el VALOR es lo que aparece DESPUÉS del ":" en cada campo.
  ✅ "Nombre o Razón Social: GRANJA SAN DIEGO S.A." → extrae "GRANJA SAN DIEGO S.A."
  ❌ Nunca extraer "Nombre o Razón Social" como valor — eso es la ETIQUETA
  ❌ Nunca extraer texto que contenga: "NIT:", "NRC:", "COD.", "DTE-", "SELLO",
     "GENERACIÓN", "CONTROL", "COMPROBANTE", "DOCUMENTO TRIBUTARIO"

  Para NÚMEROS: solo dígitos y punto decimal. Elimina "$", "US", comas de miles.
  Para FECHAS: formato DD/MM/YYYY (ej: "15/03/2025"). Busca "Fecha de Emisión:".
  Para SELLO DE RECEPCIÓN: Es ESTRICTAMENTE una cadena alfanumérica de EXACTAMENTE
    40 caracteres CONTINUOS SIN guiones ni espacios (ej: "20264BDE9F3A0C1D...").
    Reglas de identificación:
    • NUNCA es el UUID/Código de Generación: el UUID tiene guiones (XXXXXXXX-XXXX-...).
    • NUNCA es el Número de Control: empieza con "DTE-".
    • Búscalo junto al texto "Sello de Recepción", "Sello Recibido", "SelloRecibido",
      "respuestaHacienda" o "responseMH" — puede aparecer en cualquiera de estas secciones.
    • Si hay varias cadenas largas, elige la de exactamente ~40 chars sin guiones.
    • Devuelve "" (vacío) si no lo localizas con certeza — no inventes el valor.
  Para IVA: Si no existe un campo "Total IVA" explícito, búscalo en la sección
    Tributos bajo el código "20" o la descripción "Impuesto al Valor Agregado".
  Para UUID (codigo_generacion): XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX (36 chars).

  CÓDIGO DE GENERACIÓN PARTIDO (farmacias como San Nicolás y similares):
    Algunos emisores imprimen el UUID de 36 chars dividido en DOS líneas consecutivas.
    Si ves fragmentos que parecen partes de un UUID (ej: "XXXXXXXX-XXXX" en una línea y
    "XXXX-XXXX-XXXXXXXXXXXX" en la siguiente), concaténalos ELIMINANDO el salto de línea
    para reconstruir el UUID completo de 36 chars.
    Devuelve siempre el UUID en formato XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.
    NUNCA devuelvas un UUID truncado o partido.

  FOVIAL Y COTRANS ESCONDIDOS (gasolineras con formato especial):
    En algunos DTEs de gasolinera, FOVIAL y COTRANS NO aparecen en el detalle de ítems
    sino en el cuadro de 'Suma Total de Operaciones', 'Sub-total' o cuadro de tributos,
    etiquetados con los códigos:
      • D1 → FOVIAL  ($0.20 por galón)
      • C8 → COTRANS ($0.10 por galón)
    Si el emisor menciona palabras como "COMBUSTIBLE", "GALÓN", "LITRO", "GASOLINERA"
    o "SHELL", "TEXACO", "PUMA", "UNO", "PRIMAX", busca OBLIGATORIAMENTE los códigos
    D1 y C8 en el cuadro de totales o tributos y extrae sus montos en los campos
    fovial y cotrans respectivamente. No dejes estos campos en cero si los ves.

  Para num_control: formato DTE-XX-XXXX-XXXXXXXXX (con guiones).
  Para NIT/DUI del Emisor en compras:
    • Busca primero NIT de 14 dígitos. Si no encuentras NIT, busca DUI de 9 dígitos.
    • Nunca dejes la identificación del emisor vacía si hay un número de 9 o 14
      dígitos presente en el bloque del Emisor.

PASO 4 — AUTO-VALIDAR Y GENERAR ALERTAS
  Verifica cada campo extraído:
  • NIT ≠ 14 dígitos → alerta "NIT inválido: {valor extraído}"
  • DUI ≠  9 dígitos → alerta "DUI inválido: {valor extraído}"
  • Nombre contiene texto de etiqueta → alerta "Nombre parece etiqueta: {valor}"
  • IVA del doc ≠ gravadas × 13% (±$0.02) → alerta "IVA no coincide: doc={X} calc={Y}"
  • Retención DTE-07 ≠ base × 1% (±$0.02) → alerta "Retención 1% incorrecta: doc={X} calc={Y}"
  • Retención DTE-14 ≠ base × 10% (±$0.02) → alerta "Retención renta 10% incorrecta: doc={X} calc={Y}"
  • Líquido DTE-14 ≠ base × 90% (±$0.02) → alerta "Líquido incorrecto: esperado={Y}"
  • identificación emisor/sujeto vacía con número visible → alerta "Identificación no capturada"
  Lista vacía [] si no hay alertas.

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
        "• Si el receptor es 'CONSUMIDOR FINAL' → nom_receptor='CONSUMIDOR FINAL', "
        "nit_receptor y dui_receptor deja vacíos."
    ),
    "compras": (
        "El RECEPTOR es el cliente activo del sistema (quien compra y recibe el crédito).\n"
        "El EMISOR es el PROVEEDOR/VENDEDOR — extrae su nombre e identificación.\n"
        "• El NIT del emisor NUNCA puede ser igual al NIT del cliente activo.\n"
        "• Si nom_emisor coincide con el nombre del receptor → está mal extraído.\n"
        "• Identificación del proveedor — REGLA DUAL:\n"
        "  1. Busca primero NIT de 14 dígitos (nit_emisor).\n"
        "  2. Si el emisor es Persona Natural sin NIT, extrae su DUI de 9 dígitos (dui_emisor).\n"
        "  Nunca dejes la identificación del emisor vacía si hay un número de 9 o 14\n"
        "  dígitos presente en el bloque del Emisor.\n"
        "• DTE-14 (Comprobante de Liquidación / Sujeto Excluido): el proveedor NO es el\n"
        "  Emisor del documento (ese es el comprador). El proveedor real es el SUJETO\n"
        "  EXCLUIDO — busca su nombre e identificación en la sección 'Sujeto Excluido'\n"
        "  o 'sujetoExcluido'. Extrae su DUI o NIT desde ese bloque, no del bloque Emisor.\n"
        "• FOVIAL y COTRANS: si el emisor es una gasolinera o distribuidora de\n"
        "  combustibles, es OBLIGATORIO extraer estos impuestos específicos.\n"
        "  Asígnalos a las llaves 'fovial' y 'cotrans' del JSON (montos exactos en $).\n"
        "  NO los sumes al monto Gravado ni al IVA — son campos separados."
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
        "• tipo_documento    : '01'|'03'|'05'|'06' (del Número de Control)\n"
        "• fecha             : DD/MM/YYYY (campo 'Fecha de Emisión')\n"
        "• num_control       : Número de control DTE completo con guiones\n"
        "• codigo_generacion : UUID del documento (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)\n"
        "• sello_recepcion   : Sello MH — cadena alfanumérica de ~40 chars SIN guiones, junto al texto 'Sello de Recepción'\n"
        "• nom_receptor      : Nombre/Razón social del COMPRADOR (del bloque RECEPTOR)\n"
        "• nit_receptor      : NIT del receptor (14 dígitos, si aplica)\n"
        "• dui_receptor      : DUI del receptor (9 dígitos, consumidores finales)\n"
        "• gravadas, exentas, no_sujetas, iva, total : montos numéricos en dólares\n"
        "• alertas_fiscales  : lista de problemas encontrados (vacía [] si todo OK)"
    ),
    "compras": (
        "• tipo_documento    : '03'|'05'|'06'|'11'|'14'\n"
        "• fecha             : DD/MM/YYYY\n"
        "• num_control       : Número de control DTE completo\n"
        "• codigo_generacion : UUID del documento\n"
        "• sello_recepcion   : Sello MH — alfanumérico de ~40 chars SIN guiones.\n"
        "  REGLA SELLO: Busca un alfanumérico de exactamente ~40 chars sin guiones.\n"
        "  Puede estar al final del documento o bajo etiquetas como 'Sello de Recepción',\n"
        "  'respuestaHacienda', 'responseMH' o 'SelloRecibido'. Devuelve '' si no lo ubicas.\n"
        "• nom_emisor        : Nombre/Razón social del PROVEEDOR.\n"
        "  REGLA PROVEEDOR: Si el documento es DTE-14 (Sujeto Excluido), el proveedor NO\n"
        "  es el bloque Emisor — extrae nombre e identificación de la sección 'Sujeto Excluido'.\n"
        "• nit_emisor        : NIT del PROVEEDOR (14 dígitos) — preferir sobre DUI.\n"
        "  REGLA NIT/DUI: Si el proveedor es Persona Natural y NO tiene NIT de 14 dígitos,\n"
        "  extrae obligatoriamente su DUI de 9 dígitos en el campo dui_emisor. Nunca dejes\n"
        "  la identificación del proveedor vacía si hay un número de 9 o 14 dígitos visible.\n"
        "• dui_emisor        : DUI del PROVEEDOR (9 dígitos) — solo si no hay NIT de 14\n"
        "• gravadas          : monto gravado en dólares (string exacto del documento)\n"
        "• exentas           : monto exento (string exacto)\n"
        "• no_sujetas        : monto no sujeto (string exacto)\n"
        "• iva               : crédito fiscal IVA (string exacto).\n"
        "  REGLA IVA: Si no hay un campo 'Total IVA' explícito, búscalo en la sección\n"
        "  Tributos bajo el código '20' o descripción 'Impuesto al Valor Agregado' y suma\n"
        "  sus valores. No dejes iva vacío si hay un monto de tributo IVA visible.\n"
        "• total             : total del documento (string exacto)\n"
        "• fovial            : impuesto FOVIAL si el emisor es gasolinera (string exacto, '' si no aplica)\n"
        "• cotrans           : impuesto COTRANS si el emisor es gasolinera (string exacto, '' si no aplica)\n"
        "• alertas_fiscales  : lista de problemas ([] si todo OK)"
    ),
    "retenciones": (
        "• tipo_documento    : '07'\n"
        "• fecha             : DD/MM/YYYY\n"
        "• num_control       : Número de control DTE completo\n"
        "• codigo_generacion : UUID del documento (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)\n"
        "• sello_recepcion   : EXTRACCIÓN OBLIGATORIA — Sello de Recepción del MH.\n"
        "  SELLO DE RECEPCIÓN (CRÍTICO): Es un código alfanumérico contiguo de EXACTAMENTE\n"
        "  40 caracteres SIN GUIONES ni espacios (ej: '20264BDE9F3A0C1D...').\n"
        "  Búscalo en la parte superior o inferior del documento, también en cualquier sección.\n"
        "  Puede estar etiquetado como 'Sello de Recepción', 'SelloRecibido', 'selloRecibido',\n"
        "  'respuestaHacienda.selloRecibido', 'responseMH.selloRecibido', o cerca de\n"
        "  la 'Fecha y Hora de Generación' o 'Fecha de Procesamiento MH'.\n"
        "  NUNCA lo confundas con el Código de Generación/UUID (36 chars, CON guiones).\n"
        "  NUNCA lo confundas con el Número de Control (empieza con 'DTE-').\n"
        "  Si el PDF tiene múltiples páginas, revisa la PRIMERA y la ÚLTIMA exhaustivamente.\n"
        "  Devuelve '' solo si tras revisar todo el documento no lo localizas con certeza.\n"
        "• nom_retenido      : Nombre del SUJETO RETENIDO\n"
        "• nit_retenido      : NIT del sujeto retenido (14 dígitos)\n"
        "• monto_sujeto      : Base monetaria sujeta a retención ($)\n"
        "• iva_retenido      : Monto retenido ($ — debe ser ≈1% de monto_sujeto)\n"
        "• alertas_fiscales  : lista de problemas ([] si todo OK)"
    ),
    "sujetos_excluidos": (
        "• tipo_documento    : '14'\n"
        "• fecha             : DD/MM/YYYY\n"
        "• num_control       : Número de control DTE completo\n"
        "• codigo_generacion : UUID del documento (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)\n"
        "• sello_recepcion   : EXTRACCIÓN OBLIGATORIA — Sello de Recepción del MH.\n"
        "  Alfanumérico de EXACTAMENTE 40 chars SIN GUIONES. Búscalo junto a 'Sello de\n"
        "  Recepción', 'SelloRecibido', 'respuestaHacienda' o 'responseMH'. Revisa primera\n"
        "  y última página. NUNCA confundir con UUID (36 chars con guiones). Devuelve ''.\n"
        "• nom_sujeto        : Nombre del SUJETO EXCLUIDO\n"
        "• nit_sujeto        : NIT del sujeto (14 dígitos, persona jurídica)\n"
        "• dui_sujeto        : DUI del sujeto (9 dígitos, persona natural)\n"
        "• base_compras      : Sumatoria de compras / sub-total ($)\n"
        "• retencion_renta   : Retención renta Pago a Cuenta ($ ≈10% de base)\n"
        "• alertas_fiscales  : lista de problemas ([] si todo OK)"
    ),
}


def _build_prompt(tipo_dte: str, nit_ctx: str, nom_ctx: str) -> str:
    return (
        f"Eres un AUDITOR FISCAL SENIOR especializado en DTEs de El Salvador.\n"
        f"Analiza el documento PDF adjunto usando tus CAPACIDADES DE VISIÓN.\n\n"
        f"{_CONTEXTO_FISCAL}\n"
        f"CLIENTE ACTIVO DEL SISTEMA:\n"
        f"  NIT   : {nit_ctx}\n"
        f"  Nombre: {nom_ctx}\n\n"
        f"ROL EN ESTE DOCUMENTO:\n{_ROLES.get(tipo_dte, '')}\n\n"
        f"{_INSTRUCCIONES_ESPACIALES}\n"
        f"CAMPOS A EXTRAER:\n{_CAMPOS.get(tipo_dte, '')}\n\n"
        f"INSTRUCCIONES DE SALIDA:\n"
        f"  • Devuelve JSON válido según el schema. Omite o deja null campos no encontrados.\n"
        f"  • alertas_fiscales: lista todos los problemas; [] si no hay ninguno.\n"
        f"  • auditoria_ia.modelo_utilizado = 'gemini-2.5-flash-vision'\n"
        f"  • auditoria_ia.confianza_extraccion: entero 0-100.\n"
        f"  • auditoria_ia.notas: 1-2 oraciones sobre cómo resolviste ambigüedades."
    )


# ─── HTTP POST (una sola llamada, con o sin responseSchema) ───────────────────

def _http_post(
    pdf_bytes: bytes,
    prompt: str,
    api_key: str,
    schema: dict | None,
) -> dict | None:
    """
    Sends the PDF as base64 inlineData to Gemini Vision.
    Returns parsed JSON dict or None on any error (sets _ultimo_error).
    """
    global _ultimo_error

    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    gen_cfg: dict = {
        "temperature"     : 0.0,
        "maxOutputTokens" : 4096,
        "responseMimeType": "application/json",
        "thinkingConfig"  : {"thinkingBudget": 0},
    }
    if schema:
        gen_cfg["responseSchema"] = schema

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
            body = resp.text[:500]
            _ultimo_error = f"HTTP 400 — {body}"
            log.error("Vision 400: %s", resp.text[:800])
            return None
        if resp.status_code == 403:
            _ultimo_error = "API key inválida o sin permiso (403)."
            return None
        if resp.status_code == 404:
            _ultimo_error = f"Modelo '{_GEMINI_MODEL}' no disponible (404)."
            return None
        if resp.status_code == 429:
            _ultimo_error = "Cuota de Gemini Vision agotada (429)."
            return None
        if resp.status_code in (500, 502, 503, 504):
            _ultimo_error = f"Gemini Vision no disponible temporalmente ({resp.status_code})."
            return None

        resp.raise_for_status()

        candidates = resp.json().get("candidates", [])
        if not candidates:
            _ultimo_error = "Gemini Vision: respuesta sin candidatos."
            return None

        raw = ""
        for part in candidates[0].get("content", {}).get("parts", []):
            txt = part.get("text", "").strip()
            if txt:
                raw = txt
                break

        if not raw:
            _ultimo_error = "Gemini Vision: respuesta vacía."
            return None

        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
        raw = re.sub(r'\s*```\s*$', '', raw)

        result = json.loads(raw)
        _ultimo_error = ""
        return result

    except requests.exceptions.Timeout:
        _ultimo_error = f"Timeout ({_TIMEOUT}s) — PDF demasiado grande o red lenta."
        return None
    except requests.exceptions.ConnectionError:
        _ultimo_error = "Sin conexión a Internet para llamar a Gemini Vision."
        return None
    except json.JSONDecodeError as exc:
        _ultimo_error = f"JSON inválido de Gemini Vision: {exc}"
        log.warning("Vision JSON error: %s | raw=%s", exc, (raw or "")[:300])
        return None
    except Exception as exc:
        _ultimo_error = f"Error inesperado: {exc}"
        log.error("Vision unexpected error", exc_info=True)
        return None


# ─── Llamada con reintentos automáticos ──────────────────────────────────────

def _llamar_vision(pdf_bytes: bytes, prompt: str, schema: dict | None) -> dict | None:
    """
    Calls Gemini Vision with automatic retry for transient errors:
      • 429 / 5xx  → exponential backoff (2 s, 4 s, 8 s), up to 3 attempts.
      • 400 schema error → Phase 2: one retry without responseSchema (no sleep).
      • Other errors → fail immediately.
    Two-phase Vision call:
      Phase 1 — with responseSchema (structured output).
      Phase 2 — without responseSchema if Phase 1 returns HTTP 400
                 (responseSchema + inlineData can conflict in some API versions).
    """
    global _ultimo_error

    if not pdf_bytes or len(pdf_bytes) < 512:
        _ultimo_error = "PDF vacío o demasiado pequeño para Vision."
        return None

    if len(pdf_bytes) > 20 * 1024 * 1024:
        _ultimo_error = "PDF demasiado grande para envío inline (>20 MB)."
        return None

    api_key = _get_api_key()

    for attempt in range(_MAX_RETRIES):
        result = _http_post(pdf_bytes, prompt, api_key, schema)
        if result is not None:
            return result

        err = _ultimo_error

        # Transient error (429 burst limit or 5xx server error) → retry with backoff
        is_transient = (
            "429" in err or "quota" in err.lower()
            or any(code in err for code in ("500", "502", "503", "504"))
        )
        if is_transient:
            if attempt < _MAX_RETRIES - 1:
                wait = _BACKOFF_DELAYS[attempt]
                log.warning(
                    "Vision transient error (attempt %d/%d): %s. Waiting %ds...",
                    attempt + 1, _MAX_RETRIES, err[:80], wait,
                )
                time.sleep(wait)
                continue
            _ultimo_error = f"{err} (tras {_MAX_RETRIES} intentos)"
            return None

        # Schema conflict → Phase 2: one attempt without responseSchema
        is_schema_error = (
            "400" in err
            or "schema" in err.lower()
            or "nullable" in err.lower()
            or "unknown field" in err.lower()
            or "invalid value" in err.lower()
        )
        if schema and is_schema_error:
            log.warning("Vision Phase 2 (no schema) due to: %s", err[:80])
            result = _http_post(pdf_bytes, prompt, api_key, schema=None)
            if result is not None:
                if isinstance(result, dict) and "auditoria_ia" not in result:
                    result["auditoria_ia"] = {}
                _ultimo_error = ""
                return result
            if _ultimo_error:
                _ultimo_error = f"Fase 1: {err} | Fase 2: {_ultimo_error}"
            else:
                _ultimo_error = err
            return None

        # Non-retryable error (403, 404, JSON parse, connection, timeout)
        return None

    return None


# ─── Mapeo de campos (vision output → nombres esperados por las páginas) ──────

def _limpio_str(raw) -> str | None:
    if raw is None or str(raw).strip().lower() in ("null", "none", ""):
        return None
    return str(raw).strip() or None


def _limpio_sello(raw) -> str:
    """Validates a sello_recepcion: strips dashes/spaces, requires 25-60 chars, mixed alphanum."""
    if not raw:
        return ""
    v = re.sub(r'[\s\-]', '', str(raw).strip()).upper()
    if (25 <= len(v) <= 60
            and re.search(r'[A-Z]', v)
            and re.search(r'[0-9]', v)
            and not v.startswith('DTE')):
        return v
    return ""


def _limpio_nit(raw) -> str:
    return re.sub(r'[^0-9]', '', str(raw or ""))


def _limpiar_monto_vision(raw) -> float:
    """
    Robust parser for monetary STRING values returned by Gemini Vision.

    Rules applied in order:
    1. None / empty / 'null'    → 0.0
    2. Remove '$', spaces, NBSP
    3. Comma + point both present:
         "1,234.56" (comma before dot) → remove comma   → 1234.56
         "1.234,56" (dot before comma) → dot=thousands  → 1234.56
    4. Only comma:
         "60,17"  (≤2 decimal digits) → comma=decimal   → 60.17
         "1,500"  (3 decimal digits)  → comma=thousands → 1500.0
    5. Point with exactly 3 decimal digits ("60.177"):
         → provider typo, truncate to 2 decimals        → 60.17
    6. Otherwise: direct float conversion.

    Returns 0.0 on any parse failure.
    """
    if raw is None:
        return 0.0
    s = str(raw).strip().replace("$", "").replace(" ", "").replace("\xa0", "")
    if not s or s.lower() in ("null", "none", ""):
        return 0.0

    if "," in s and "." in s:
        if s.index(",") < s.index("."):
            s = s.replace(",", "")           # "1,234.56" → comma=thousands
        else:
            s = s.replace(".", "").replace(",", ".")  # "1.234,56" → dot=thousands
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace(",", "")           # "1,500" → comma=thousands
        else:
            s = s.replace(",", ".")          # "60,17" → comma=decimal

    try:
        val = float(s)
        # Truncate if exactly 3 decimal digits (provider typo: "60.177" → 60.17)
        if "." in s and len(s.split(".", 1)[1]) == 3:
            val = math.floor(val * 100) / 100
        return round(val, 2)
    except (ValueError, TypeError):
        return 0.0


def _buscar_sello_forzado(pdf_bytes: bytes) -> str:
    """
    Segunda llamada a Gemini Vision dedicada SOLO al Sello de Recepción.
    Usa respuesta texto plano (no JSON schema) y un prompt ultrafocalizado.
    Se invoca cuando la llamada principal no extrajo el sello.
    """
    api_key = _get_api_key()
    if not api_key or not pdf_bytes:
        return ""

    prompt = (
        "Eres un extractor especializado. Tu ÚNICA tarea es encontrar el Sello de Recepción "
        "en este documento DTE de El Salvador.\n\n"
        "El Sello de Recepción es:\n"
        "• Una cadena alfanumérica de EXACTAMENTE ~40 caracteres SIN guiones ni espacios\n"
        "• Contiene letras (A-Z) Y dígitos (0-9) mezclados\n"
        "• Ejemplos reales: 20255C20E45745184C2B954A6A3635B24471EKLT\n"
        "                   20258A7BB96EF5724E438F17E95D508EB6ECFKLC\n\n"
        "Búscalo en TODO el documento:\n"
        "• Junto a la etiqueta 'Sello de Recepción:' o 'SelloRecibido:'\n"
        "• En la parte SUPERIOR o INFERIOR del documento (sello/stamp del MH)\n"
        "• Cerca de 'Fecha y Hora de Generación', 'Procesado por MH', 'Fecha Procesado'\n"
        "• En cualquier recuadro o sello visual impreso\n"
        "• Como campo JSON: selloRecibido, respuestaHacienda.selloRecibido\n\n"
        "NUNCA confundas con:\n"
        "• UUID/Código de Generación: tiene GUIONES (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)\n"
        "• Número de Control: empieza con 'DTE-'\n"
        "• NIT: exactamente 14 dígitos (solo números)\n\n"
        "Revisa la primera Y la última página exhaustivamente.\n\n"
        "Responde ÚNICAMENTE con el sello encontrado (la cadena alfanumérica).\n"
        "Si definitivamente no lo encuentras, responde exactamente: NOTFOUND"
    )

    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    payload  = {
        "contents": [{
            "parts": [
                {"inlineData": {"mimeType": "application/pdf", "data": pdf_b64}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "temperature"     : 0.0,
            "maxOutputTokens" : 128,
            "thinkingConfig"  : {"thinkingBudget": 0},
        },
    }

    try:
        resp = requests.post(
            _GEMINI_URL,
            params  = {"key": api_key},
            json    = payload,
            timeout = _TIMEOUT,
        )
        if resp.status_code != 200:
            log.warning("_buscar_sello_forzado HTTP %d", resp.status_code)
            return ""

        candidates = resp.json().get("candidates", [])
        if not candidates:
            return ""

        raw = ""
        for part in candidates[0].get("content", {}).get("parts", []):
            txt = part.get("text", "").strip()
            if txt:
                raw = txt
                break

        if not raw or "NOTFOUND" in raw.upper():
            return ""

        return _limpio_sello(raw)

    except Exception as exc:
        log.warning("_buscar_sello_forzado error: %s", exc)
        return ""


def _mapear_campos(resultado: dict, tipo_dte: str, nit_ctx: str) -> dict:
    """Maps vision field names to page-expected field names and filters invalid values."""
    out: dict = {}

    # tipo_documento: forzar código de 2 dígitos (Gemini puede devolver "CCF", "3", "03-CCF")
    raw_tipo = resultado.get("tipo_documento")
    if raw_tipo is not None:
        _m_tipo = re.search(r'\d+', str(raw_tipo))
        if _m_tipo:
            out["tipo_documento"] = _m_tipo.group(0).zfill(2)

    # Campos comunes de texto
    for campo in ("fecha", "num_control"):
        v = _limpio_str(resultado.get(campo))
        if v:
            out[campo] = v

    # UUID: limpieza forzada de saltos de línea incrustados (farmacias con UUID partido)
    uuid_raw = resultado.get("codigo_generacion")
    if uuid_raw is not None:
        uuid_clean = str(uuid_raw).replace("\n", "").replace("\r", "").replace(" ", "").strip()
        if uuid_clean and uuid_clean.lower() not in ("null", "none", ""):
            out["codigo_generacion"] = uuid_clean

    sello_v = _limpio_sello(resultado.get("sello_recepcion"))
    if sello_v:
        out["sello_recepcion"] = sello_v

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
            v = _limpiar_monto_vision(resultado.get(campo))
            if v:
                out[campo] = v

    elif tipo_dte == "compras":
        nom = _limpio_str(resultado.get("nom_emisor"))
        if nom and len(nom) >= 3:
            out["nom_prov"] = nom.upper()

        nit = _limpio_nit(resultado.get("nit_emisor"))
        if len(nit) == 14 and nit != nit_ctx:
            out["nit_prov"] = nit
        else:
            # DUI fallback: some providers are individuals without NIT (9-digit DUI)
            dui = _limpio_nit(resultado.get("dui_emisor"))
            if len(dui) == 9 and dui != nit_ctx:
                out["nit_prov"] = dui

        for campo in ("gravadas", "exentas", "no_sujetas", "iva", "total"):
            v = _limpiar_monto_vision(resultado.get(campo))
            if v:
                out[campo] = v

        fov = _limpiar_monto_vision(resultado.get("fovial"))
        if fov > 0:
            out["fovial"] = fov

        cot = _limpiar_monto_vision(resultado.get("cotrans"))
        if cot > 0:
            out["cotrans"] = cot

    elif tipo_dte == "retenciones":
        nom = _limpio_str(resultado.get("nom_retenido"))
        if nom and len(nom) >= 3:
            out["nom_prov"] = nom.upper()

        nit = _limpio_nit(resultado.get("nit_retenido"))
        if len(nit) == 14 and nit != nit_ctx:
            out["nit_prov"] = nit

        base = _limpiar_monto_vision(resultado.get("monto_sujeto"))
        if base:
            out["base"] = base

        ret = _limpiar_monto_vision(resultado.get("iva_retenido"))
        if ret:
            out["ret"] = ret

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

        base = _limpiar_monto_vision(resultado.get("base_compras"))
        if base:
            out["base"] = base

        ret = _limpiar_monto_vision(resultado.get("retencion_renta"))
        if ret:
            out["ret"] = ret

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
          campos  : dict con campos extraídos (nombres compatibles con cada página).
          alertas : list[str] con alertas de validación fiscal detectadas por Vision.
          audit   : {"confianza": int, "notas": str, "layout": str, "tipo_dte": str}
                    Vacío {} si Vision no pudo ejecutarse.
    """
    global _ultimo_error

    if not vision_disponible():
        _ultimo_error = "API key de Gemini no configurada en secrets.toml."
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
        "layout"   : str(razon.get("layout_detectado", "") if razon else ""),
        "tipo_dte" : tipo_dte,
        "modelo"   : str(audit_raw.get("modelo_utilizado", "gemini-2.5-flash-vision")),
    }

    campos = _mapear_campos(resultado, tipo_dte, nit_ctx)

    # Segunda llamada focalizada si el sello no fue extraído en el primer pase
    if not campos.get("sello_recepcion"):
        sello_extra = _buscar_sello_forzado(pdf_bytes)
        if sello_extra:
            campos["sello_recepcion"] = sello_extra
            log.info("Sello encontrado en segunda llamada focalizada: %s…", sello_extra[:12])

    return campos, alertas, audit
