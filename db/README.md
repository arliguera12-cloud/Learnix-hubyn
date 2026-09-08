# Base de datos — Supabase

Scripts SQL para provisionar el esquema en **Supabase → SQL Editor**.

## Orden de ejecución (instalación nueva)

1. `01_schema_saas.sql` — schema multi-tenant v2.1 (organizaciones, perfiles, clientes, RLS, triggers)
2. `02_dte_tables.sql` — tablas de almacenamiento de DTEs procesados
3. `03_proveedores.sql` — módulo de proveedores (requiere que `01_schema_saas.sql` ya esté aplicado)
4. `04_fix_reparar_perfil.sql` — parche idempotente, seguro de re-ejecutar
5. `06_local_data_tables.sql` — directorio de clientes/proveedores usado por el backend (reemplaza el almacenamiento en `backend/data/*.json`; requiere `01_schema_saas.sql`)
6. `07_procesamiento_jobs.sql` — respaldo del progreso de lotes en background (`utils/jobs.py`), para que un redeploy/reinicio del contenedor no pierda un lote en curso
7. `08_org_scope_directorio.sql` — mueve el directorio de clientes/proveedores a alcance por organización
8. `09_permisos_funciones.sql` — cierra permisos de ejecución de funciones SECURITY DEFINER que no hacían falta
9. `10_revision_manual_update.sql` — política UPDATE sobre `db_ventas`/`db_compras`/`db_retenciones`/`db_sujetos`, para la pantalla de Revisión Manual
10. `11_libros_legales.sql` — correlativo persistente por cliente/año sobre `db_compras`/`db_ventas`, para el Libro de Compras y los libros de Ventas (Contribuyentes / Consumidor Final)

`legacy/schema_v1_superseded.sql` es el schema v1.0 (single-tenant), superado por `01_schema_saas.sql`. **No ejecutar en instalaciones nuevas** — se conserva solo como referencia histórica.

Ver `docs/IMPLEMENTACION_SAAS.md` para la guía completa paso a paso (incluye verificación de triggers, RLS y cron job de reset mensual).
