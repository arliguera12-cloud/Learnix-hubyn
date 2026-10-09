"""
Pruebas del ritmo y del circuito de utils/mh_consulta.py — sin red: reloj falso
y `requests.get` simulado.

Cubren lo que decidió el cambio de "limitar concurrencia" a "espaciar
consultas": Hacienda corta con 429 por ~5 min al pasar de ~15 consultas
seguidas, y lo que lo evita es el ritmo, no cuántas van en paralelo.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import mh_consulta as mh  # noqa: E402

COD = "EF2823DF-8DB6-4F6C-9129-2BDDBF160AAF"
FECHA = "2026-09-14"
DOC_OK = {"action": "OK", "estadoDoc": "Transmitido Satisfactoriamente", "documento": {"resumen": {}}}

fallos = []
_ahora_real, _dormir_real = mh._ahora, mh._dormir


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def ahora(self):
        return self.t

    def dormir(self, segundos):
        self.t += segundos


def resp(status=200, cuerpo=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.json.return_value = cuerpo or {}
    return r


def escenario(intervalo=5.0, espera_max=12.0, cooldown=300.0):
    """Estado limpio del módulo con reloj falso."""
    reloj = Reloj()
    mh._ahora, mh._dormir = reloj.ahora, reloj.dormir
    mh._INTERVALO_S, mh._ESPERA_MAX_S, mh._COOLDOWN_429_S = intervalo, espera_max, cooldown
    mh._proximo_turno = 0.0
    mh._fallos_consecutivos = 0
    mh._circuito_abierto_hasta = 0.0
    return reloj


def caso(nombre, fn, esperado):
    try:
        obtenido = fn()
        ok = obtenido == esperado
        detalle = repr(obtenido)[:70]
    except Exception as exc:
        ok, detalle = False, f"{type(exc).__name__}: {exc}"
    print(f"{'PASA ' if ok else 'FALLA'}  {nombre:<58} → {detalle}")
    if not ok:
        fallos.append(nombre)


# ── Ritmo ──────────────────────────────────────────────────────────────────
def _cuatro_simultaneas():
    escenario()
    return [mh._reservar_turno() for _ in range(4)]


caso("4 documentos a la vez: turnos 0, 5, 10 y el 4º se omite",
     _cuatro_simultaneas, [0.0, 5.0, 10.0, None])


def _fila_se_libera():
    reloj = escenario()
    for _ in range(3):
        mh._reservar_turno()
    reloj.t += 20
    return mh._reservar_turno()


caso("pasado el tiempo, la fila se libera", _fila_se_libera, 0.0)


def _omitido_no_llama_a_hacienda():
    escenario(espera_max=6.0)
    mh._reservar_turno(), mh._reservar_turno()          # turnos 0 y 5
    with patch.object(mh.requests, "get") as get:
        resultado = mh.consultar_dte_publico(COD, FECHA)  # le tocaría esperar 10 > 6
        return resultado, get.call_count


caso("fila más larga que el máximo: no consulta", _omitido_no_llama_a_hacienda, (None, 0))


def _espera_su_turno():
    reloj = escenario()
    mh._reservar_turno()                                 # ocupa el turno 0
    with patch.object(mh.requests, "get", return_value=resp(cuerpo=DOC_OK)):
        mh.consultar_dte_publico(COD, FECHA)
    return reloj.t - 1000.0


caso("el segundo documento duerme 5 s antes de consultar", _espera_su_turno, 5.0)

# ── Consulta ───────────────────────────────────────────────────────────────
caso("UUID inválido: no consulta",
     lambda: (escenario(), mh.consultar_dte_publico("no-es-uuid", FECHA))[1], None)


def _respuesta_ok():
    escenario()
    with patch.object(mh.requests, "get", return_value=resp(cuerpo=DOC_OK)) as get:
        data = mh.consultar_dte_publico(COD.lower(), FECHA)
        params = get.call_args.kwargs["params"]
    return data["estadoDoc"], params["codigoGeneracion"], params["fechaEmi"]


caso("respuesta OK: normaliza el UUID y devuelve el documento",
     _respuesta_ok, ("Transmitido Satisfactoriamente", COD, FECHA))


def _rechazado_se_conserva():
    escenario()
    cuerpo = {"action": "ERROR", "estadoDoc": "Rechazado", "descripcionEstado": "estructura"}
    with patch.object(mh.requests, "get", return_value=resp(cuerpo=cuerpo)):
        return mh.consultar_dte_publico(COD, FECHA)["estadoDoc"]


caso("action=ERROR con estadoDoc=Rechazado se devuelve (alerta)", _rechazado_se_conserva, "Rechazado")

# ── Circuito ───────────────────────────────────────────────────────────────
def _tope_429(retry_after, avance):
    """Tras un 429, ¿se vuelve a consultar `avance` segundos después?"""
    reloj = escenario()
    headers = {"Retry-After": retry_after} if retry_after else {}
    with patch.object(mh.requests, "get", side_effect=[resp(429, headers=headers), resp(cuerpo=DOC_OK)]) as get:
        mh.consultar_dte_publico(COD, FECHA)
        reloj.t += avance
        mh.consultar_dte_publico(COD, FECHA)
        return get.call_count


caso("429 con Retry-After=120: a los 100 s sigue sin consultar", lambda: _tope_429("120", 100), 1)
caso("429 con Retry-After=120: a los 130 s vuelve a consultar", lambda: _tope_429("120", 130), 2)
caso("429 sin Retry-After: a los 290 s sigue cerrado (~5 min)", lambda: _tope_429(None, 290), 1)
caso("429 sin Retry-After: a los 310 s vuelve a consultar", lambda: _tope_429(None, 310), 2)
caso("Retry-After como fecha HTTP: usa el cooldown por defecto",
     lambda: _tope_429("Wed, 21 Oct 2026 07:28:00 GMT", 290), 1)


def _cuatro_timeouts():
    escenario(intervalo=0.0)
    with patch.object(mh.requests, "get", side_effect=requests.exceptions.Timeout()) as get:
        for _ in range(6):
            mh.consultar_dte_publico(COD, FECHA)
        return get.call_count


caso("4 timeouts seguidos abren el circuito (el 5º y 6º no consultan)", _cuatro_timeouts, 4)

mh._ahora, mh._dormir = _ahora_real, _dormir_real
print()
print("TODOS LOS CASOS PASAN" if not fallos else f"FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
