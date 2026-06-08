"""
Endpoints de extracción de DTEs.
Cada endpoint recibe un PDF (multipart/form-data) y devuelve JSON estructurado
con los datos extraídos, listos para guardarse en Supabase.
"""
import sys
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import List

# Asegurar que backend/ esté en el path para que utils.* funcionen
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from extractors.ventas import extraer_venta_nativo_pro
from extractors.compras import extraer_compra_nativo_pro
from extractors.retenciones import extraer_retencion_nativa
from extractors.sujetos_excluidos import extraer_sujetos_nativo

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper compartido
# ---------------------------------------------------------------------------

def _read_pdf_bytes(file: UploadFile) -> bytes:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    return file.file.read()


def _build_cliente_activo(declarante_id: str, nombre: str = "", nit: str = "",
                           dui: str = "", nrc: str = "") -> dict:
    """Construye el dict cliente_activo que esperan los extractores."""
    return {
        "id":      declarante_id,
        "nit":     nit or declarante_id,
        "nombre":  nombre,
        "dui":     dui,
        "nrc":     nrc,
    }


def _handle_extractor_result(result: dict, tipo: str, filename: str, declarante_id: str) -> dict:
    """Normaliza la respuesta del extractor al formato de la API."""
    if "error_fatal" in result:
        raise HTTPException(status_code=422, detail=result["error_fatal"])
    if "error_tipo" in result:
        raise HTTPException(status_code=422, detail=result["error_tipo"])
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    # Separar campos internos de la respuesta al cliente
    campos_internos = {"_vision_campos", "_vision_alertas", "_vision_audit"}
    registro_limpio = {k: v for k, v in result.items() if k not in campos_internos}

    return {
        "tipo":           tipo,
        "declarante_id":  declarante_id,
        "filename":       filename,
        "registro":       registro_limpio,
        "correcciones_ia": result.get("gemini_correcciones", []),
        "vision_campos":  result.get("_vision_campos", {}),
    }


# ---------------------------------------------------------------------------
# Ventas (CCF / Factura consumidor final)
# ---------------------------------------------------------------------------

@router.post("/ventas")
async def procesar_ventas(
    file: UploadFile = File(..., description="PDF del DTE de ventas"),
    declarante_id: str = Form(..., description="ID del declarante (NIT sin guiones)"),
    nombre_declarante: str = Form("", description="Nombre/razón social del declarante"),
    nrc_declarante: str = Form("", description="NRC del declarante"),
):
    """
    Extrae los datos de un DTE de ventas.
    Devuelve un registro con estructura del Anexo 1 (contribuyentes) o Anexo 2 (consumidor final).
    """
    pdf_bytes = _read_pdf_bytes(file)
    cliente = _build_cliente_activo(
        declarante_id,
        nombre=nombre_declarante,
        nrc=nrc_declarante,
    )
    result = extraer_venta_nativo_pro(pdf_bytes, cliente)
    return _handle_extractor_result(result, "ventas", file.filename, declarante_id)


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------

@router.post("/compras")
async def procesar_compras(
    file: UploadFile = File(..., description="PDF del DTE de compras"),
    declarante_id: str = Form(..., description="ID del declarante (NIT sin guiones)"),
    nombre_declarante: str = Form("", description="Nombre/razón social del declarante"),
    nrc_declarante: str = Form("", description="NRC del declarante"),
):
    """
    Extrae los datos de un DTE de compras.
    Devuelve un registro con estructura del Anexo 3 DGII.
    """
    pdf_bytes = _read_pdf_bytes(file)
    cliente = _build_cliente_activo(
        declarante_id,
        nombre=nombre_declarante,
        nrc=nrc_declarante,
    )
    result = extraer_compra_nativo_pro(pdf_bytes, cliente)
    return _handle_extractor_result(result, "compras", file.filename, declarante_id)


# ---------------------------------------------------------------------------
# Retenciones
# ---------------------------------------------------------------------------

