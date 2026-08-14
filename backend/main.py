import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, procesamiento, exportar

app = FastAPI(
    title="Learnix DTE Hub API",
    description="API para extracción y gestión de DTEs — El Salvador",
    version="2.0.0",
)

# Orígenes permitidos: desarrollo local + orígenes extra vía env (p. ej. tu URL de Vercel)
_extra_origins = [
    o.strip() for o in os.environ.get("EXTRA_CORS_ORIGINS", "").split(",") if o.strip()
]
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    *_extra_origins,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
app.include_router(procesamiento.router, prefix="/procesar", tags=["Procesamiento DTEs"])
app.include_router(exportar.router, prefix="/exportar", tags=["Exportación"])


@app.get("/health", tags=["Sistema"])
def health_check():
    return {"status": "ok", "service": "Learnix DTE Hub API", "version": "2.0.0"}
