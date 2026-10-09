-- =============================================================
-- LEARNIX DTE HUB — Cola de consultas a Hacienda (modo relay)
-- =============================================================
-- Ejecuta en: Supabase → SQL Editor → New Query → Run (idempotente)
--
-- CONTEXTO: Hacienda responde 403 a las peticiones que salen de Railway
-- (probado con dos IP distintas), pero responde bien a una IP residencial de
-- El Salvador. En modo relay el backend no consulta a Hacienda: deja el DTE en
-- esta cola y un worker (scripts/mh_worker, corriendo en un equipo con salida
-- desde El Salvador) lo consulta y escribe el resultado. La tabla también hace
-- de caché: un mismo código/fecha no se vuelve a consultar mientras la
-- respuesta sea reciente.
--
-- Acceso: SOLO el backend (SUPABASE_SERVICE_KEY, bypassa RLS). El worker no
-- toca Supabase: habla con el backend con un token propio (MH_RELAY_TOKEN).
-- Los datos de Hacienda son los de la consulta pública (los mismos que muestra
-- el QR del documento); se comparten entre organizaciones porque se indexan por
-- código de generación y solo los recibe quien ya conoce ese código.
-- =============================================================

CREATE TABLE IF NOT EXISTS mh_consulta_cola (
    codigo_generacion TEXT        NOT NULL,
    fecha_emi         DATE        NOT NULL,
    ambiente          TEXT        NOT NULL DEFAULT '01',
    -- pendiente    → esperando al worker
    -- procesando   → reclamado por el worker (vuelve a pendiente si pasan 2 min sin respuesta)
    -- ok           → Hacienda respondió con el documento
    -- no_encontrado→ Hacienda respondió 400/404 (el documento no existe o los datos no calzan)
    -- error        → 5 intentos fallidos
    estado            TEXT        NOT NULL DEFAULT 'pendiente'
                      CHECK (estado IN ('pendiente', 'procesando', 'ok', 'no_encontrado', 'error')),
    resultado         JSONB,
    http_status       INTEGER,
    intentos          INTEGER     NOT NULL DEFAULT 0,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reclamado_en      TIMESTAMPTZ,
    actualizado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (codigo_generacion, fecha_emi, ambiente)
);

CREATE INDEX IF NOT EXISTS idx_mh_cola_pendientes
    ON mh_consulta_cola (creado_en) WHERE estado IN ('pendiente', 'procesando');

ALTER TABLE mh_consulta_cola ENABLE ROW LEVEL SECURITY;
-- Sin políticas a propósito: solo el service_role (que bypassa RLS) la toca.


-- ─────────────────────────────────────────────────────────────
-- Encolar (o devolver lo que ya hay)
-- ─────────────────────────────────────────────────────────────
-- Inserta la fila si no existe. Si existe pero está vencida, la vuelve a poner
-- pendiente:
--   · ok            > 24 h  → un DTE puede invalidarse después; no se confía
--                             en una verificación vieja.
--   · no_encontrado / error > 10 min → reintento razonable.
-- Devuelve la fila resultante.
CREATE OR REPLACE FUNCTION mh_cola_encolar(p_codigo TEXT, p_fecha DATE, p_ambiente TEXT DEFAULT '01')
RETURNS SETOF mh_consulta_cola
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO mh_consulta_cola AS c (codigo_generacion, fecha_emi, ambiente)
    VALUES (p_codigo, p_fecha, p_ambiente)
    ON CONFLICT (codigo_generacion, fecha_emi, ambiente) DO UPDATE
        SET estado = 'pendiente', resultado = NULL, http_status = NULL, intentos = 0,
            creado_en = NOW(), reclamado_en = NULL, actualizado_en = NOW()
        WHERE (c.estado = 'ok' AND c.actualizado_en < NOW() - INTERVAL '24 hours')
           OR (c.estado IN ('no_encontrado', 'error') AND c.actualizado_en < NOW() - INTERVAL '10 minutes');

    RETURN QUERY
        SELECT * FROM mh_consulta_cola
        WHERE codigo_generacion = p_codigo AND fecha_emi = p_fecha AND ambiente = p_ambiente;
END;
$$;


-- ─────────────────────────────────────────────────────────────
-- Reclamar trabajos para el worker
-- ─────────────────────────────────────────────────────────────
-- Toma hasta p_max pendientes (los más antiguos primero) y los marca como
-- procesando. También recupera los que quedaron procesando hace más de 2
-- minutos (el worker se cayó a mitad). SKIP LOCKED evita que dos workers
-- tomen el mismo.
CREATE OR REPLACE FUNCTION mh_cola_reclamar(p_max INTEGER DEFAULT 3)
RETURNS SETOF mh_consulta_cola
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    WITH elegidos AS (
        SELECT codigo_generacion, fecha_emi, ambiente
        FROM mh_consulta_cola
        WHERE estado = 'pendiente'
           OR (estado = 'procesando' AND reclamado_en < NOW() - INTERVAL '2 minutes')
        ORDER BY creado_en
        LIMIT GREATEST(LEAST(p_max, 10), 1)
        FOR UPDATE SKIP LOCKED
    )
    UPDATE mh_consulta_cola c
       SET estado = 'procesando', reclamado_en = NOW(), actualizado_en = NOW()
      FROM elegidos e
     WHERE c.codigo_generacion = e.codigo_generacion
       AND c.fecha_emi = e.fecha_emi
       AND c.ambiente = e.ambiente
    RETURNING c.*;
$$;


-- Mismo problema que db/09: Postgres concede EXECUTE a PUBLIC por defecto, y la
-- clave anon viaja en el bundle del frontend. Estas funciones son SECURITY
-- DEFINER, así que solo el backend (service_role) debe poder llamarlas.
REVOKE ALL ON FUNCTION mh_cola_encolar(TEXT, DATE, TEXT) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION mh_cola_reclamar(INTEGER)         FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION mh_cola_encolar(TEXT, DATE, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION mh_cola_reclamar(INTEGER)         TO service_role;

-- Limpieza manual cuando haga falta (no hay cron):
--   DELETE FROM mh_consulta_cola WHERE actualizado_en < NOW() - INTERVAL '30 days';
