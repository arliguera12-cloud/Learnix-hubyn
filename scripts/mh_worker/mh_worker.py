"""
mh_worker.py — Worker de consultas a Hacienda para Learnix.

Corre en un equipo con salida a internet desde El Salvador (Hacienda bloquea las
IP de Railway). Pregunta al backend de Learnix qué DTE hay por verificar,
los consulta en el portal público de Hacienda (el mismo GET que usa el QR de
cada documento), uno cada ~4.5 s, y le devuelve la respuesta al backend.

No guarda ni necesita claves de Supabase: solo LEARNIX_URL y MH_RELAY_TOKEN
(ver worker.env.example). Solo depende de `requests`. Compatible con Python 3.8+.

Uso:
    python mh_worker.py --probar   # comprueba token y Hacienda, sin tocar la cola
    python mh_worker.py            # queda corriendo (lo hace ejecutar.bat)

Ritmo: pasan ~15 consultas seguidas y luego Hacienda responde 429 ~5 min; con
4 s entre consultas pasaron 51 de 51 (probado el 9-oct-2026 desde una IP
residencial). Ante un 429 o 403 el worker se pone en pausa y devuelve los
trabajos pendientes a la cola en vez de insistir.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests

URL_HACIENDA = "https://admin.factura.gob.sv/prod/consultas/publica/simple/1"
EJEMPLO = ("EF2823DF-8DB6-4F6C-9129-2BDDBF160AAF", "2026-09-14")

log = logging.getLogger("mh_worker")

# Los tests reemplazan estos dos por un reloj falso.
_ahora, _dormir = time.monotonic, time.sleep


class Config:
    def __init__(self):
        self.url = os.environ.get("LEARNIX_URL", "").strip().rstrip("/")
        self.token = os.environ.get("MH_RELAY_TOKEN", "").strip()
        self.intervalo = _num("MH_WORKER_INTERVALO_S", 4.5)
        self.espera_sin_trabajo = _num("MH_WORKER_ESPERA_S", 4.0)
        self.pausa_429 = _num("MH_WORKER_PAUSA_429_S", 300.0)
        self.pausa_403 = _num("MH_WORKER_PAUSA_403_S", 900.0)
        self.user_agent = os.environ.get("MH_WORKER_UA", "LearnixDTE-Worker/1.0 (+verificacion de DTE)")


def _num(nombre, defecto):
    try:
        return float(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


def cargar_env(ruta):
    """Lee KEY=VALUE de worker.env (sin pisar variables ya definidas)."""
    try:
        lineas = Path(ruta).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


# ── Backend de Learnix ──────────────────────────────────────────────────────
def _backend(cfg, metodo, ruta, **kw):
    return requests.request(metodo, cfg.url + ruta, headers={"X-Relay-Token": cfg.token}, timeout=20, **kw)


def _retry_after(resp, defecto):
    try:
        return min(float(resp.headers.get("Retry-After")), 900.0)
    except (TypeError, ValueError):
        return defecto


def reclamar(cfg):
    """Lista de trabajos (posiblemente vacía) o None si hay que esperar un rato
    por un problema de configuración o del backend."""
    r = _backend(cfg, "POST", "/mh-relay/reclamar", json={"max": 3})
    if r.status_code == 200:
        return r.json().get("trabajos", [])
    if r.status_code == 429:
        _dormir(_retry_after(r, 60.0))
        return None
    if r.status_code in (401, 503):
        log.error("El backend rechazó al worker (HTTP %s): revisa MH_RELAY_TOKEN aquí y en Railway. Reintento en 60 s.", r.status_code)
    else:
        log.warning("El backend respondió HTTP %s al reclamar trabajos. Reintento en 30 s.", r.status_code)
    _dormir(60.0 if r.status_code in (401, 503) else 30.0)
    return None


def enviar_resultado(cfg, trabajo, status, cuerpo, error=None):
    """Devuelve el resultado al backend, con 3 intentos. Si no llega, el
    trabajo vuelve solo a la cola a los 2 minutos (lo recupera el backend)."""
    payload = {
        "codigo_generacion": trabajo["codigo_generacion"], "fecha_emi": trabajo["fecha_emi"],
        "ambiente": trabajo.get("ambiente", "01"), "http_status": status, "cuerpo": cuerpo,
        "error": (error or None) and str(error)[:300],
    }
    for intento in range(3):
        try:
            r = _backend(cfg, "POST", "/mh-relay/resultado", json=payload)
            if r.status_code == 200:
                return True
            if r.status_code == 422:   # el backend no lo acepta: reintentar no cambia nada
                log.warning("El backend rechazó el resultado de %s: %s", trabajo["codigo_generacion"], r.text[:200])
                return False
            log.warning("Resultado de %s: HTTP %s (intento %d/3)", trabajo["codigo_generacion"], r.status_code, intento + 1)
        except requests.RequestException as exc:
            log.warning("Resultado de %s: %s (intento %d/3)", trabajo["codigo_generacion"], exc, intento + 1)
        _dormir(5.0)
    return False


# ── Hacienda ────────────────────────────────────────────────────────────────
def consultar_hacienda(cfg, codigo, fecha, ambiente="01"):
    """(http_status, cuerpo, error, retry_after). http_status 0 = no se pudo consultar."""
    try:
        r = requests.get(
            URL_HACIENDA,
            params={"codigoGeneracion": codigo, "fechaEmi": fecha, "ambiente": ambiente},
            headers={"User-Agent": cfg.user_agent, "Accept": "application/json"},
            timeout=20,
        )
    except requests.RequestException as exc:
        return 0, None, str(exc), None
    if r.status_code == 200:
        try:
            cuerpo = r.json()
        except ValueError:
            return 200, None, "respuesta que no es JSON", None
        return 200, cuerpo if isinstance(cuerpo, dict) else None, None, None
    return r.status_code, None, "HTTP %s" % r.status_code, r.headers.get("Retry-After")


_ultima_consulta = 0.0


def _respetar_ritmo(cfg):
    global _ultima_consulta
    falta = _ultima_consulta + cfg.intervalo - _ahora()
    if falta > 0:
        _dormir(falta)
    _ultima_consulta = _ahora()


# ── Bucle principal ─────────────────────────────────────────────────────────
def procesar_lote(cfg, trabajos):
    """Consulta los trabajos de a uno. Devuelve los segundos de pausa que
    corresponde tomar tras el lote (0 si todo fue normal)."""
    for i, t in enumerate(trabajos):
        _respetar_ritmo(cfg)
        status, cuerpo, error, retry = consultar_hacienda(cfg, t["codigo_generacion"], t["fecha_emi"], t.get("ambiente", "01"))
        enviar_resultado(cfg, t, status, cuerpo, error)
        if status == 200 and cuerpo is not None:
            log.info("%s -> %s", t["codigo_generacion"], cuerpo.get("estadoDoc") or cuerpo.get("action"))
        elif status in (400, 404):
            log.info("%s -> Hacienda no lo encontró (HTTP %s)", t["codigo_generacion"], status)
        else:
            pausa = {429: cfg.pausa_429, 403: cfg.pausa_403}.get(status, 30.0)
            if status == 429 and retry:
                try:
                    pausa = min(float(retry), 900.0)
                except ValueError:
                    pass
            if status == 403:
                log.error("Hacienda respondió 403 también desde esta conexión: puede estar bloqueando este equipo. Pausa de %.0f s.", pausa)
            else:
                log.warning("%s -> %s. Pausa de %.0f s.", t["codigo_generacion"], error or status, pausa)
            for resto in trabajos[i + 1:]:   # no se consultaron: vuelven a la cola
                enviar_resultado(cfg, resto, 0, None, "liberado por pausa")
            return pausa
    return 0.0


def bucle(cfg, ciclos=None):
    """`ciclos` limita las vueltas (solo para pruebas); None = para siempre."""
    fallos_red = 0
    vueltas = 0
    while ciclos is None or vueltas < ciclos:
        vueltas += 1
        try:
            trabajos = reclamar(cfg)
            fallos_red = 0
        except requests.RequestException as exc:
            fallos_red += 1
            espera = min(10.0 * fallos_red, 120.0)
            log.warning("Sin conexión con el backend (%s). Reintento en %.0f s.", exc, espera)
            _dormir(espera)
            continue
        if trabajos is None:
            continue
        if not trabajos:
            _dormir(cfg.espera_sin_trabajo)
            continue
        pausa = procesar_lote(cfg, trabajos)
        if pausa:
            _dormir(pausa)


# ── Comprobación ────────────────────────────────────────────────────────────
def probar(cfg):
    """Imprime si el backend y Hacienda responden desde este equipo. Código de salida 0 si todo bien."""
    ok = True
    if not cfg.url or len(cfg.token) < 32:
        print("[FALTA] worker.env: define LEARNIX_URL y MH_RELAY_TOKEN (token de 32+ caracteres).")
        return 1
    try:
        r = _backend(cfg, "GET", "/mh-relay/ping")
        if r.status_code == 200:
            print("[OK]    Backend de Learnix: token aceptado.")
        elif r.status_code == 503:
            print("[FALLA] Backend: MH_RELAY_TOKEN no está definida (o es corta) en Railway.")
            ok = False
        elif r.status_code == 401:
            print("[FALLA] Backend: el token no coincide con el de Railway.")
            ok = False
        else:
            print("[FALLA] Backend: respondió HTTP %s (revisa LEARNIX_URL)." % r.status_code)
            ok = False
    except requests.RequestException as exc:
        print("[FALLA] No se pudo conectar al backend: %s" % exc)
        ok = False
    status, cuerpo, error, _ = consultar_hacienda(cfg, *EJEMPLO)
    if status == 200 and cuerpo:
        print("[OK]    Hacienda: respondió (%s)." % (cuerpo.get("estadoDoc") or cuerpo.get("action")))
    elif status == 403:
        print("[FALLA] Hacienda: 403 también desde este equipo.")
        ok = False
    elif status == 429:
        print("[AVISO] Hacienda: 429 (tope de tasa). Espera 5 minutos y repite.")
        ok = False
    else:
        print("[FALLA] Hacienda: %s" % (error or status))
        ok = False
    return 0 if ok else 1


def configurar_logs(carpeta):
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    consola = logging.StreamHandler()
    consola.setFormatter(fmt)
    log.addHandler(consola)
    try:
        carpeta.mkdir(exist_ok=True)
        archivo = RotatingFileHandler(str(carpeta / "mh_worker.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        archivo.setFormatter(fmt)
        log.addHandler(archivo)
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="Worker de consultas a Hacienda para Learnix")
    ap.add_argument("--probar", action="store_true", help="comprueba el token y la conexión con Hacienda y termina")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):   # consola de Windows en cp437/cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    aqui = Path(__file__).resolve().parent
    cargar_env(aqui / "worker.env")
    cfg = Config()
    if args.probar:
        return probar(cfg)

    configurar_logs(aqui / "logs")
    if not cfg.url or len(cfg.token) < 32:
        log.error("Falta configuración: copia worker.env.example a worker.env y completa LEARNIX_URL y MH_RELAY_TOKEN.")
        return 2
    log.info("Worker iniciado: backend=%s, una consulta cada %.1f s", cfg.url, cfg.intervalo)
    try:
        bucle(cfg)
    except KeyboardInterrupt:
        log.info("Worker detenido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
