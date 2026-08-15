"""
schemas/procesamiento.py — Validación de los campos de formulario que
acompañan cada PDF subido a /procesar/*.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DeclaranteFields(BaseModel):
    declarante_id: str = Field(min_length=1, max_length=20, pattern=r"^[0-9A-Za-z\-]+$")
    nombre_declarante: str = Field("", max_length=200)
    nrc_declarante: str = Field("", max_length=20, pattern=r"^[0-9A-Za-z\-]*$")
