"""
schemas/dte_hacienda.py — Modelos Pydantic para el JSON firmado por Hacienda (dteJson).

Refleja únicamente los campos que ya lee backend/utils/concurrent_processor.py
(procesar_json_nativo_ventas/_compras) — no se inventan campos nuevos del schema
oficial de Hacienda que el resto del pipeline no usa.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class _ModeloDTE(BaseModel):
    """
    Base que trata un campo con valor `null` como ausente.

    Hacienda no omite las claves opcionales: las envía con `null` (por ejemplo
    `receptor.nrc` en un consumidor final). Declarar `nrc: str = ""` solo cubre
    la clave ausente — con la clave presente y en `null`, Pydantic rechazaba el
    documento entero con "Input should be a valid string". Al descartar los
    nulos antes de validar, cada campo cae en su valor por defecto y los
    obligatorios siguen fallando si de verdad faltan.
    """

    @model_validator(mode="before")
    @classmethod
    def _descartar_nulos(cls, datos):
        if isinstance(datos, dict):
            return {k: v for k, v in datos.items() if v is not None}
        return datos


class DTEIdentificacion(_ModeloDTE):
    tipoDte: str
    numeroControl: str
    codigoGeneracion: str = ""
    fecEmi: str = ""
    horEmi: str = ""


class DTEEmisor(_ModeloDTE):
    nit: str = ""
    nrc: str = ""
    dui: str = ""
    numDocumento: str = ""
    nombre: str = ""


class DTEReceptor(_ModeloDTE):
    nit: str = ""
    nrc: str = ""
    dui: str = ""
    numDocumento: str = ""
    nombre: str = ""


class DTETributo(_ModeloDTE):
    codigo: str = ""
    descripcion: str = ""
    valor: float = 0.0


class DTEResumen(_ModeloDTE):
    totalGravada: float = 0.0
    totalExenta: float = 0.0
    totalNoSuj: float = 0.0
    totalIva: float = 0.0
    totalPagar: float = 0.0
    tributos: list[DTETributo] = Field(default_factory=list)


class DTESujetoExcluido(_ModeloDTE):
    nombre: str = ""
    documento: str = ""
    nit: str = ""
    dui: str = ""


class DTEDocumento(_ModeloDTE):
    """Modelo raíz — corresponde al contenido de `dteJson` en el JSON firmado por Hacienda."""
    identificacion: DTEIdentificacion
    emisor: DTEEmisor = Field(default_factory=DTEEmisor)
    receptor: DTEReceptor = Field(default_factory=DTEReceptor)
    resumen: DTEResumen = Field(default_factory=DTEResumen)
    sujetoExcluido: DTESujetoExcluido | None = None