@router.post("/retenciones")
async def procesar_retenciones(
    file: UploadFile = File(..., description="PDF del DTE de retenciones"),
    declarante_id: str = Form(..., description="ID del declarante (NIT sin guiones)"),
    nombre_declarante: str = Form("", description="Nombre/razón social del declarante"),
):
    """
    Extrae los datos de un DTE de retenciones (DTE-07, casilla 162 / IVA 1%).
    Devuelve un registro con estructura del Anexo 7 DGII.
    """
    pdf_bytes = _read_pdf_bytes(file)
    cliente = _build_cliente_activo(declarante_id, nombre=nombre_declarante)
    result = extraer_retencion_nativa(pdf_bytes, cliente)
    return _handle_extractor_result(result, "retenciones", file.filename, declarante_id)


# ---------------------------------------------------------------------------
# Sujetos Excluidos
# ---------------------------------------------------------------------------

@router.post("/sujetos-excluidos")
async def procesar_sujetos_excluidos(
    file: UploadFile = File(..., description="PDF del DTE de sujetos excluidos"),
    declarante_id: str = Form(..., description="ID del declarante (NIT sin guiones)"),
    nombre_declarante: str = Form("", description="Nombre/razón social del declarante"),
):
    """
    Extrae los datos de un DTE de sujetos excluidos (DTE-14, casilla 66 / retención renta 10%).
    Devuelve un registro con estructura del Anexo 5 DGII.
    """
    pdf_bytes = _read_pdf_bytes(file)
    cliente = _build_cliente_activo(declarante_id, nombre=nombre_declarante)
    result = extraer_sujetos_nativo(pdf_bytes, cliente)
    return _handle_extractor_result(result, "sujetos_excluidos", file.filename, declarante_id)


# ---------------------------------------------------------------------------
# Lote (multi-PDF)
# ---------------------------------------------------------------------------

def _process_lote(files: List[UploadFile], extractor_fn, tipo: str,
                  declarante_id: str, nombre_declarante: str = "", nrc_declarante: str = "") -> dict:
    cliente = _build_cliente_activo(declarante_id, nombre=nombre_declarante, nrc=nrc_declarante)
    resultados = []
    errores = []
    for f in files:
        try:
            pdf_bytes = _read_pdf_bytes(f)
            result = extractor_fn(pdf_bytes, cliente)
            resultados.append(_handle_extractor_result(result, tipo, f.filename, declarante_id))
        except HTTPException as e:
            errores.append({"filename": f.filename, "error": e.detail})
        except Exception as e:
            errores.append({"filename": f.filename, "error": str(e)})
    return {"resultados": resultados, "errores": errores, "total": len(files),
            "exitosos": len(resultados), "fallidos": len(errores)}


@router.post("/ventas/lote")
async def procesar_ventas_lote(
    files: List[UploadFile] = File(...),
    declarante_id: str = Form(...),
    nombre_declarante: str = Form(""),
    nrc_declarante: str = Form(""),
):
    return _process_lote(files, extraer_venta_nativo_pro, "ventas",
                         declarante_id, nombre_declarante, nrc_declarante)


@router.post("/compras/lote")
async def procesar_compras_lote(
    files: List[UploadFile] = File(...),
    declarante_id: str = Form(...),
    nombre_declarante: str = Form(""),
    nrc_declarante: str = Form(""),
):
    return _process_lote(files, extraer_compra_nativo_pro, "compras",
                         declarante_id, nombre_declarante, nrc_declarante)


@router.post("/retenciones/lote")
async def procesar_retenciones_lote(
    files: List[UploadFile] = File(...),
    declarante_id: str = Form(...),
    nombre_declarante: str = Form(""),
):
    return _process_lote(files, extraer_retencion_nativa, "retenciones",
                         declarante_id, nombre_declarante)


@router.post("/sujetos-excluidos/lote")
async def procesar_sujetos_excluidos_lote(
    files: List[UploadFile] = File(...),
    declarante_id: str = Form(...),
    nombre_declarante: str = Form(""),
):
    return _process_lote(files, extraer_sujetos_nativo, "sujetos_excluidos",
                         declarante_id, nombre_declarante)


# ---------------------------------------------------------------------------
# Declarantes
# ---------------------------------------------------------------------------

@router.get("/declarantes")
async def listar_declarantes():
    """Lista los declarantes (clientes activos) registrados en local_db."""
    try:
        from utils.local_db import cargar_clientes_db
        clientes = cargar_clientes_db()
        return {"declarantes": clientes, "total": len(clientes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
