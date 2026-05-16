-- =============================================================
-- LEARNIX DTE HUB — Módulo de Proveedores Híbrido
-- =============================================================
-- Ejecuta en: Supabase → SQL Editor → New Query → Run
-- Requiere que supabase_schema_saas.sql ya esté ejecutado.
-- =============================================================


-- ─────────────────────────────────────────────────────────────
-- [1] TABLA: proveedores  (catálogo privado por organización)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proveedores (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id  UUID        NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    nit              TEXT        NOT NULL,
    nombre_comercial TEXT        NOT NULL DEFAULT '',
    nrc              TEXT        DEFAULT '',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organizacion_id, nit)
);

CREATE INDEX IF NOT EXISTS idx_proveedores_org ON proveedores(organizacion_id);
CREATE INDEX IF NOT EXISTS idx_proveedores_nit ON proveedores(nit);

ALTER TABLE proveedores ENABLE ROW LEVEL SECURITY;

-- Cualquier miembro de la org puede ver sus proveedores
CREATE POLICY "proveedores_select_org" ON proveedores
    FOR SELECT USING (organizacion_id = get_mi_organizacion_id());

-- Cualquier miembro puede agregar proveedores (auto-registro al procesar DTEs)
CREATE POLICY "proveedores_insert_org" ON proveedores
    FOR INSERT WITH CHECK (organizacion_id = get_mi_organizacion_id());

-- Cualquier miembro puede editar
CREATE POLICY "proveedores_update_org" ON proveedores
    FOR UPDATE USING (organizacion_id = get_mi_organizacion_id());

-- Solo admins pueden eliminar
CREATE POLICY "proveedores_delete_admin" ON proveedores
    FOR DELETE USING (
        organizacion_id = get_mi_organizacion_id()
        AND es_admin_de_mi_org()
    );


-- ─────────────────────────────────────────────────────────────
-- [2] TABLA: proveedores_globales  (catálogo maestro interno)
-- No lleva organizacion_id: es una lista curada por el admin
-- del sistema, visible para TODOS los usuarios autenticados.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proveedores_globales (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nit              TEXT        NOT NULL UNIQUE,
    nombre_comercial TEXT        NOT NULL DEFAULT '',
    categoria        TEXT        DEFAULT '',  -- ej. 'banco','gobierno','telefonia','energia'
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prov_global_nit ON proveedores_globales(nit);

ALTER TABLE proveedores_globales ENABLE ROW LEVEL SECURITY;

-- Todos los usuarios autenticados pueden leer el catálogo global
CREATE POLICY "prov_global_select_auth" ON proveedores_globales
    FOR SELECT USING (auth.uid() IS NOT NULL);

-- Escritura solo vía service_role (panel de admin o SQL Editor)
-- No se crean políticas INSERT/UPDATE/DELETE para usuarios normales


-- ─────────────────────────────────────────────────────────────
-- [3] Datos semilla: proveedores globales comunes en El Salvador
-- Puedes expandir esta lista directamente en Supabase Table Editor
-- ─────────────────────────────────────────────────────────────
INSERT INTO proveedores_globales (nit, nombre_comercial, categoria) VALUES
    ('06141400860101', 'CLARO EL SALVADOR S.A. DE C.V.',          'telefonia'),
    ('06140103910019', 'TIGO EL SALVADOR S.A. DE C.V.',           'telefonia'),
    ('06141200600011', 'AES EL SALVADOR S.A. DE C.V.',            'energia'),
    ('06141200600060', 'CAESS S.A. DE C.V.',                      'energia'),
    ('06141200601012', 'EEO S.A. DE C.V.',                        'energia'),
    ('06140106860028', 'BANCO AGRICOLA S.A.',                     'banco'),
    ('06141204880016', 'BANCO DAVIVIENDA SALVADOREÑO S.A.',       'banco'),
    ('06141206050013', 'BANCO DE AMERICA CENTRAL S.A.',           'banco'),
    ('06140111960017', 'BANCO CUSCATLAN S.A.',                    'banco'),
    ('06141400600074', 'DISTRIBUIDORA DE ELECTRICIDAD DEL SUR',   'energia')
ON CONFLICT (nit) DO NOTHING;
-- =============================================================
-- FIN DEL SCRIPT
-- =============================================================
