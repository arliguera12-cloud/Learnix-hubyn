-- =============================================================
-- LEARNIX DTE HUB — FIX: función reparar_perfil_sin_org
-- =============================================================
-- Ejecutar en: Supabase → SQL Editor → New Query → Run
--
-- Este script:
--   1. Crea la función reparar_perfil_sin_org (idempotente)
--   2. Otorga permiso EXECUTE al rol 'authenticated'
--   3. Repara MANUALMENTE el usuario actual si tiene perfil sin org
--
-- Es seguro re-ejecutar este script múltiples veces.
-- =============================================================


-- ─────────────────────────────────────────────────────────────
-- PASO 1 · Crear/actualizar la función reparar_perfil_sin_org
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION reparar_perfil_sin_org()
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user_id  UUID;
    v_email    TEXT;
    v_org_id   UUID;
BEGIN
    v_user_id := auth.uid();
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'No hay usuario autenticado';
    END IF;

    -- Si ya tiene org, devolverla sin hacer nada
    SELECT organizacion_id INTO v_org_id FROM perfiles WHERE id = v_user_id;
    IF v_org_id IS NOT NULL THEN
        RETURN v_org_id;
    END IF;

    SELECT email INTO v_email FROM auth.users WHERE id = v_user_id;

    -- Crear la organización
    INSERT INTO organizaciones (nombre, plan_suscripcion, email_contacto)
    VALUES ('Firma de ' || split_part(v_email, '@', 1), 'starter', v_email)
    RETURNING id INTO v_org_id;

    -- Asegurar que existe el perfil (puede no existir si el trigger falló)
    INSERT INTO perfiles (id, nombre_contador, organizacion_id, rol)
    VALUES (
        v_user_id,
        split_part(v_email, '@', 1),
        v_org_id,
        'admin'
    )
    ON CONFLICT (id) DO UPDATE
        SET organizacion_id = EXCLUDED.organizacion_id,
            rol             = 'admin';

    -- Migrar datos huérfanos del usuario (clientes que insertó antes)
    UPDATE clientes
    SET    organizacion_id = v_org_id
    WHERE  user_id = v_user_id AND organizacion_id IS NULL;

    UPDATE dte_procesados
    SET    organizacion_id = v_org_id
    WHERE  user_id = v_user_id AND organizacion_id IS NULL;

    -- Sincronizar contador mensual
    UPDATE organizaciones
    SET    dtes_procesados_mes = (
               SELECT COUNT(*) FROM dte_procesados
               WHERE  organizacion_id = v_org_id
                 AND  DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
           )
    WHERE  id = v_org_id;

    RETURN v_org_id;
END;
$$;


-- ─────────────────────────────────────────────────────────────
-- PASO 2 · Otorgar permiso EXECUTE al rol 'authenticated'
-- ─────────────────────────────────────────────────────────────
-- Sin este GRANT, la app no puede llamar a la función vía RPC.
GRANT EXECUTE ON FUNCTION reparar_perfil_sin_org() TO authenticated;
GRANT EXECUTE ON FUNCTION reparar_perfil_sin_org() TO anon;


-- ─────────────────────────────────────────────────────────────
-- PASO 3 · Reparación MANUAL de tu usuario nahum.mpc@gmail.com
-- ─────────────────────────────────────────────────────────────
-- Esto es un fallback por si la app no logra disparar la función
-- antes de mostrar el error. Crea la org directamente desde SQL.
DO $$
DECLARE
    v_email    TEXT := 'nahum.mpc@gmail.com';
    v_user_id  UUID;
    v_org_id   UUID;
    v_nombre   TEXT;
