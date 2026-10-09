"""
routers/mh_relay.py — Endpoints que usa el worker de consultas a Hacienda
(scripts/mh_worker). Ver utils/mh_relay.py para el flujo completo.

Autenticación: encabezado `X-Relay-Token` contra la variable MH_RELAY_TOKEN
(mínimo 32 caracteres; si no está definida o es corta, los endpoints responden
503 y el modo relay queda inutilizable en vez de abierto). No usa el login de
usuarios: el worker no es una persona ni pertenece a una organización.

El worker no manda "a qué URL consultar": solo reclama códigos de la cola y
devuelve lo que Hacienda respondió, así que este endpoint no sirve de proxy
abierto. Los intentos fallidos de token se limitan por IP.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from middleware.rate_limit import _get_client_ip, consumir_cupo
from utils import mh_relay

router = APIRouter()

_TOKEN_MIN = 32
_FALLOS_POR_MINUTO = 10


def _exigir_token(request: Request, token: str | None) -> None:
    esperado = os.environ.get("MH_RELAY_TOKEN", "")
    if len(esperado) < _TOKEN_MIN:
        raise HTTPException(503, "Relay de Hacienda no configurado")
    ip = _get_client_ip(request)
    if not token or not hmac.compare_digest(token.encode(), esperado.encode()):
        if not consumir_cupo(f"relay-fallo:{ip}", _FALLOS_POR_MINUTO):
            raise HTTPException(429, "Demasiados intentos", headers={"Retry-After": "60"})
        raise HTTPException(401, "Token inválido")


class ReclamarIn(BaseModel):
    max: int = Field(default=3, ge=1, le=5)


class ResultadoIn(BaseModel):
    codigo_generacion: str
    fecha_emi: str
    ambiente: str = "01"
    # Código HTTP que dio Hacienda; 0 = no se pudo consultar (red, pausa por tope).
    http_status: int = Field(ge=0, le=599)
    cuerpo: dict | None = None
    error: str | None = Field(default=None, max_length=300)


@router.get("/ping")
def ping(request: Request, x_relay_token: str | None = Header(default=None)):
    """Para que el instalador del worker compruebe URL y token."""
    _exigir_token(request, x_relay_token)
    mh_relay.registrar_latido()
    return {"ok": True}


@router.post("/reclamar")
def reclamar(body: ReclamarIn, request: Request, x_relay_token: str | None = Header(default=None)):
    _exigir_token(request, x_relay_token)
    return {"trabajos": mh_relay.reclamar_trabajos(body.max)}


@router.post("/resultado")
def resultado(body: ResultadoIn, request: Request, x_relay_token: str | None = Header(default=None)):
    _exigir_token(request, x_relay_token)
    try:
        estado = mh_relay.guardar_resultado(
            body.codigo_generacion.strip().upper(), body.fecha_emi.strip(), body.ambiente,
            body.http_status, body.cuerpo, body.error,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"estado": estado}
