# Learnix DTE Hub — Guía de Implementación SaaS Multi-tenant v2.0

> **Orden de lectura:** Sigue los pasos exactamente en la secuencia indicada.  
> Cada paso está marcado con **dónde** lo ejecutas: `[SUPABASE]` o `[LOCAL]`.

---

## PILAR 1 — Base de Datos SaaS (SQL)

### Paso 1 · [SUPABASE] Ejecutar el nuevo schema

1. Abre tu proyecto en **app.supabase.com**
2. Ve a **SQL Editor** → **New query**
3. Copia el contenido completo de `supabase_schema_saas.sql` y pégalo
4. Haz clic en **Run** (ícono ▶)

**Qué crea este script:**

| Objeto | Tipo | Propósito |
|---|---|---|
| `organizaciones` | Tabla | Un registro por firma contable (el "tenant") |
| `perfiles` | Tabla | Un registro por usuario, con `organizacion_id` y `rol` |
| `clientes` | Tabla | Clientes de la firma, aislados por `organizacion_id` |
| `dte_procesados` | Tabla | Historial de DTEs, aislados por `organizacion_id` |
| `get_mi_organizacion_id()` | Función | Helper SECURITY DEFINER para RLS sin recursión |
| `es_admin_de_mi_org()` | Función | Verifica rol admin para las políticas de borrado |
| `handle_new_user()` | Trigger | Crea perfil + org automáticamente al registrarse |
| `incrementar_dtes_mes()` | Trigger | Actualiza contador de DTEs al insertar uno nuevo |
| `puede_procesar_dte()` | Función | Verifica límite mensual por plan |

---

### Paso 2 · [SUPABASE] Verificar que el trigger funciona

1. Ve a **Authentication** → **Users** → **Add user** → **Create new user**
2. Ingresa un correo de prueba (ej. `test@learnix.sv`) y contraseña
3. En el campo **User metadata** agrega:
   ```json
   {
     "nombre_contador": "Lic. Prueba",
     "crear_org": true,
     "nombre_org": "Firma de Prueba"
   }
   ```
4. Haz clic en **Create user**
5. Ve a **Table Editor** → tabla `perfiles` → confirma que se creó el registro
6. Ve a tabla `organizaciones` → confirma que se creó "Firma de Prueba"

✅ Si ves ambos registros, el trigger funciona correctamente.

---

### Paso 3 · [SUPABASE] Configurar el Cron Job de reset mensual

1. Ve a **Database** → **Extensions** → activa **pg_cron** si no está activo
2. Ve a **Database** → **Cron Jobs** → **New cron job**
3. Configura:
   - **Name:** `reset-dtes-mensuales`
   - **Schedule:** `0 0 1 * *` *(día 1 de cada mes, medianoche UTC)*
   - **Query:** `UPDATE organizaciones SET dtes_procesados_mes = 0`
4. Haz clic en **Save**

---

## PILAR 2 — RLS Multi-tenant (ya incluido en el schema)

Las políticas ya están en `supabase_schema_saas.sql`. Esta es la lógica aplicada:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MATRIZ DE PERMISOS RLS                       │
├───────────────┬─────────┬───────────┬────────────┬─────────────┤
│ Tabla         │ SELECT  │  INSERT   │   UPDATE   │   DELETE    │
├───────────────┼─────────┼───────────┼────────────┼─────────────┤
│ organizaciones│ Miembro │    ✗      │ Admin org  │     ✗       │
│ perfiles      │ Own/Adm │ Own only  │ Own only   │     ✗       │
│ clientes      │ Org     │ Org       │ Org        │ Admin org   │
│ dte_procesados│ Org     │ Org       │ Org        │ Admin org   │
└───────────────┴─────────┴───────────┴────────────┴─────────────┘

Org = cualquier miembro de la misma organización
Admin org = solo rol='admin' de la misma organización
```

### Paso 4 · [SUPABASE] Verificar el aislamiento multi-tenant

Ejecuta en SQL Editor para confirmar el aislamiento:

```sql
-- Simula la sesión del usuario de prueba (sustituye el UUID real)
SET LOCAL role TO authenticated;
SET LOCAL request.jwt.claim.sub TO '<UUID_del_usuario_de_prueba>';

-- Debe retornar solo los clientes de SU organización
SELECT * FROM clientes;

-- Debe retornar el ID de SU organización
SELECT get_mi_organizacion_id();
```

---

## PILAR 3 — Auth Profesional en Streamlit

### Paso 5 · [LOCAL] Actualizar dependencias

```bash
pip install -r requirements.txt
```

El nuevo paquete agregado es `streamlit-cookies-controller>=0.0.4`.  
Este paquete guarda el `refresh_token` de Supabase en una cookie del navegador,  
permitiendo que al cerrar y reabrir la pestaña la sesión se restaure automáticamente.

**Flujo completo de autenticación:**

```
Usuario cierra pestaña
       │
       ▼
App recarga → restaurar_sesion_desde_cookie()
       │
       ├── Cookie con refresh_token? ──→ NO ──→ Mostrar login
       │
       └── SÍ → supabase.auth.refresh_session()
                      │
                      ├── Éxito → Sesión restaurada silenciosamente ✓
                      └── Fallo → Cookie expirada, mostrar login
