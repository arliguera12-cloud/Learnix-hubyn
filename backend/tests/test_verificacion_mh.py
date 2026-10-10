"""
Pruebas de la verificación en segundo plano (modo relay con MH_RELAY_ESPERA_S=0,
marca_mh y POST /procesar/verificacion-mh) — sin red ni Supabase.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from routers import procesamiento  # noqa: E402
from utils import mh_consulta, mh_relay as mr  # noqa: E402
from utils.org_context import get_current_org  # noqa: E402

COD = "EF2823DF-8DB6-4F6C-9129-2BDDBF160AAF"
COD2 = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
FECHA = "2026-09-14"
DOC = {"action": "OK", "estadoDoc": "Transmitido Satisfactoriamente", "documento": {}}
fallos = []


def caso(nombre, fn, esperado):
    try:
        obtenido = fn()
        ok, detalle = obtenido == esperado, repr(obtenido)[:70]
    except Exception as exc:
        ok, detalle = False, f"{type(exc).__name__}: {exc}"
    print(f"{'PASA ' if ok else 'FALLA'}  {nombre:<62} → {detalle}")
    if not ok:
        fallos.append(nombre)


class Cola:
    def __init__(self, filas=None):
        self.filas = filas or {}
        self.t = 1000.0

    def encolar(self, cod, fecha, amb):
        return self.filas.setdefault(cod, {"codigo_generacion": cod, "fecha_emi": fecha, "ambiente": amb,
                                           "estado": "pendiente", "resultado": None})

    def leer(self, cod, fecha, amb):
        return self.filas.get(cod)

    def estados(self, codigos):
        return [{**f, "estadoDoc": (f["resultado"] or {}).get("estadoDoc"),
                 "descripcionEstado": (f["resultado"] or {}).get("descripcionEstado")}
                for c, f in self.filas.items() if c in codigos]


def montar(filas=None):
    cola = Cola(filas)
    mr._ahora, mr._dormir = (lambda: cola.t), (lambda s: setattr(cola, "t", cola.t + s))
    mr._db_encolar, mr._db_leer, mr._db_estados = cola.encolar, cola.leer, cola.estados
    mr._ultimo_latido = 0.0
    return cola


def fila(cod, estado, resultado=None, fecha=FECHA):
    return {"codigo_generacion": cod, "fecha_emi": fecha, "ambiente": "01", "estado": estado, "resultado": resultado}


# ── MH_RELAY_ESPERA_S=0: encola y devuelve None al instante ─────────────────
def _sin_espera():
    cola = montar()
    os.environ["MH_CONSULTA_MODO"], os.environ["MH_RELAY_ESPERA_S"] = "relay", "0"
    mr.registrar_latido()  # worker vivo: con espera normal esperaría hasta 60 s
    r = mh_consulta.consultar_dte_publico(COD, FECHA)
    return r, cola.t - 1000.0, cola.filas[COD]["estado"]


caso("ESPERA_S=0 con worker vivo: encola y devuelve None sin esperar", _sin_espera, (None, 0.0, "pendiente"))


def _cache_con_espera_cero():
    montar({COD: fila(COD, "ok", DOC)})
    return mh_consulta.consultar_dte_publico(COD, FECHA)["estadoDoc"]


caso("ESPERA_S=0: lo ya verificado se sirve de la caché", _cache_con_espera_cero, "Transmitido Satisfactoriamente")

# ── marca_mh ──────────────────────────────────────────────────────
QR = {"codigo_generacion": COD.lower(), "fecha_qr": FECHA}
caso("relay y sin respuesta: marca pendiente con gen y fecha",
     lambda: mh_consulta.marca_mh(QR, None), {"mh_estado": "pendiente", "mh_pendiente": True, "mh_gen": COD, "mh_fecha_qr": FECHA})
caso("relay y Hacienda ya respondió: verificado, sin alerta", lambda: mh_consulta.marca_mh(QR, DOC),
     {"mh_estado": "verificado", "mh_estadoDoc": "Transmitido Satisfactoriamente", "mh_alerta": None})
caso("relay y Hacienda respondió Rechazado: verificado con alerta",
     lambda: mh_consulta.marca_mh(QR, {"estadoDoc": "Rechazado"})["mh_alerta"], "documento RECHAZADO ante Hacienda")
caso("QR sin fecha: sin marca", lambda: mh_consulta.marca_mh({"codigo_generacion": COD}, None), {})
os.environ["MH_CONSULTA_MODO"] = "directo"
caso("modo directo: sin marca (el registro no cambia)", lambda: mh_consulta.marca_mh(QR, None), {})
os.environ["MH_CONSULTA_MODO"] = "relay"

# ── Endpoint ────────────────────────────────────────────────────────────────
app = FastAPI()
app.include_router(procesamiento.router, prefix="/procesar")
cliente = TestClient(app)
URL = "/procesar/verificacion-mh"


def _post(docs):
    app.dependency_overrides[get_current_org] = lambda: {"organizacion_id": "org-1"}
    try:
        return cliente.post(URL, json=docs)
    finally:
        app.dependency_overrides.clear()


def _estados():
    montar({
        COD: fila(COD, "ok", {"estadoDoc": "Rechazado", "descripcionEstado": "Error de estructura"}),
        COD2: fila(COD2, "procesando"),
    })
    mr.registrar_latido()
    r = _post([{"codigo_generacion": COD.lower(), "fecha_emi": FECHA},
               {"codigo_generacion": COD2, "fecha_emi": FECHA},
               {"codigo_generacion": "11111111-2222-3333-4444-555555555555", "fecha_emi": FECHA}]).json()
    d = r["documentos"]
    return r["worker_activo"], d[COD]["estado"], d[COD]["alerta"], d[COD2]["estado"], d["11111111-2222-3333-4444-555555555555"]["estado"]


caso("rechazado → verificado con alerta; en proceso y ausente → pendiente", _estados,
     (True, "verificado", "documento RECHAZADO ante Hacienda — Error de estructura", "pendiente", "pendiente"))


def _sano():
    montar({COD: fila(COD, "ok", DOC)})
    d = _post([{"codigo_generacion": COD, "fecha_emi": FECHA}]).json()["documentos"][COD]
    return d["estado"], d["alerta"]


caso("transmitido: verificado sin alerta", _sano, ("verificado", None))
caso("fecha distinta a la de la cola: sigue pendiente",
     lambda: (montar({COD: fila(COD, "ok", DOC)}),
              _post([{"codigo_generacion": COD, "fecha_emi": "2026-01-01"}]).json()["documentos"][COD]["estado"])[1], "pendiente")
caso("no_encontrado y error se reportan tal cual",
     lambda: (montar({COD: fila(COD, "no_encontrado"), COD2: fila(COD2, "error")}),
              [v["estado"] for v in _post([{"codigo_generacion": COD, "fecha_emi": FECHA},
                                           {"codigo_generacion": COD2, "fecha_emi": FECHA}]).json()["documentos"].values()])[1],
     ["no_encontrado", "error"])
caso("101 documentos: 422",
     lambda: _post([{"codigo_generacion": COD, "fecha_emi": FECHA}] * 101).status_code, 422)
caso("lista vacía: 422", lambda: _post([]).status_code, 422)
caso("código inválido: 422", lambda: _post([{"codigo_generacion": "x", "fecha_emi": FECHA}]).status_code, 422)
caso("sin login de usuario: 401/403",
     lambda: cliente.post(URL, json=[{"codigo_generacion": COD, "fecha_emi": FECHA}]).status_code in (401, 403), True)


def _db_caida():
    def boom(_): raise RuntimeError("caída")
    montar(); mr._db_estados = boom
    return _post([{"codigo_generacion": COD, "fecha_emi": FECHA}]).status_code


caso("base de datos caída: 503", _db_caida, 503)

os.environ.pop("MH_CONSULTA_MODO", None)
os.environ.pop("MH_RELAY_ESPERA_S", None)
if fallos:
    print(f"\n{len(fallos)} CASO(S) FALLAN")
    sys.exit(1)
print("\nTODOS LOS CASOS PASAN")