BEGIN
    SELECT id INTO v_user_id FROM auth.users WHERE email = v_email;
    IF v_user_id IS NULL THEN
        RAISE NOTICE 'Usuario % no existe en auth.users — saltando reparación manual', v_email;
        RETURN;
    END IF;

    -- ¿Ya tiene org?
    SELECT organizacion_id INTO v_org_id FROM perfiles WHERE id = v_user_id;
    IF v_org_id IS NOT NULL THEN
        RAISE NOTICE 'Usuario % ya tiene org: % — sin cambios', v_email, v_org_id;
        RETURN;
    END IF;

    v_nombre := split_part(v_email, '@', 1);

    -- Crear org
    INSERT INTO organizaciones (nombre, plan_suscripcion, email_contacto)
    VALUES ('Firma de ' || v_nombre, 'starter', v_email)
    RETURNING id INTO v_org_id;

    -- Asegurar perfil + vincularlo como admin
    INSERT INTO perfiles (id, nombre_contador, organizacion_id, rol)
    VALUES (v_user_id, v_nombre, v_org_id, 'admin')
    ON CONFLICT (id) DO UPDATE
        SET organizacion_id = EXCLUDED.organizacion_id,
            rol             = 'admin';

    -- Migrar datos huérfanos (si existían)
    UPDATE clientes
    SET    organizacion_id = v_org_id
    WHERE  user_id = v_user_id AND organizacion_id IS NULL;

    UPDATE dte_procesados
    SET    organizacion_id = v_org_id
    WHERE  user_id = v_user_id AND organizacion_id IS NULL;

    RAISE NOTICE 'Reparación manual exitosa para %: org_id=%', v_email, v_org_id;
END $$;


-- ─────────────────────────────────────────────────────────────
-- PASO 4 (BONUS) · Reparar TODOS los perfiles huérfanos
-- ─────────────────────────────────────────────────────────────
-- Si tienes otros usuarios sin org (no solo nahum), esto los repara.
-- Comenta este bloque si solo quieres reparar a tu usuario.
DO $$
DECLARE
    r          RECORD;
    v_org_id   UUID;
BEGIN
    FOR r IN
        SELECT u.id   AS user_id,
               u.email AS email
        FROM   auth.users u
        LEFT JOIN perfiles p ON p.id = u.id
        WHERE  p.organizacion_id IS NULL
    LOOP
        INSERT INTO organizaciones (nombre, plan_suscripcion, email_contacto)
        VALUES ('Firma de ' || split_part(r.email, '@', 1), 'starter', r.email)
        RETURNING id INTO v_org_id;

        INSERT INTO perfiles (id, nombre_contador, organizacion_id, rol)
        VALUES (r.user_id, split_part(r.email, '@', 1), v_org_id, 'admin')
        ON CONFLICT (id) DO UPDATE
            SET organizacion_id = EXCLUDED.organizacion_id,
                rol             = 'admin';

        UPDATE clientes
        SET    organizacion_id = v_org_id
        WHERE  user_id = r.user_id AND organizacion_id IS NULL;

        UPDATE dte_procesados
        SET    organizacion_id = v_org_id
        WHERE  user_id = r.user_id AND organizacion_id IS NULL;

        RAISE NOTICE 'Reparado: % → org %', r.email, v_org_id;
    END LOOP;
END $$;


-- ─────────────────────────────────────────────────────────────
-- PASO 5 · Verificación final
-- ─────────────────────────────────────────────────────────────
-- Después de ejecutar todo lo anterior, corre este SELECT
-- para confirmar que tu usuario ya tiene org asignada.
SELECT
    u.email                              AS usuario,
    p.nombre_contador                    AS contador,
    p.rol                                AS rol,
    o.id                                 AS org_id,
    o.nombre                             AS org_nombre,
    o.plan_suscripcion                   AS plan,
    o.dtes_procesados_mes || '/' || o.limite_dtes_mes  AS uso_dtes
FROM   auth.users u
LEFT JOIN perfiles p     ON p.id              = u.id
LEFT JOIN organizaciones o ON o.id            = p.organizacion_id
ORDER BY u.created_at DESC;

-- =============================================================
-- FIN DEL SCRIPT
-- Después de ejecutarlo:
--   1. Recarga la app de Streamlit (Ctrl+R)
--   2. Cierra sesión y vuelve a entrar (para refrescar el JWT)
--   3. Intenta guardar el cliente de nuevo — ya debería funcionar
-- =============================================================
