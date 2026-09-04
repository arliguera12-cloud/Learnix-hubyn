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
    # Normativa de Cumplimiento DTE 2.0 (obligatoria desde el 01/12/2026):
    # el número de control pasa a ser consecutivo por establecimiento/punto
    # de venta en vez de un único correlativo global. Estos campos ya
    # existen en el JSON de Hacienda hoy (identifican dónde se emitió el
    # documento) pero no se leían — se agregan tolerantes (no rompen nada
    # si faltan) para no tener que tocar el schema de nuevo cuando 2.0 sea
    # obligatorio. Aún no se usan en ningún cálculo del pipeline.
    codEstableMH: str = ""
    codEstable: str = ""
    codPuntoVentaMH: str = ""
    codPuntoVenta: str = ""


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
    # DTE 2.0: desglose de forma de pago y saldo a favor. `pagos` trae
    # forma de pago/monto/referencia por Hacienda; se captura como lista
    # de dicts sin tipar cada campo (no hay un uso todavía en el pipeline,
    # y tipar de más algo que no se usa es más riesgo de romper el parseo
    # que beneficio).
    pagos: list[dict] = Field(default_factory=list)
    saldoFavor: float = 0.0
    numPagoElectronico: str = ""


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
    # DTE 2.0: campos nuevos del esquema, capturados de forma tolerante.
    # numeroDocumento reemplaza/acompaña al numeroControl en ciertos tipos;
    # placaVehiculo aplica a documentos de transporte de carga.
    numeroDocumento: str = ""
    observaciones: str = ""
    placaVehiculo: str = ""
