"""
Learnix Hub — Procesador paralelo de lotes de DTE.

ThreadPoolExecutor con max_workers=10.

Mejoras v2.0:
  - Deduplicación: filtra PDFs ya procesados en la sesión (por SHA-256).
  - Caché de extracción: reutiliza resultados anteriores para el mismo archivo.

Uso típico en una página:
    from utils.concurrent_processor import leer_y_procesar_lote, filtrar_duplicados

    nombres_bytes = leer_archivos_uploaded(nuevos)
    nombres_bytes = filtrar_duplicados(nombres_bytes)   # elimina repetidos
    resultados    = leer_y_procesar_lote(
        nombres_bytes,
        fn_extraccion,
        progreso_cb=lambda c, t, n: (bar.progress(c/t), txt.caption(f"⏳ {c}/{t}")),
    )
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from utils.dte_json import cargar_json

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

# Configurable: usa hasta la mitad de CPUs, máximo 10
import os as _os
MAX_WORKERS: int = min(_os.cpu_count() or 4, 10)

_CACHE_MAX_SIZE   = 200
_CACHE_EVICT_SIZE = 50


# ─── Deduplicación y caché por sesión ────────────────────────────────────────

def _pdf_hash(pdf_bytes: bytes) -> str:
    """SHA-256 hex del contenido del PDF."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def filtrar_duplicados(
    nombres_y_bytes: list[tuple[str, bytes]],
    session_key: str = "_pdfs_procesados",
) -> list[tuple[str, bytes]]:
    """
    Filtra archivos cuyos bytes ya fueron procesados en esta sesión (mismo hash SHA-256).

    IMPORTANTE: llamar SIEMPRE desde el hilo principal de Streamlit, ANTES de
    pasar la lista a leer_y_procesar_lote(). st.session_state no es accesible
    desde threads secundarios del ThreadPoolExecutor.

    Args:
        nombres_y_bytes: lista de (nombre, bytes) a filtrar.
        session_key:     clave en st.session_state donde se acumula el set de hashes.

    Returns:
        Sublista con solo los archivos nuevos (hashes no vistos en la sesión actual).
    """
    # Leer y escribir session_state en el hilo principal antes de cualquier thread
    vistos: set = set()
    try:
        if session_key not in st.session_state:
            st.session_state[session_key] = set()
        vistos = st.session_state[session_key]
    except Exception:
        pass  # fuera de contexto Streamlit — dedup desactivado silenciosamente

    nuevos = []
    for fname, fb in nombres_y_bytes:
        if not fb:
            continue
        h = _pdf_hash(fb)
        if h in vistos:
            log.info("Duplicado omitido: %s (%s…)", fname, h[:8])
        else:
            vistos.add(h)
            nuevos.append((fname, fb))

    try:
        st.session_state[session_key] = vistos
    except Exception:
        pass

    omitidos = len(nombres_y_bytes) - len(nuevos)
    if omitidos:
        log.info("filtrar_duplicados: %d archivo(s) omitido(s) por duplicado", omitidos)

    return nuevos


def con_cache_extraccion(
    fn_extraccion: Callable[[bytes], dict],
    tipo_dte: str = "",
    session_key: str = "_cache_extracciones",
) -> Callable[[bytes], dict]:
    """
    Envuelve fn_extraccion con un caché thread-safe.

    El cache se lee/escribe en st.session_state SOLO desde el hilo principal:
    se carga antes de crear el ThreadPoolExecutor y se persiste después.
    Dentro del worker solo se usa un dict ordinario (thread-safe read-only lookup).

    Uso:
        fn = con_cache_extraccion(mi_fn_extraccion, tipo_dte="compras")
        resultados = leer_y_procesar_lote(nombres_bytes, fn, ...)
    """
    # Cargar cache desde session_state en el hilo principal (antes del pool)
    cache: dict = {}
    try:
        if session_key not in st.session_state:
            st.session_state[session_key] = {}
        cache = dict(st.session_state[session_key])  # copia local thread-safe
    except Exception:
        pass

    _cache_lock = threading.Lock()

    def _wrapper(pdf_bytes: bytes) -> dict:
        h = _pdf_hash(pdf_bytes)
        cache_key = f"{h}_{tipo_dte}"

        with _cache_lock:
            if cache_key in cache:
                log.info("Caché hit: %s…_%s", h[:8], tipo_dte)
                return dict(cache[cache_key])

        resultado = fn_extraccion(pdf_bytes)

        with _cache_lock:
            # LRU: si el cache está lleno, eliminar los más antiguos
            if len(cache) >= _CACHE_MAX_SIZE:
                for k in list(cache.keys())[:_CACHE_EVICT_SIZE]:
                    del cache[k]
            cache[cache_key] = resultado

        # Persistir de vuelta a session_state (solo es efectivo si llamado desde hilo principal;
        # desde workers es no-op silencioso, la persistencia ocurre en la siguiente carga)
        try:
            st.session_state[session_key] = dict(cache)
        except Exception:
            pass

        return resultado

    return _wrapper


