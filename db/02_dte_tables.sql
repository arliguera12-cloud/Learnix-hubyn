-- ============================================================
-- Tablas para almacenar DTEs procesados por Learnix DTE Hub
-- Ejecutar en Supabase SQL Editor (o en tu instancia local)
-- ============================================================

-- Ventas (Anexo 1 y 2)
CREATE TABLE IF NOT EXISTS db_ventas (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    declarante_id TEXT        NOT NULL,
    filename      TEXT,
    periodo       TEXT,
    fecha         TEXT,
    tipo_dte      TEXT,
    registro      JSONB       NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Compras (Anexo 3)
CREATE TABLE IF NOT EXISTS db_compras (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    declarante_id TEXT        NOT NULL,
    filename      TEXT,
    periodo       TEXT,
    fecha         TEXT,
    tipo_dte      TEXT,
    registro      JSONB       NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Retenciones (Anexo 7)
CREATE TABLE IF NOT EXISTS db_retenciones (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    declarante_id TEXT        NOT NULL,
    filename      TEXT,
    periodo       TEXT,
    fecha         TEXT,
    tipo_dte      TEXT,
    registro      JSONB       NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Sujetos Excluidos (Anexo 5)
CREATE TABLE IF NOT EXISTS db_sujetos (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    declarante_id TEXT        NOT NULL,
    filename      TEXT,
    periodo       TEXT,
    fecha         TEXT,
    tipo_dte      TEXT,
    registro      JSONB       NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE db_ventas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE db_compras     ENABLE ROW LEVEL SECURITY;
ALTER TABLE db_retenciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE db_sujetos     ENABLE ROW LEVEL SECURITY;

-- Policies: cada usuario solo ve sus propios registros
DO $$ DECLARE t TEXT; BEGIN
  FOREACH t IN ARRAY ARRAY['db_ventas','db_compras','db_retenciones','db_sujetos'] LOOP
    EXECUTE format('
      CREATE POLICY "%s_select" ON %s FOR SELECT USING (auth.uid() = user_id);
      CREATE POLICY "%s_insert" ON %s FOR INSERT WITH CHECK (auth.uid() = user_id);
      CREATE POLICY "%s_delete" ON %s FOR DELETE USING (auth.uid() = user_id);
    ', t, t, t, t, t, t);
  END LOOP;
END $$;

-- Índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_db_ventas_user      ON db_ventas      (user_id, declarante_id);
CREATE INDEX IF NOT EXISTS idx_db_compras_user     ON db_compras     (user_id, declarante_id);
CREATE INDEX IF NOT EXISTS idx_db_retenciones_user ON db_retenciones (user_id, declarante_id);
CREATE INDEX IF NOT EXISTS idx_db_sujetos_user     ON db_sujetos     (user_id, declarante_id);
CREATE INDEX IF NOT EXISTS idx_db_ventas_periodo      ON db_ventas      (user_id, periodo);
CREATE INDEX IF NOT EXISTS idx_db_compras_periodo     ON db_compras     (user_id, periodo);
CREATE INDEX IF NOT EXISTS idx_db_retenciones_periodo ON db_retenciones (user_id, periodo);
CREATE INDEX IF NOT EXISTS idx_db_sujetos_periodo     ON db_sujetos     (user_id, periodo);
