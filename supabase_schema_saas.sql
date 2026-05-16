-- =============================================================
-- LEARNIX DTE HUB — SaaS Multi-tenant Schema  v2.1
-- =============================================================
-- Ejecuta en: Supabase → SQL Editor → New Query → Run
-- Si vienes de v1.0, lee la sección MIGRACIÓN al final.
--
-- ORDEN DE EJECUCIÓN (dependencias resueltas):
--   1. Tablas base (sin políticas)
--   2. Funciones SECURITY DEFINER helper
--   3. Políticas RLS (ya con todas las tablas creadas)
--   4. Triggers
-- =============================================================


-- =============================================================
-- BLOQUE 1: TABLAS BASE
-- Creamos primero todas las tablas sin políticas para que
-- las funciones y políticas puedan referenciarlas libremente.
-- =============================================================

-- ─────────────────────────────────────────────────────────────
-- [1.1] TABLA: organizaciones  (el "tenant" central del SaaS)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizaciones (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre              TEXT        NOT NULL,
    plan_suscripcion    TEXT        NOT NULL DEFAULT 'starter'
                                    CHECK (plan_suscripcion IN ('starter', 'profesional', 'enterprise')),
    dtes_procesados_mes INTEGER     NOT NULL DEFAULT 0,
    estado_activa       BOOLEAN     NOT NULL DEFAULT TRUE,
    max_usuarios        INTEGER     NOT NULL DEFAULT 3,
    max_clientes        INTEGER     NOT NULL DEFAULT 10,
    limite_dtes_mes     INTEGER     NOT NULL DEFAULT 500,
    email_contacto      TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- [1.2] TABLA: perfiles  (un registro por usuario auth.users)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS perfiles (
    id               UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre_contador  TEXT        NOT NULL DEFAULT '',
    organizacion_id  UUID        REFERENCES organizaciones(id) ON DELETE SET NULL,
    rol              TEXT        NOT NULL DEFAULT 'contador'
                                 CHECK (rol IN ('admin', 'contador', 'viewer')),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- [1.3] TABLA: clientes  (empresas auditadas — nivel org)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clientes (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id  UUID        NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    user_id          UUID        NOT NULL REFERENCES auth.users(id)     ON DELETE SET NULL,
    nit              TEXT        NOT NULL,
    nombre_comercial TEXT        NOT NULL,
    nrc              TEXT        DEFAULT '',
    dui              TEXT        DEFAULT '',
    actividad        TEXT        DEFAULT '',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organizacion_id, nit)
);

CREATE INDEX IF NOT EXISTS idx_clientes_org  ON clientes(organizacion_id);
CREATE INDEX IF NOT EXISTS idx_clientes_user ON clientes(user_id);
CREATE INDEX IF NOT EXISTS idx_clientes_nit  ON clientes(nit);

-- ─────────────────────────────────────────────────────────────
-- [1.4] TABLA: dte_procesados  (historial de DTEs — nivel org)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dte_procesados (
    id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id  UUID          NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    user_id          UUID          NOT NULL REFERENCES auth.users(id)     ON DELETE SET NULL,
    cliente_id       UUID          NOT NULL REFERENCES clientes(id)       ON DELETE CASCADE,
    tipo_dte         TEXT          NOT NULL,
    fecha_emision    TEXT,
    numero_control   TEXT,
    sello            TEXT,
    uuid_dte         TEXT,
    nit_emisor       TEXT,
    nit_receptor     TEXT,
    monto_total      NUMERIC(14,2) DEFAULT 0,
    monto_gravado    NUMERIC(14,2) DEFAULT 0,
    monto_exento     NUMERIC(14,2) DEFAULT 0,
    monto_iva        NUMERIC(14,2) DEFAULT 0,
    monto_retencion  NUMERIC(14,2) DEFAULT 0,
    json_data        JSONB,
    archivo_nombre   TEXT,
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dte_org_id    ON dte_procesados(organizacion_id);
CREATE INDEX IF NOT EXISTS idx_dte_user_id   ON dte_procesados(user_id);
CREATE INDEX IF NOT EXISTS idx_dte_cliente   ON dte_procesados(cliente_id);
CREATE INDEX IF NOT EXISTS idx_dte_tipo      ON dte_procesados(tipo_dte);
CREATE INDEX IF NOT EXISTS idx_dte_fecha     ON dte_procesados(fecha_emision);
CREATE INDEX IF NOT EXISTS idx_dte_org_fecha ON dte_procesados(organizacion_id, fecha_emision);


-- =============================================================
-- BLOQUE 2: FUNCIONES SECURITY DEFINER
-- Ahora que todas las tablas existen podemos crearlas
-- sin riesgo de referencias rotas.
-- =============================================================

-- Retorna el organizacion_id del usuario autenticado
CREATE OR REPLACE FUNCTION get_mi_organizacion_id()
RETURNS UUID
LANGUAGE SQL
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT organizacion_id
    FROM   perfiles
    WHERE  id = auth.uid()
$$;

-- Retorna TRUE si el usuario autenticado tiene rol='admin'
CREATE OR REPLACE FUNCTION es_admin_de_mi_org()
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM perfiles
        WHERE id = auth.uid() AND rol = 'admin'
    )
$$;

-- Retorna el plan de suscripción de la organización del usuario
CREATE OR REPLACE FUNCTION get_plan_org()
RETURNS TEXT
LANGUAGE SQL
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT o.plan_suscripcion
    FROM   organizaciones o
    JOIN   perfiles p ON p.organizacion_id = o.id
    WHERE  p.id = auth.uid()
$$;

-- Retorna TRUE si la organización del usuario está activa
CREATE OR REPLACE FUNCTION org_esta_activa()
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT COALESCE(o.estado_activa, false)
    FROM   organizaciones o
    JOIN   perfiles p ON p.organizacion_id = o.id
    WHERE  p.id = auth.uid()
$$;

-- Verifica si la org puede procesar más DTEs este mes
CREATE OR REPLACE FUNCTION puede_procesar_dte(p_organizacion_id UUID)
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT
        o.estado_activa
        AND o.dtes_procesados_mes < o.limite_dtes_mes
    FROM organizaciones o
    WHERE o.id = p_organizacion_id
$$;


-- =============================================================
-- BLOQUE 3: HABILITAR RLS + POLÍTICAS
-- Todas las tablas ya existen y las funciones helper también.
-- =============================================================

-- ─────────────────────────────────────────────────────────────
-- RLS: organizaciones
-- ─────────────────────────────────────────────────────────────
ALTER TABLE organizaciones ENABLE ROW LEVEL SECURITY;

-- Miembros ven solo su propia organización
CREATE POLICY "org_select_miembros" ON organizaciones
    FOR SELECT USING (
        id = get_mi_organizacion_id()
    );

-- Solo admins actualizan datos de su organización
CREATE POLICY "org_update_admin" ON organizaciones
    FOR UPDATE USING (
        id = get_mi_organizacion_id()
        AND es_admin_de_mi_org()
    );

-- ─────────────────────────────────────────────────────────────
-- RLS: perfiles
-- ─────────────────────────────────────────────────────────────
ALTER TABLE perfiles ENABLE ROW LEVEL SECURITY;

-- Cada usuario siempre puede ver su propio perfil
CREATE POLICY "perfil_select_own" ON perfiles
    FOR SELECT USING (auth.uid() = id);

-- Un admin puede ver todos los perfiles de su organización
CREATE POLICY "perfil_select_admin_org" ON perfiles
    FOR SELECT USING (
        organizacion_id = get_mi_organizacion_id()
        AND es_admin_de_mi_org()
    );

CREATE POLICY "perfil_insert" ON perfiles
    FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "perfil_update_own" ON perfiles
    FOR UPDATE USING (auth.uid() = id);

-- ─────────────────────────────────────────────────────────────
-- RLS: clientes
-- ─────────────────────────────────────────────────────────────
ALTER TABLE clientes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "clientes_select_org" ON clientes
    FOR SELECT USING (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "clientes_insert_org" ON clientes
    FOR INSERT WITH CHECK (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "clientes_update_org" ON clientes
    FOR UPDATE USING (organizacion_id = get_mi_organizacion_id());

-- Solo admins pueden eliminar clientes
CREATE POLICY "clientes_delete_admin" ON clientes
    FOR DELETE USING (
        organizacion_id = get_mi_organizacion_id()
        AND es_admin_de_mi_org()
    );

-- ─────────────────────────────────────────────────────────────
-- RLS: dte_procesados
-- ─────────────────────────────────────────────────────────────
ALTER TABLE dte_procesados ENABLE ROW LEVEL SECURITY;

CREATE POLICY "dte_select_org" ON dte_procesados
    FOR SELECT USING (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "dte_insert_org" ON dte_procesados
    FOR INSERT WITH CHECK (organizacion_id = get_mi_organizacion_id());

CREATE POLICY "dte_update_org" ON dte_procesados
    FOR UPDATE USING (organizacion_id = get_mi_organizacion_id());

-- Solo admins pueden eliminar DTEs
CREATE POLICY "dte_delete_admin" ON dte_procesados
    FOR DELETE USING (
        organizacion_id = get_mi_organizacion_id()
        AND es_admin_de_mi_org()
    );


-- =============================================================
-- BLOQUE 4: TRIGGERS
-- =============================================================

-- ─────────────────────────────────────────────────────────────
-- [4.1] TRIGGER principal: Auto-crear perfil + org al registrar
-- ─────────────────────────────────────────────────────────────
--
-- Metadata que debe enviar el cliente al hacer sign_up:
--
--   Flujo Admin (crea nueva firma contable):
--     { "nombre_contador": "Lic. Juan Pérez",
--       "crear_org": true,
--       "nombre_org": "Despacho Fiscal Pérez & Asociados" }
--
--   Flujo Invitado (se une a firma existente):
--     { "nombre_contador": "Ana García",
--       "organizacion_id": "<UUID de la organización>",
--       "rol": "contador" }
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_org_id      UUID;
    v_org_nombre  TEXT;
    v_org_uuid    TEXT;
    v_crear_org   BOOLEAN;
    v_nombre      TEXT;
    v_rol         TEXT;
BEGIN
    v_nombre     := COALESCE(
                        NEW.raw_user_meta_data->>'nombre_contador',
                        split_part(NEW.email, '@', 1)
                    );
    v_crear_org  := COALESCE((NEW.raw_user_meta_data->>'crear_org')::boolean, false);
    v_org_nombre := COALESCE(NEW.raw_user_meta_data->>'nombre_org', 'Mi Firma Contable');
    v_org_uuid   := NEW.raw_user_meta_data->>'organizacion_id';

    IF v_crear_org OR v_org_uuid IS NULL THEN
        -- Flujo Admin: crear nueva organización
        INSERT INTO organizaciones (nombre, plan_suscripcion, email_contacto)
        VALUES (v_org_nombre, 'starter', NEW.email)
        RETURNING id INTO v_org_id;

        v_rol := 'admin';
    ELSE
        -- Flujo Invitado: vincularse a organización existente
        BEGIN
            v_org_id := v_org_uuid::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            -- UUID mal formado — crear org de emergencia
            INSERT INTO organizaciones (nombre, email_contacto)
            VALUES ('Org de ' || split_part(NEW.email, '@', 1), NEW.email)
            RETURNING id INTO v_org_id;
        END;
        v_rol := COALESCE(NEW.raw_user_meta_data->>'rol', 'contador');
    END IF;

    INSERT INTO perfiles (id, nombre_contador, organizacion_id, rol)
    VALUES (NEW.id, v_nombre, v_org_id, v_rol);

    RETURN NEW;

EXCEPTION WHEN OTHERS THEN
    -- Salvaguarda: nunca bloquear el registro por un error aquí
    INSERT INTO perfiles (id, nombre_contador)
    VALUES (NEW.id, v_nombre)
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ─────────────────────────────────────────────────────────────
-- [4.2] TRIGGER: updated_at automático en organizaciones
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_org_updated_at ON organizaciones;
CREATE TRIGGER tg_org_updated_at
    BEFORE UPDATE ON organizaciones
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─────────────────────────────────────────────────────────────
-- [4.3] TRIGGER: Incrementa el contador mensual de DTEs
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION incrementar_dtes_mes()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE organizaciones
    SET    dtes_procesados_mes = dtes_procesados_mes + 1,
           updated_at          = NOW()
    WHERE  id = NEW.organizacion_id;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_contar_dte_insert ON dte_procesados;
CREATE TRIGGER tg_contar_dte_insert
    AFTER INSERT ON dte_procesados
    FOR EACH ROW EXECUTE FUNCTION incrementar_dtes_mes();


-- =============================================================
-- BLOQUE 5: CRON (activar manualmente en Supabase Dashboard)
-- Database → Cron Jobs → New cron job
-- Name: reset-dtes-mensuales
-- Schedule: 0 0 1 * *  (día 1 de cada mes, medianoche UTC)
-- =============================================================
-- SELECT cron.schedule(
--     'reset-dtes-mensuales',
--     '0 0 1 * *',
--     $$ UPDATE organizaciones SET dtes_procesados_mes = 0 $$
-- );


-- =============================================================
-- BLOQUE 6: MIGRACIÓN DESDE v1.0
-- Solo ejecutar si ya tienes tablas antiguas con datos.
-- Descomenta bloque a bloque y ejecuta en orden.
-- =============================================================
/*

-- M1: Agregar columnas nuevas (idempotente)
ALTER TABLE perfiles
    ADD COLUMN IF NOT EXISTS organizacion_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS rol TEXT NOT NULL DEFAULT 'contador'
        CHECK (rol IN ('admin', 'contador', 'viewer'));

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS organizacion_id UUID REFERENCES organizaciones(id) ON DELETE CASCADE;

ALTER TABLE dte_procesados
    ADD COLUMN IF NOT EXISTS organizacion_id UUID REFERENCES organizaciones(id) ON DELETE CASCADE;


-- M2: Eliminar políticas de v1.0
DROP POLICY IF EXISTS "perfil_select"   ON perfiles;
DROP POLICY IF EXISTS "perfil_insert"   ON perfiles;
DROP POLICY IF EXISTS "perfil_update"   ON perfiles;
DROP POLICY IF EXISTS "clientes_select" ON clientes;
DROP POLICY IF EXISTS "clientes_insert" ON clientes;
DROP POLICY IF EXISTS "clientes_update" ON clientes;
DROP POLICY IF EXISTS "clientes_delete" ON clientes;
DROP POLICY IF EXISTS "dte_select"      ON dte_procesados;
DROP POLICY IF EXISTS "dte_insert"      ON dte_procesados;
DROP POLICY IF EXISTS "dte_update"      ON dte_procesados;
DROP POLICY IF EXISTS "dte_delete"      ON dte_procesados;


-- M3: Crear una organización por cada usuario existente
DO $$
DECLARE
    r        RECORD;
    v_org_id UUID;
BEGIN
    FOR r IN
        SELECT p.id, u.email
        FROM   perfiles p
        JOIN   auth.users u ON u.id = p.id
        WHERE  p.organizacion_id IS NULL
    LOOP
        INSERT INTO organizaciones (nombre, plan_suscripcion, email_contacto)
        VALUES ('Firma de ' || split_part(r.email, '@', 1), 'starter', r.email)
        RETURNING id INTO v_org_id;

        UPDATE perfiles       SET organizacion_id = v_org_id, rol = 'admin' WHERE id = r.id;
        UPDATE clientes       SET organizacion_id = v_org_id WHERE user_id = r.id;
        UPDATE dte_procesados SET organizacion_id = v_org_id WHERE user_id = r.id;

        -- Sincronizar contador del mes actual
        UPDATE organizaciones
        SET dtes_procesados_mes = (
            SELECT COUNT(*) FROM dte_procesados
            WHERE  organizacion_id = v_org_id
              AND  DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
        )
        WHERE id = v_org_id;

        RAISE NOTICE 'Migrado usuario % → org %', r.id, v_org_id;
    END LOOP;
END $$;


-- M4: Reemplazar constraint antigua por la nueva
ALTER TABLE clientes DROP CONSTRAINT IF EXISTS clientes_user_id_nit_key;
ALTER TABLE clientes ADD CONSTRAINT  clientes_org_nit_key UNIQUE (organizacion_id, nit);


-- M5: Hacer NOT NULL las columnas migradas
ALTER TABLE clientes       ALTER COLUMN organizacion_id SET NOT NULL;
ALTER TABLE dte_procesados ALTER COLUMN organizacion_id SET NOT NULL;

*/
-- =============================================================
-- FIN DEL SCRIPT
-- =============================================================
