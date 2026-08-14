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
├── main.py                  ← FastAPI app, CORS, routers
├── routers/
│   ├── auth.py              ← POST /auth/login, POST /auth/logout
│   ├── procesamiento.py     ← POST /procesar/{ventas,compras,retenciones,sujetos-excluidos}
│   │                           GET  /procesar/declarantes
│   └── exportar.py          ← GET  /exportar/excel
├── extractors/              ← Lógica de extracción por tipo de DTE
│   ├── ventas.py
│   ├── compras.py
│   ├── retenciones.py
│   └── sujetos_excluidos.py
├── utils/
│   ├── ai_utils.py          ← Motor IA dual (Groq + Vertex), circuit breaker
│   ├── pdf_utils.py         ← Extracción texto PDF
│   ├── qa_utils.py          ← Validación fiscal DGII
│   ├── concurrent_processor.py
│   ├── supabase_client.py
│   ├── export_utils.py
│   ├── local_db.py          ← Almacenamiento local JSON (clientes/proveedores)
│   ├── constants.py
│   └── anexos_schema/       ← Definición de campos por anexo DGII
├── data/                    ← clientes.json / proveedores.json (almacenamiento local)
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
| `SUPABASE_KEY` | Service role key de Supabase |
| `GROQ_API_KEY` | API key de Groq Cloud |
| `GOOGLE_APPLICATION_CREDENTIALS` | Ruta al JSON de la cuenta de servicio GCP |
| `GEMINI_API_KEY` | API key alternativa (Gemini Developer API) |
| `VERTEX_PROJECT` | ID del proyecto en Google Cloud |
| `VERTEX_LOCATION` | Región de Vertex AI (ej. `us-central1`) |
| `APP_PASSWORD` | Contraseña de acceso a la app |
| `EXTRA_CORS_ORIGINS` | Orígenes CORS extra permitidos, separados por coma |
| `LOCAL_DB_DIR` | Override opcional de la ruta de `data/` (ver nota abajo) |

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
5. Agregar la URL de Vercel a `EXTRA_CORS_ORIGINS` en el backend

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

## Nota sobre almacenamiento local

`backend/utils/local_db.py` guarda clientes y proveedores en `backend/data/*.json`. En Railway este directorio es efímero (se reinicia en cada deploy), así que este almacenamiento es apto para desarrollo local pero no para producción estable. Migrar clientes/proveedores a tablas de Supabase queda como mejora futura.
