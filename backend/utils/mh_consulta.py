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
así que sin control saturaría el cupo que Hacienda da a nuestra IP — las
consultas se espacian a una cada _INTERVALO_S segundos para toda la
instancia (ver "Ritmo de consultas" abajo). Si el servicio no
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
import os
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

# ── Ritmo de consultas ──────────────────────────────────────────────────────
# Hacienda aplica un tope de tasa a la IP que consulta: pasan ~15 consultas
# seguidas y después responde 429 durante ~5 minutos. Lo que decide si se llega
# al tope es el RITMO (consultas por minuto), no la concurrencia.
#
# Evidencia (9-oct-2026, 51 consultas reales de un mismo lote, hechas desde un
# navegador, una a la vez):
#   · Con ~1 s de pausa entre consultas pasaron 15, 15 y 14, y cada grupo fue
#     seguido de ~5 min de 429 (3 documentos × 6 reintentos con espera
#     creciente, ~105 s cada uno).
#   · Con 4 s entre consultas pasaron 51 de 51, sin un solo 429.
# Eso explica los lotes de 96 PDFs ya registrados: con concurrencia 5 o con 2
# pasaban siempre ~15 en los primeros segundos, porque ambas configuraciones
# superan el ritmo por igual — bajar la concurrencia no cambiaba nada. Lo que
# no se había probado era el espaciado entre consultas.
#
# Por eso: una consulta cada _INTERVALO_S, global a la instancia. Un documento
# espera su turno hasta _ESPERA_MAX_S; si la fila ya es más larga, se omite la
# consulta y el documento sigue con regex/Visión/IA, igual que si Hacienda no
# hubiera respondido.
#
# Ojo: la evidencia es de una IP residencial. En Railway hay que confirmarlo en
# los logs ("Consulta pública MH ... OK" vs "TOPE de tasa") y, si hace falta,
# ajustar con las variables de entorno sin tocar código.
def _leer_float(nombre: str, defecto: float) -> float:
    try:
        return float(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


_INTERVALO_S    = _leer_float("MH_CONSULTA_INTERVALO_S", 5.0)    # 12 por minuto
_ESPERA_MAX_S   = _leer_float("MH_CONSULTA_ESPERA_MAX_S", 12.0)  # ~3 documentos en fila
_COOLDOWN_429_S = _leer_float("MH_CONSULTA_COOLDOWN_429_S", 300.0)

# Los tests reemplazan estos dos por un reloj falso.
_ahora, _dormir = time.monotonic, time.sleep

_ritmo_lock = threading.Lock()
_proximo_turno = 0.0


def _reservar_turno() -> float | None:
    """Segundos a esperar para consultar a Hacienda, o None (sin reservar nada)
    si la fila ya supera _ESPERA_MAX_S."""
    global _proximo_turno
    with _ritmo_lock:
        ahora = _ahora()
        turno = max(ahora, _proximo_turno)
        if turno - ahora > _ESPERA_MAX_S:
            return None
        _proximo_turno = turno + _INTERVALO_S
        return turno - ahora


# ── Circuit breaker ──────────────────────────────────────────────────────
_FALLOS_CONSECUTIVOS_MAX = 4
_CIRCUITO_COOLDOWN = 60  # segundos que se deja de intentar tras abrir el circuito

_estado_lock = threading.Lock()
_fallos_consecutivos = 0
_circuito_abierto_hasta = 0.0


def _circuito_abierto() -> bool:
    with _estado_lock:
        return _ahora() < _circuito_abierto_hasta


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
        if _fallos_consecutivos >= _FALLOS_CONSECUTIVOS_MAX and _ahora() >= _circuito_abierto_hasta:
            _circuito_abierto_hasta = _ahora() + _CIRCUITO_COOLDOWN
            log.warning(
                "Consulta pública MH: circuito ABIERTO tras %d fallos seguidos — "
                "se omite esta consulta por %ds (Hacienda parece caída/degradada)",
                _fallos_consecutivos, _CIRCUITO_COOLDOWN,
            )


def _abrir_circuito_por_tope(retry_after: str | None) -> None:
    """Un 429 es el tope de tasa de Hacienda dicho explícitamente: no hace falta
    esperar varios fallos para abrir el circuito, y el bloqueo dura minutos
    (~5 en lo observado), así que se respeta Retry-After si viene y, si no,
    _COOLDOWN_429_S. Seguir insistiendo no lo acorta."""
    global _circuito_abierto_hasta
    try:
        espera = min(float(retry_after), 900.0) if retry_after else _COOLDOWN_429_S
    except ValueError:  # Retry-After también puede venir como fecha HTTP
        espera = _COOLDOWN_429_S
    with _estado_lock:
        _circuito_abierto_hasta = max(_circuito_abierto_hasta, _ahora() + espera)
    log.warning("Consulta pública MH: circuito ABIERTO por tope de tasa (429) — se omite por %.0fs", espera)


# Hacienda usa varios textos distintos para "documento aceptado" según el
# tipo de DTE/consulta — confirmado con logs reales de producción:
# "Transmitido Satisfactoriamente" es el estado SANO más común (no
# "Procesado" como se asumió al principio sin verificar contra datos reales;
# ese supuesto causó que TODO documento aceptado se marcara como alerta
# falsa — 15/96 documentos terminaron en REVISION_MANUAL con un mensaje que
# literalmente decía "documento TRANSMITIDO SATISFACTORIAMENTE" como si
# fuera un problema). En vez de adivinar la lista completa de estados
# "buenos" (arriesgado: un valor sano no contemplado volvería a producir
# falsos positivos), se usa una lista de palabras clave que SÍ son
# inequívocamente un problema — cualquier otra cosa (incluida cualquier
# variante de "sano" no vista todavía) no genera alerta.
_ESTADO_DOC_PROBLEMA = ("RECHAZ", "INVALID", "ANULA")


def verificar_cliente_en_consulta_mh(
    consulta_mh: dict | None, cliente_activo: dict, rol_esperado: str,
) -> tuple[bool, str] | None:
    """
    ¿El cliente activo aparece en el rol que le corresponde ("emisor" o
    "receptor"), según el documento oficial que devuelve esta consulta?

    Es la fuente más confiable posible para esto: `documento.emisor` /
    `documento.receptor` vienen tal como Hacienda los tiene registrados
    (mismos campos que schemas/dte_hacienda.py), no hay que adivinarlos de
    un PDF cuyo layout varía de un emisor a otro — el regex de
    dte_layout.verificar_cliente_en_documento ya se topó con al menos dos
    formatos reales (columnas con NIT+NRC intercalados, y facturación por
    cuenta de terceros vía un procesador de pagos) donde el emisor/receptor
    no caen en una sola línea parejita y esa detección no tiene con qué
    trabajar.

    Devuelve `None` (no concluyente, que quien llama recurra al chequeo por
    texto) cuando: no hay consulta, el documento no trae emisor/receptor,
    el cliente activo no tiene ningún NIT/NRC/DUI cargado para comparar, o
    ninguno de los dos lados calza — ahí no se afirma "ausente" porque el
    directorio podría tener el identificador en otro formato que Hacienda.
    Solo devuelve una respuesta firme cuando hay una coincidencia real,
    en el rol esperado o en el contrario.
    """
    documento = (consulta_mh or {}).get("documento") or {}
    emisor = documento.get("emisor") or {}
    receptor = documento.get("receptor") or {}
    if not emisor and not receptor:
        return None

    identificadores = {
        campo: re.sub(r"[^0-9]", "", str(cliente_activo.get(campo, "") or ""))
        for campo in ("nrc", "nit", "dui")
    }
    identificadores = {k: v for k, v in identificadores.items() if v}
    if not identificadores:
        return None

    def _coincide(lado: dict) -> bool:
        for campo, valor in identificadores.items():
            crudo = re.sub(r"[^0-9]", "", str(lado.get(campo, "") or ""))
            if crudo and crudo == valor:
                return True
        return False

    rol_contrario   = "receptor" if rol_esperado == "emisor" else "emisor"
    lado_esperado   = emisor if rol_esperado == "emisor" else receptor
    lado_contrario  = receptor if rol_esperado == "emisor" else emisor

    if _coincide(lado_esperado):
        return True, ""
    if _coincide(lado_contrario):
        return False, f"aparece como {rol_contrario}, no como {rol_esperado} (confirmado por Hacienda)"
    return None


def estado_doc_alerta(consulta_mh: dict | None) -> str | None:
    """
    Si la consulta MH trae un estadoDoc que indica un problema real
    (Rechazado, Invalidado, Anulado — por prefijo, tolera variantes como
    "Rechazado por Contingencia"), arma un mensaje de alerta listo para
    gemini_correcciones/detalle_confianza. None si no hay nada que alertar
    (sin consulta, estadoDoc vacío, o cualquier estado que no matchee un
    problema conocido — incluye "Transmitido Satisfactoriamente" y
    cualquier otro estado sano no listado explícitamente).
    """
    if not consulta_mh:
        return None
    estado = str(consulta_mh.get("estadoDoc") or "").strip()
    if not estado:
        return None
    estado_up = estado.upper()
    if not any(palabra in estado_up for palabra in _ESTADO_DOC_PROBLEMA):
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

    espera = _reservar_turno()
    if espera is None:
        log.info("Consulta pública MH: fila de espera > %.0fs — se omite %s (sigue con regex/Visión)", _ESPERA_MAX_S, cod)
        return None
    if espera > 0:
        log.info("Consulta pública MH %s espera %.1fs su turno (1 consulta cada %.1fs)", cod, espera, _INTERVALO_S)
        _dormir(espera)
        if _circuito_abierto():  # Hacienda puso tope mientras este documento esperaba
            log.info("Consulta pública MH: circuito abierto mientras esperaba — se omite %s", cod)
            return None

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
            _abrir_circuito_por_tope(resp.headers.get("Retry-After"))
            return None
        resp.raise_for_status()
        data = resp.json()
        if data.get("action") == "OK" and isinstance(data.get("documento"), dict):
            log.info("Consulta pública MH OK para %s (estado=%s, %.2fs)", cod, data.get("estadoDoc"), elapsed)
            _registrar_resultado(True)
            return data
        # Hacienda respondió (no es una caída del servicio), pero con
        # action != "OK" — puede ser simplemente que el documento no
        # existe/no se encontró, O puede traer un estadoDoc real y
        # valioso (p. ej. "Rechazado": el documento se transmitió pero
        # Hacienda lo rechazó por no cumplir estructura/parámetros —
        # confirmado con un caso real: action="ERROR" pero
        # estadoDoc="Rechazado" con descripcionEstado explicando el
        # motivo). Descartar esto en silencio escondía justo la
        # información que un usuario iría a buscar manualmente
        # escaneando el QR — se devuelve igual para que el extractor
        # pueda marcarlo como alerta en vez de tratarlo como "no
        # encontrado, seguir con regex/Visión sin más".
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
