"""
rate_limit.py — Rate limiting por IP, en memoria.

Suficiente para una sola instancia de Railway. Si se escala a múltiples
instancias, esto necesita moverse a un store compartido (Redis).
"""
import os
import threading
import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse

_requests: dict[str, list[float]] = defaultdict(list)

_WINDOW = 60  # segundos

# Techo de IPs distintas seguidas a la vez. Sin él, `_requests` crece con cada
# valor nuevo de X-Forwarded-For que llegue — y ese encabezado lo escribe el
# cliente, así que rotarlo bastaba para inflar el dict sin límite.
_MAX_CLAVES = 10_000


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


def _proxies_de_confianza() -> int:
    """Cuántos proxies propios hay delante de la app (Railway: 1)."""
    return int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))


def _get_client_ip(request: Request) -> str:
    """
    IP real detrás de proxy (Railway/Vercel usan X-Forwarded-For).

    Se lee desde la DERECHA, no desde la izquierda. X-Forwarded-For es una
    lista que cada proxy va ampliando, y el cliente puede mandar la suya ya
    escrita: con `split(",")[0]` bastaba con enviar
    `X-Forwarded-For: 1.2.3.4` y cambiar ese valor en cada request para
    esquivar el límite por completo. Solo las últimas `TRUSTED_PROXY_COUNT`
    entradas las escribieron proxies nuestros; la que agregó el proxy más
    externo de confianza es la IP real del cliente.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        cadena = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        confiables = _proxies_de_confianza()
        if cadena and confiables > 0:
            indice = max(len(cadena) - confiables, 0)
            return cadena[indice]
    return request.client.host if request.client else "unknown"


def _podar(now: float) -> None:
    """Descarta las entradas cuya ventana ya venció. Si aun así se pasa del
    techo, vacía el registro entero: es un contador efímero de un minuto, y
    perderlo solo regala una ventana de gracia, mientras que dejarlo crecer
    sin control agota la memoria del contenedor."""
    vencidas = [ip for ip, marcas in _requests.items() if not marcas or now - marcas[-1] >= _WINDOW]
    for ip in vencidas:
        del _requests[ip]
    if len(_requests) > _MAX_CLAVES:
        _requests.clear()


# ─── Límite por clave arbitraria (p. ej. por usuario) ────────────────────────
# El límite general es por IP, que no sirve para frenar el abuso de un endpoint
# que recibe credenciales de terceros: quien las prueba puede rotar la IP, y
# quien las sufre no es el dueño de la IP sino el dueño de la cuenta atacada.
_por_clave: dict[str, list[float]] = defaultdict(list)
# A diferencia de `_requests`, que solo toca el middleware sobre el event loop,
# esto lo llaman endpoints declarados con `def`: FastAPI los corre en su
# threadpool, o sea varios hilos a la vez sobre el mismo dict.
_por_clave_lock = threading.Lock()


def consumir_cupo(clave: str, limite: int, ventana: int = _WINDOW) -> bool:
    """Registra un intento y devuelve False si `clave` ya agotó su cupo."""
    now = time.time()
    with _por_clave_lock:
        marcas = [t for t in _por_clave[clave] if now - t < ventana]
        _por_clave[clave] = marcas
        if len(marcas) >= limite:
            return False
        marcas.append(now)
        if len(_por_clave) > _MAX_CLAVES:
            vencidas = [k for k, v in _por_clave.items() if not v or now - v[-1] >= ventana]
            for k in vencidas:
                del _por_clave[k]
        return True


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
    _podar(now)
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