```

### Paso 6 · [LOCAL] Proteger cada página con `check_auth()`

Agrega al inicio de **cada archivo** en la carpeta `pages/`:

```python
# Al inicio del archivo, después de los imports
from utils.auth_guard import check_auth
check_auth()   # Verifica sesión + org activa
```

Para páginas de solo admins (ej. configuración de la firma):
```python
check_auth(rol="admin")
```

Para verificar límite de DTEs antes de un lote grande:
```python
from utils.auth_guard import check_auth, check_limite_dtes
check_auth()
check_limite_dtes()   # Muestra advertencia y bloquea si excede el límite
```

**Reemplaza el guard antiguo** en todas las páginas:
```python
# ANTES (v1.0) — eliminar esta línea:
if not st.session_state.get("autenticado"):
    st.warning("...")
    st.stop()

# DESPUÉS (v2.0) — usar esto:
from utils.auth_guard import check_auth
check_auth()
```

### Paso 7 · [SUPABASE] Configurar Auth settings

1. Ve a **Authentication** → **Providers** → **Email**
2. Configura:
   - **Enable Email provider:** ✅ ON
   - **Confirm email:** ✅ ON (recomendado para producción)
   - **Secure email change:** ✅ ON
3. Ve a **Authentication** → **URL Configuration**
   - **Site URL:** tu dominio de producción (ej. `https://learnix.streamlit.app`)
   - **Redirect URLs:** agrega la misma URL

---

## PILAR 4 — Flujo de Registro de Nuevos Clientes (Firmas)

### Cómo registrar una nueva firma contable (Admin)

Desde tu app o desde el Dashboard de Supabase, el sign_up debe incluir metadata:

```python
# Ejemplo desde Python (puedes adaptarlo a un formulario de registro)
from utils.supabase_client import get_supabase

sb = get_supabase()
sb.auth.sign_up({
    "email":    "admin@despachopeñate.com",
    "password": "contraseña_segura_123",
    "options": {
        "data": {
            "nombre_contador": "Lic. Carlos Peñate",
            "crear_org":       True,
            "nombre_org":      "Despacho Fiscal Peñate & Asociados"
        }
    }
})
# El trigger handle_new_user() crea la organización + perfil automáticamente
```

### Cómo invitar un segundo contador a la misma firma

```python
# Paso 1: El admin obtiene su organizacion_id
org_id = st.session_state["sb_organizacion"]["id"]

# Paso 2: Registrar al nuevo usuario vinculado a esa org
sb.auth.sign_up({
    "email":    "ana@despachopeñate.com",
    "password": "clave_temporal_456",
    "options": {
        "data": {
            "nombre_contador": "Lic. Ana García",
            "organizacion_id": org_id,   # <-- clave del flujo invitado
            "rol":             "contador"
        }
    }
})
# El trigger crea el perfil vinculado a la org existente, sin crear nueva org
```

---

## Tabla de Planes de Suscripción (referencia)

| Campo en BD | starter | profesional | enterprise |
|---|---|---|---|
| `max_usuarios` | 3 | 10 | Sin límite |
| `max_clientes` | 10 | 50 | Sin límite |
| `limite_dtes_mes` | 500 | 3,000 | 20,000 |

Para cambiar el plan de una firma desde Supabase:

```sql
UPDATE organizaciones
SET    plan_suscripcion  = 'profesional',
       limite_dtes_mes   = 3000,
       max_usuarios      = 10,
       max_clientes      = 50
WHERE  id = '<UUID_de_la_organización>';
```

Para suspender una firma (bloquea acceso a toda la app inmediatamente):

```sql
UPDATE organizaciones
SET estado_activa = FALSE
WHERE id = '<UUID_de_la_organización>';
```

---

## Checklist de Implementación

```
SUPABASE
□ Paso 1: Ejecutar supabase_schema_saas.sql en SQL Editor
□ Paso 2: Verificar trigger con usuario de prueba
□ Paso 3: Configurar cron job de reset mensual
□ Paso 4: Confirmar aislamiento RLS con SET LOCAL
□ Paso 7: Configurar Auth settings y Site URL

LOCAL
□ Paso 5: pip install -r requirements.txt
□ Paso 6: Agregar check_auth() al inicio de cada página en pages/
□ Probar login → verificar card de org en sidebar
□ Probar cierre y reapertura de pestaña (persistencia de sesión)
□ Probar con org.estado_activa = FALSE (debe bloquear acceso)
```

---

## Archivos modificados en esta versión

| Archivo | Tipo | Descripción |
|---|---|---|
| `supabase_schema_saas.sql` | **NUEVO** | Schema completo v2.0 con multi-tenancy |
| `utils/supabase_client.py` | **MODIFICADO** | Auth con cookies + helpers multi-tenant |
| `utils/auth_guard.py` | **NUEVO** | Decorador check_auth() para protección de rutas |
| `app.py` | **MODIFICADO** | Restauración de sesión + card de organización |
| `pages/0_Dashboard_Inicio.py` | **MODIFICADO** | check_auth() reemplaza guard manual |
| `requirements.txt` | **MODIFICADO** | Agrega streamlit-cookies-controller |
