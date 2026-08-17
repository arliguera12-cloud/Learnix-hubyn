# Learnix DTE Hub

Sistema de extracción automatizada de DTEs (Documentos Tributarios Electrónicos) para El Salvador, con validación fiscal según normativa DGII.

---

## Arquitectura

```
Learnix-hubyn/
│
├── backend/          ← FastAPI (Python) — deploy en Railway
├── frontend/         ← React + Vite — deploy en Vercel
├── db/                ← Scripts SQL de Supabase (orden de ejecución en db/README.md)
└── docs/               ← Documentación adicional
```

### Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend API | FastAPI + Uvicorn |
| Frontend | React 18 + Vite + React Router |
| Base de datos | Supabase (PostgreSQL) |
| Autenticación | Supabase Auth |
| IA primaria | Groq — llama-3.3-70b-versatile (texto) + llama-4-scout-17b (visión) |
| IA secundaria | Google Vertex AI / Gemini 2.0 Flash (opcional) |
| Deploy backend | Railway |
| Deploy frontend | Vercel |

---

## Backend (`/backend`)

```
backend/
├── main.py                  ← FastAPI app, CORS, middlewares, routers, healthcheck
├── routers/
│   ├── procesamiento.py     ← POST /procesar/{ventas,compras,retenciones,sujetos-excluidos}
│   │                           GET  /procesar/declarantes (todo requiere JWT de Supabase)
│   ├── exportar.py          ← POST /exportar/excel (requiere JWT de Supabase)
│   └── importar.py          ← POST /importar/drive/{listar,descargar}, /importar/gmail/buscar
│                               (Centro de importación: trae PDF/JSON de Drive o Gmail; JWT de Supabase)
├── middleware/
│   └── rate_limit.py        ← Rate limiting por IP, en memoria
├── schemas/
│   └── procesamiento.py     ← Validación Pydantic de los campos de formulario
├── extractors/               ← Lógica de extracción por tipo de DTE
│   ├── ventas.py
│   ├── compras.py
│   ├── retenciones.py
│   └── sujetos_excluidos.py
├── utils/
│   ├── ai_utils.py          ← Motor IA dual (Groq + Vertex), circuit breaker
│   ├── pdf_utils.py         ← Extracción texto PDF
│   ├── qa_utils.py          ← Validación fiscal DGII
│   ├── concurrent_processor.py
│   ├── auth_dependency.py   ← Verificación del JWT de Supabase Auth
│   ├── supabase_admin.py    ← Cliente Supabase (service role)
│   ├── export_utils.py
│   ├── drive_utils.py       ← Lectura de carpetas Drive públicas (Centro de importación)
│   ├── gmail_utils.py       ← Búsqueda de adjuntos por IMAP (Centro de importación)
│   ├── local_db.py          ← Directorio clientes/proveedores (tablas Supabase)
│   ├── constants.py
│   └── anexos_schema/       ← Definición de campos por anexo DGII
├── requirements.txt
├── railway.json
└── .env.example
```

### Desarrollo local

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # completar variables
uvicorn main:app --reload
# API disponible en http://localhost:8000
# Docs interactivos: http://localhost:8000/docs
```

---

## Frontend (`/frontend`)

```
frontend/
├── src/
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx
│   │   ├── Ventas.jsx
│   │   ├── Compras.jsx
│   │   ├── Retenciones.jsx
│   │   ├── SujetosExcluidos.jsx
│   │   ├── Clientes.jsx
│   │   └── Proveedores.jsx
│   ├── components/
│   │   ├── PdfUploader.jsx       ← Upload + declarante selector
│   │   └── ResultadosTabla.jsx   ← Tabla de registros extraídos
│   ├── services/
│   │   ├── supabase.js           ← Cliente Supabase
│   │   ├── auth.js               ← Hook useAuth + signIn/signOut
│   │   └── api.js                ← Llamadas al backend FastAPI (axios)
│   └── App.jsx                   ← Router + rutas protegidas
├── package.json
├── vite.config.js
├── vercel.json                    ← SPA rewrite para React Router
└── .env.example
```

### Desarrollo local

```bash
cd frontend
npm install
cp .env.example .env  # completar VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL
npm run dev
# App disponible en http://localhost:5173
```

---

## Variables de entorno

### Backend (`.env`)

| Variable | Descripción |
|----------|-------------|
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_KEY` | Anon key de Supabase |
| `SUPABASE_SERVICE_KEY` | Service role key (opcional, healthcheck y directorio de clientes/proveedores; nunca en el frontend) |
| `SUPABASE_JWT_SECRET` | Settings → API → JWT Secret — verifica el JWT emitido por Supabase Auth |
| `GROQ_API_KEY` | API key de Groq Cloud |
| `GOOGLE_APPLICATION_CREDENTIALS` | Ruta al JSON de la cuenta de servicio GCP |
| `GEMINI_API_KEY` | API key alternativa (Gemini Developer API) |
| `VERTEX_PROJECT` | ID del proyecto en Google Cloud |
| `VERTEX_LOCATION` | Región de Vertex AI (ej. `us-central1`) |
| `ENVIRONMENT` | `production` \| `development` — controla CORS estricto y HSTS |
| `ALLOWED_ORIGINS` | Orígenes CORS explícitos permitidos, separados por coma |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_BURST` | Límites de rate limiting por IP |
| `BLOCKED_IPS` | IPs bloqueadas manualmente, separadas por coma |

### Frontend (`.env`)

| Variable | Descripción |
|----------|-------------|
| `VITE_SUPABASE_URL` | URL del proyecto Supabase |
| `VITE_SUPABASE_ANON_KEY` | Anon key pública de Supabase |
| `VITE_API_URL` | URL base del backend FastAPI |

---

## Deploy

### Backend → Railway

1. Conectar repositorio en Railway
2. Configurar **Root Directory**: `backend`
3. Agregar variables de entorno (ver tabla arriba)
4. Railway detecta `backend/railway.json` y ejecuta `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Frontend → Vercel

