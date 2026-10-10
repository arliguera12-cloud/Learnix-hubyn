"""
Pruebas del worker — sin red: backend y Hacienda simulados, reloj falso.
    python test_mh_worker.py
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mh_worker as w  # noqa: E402

COD = "EF2823DF-8DB6-4F6C-9129-2BDDBF160AAF"
DOC = {"action": "OK", "estadoDoc": "Transmitido Satisfactoriamente", "documento": {}}
fallos = []


class Reloj:
    def __init__(self):
        self.t = 1000.0
        self.dormidos = []

    def ahora(self):
        return self.t

    def dormir(self, s):
        self.dormidos.append(round(s, 2))
        self.t += s


def resp(status=200, cuerpo=None, headers=None):
    r = MagicMock()
    r.status_code, r.headers, r.text = status, headers or {}, ""
    r.json.return_value = cuerpo if cuerpo is not None else {}
    return r


def cfg_prueba():
    for k in ("MH_WORKER_INTERVALO_S", "MH_WORKER_ESPERA_S", "MH_WORKER_PAUSA_429_S", "MH_WORKER_PAUSA_403_S"):
        os.environ.pop(k, None)
    os.environ["LEARNIX_URL"] = "https://learnix.example/"
    os.environ["MH_RELAY_TOKEN"] = "t" * 40
    return w.Config()


def entorno():
    reloj = Reloj()
    w._ahora, w._dormir = reloj.ahora, reloj.dormir
    w._ultima_consulta = 0.0
    return reloj, cfg_prueba()


def trabajos(n):
    return [{"codigo_generacion": COD[:-1] + str(i), "fecha_emi": "2026-09-14", "ambiente": "01"} for i in range(n)]


def caso(nombre, fn, esperado):
    try:
        obtenido = fn()
        ok = obtenido == esperado
        detalle = repr(obtenido)[:80]
    except Exception as exc:
        ok, detalle = False, f"{type(exc).__name__}: {exc}"
    print(f"{'PASA ' if ok else 'FALLA'}  {nombre:<58} → {detalle}")
    if not ok:
        fallos.append(nombre)


def _ritmo():
    reloj, cfg = entorno()
    marcas = []

    def get(*a, **k):
        marcas.append(reloj.t)
        return resp(200, DOC)
    with patch.object(w.requests, "get", side_effect=get), patch.object(w.requests, "request", return_value=resp(200)):
        pausa = w.procesar_lote(cfg, trabajos(3))
    return [round(b - a, 1) for a, b in zip(marcas, marcas[1:])], pausa


caso("3 consultas seguidas van separadas 4.5 s", _ritmo, ([4.5, 4.5], 0.0))


def _envia_cuerpo():
    reloj, cfg = entorno()
    with patch.object(w.requests, "get", return_value=resp(200, DOC)), \
         patch.object(w.requests, "request", return_value=resp(200)) as req:
        w.procesar_lote(cfg, trabajos(1))
        _, url = req.call_args.args[:2]
        j = req.call_args.kwargs["json"]
        return url, j["http_status"], j["cuerpo"] == DOC, req.call_args.kwargs["headers"]["X-Relay-Token"] == "t" * 40


caso("devuelve al backend lo que dijo Hacienda, con el token",
     _envia_cuerpo, ("https://learnix.example/mh-relay/resultado", 200, True, True))


def _tope_429():
    reloj, cfg = entorno()
    enviados = []
    with patch.object(w.requests, "get", return_value=resp(429, headers={"Retry-After": "120"})) as get, \
         patch.object(w.requests, "request", side_effect=lambda m, u, **k: (enviados.append(k["json"]["http_status"]), resp(200))[1]):
        pausa = w.procesar_lote(cfg, trabajos(3))
        return pausa, get.call_count, enviados


caso("429: pausa el Retry-After, no insiste y libera el resto", _tope_429, (120.0, 1, [429, 0, 0]))


def _bloqueo_403():
    reloj, cfg = entorno()
    with patch.object(w.requests, "get", return_value=resp(403)), patch.object(w.requests, "request", return_value=resp(200)):
        return w.procesar_lote(cfg, trabajos(2))


caso("403: pausa larga (900 s)", _bloqueo_403, 900.0)


def _no_encontrado():
    reloj, cfg = entorno()
    with patch.object(w.requests, "get", return_value=resp(404)), patch.object(w.requests, "request", return_value=resp(200)):
        return w.procesar_lote(cfg, trabajos(1))


caso("404: se informa y sigue sin pausa", _no_encontrado, 0.0)


def _red_hacienda():
    reloj, cfg = entorno()
    with patch.object(w.requests, "get", side_effect=requests.exceptions.ConnectionError("sin red")), \
         patch.object(w.requests, "request", return_value=resp(200)):
        return w.procesar_lote(cfg, trabajos(1))


caso("sin red hacia Hacienda: pausa corta (30 s)", _red_hacienda, 30.0)


def _sin_trabajo():
    reloj, cfg = entorno()
    with patch.object(w.requests, "request", return_value=resp(200, {"trabajos": []})):
        w.bucle(cfg, ciclos=2)
    return reloj.dormidos


caso("sin trabajos: espera 4 s entre preguntas", _sin_trabajo, [4.0, 4.0])


def _backend_caido():
    reloj, cfg = entorno()
    with patch.object(w.requests, "request", side_effect=requests.exceptions.ConnectionError("x")):
        w.bucle(cfg, ciclos=3)
    return reloj.dormidos


caso("backend caído: reintentos 10 s, 20 s, 30 s", _backend_caido, [10.0, 20.0, 30.0])


def _token_malo():
    reloj, cfg = entorno()
    with patch.object(w.requests, "request", return_value=resp(401)):
        return w.reclamar(cfg), reloj.dormidos


caso("token rechazado (401): espera 60 s y no cae", _token_malo, (None, [60.0]))


def _backend_limita():
    reloj, cfg = entorno()
    with patch.object(w.requests, "request", return_value=resp(429, headers={"Retry-After": "45"})):
        return w.reclamar(cfg), reloj.dormidos


caso("el backend responde 429: respeta su Retry-After", _backend_limita, (None, [45.0]))


def _resultado_reintenta():
    reloj, cfg = entorno()
    with patch.object(w.requests, "request", side_effect=requests.exceptions.ConnectionError("x")) as req:
        return w.enviar_resultado(cfg, trabajos(1)[0], 200, DOC), req.call_count


caso("resultado que no llega: 3 intentos y sigue", _resultado_reintenta, (False, 3))


def _resultado_422():
    reloj, cfg = entorno()
    with patch.object(w.requests, "request", return_value=resp(422)) as req:
        return w.enviar_resultado(cfg, trabajos(1)[0], 200, DOC), req.call_count


caso("422 del backend: no reintenta", _resultado_422, (False, 1))


def _probar(token_ok=True, hacienda=200):
    reloj, cfg = entorno()
    with patch.object(w.requests, "request", return_value=resp(200 if token_ok else 401)), \
         patch.object(w.requests, "get", return_value=resp(hacienda, DOC)), patch("builtins.print"):
        return w.probar(cfg)


caso("--probar con todo bien: salida 0", _probar, 0)
caso("--probar con token malo: salida 1", lambda: _probar(token_ok=False), 1)
caso("--probar con Hacienda en 403: salida 1", lambda: _probar(hacienda=403), 1)


def _env():
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "worker.env"
        ruta.write_text('# comentario\nLEARNIX_URL="https://x.example"\n\nMH_RELAY_TOKEN = abc\nSIN_IGUAL\n', encoding="utf-8-sig")
        for k in ("LEARNIX_URL", "MH_RELAY_TOKEN"):
            os.environ.pop(k, None)
        w.cargar_env(ruta)
        return os.environ["LEARNIX_URL"], os.environ["MH_RELAY_TOKEN"]


caso("worker.env: lee valores con comillas, espacios y comentarios", _env, ("https://x.example", "abc"))

print()
print("TODOS LOS CASOS PASAN" if not fallos else f"FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
