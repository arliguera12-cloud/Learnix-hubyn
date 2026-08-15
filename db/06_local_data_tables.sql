-- =============================================================
-- LEARNIX DTE HUB — Directorio local (migración desde backend/data/*.json)
-- =============================================================
-- Ejecuta en: Supabase → SQL Editor → New Query → Run
-- Requiere que 01_schema_saas.sql ya esté ejecutado (usa get_mi_organizacion_id()
-- y es_admin_de_mi_org()).
--
-- CONTEXTO: backend/utils/local_db.py guardaba clientes/proveedores en JSON
-- en el filesystem del backend — en Railway ese filesystem es efímero y se
-- pierde en cada redeploy. Estas tablas reemplazan ese almacenamiento.
--
-- NOTA — duplicación conocida: el frontend (Clientes.jsx/Proveedores.jsx)
-- ya lee directo de las tablas `clientes`/`proveedores` (db/01, db/03),
-- separadas de este directorio. Este script NO las unifica: local_db.py
-- se llama hoy sin contexto de organización/usuario en la mayoría de sus
-- invocaciones (extractors internos, sin request scope), así que unificarlo
-- con `clientes`/`proveedores` habría requerido enhebrar organizacion_id por
-- todos los extractors — fuera de alcance de esta migración, que solo mueve
-- el almacenamiento de filesystem a Supabase preservando la interfaz actual.
-- =============================================================


-- ─────────────────────────────────────────────────────────────
-- [1] TABLA: clientes_directorio
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clientes_directorio (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id  UUID        REFERENCES organizaciones(id) ON DELETE CASCADE,
    nit              TEXT        NOT NULL,
    nombre_comercial TEXT        NOT NULL DEFAULT '',
    dui              TEXT        DEFAULT '',
    nrc              TEXT        DEFAULT '',
    actividad        TEXT        DEFAULT '',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Un NIT por organización; y un NIT único entre las filas "sin organización"
-- (las migradas desde el JSON legado, que no tenían este concepto).
CREATE UNIQUE INDEX IF NOT EXISTS uq_clientes_dir_org_nit
    ON clientes_directorio (organizacion_id, nit) WHERE organizacion_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_clientes_dir_nit_sin_org
    ON clientes_directorio (nit) WHERE organizacion_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_clientes_dir_org ON clientes_directorio(organizacion_id);

ALTER TABLE clientes_directorio ENABLE ROW LEVEL SECURITY;

CREATE POLICY "clientes_dir_select_org" ON clientes_directorio
    FOR SELECT USING (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "clientes_dir_insert_org" ON clientes_directorio
    FOR INSERT WITH CHECK (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "clientes_dir_update_org" ON clientes_directorio
    FOR UPDATE USING (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "clientes_dir_delete_admin" ON clientes_directorio
    FOR DELETE USING (
        organizacion_id = get_mi_organizacion_id()
        AND es_admin_de_mi_org()
    );


-- ─────────────────────────────────────────────────────────────
-- [2] TABLA: proveedores_directorio
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proveedores_directorio (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id  UUID        REFERENCES organizaciones(id) ON DELETE CASCADE,
    nit              TEXT        NOT NULL,
    nombre_comercial TEXT        NOT NULL DEFAULT '',
    nrc              TEXT        DEFAULT '',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_proveedores_dir_org_nit
    ON proveedores_directorio (organizacion_id, nit) WHERE organizacion_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_proveedores_dir_nit_sin_org
    ON proveedores_directorio (nit) WHERE organizacion_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_proveedores_dir_org ON proveedores_directorio(organizacion_id);

ALTER TABLE proveedores_directorio ENABLE ROW LEVEL SECURITY;

CREATE POLICY "proveedores_dir_select_org" ON proveedores_directorio
    FOR SELECT USING (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "proveedores_dir_insert_org" ON proveedores_directorio
    FOR INSERT WITH CHECK (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "proveedores_dir_update_org" ON proveedores_directorio
    FOR UPDATE USING (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "proveedores_dir_delete_admin" ON proveedores_directorio
    FOR DELETE USING (
        organizacion_id = get_mi_organizacion_id()
        AND es_admin_de_mi_org()
    );

-- =============================================================
-- IMPORTANTE:
-- backend/utils/local_db.py accede a estas tablas con SUPABASE_SERVICE_KEY
-- (service_role), que hace bypass de RLS — igual que el healthcheck. Las
-- políticas de arriba protegen cualquier acceso futuro directo desde el
-- frontend (anon key), que hoy NO existe para estas dos tablas.
-- =============================================================
