"""
Endpoints de extracción de DTEs.
Cada endpoint recibe un PDF (multipart/form-data) y devuelve JSON estructurado
con los registros extraídos, listos para guardarse en Supabase.
"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper compartido
# ---------------------------------------------------------------------------

def _read_pdf_bytes(file: UploadFile) -> bytes:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    return file.file.read()


# ---------------------------------------------------------------------------
# Ventas (CCF / Factura consumidor final)
# ---------------------------------------------------------------------------

@router.post("/ventas")
async def procesar_ventas(
    file: UploadFile = File(..., description="PDF del DTE de ventas"),
    declarante_id: str = Form(..., description="ID del declarante en Supabase"),
):
    """
    Extrae registros de un DTE de ventas (contribuyentes o consumidor final).
    Devuelve lista de registros validados con estructura del Anexo 1/2 DGII.
    """
    pdf_bytes = _read_pdf_bytes(file)
    # TODO: invocar lógica de extracción desde extractors/ventas.py
    return {
        "tipo": "ventas",
        "declarante_id": declarante_id,
        "filename": file.filename,
        "registros": [],
        "status": "pendiente_implementacion",
    }


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------

@router.post("/compras")
async def procesar_compras(
    file: UploadFile = File(..., description="PDF del DTE de compras"),
    declarante_id: str = Form(..., description="ID del declarante en Supabase"),
):
    """Extrae registros de un DTE de compras. Estructura Anexo 3 DGII."""
    pdf_bytes = _read_pdf_bytes(file)
    return {
        "tipo": "compras",
        "declarante_id": declarante_id,
        "filename": file.filename,
        "registros": [],
        "status": "pendiente_implementacion",
    }


# ---------------------------------------------------------------------------
# Retenciones
# ---------------------------------------------------------------------------

@router.post("/retenciones")
async def procesar_retenciones(
    file: UploadFile = File(..., description="PDF del DTE de retenciones"),
    declarante_id: str = Form(..., description="ID del declarante en Supabase"),
):
    """Extrae registros de un DTE de retenciones (casilla 162 / 1%). Anexo 7 DGII."""
    pdf_bytes = _read_pdf_bytes(file)
    return {
        "tipo": "retenciones",
        "declarante_id": declarante_id,
        "filename": file.filename,
        "registros": [],
        "status": "pendiente_implementacion",
    }


# ---------------------------------------------------------------------------
# Sujetos Excluidos
# ---------------------------------------------------------------------------

@router.post("/sujetos-excluidos")
async def procesar_sujetos_excluidos(
    file: UploadFile = File(..., description="PDF del DTE de sujetos excluidos"),
    declarante_id: str = Form(..., description="ID del declarante en Supabase"),
):
    """Extrae registros de un DTE de sujetos excluidos (casilla 66). Anexo 5 DGII."""
    pdf_bytes = _read_pdf_bytes(file)
    return {
        "tipo": "sujetos_excluidos",
        "declarante_id": declarante_id,
        "filename": file.filename,
        "registros": [],
        "status": "pendiente_implementacion",
    }


# ---------------------------------------------------------------------------
# Declarantes
# ---------------------------------------------------------------------------

@router.get("/declarantes")
async def listar_declarantes():
    """Lista los declarantes registrados en Supabase."""
    # TODO: integrar con supabase_client
    return {"declarantes": [], "status": "pendiente_implementacion"}
