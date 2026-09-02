"""
utils/mh_consulta.py — Consulta pública del DTE en el portal del Ministerio de
Hacienda: el mismo endpoint que usa https://admin.factura.gob.sv/consultaPublica
cuando escaneás el QR del documento con el celular y le das "Consultar".

Es un GET público, sin autenticación ni captcha, que devuelve el DTE oficial
completo (identificación, resumen con montos, cuerpo del documento) — la
fuente más confiable posible, porque viene directo de la base de datos del
MH en vez de inferirse de un PDF con OCR/regex/IA.

Verificado con un DTE-07 real: totalSujetoRetencion=800, totalIVAretenido=8
(800 × 1% = 8, exacto) — mismos nombres de campo que ya usa
schemas/dte_hacienda.py para el JSON nativo firmado (totalGravada,
totalExenta, totalPagar aparecen con el mismo nombre en el `resumen`).

Uso responsable: se llama una sola vez por documento que el usuario ya
subió. Un lote procesa varios documentos en paralelo (hasta 10 por tanda),
así que sin control esto sí podía volverse una ráfaga de N consultas
simultáneas — se limita a _MAX_CONCURRENTES en vuelo a la vez (ver abajo)
para no parecer scraping automatizado ante Hacienda. Si el servicio no
responde, cambia de forma, da 429 (tope de tasa) o el documento no existe,
se degrada en silencio al pipeline normal (regex + Vision + IA) — nunca
bloquea ni retrasa la extracción más que el timeout configurado. Los
resultados (éxito/fallo/tiempo) se loguean con log.warning en los casos de
falla real para que queden visibles en Railway (antes de agregar
logging.basicConfig() en main.py, TODO log.info() de este módulo se
descartaba en silencio y esta consulta era invisible en los logs).

Circuit breaker: si Hacienda está caída/degradada (varios fallos de red o
timeout seguidos — no un simple "documento no encontrado", que es una
respuesta válida), se abre el circuito y las siguientes consultas se omiten
directo por _CIRCUITO_COOLDOWN segundos, sin ni siquiera intentar la
llamada. Sin esto, un lote de 96 PDFs con Hacienda caída pagaría el timeout
completo en CADA documento — con el aviso oficial de uso restringido de
endpoints (efectivo 25-ago-2026) ya vencido y reportes de lentitud real,
es exactamente el escenario a cubrir.
"""
from __future__ import annotations

import logging
import re
import threading
import time

import requests

log = logging.getLogger(__name__)

_URL = "https://admin.factura.gob.sv/prod/consultas/publica/simple/1"
_TIMEOUT = 4  # segundos — reducido de 8: un dato opcional no debería poder
              # costarle 8s a cada documento cuando Hacienda está lenta.

