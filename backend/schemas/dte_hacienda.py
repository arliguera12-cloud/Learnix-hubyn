"""
schemas/dte_hacienda.py — Modelos Pydantic para el JSON firmado por Hacienda (dteJson).

Refleja únicamente los campos que ya lee backend/utils/concurrent_processor.py
(procesar_json_nativo_ventas/_compras) — no se inventan campos nuevos del schema
oficial de Hacienda que el resto del pipeline no usa.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DTEIdentificacion(BaseModel):
    tipoDte: str
    numeroControl: str
    codigoGeneracion: str = ""
    fecEmi: str = ""
    horEmi: str = ""


class DTEEmisor(BaseModel):
    nit: str = ""
    nrc: str = ""
    dui: str = ""
    numDocumento: str = ""
    nombre: str = ""


class DTEReceptor(BaseModel):
    nit: str = ""
    nrc: str = ""
    dui: str = ""
    numDocumento: str = ""
    nombre: str = ""


class DTETributo(BaseModel):
    codigo: str = ""
    descripcion: str = ""
    valor: float = 0.0


class DTEResumen(BaseModel):
    totalGravada: float = 0.0
    totalExenta: float = 0.0
    totalNoSuj: float = 0.0
    totalIva: float = 0.0
    totalPagar: float = 0.0
    tributos: list[DTETributo] = Field(default_factory=list)


class DTESujetoExcluido(BaseModel):
    nombre: str = ""
    documento: str = ""
    nit: str = ""
    dui: str = ""


class DTEDocumento(BaseModel):
    """Modelo raíz — corresponde al contenido de `dteJson` en el JSON firmado por Hacienda."""
    identificacion: DTEIdentificacion
    emisor: DTEEmisor = Field(default_factory=DTEEmisor)
    receptor: DTEReceptor = Field(default_factory=DTEReceptor)
    resumen: DTEResumen = Field(default_factory=DTEResumen)
    sujetoExcluido: DTESujetoExcluido | None = None
