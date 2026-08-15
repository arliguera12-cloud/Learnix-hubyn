"""
auth_dependency.py — Verificación del JWT emitido por Supabase Auth.

El frontend inicia sesión directamente contra Supabase (supabase-js) y adjunta
el access_token real en cada request al backend (ver frontend/src/services/api.js).
Este módulo solo verifica la firma/expiración de ese token — no emite ni gestiona
sesiones (eso lo hace Supabase).
"""
from __future__ import annotations

import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


def _get_jwt_secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET no está configurado. "
            "Cópialo de Supabase → Settings → API → JWT Secret."
        )
    return secret


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            _get_jwt_secret(),
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"user_id": payload["sub"], "email": payload.get("email")}