_UUID_RE  = re.compile(r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$')
_FECHA_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# ── Throttle de concurrencia ────────────────────────────────────────────────
# Cada extractor (ventas/compras/retenciones/sujetos_excluidos) llama a esta
# consulta desde un hilo aparte por documento, y un lote se procesa con
# asyncio.gather sobre toda una tanda (TAMANO_TANDA=10 en el frontend) —
# eso significa hasta 10 llamadas a admin.factura.gob.sv EN PARALELO desde
# la misma instancia de Railway. El docstring de este módulo promete "mismo
# volumen que una consulta manual hecha a mano, nunca en bucles de scraping",
# pero sin este límite el comportamiento real es justo una ráfaga concurrente
# — el patrón que el aviso de Hacienda sobre uso restringido de endpoints
# apunta a frenar, y candidato directo a disparar un tope de tasa en su lado.
# _MAX_CONCURRENTES=5 (mitad de una tanda) es un punto medio: sigue evitando
# la ráfaga de 10 a la vez, pero con el circuit breaker de abajo el caso
# realmente costoso (Hacienda caída) ya no depende de este número — se
# resuelve dejando de intentar del todo tras unos pocos fallos.
_MAX_CONCURRENTES = 5
_semaforo = threading.Semaphore(_MAX_CONCURRENTES)

# ── Circuit breaker ──────────────────────────────────────────────────────
_FALLOS_CONSECUTIVOS_MAX = 4
_CIRCUITO_COOLDOWN = 60  # segundos que se deja de intentar tras abrir el circuito

_estado_lock = threading.Lock()
_fallos_consecutivos = 0
_circuito_abierto_hasta = 0.0


def _circuito_abierto() -> bool:
    with _estado_lock:
        return time.monotonic() < _circuito_abierto_hasta


def _registrar_resultado(ok: bool) -> None:
    """Solo fallos de red/timeout/HTTP cuentan para el circuito — un 'no
    encontrado' (action != OK) es una respuesta normal del servicio, no una
    caída, y no debe abrirlo."""
    global _fallos_consecutivos, _circuito_abierto_hasta
    with _estado_lock:
        if ok:
            _fallos_consecutivos = 0
            _circuito_abierto_hasta = 0.0
            return
        _fallos_consecutivos += 1
        if _fallos_consecutivos >= _FALLOS_CONSECUTIVOS_MAX and time.monotonic() >= _circuito_abierto_hasta:
            _circuito_abierto_hasta = time.monotonic() + _CIRCUITO_COOLDOWN
            log.warning(
                "Consulta pública MH: circuito ABIERTO tras %d fallos seguidos — "
                "se omite esta consulta por %ds (Hacienda parece caída/degradada)",
                _fallos_consecutivos, _CIRCUITO_COOLDOWN,
            )


# Único estado "sano" que devuelve Hacienda para un DTE aceptado. Cualquier
# otro valor no vacío (Rechazado, Invalidado, Anulado, ...) es una alerta real
# que el usuario iría a buscar manualmente escaneando el QR.
_ESTADO_DOC_SANO = "PROCESADO"


def estado_doc_alerta(consulta_mh: dict | None) -> str | None:
    """
    Si la consulta MH trae un estadoDoc distinto de "Procesado" (Rechazado,
    Invalidado, Anulado, etc.), arma un mensaje de alerta listo para
    gemini_correcciones/detalle_confianza. None si no hay nada que alertar
    (sin consulta, o estadoDoc vacío/"Procesado").
    """
    if not consulta_mh:
        return None
    estado = str(consulta_mh.get("estadoDoc") or "").strip()
    if not estado or estado.upper() == _ESTADO_DOC_SANO:
        return None
    detalle = str(consulta_mh.get("descripcionEstado") or "").strip()
    return f"documento {estado.upper()} ante Hacienda" + (f" — {detalle}" if detalle else "")


def consultar_dte_publico(codigo_generacion: str, fecha_emi_iso: str, ambiente: str = "01") -> dict | None:
    """
    Consulta el DTE en el portal público del MH.

    Args:
        codigo_generacion: UUID del DTE (con o sin guiones).
        fecha_emi_iso: fecha de emisión en formato YYYY-MM-DD — la que trae
            el QR en `fecha_qr` (utils/qr_reader.py), no la que se muestra
            formateada en pantalla (DD/MM/YYYY).
        ambiente: "01" producción, "00" pruebas.

    Returns:
        El JSON completo de la respuesta si `action == "OK"` y trae un
        `documento`. `None` en cualquier otro caso (no encontrado, forma
        inesperada, error de red, timeout). Nunca lanza excepción — esta
        consulta es un enriquecimiento opcional, no puede tumbar la
        extracción si Hacienda está lenta o caída.
    """
    cod = re.sub(r'[^0-9A-Fa-f-]', '', str(codigo_generacion or '')).upper()
    fecha = str(fecha_emi_iso or '').strip()
    if not _UUID_RE.match(cod) or not _FECHA_RE.match(fecha):
        log.info("Consulta pública MH: codigo_generacion/fecha con formato inválido (cod=%r, fecha=%r) — se omite", cod, fecha)
        return None

    if _circuito_abierto():
        log.info("Consulta pública MH: circuito abierto (Hacienda caída/degradada) — se omite %s sin intentar", cod)
        return None

    t0 = time.monotonic()
    with _semaforo:
        espera = round(time.monotonic() - t0, 2)
        if espera > 0.5:
            log.info("Consulta pública MH %s esperó %.2fs por el cupo de concurrencia (%d simultáneas máx)", cod, espera, _MAX_CONCURRENTES)
        t1 = time.monotonic()
        try:
            resp = requests.get(
                _URL,
                params={"codigoGeneracion": cod, "fechaEmi": fecha, "ambiente": ambiente},
                timeout=_TIMEOUT,
            )
            elapsed = round(time.monotonic() - t1, 2)
            if resp.status_code == 429:
                log.warning("Consulta pública MH: TOPE de tasa (429) para %s tras %.2fs — Retry-After=%s", cod, elapsed, resp.headers.get("Retry-After"))
                _registrar_resultado(False)
                return None
            resp.raise_for_status()
            data = resp.json()
            if data.get("action") == "OK" and isinstance(data.get("documento"), dict):
                log.info("Consulta pública MH OK para %s (estado=%s, %.2fs)", cod, data.get("estadoDoc"), elapsed)
                _registrar_resultado(True)
                return data
            # Hacienda respondió (no es una caída del servicio), pero con
            # action != "OK" — puede ser simplemente que el documento no
            # existe/no se encontró, O puede traer un estadoDoc real y valioso
            # (p. ej. "Rechazado": el documento se transmitió pero Hacienda lo
            # rechazó por no cumplir estructura/parámetros — confirmado con un
            # caso real: action="ERROR" pero estadoDoc="Rechazado" con
            # descripcionEstado explicando el motivo). Descartar esto en
            # silencio escondía justo la información que un usuario iría a
            # buscar manualmente escaneando el QR — se devuelve igual para que
            # el extractor pueda marcarlo como alerta en vez de tratarlo como
            # "no encontrado, seguir con regex/Visión sin más".
            _estado_doc = str(data.get("estadoDoc") or "").strip()
            if _estado_doc:
                log.warning(
                    "Consulta pública MH: %s tiene estadoDoc=%r (%s) — %.2fs",
                    cod, _estado_doc, data.get("descripcionEstado") or "sin detalle", elapsed,
                )
                _registrar_resultado(True)
                return data
            log.info("Consulta pública MH: %s respondió sin documento válido (action=%r, %.2fs)", cod, data.get("action"), elapsed)
            _registrar_resultado(True)  # el servicio respondió bien, solo no hay documento — no es una caída
            return None
        except requests.exceptions.Timeout:
            elapsed = round(time.monotonic() - t1, 2)
            log.warning("Consulta pública MH: TIMEOUT para %s tras %.2fs (límite %ds)", cod, elapsed, _TIMEOUT)
            _registrar_resultado(False)
            return None
        except requests.exceptions.HTTPError as exc:
            elapsed = round(time.monotonic() - t1, 2)
            log.warning("Consulta pública MH: HTTP %s para %s tras %.2fs", getattr(exc.response, "status_code", "?"), cod, elapsed)
            _registrar_resultado(False)
            return None
        except Exception as exc:
            elapsed = round(time.monotonic() - t1, 2)
            log.warning("Consulta pública MH falló para %s tras %.2fs: %s", cod, elapsed, exc)
            _registrar_resultado(False)
            return None
