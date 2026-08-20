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
subió (mismo volumen que una consulta manual real hecha a mano), nunca en
bucles de scraping. Si el servicio no responde, cambia de forma o el
documento no existe, se degrada en silencio al pipeline normal
(regex + Vision + IA) — nunca bloquea ni retrasa la extracción más que el
timeout configurado.
"""
from __future__ import annotations

import logging
import re

import requests

log = logging.getLogger(__name__)

_URL = "https://admin.factura.gob.sv/prod/consultas/publica/simple/1"
_TIMEOUT = 8  # segundos — no vale la pena esperar más por un dato opcional

_UUID_RE  = re.compile(r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$')
_FECHA_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


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
        return None

    try:
        resp = requests.get(
            _URL,
            params={"codigoGeneracion": cod, "fechaEmi": fecha, "ambiente": ambiente},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("action") == "OK" and isinstance(data.get("documento"), dict):
            return data
        return None
    except Exception as exc:
        log.debug("Consulta pública MH falló para %s: %s", cod, exc)
        return None
