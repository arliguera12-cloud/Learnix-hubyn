-- =============================================================
-- LEARNIX DTE HUB — Permisos de ejecución de las funciones SECURITY DEFINER
-- =============================================================
-- Ejecuta en: Supabase → SQL Editor → New Query → Run
-- Requiere 01_schema_saas.sql y 04_fix_reparar_perfil.sql.
--
-- CONTEXTO: Postgres concede EXECUTE a PUBLIC por defecto en cada función que
-- se crea, así que los roles `anon` y `authenticated` de Supabase pueden
-- llamarlas por RPC (PostgREST). La clave `anon` viaja en el bundle del
-- frontend, o sea que "puede llamarla anon" equivale a "puede llamarla
-- cualquiera en internet". El Security Advisor marca todas por igual; este
-- script solo cierra las que de verdad hacen falta y explica por qué las
-- otras se dejan como están.
--
-- IMPORTANTE — lo que este script NO hace: no revoca get_mi_organizacion_id()
-- ni es_admin_de_mi_org() al rol `authenticated`. Todas las políticas RLS del
-- esquema (db/01, db/03, db/06) las invocan, y una política se evalúa con los
-- privilegios de quien consulta: sin EXECUTE, cada SELECT del frontend
-- fallaría con "permission denied for function". Revocarlas para silenciar el
-- aviso tumbaría la aplicación entera.
-- =============================================================


-- ─────────────────────────────────────────────────────────────
-- [1] puede_procesar_dte(uuid) — el único con entrada del llamador
-- ─────────────────────────────────────────────────────────────
-- Es SECURITY DEFINER (bypassa RLS) y recibe un organizacion_id arbitrario,
-- así que cualquiera con la clave anon podía preguntar por CUALQUIER
-- organización y saber si está activa y si le queda cupo de DTEs del mes. No
-- devuelve datos de los DTE, pero sí confirma que ese id existe y filtra
-- estado de negocio de otro tenant.
--
-- Nadie la llama por RPC: ni el frontend (no hay una sola llamada .rpc() en
-- todo el código) ni el backend. Queda solo para uso interno del esquema.
REVOKE ALL ON FUNCTION puede_procesar_dte(UUID) FROM PUBLIC, anon, authenticated;


-- ─────────────────────────────────────────────────────────────
-- [2] reparar_perfil_sin_org() — quitar el permiso a anon
-- ─────────────────────────────────────────────────────────────
-- db/04 la concedió a `anon` además de a `authenticated`, pero la función
-- lanza excepción si auth.uid() es NULL, que es siempre el caso de anon: el
-- permiso nunca sirvió para nada y solo amplía la superficie expuesta.
-- Se mantiene en `authenticated`, que es quien la necesita.
REVOKE ALL ON FUNCTION reparar_perfil_sin_org() FROM anon;
GRANT EXECUTE ON FUNCTION reparar_perfil_sin_org() TO authenticated;


-- ─────────────────────────────────────────────────────────────
-- [3] Funciones de trigger — cerrarlas a todos los roles de la API
-- ─────────────────────────────────────────────────────────────
-- Postgres ya rechaza llamar directamente a una función que devuelve TRIGGER
-- ("trigger functions can only be called as triggers"), así que el aviso del
-- linter es teórico. Aun así se revocan: los triggers se disparan como parte
-- de la operación sobre la tabla y no dependen del EXECUTE de estos roles,
-- de modo que revocarlos no cambia ningún comportamiento.
REVOKE ALL ON FUNCTION handle_new_user()     FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION incrementar_dtes_mes() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION set_updated_at()       FROM PUBLIC, anon, authenticated;


-- ─────────────────────────────────────────────────────────────
-- [4] set_updated_at() — fijar el search_path
-- ─────────────────────────────────────────────────────────────
-- Es la única función del esquema sin `SET search_path` (el aviso "Function
-- Search Path Mutable"). No es SECURITY DEFINER, así que no hay escalada de
-- privilegios, pero dejar el search_path a merced de quien la invoca permite
-- que resuelva objetos distintos de los previstos. Se fija por higiene.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION set_updated_at() FROM PUBLIC, anon, authenticated;


-- ─────────────────────────────────────────────────────────────
-- [5] Se dejan como están, a propósito
-- ─────────────────────────────────────────────────────────────
--   get_mi_organizacion_id()  → la usan todas las políticas RLS (ver cabecera)
--   es_admin_de_mi_org()      → ídem, en las políticas de DELETE
--   get_plan_org()            → sin parámetros, resuelve por auth.uid()
--   org_esta_activa()         → ídem
--
-- Las cuatro leen exclusivamente de auth.uid(). Para `anon` ese valor es NULL,
-- así que devuelven NULL/false y no revelan nada de ninguna organización. El
-- Security Advisor las marca por ser SECURITY DEFINER ejecutables, no porque
-- filtren datos.
--
-- PENDIENTE DE REVISAR A MANO: `rls_auto_enable()` aparece en el Security
-- Advisor pero no la crea ningún script de db/ — existe en la base y no en el
-- control de versiones, así que nadie puede revisar qué hace. Averigua su
-- origen (Supabase → Database → Functions) y, o bien súmala a este directorio,
-- o bien elimínala si fue una prueba suelta.
