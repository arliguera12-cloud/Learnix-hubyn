"""
utils/jobs.py — Job store en memoria (camino rápido) + respaldo en Supabase
para el procesamiento de lotes en background.

Un solo proceso Uvicorn en Railway (sin autoscaling horizontal), así que el
dict en memoria sigue siendo el camino normal de lectura/escritura — sin la
latencia de una llamada de red por cada documento procesado. Pero un
redeploy o reinicio del contenedor lo borra a mitad de camino: confirmado en
producción, un merge a main disparó un redeploy justo mientras un usuario
tenía un lote en curso, y el frontend recibió "Job no encontrado o
expirado" pese a que el lote se hubiera procesado bien.

Por eso las funciones de este módulo son TODAS síncronas y solo tocan
memoria (rápidas, sin red) — el respaldo/recuperación en Supabase
(`guardar_snapshot` / `cargar_de_supabase`, bloqueantes) las invoca
explícitamente quien llama desde código async (routers/procesamiento.py),
envueltas en `run_in_threadpool`, igual que cualquier otra llamada
bloqueante del backend.

Por qué existe /procesar/{tipo}/lote como job en background: antes
respondía recién cuando terminaba todo el lote (podía tardar minutos) —
cualquier timeout intermedio (navegador, proxy, Vercel) cortaba esa
conexión aunque el backend siguiera trabajando y terminara bien, mostrando
"Network Error" en el frontend sin que hubiera ningún error real del lado
del servidor.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid

log = logging.getLogger(__name__)

_TABLA = "procesamiento_jobs"
_TTL_SEGUNDOS = 2 * 60 * 60  # 2h — tiempo de sobra para que el usuario haga polling y descargue el resultado

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def crear_job(total: int) -> dict:
    """Crea el job en memoria y devuelve su snapshot (para respaldarlo en
    Supabase — ver guardar_snapshot)."""
    job_id = uuid.uuid4().hex
    ahora = time.time()
    with _lock:
        _limpiar_viejos(ahora)
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "processing",  # processing | done | error
            "total": total,
            "procesados": 0,
            "resultados": [],
            "errores": [],
            "error_fatal": None,
            "creado_en": ahora,
            "terminado_en": None,
        }
        return dict(_jobs[job_id])


def _limpiar_viejos(ahora: float) -> None:
    # Se asume que _lock ya está tomado por quien llama.
    vencidos = [
        jid for jid, job in _jobs.items()
        if job["terminado_en"] is not None and (ahora - job["terminado_en"]) > _TTL_SEGUNDOS
    ]
    for jid in vencidos:
        del _jobs[jid]


def actualizar_progreso(job_id: str, resultado: dict | None = None, error: dict | None = None) -> dict | None:
    """Devuelve el snapshot actualizado (o None si el job ya no está en
    memoria — pasó el TTL o el proceso se reinició)."""
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        if resultado is not None:
            job["resultados"].append(resultado)
        if error is not None:
            job["errores"].append(error)
        job["procesados"] += 1
        return dict(job)


def finalizar_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        job["status"] = "done"
        job["terminado_en"] = time.time()
        return dict(job)


def marcar_error_job(job_id: str, mensaje: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        job["status"] = "error"
        job["error_fatal"] = mensaje
        job["terminado_en"] = time.time()
        return dict(job)


def obtener_job(job_id: str) -> dict | None:
    """Solo memoria — rápido. Si el proceso se reinició y el job ya no está
    acá, el llamador debe intentar cargar_de_supabase() como respaldo."""
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


# ─── Respaldo en Supabase (bloqueante — envolver en run_in_threadpool) ────

def guardar_snapshot(job: dict) -> None:
    """Escribe el estado actual del job en Supabase. Nunca debe tumbar el
    procesamiento del lote: si Supabase falla o no está configurado, se
    loguea y se sigue — el dict en memoria sigue siendo la fuente de verdad
    mientras el proceso esté vivo."""
    try:
        from utils.supabase_admin import get_supabase
        row = {
            "job_id":       job["job_id"],
            "status":       job["status"],
            "total":        job["total"],
            "procesados":   job["procesados"],
            "resultados":   job["resultados"],
            "errores":      job["errores"],
            "error_fatal":  job["error_fatal"],
            "terminado_en": _iso(job["terminado_en"]),
        }
        get_supabase().table(_TABLA).upsert(row).execute()
    except Exception as exc:
        log.warning("No se pudo respaldar el job %s en Supabase: %s", job.get("job_id"), exc)


def cargar_de_supabase(job_id: str) -> dict | None:
    """Recupera un job desde Supabase cuando ya no está en memoria (p. ej.
    tras un redeploy). No lo vuelve a poner en memoria — la respuesta del
    endpoint alcanza con este dict."""
    try:
        from utils.supabase_admin import get_supabase
        resp = get_supabase().table(_TABLA).select("*").eq("job_id", job_id).limit(1).execute()
        if not resp.data:
            return None
        row = resp.data[0]
        return {
            "job_id":       row["job_id"],
            "status":       row["status"],
            "total":        row["total"],
            "procesados":   row["procesados"],
            "resultados":   row.get("resultados") or [],
            "errores":      row.get("errores") or [],
            "error_fatal":  row.get("error_fatal"),
            "creado_en":    row.get("creado_en"),
            "terminado_en": row.get("terminado_en"),
        }
    except Exception as exc:
        log.warning("No se pudo recuperar el job %s de Supabase: %s", job_id, exc)
        return None


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))
