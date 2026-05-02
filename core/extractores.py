# core/extractores.py
"""
Módulo central de funciones compartidas para todos los extractores DTE.
Incluye: parsers, validadores, filtros, helpers de limpieza.
"""

import re
import json
import streamlit as st
import pandas as pd
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# HELPERS DE LIMPIEZA Y FORMATEO
# ═══════════════════════════════════════════════════════════════

def limpiar_monto(valor_str: str) -> float:
    """
    Convierte un string de monto a float.
    Maneja formatos: '1,234.56', '1234.56', '1.234,56'
    """
    if not valor_str:
        return 0.0
    try:
        limpio = str(valor_str).replace(",", "").replace("$", "").strip()
        return float(limpio)
    except Exception:
        return 0.0


def formatear_uuid(uuid_raw: str) -> str:
    """
    Formatea un UUID a formato estándar con guiones.
    Ejemplo: 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX' -> 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX'
    """
    if not uuid_raw:
        return ""

    limpio = re.sub(r'[^A-F0-9a-f]', '', uuid_raw).upper()

    if len(limpio) == 32:
        return f"{limpio[0:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:32]}"

    return uuid_raw


def extraer_y_formatear_fecha(texto: str) -> str:
    """
    Extrae y formatea fecha desde texto DTE.
    Soporta formatos: DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY
    Retorna: YYYY-MM-DD
    """
    # Formato ISO: 2025-01-15
    m = re.search(r'\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\b', texto)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

    # Formato DD/MM/YYYY
    m = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b', texto)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    return ""


# ═══════════════════════════════════════════════════════════════
# VALIDACIÓN CON GEMINI
# ═══════════════════════════════════════════════════════════════

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
    
    Args:
        texto_pdf: texto crudo del PDF
        datos_extraidos: dict con datos ya extraídos
        tipo_doc: tipo de documento ("CCF", "Factura", "Compra", etc.)
    
    Returns:
        dict con datos validados/corregidos
    """
    try:
        import google.generativeai as genai

        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"_exito": False, "error": "API Key no configurada"}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
Eres un experto en documentos tributarios electrónicos (DTE) de El Salvador.
Analiza el siguiente texto de un {tipo_doc} y extrae/corrige estos campos:

TEXTO DEL DOCUMENTO:
{texto_pdf[:3000]}

DATOS YA EXTRAÍDOS (pueden estar incompletos o incorrectos):
{json.dumps(datos_extraidos, indent=2, ensure_ascii=False)}

INSTRUCCIONES:
1. Identifica y corrige: NIT del receptor/emisor, nombre/razón social, monto gravado, IVA, total.
2. Formato NIT: XXXX-XXXXXX-XXX-X (14 dígitos con guiones)
3. Montos: decimales con punto (1234.56)
4. Si un campo no está en el texto, deja el valor original.

RESPONDE SOLO en JSON con esta estructura exacta:
{{
  "nit": "...",
  "nom": "...",
  "gra": 0.00,
  "iva": 0.00,
  "exe": 0.00,
  "tot": 0.00,
  "gen": "...",
  "confianza_gemini": "alta|media|baja",
  "observaciones": "..."
}}
"""
        respuesta = model.generate_content(prompt)
        texto_resp = respuesta.text.strip()

        # Extraer JSON de la respuesta
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
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
Eres un experto en DTE de El Salvador. Analiza este Comprobante de Retención (DTE-07).

TEXTO:
{texto_pdf[:2000]}

DATOS ACTUALES:
{json.dumps(datos_extraidos, indent=2)}

Extrae y corrige: NIT de la contraparte, nombre, monto sujeto a retención, monto retenido.

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


# ═══════════════════════════════════════════════════════════════
# PARSER JSON DTE (FORMATO MINISTERIO HACIENDA)
# ═══════════════════════════════════════════════════════════════

