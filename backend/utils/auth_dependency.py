"""
auth_dependency.py — Verificación del JWT emitido por Supabase Auth.

El frontend inicia sesión directamente contra Supabase (supabase-js) y adjunta
el access_token real en cada request al backend (ver frontend/src/services/api.js).
Este módulo solo verifica la firma/expiración de ese token — no emite ni gestiona
sesiones (eso lo hace Supabase).

Sobre el algoritmo de firma
---------------------------
Supabase migró a claves de firma asimétricas: los proyectos nuevos firman los
access_token con ECC (ES256) y publican la clave pública en el JWKS del
proyecto. El secreto compartido HS256 queda como "Legacy JWT Secret" y solo
sirve para verificar tokens emitidos antes de la migración.

Este módulo elige el camino según el encabezado del propio token:

  - ES256 / RS256  → clave pública obtenida del JWKS (con caché y refresco
                     automático ante rotación de claves).
  - HS256          → SUPABASE_JWT_SECRET, el secreto legacy.

Así funcionan tanto los proyectos ya migrados como los que todavía firman con
el secreto compartido, sin configuración adicional.
"""
from __future__ import annotations

import os
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

# Algoritmos asimétricos que Supabase puede usar para firmar. La verificación
# nunca se deja a elección del token: se comprueba que el `alg` declarado esté
# en esta lista (o sea HS256) antes de decidir con qué clave validar.
_ALGORITMOS_ASIMETRICOS = ("ES256", "RS256")


def _supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    if not url:
        raise RuntimeError(
            "SUPABASE_URL no está configurado. Cópialo de Supabase → "
            "Project Settings → General (o constrúyelo con el Project ID: "
            "https://<project-id>.supabase.co)."
        )
    return url


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """
    Cliente JWKS del proyecto, memorizado.

    PyJWKClient cachea el juego de claves y lo vuelve a pedir automáticamente
    cuando aparece un `kid` desconocido, que es justo lo que ocurre cuando se
    rota la clave de firma en Supabase. Por eso no hace falta invalidar nada a
    mano al rotar.
    """
    return jwt.PyJWKClient(
        f"{_supabase_url()}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
        lifespan=600,
    )


def _clave_de_verificacion(token: str, alg: str):
    """Devuelve la clave con la que debe verificarse este token."""
    if alg in _ALGORITMOS_ASIMETRICOS:
        return _jwks_client().get_signing_key_from_jwt(token).key

    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "El token viene firmado con HS256 pero SUPABASE_JWT_SECRET no está "
            "configurado. Cópialo de Supabase → Project Settings → JWT Keys → "
            "pestaña 'Legacy JWT Secret'."
        )
    return secret


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependencia síncrona a propósito: la obtención del JWKS hace una petición
    HTTP bloqueante la primera vez y cada vez que caduca la caché. Declarada
    con `def`, FastAPI la ejecuta en su threadpool y no bloquea el event loop.
    """
    token = credentials.credentials

    try:
        encabezado = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    alg = encabezado.get("alg")
    if alg not in (*_ALGORITMOS_ASIMETRICOS, "HS256"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Algoritmo de firma no admitido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        clave = _clave_de_verificacion(token, alg)
    except jwt.PyJWKClientError as exc:
        # No se pudo resolver la clave pública (JWKS inalcanzable o sin el kid).
        # Es un fallo de configuración/infraestructura, no una credencial mala.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo obtener la clave de verificación: {exc}",
        )

    try:
        payload = jwt.decode(
            token,
            clave,
            algorithms=[alg],
            audience="authenticated",
            issuer=f"{_supabase_url()}/auth/v1",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidIssuerError:
        # Suele significar que SUPABASE_URL del backend apunta a un proyecto
        # distinto del que usa el frontend. Se distingue del resto de fallos
        # porque el remedio es de configuración, no de credenciales.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "El token fue emitido por otro proyecto de Supabase. Revisa que "
                "SUPABASE_URL del backend y VITE_SUPABASE_URL del frontend "
                "apunten al mismo proyecto."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"user_id": payload["sub"], "email": payload.get("email")}
