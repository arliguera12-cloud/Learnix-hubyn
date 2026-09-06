-- =============================================================
-- LEARNIX DTE HUB — Aislamiento por organización del directorio y los jobs
-- =============================================================
-- Ejecuta en: Supabase → SQL Editor → New Query → Run
-- Requiere 01_schema_saas.sql, 06_local_data_tables.sql y 07_procesamiento_jobs.sql.
--
-- CONTEXTO: db/06 dejó `organizacion_id` como columna opcional en
-- clientes_directorio / proveedores_directorio, y backend/utils/local_db.py
-- nunca la enviaba: todas las filas quedaban con organizacion_id IS NULL, es
-- decir un único directorio global compartido por todos los tenants. Como el
-- backend usa SUPABASE_SERVICE_KEY (bypassa RLS), las políticas por
-- organización de db/06 tampoco lo frenaban: cualquier usuario autenticado
-- leía, sobrescribía y borraba los clientes y proveedores de cualquier otro.
--
-- El backend ya exige `organizacion_id` en todas esas operaciones. Este
-- script pone la base de datos en el mismo estado: reasigna las filas legadas
-- y prohíbe que vuelvan a crearse sin organización.
--
-- Lo mismo para procesamiento_jobs: se le agrega organizacion_id para que
-- GET /procesar/lote/jobs/{job_id} solo devuelva el lote a quien lo creó.
-- =============================================================


-- ─────────────────────────────────────────────────────────────
-- [1] Reasignar el directorio legado (organizacion_id IS NULL)
-- ─────────────────────────────────────────────────────────────
-- Las filas migradas desde el JSON plano no registran de quién eran. Si el
-- proyecto tiene exactamente UNA organización, son suyas sin ambigüedad y se
-- le asignan. Con varias organizaciones no hay forma de adivinarlo: el script
-- avisa y deja esas filas sin tocar para que se resuelvan a mano.
DO $$
DECLARE
    v_org_id    UUID;
    v_num_orgs  INT;
    v_huerfanas INT;
BEGIN
    SELECT COUNT(*) INTO v_num_orgs FROM organizaciones;

    SELECT COUNT(*) INTO v_huerfanas
    FROM (
        SELECT 1 FROM clientes_directorio    WHERE organizacion_id IS NULL
        UNION ALL
        SELECT 1 FROM proveedores_directorio WHERE organizacion_id IS NULL
    ) t;

    IF v_huerfanas = 0 THEN
        RAISE NOTICE 'Directorio: no hay filas sin organización, nada que reasignar.';
    ELSIF v_num_orgs = 1 THEN
        SELECT id INTO v_org_id FROM organizaciones;
        UPDATE clientes_directorio    SET organizacion_id = v_org_id WHERE organizacion_id IS NULL;
        UPDATE proveedores_directorio SET organizacion_id = v_org_id WHERE organizacion_id IS NULL;
        RAISE NOTICE 'Directorio: % filas legadas asignadas a la organización %.', v_huerfanas, v_org_id;
    ELSE
        RAISE WARNING
            'Directorio: % filas sin organización y % organizaciones en el proyecto. '
            'No se pueden asignar automáticamente — revísalas con: '
            'SELECT * FROM clientes_directorio WHERE organizacion_id IS NULL; '
            'Hasta entonces esas filas quedan invisibles para la aplicación.',
            v_huerfanas, v_num_orgs;
    END IF;
END $$;


-- ─────────────────────────────────────────────────────────────
-- [2] Prohibir filas sin organización de aquí en adelante
-- ─────────────────────────────────────────────────────────────
-- Solo se aplica si el paso [1] no dejó huérfanas: un NOT NULL con filas
-- nulas presentes fallaría y abortaría todo el script.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM clientes_directorio WHERE organizacion_id IS NULL) THEN
        ALTER TABLE clientes_directorio ALTER COLUMN organizacion_id SET NOT NULL;
        DROP INDEX IF EXISTS uq_clientes_dir_nit_sin_org;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM proveedores_directorio WHERE organizacion_id IS NULL) THEN
        ALTER TABLE proveedores_directorio ALTER COLUMN organizacion_id SET NOT NULL;
        DROP INDEX IF EXISTS uq_proveedores_dir_nit_sin_org;
    END IF;
END $$;


-- ─────────────────────────────────────────────────────────────
-- [3] procesamiento_jobs: dueño del lote
-- ─────────────────────────────────────────────────────────────
ALTER TABLE procesamiento_jobs
    ADD COLUMN IF NOT EXISTS organizacion_id UUID REFERENCES organizaciones(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_procesamiento_jobs_org
    ON procesamiento_jobs(organizacion_id);

-- Los jobs anteriores a esta columna no tienen dueño y contienen datos
-- fiscales extraídos. No se pueden atribuir a nadie, y su TTL útil es de
-- horas (el frontend hace polling y descarga el resultado en el momento),
-- así que se borran en vez de quedar accesibles sin dueño.
DELETE FROM procesamiento_jobs WHERE organizacion_id IS NULL;