def parsear_json_dte(datos: dict, modo: str = "ventas") -> dict:
    """
    Parsea un JSON de DTE en formato oficial del Ministerio de Hacienda.

    Args:
        datos: dict con el JSON cargado
        modo: "ventas" | "compras" | "retenciones" | "sujetos_excluidos"

    Returns:
        dict normalizado con los campos estándar
    """
    try:
        identificacion = datos.get("identificacion", {})
        emisor = datos.get("emisor", {})
        receptor = datos.get("receptor", {})
        resumen = datos.get("resumen", {})
        cuerpo = datos.get("cuerpo", [])

        tipo = str(identificacion.get("tipoDte", "01")).zfill(2)
        ctrl = identificacion.get("numeroControl", "")
        gen = formatear_uuid(identificacion.get("codigoGeneracion", ""))
        sello = datos.get("selloRecibido", "")
        fecha_raw = identificacion.get("fecEmi", "")
        fecha = extraer_y_formatear_fecha(fecha_raw) if fecha_raw else ""

        # ── MONTOS ──
        monto_no_sujeto = float(resumen.get("totalNoSuj", 0) or 0)
        monto_exento = float(resumen.get("totalExenta", 0) or 0)
        monto_gravado = float(resumen.get("totalGravada", 0) or 0)
        monto_iva = float(resumen.get("totalIva", 0) or 0)
        monto_total = float(resumen.get("montoTotalOperacion", resumen.get("totalPagar", 0)) or 0)
        monto_retencion = float(resumen.get("totalIvaRetenido", resumen.get("reteRenta", 0)) or 0)
        monto_exportacion = float(resumen.get("totalVentas", 0) or 0)

        if modo == "ventas":
            return {
                "fecha": fecha,
                "nit": _extraer_id_receptor(receptor),
                "nom": receptor.get("nombre", receptor.get("nombreComercial", "")),
                "tipo": tipo,
                "ctrl": ctrl,
                "gen": gen,
                "sello": sello,
                "nos": monto_no_sujeto,
                "exe": monto_exento,
                "gra": monto_gravado,
                "iva": monto_iva,
                "exp_serv": monto_exportacion,
                "tot": monto_total,
                "t_ing": "3",
                "motor": "JSON",
                "iva_calculado": False,
                "confianza_nit": "alta",
                "confianza_rs": "alta",
                "fuente": "JSON",
                "archivo": ""
            }

        elif modo == "compras":
            return {
                "fecha": fecha,
                "nit_prov": _extraer_id_emisor(emisor),
                "nom_prov": emisor.get("nombre", emisor.get("nombreComercial", "")),
                "dui_prov": emisor.get("nit", ""),
                "tipo": tipo,
                "ctrl": ctrl,
                "gen": gen,
                "sello": sello,
                "exe": monto_exento,
                "gra": monto_gravado,
                "iva": monto_iva,
                "ret": monto_retencion,
                "perc": 0.0,
                "tot": monto_total,
                "motor": "JSON",
                "iva_calc": False,
                "confianza_nit": "alta",
                "confianza_rs": "alta",
                "fuente": "JSON",
                "archivo": ""
            }

        elif modo == "retenciones":
            return {
                "fecha": fecha,
                "nit_contraparte": _extraer_id_receptor(receptor),
                "nom_contraparte": receptor.get("nombre", ""),
                "tipo": tipo,
                "ctrl": ctrl,
                "gen": gen,
                "sello": sello,
                "monto_sujeto": monto_gravado or monto_total,
                "monto_retenido": monto_iva or monto_retencion,
                "ret_calc": False,
                "motor": "JSON",
                "confianza_nit": "alta",
                "confianza_rs": "alta",
                "fuente": "JSON",
                "archivo": ""
            }

        elif modo == "sujetos_excluidos":
            nit_doc = _extraer_id_receptor(receptor)
            nit = nit_doc if len(re.sub(r'[^0-9]', '', nit_doc)) == 14 else ""
            dui = nit_doc if len(re.sub(r'[^0-9]', '', nit_doc)) == 9 else ""

            return {
                "fecha": fecha,
                "nombre": receptor.get("nombre", ""),
                "documento": nit_doc,
                "nit": nit,
                "dui": dui,
                "tipo": tipo,
                "ctrl": ctrl,
                "gen": gen,
                "sello": sello,
                "monto": monto_total,
                "retencion": monto_retencion,
                "retencion_calculada": False,
                "motor": "JSON",
                "fuente": "JSON",
                "archivo": ""
            }

        return {"error": f"Modo '{modo}' no reconocido"}

    except Exception as e:
        return {"error": f"Error al parsear JSON: {str(e)}"}


