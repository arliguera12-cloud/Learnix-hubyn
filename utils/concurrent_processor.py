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


def procesar_json_nativo_ventas(file_bytes: bytes) -> dict:
    """
    Parses a native Hacienda DTE JSON (ventas side).
    Returns the same field schema as extraer_venta_nativo_pro so the
    Streamlit page can handle it without special-casing.
    Any unexpected parsing error returns blank/zero fields instead of crashing.
    """
    _BLANK = {
        "tipo": "", "fecha": "", "num_control": "", "num_control_raw": "",
        "gen": "", "gen_sin_guiones": "", "sello": "",
        "nom_cli": "CONSUMIDOR FINAL", "nit_cli": "", "dui_cli": "",
        "gravadas": 0.0, "exentas": 0.0, "no_sujetas": 0.0,
        "debito": 0.0, "terceros": 0.0, "deb_terc": 0.0,
        "total": 0.0, "fovial": 0.0, "cotrans": 0.0, "_origen": "json_nativo",
    }
    try:
        data = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception as exc:
        return {"error_fatal": f"JSON inválido: {exc}"}

    try:
        # Los datos del DTE vienen dentro de dteJson; fallback a la raíz por compatibilidad
        dte = data.get("dteJson") or data

        ident    = dte.get("identificacion") or {}
        receptor = dte.get("receptor") or {}
        resumen  = dte.get("resumen") or {}

        # Sello nómada: puede estar en varios niveles del envoltorio o del DTE
        def _ss(v): return re.sub(r"\s+", "", str(v or "")).strip()
        sello = (
            _ss(data.get("selloRecibido"))
            or _ss(dte.get("selloRecibido"))
            or _ss((dte.get("respuestaHacienda") or {}).get("selloRecibido"))
            or _ss((dte.get("responseMH") or {}).get("selloRecibido"))
            or _ss(ident.get("SelloRecibido"))
            or _ss(ident.get("selloRecibido"))
        )

        # Fecha: YYYY-MM-DD → DD/MM/YYYY
        fecha_raw = str(ident.get("fecEmi") or "")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", fecha_raw):
            y, m, d = fecha_raw.split("-")
            fecha = f"{d}/{m}/{y}"
        else:
            fecha = fecha_raw

        # Identificación del receptor — strip guiones antes de filtrar dígitos
        _raw_r = str(
            receptor.get("nit") or receptor.get("dui") or receptor.get("numDocumento") or ""
        ).replace("-", "").strip()
        nit_r = re.sub(r"[^0-9]", "", _raw_r)
        _raw_dui_r = str(receptor.get("numDocumento") or "").replace("-", "").strip()
        dui_r = re.sub(r"[^0-9]", "", _raw_dui_r)

        # Identificación del emisor (para validación de pertenencia en ventas)
        emisor_v = dte.get("emisor") or {}
        _raw_emit_v = str(
            emisor_v.get("nit") or emisor_v.get("dui") or emisor_v.get("numDocumento") or ""
        ).replace("-", "").strip()
        nit_emisor_v = re.sub(r"[^0-9]", "", _raw_emit_v)

        # Tributos: IVA, FOVIAL, COTRANS — proteger contra None
        tributos_v = resumen.get("tributos") or []
        iva_val = fovial = cotrans = 0.0
        for t in tributos_v:
            cod  = str(t.get("codigo") or "")
            desc = str(t.get("descripcion") or "").upper()
            val  = _safe_float(t.get("valor"))
            if cod == "20" or "IVA" in desc or "IMPUESTO AL VALOR AGREGADO" in desc:
                iva_val = val
            elif cod == "C3" or "FOVIAL" in desc:
                fovial = val
            elif cod == "59" or "COTRANS" in desc:
                cotrans = val
        if not iva_val:
            iva_val = _safe_float(resumen.get("totalIva"))

        gen_uuid = str(ident.get("codigoGeneracion") or "")
        num_ctrl = str(ident.get("numeroControl") or "")

        return {
            "tipo"           : str(ident.get("tipoDte") or ""),
            "fecha"          : fecha,
            "num_control"    : num_ctrl,
            "num_control_raw": num_ctrl,
            "gen"            : gen_uuid,
            "gen_sin_guiones": gen_uuid.replace("-", ""),
            "sello"          : sello,
            "_nit_emisor"    : nit_emisor_v,
            "nom_cli"        : str(receptor.get("nombre") or "CONSUMIDOR FINAL").upper().strip(),
            "nit_cli"        : nit_r if len(nit_r) == 14 else "",
            "dui_cli"        : dui_r if len(dui_r) == 9 else "",
            "gravadas"       : _safe_float(resumen.get("totalGravada")),
            "exentas"        : _safe_float(resumen.get("totalExenta")),
            "no_sujetas"     : _safe_float(resumen.get("totalNoSuj")),
            "debito"         : iva_val,
            "terceros"       : 0.0,
            "deb_terc"       : 0.0,
            "total"          : _safe_float(resumen.get("totalPagar")),
            "fovial"         : fovial,
            "cotrans"        : cotrans,
            "_origen"        : "json_nativo",
        }
    except Exception as exc:
        log.error("Error inesperado parseando JSON ventas: %s", exc, exc_info=True)
        return _BLANK


