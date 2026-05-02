"""
Parser de JSON DTE — Ministerio de Hacienda El Salvador.

Convierte el formato oficial de DTE (JSON) al formato interno del sistema.
Compatible con: DTE-01, DTE-03, DTE-05, DTE-06, DTE-07, DTE-11, DTE-14

Estructura esperada del JSON oficial:
{
  "dteJson": {
    "encabezado": {
      "identificacion": { ... },
      "emisor": { ... },
      "receptor": { ... },
      "resumen": { ... }
    },
    "cuerpo": [ ... ]
  },
  "selloRecibido": "...",
  "codigoGeneracion": "..."
}
"""

import re
import json


# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

TIPOS_VENTAS    = {"01", "03", "05", "06", "11"}
TIPOS_COMPRAS   = {"03", "05", "06"}
TIPOS_RETENCION = {"07"}
TIPOS_SE        = {"14"}


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _safe_float(valor, default: float = 0.0) -> float:
    try:
        return round(float(valor or 0), 2)
    except (TypeError, ValueError):
        return default


def _safe_str(valor, default: str = "") -> str:
    if valor is None:
        return default
    return str(valor).strip()


def _limpiar_nit(valor) -> str:
    return re.sub(r'[^0-9]', '', str(valor or ""))


def _formatear_fecha(fecha_raw: str) -> str:
    """Convierte YYYY-MM-DD → DD/MM/YYYY."""
    partes = str(fecha_raw).split("-")
    if len(partes) == 3:
        return f"{partes[2].zfill(2)}/{partes[1].zfill(2)}/{partes[0]}"
    return str(fecha_raw)


def _detectar_tipo_doc(nit_limpio: str) -> str:
    """Detecta si un identificador es NIT (14) o DUI (9)."""
    largo = len(nit_limpio)
    if largo == 14:
        return "1"  # NIT
    if largo == 9:
        return "2"  # DUI
    return "3"  # Otro


# ═══════════════════════════════════════════════════════════════
# EXTRACTOR DE CAMPOS COMUNES
# ═══════════════════════════════════════════════════════════════

def _extraer_campos_base(datos_json: dict) -> dict:
    """Extrae campos comunes a todos los tipos de DTE."""
    dte_json = datos_json.get("dteJson", datos_json)
    enc      = dte_json.get("encabezado", {})
    ident    = enc.get("identificacion", {})

    tipo_raw = str(ident.get("tipoDte", "01"))
    tipo     = tipo_raw.zfill(2)

    fecha_raw = ident.get("fecEmi", "")
    fecha     = _formatear_fecha(fecha_raw) if fecha_raw else ""

    gen   = _safe_str(
        ident.get("codigoGeneracion")
        or datos_json.get("codigoGeneracion")
    )
    ctrl  = _safe_str(ident.get("numeroControl"))
    sello = _safe_str(datos_json.get("selloRecibido"))

    return {
        "tipo":   tipo,
        "fecha":  fecha,
        "gen":    gen.upper(),
        "ctrl":   ctrl,
        "sello":  sello,
        "fuente": "JSON",
        "motor":  "JSON-Parser",
    }


# ═══════════════════════════════════════════════════════════════
# PARSERS POR TIPO
# ═══════════════════════════════════════════════════════════════

def _parsear_ventas(datos_json: dict, base: dict) -> dict:
    """Parser para DTE de Ventas (01, 03, 05, 06, 11)."""
    dte_json  = datos_json.get("dteJson", datos_json)
    enc       = dte_json.get("encabezado", {})
    receptor  = enc.get("receptor", {})
    resumen   = enc.get("resumen", {})

    nit = _limpiar_nit(
        receptor.get("nit")
        or receptor.get("numDocumento", "")
    )

    res = dict(base)
    res.update({
        "nit":          nit,
        "nom":          _safe_str(receptor.get("nombre")).upper(),
        "nos":          _safe_float(resumen.get("totalNoSuj")),
        "exe":          _safe_float(resumen.get("totalExenta")),
        "gra":          _safe_float(resumen.get("totalGravada")),
        "iva":          _safe_float(resumen.get("totalIva")),
        "tot":          _safe_float(resumen.get("totalPagar")),
        "exp_serv":     _safe_float(resumen.get("totalExportacion")),
        "t_ing":        "3",
        "iva_calculado": False,
    })
    return res


