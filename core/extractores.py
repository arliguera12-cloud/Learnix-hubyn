# core/extractores.py
"""
Funciones de extracción y limpieza de datos DTE
"""

import re
import json
from datetime import datetime
from .constantes import (
    PATRON_FECHA_ISO,
    PATRON_FECHA_TRADICIONAL,
    PATRON_UUID,
)


# ═══════════════════════════════════════════════════════════════
# HELPERS DE LIMPIEZA Y FORMATEO
# ═══════════════════════════════════════════════════════════════

def limpiar_monto(valor_str: str) -> float:
    """
    Convierte un string de monto a float.
    
    Args:
        valor_str: '1,234.56' o '1234.56' o '1.234,56'
    
    Returns:
        float: Monto limpio (ej: 1234.56)
    """
    if not valor_str:
        return 0.0
    
    try:
        limpio = str(valor_str).replace(",", "").replace("$", "").strip()
        return float(limpio)
    except (ValueError, AttributeError):
        return 0.0


def formatear_uuid(uuid_raw: str) -> str:
    """
    Formatea un UUID a formato estándar.
    
    Args:
        uuid_raw: 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    
    Returns:
        str: 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX'
    """
    if not uuid_raw:
        return ""

    # Extraer solo caracteres hexadecimales
    limpio = re.sub(r'[^A-F0-9a-f]', '', uuid_raw).upper()

    # Si tiene 32 caracteres, agregar guiones
    if len(limpio) == 32:
        return f"{limpio[0:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:32]}"

    return uuid_raw


def extraer_y_formatear_fecha(texto: str) -> str:
    """
    Extrae y formatea fecha desde texto.
    
    Args:
        texto: Texto con fecha (DD/MM/YYYY, YYYY-MM-DD, etc.)
    
    Returns:
        str: Fecha en formato YYYY-MM-DD
    """
    if not texto:
        return ""

    # Intentar ISO primero (2025-01-15)
    m = re.search(PATRON_FECHA_ISO, texto)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

    # Intentar tradicional (15/01/2025)
    m = re.search(PATRON_FECHA_TRADICIONAL, texto)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    return ""


# ═══════════════════════════════════════════════════════════════
# PARSER JSON DTE
# ═══════════════════════════════════════════════════════════════

def parsear_json_dte(datos: dict, modo: str = "ventas") -> dict:
    """
    Parsea un JSON de DTE en formato oficial.
    
    Args:
        datos: dict con el JSON cargado
        modo: "ventas" | "compras" | "retenciones" | "sujetos_excluidos"
    
    Returns:
        dict normalizado
    """
    try:
        identificacion = datos.get("identificacion", {})
        emisor = datos.get("emisor", {})
        receptor = datos.get("receptor", {})
        resumen = datos.get("resumen", {})

        # Extraer campos comunes
        tipo = str(identificacion.get("tipoDte", "01")).zfill(2)
        ctrl = identificacion.get("numeroControl", "")
        gen = formatear_uuid(identificacion.get("codigoGeneracion", ""))
        sello = datos.get("selloRecibido", "")
        fecha_raw = identificacion.get("fecEmi", "")
        fecha = extraer_y_formatear_fecha(fecha_raw) if fecha_raw else ""

        # Extraer montos
        monto_no_sujeto = float(resumen.get("totalNoSuj", 0) or 0)
        monto_exento = float(resumen.get("totalExenta", 0) or 0)
        monto_gravado = float(resumen.get("totalGravada", 0) or 0)
        monto_iva = float(resumen.get("totalIva", 0) or 0)
        monto_total = float(resumen.get("montoTotalOperacion", resumen.get("totalPagar", 0)) or 0)
        monto_retencion = float(resumen.get("totalIvaRetenido", resumen.get("reteRenta", 0)) or 0)

        # ── PARSEO POR TIPO ──
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
                "exp_serv": 0.0,
                "tot": monto_total,
                "t_ing": "3",
                "motor": "JSON",
                "iva_calculado": False,
                "confianza_nit": "alta",
                "confianza_rs": "alta",
                "fuente": "JSON",
                "archivo": "",
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
                "archivo": "",
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
                "archivo": "",
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
                "archivo": "",
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
