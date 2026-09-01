# Base de datos — Supabase

Scripts SQL para provisionar el esquema en **Supabase → SQL Editor**.

## Orden de ejecución (instalación nueva)

1. `01_schema_saas.sql` — schema multi-tenant v2.1 (organizaciones, perfiles, clientes, RLS, triggers)
2. `02_dte_tables.sql` — tablas de almacenamiento de DTEs procesados
3. `03_proveedores.sql` — módulo de proveedores (requiere que `01_schema_saas.sql` ya esté aplicado)
4. `04_fix_reparar_perfil.sql` — parche idempotente, seguro de re-ejecutar
5. `06_local_data_tables.sql` — directorio de clientes/proveedores usado por el backend (reemplaza el almacenamiento en `backend/data/*.json`; requiere `01_schema_saas.sql`)
6. `07_procesamiento_jobs.sql` — respaldo del progreso de lotes en background (`utils/jobs.py`), para que un redeploy/reinicio del contenedor no pierda un lote en curso

`legacy/schema_v1_superseded.sql` es el schema v1.0 (single-tenant), superado por `01_schema_saas.sql`. **No ejecutar en instalaciones nuevas** — se conserva solo como referencia histórica.

Ver `docs/IMPLEMENTACION_SAAS.md` para la guía completa paso a paso (incluye verificación de triggers, RLS y cron job de reset mensual).
