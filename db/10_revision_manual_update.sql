-- ============================================================
-- Permite corregir documentos marcados para revisión manual
-- Ejecutar en Supabase SQL Editor (requiere 02_dte_tables.sql)
-- ============================================================
--
-- db_ventas/db_compras/db_retenciones/db_sujetos solo tenían políticas de
-- SELECT/INSERT/DELETE (ver 02_dte_tables.sql) — no existía forma de que el
-- propio usuario corrigiera un `registro` con datos mal extraídos y lo
-- guardara. La pantalla de Revisión Manual necesita hacer
-- `UPDATE ... SET registro = ...` sobre sus propios documentos.

DO $$ DECLARE t TEXT; BEGIN
  FOREACH t IN ARRAY ARRAY['db_ventas','db_compras','db_retenciones','db_sujetos'] LOOP
    EXECUTE format('DROP POLICY IF EXISTS "%s_update" ON %s;', t, t);
    EXECUTE format('
      CREATE POLICY "%s_update" ON %s
        FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
    ', t, t);
  END LOOP;
END $$;
