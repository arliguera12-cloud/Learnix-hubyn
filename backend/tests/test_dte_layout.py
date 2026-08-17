"""
Prueba de la lectura de columnas EMISOR / RECEPTOR.

Regresión de un fallo que llegó a producción: en un lote de 20 ventas, las 20
salieron con el identificador del emisor en la columna del cliente. El DTE
imprime ambos bloques en dos columnas, así que emisor y receptor comparten
línea, y quedarse con "el primer NIT del documento" devuelve el del emisor.

Agrava el caso que el declarante estuviera registrado con su NIT de 14 dígitos
mientras el DTE imprime su DUI en el campo NIT: la exclusión por directorio no
lo reconocía y el número pasaba el filtro.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.dte_layout import (  # noqa: E402
    ids_pareados, identificadores_emisor, buscar_numero_control,
)

# Fragmento con el formato exacto que emite Hacienda (dos columnas).
DTE_DOS_COLUMNAS = """\
DOCUMENTO TRIBUTARIO ELECTRÓNICO
COMPROBANTE DE CRÉDITO FISCAL
Número de Control : DTE-03-M001P001-000000000000097
EMISOR RECEPTOR
Nombre: JORGE ARTURO MAGAÑA EGUIZABAL Nombre: VICTOR ALEJANDRO RIVAS
NIT: 01697286-7 NIT: 0502-160984-104-0
NRC: 228200-7 NRC: 217691-4
Actividad económica : Servicios n.c.p. Actividad económica : Transporte
VENTA POR CUENTA DE TERCEROS
NIT: - Nombre del Tercero: -
"""

fallos = []


def caso(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(f"{'PASA ' if ok else 'FALLA'}  {nombre:<52} → {obtenido!r}")
    if not ok:
        fallos.append(f"{nombre}: esperaba {esperado!r}, obtuvo {obtenido!r}")


pares = ids_pareados(DTE_DOS_COLUMNAS)

caso("NIT del receptor (no el del emisor)",
     pares["receptor"]["nit"], "05021609841040")
caso("NRC del receptor",
     pares["receptor"]["nrc"], "2176914")
caso("NIT del emisor queda en su columna",
     pares["emisor"]["nit"], "016972867")
caso("identificadores del emisor para exclusión",
     identificadores_emisor(DTE_DOS_COLUMNAS), {"016972867", "2282007"})

# La sección "VENTA POR CUENTA DE TERCEROS" repite la etiqueta NIT más abajo:
# no debe sobrescribir el valor del receptor.
caso("una etiqueta repetida no pisa la primera",
     pares["receptor"]["nit"], "05021609841040")

# ── Formatos que NO son de dos columnas: no debe inventar pares ─────────────
caso("una sola columna → sin pares",
     ids_pareados("RECEPTOR\nNIT: 0614-150307-102-3\nNRC: 178265-9"), {})
caso("etiquetas distintas en la línea → sin pares",
     ids_pareados("NIT: 01697286-7 NRC: 228200-7"), {})
caso("valores en líneas separadas → sin pares",
     ids_pareados("NIT: 01697286-7\nNIT: 0614-150307-102-3"), {})
caso("texto vacío → sin pares",
     ids_pareados(""), {})
caso("emisor sin formato reconocido → exclusión vacía",
     identificadores_emisor("NIT: 0614-150307-102-3"), set())

# ── Número de control partido por el salto de línea del PDF ────────────────
# Caso real: el prefijo cierra la línea y el correlativo aparece más adelante,
# detrás del texto de la columna vecina. Buscarlo solo contiguo descartaba el
# documento con "No se detectó Número de Control válido".
DTE_CONTROL_PARTIDO = """\
OD EL SALVADOR LTDA, DE C.V. Código de Generación: A1CD945D-D065-4402-
NIT: 06140711071030 ACCB-16F30B2027EA
NRC: 1832035 Número de control: DTE-03-S001P005-
OD EL SALVADOR LTDA, DE C.V. 000000000008829
"""

caso("control partido en dos líneas",
     buscar_numero_control(DTE_CONTROL_PARTIDO),
     ("DTE-03-S001P005-000000000008829", "03"))
caso("control contiguo (caso habitual)",
     buscar_numero_control("Número de Control : DTE-03-M001P001-000000000000097"),
     ("DTE-03-M001P001-000000000000097", "03"))
caso("sin número de control",
     buscar_numero_control("TIQUETE: ODSACA481786\nNIT 06140711071030"),
     ("", ""))
caso("prefijo sin correlativo cerca",
     buscar_numero_control("DTE-03-S001P005-" + "x" * 400 + "000000000008829"),
     ("", ""))

print()
print("TODOS LOS CASOS PASAN" if not fallos else "FALLOS:\n  " + "\n  ".join(fallos))
sys.exit(1 if fallos else 0)
