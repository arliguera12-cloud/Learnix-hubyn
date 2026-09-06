"""
Endpoints del Centro de Importación: traer PDF/JSON de facturas desde una
carpeta de Google Drive compartida o desde adjuntos de Gmail, sin que el
usuario tenga que descargarlos a mano primero.

Existía como componente de Streamlit (components/drive_import.py,
components/gmail_import.py) pero se quedó sin conectar al reescribir el
backend a FastAPI — utils/drive_utils.py y utils/gmail_utils.py seguían
completos y sin usar. Este router es la reconexión: misma lógica de
descarga, expuesta ahora como API para el frontend React.

Las credenciales (API Key de Drive, contraseña de aplicación de Gmail) solo
viven en memoria durante el request; no se persisten ni se registran en
logs.

Estos endpoints prueban credenciales de terceros contra Google, así que
llevan un límite propio por usuario además del límite general por IP: sin él,
el backend servía de proxy para intentar contraseñas de aplicación de Gmail
o API keys de Drive a ritmo de IP rotada.
"""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status

from middleware.rate_limit import consumir_cupo
from schemas.importar import (
    DriveDescargarRequest,
    DriveListarRequest,
    GmailBuscarRequest,
)
from utils.auth_dependency import get_current_user
from utils.drive_utils import DriveError, descargar_como_drivefiles, listar_archivos
from utils.gmail_utils import GmailError, buscar_adjuntos

router = APIRouter(dependencies=[Depends(get_current_user)])

# Un usuario legítimo conecta su Drive o Gmail unas pocas veces por minuto;
# probar credenciales requiere órdenes de magnitud más.
_INTENTOS_POR_MINUTO = 10


def _limitar_por_usuario(operacion: str, user: dict) -> None:
    if not consumir_cupo(f"{operacion}:{user['user_id']}", _INTENTOS_POR_MINUTO):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de conexión — espera un minuto",
            headers={"Retry-After": "60"},
        )


@router.post("/drive/listar")
def drive_listar(datos: DriveListarRequest, user: dict = Depends(get_current_user)):
    _limitar_por_usuario("drive", user)
    try:
        archivos = listar_archivos(
            datos.api_key,
            datos.url,
            recursivo=datos.recursivo,
            max_archivos=datos.max_archivos,
        )
    except DriveError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"archivos": archivos}


@router.post("/drive/descargar")
def drive_descargar(datos: DriveDescargarRequest, user: dict = Depends(get_current_user)):
    _limitar_por_usuario("drive", user)
    items = [item.model_dump() for item in datos.archivos]
    archivos_ok, errores = descargar_como_drivefiles(datos.api_key, items)
    return {
        "archivos": [
            {
                "name": archivo.name,
                "carpeta": archivo.carpeta,
                "contenido_base64": base64.b64encode(archivo.getvalue()).decode("ascii"),
            }
            for archivo in archivos_ok
        ],
        "errores": [{"name": nombre, "error": mensaje} for nombre, mensaje in errores],
    }


@router.post("/gmail/buscar")
def gmail_buscar(datos: GmailBuscarRequest, user: dict = Depends(get_current_user)):
    _limitar_por_usuario("gmail", user)
    try:
        adjuntos = buscar_adjuntos(
            datos.email,
            datos.app_password,
            remitente=datos.remitente,
            texto=datos.texto,
            dias=datos.dias,
            max_correos=datos.max_correos,
        )
    except GmailError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return {
        "adjuntos": [
            {
                "filename": a["filename"],
                "size": a["size"],
                "remitente": a["remitente"],
                "asunto": a["asunto"],
                "fecha": a["fecha"],
                "contenido_base64": base64.b64encode(a["data"]).decode("ascii"),
            }
            for a in adjuntos
        ]
    }
