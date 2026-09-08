-- ============================================================
-- Libros legales: correlativo persistente por libro
-- Ejecutar en Supabase SQL Editor (requiere 02_dte_tables.sql)
-- ============================================================
--
-- Los "libros de IVA" (Compras, Ventas a Contribuyentes, Ventas a
-- Consumidor Final — Ley de IVA / Código Tributario) exigen un folio
-- correlativo que nunca se salta ni se reordena. Eso es justo lo que NO
-- tenía el sistema: `routers/exportar.py` genera el Anexo del F-07 (el
-- archivo que se sube al portal de Hacienda cada mes), pero es un archivo
-- de una sola vez, sin numeración persistente entre subidas — no es un
-- libro. Este script agrega esa numeración sobre las mismas tablas que ya
-- guardan cada documento extraído (db_compras / db_ventas).
--
-- Convención de folio: correlativo por (declarante, año), reiniciado cada
-- 1 de enero — la más común en los sistemas contables salvadoreños para
-- estos libros. El libro de Compras lleva un correlativo. El libro de
-- Ventas lleva DOS correlativos independientes, porque son dos libros
-- distintos aunque compartan tabla: Contribuyentes (CCF/NC/ND, tipo_dte
-- 03/05/06) y Consumidor Final (el resto).
--
-- El correlativo se asigna en un trigger (no en el backend ni en el
-- frontend) para que valga sin importar el camino de inserción —
-- guardarResultados() en el frontend inserta directo a Supabase, no pasa
-- por FastAPI. `pg_advisory_xact_lock` serializa por clave para que dos
-- filas del mismo lote no lean el mismo MAX() antes de que la otra
-- confirme su INSERT y terminen con el correlativo repetido.

ALTER TABLE db_compras ADD COLUMN IF NOT EXISTS correlativo INTEGER;
ALTER TABLE db_ventas  ADD COLUMN IF NOT EXISTS correlativo INTEGER;

CREATE INDEX IF NOT EXISTS idx_db_compras_libro
    ON db_compras (user_id, declarante_id, periodo);
CREATE INDEX IF NOT EXISTS idx_db_ventas_libro
    ON db_ventas  (user_id, declarante_id, periodo, tipo_dte);


-- ─────────────────────────────────────────────────────────────
-- Libro de Compras
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION asignar_correlativo_compras()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    anio TEXT := COALESCE(NULLIF(split_part(NEW.periodo, '-', 1), ''), to_char(NOW(), 'YYYY'));
BEGIN
    IF NEW.correlativo IS NOT NULL THEN
        RETURN NEW; -- ya trae correlativo (p. ej. una corrección manual)
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(NEW.user_id::text || '|' || NEW.declarante_id || '|' || anio, 0)
    );

    SELECT COALESCE(MAX(correlativo), 0) + 1 INTO NEW.correlativo
    FROM db_compras
    WHERE user_id = NEW.user_id
      AND declarante_id = NEW.declarante_id
      AND COALESCE(NULLIF(split_part(periodo, '-', 1), ''), to_char(created_at, 'YYYY')) = anio;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_correlativo_compras ON db_compras;
CREATE TRIGGER tg_correlativo_compras
    BEFORE INSERT ON db_compras
    FOR EACH ROW EXECUTE FUNCTION asignar_correlativo_compras();


-- ─────────────────────────────────────────────────────────────
-- Libro de Ventas — dos correlativos independientes en la misma tabla
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION asignar_correlativo_ventas()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    anio             TEXT    := COALESCE(NULLIF(split_part(NEW.periodo, '-', 1), ''), to_char(NOW(), 'YYYY'));
    es_contribuyente BOOLEAN := NEW.tipo_dte IN ('03', '05', '06');
BEGIN
    IF NEW.correlativo IS NOT NULL THEN
        RETURN NEW;
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended(
        NEW.user_id::text || '|' || NEW.declarante_id || '|' || anio || '|' || es_contribuyente::text, 0
    ));

    SELECT COALESCE(MAX(correlativo), 0) + 1 INTO NEW.correlativo
    FROM db_ventas
    WHERE user_id = NEW.user_id
      AND declarante_id = NEW.declarante_id
      AND (tipo_dte IN ('03', '05', '06')) = es_contribuyente
      AND COALESCE(NULLIF(split_part(periodo, '-', 1), ''), to_char(created_at, 'YYYY')) = anio;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_correlativo_ventas ON db_ventas;
CREATE TRIGGER tg_correlativo_ventas
    BEFORE INSERT ON db_ventas
    FOR EACH ROW EXECUTE FUNCTION asignar_correlativo_ventas();


-- ─────────────────────────────────────────────────────────────
-- Documentos ya guardados ANTES de este script: no tienen correlativo.
-- Se numeran acá mismo, en el orden en que se guardaron (created_at), para
-- no dejar huecos en el libro de quien ya venía usando la app.
-- ─────────────────────────────────────────────────────────────
DO $$
DECLARE
    fila RECORD;
    contador INTEGER;
BEGIN
    FOR fila IN
        SELECT DISTINCT user_id, declarante_id,
               COALESCE(NULLIF(split_part(periodo, '-', 1), ''), to_char(created_at, 'YYYY')) AS anio
        FROM db_compras WHERE correlativo IS NULL
    LOOP
        contador := 0;
        UPDATE db_compras SET correlativo = sub.n
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) AS n
            FROM db_compras
            WHERE user_id = fila.user_id AND declarante_id = fila.declarante_id
              AND COALESCE(NULLIF(split_part(periodo, '-', 1), ''), to_char(created_at, 'YYYY')) = fila.anio
              AND correlativo IS NULL
        ) sub
        WHERE db_compras.id = sub.id;
    END LOOP;

    FOR fila IN
        SELECT DISTINCT user_id, declarante_id, (tipo_dte IN ('03','05','06')) AS es_contrib,
               COALESCE(NULLIF(split_part(periodo, '-', 1), ''), to_char(created_at, 'YYYY')) AS anio
        FROM db_ventas WHERE correlativo IS NULL
    LOOP
        UPDATE db_ventas SET correlativo = sub.n
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) AS n
            FROM db_ventas
            WHERE user_id = fila.user_id AND declarante_id = fila.declarante_id
              AND (tipo_dte IN ('03','05','06')) = fila.es_contrib
              AND COALESCE(NULLIF(split_part(periodo, '-', 1), ''), to_char(created_at, 'YYYY')) = fila.anio
              AND correlativo IS NULL
        ) sub
        WHERE db_ventas.id = sub.id;
    END LOOP;
END $$;
