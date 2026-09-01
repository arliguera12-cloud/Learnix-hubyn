-- =============================================================
-- LEARNIX DTE HUB — Persistencia de jobs de procesamiento en lote
-- =============================================================
-- Ejecuta en: Supabase → SQL Editor → New Query → Run
--
-- CONTEXTO: los lotes de PDFs se procesan en background (FastAPI
-- BackgroundTasks) y el frontend hace polling del progreso. Antes ese
-- progreso vivía SOLO en un dict en memoria del proceso Uvicorn — un
-- redeploy o reinicio del contenedor (Railway) lo borraba a mitad de
-- camino, mostrando "Job no encontrado o expirado" en el frontend aunque
-- el lote se hubiera estado procesando bien. Confirmado en producción:
-- un merge a main disparó un redeploy justo mientras un usuario tenía un
-- lote en curso.
--
-- Esta tabla es un respaldo, no reemplaza la memoria: utils/jobs.py sigue
-- leyendo/escribiendo el dict en memoria como camino rápido (sin latencia
-- de red en cada actualización de progreso) y además escribe cada cambio
-- acá — si el proceso se reinicia y el job ya no está en memoria, se
-- recupera desde esta tabla.
--
-- Acceso: solo el backend (SUPABASE_SERVICE_KEY, bypassa RLS) — el
-- frontend nunca consulta esta tabla directo, siempre a través del
-- endpoint GET /procesar/lote/jobs/{job_id}.
-- =============================================================

CREATE TABLE IF NOT EXISTS procesamiento_jobs (
    job_id        TEXT        PRIMARY KEY,
    status        TEXT        NOT NULL DEFAULT 'processing',  -- processing | done | error
    total         INTEGER     NOT NULL,
    procesados    INTEGER     NOT NULL DEFAULT 0,
    resultados    JSONB       NOT NULL DEFAULT '[]'::jsonb,
    errores       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    error_fatal   TEXT,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    terminado_en  TIMESTAMPTZ
);

-- Para limpiar jobs viejos manualmente si hace falta (no hay cron acá,
-- utils/jobs.py limpia los suyos en memoria; esta tabla se puede vaciar
-- cada tanto con un DELETE WHERE terminado_en < NOW() - INTERVAL '2 days').
CREATE INDEX IF NOT EXISTS idx_procesamiento_jobs_terminado
    ON procesamiento_jobs(terminado_en) WHERE terminado_en IS NOT NULL;

ALTER TABLE procesamiento_jobs ENABLE ROW LEVEL SECURITY;
-- Sin políticas a propósito: solo accesible con SUPABASE_SERVICE_KEY
-- (service_role bypassa RLS). El frontend nunca la consulta directo, así
-- que no hace falta ninguna policy para anon/authenticated.
