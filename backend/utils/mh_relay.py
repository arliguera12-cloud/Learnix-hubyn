"""
utils/mh_relay.py — Consulta pública de Hacienda por relevo (modo "relay").

POR QUÉ EXISTE: Hacienda responde 403 a las peticiones que salen de Railway
(probado el 9-oct-2026 con dos IP de salida distintas, con `curl` y con
`requests`), y responde bien a una IP residencial de El Salvador. Como desde el
servidor no se puede llegar, la consulta la hace un worker (scripts/mh_worker)
en un equipo con salida desde El Salvador:

    extractor ──► consultar_via_relay ──► cola en Supabase (mh_consulta_cola)
                                                │  (el worker pregunta cada pocos s)
    worker ──► POST /mh-relay/reclamar ◄────────┘
    worker ──► GET Hacienda (1 consulta cada ~4.5 s, desde su IP)
    worker ──► POST /mh-relay/resultado ──► cola ──► el extractor lo recoge

El worker NO tiene claves de Supabase: solo un token (MH_RELAY_TOKEN) que el
backend valida (routers/mh_relay.py). Lo peor que puede hacer quien lo robe es
pedir/escribir consultas de la cola, y se revoca cambiando la variable.

Activación: MH_CONSULTA_MODO=relay (por defecto "directo", el comportamiento
anterior). Con el modo relay, el ritmo hacia Hacienda lo controla el worker, no
el limitador de mh_consulta.py.

Degradación: igual que la consulta directa, nunca lanza ni bloquea de más. Si el
worker no ha dado señales (apagado, sin internet) el DTE queda en cola y se
devuelve None sin esperar: la extracción sigue con regex/Visión/IA y, cuando el
worker vuelva, la verificación queda guardada y se sirve al instante en el
próximo procesamiento (caché de 24 h).

shortcut: el latido del worker vive en memoria del proceso (un solo proceso
Uvicorn en Railway, igual que utils/jobs.py); con varias instancias habría que
moverlo a la base de datos.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import datetime, timezone

log =logging.getLogger(__name__)

_UUID_RE = re.compile(r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$')
_FECHA_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

MAX_INTENTOS = 5
MAX_BYTES_CUERPO = 500_000  # una respuesta real pesa pocos KB

# Los tests reemplazan estos dos por un reloj falso.
_ahora, _dormir = time.monotonic, time.sleep


def _leer_float(nombre: str, defecto: float) -> float:
    try:
        return float(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


def modo_relay() -> bool:
    return os.getenv("MH_CONSULTA_MODO", "directo").strip().lower() == "relay"


def _espera_max_s() -> float:
    # Un lote de 15 PDF a ~4.5 s por consulta tarda ~70 s en el peor caso.
    return _leer_float("MH_RELAY_ESPERA_S", 60.0)


def _vivo_s() -> float:
    # El worker pregunta cada ~4 s; con 45 s sin señal se da por caído.
    return _leer_float("MH_RELAY_VIVO_S", 45.0)


_POLL_S = 3.0

# ── Latido del worker ───────────────────────────────────────────────────────
_latido_lock = threading.Lock()
_ultimo_latido = 0.0


def registrar_latido() -> None:
    global _ultimo_latido
    with _latido_lock:
        _ultimo_latido = _ahora()


def worker_vivo() -> bool:
    with _latido_lock:
        return _ultimo_latido > 0 and (_ahora() - _ultimo_latido) < _vivo_s()


# ── Acceso a la cola (los tests reemplazan estas cuatro funciones) ──────────
def _db():
    from utils.supabase_admin import get_supabase
    return get_supabase()


def _db_encolar(cod: str, fecha: str, ambiente: str) -> dict | None:
    filas = _db().rpc("mh_cola_encolar", {"p_codigo": cod, "p_fecha": fecha, "p_ambiente": ambiente}).execute().data
    return filas[0] if filas else None


def _db_leer(cod: str, fecha: str, ambiente: str) -> dict | None:
    filas = (
        _db().table("mh_consulta_cola")
        .select("estado,resultado,intentos")
        .eq("codigo_generacion", cod).eq("fecha_emi", fecha).eq("ambiente", ambiente)
        .limit(1).execute().data
    )
    return filas[0] if filas else None


def _db_reclamar(n: int) -> list[dict]:
    return _db().rpc("mh_cola_reclamar", {"p_max": n}).execute().data or []


def _db_actualizar(cod: str, fecha: str, ambiente: str, cambios: dict) -> None:
    """Solo actualiza si la fila sigue 'procesando': un resultado tardío de un
    trabajo que ya se reasignó no debe pisar a otro."""
    (
        _db().table("mh_consulta_cola").update(cambios)
        .eq("codigo_generacion", cod).eq("fecha_emi", fecha).eq("ambiente", ambiente)
        .eq("estado", "procesando").execute()
    )


# ── Interpretación de la respuesta de Hacienda ──────────────────────────────
def _aceptar(data) -> dict | None:
    """Misma regla que utils/mh_consulta.consultar_dte_publico: se devuelve el
    JSON si trae el documento (action OK) o un estadoDoc (p. ej. "Rechazado");
    si no, el documento no existe y es None."""
    if not isinstance(data, dict):
        return None
    if data.get("action") == "OK" and isinstance(data.get("documento"), dict):
        return data
    if str(data.get("estadoDoc") or "").strip():
        return data
    return None


def decidir_estado(http_status: int, cuerpo, intentos: int) -> tuple[str, int]:
    """(estado nuevo, intentos nuevos) según lo que reportó el worker.

    · 200 con documento      → ok
    · 200 sin documento, 400, 404 → no_encontrado (respuesta válida de Hacienda)
    · 0 / 403 / 429          → pendiente SIN contar intento: es el tope de tasa o
                               un bloqueo, no un fallo del documento; el worker
                               se pone en pausa por su cuenta.
    · cualquier otro (5xx, timeouts) → pendiente, contando intento; al quinto, error.
    """
    if http_status == 200 and isinstance(cuerpo, dict):
        return ("ok", intentos) if _aceptar(cuerpo) is not None else ("no_encontrado", intentos)
    if http_status in (400, 404):
        return "no_encontrado", intentos
    if http_status in (0, 403, 429):
        return "pendiente", intentos
    intentos += 1
    return ("error" if intentos >= MAX_INTENTOS else "pendiente"), intentos


# ── Lado extractor ──────────────────────────────────────────────────────────
def consultar_via_relay(cod: str, fecha: str, ambiente: str = "01") -> dict | None:
    """Equivalente a la consulta directa, pero a través de la cola. `cod` y
    `fecha` ya vienen validados por consultar_dte_publico."""
    try:
        fila = _db_encolar(cod, fecha, ambiente)
    except Exception as exc:
        log.warning("Consulta MH (relay): no se pudo encolar %s: %s", cod, exc)
        return None
    if not fila:
        return None

    resultado = _resolver(fila, cod)
    if resultado is not _EN_ESPERA:
        return resultado

    if not worker_vivo():
        log.info("Consulta MH (relay): el worker no da señales — %s queda en cola, se sigue con regex/Visión", cod)
        return None

    limite = _ahora() + _espera_max_s()
    while _ahora() < limite:
        _dormir(_POLL_S)
        try:
            fila = _db_leer(cod, fecha, ambiente)
        except Exception as exc:
            log.warning("Consulta MH (relay): error leyendo %s: %s", cod, exc)
            return None
        if not fila:
            return None
        resultado = _resolver(fila, cod)
        if resultado is not _EN_ESPERA:
            return resultado
    log.info("Consulta MH (relay): %s sigue en cola tras %.0fs — se sigue sin ella (queda guardada cuando el worker la complete)", cod, _espera_max_s())
    return None


_EN_ESPERA = object()


def _resolver(fila: dict, cod: str):
    estado = fila.get("estado")
    if estado == "ok":
        data = _aceptar(fila.get("resultado"))
        log.info("Consulta MH (relay) OK para %s (estado=%s)", cod, (data or {}).get("estadoDoc"))
        return data
    if estado in ("no_encontrado", "error"):
        log.info("Consulta MH (relay): %s → %s", cod, estado)
        return None
    return _EN_ESPERA


# ── Lado worker (lo llama routers/mh_relay.py) ──────────────────────────────
def reclamar_trabajos(n: int) -> list[dict]:
    registrar_latido()
    filas = _db_reclamar(max(1, min(int(n), 5)))
    return [
        {"codigo_generacion": f["codigo_generacion"], "fecha_emi": str(f["fecha_emi"]), "ambiente": f.get("ambiente") or "01"}
        for f in filas
    ]


def guardar_resultado(cod: str, fecha: str, ambiente: str, http_status: int, cuerpo, error: str | None = None) -> str:
    """Registra lo que reportó el worker y devuelve el estado resultante.
    Lanza ValueError con un mensaje legible si el reporte no es aceptable."""
    registrar_latido()
    if not _UUID_RE.match(cod) or not _FECHA_RE.match(fecha) or ambiente not in ("00", "01"):
        raise ValueError("código, fecha o ambiente con formato inválido")
    if cuerpo is not None:
        if not isinstance(cuerpo, dict):
            raise ValueError("el cuerpo debe ser un objeto JSON")
        if len(repr(cuerpo)) > MAX_BYTES_CUERPO:
            raise ValueError("el cuerpo es demasiado grande")
        # Defensa ante un worker con un error: la respuesta tiene que ser del
        # documento que se pidió.
        recibido = (((cuerpo.get("documento") or {}).get("identificacion") or {}).get("codigoGeneracion"))
        if recibido and str(recibido).upper() != cod:
            raise ValueError("el cuerpo corresponde a otro código de generación")

    fila = _db_leer(cod, fecha, ambiente)
    if not fila or fila.get("estado") != "procesando":
        raise ValueError("ese trabajo no está en proceso")

    estado, intentos = decidir_estado(http_status, cuerpo, int(fila.get("intentos") or 0))
    cambios = {
        "estado": estado,
        "http_status": http_status or None,
        "intentos": intentos,
        "resultado": cuerpo if estado == "ok" else None,
        "reclamado_en": None,
        # PostgREST no evalúa `now()` como valor: se manda la hora.
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
    }
    _db_actualizar(cod, fecha, ambiente, cambios)
    if error:
        log.info("Consulta MH (relay): worker reportó %s para %s (%s)", http_status, cod, error[:120])
    return estado
