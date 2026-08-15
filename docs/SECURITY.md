# Seguridad — Learnix DTE Hub

Resumen de las medidas de seguridad implementadas en el backend y la base de datos.

## Autenticación

El frontend inicia sesión directamente contra **Supabase Auth** (`supabase.auth.signInWithPassword`, en `frontend/src/services/auth.js`) y adjunta el `access_token` real en cada llamada al backend (`frontend/src/services/api.js`).

El backend **verifica ese mismo JWT** — no emite ni gestiona sesiones propias. `backend/utils/auth_dependency.py` decodifica el token localmente con `SUPABASE_JWT_SECRET` (HS256, `audience="authenticated"`) y lo aplica como dependencia a nivel de router en `backend/routers/procesamiento.py` y `backend/routers/exportar.py`. `/health` es la única ruta pública.

**Decisión explícita:** se descartó construir un sistema JWT/bcrypt propio (login, refresh, tabla de passwords). El repo ya tenía una autenticación real vía Supabase que el frontend usa; un sistema paralelo habría sido redundante, no habría conectado con el flujo real del frontend, y habría requerido una columna de password que no existe en el schema (Supabase la gestiona en `auth.users`, fuera de nuestro control). Como parte de esta limpieza se eliminaron `backend/routers/auth.py` y `backend/utils/supabase_client.py` — un endpoint `/auth/login` legado de la época Streamlit (contraseña compartida `APP_PASSWORD`) que el frontend nunca llamaba.

## Autorización — Row Level Security (Supabase)

Auditado (no reescrito — ya estaba implementado):

| Tabla | RLS | Modelo |
|---|---|---|
| `organizaciones`, `perfiles`, `clientes`, `dte_procesados` | ✅ (`db/01_schema_saas.sql`) | Multi-tenant por `organizacion_id`, admin-gated para operaciones destructivas |
| `db_ventas`, `db_compras`, `db_retenciones`, `db_sujetos` | ✅ (`db/02_dte_tables.sql`) | Por `user_id` (SELECT/INSERT/DELETE; sin UPDATE — los registros son inmutables por diseño, se reemplazan con delete+insert) |
| `proveedores` | ✅ (`db/03_proveedores.sql`) | Por `organizacion_id`, delete solo admin |
| `proveedores_globales` | ✅ (`db/03_proveedores.sql`) | Lectura para cualquier usuario autenticado, escritura solo `service_role` |
| `clientes_directorio`, `proveedores_directorio` | ✅ (`db/06_local_data_tables.sql`) | Por `organizacion_id` (nullable), delete solo admin. Hoy solo accedidas por `backend/utils/local_db.py` vía `service_role` (bypass RLS) — las políticas protegen cualquier acceso futuro directo desde el frontend, que hoy no existe para estas dos tablas |

No se encontraron huecos: cada tabla con datos de usuario tiene RLS habilitado y políticas coherentes con el modelo de acceso. El backend usa `SUPABASE_KEY` (o `SUPABASE_SERVICE_KEY` si está definida) para el healthcheck y para el directorio de clientes/proveedores (`local_db.py`) — el resto del acceso a datos ocurre desde el frontend con la `anon key`, que sí respeta RLS.

## Rate limiting

`backend/middleware/rate_limit.py` — en memoria, por IP (`X-Forwarded-For` detrás de Railway). Configurable vía `RATE_LIMIT_PER_MINUTE` (default 30), `RATE_LIMIT_BURST` (default 60), `BLOCKED_IPS`. `/health` está excluido. Suficiente para una sola instancia; si se escala a múltiples instancias, migrar a un store compartido (Redis) — no implementado en esta fase.

## Validación de input

- `backend/schemas/procesamiento.py`: Pydantic v2 para `declarante_id`/`nombre_declarante`/`nrc_declarante` (longitud + patrón).
- `backend/routers/procesamiento.py` (`_read_pdf_bytes`): extensión `.pdf`, tamaño máximo 10MB, verificación de magic bytes (`%PDF-`) — no confía solo en la extensión del archivo.
- `backend/routers/exportar.py`: `tipo` validado contra un set fijo de valores permitidos.

## Encriptación

- **En tránsito:** TLS/HTTPS gestionado automáticamente por Railway y Vercel.
- **Headers de seguridad** (`backend/main.py`, middleware `security_headers`): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, y `Strict-Transport-Security` (HSTS) solo cuando `ENVIRONMENT=production`.
- **En reposo:** Supabase encripta at-rest por defecto (PostgreSQL/AES-256 a nivel de storage). Los passwords de usuario los gestiona Supabase Auth (bcrypt), no este repo.

## CORS

`backend/main.py`: orígenes explícitos vía `ALLOWED_ORIGINS` (comma-separated). El regex `https://*.vercel.app` (para preview deploys) solo se activa cuando `ENVIRONMENT != production` — en producción, solo orígenes explícitos.

## Secrets

Todo vía variables de entorno (`backend/.env.example`, `frontend/.env.example`), nunca en código ni en los `.json` de deploy (`railway.json`, `vercel.json`). Los `.env` reales están en `.gitignore`.

## Pendiente / fuera de esta fase

- Rate limiting in-memory → Redis, si se escala a múltiples instancias.
- No hay tests ni CI en el repo (fuera de alcance de esta fase).