def _extraer_id_emisor(emisor: dict) -> str:
    """Extrae NIT o DUI del emisor."""
    nit = emisor.get("nit", emisor.get("numDocumento", ""))
    return str(nit).strip() if nit else ""


def _extraer_id_receptor(receptor: dict) -> str:
    """Extrae NIT o DUI del receptor."""
    nit = receptor.get("nit", receptor.get("numDocumento", ""))
    return str(nit).strip() if nit else ""


# ═══════════════════════════════════════════════════════════════
# PANEL DE FILTROS REUTILIZABLE
# ═══════════════════════════════════════════════════════════════

def render_panel_filtros(df: pd.DataFrame, key_prefix: str = "filtro") -> pd.DataFrame:
    """
    Renderiza un panel de filtros interactivos para un DataFrame de DTE.

    Args:
        df: DataFrame con los datos extraídos
        key_prefix: prefijo único para las keys de los widgets

    Returns:
        DataFrame filtrado
    """
    if df.empty:
        return df

    with st.expander("🔍 Filtros de Búsqueda", expanded=False):
        col1, col2, col3 = st.columns(3)

        df_filtrado = df.copy()

        # Filtro por tipo DTE
        if "tipo" in df.columns:
            with col1:
                tipos_disponibles = ["Todos"] + sorted(df["tipo"].dropna().unique().tolist())
                tipo_sel = st.selectbox(
                    "Tipo DTE",
                    tipos_disponibles,
                    key=f"{key_prefix}_tipo"
                )
                if tipo_sel != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["tipo"] == tipo_sel]

        # Filtro por fecha
        if "fecha" in df.columns:
            with col2:
                fechas_validas = df["fecha"].dropna()
                fechas_validas = fechas_validas[fechas_validas != ""]

                if not fechas_validas.empty:
                    fecha_min_str = fechas_validas.min()
                    fecha_max_str = fechas_validas.max()

                    try:
                        fecha_min = datetime.strptime(fecha_min_str, "%Y-%m-%d").date()
                        fecha_max = datetime.strptime(fecha_max_str, "%Y-%m-%d").date()

                        fecha_desde = st.date_input(
                            "Desde",
                            value=fecha_min,
                            key=f"{key_prefix}_fecha_desde"
                        )
                        fecha_hasta = st.date_input(
                            "Hasta",
                            value=fecha_max,
                            key=f"{key_prefix}_fecha_hasta"
                        )

                        def _en_rango(f):
                            try:
                                fd = datetime.strptime(str(f), "%Y-%m-%d").date()
                                return fecha_desde <= fd <= fecha_hasta
                            except Exception:
                                return True

                        df_filtrado = df_filtrado[df_filtrado["fecha"].apply(_en_rango)]
                    except Exception:
                        pass

        # Filtro por motor
        if "motor" in df.columns:
            with col3:
                motores_disponibles = ["Todos"] + sorted(df["motor"].dropna().unique().tolist())
                motor_sel = st.selectbox(
                    "Motor",
                    motores_disponibles,
                    key=f"{key_prefix}_motor"
                )
                if motor_sel != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["motor"] == motor_sel]

        # Filtro por fuente
        if "fuente" in df.columns:
            col4, col5 = st.columns(2)
            with col4:
                fuentes_disponibles = ["Todos"] + sorted(df["fuente"].dropna().unique().tolist())
                fuente_sel = st.selectbox(
                    "Fuente",
                    fuentes_disponibles,
                    key=f"{key_prefix}_fuente"
                )
                if fuente_sel != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["fuente"] == fuente_sel]

        # Búsqueda por texto
        with st.container():
            busqueda = st.text_input(
                "Buscar por nombre o NIT",
                placeholder="Ej: 0614-123456...",
                key=f"{key_prefix}_busqueda"
            )
            if busqueda:
                campos_texto = ["nom", "nit", "nom_prov", "nit_prov", "nombre", "nom_contraparte", "nit_contraparte"]
                campos_validos = [c for c in campos_texto if c in df_filtrado.columns]

                if campos_validos:
                    mascara = df_filtrado[campos_validos].apply(
                        lambda col: col.astype(str).str.contains(busqueda, case=False, na=False)
                    ).any(axis=1)
                    df_filtrado = df_filtrado[mascara]

    return df_filtrado
