"""
Prueba del aislamiento entre organizaciones (tenants).

Regresión de una fuga de datos entre clientes del SaaS: `utils/local_db.py`
aceptaba `organizacion_id=None` y todos sus llamadores lo omitían, así que el
directorio de clientes y proveedores era uno solo, compartido por todas las
organizaciones. Como el backend habla con Supabase usando la service key —que
bypassa RLS— las políticas por organización de db/06 tampoco lo frenaban:
cualquier usuario autenticado leía, sobrescribía y borraba el directorio de
cualquier otro.

Lo mismo en `utils/jobs.py`: GET /procesar/lote/jobs/{job_id} devolvía los
datos fiscales completos de un lote a quien presentara un token válido, sin
comprobar que el lote fuera suyo.

Estas pruebas no tocan Supabase: verifican que las funciones se nieguen a
operar sin un scope de organización, y que un job no se entregue a otra.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import jobs as jobs_store  # noqa: E402
from utils import local_db  # noqa: E402

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"

fallos = []


def caso(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(f"{'PASA ' if ok else 'FALLA'}  {nombre:<56} → {obtenido!r}")
    if not ok:
        fallos.append(f"{nombre}: esperaba {esperado!r}, obtuvo {obtenido!r}")


def rechaza_sin_org(fn, *args, **kwargs) -> bool:
    """¿La función se niega a operar sin organización?"""
    try:
        fn(*args, **kwargs)
    except ValueError:
        return True
    except TypeError:
        # Falta el argumento obligatorio — también es un rechazo, y además
        # significa que ningún llamador puede omitirlo por descuido.
        return True
    return False


# ─── El directorio exige scope de organización ───────────────────────────────

caso("cargar_clientes_db sin organización",
     rechaza_sin_org(local_db.cargar_clientes_db), True)
caso("cargar_clientes_db con organización vacía",
     rechaza_sin_org(local_db.cargar_clientes_db, ""), True)
caso("cargar_proveedores_combinados sin organización",
     rechaza_sin_org(local_db.cargar_proveedores_combinados), True)
caso("cargar_proveedores_db con organización vacía",
     rechaza_sin_org(local_db.cargar_proveedores_db, ""), True)
caso("guardar_cliente_db sin organización",
     rechaza_sin_org(local_db.guardar_cliente_db, "0614", "ACME"), True)
caso("guardar_proveedor_db con organización vacía",
     rechaza_sin_org(local_db.guardar_proveedor_db, "0614", "ACME", ""), True)
caso("eliminar_cliente_db con organización vacía",
     rechaza_sin_org(local_db.eliminar_cliente_db, "algún-id", ""), True)
caso("eliminar_proveedor_db con organización vacía",
     rechaza_sin_org(local_db.eliminar_proveedor_db, "algún-id", ""), True)
caso("buscar_proveedor_por_nit con organización vacía",
     rechaza_sin_org(local_db.buscar_proveedor_por_nit, "0614", ""), True)
caso("auto_registrar_proveedor con organización vacía",
     rechaza_sin_org(local_db.auto_registrar_proveedor, "0614", "ACME", ""), True)


# ─── Un lote solo lo lee la organización que lo creó ─────────────────────────

job = jobs_store.crear_job(3, ORG_A)
job_id = job["job_id"]
jobs_store.actualizar_progreso(job_id, resultado={"registro": {"tot": "1500.00"}})

caso("el dueño ve su propio job",
     (jobs_store.obtener_job(job_id, ORG_A) or {}).get("job_id"), job_id)
caso("otra organización no ve el job",
     jobs_store.obtener_job(job_id, ORG_B), None)
caso("sin organización tampoco",
     jobs_store.obtener_job(job_id, ""), None)
caso("el respaldo en Supabase no se consulta sin organización",
     jobs_store.cargar_de_supabase(job_id, ""), None)
caso("crear un job sin organización se rechaza",
     rechaza_sin_org(jobs_store.crear_job, 1, ""), True)

print()
print("TODOS LOS CASOS PASAN" if not fallos else "FALLOS:\n  " + "\n  ".join(fallos))
sys.exit(1 if fallos else 0)
