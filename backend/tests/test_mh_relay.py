"""
Pruebas del modo relay (utils/mh_relay.py + routers/mh_relay.py) — sin red ni
Supabase: la cola se simula en memoria y el reloj es falso.

Las funciones SQL de la cola (db/12_mh_consulta_cola.sql) no se prueban acá;
se probaron aparte contra un Postgres real (ver README del worker).
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from middleware import rate_limit  # noqa: E402
from routers import mh_relay as router_relay  # noqa: E402
from utils import mh_consulta, mh_relay as mr  # noqa: E402

COD = "EF2823DF-8DB6-4F6C-9129-2BDDBF160AAF"
FECHA = "2026-09-14"
DOC = {"action": "OK", "estadoDoc": "Transmitido Satisfactoriamente",
       "documento": {"identificacion": {"codigoGeneracion": COD}, "resumen": {}}}
TOKEN = "t" * 40

fallos = []


class Reloj:
    def __init__(self):
        self.t = 1000.0
        self.al_dormir = None  # gancho: lo que "pasa" mientras el extractor espera

    def ahora(self):
        return self.t

    def dormir(self, s):
        self.t += s
        if self.al_dormir:
            self.al_dormir()


class Cola:
    """Cola en memoria con la misma semántica que las funciones SQL."""

    def __init__(self):
        self.filas = {}

    def encolar(self, cod, fecha, amb):
        self.filas.setdefault((cod, fecha, amb), {"estado": "pendiente", "resultado": None, "intentos": 0,
                                                  "codigo_generacion": cod, "fecha_emi": fecha, "ambiente": amb})
        return dict(self.filas[(cod, fecha, amb)])

    def leer(self, cod, fecha, amb):
        f = self.filas.get((cod, fecha, amb))
        return dict(f) if f else None

    def reclamar(self, n):
        out = []
        for f in self.filas.values():
            if f["estado"] == "pendiente" and len(out) < n:
                f["estado"] = "procesando"
                out.append(dict(f))
        return out

    def actualizar(self, cod, fecha, amb, cambios):
        f = self.filas.get((cod, fecha, amb))
        if f and f["estado"] == "procesando":
            f.update({k: v for k, v in cambios.items() if k != "actualizado_en"})


def escenario(poner=None):
    """Estado limpio: cola vacía, reloj falso, worker sin latido."""
    reloj, cola = Reloj(), Cola()
    mr._ahora, mr._dormir = reloj.ahora, reloj.dormir
    mr._ultimo_latido = 0.0
    mr._db_encolar, mr._db_leer = cola.encolar, cola.leer
    mr._db_reclamar, mr._db_actualizar = cola.reclamar, cola.actualizar
    os.environ.pop("MH_RELAY_ESPERA_S", None)
    os.environ.pop("MH_RELAY_VIVO_S", None)
    if poner:
        cola.filas[(COD, FECHA, "01")] = {"codigo_generacion": COD, "fecha_emi": FECHA, "ambiente": "01",
                                          "resultado": None, "intentos": 0, **poner}
    return reloj, cola


def caso(nombre, fn, esperado):
    try:
        obtenido = fn()
        ok = obtenido == esperado
        detalle = repr(obtenido)[:70]
    except Exception as exc:
        ok, detalle = False, f"{type(exc).__name__}: {exc}"
    print(f"{'PASA ' if ok else 'FALLA'}  {nombre:<62} → {detalle}")
    if not ok:
        fallos.append(nombre)


# ── Lado extractor ──────────────────────────────────────────────────────────
def _cache_ok():
    reloj, _ = escenario({"estado": "ok", "resultado": DOC})
    r = mr.consultar_via_relay(COD, FECHA)
    return r["estadoDoc"], reloj.t - 1000.0   # sin worker y sin esperar


caso("verificación ya guardada: se sirve al instante", _cache_ok, ("Transmitido Satisfactoriamente", 0.0))


def _sin_worker():
    reloj, cola = escenario()
    return mr.consultar_via_relay(COD, FECHA), reloj.t - 1000.0, cola.leer(COD, FECHA, "01")["estado"]


caso("worker sin señales: no espera y deja el DTE en cola", _sin_worker, (None, 0.0, "pendiente"))


def _worker_responde():
    reloj, cola = escenario()
    mr.registrar_latido()
    n = {"v": 0}

    def al_dormir():
        n["v"] += 1
        mr.registrar_latido()
        if n["v"] == 3:   # el worker termina al tercer sondeo (~9 s)
            cola.filas[(COD, FECHA, "01")].update(estado="ok", resultado=DOC)
    reloj.al_dormir = al_dormir
    r = mr.consultar_via_relay(COD, FECHA)
    return r["estadoDoc"], reloj.t - 1000.0


caso("worker vivo: espera su turno y devuelve el documento", _worker_responde,
     ("Transmitido Satisfactoriamente", 9.0))


def _worker_no_termina():
    reloj, _ = escenario()
    mr.registrar_latido()
    reloj.al_dormir = mr.registrar_latido
    r = mr.consultar_via_relay(COD, FECHA)
    return r, 60.0 <= reloj.t - 1000.0 <= 63.0


caso("worker vivo pero lento: se rinde a los ~60 s (sigue sin Hacienda)", _worker_no_termina, (None, True))

caso("Hacienda dijo no encontrado: None",
     lambda: (escenario({"estado": "no_encontrado"}), mr.consultar_via_relay(COD, FECHA))[1], None)


def _db_caida():
    escenario()
    mr._db_encolar = lambda *a: (_ for _ in ()).throw(RuntimeError("supabase caído"))
    return mr.consultar_via_relay(COD, FECHA)


caso("base de datos caída: devuelve None, no lanza", _db_caida, None)


def _latido():
    reloj, _ = escenario()
    a = mr.worker_vivo()
    mr.registrar_latido()
    b = mr.worker_vivo()
    reloj.t += 44
    c = mr.worker_vivo()
    reloj.t += 2
    return a, b, c, mr.worker_vivo()


caso("latido: vivo hasta 45 s sin señal", _latido, (False, True, True, False))

# ── Decisión de estado ──────────────────────────────────────────────────────
caso("200 con documento → ok", lambda: mr.decidir_estado(200, DOC, 0), ("ok", 0))
caso("200 con estadoDoc Rechazado → ok (se conserva la alerta)",
     lambda: mr.decidir_estado(200, {"action": "ERROR", "estadoDoc": "Rechazado"}, 0), ("ok", 0))
caso("200 sin documento ni estado → no_encontrado",
     lambda: mr.decidir_estado(200, {"action": "ERROR"}, 0), ("no_encontrado", 0))
caso("404 → no_encontrado", lambda: mr.decidir_estado(404, None, 0), ("no_encontrado", 0))
caso("429 / 403 / 0 → pendiente sin gastar intento",
     lambda: [mr.decidir_estado(s, None, 2) for s in (429, 403, 0)], [("pendiente", 2)] * 3)
caso("500 → pendiente y cuenta intento", lambda: mr.decidir_estado(500, None, 1), ("pendiente", 2))
caso("quinto fallo → error", lambda: mr.decidir_estado(500, None, 4), ("error", 5))

# ── guardar_resultado ───────────────────────────────────────────────────────
def _guardar_ok():
    _, cola = escenario({"estado": "procesando"})
    est = mr.guardar_resultado(COD, FECHA, "01", 200, DOC)
    return est, cola.leer(COD, FECHA, "01")["resultado"] == DOC


caso("resultado válido de un trabajo en proceso se guarda", _guardar_ok, ("ok", True))


def _rechaza(**kw):
    try:
        mr.guardar_resultado(**kw)
        return "aceptado"
    except ValueError as exc:
        return "rechazado"


base = dict(cod=COD, fecha=FECHA, ambiente="01", http_status=200, cuerpo=DOC)
caso("rechaza un trabajo que no está en proceso",
     lambda: (escenario({"estado": "pendiente"}), _rechaza(**base))[1], "rechazado")
caso("rechaza si no existe en la cola", lambda: (escenario(), _rechaza(**base))[1], "rechazado")
caso("rechaza cuerpo de otro código de generación",
     lambda: (escenario({"estado": "procesando"}),
              _rechaza(**{**base, "cuerpo": {"documento": {"identificacion": {"codigoGeneracion": "0" * 8 + COD[8:]}}}}))[1],
     "rechazado")
caso("rechaza UUID con formato inválido",
     lambda: (escenario({"estado": "procesando"}), _rechaza(**{**base, "cod": "no-es-uuid"}))[1], "rechazado")
caso("rechaza cuerpo gigante",
     lambda: (escenario({"estado": "procesando"}), _rechaza(**{**base, "cuerpo": {"x": "a" * 600_000}}))[1],
     "rechazado")

# ── Gancho en consultar_dte_publico ─────────────────────────────────────────
def _gancho(modo):
    if modo is None:
        os.environ.pop("MH_CONSULTA_MODO", None)
    else:
        os.environ["MH_CONSULTA_MODO"] = modo
    with patch.object(mr, "consultar_via_relay", return_value={"via": "relay"}) as relay, \
         patch.object(mh_consulta.requests, "get", side_effect=RuntimeError("no debe llamarse")) as get:
        try:
            r = mh_consulta.consultar_dte_publico(COD, FECHA)
        except RuntimeError:
            r = "llamó a Hacienda"
        return r, relay.call_count, get.call_count


caso("MH_CONSULTA_MODO=relay: delega en el relay, no llama a Hacienda", lambda: _gancho("relay"),
     ({"via": "relay"}, 1, 0))
caso("sin MH_CONSULTA_MODO: modo directo (no usa el relay)",
     lambda: _gancho(None)[1:], (0, 1))
os.environ.pop("MH_CONSULTA_MODO", None)

# ── Endpoints ───────────────────────────────────────────────────────────────
app = FastAPI()
app.include_router(router_relay.router, prefix="/mh-relay")
cliente = TestClient(app)
H = {"X-Relay-Token": TOKEN}


def con_token(valor):
    if valor is None:
        os.environ.pop("MH_RELAY_TOKEN", None)
    else:
        os.environ["MH_RELAY_TOKEN"] = valor
    rate_limit._por_clave.clear()


caso("sin MH_RELAY_TOKEN configurado: 503 (no queda abierto)",
     lambda: (con_token(None), cliente.get("/mh-relay/ping", headers=H).status_code)[1], 503)
caso("MH_RELAY_TOKEN demasiado corto: 503",
     lambda: (con_token("corto"), cliente.get("/mh-relay/ping", headers={"X-Relay-Token": "corto"}).status_code)[1], 503)
caso("sin encabezado de token: 401",
     lambda: (con_token(TOKEN), cliente.get("/mh-relay/ping").status_code)[1], 401)
caso("token incorrecto: 401",
     lambda: (con_token(TOKEN), cliente.get("/mh-relay/ping", headers={"X-Relay-Token": "x" * 40}).status_code)[1], 401)


def _fuerza_bruta():
    con_token(TOKEN)
    codigos = [cliente.get("/mh-relay/ping", headers={"X-Relay-Token": "x" * 40}).status_code for _ in range(12)]
    return codigos[:10] == [401] * 10, codigos[10:], cliente.get("/mh-relay/ping", headers=H).status_code


caso("fuerza bruta: tras 10 fallos por minuto, 429", _fuerza_bruta, (True, [429, 429], 200))
caso("token correcto: ping 200", lambda: (con_token(TOKEN), cliente.get("/mh-relay/ping", headers=H).status_code)[1], 200)


def _flujo_completo():
    con_token(TOKEN)
    _, cola = escenario()
    cola.encolar(COD, FECHA, "01")
    r1 = cliente.post("/mh-relay/reclamar", json={"max": 3}, headers=H).json()
    r2 = cliente.post("/mh-relay/resultado", headers=H, json={
        "codigo_generacion": COD.lower(), "fecha_emi": FECHA, "http_status": 200, "cuerpo": DOC}).json()
    return r1, r2


caso("reclamar → resultado: el worker completa un trabajo", _flujo_completo,
     ({"trabajos": [{"codigo_generacion": COD, "fecha_emi": FECHA, "ambiente": "01"}]}, {"estado": "ok"}))


def _resultado_sin_reclamar():
    con_token(TOKEN)
    _, cola = escenario()
    cola.encolar(COD, FECHA, "01")
    return cliente.post("/mh-relay/resultado", headers=H, json={
        "codigo_generacion": COD, "fecha_emi": FECHA, "http_status": 200, "cuerpo": DOC}).status_code


caso("resultado de un trabajo que no se reclamó: 422", _resultado_sin_reclamar, 422)
caso("reclamar con max=9: 422 (validación)",
     lambda: (con_token(TOKEN), cliente.post("/mh-relay/reclamar", json={"max": 9}, headers=H).status_code)[1], 422)

con_token(None)
print()
print("TODOS LOS CASOS PASAN" if not fallos else f"FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
