-- =============================================================
-- LEARNIX DTE HUB — SUPABASE SCHEMA  v1.0
-- Ejecuta este script completo en: Supabase → SQL Editor → Run
-- =============================================================

-- ─────────────────────────────────────────────
-- TABLA: perfiles  (vinculada a auth.users)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS perfiles (
    id               UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre_contador  TEXT        NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE perfiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "perfil_select" ON perfiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "perfil_insert" ON perfiles
    FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "perfil_update" ON perfiles
    FOR UPDATE USING (auth.uid() = id);

-- Trigger: crea perfil vacío automáticamente al registrar un usuario
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO perfiles(id, nombre_contador)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'nombre_contador', '')
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();


-- ─────────────────────────────────────────────
-- TABLA: clientes  (empresas que el contador audita)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clientes (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    nit              TEXT        NOT NULL,
    nombre_comercial TEXT        NOT NULL,
    nrc              TEXT        DEFAULT '',
    dui              TEXT        DEFAULT '',
    actividad        TEXT        DEFAULT '',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, nit)          -- un contador no puede tener el mismo NIT dos veces
);

ALTER TABLE clientes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "clientes_select" ON clientes
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "clientes_insert" ON clientes
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "clientes_update" ON clientes
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "clientes_delete" ON clientes
    FOR DELETE USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_clientes_user ON clientes(user_id);
CREATE INDEX IF NOT EXISTS idx_clientes_nit  ON clientes(nit);


-- ─────────────────────────────────────────────
-- TABLA: dte_procesados  (historial de facturas procesadas)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dte_procesados (
    id               UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID           NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    cliente_id       UUID           NOT NULL REFERENCES clientes(id)   ON DELETE CASCADE,
    tipo_dte         TEXT           NOT NULL,          -- '01','03','05','06','07','11','14'
    fecha_emision    TEXT,                             -- DD/MM/YYYY
    numero_control   TEXT,
    sello            TEXT,
    uuid_dte         TEXT,
    nit_emisor       TEXT,
    nit_receptor     TEXT,
    monto_total      NUMERIC(14,2)  DEFAULT 0,
    monto_gravado    NUMERIC(14,2)  DEFAULT 0,
    monto_exento     NUMERIC(14,2)  DEFAULT 0,
    monto_iva        NUMERIC(14,2)  DEFAULT 0,
    monto_retencion  NUMERIC(14,2)  DEFAULT 0,
    json_data        JSONB,                            -- JSON completo del DTE
    archivo_nombre   TEXT,
    created_at       TIMESTAMPTZ    DEFAULT NOW()
);

ALTER TABLE dte_procesados ENABLE ROW LEVEL SECURITY;

CREATE POLICY "dte_select" ON dte_procesados
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "dte_insert" ON dte_procesados
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "dte_update" ON dte_procesados
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "dte_delete" ON dte_procesados
    FOR DELETE USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_dte_user_id    ON dte_procesados(user_id);
CREATE INDEX IF NOT EXISTS idx_dte_cliente_id ON dte_procesados(cliente_id);
CREATE INDEX IF NOT EXISTS idx_dte_tipo       ON dte_procesados(tipo_dte);
CREATE INDEX IF NOT EXISTS idx_dte_fecha      ON dte_procesados(fecha_emision);