def _parsear_compras(datos_json: dict, base: dict) -> dict:
    """Parser para DTE de Compras (03, 05, 06)."""
    dte_json = datos_json.get("dteJson", datos_json)
    enc      = dte_json.get("encabezado", {})
    emisor   = enc.get("emisor", {})
    resumen  = enc.get("resumen", {})

    nit_raw = _limpiar_nit(emisor.get("nit") or emisor.get("numDocumento", ""))
    dui_raw = _limpiar_nit(emisor.get("numDocumento", ""))
    dui     = dui_raw if len(dui_raw) == 9 else ""

    res = dict(base)
    res.update({
        "nit_prov":      nit_raw,
        "dui_prov":      dui,
        "nom_prov":      _safe_str(emisor.get("nombre")).upper(),
        "exe":           _safe_float(resumen.get("totalExenta")),
        "gra":           _safe_float(resumen.get("totalGravada")),
        "iva":           _safe_float(resumen.get("totalIva")),
        "ret":           _safe_float(resumen.get("reteRenta")),
        "tot":           _safe_float(resumen.get("totalPagar")),
        "perc":          0.0,
        "iva_calc":      False,
        "es_nuevo":      True,
        "nit_nuevo":     nit_raw,
        "estado":        "OK",
        "confianza_nit": "alta",
        "confianza_rs":  "alta",
    })
    return res


def _parsear_retenciones(datos_json: dict, base: dict) -> dict:
    """Parser para Comprobante de Retencion DTE-07."""
    dte_json = datos_json.get("dteJson", datos_json)
    enc      = dte_json.get("encabezado", {})
    emisor   = enc.get("emisor", {})
    resumen  = enc.get("resumen", {})
    cuerpo   = dte_json.get("cuerpo", [{}])
    item0    = cuerpo[0] if cuerpo else {}

    monto_sujeto   = _safe_float(
        item0.get("montoSujetoGrav")
        or resumen.get("totalSujetoRetencion")
        or resumen.get("montoSujeto")
    )
    monto_retenido = _safe_float(
        resumen.get("ivaRete1")
        or resumen.get("montoRetenido")
        or item0.get("ivaRetenido")
    )

    # Calcular si falta
    ret_calc = False
    if monto_sujeto > 0 and monto_retenido == 0.0:
        monto_retenido = round(monto_sujeto * 0.01, 2)
        ret_calc = True
    elif monto_retenido > 0 and monto_sujeto == 0.0:
        monto_sujeto = round(monto_retenido / 0.01, 2)
        ret_calc = True

    nit_contra = _limpiar_nit(emisor.get("nit") or emisor.get("numDocumento", ""))

    res = dict(base)
    res.update({
        "nit_contraparte":  nit_contra,
        "nom_contraparte":  _safe_str(emisor.get("nombre")).upper(),
        "monto_sujeto":     monto_sujeto,
        "monto_retenido":   monto_retenido,
        "es_nuevo":         True,
        "ret_calc":         ret_calc,
        "estado":           "OK",
    })
    return res


def _parsear_sujetos_excluidos(datos_json: dict, base: dict) -> dict:
    """Parser para Comprobante de Sujeto Excluido DTE-14."""
    dte_json = datos_json.get("dteJson", datos_json)
    enc      = dte_json.get("encabezado", {})
    emisor   = enc.get("emisor", {})
    resumen  = enc.get("resumen", {})

    doc_raw = _limpiar_nit(emisor.get("numDocumento", "") or emisor.get("nit", ""))
    es_nit  = len(doc_raw) == 14
    es_dui  = len(doc_raw) == 9
    tipo_doc = "1" if es_nit else ("2" if es_dui else "3")

    monto     = _safe_float(resumen.get("totalPagar"))
    retencion = _safe_float(resumen.get("reteRenta"))
    ret_calc  = False
    if retencion == 0.0 and monto > 0:
        retencion = round(monto * 0.10, 2)
        ret_calc  = True

    res = dict(base)
    res.update({
        "nombre":              _safe_str(emisor.get("nombre")).upper(),
        "documento":           doc_raw,
        "nit":                 doc_raw if es_nit else "",
        "dui":                 doc_raw if es_dui else "",
        "tipo_doc_compras":    tipo_doc,
        "monto":               monto,
        "retencion":           retencion,
        "retencion_calculada": ret_calc,
        "codigo":              base.get("gen", ""),
        "sello_doc":           base.get("sello", ""),
        "valido":              True,
        "error":               "",
    })
    return res


