"""
Learnix Hub — Procesador paralelo de lotes de DTE.

ThreadPoolExecutor con max_workers=10 para enviar PDFs simultáneamente a Gemini.
Con 1,000 RPM en AI Studio cada hilo puede hacer ~100 req/min; 10 hilos usan
hasta ~600 RPM en carga pico, dejando margen para la cuota diaria.

Uso típico en una página:
    from utils.concurrent_processor import leer_y_procesar_lote

    nombres_bytes = leer_archivos_uploaded(nuevos)   # pre-lectura en hilo principal
    resultados    = leer_y_procesar_lote(
        nombres_bytes,
        fn_extraccion,          # fn(bytes) -> dict
        progreso_cb=lambda c, t, n: (bar.progress(c/t), txt.caption(f"⏳ {c}/{t}")),
    )
    for fname, fbytes, res in resultados:
        ...
"""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

log = logging.getLogger(__name__)

MAX_WORKERS: int = 10   # hilos simultáneos — seguro bajo 1,000 RPM


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


def procesar_json_nativo_ventas(file_bytes: bytes) -> dict:
    """
    Parses a native Hacienda DTE JSON (ventas side).
    Returns the same field schema as extraer_venta_nativo_pro so the
    Streamlit page can handle it without special-casing.

    Key mappings from DTE JSON → internal schema:
      identificacion.tipoDte         → tipo
      identificacion.fecEmi          → fecha (DD/MM/YYYY)
      identificacion.numeroControl   → num_control / num_control_raw
      identificacion.codigoGeneracion→ gen / gen_sin_guiones
      identificacion.selloRecibido   → sello
      receptor.nombre                → nom_cli
      receptor.nit / numDocumento    → nit_cli / dui_cli
      resumen.totalGravada           → gravadas
      resumen.totalExenta            → exentas
      resumen.totalNoSuj             → no_sujetas
      resumen.totalIva / tributos IVA→ debito
      resumen.totalPagar             → total
      tributos FOVIAL (C3)           → fovial
      tributos COTRANS (59)          → cotrans
    """
    try:
        data = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception as exc:
        return {"error_fatal": f"JSON inválido: {exc}"}

    ident    = data.get("identificacion") or {}
    receptor = data.get("receptor") or {}
    resumen  = data.get("resumen") or {}

    # Fecha: YYYY-MM-DD → DD/MM/YYYY
    fecha_raw = str(ident.get("fecEmi") or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", fecha_raw):
        y, m, d = fecha_raw.split("-")
        fecha = f"{d}/{m}/{y}"
    else:
        fecha = fecha_raw

    # Identificación del receptor
    nit_r = re.sub(r"[^0-9]", "", str(receptor.get("nit") or receptor.get("numDocumento") or ""))
    dui_r = re.sub(r"[^0-9]", "", str(receptor.get("numDocumento") or ""))

    # Tributos: IVA, FOVIAL, COTRANS
    iva_val = fovial = cotrans = 0.0
    for t in (resumen.get("tributos") or []):
        cod  = str(t.get("codigo") or "")
        desc = str(t.get("descripcion") or "").upper()
        val  = float(t.get("valor") or 0)
        if cod == "20" or "IVA" in desc:
            iva_val = val
        elif cod == "C3" or "FOVIAL" in desc:
            fovial = val
        elif cod == "59" or "COTRANS" in desc:
            cotrans = val
    if not iva_val:
        iva_val = float(resumen.get("totalIva") or 0)

    gen_uuid = str(ident.get("codigoGeneracion") or "")
    num_ctrl = str(ident.get("numeroControl") or "")

    return {
        "tipo"           : str(ident.get("tipoDte") or ""),
        "fecha"          : fecha,
        "num_control"    : num_ctrl,
        "num_control_raw": num_ctrl,
        "gen"            : gen_uuid,
        "gen_sin_guiones": gen_uuid.replace("-", ""),
        "sello"          : str(ident.get("selloRecibido") or "").strip(),
        "nom_cli"        : str(receptor.get("nombre") or "CONSUMIDOR FINAL").upper().strip(),
        "nit_cli"        : nit_r if len(nit_r) == 14 else "",
        "dui_cli"        : dui_r if len(dui_r) == 9 else "",
        "gravadas"       : float(resumen.get("totalGravada") or 0),
        "exentas"        : float(resumen.get("totalExenta") or 0),
        "no_sujetas"     : float(resumen.get("totalNoSuj") or 0),
        "debito"         : iva_val,
        "terceros"       : 0.0,
        "deb_terc"       : 0.0,
        "total"          : float(resumen.get("totalPagar") or 0),
        "fovial"         : fovial,
        "cotrans"        : cotrans,
        "_origen"        : "json_nativo",
    }


def procesar_json_nativo_compras(file_bytes: bytes) -> dict:
    """
    Parses a native Hacienda DTE JSON (compras side).
    Returns the same field schema as extraer_compra_nativo_pro.

    Key mappings:
      identificacion.*               → same as ventas
      emisor.nit                     → nit_prov
      emisor.nombre                  → nom_prov
      resumen.totalGravada           → gra
      resumen.totalExenta            → exe
      resumen.totalNoSuj             → no_sujetas (stored as no_sujetas)
      resumen.totalIva / tributos IVA→ iva
      resumen.totalPagar             → tot
      tributos FOVIAL / COTRANS      → fovial / cotrans
    """
    try:
        data = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception as exc:
        return {"error_fatal": f"JSON inválido: {exc}"}

    ident   = data.get("identificacion") or {}
    emisor  = data.get("emisor") or {}
    resumen = data.get("resumen") or {}

    fecha_raw = str(ident.get("fecEmi") or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", fecha_raw):
        y, m, d = fecha_raw.split("-")
        fecha = f"{d}/{m}/{y}"
    else:
        fecha = fecha_raw

    nit_e = re.sub(r"[^0-9]", "", str(emisor.get("nit") or ""))
    dui_e = re.sub(r"[^0-9]", "", str(emisor.get("numDocumento") or ""))

    iva_val = fovial = cotrans = 0.0
    for t in (resumen.get("tributos") or []):
        cod  = str(t.get("codigo") or "")
        desc = str(t.get("descripcion") or "").upper()
        val  = float(t.get("valor") or 0)
        if cod == "20" or "IVA" in desc:
            iva_val = val
        elif cod == "C3" or "FOVIAL" in desc:
            fovial = val
        elif cod == "59" or "COTRANS" in desc:
            cotrans = val
    if not iva_val:
        iva_val = float(resumen.get("totalIva") or 0)

    gen_uuid = str(ident.get("codigoGeneracion") or "")
    num_ctrl = str(ident.get("numeroControl") or "")

    return {
        "tipo"           : str(ident.get("tipoDte") or ""),
        "fecha"          : fecha,
        "num_control"    : num_ctrl,
        "num_control_raw": num_ctrl,
        "gen"            : gen_uuid,
        "gen_sin_guiones": gen_uuid.replace("-", ""),
        "sello"          : str(ident.get("selloRecibido") or "").strip(),
        "nom_prov"       : str(emisor.get("nombre") or "").upper().strip(),
        "nit_prov"       : nit_e if len(nit_e) == 14 else "",
        "dui_prov"       : dui_e if len(dui_e) == 9 else "",
        "gra"            : float(resumen.get("totalGravada") or 0),
        "exe"            : float(resumen.get("totalExenta") or 0),
        "no_sujetas"     : float(resumen.get("totalNoSuj") or 0),
        "iva"            : iva_val,
        "ret"            : 0.0,
        "perc"           : 0.0,
        "tot"            : float(resumen.get("totalPagar") or 0),
        "fovial"         : fovial,
        "cotrans"        : cotrans,
        "_origen"        : "json_nativo",
    }
