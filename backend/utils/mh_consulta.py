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
"""
from __future__ import annotations

import logging
import re
import threading
import time

import requests

log = logging.getLogger(__name__)

_URL = "https://admin.factura.gob.sv/prod/consultas/publica/simple/1"
_TIMEOUT = 8  # segundos — no vale la pena esperar más por un dato opcional

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
# (25-ago-2026) apunta a frenar, y candidato directo a disparar un tope de
# tasa en su lado. Se serializa a lo sumo _MAX_CONCURRENTES consultas a la
# vez; el resto de la extracción (Visión, regex) no se ve afectado, solo
# esta llamada de red puntual.
_MAX_CONCURRENTES = 2
_semaforo = threading.Semaphore(_MAX_CONCURRENTES)


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
                return None
            resp.raise_for_status()
            data = resp.json()
            if data.get("action") == "OK" and isinstance(data.get("documento"), dict):
                log.info("Consulta pública MH OK para %s (estado=%s, %.2fs)", cod, data.get("estadoDoc"), elapsed)
                return data
            log.info("Consulta pública MH: %s respondió sin documento válido (action=%r, %.2fs)", cod, data.get("action"), elapsed)
            return None
        except requests.exceptions.Timeout:
            elapsed = round(time.monotonic() - t1, 2)
            log.warning("Consulta pública MH: TIMEOUT para %s tras %.2fs (límite %ds)", cod, elapsed, _TIMEOUT)
            return None
        except requests.exceptions.HTTPError as exc:
            elapsed = round(time.monotonic() - t1, 2)
            log.warning("Consulta pública MH: HTTP %s para %s tras %.2fs", getattr(exc.response, "status_code", "?"), cod, elapsed)
            return None
        except Exception as exc:
            elapsed = round(time.monotonic() - t1, 2)
            log.warning("Consulta pública MH falló para %s tras %.2fs: %s", cod, elapsed, exc)
            return None