# ═══════════════════════════════════════════════════════════════
# FUNCION PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def parsear_json_dte(datos_json: dict, tipo_extractor: str) -> dict:
    """
    Parsea un JSON oficial del Ministerio de Hacienda de El Salvador
    y lo convierte al formato interno del sistema.

    Args:
        datos_json:     dict con el contenido del archivo JSON
        tipo_extractor: 'ventas' | 'compras' | 'retenciones' | 'sujetos_excluidos'

    Returns:
        dict con campos normalizados al formato interno, o {'error': ...}
    """
    try:
        base = _extraer_campos_base(datos_json)
        tipo = base.get("tipo", "01")

        # Validar que el tipo DTE corresponda al extractor
        if tipo_extractor == "ventas" and tipo not in TIPOS_VENTAS:
            return {
                "error_tipo": f"DTE-{tipo} no es un documento de Ventas.",
                "fuente": "JSON"
            }
        if tipo_extractor == "compras" and tipo not in TIPOS_COMPRAS:
            return {
                "error_tipo": f"DTE-{tipo} no es un documento de Compras (solo 03, 05, 06).",
                "fuente": "JSON"
            }
        if tipo_extractor == "retenciones" and tipo not in TIPOS_RETENCION:
            return {
                "error_tipo": f"DTE-{tipo} no es un Comprobante de Retencion (solo 07).",
                "fuente": "JSON"
            }
        if tipo_extractor == "sujetos_excluidos" and tipo not in TIPOS_SE:
            return {
                "error_tipo": f"DTE-{tipo} no es un Comprobante de Sujeto Excluido (solo 14).",
                "fuente": "JSON"
            }

        # Parsear segun tipo
        if tipo_extractor == "ventas":
            return _parsear_ventas(datos_json, base)
        elif tipo_extractor == "compras":
            return _parsear_compras(datos_json, base)
        elif tipo_extractor == "retenciones":
            return _parsear_retenciones(datos_json, base)
        elif tipo_extractor == "sujetos_excluidos":
            return _parsear_sujetos_excluidos(datos_json, base)
        else:
            return {"error": f"tipo_extractor desconocido: {tipo_extractor}", "fuente": "JSON"}

    except Exception as e:
        return {"error": f"Error al parsear JSON: {str(e)}", "fuente": "JSON"}


def parsear_multiples_json(
    archivos_json: list,
    tipo_extractor: str,
    archivos_procesados: set
) -> tuple:
    """
    Procesa una lista de archivos JSON subidos via Streamlit.

    Args:
        archivos_json:       lista de UploadedFile
        tipo_extractor:      tipo de extractor
        archivos_procesados: set de nombres ya procesados

    Returns:
        (extracted, duplicados, errores, rechazados_tipo)
    """
    extracted       = []
    duplicados      = []
    errores         = []
    rechazados_tipo = []

    for f in archivos_json:
        if f.name in archivos_procesados:
            continue
        try:
            datos = json.load(f)
            res   = parsear_json_dte(datos, tipo_extractor)

            if "error_tipo" in res:
                rechazados_tipo.append(f"{f.name} — {res['error_tipo']}")
            elif "error" in res:
                errores.append(f"{f.name} — {res['error']}")
            else:
                res["archivo"] = f.name
                extracted.append(res)

        except json.JSONDecodeError:
            errores.append(f"{f.name} — JSON invalido o malformado")
        except Exception as e:
            errores.append(f"{f.name} — {str(e)}")

    return extracted, duplicados, errores, rechazados_tipo