def _safe_float(value) -> float:
    """Convert any value to float, returning 0.0 on any failure."""
    try:
        if value is None:
            return 0.0
        return float(str(value).replace(",", ".").strip() or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def leer_archivos_uploaded(archivos: list) -> list[tuple[str, bytes]]:
    """
    Lee los bytes de una lista de UploadedFile de Streamlit en el hilo principal.
    UploadedFile no es thread-safe; hay que leer antes de pasar al pool.

    Returns:
        Lista de (nombre_archivo, bytes_pdf).
    """
    result = []
    for f in archivos:
        try:
            fb = f.read()
            result.append((f.name, fb))
        except Exception as exc:
            log.error("No se pudo leer %s: %s", f.name, exc)
            result.append((f.name, b""))
    return result


def leer_y_procesar_lote(
    nombres_y_bytes: list[tuple[str, bytes]],
    fn_extraccion: Callable[[bytes], dict],
    max_workers: int = MAX_WORKERS,
    progreso_cb: Callable[[int, int, str], None] | None = None,
) -> list[tuple[str, bytes, dict]]:
    """
    Procesa una lista de PDFs en paralelo con ThreadPoolExecutor.

    Args:
        nombres_y_bytes : lista de (nombre_archivo, bytes_pdf) ya leídos.
        fn_extraccion   : función pura (bytes_pdf) -> dict resultado.
                          Usar functools.partial para fijar argumentos extra.
        max_workers     : hilos simultáneos (default MAX_WORKERS=10).
        progreso_cb     : callback(completados, total, nombre_archivo) para
                          actualizar la barra de progreso de Streamlit.
                          Se invoca desde el hilo principal (as_completed loop).

    Returns:
        Lista de (nombre_archivo, bytes_pdf, resultado_dict) en orden de llegada.
        Si una extracción lanza excepción el resultado es {"error_fatal": str(exc)}.
    """
    if not nombres_y_bytes:
        return []

    total   = len(nombres_y_bytes)
    results : list[tuple[str, bytes, dict]] = []

    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as pool:
        future_map: dict = {
            pool.submit(fn_extraccion, fb): (fname, fb)
            for fname, fb in nombres_y_bytes
        }

        completados = 0
        for future in as_completed(future_map):
            fname, fb = future_map[future]
            completados += 1
            try:
                res = future.result()
            except Exception as exc:
                log.error("Error procesando %s: %s", fname, exc, exc_info=True)
                res = {"error_fatal": str(exc)}

            results.append((fname, fb, res))

            if progreso_cb:
                try:
                    progreso_cb(completados, total, fname)
                except Exception:
                    pass

    return results


def _extraer_sello_envoltorio(data: dict, dte: dict, ident: dict) -> str:
    """Sello de recepción: puede estar en varios niveles del envoltorio de transmisión."""
    def _ss(v): return re.sub(r"\s+", "", str(v or "")).strip()
    return (
        _ss(data.get("selloRecibido"))
        or _ss(dte.get("selloRecibido"))
        or _ss((dte.get("respuestaHacienda") or {}).get("selloRecibido"))
        or _ss((dte.get("responseMH") or {}).get("selloRecibido"))
        or _ss(ident.get("SelloRecibido"))
        or _ss(ident.get("selloRecibido"))
    )


def _fecha_ddmmyyyy(fec_emi: str) -> str:
    """YYYY-MM-DD → DD/MM/YYYY. Si no matchea el formato esperado, retorna tal cual."""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", fec_emi):
        y, m, d = fec_emi.split("-")
        return f"{d}/{m}/{y}"
    return fec_emi


def _tributos_iva_fovial_cotrans(resumen: "DTEResumen") -> tuple[float, float, float]:
    """Extrae IVA/FOVIAL/COTRANS de la lista de tributos tipada; fallback a totalIva."""
    iva_val = fovial = cotrans = 0.0
    for t in resumen.tributos:
        cod  = t.codigo
        desc = t.descripcion.upper()
        val  = t.valor
        if cod == "20" or "IVA" in desc or "IMPUESTO AL VALOR AGREGADO" in desc:
            iva_val = val
        elif cod == "C3" or "FOVIAL" in desc:
            fovial = val
        elif cod == "59" or "COTRANS" in desc:
            cotrans = val
    if not iva_val:
        iva_val = resumen.totalIva
    return iva_val, fovial, cotrans


def _validar_dte_documento(dte_raw: dict) -> "DTEDocumento | str":
    """Valida dte_raw contra el schema de Hacienda. Retorna el modelo o un mensaje de error."""
    from pydantic import ValidationError
    from schemas.dte_hacienda import DTEDocumento

    try:
        return DTEDocumento.model_validate(dte_raw)
    except ValidationError as exc:
        return f"JSON no cumple el schema de Hacienda: {exc.errors()[0]['msg']} (campo: {'.'.join(str(p) for p in exc.errors()[0]['loc'])})"


def procesar_json_nativo_ventas(file_bytes: bytes) -> dict:
    """
    Parsea un JSON firmado por Hacienda (lado ventas) contra el schema oficial
    (backend/schemas/dte_hacienda.py) y retorna el mismo shape de campos que
    extraer_venta_nativo_pro, con confianza=100 (es el documento oficial, sin
    ambigüedad de OCR/regex).
    """
    try:
        data = cargar_json(file_bytes)
    except Exception as exc:
        return {"error_fatal": f"JSON inválido: {exc}"}

    # Los datos del DTE vienen dentro de dteJson; fallback a la raíz por compatibilidad
    dte_raw = data.get("dteJson") or data

    dte = _validar_dte_documento(dte_raw)
    if isinstance(dte, str):
        return {"error_fatal": dte}

    ident    = dte.identificacion
    receptor = dte.receptor
    resumen  = dte.resumen

    sello = _extraer_sello_envoltorio(data, dte_raw, dte_raw.get("identificacion") or {})
    fecha = _fecha_ddmmyyyy(ident.fecEmi)

    _raw_r = (receptor.nit or receptor.dui or receptor.numDocumento).replace("-", "").strip()
    nit_r = re.sub(r"[^0-9]", "", _raw_r)
    dui_r = re.sub(r"[^0-9]", "", receptor.numDocumento.replace("-", "").strip())

    _raw_emit_v = (dte.emisor.nit or dte.emisor.dui or dte.emisor.numDocumento).replace("-", "").strip()
    nit_emisor_v = re.sub(r"[^0-9]", "", _raw_emit_v)

    iva_val, fovial, cotrans = _tributos_iva_fovial_cotrans(resumen)

    gen_uuid = ident.codigoGeneracion
    num_ctrl = ident.numeroControl

    resultado = {
        "tipo"           : ident.tipoDte,
        "fecha"          : fecha,
        "num_control"    : num_ctrl,
        "num_control_raw": num_ctrl,
        "gen"            : gen_uuid,
        "gen_sin_guiones": gen_uuid.replace("-", ""),
        "sello"          : sello,
        "_nit_emisor"    : nit_emisor_v,
        "nom_cli"        : (receptor.nombre or "CONSUMIDOR FINAL").upper().strip(),
        "nit_cli"        : nit_r if len(nit_r) == 14 else "",
        "dui_cli"        : dui_r if len(dui_r) == 9 else "",
        "gravadas"       : round(resumen.totalGravada, 2),
        # FOVIAL/COTRANS (tributos C3/59) están en totalPagar pero no en
        # totalExenta/totalNoSuj — sin sumarlos, validar_montos_ventas marca
        # "Total no cuadra" en toda venta de combustible (mismo bug
        # encontrado y corregido en el path PDF con documentos reales).
        "exentas"        : round(resumen.totalExenta + fovial + cotrans, 2),
        "no_sujetas"     : round(resumen.totalNoSuj, 2),
        "debito"         : round(iva_val, 2),
        "terceros"       : 0.0,
        "deb_terc"       : 0.0,
        "total"          : round(resumen.totalPagar, 2),
        "fovial"         : round(fovial, 2),
        "cotrans"        : round(cotrans, 2),
        "_origen"        : "json_nativo",
        "fuentes"        : {
            k: "json_oficial" for k in
            ("fecha", "num_control", "sello", "nit_cli", "nom_cli", "gravadas", "debito", "exentas", "total")
        },
    }

    from utils.qa_utils import validar_montos_ventas
    alertas = validar_montos_ventas(resultado)
    if alertas:
        resultado["estado"] = "REVISAR"
        resultado["confianza"] = 60
        resultado["detalle_confianza"] = "; ".join(alertas)
    else:
        resultado["estado"] = "OK"
        resultado["confianza"] = 100
        resultado["detalle_confianza"] = "JSON oficial de Hacienda — schema validado, montos cuadran."
    resultado["campos_faltantes"] = []
    resultado["validacion_montos"] = "error" if alertas else "ok"
    return resultado


def procesar_json_nativo_compras(file_bytes: bytes) -> dict:
    """
    Parsea un JSON firmado por Hacienda (lado compras) contra el schema oficial
    y retorna el mismo shape de campos que extraer_compra_nativo_pro, con
    confianza=100 (documento oficial, sin ambigüedad).
    """
    from utils.constants import TIPOS_VALIDOS_COMPRAS

    try:
        data = cargar_json(file_bytes)
    except Exception as exc:
        return {"error_fatal": f"JSON inválido: {exc}"}

    dte_raw = data.get("dteJson") or data

    dte = _validar_dte_documento(dte_raw)
    if isinstance(dte, str):
        return {"error_fatal": dte}

    ident   = dte.identificacion
    resumen = dte.resumen
    tipo_dte = ident.tipoDte

    if tipo_dte not in TIPOS_VALIDOS_COMPRAS:
        return {
            "error_tipo": (
                f"DTE-{tipo_dte} no admitido en compras. "
                f"Validos: {', '.join(sorted(TIPOS_VALIDOS_COMPRAS))}."
            )
        }

    sello = _extraer_sello_envoltorio(data, dte_raw, dte_raw.get("identificacion") or {})

    # Proveedor: emisor por defecto; para DTE-14, usar sujetoExcluido
    if tipo_dte == "14" and dte.sujetoExcluido:
        sujeto   = dte.sujetoExcluido
        nom_prov = sujeto.nombre.upper().strip()
        _raw_suj = (sujeto.documento or sujeto.nit or sujeto.dui).replace("-", "").strip()
        id_prov  = re.sub(r"[^0-9]", "", _raw_suj)
    else:
        emisor   = dte.emisor
        nom_prov = emisor.nombre.upper().strip()
        _raw_em  = (emisor.nit or emisor.dui or emisor.numDocumento or emisor.nrc).replace("-", "").strip()
        id_prov  = re.sub(r"[^0-9]", "", _raw_em)

    nit_prov = id_prov if len(id_prov) == 14 else ""
    dui_prov = id_prov if len(id_prov) == 9  else ""

    receptor_c = dte.receptor
    _raw_rec_c = (receptor_c.nit or receptor_c.dui or receptor_c.numDocumento).replace("-", "").strip()
    nit_receptor_c = re.sub(r"[^0-9]", "", _raw_rec_c)

    fecha = _fecha_ddmmyyyy(ident.fecEmi)
    iva_val, fovial, cotrans = _tributos_iva_fovial_cotrans(resumen)

    gen_uuid = ident.codigoGeneracion
    num_ctrl = ident.numeroControl

    resultado = {
        "tipo"           : tipo_dte,
        "fecha"          : fecha,
        "num_control"    : num_ctrl,
        "num_control_raw": num_ctrl,
        "gen"            : gen_uuid,
        "gen_sin_guiones": gen_uuid.replace("-", ""),
        "sello"          : sello,
        "_nit_receptor"  : nit_receptor_c,
        "nom_prov"       : nom_prov,
        "nit_prov"       : nit_prov,
        "dui_prov"       : dui_prov,
        "gra"            : round(resumen.totalGravada, 2),
        # FOVIAL/COTRANS (tributos C3/59) están en totalPagar pero no en
        # totalExenta/totalNoSuj — mismo ajuste que en el lado ventas, ver
        # comentario arriba.
        "exe"            : round(resumen.totalExenta + fovial + cotrans, 2),
        "no_sujetas"     : round(resumen.totalNoSuj, 2),
        "iva"            : round(iva_val, 2),
        "ret"            : 0.0,
        "perc"           : 0.0,
        "tot"            : round(resumen.totalPagar, 2),
        "fovial"         : round(fovial, 2),
        "cotrans"        : round(cotrans, 2),
        "_origen"        : "json_nativo",
        "fuentes"        : {
            k: "json_oficial" for k in
            ("fecha", "num_control", "sello", "nit_prov", "nom_prov", "gra", "iva", "exe", "tot")
        },
    }

    from utils.qa_utils import validar_montos_ventas
    alertas = validar_montos_ventas(resultado)
    if alertas:
        resultado["estado"] = "REVISAR"
        resultado["confianza"] = 60
        resultado["detalle_confianza"] = "; ".join(alertas)
    else:
        resultado["estado"] = "OK"
        resultado["confianza"] = 100
        resultado["detalle_confianza"] = "JSON oficial de Hacienda — schema validado, montos cuadran."
    resultado["campos_faltantes"] = []
    resultado["validacion_montos"] = "error" if alertas else "ok"
    return resultado