def procesar_json_nativo_compras(file_bytes: bytes) -> dict:
    """
    Parses a native Hacienda DTE JSON (compras side).
    Returns the same field schema as extraer_compra_nativo_pro.
    Any unexpected parsing error returns blank/zero fields instead of crashing.
    """
    _BLANK = {
        "tipo": "", "fecha": "", "num_control": "", "num_control_raw": "",
        "gen": "", "gen_sin_guiones": "", "sello": "",
        "nom_prov": "", "nit_prov": "", "dui_prov": "",
        "gra": 0.0, "exe": 0.0, "no_sujetas": 0.0,
        "iva": 0.0, "ret": 0.0, "perc": 0.0,
        "tot": 0.0, "fovial": 0.0, "cotrans": 0.0, "_origen": "json_nativo",
    }
    try:
        data = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception as exc:
        return {"error_fatal": f"JSON inválido: {exc}"}

    try:
        # Los datos del DTE vienen dentro de dteJson; fallback a la raíz por compatibilidad
        dte = data.get("dteJson") or data

        ident   = dte.get("identificacion") or {}
        resumen = dte.get("resumen") or {}

        # Sello nómada: puede estar en varios niveles del envoltorio o del DTE
        def _ss(v): return re.sub(r"\s+", "", str(v or "")).strip()
        sello = (
            _ss(data.get("selloRecibido"))
            or _ss(dte.get("selloRecibido"))
            or _ss((dte.get("respuestaHacienda") or {}).get("selloRecibido"))
            or _ss((dte.get("responseMH") or {}).get("selloRecibido"))
            or _ss(ident.get("SelloRecibido"))
            or _ss(ident.get("selloRecibido"))
        )

        # Proveedor: emisor por defecto; para DTE-14, usar sujetoExcluido
        tipo_dte = str(ident.get("tipoDte") or "")
        if tipo_dte == "14":
            sujeto   = dte.get("sujetoExcluido") or {}
            nom_prov = str(sujeto.get("nombre") or "").upper().strip()
            _raw_suj = str(
                sujeto.get("documento") or sujeto.get("nit") or sujeto.get("dui") or ""
            ).replace("-", "").strip()
            id_prov  = re.sub(r"[^0-9]", "", _raw_suj)
        else:
            emisor   = dte.get("emisor") or {}
            nom_prov = str(emisor.get("nombre") or "").upper().strip()
            _raw_em  = str(
                emisor.get("nit") or emisor.get("dui") or emisor.get("numDocumento") or emisor.get("nrc") or ""
            ).replace("-", "").strip()
            id_prov  = re.sub(r"[^0-9]", "", _raw_em)

        nit_prov = id_prov if len(id_prov) == 14 else ""
        dui_prov = id_prov if len(id_prov) == 9  else ""

        # Identificación del receptor (para validación de pertenencia en compras)
        receptor_c = dte.get("receptor") or {}
        _raw_rec_c = str(
            receptor_c.get("nit") or receptor_c.get("dui") or receptor_c.get("numDocumento") or ""
        ).replace("-", "").strip()
        nit_receptor_c = re.sub(r"[^0-9]", "", _raw_rec_c)

        fecha_raw = str(ident.get("fecEmi") or "")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", fecha_raw):
            y, m, d = fecha_raw.split("-")
            fecha = f"{d}/{m}/{y}"
        else:
            fecha = fecha_raw

        tributos_c = resumen.get("tributos") or []
        iva_val = fovial = cotrans = 0.0
        for t in tributos_c:
            cod  = str(t.get("codigo") or "")
            desc = str(t.get("descripcion") or "").upper()
            val  = _safe_float(t.get("valor"))
            if cod == "20" or "IVA" in desc or "IMPUESTO AL VALOR AGREGADO" in desc:
                iva_val = val
            elif cod == "C3" or "FOVIAL" in desc:
                fovial = val
            elif cod == "59" or "COTRANS" in desc:
                cotrans = val
        if not iva_val:
            iva_val = _safe_float(resumen.get("totalIva"))

        gen_uuid = str(ident.get("codigoGeneracion") or "")
        num_ctrl = str(ident.get("numeroControl") or "")

        return {
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
            "gra"            : _safe_float(resumen.get("totalGravada")),
            "exe"            : _safe_float(resumen.get("totalExenta")),
            "no_sujetas"     : _safe_float(resumen.get("totalNoSuj")),
            "iva"            : iva_val,
            "ret"            : 0.0,
            "perc"           : 0.0,
            "tot"            : _safe_float(resumen.get("totalPagar")),
            "fovial"         : fovial,
            "cotrans"        : cotrans,
            "_origen"        : "json_nativo",
        }
    except Exception as exc:
        log.error("Error inesperado parseando JSON compras: %s", exc, exc_info=True)
        return _BLANK
