"""
schemas/importar.py — Validación de los endpoints de /importar/* (Drive y
Gmail). Las credenciales (API Key, contraseña de aplicación) viajan en el
cuerpo de la petición y no se guardan en el backend: se usan una sola vez
para la llamada a Google y se descartan al terminar el request.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DriveListarRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=500)
    recursivo: bool = True
    max_archivos: int = Field(200, ge=1, le=500)


class DriveArchivoRef(BaseModel):
    id: str
    name: str = ""
    resourceKey: str | None = None
    carpeta: str = ""


class DriveDescargarRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=200)
    archivos: list[DriveArchivoRef] = Field(min_length=1, max_length=200)


class GmailBuscarRequest(BaseModel):
    email: str = Field(min_length=1, max_length=200)
    app_password: str = Field(min_length=1, max_length=64)
    remitente: str = Field("", max_length=500)
    texto: str = Field("", max_length=200)
    dias: int = Field(30, ge=1, le=365)
    max_correos: int = Field(50, ge=1, le=200)
