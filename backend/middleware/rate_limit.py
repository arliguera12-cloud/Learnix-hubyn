"""
rate_limit.py — Rate limiting por IP, en memoria.

Suficiente para una sola instancia de Railway. Si se escala a múltiples
instancias, esto necesita moverse a un store compartido (Redis).
"""
import os
import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse

_requests: dict[str, list[float]] = defaultdict(list)

_WINDOW = 60  # segundos


def _rate_limit() -> int:
    return int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))


def _burst_limit() -> int:
    return int(os.environ.get("RATE_LIMIT_BURST", "60"))


def _blocked_ips() -> set[str]:
    return {
        ip.strip()
        for ip in os.environ.get("BLOCKED_IPS", "").split(",")
        if ip.strip()
    }


def _get_client_ip(request: Request) -> str:
    """IP real detrás de proxy (Railway/Vercel usan X-Forwarded-For)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    # El frontend hace polling de /procesar/lote/jobs/{id} cada pocos segundos
    # mientras un lote corre en background (ver utils/jobs.py) — con lotes
    # grandes (varias tandas de varios minutos cada una) ese polling legítimo
    # por sí solo supera el límite general y el propio sistema se bloqueaba a
    # sí mismo ("Límite de solicitudes alcanzado" en medio de un lote en
    # curso, confirmado en producción con 96 PDFs). Es una lectura liviana
    # (memoria o una fila de Supabase, sin llamadas a Groq/Hacienda) detrás
    # de autenticación (get_current_user), así que se excluye del límite
    # general igual que /health — el riesgo de abuso que este middleware
    # existe para frenar está en los endpoints de extracción, no acá.
    if request.url.path.startswith("/procesar/lote/jobs/"):
        return await call_next(request)

    client_ip = _get_client_ip(request)

    if client_ip in _blocked_ips():
        return JSONResponse({"detail": "Acceso denegado"}, status_code=403)

    now = time.time()
    _requests[client_ip] = [t for t in _requests[client_ip] if now - t < _WINDOW]

    if len(_requests[client_ip]) >= _burst_limit():
        return JSONResponse(
            {"detail": "Demasiadas solicitudes — intenta en un minuto"},
            status_code=429,
            headers={"Retry-After": "60"},
        )

    if len(_requests[client_ip]) >= _rate_limit():
        return JSONResponse(
            {"detail": "Límite de solicitudes alcanzado"},
            status_code=429,
            headers={"Retry-After": "60"},
        )

    _requests[client_ip].append(now)
    return await call_next(request)
