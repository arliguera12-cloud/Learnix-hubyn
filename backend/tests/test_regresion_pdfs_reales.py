"""
Regresión contra PDFs reales — congela el comportamiento actual de los
extractores para detectar cuando un cambio de regex rompe algo que ya
andaba bien.

Los PDFs (`fixtures/compras/`, `fixtures/ventas/`) son documentos reales
que el usuario compartió durante el desarrollo — varios de ellos fueron
justamente la evidencia de bugs ya corregidos en esta sesión (FOVIAL/
COTRANS no contados, "Otros montos no afectos" sin reconocer, el nombre
del cliente colándose como proveedor, la codificación Latin-1 del caso
MAGAÑA/EGUIZABAL). Tenerlos como fixtures evita volver a romperlos.

Cómo funciona:
  - Corre el extractor real (`extraer_compra_nativo_pro` / `_venta_`)
    sobre cada PDF y compara los campos clave contra una "foto" (snapshot)
    guardada en `fixtures/snapshots/<tipo>.json`.
  - Vision/IA (Groq) y la consulta pública de Hacienda se desactivan a
    propósito (mock) — dependen de red y de API keys, así que dejarlos
    prendidos volvería la prueba no determinística. Esto significa que el
    snapshot congela el camino regex + QR local, no el resultado que vería
    un usuario real con Vision/Hacienda disponibles — sigue sirviendo para
    cazar regresiones de regex, que es lo que rompió antes.
  - Si `fixtures/snapshots/<tipo>.json` no existe, esta corrida lo CREA
    (modo grabación) — usalo una vez para fijar la base, revisando a mano
    que los valores grabados sean correctos antes de commitear el JSON.
  - Para regrabar a propósito tras un cambio de comportamiento verificado:
    `LEARNIX_REGRABAR_SNAPSHOTS=1 python3 tests/test_regresion_pdfs_reales.py`
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractors.compras import extraer_compra_nativo_pro  # noqa: E402
from extractors.ventas import extraer_venta_nativo_pro  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REGRABAR = os.environ.get("LEARNIX_REGRABAR_SNAPSHOTS") == "1"

CLIENTE_ACTIVO_VACIO = {"nit": "", "dui": "", "nrc": "", "nombre": ""}

# Campos que se congelan por tipo de documento — los que ya causaron bugs
# reales (montos, nombre de contraparte, identificadores) más los que
# determinan qué tan bien quedó el documento (estado/confianza).
CAMPOS_COMPRAS = [
    "tipo", "fecha", "num_control", "gen", "sello",
    "nit_prov", "nom_prov", "dui_prov",
    "exe", "gra", "iva", "ret", "perc", "tot", "fovial", "cotrans",
    "estado", "confianza",
    "error_tipo",  # DTE-01 rechazado a propósito en compras — parte del contrato
]
CAMPOS_VENTAS = [
    "tipo", "fecha", "num_control", "gen", "sello",
    "nit_cli", "nom_cli", "dui_cli",
    "exentas", "no_sujetas", "gravadas", "debito", "terceros", "deb_terc", "total",
    "estado", "confianza",
]


def _normalizar(valor):
    """Redondea floats a 2 decimales para que un ruido de punto flotante no cuente como regresión."""
    if isinstance(valor, float):
        return round(valor, 2)
    return valor


def _extraer_snapshot(resultado: dict, campos: list[str]) -> dict:
    return {c: _normalizar(resultado.get(c)) for c in campos if c in resultado or c == "error_tipo"}


def _correr(carpeta: str, fn_extraer, campos: list[str], nombre_snapshot: str, fallos: list[str]):
    carpeta_pdfs = FIXTURES / carpeta
    archivo_snapshot = FIXTURES / "snapshots" / f"{nombre_snapshot}.json"

    pdfs = sorted(carpeta_pdfs.glob("*.pdf")) + sorted(carpeta_pdfs.glob("*.PDF"))
    if not pdfs:
        print(f"AVISO  sin fixtures en {carpeta_pdfs} — nada que correr")
        return

    snapshot_previo = {}
    if archivo_snapshot.exists() and not REGRABAR:
        snapshot_previo = json.loads(archivo_snapshot.read_text())

    snapshot_nuevo = {}
    modulo_extractor = fn_extraer.__module__
    with patch(f"{modulo_extractor}.consultar_dte_publico", return_value=None), \
         patch(f"{modulo_extractor}.vision_disponible", return_value=False), \
         patch(f"{modulo_extractor}.gemini_disponible", return_value=False):
        for pdf in pdfs:
            nombre = pdf.name
            try:
                resultado = fn_extraer(pdf.read_bytes(), dict(CLIENTE_ACTIVO_VACIO))
                actual = _extraer_snapshot(resultado, campos)
            except Exception as exc:
                actual = {"_excepcion": f"{type(exc).__name__}: {exc}"}
            snapshot_nuevo[nombre] = actual

            if nombre not in snapshot_previo:
                print(f"GRABADO  {carpeta}/{nombre:<45}")
                continue

            esperado = snapshot_previo[nombre]
            if actual == esperado:
                print(f"PASA     {carpeta}/{nombre}")
            else:
                diffs = {
                    k: (esperado.get(k), actual.get(k))
                    for k in set(esperado) | set(actual)
                    if esperado.get(k) != actual.get(k)
                }
                print(f"FALLA    {carpeta}/{nombre} → cambios: {diffs}")
                fallos.append(f"{carpeta}/{nombre}")

    archivo_snapshot.parent.mkdir(parents=True, exist_ok=True)
    if REGRABAR or not snapshot_previo:
        archivo_snapshot.write_text(json.dumps(snapshot_nuevo, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"— snapshot {'regrabado' if REGRABAR else 'grabado'}: {archivo_snapshot}")


fallos: list[str] = []
_correr("compras", extraer_compra_nativo_pro, CAMPOS_COMPRAS, "compras", fallos)
_correr("ventas", extraer_venta_nativo_pro, CAMPOS_VENTAS, "ventas", fallos)

print()
print("TODOS LOS CASOS PASAN" if not fallos else f"FALLOS ({len(fallos)}): {fallos}")
sys.exit(1 if fallos else 0)
