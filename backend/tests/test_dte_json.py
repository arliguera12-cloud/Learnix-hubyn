"""
Pruebas de la lectura del JSON firmado por Hacienda.

Regresión de dos fallos que descartaban compras reales de un lote:

1. Un DTE válido codificado en Latin-1 (la "Ñ" de un nombre viaja como el byte
   0xD1) se rechazaba con "El archivo no es un JSON válido", porque
   `json.loads` sobre bytes asume UTF-8.
2. Hacienda no omite las claves opcionales: las envía con `null`. Declarar
   `nrc: str = ""` solo cubre la clave ausente, así que un `receptor.nrc` en
   null tumbaba la validación del documento entero.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas.dte_hacienda import DTEDocumento  # noqa: E402
from utils.dte_json import cargar_json, decodificar_texto  # noqa: E402

fallos = []


def caso(nombre, fn, esperado=None, debe_fallar=False):
    try:
        obtenido = fn()
        ok = (not debe_fallar) and (esperado is None or obtenido == esperado)
        detalle = repr(obtenido)[:60]
    except Exception as exc:
        ok = debe_fallar
        detalle = f"{type(exc).__name__}"
    print(f"{'PASA ' if ok else 'FALLA'}  {nombre:<50} → {detalle}")
    if not ok:
        fallos.append(nombre)


DOC = {"identificacion": {"tipoDte": "03", "numeroControl": "DTE-03-M001P001-001"}}

# ── Codificación ───────────────────────────────────────────────────────────
caso("UTF-8 normal",
     lambda: cargar_json(json.dumps(DOC).encode("utf-8"))["identificacion"]["tipoDte"],
     "03")
caso("UTF-8 con BOM",
     lambda: cargar_json(json.dumps(DOC).encode("utf-8-sig"))["identificacion"]["tipoDte"],
     "03")
caso("Latin-1 con Ñ (caso FREUND)",
     lambda: cargar_json('{"nombre":"MAGAÑA EGUIZABAL"}'.encode("latin-1"))["nombre"],
     "MAGAÑA EGUIZABAL")
caso("UTF-8 con Ñ no se convierte en mojibake",
     lambda: decodificar_texto("MAGAÑA".encode("utf-8")),
     "MAGAÑA")
caso("bytes que no son JSON",
     lambda: cargar_json(b"esto no es json"),
     debe_fallar=True)

# ── null en campos opcionales ──────────────────────────────────────────────
caso("receptor.nrc en null (consumidor final)",
     lambda: DTEDocumento.model_validate({
         **DOC, "receptor": {"nit": None, "nrc": None, "nombre": "CLIENTE"},
     }).receptor.nrc,
     "")
caso("null no borra los valores presentes",
     lambda: DTEDocumento.model_validate({
         **DOC, "receptor": {"nit": "06141503071023", "nrc": None},
     }).receptor.nit,
     "06141503071023")
caso("resumen con totales en null",
     lambda: DTEDocumento.model_validate({
         **DOC, "resumen": {"totalGravada": None, "totalIva": 13.0},
     }).resumen.totalGravada,
     0.0)
caso("un campo obligatorio en null sigue fallando",
     lambda: DTEDocumento.model_validate({
         "identificacion": {"tipoDte": None, "numeroControl": "X"},
     }),
     debe_fallar=True)

print()
print("TODOS LOS CASOS PASAN" if not fallos else f"FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
