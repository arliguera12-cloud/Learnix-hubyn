"""
utils/jobs.py — Job store en memoria para el procesamiento de lotes en background.

Un solo proceso Uvicorn en Railway (sin autoscaling horizontal), así que un
dict en memoria alcanza — no hace falta Redis/Celery para esto. Los jobs
sobreviven mientras el contenedor esté vivo; si se reinicia se pierden los
que estaban en curso, igual que se perdía cualquier request en vuelo antes
de este cambio.

Por qué existe: antes /procesar/{tipo}/lote respondía recién cuando
terminaba todo el lote (podía tardar minutos) — cualquier timeout
intermedio (navegador, proxy, Vercel) cortaba esa conexión aunque el
backend siguiera trabajando y terminara bien, mostrando "Network Error" en
el frontend sin que hubiera ningún error real del lado del servidor. Ahora
el endpoint crea un job y responde al instante con su id; el trabajo real
corre en background (FastAPI BackgroundTasks) y el frontend consulta el
progreso con GET periódicos — conexiones cortas, sin nada que un timeout
intermedio pueda cortar a mitad de camino.
"""
from __future__ import annotations

import threading
import time
import uuid

_TTL_SEGUNDOS = 2 * 60 * 60  # 2h — tiempo de sobra para que el usuario haga polling y descargue el resultado

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def crear_job(total: int) -> str:
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
    return job_id


def _limpiar_viejos(ahora: float) -> None:
    # Se asume que _lock ya está tomado por quien llama.
    vencidos = [
        jid for jid, job in _jobs.items()
        if job["terminado_en"] is not None and (ahora - job["terminado_en"]) > _TTL_SEGUNDOS
    ]
    for jid in vencidos:
        del _jobs[jid]


def actualizar_progreso(job_id: str, resultado: dict | None = None, error: dict | None = None) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if resultado is not None:
            job["resultados"].append(resultado)
        if error is not None:
            job["errores"].append(error)
        job["procesados"] += 1


def finalizar_job(job_id: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job["status"] = "done"
            job["terminado_en"] = time.time()


def marcar_error_job(job_id: str, mensaje: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job["status"] = "error"
            job["error_fatal"] = mensaje
            job["terminado_en"] = time.time()


def obtener_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None
