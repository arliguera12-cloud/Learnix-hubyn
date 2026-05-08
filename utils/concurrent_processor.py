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

import logging
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
