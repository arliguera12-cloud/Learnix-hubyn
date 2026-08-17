import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from middleware.rate_limit import rate_limit_middleware
from routers import procesamiento, exportar, importar

app = FastAPI(
    title="Learnix DTE Hub API",
    description="API para extracción y gestión de DTEs — El Salvador",
    version="2.0.0",
)

# ---------------------------------------------------------------------------
# Rate limiting — registrado antes de CORS para rechazar temprano
# ---------------------------------------------------------------------------
app.middleware("http")(rate_limit_middleware)


# ---------------------------------------------------------------------------
# CORS — en producción, solo orígenes explícitos. El regex de *.vercel.app
# (útil para preview deploys) solo aplica fuera de producción.
# ---------------------------------------------------------------------------
def _get_allowed_origins() -> list[str]:
    origins = [
        o.strip()
        for o in os.environ.get("ALLOWED_ORIGINS", "").split(",")
        if o.strip()
    ]
    # Compat con el nombre anterior de la variable
    origins += [
        o.strip()
        for o in os.environ.get("EXTRA_CORS_ORIGINS", "").split(",")
        if o.strip()
    ]
    if os.environ.get("ENVIRONMENT", "production") != "production":
        origins += ["http://localhost:5173", "http://localhost:3000"]
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_origin_regex=(
        r"https://.*\.vercel\.app"
        if os.environ.get("ENVIRONMENT", "production") != "production"
        else None
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if os.environ.get("ENVIRONMENT", "production") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(procesamiento.router, prefix="/procesar", tags=["Procesamiento DTEs"])
app.include_router(exportar.router, prefix="/exportar", tags=["Exportación"])
app.include_router(importar.router, prefix="/importar", tags=["Importación"])


@app.get("/health", tags=["Sistema"])
def health_check():
    checks = {"api": "ok"}
    try:
        from utils.supabase_admin import get_supabase

        get_supabase().table("organizaciones").select("id").limit(1).execute()
        checks["database"] = "connected"
    except Exception as exc:
        checks["database"] = "disconnected"
        checks["db_error"] = str(exc)[:100]

    overall = "ok" if checks["database"] == "connected" else "degraded"
    return {"status": overall, "service": "Learnix DTE Hub API", "version": "2.0.0", "checks": checks}