1. Conectar repositorio en Vercel
2. Configurar **Root Directory**: `frontend`
3. Framework preset: **Vite** (Vercel detecta `frontend/vercel.json` para el rewrite SPA)
4. Agregar variables de entorno `VITE_*`
5. Agregar la URL de Vercel a `ALLOWED_ORIGINS` en el backend

### Base de datos → Supabase

Ver `db/README.md` para el orden de ejecución de los scripts SQL.

---

## Módulos DTE

| Módulo | Tipo DGII | Anexo | Validación |
|--------|-----------|-------|-----------|
| Ventas contribuyentes | CCF / NC / ND | Anexo 1 | IVA = gravadas × 13% |
| Ventas consumidor final | FC | Anexo 2 | Total = suma de columnas |
| Compras | CCF recibidos | Anexo 3 | IVA crédito fiscal |
| Retenciones | DTE-07 | Anexo 7 | IVA retenido = base × 1% |
| Sujetos Excluidos | DTE-14 | Anexo 5 | Retención renta = base × 10% |

---

## Seguridad

Ver [`docs/SECURITY.md`](docs/SECURITY.md) para el detalle completo: verificación de JWT de Supabase en el backend, RLS en Supabase (auditado, cobertura completa), rate limiting por IP, validación de input (Pydantic + magic bytes en PDFs), headers de seguridad + CORS por entorno, y manejo de secrets.

---

## Directorio de clientes/proveedores

`backend/utils/local_db.py` persiste el directorio de clientes y proveedores (usado por los extractors para autocompletar) en las tablas `clientes_directorio`/`proveedores_directorio` de Supabase (`db/06_local_data_tables.sql`), con RLS habilitado. Antes vivía en `backend/data/*.json` sobre el filesystem del backend, que en Railway es efímero y se perdía en cada redeploy — ya resuelto.

Si venías de una instalación con datos en `backend/data/*.json`, corre `scripts/migrate_local_json.py` **contra el filesystem de esa instalación, antes de actualizar a esta versión** (una vez actualizado, esos archivos ya no existen en el repo). Ver el docstring del script para el uso exacto.

**Nota de arquitectura:** el frontend (`Clientes.jsx`/`Proveedores.jsx`) lee directo de las tablas `clientes`/`proveedores` (multi-tenant, `db/01`/`db/03`) — un directorio distinto y hoy desconectado de `clientes_directorio`/`proveedores_directorio`. Unificarlos requeriría enhebrar `organizacion_id` a través de los extractors (que hoy corren sin contexto de organización); queda fuera de alcance de esta migración, documentado como mejora futura.

---

## Pendiente / limpieza futura

- `export_utils.py`, `gemini_utils.py`, `rag_validator.py`, `nit_validator.py` en `backend/utils/` no están conectados a la cadena viva del backend (`main.py` → `routers` → `extractors` → `utils`). Candidatos a limpieza o a una futura conexión, según se decida caso por caso.
- `qa_utils.py` (validadores matemáticos + `calcular_confianza`) y `gmail_utils.py`/`drive_utils.py` (Centro de importación) ya están conectados: el primero calcula el `estado`/`confianza` de cada extractor, los segundos alimentan `routers/importar.py` y el panel "Importar desde Drive o Gmail" de `PdfUploader.jsx`.
- Rate limiting en memoria → Redis, si se escala a múltiples instancias de Railway.
- Unificar `clientes_directorio`/`proveedores_directorio` con las tablas `clientes`/`proveedores` que ya usa el frontend (ver nota de arquitectura arriba) — requiere enhebrar `organizacion_id` por los extractors.
- Sistema de diseño: los tokens de color/tipografía/radios de Certia (ContaSV) ya están aplicados vía `frontend/tailwind.config.js` + `frontend/src/index.css` (heredado por toda la UI), incluyendo los componentes editoriales (`.registro-seal`, `.rule-double`, `.stamp`).
- No hay tests ni CI en el repo.
