"""
Endpoints de extracción de DTEs.
Cada endpoint recibe un PDF o (ventas/compras) un JSON firmado por Hacienda
(multipart/form-data) y devuelve JSON estructurado con los datos extraídos,
listos para guardarse en Supabase.
"""
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from typing import List

from extractors.ventas import extraer_venta_nativo_pro
from extractors.compras import extraer_compra_nativo_pro
from extractors.retenciones import extraer_retencion_nativa
from extractors.sujetos_excluidos import extraer_sujetos_nativo
from schemas.procesamiento import DeclaranteFields
from utils.concurrent_processor import procesar_json_nativo_ventas, procesar_json_nativo_compras
from utils.dte_json import cargar_json as _cargar_json_dte
from utils.org_context import get_current_org
from utils import jobs as jobs_store

router = APIRouter(dependencies=[Depends(get_current_org)])

_MAX_PDF_SIZE = 10 * 1024 * 1024   # 10MB
_MAX_JSON_SIZE = 2 * 1024 * 1024   # 2MB
_MAX_LOTE_ARCHIVOS = 15             # ver TAMANO_TANDA en frontend/src/utils/dte.jsx — con más,
                                     # el pico de memoria de Visión en paralelo tumbaba el contenedor


# ---------------------------------------------------------------------------
# Helper compartido
# ---------------------------------------------------------------------------

def _read_upload_bytes(file: UploadFile, permitir_json: bool = False) -> tuple[bytes, str]:
    """
    Lee y valida el archivo subido. Acepta .pdf siempre; .json solo cuando
    permitir_json=True (hoy: ventas y compras, que tienen parser JSON nativo
    contra el schema oficial de Hacienda — ver utils/concurrent_processor.py).

    Returns:
        (bytes, "pdf"|"json")
    """
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        content = file.file.read()
        if len(content) > _MAX_PDF_SIZE:
            raise HTTPException(status_code=400, detail="El archivo excede 10MB")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="El archivo no es un PDF válido")
        return content, "pdf"

    if filename.endswith(".json"):
        if not permitir_json:
            raise HTTPException(
                status_code=400,
                detail="Este tipo de DTE aún no soporta carga de JSON, solo PDF",
            )
        content = file.file.read()
        if len(content) > _MAX_JSON_SIZE:
            raise HTTPException(status_code=400, detail="El archivo JSON excede 2MB")
        try:
            # Decodificación tolerante: hay emisores que entregan el DTE en
            # Latin-1, y json.loads sobre bytes asume UTF-8.
            _cargar_json_dte(content)
        except Exception:
            raise HTTPException(status_code=400, detail="El archivo no es un JSON válido")
        return content, "json"

    tipos_aceptados = "PDF o JSON" if permitir_json else "PDF"
    raise HTTPException(status_code=400, detail=f"Solo se aceptan archivos {tipos_aceptados}")


def _build_cliente_activo(declarante_id: str, organizacion_id: str, nombre: str = "",
                          nit: str = "", dui: str = "", nrc: str = "") -> dict:
    """
    Valida los campos del declarante y construye el dict que esperan los
    extractores. `organizacion_id` viaja acá dentro porque los extractores
    consultan el directorio de clientes/proveedores (utils/local_db.py) y ese
    directorio está aislado por organización — sin este dato no sabrían qué
    catálogo mirar.
    """
    try:
        fields = DeclaranteFields(
            declarante_id=declarante_id, nombre_declarante=nombre, nrc_declarante=nrc,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    return {
        "id":              fields.declarante_id,
        "nit":             nit or fields.declarante_id,
        "nombre":          fields.nombre_declarante,
        "dui":             dui,
        "nrc":             fields.nrc_declarante,
        "organizacion_id": organizacion_id,
    }


def _handle_extractor_result(result: dict, tipo: str, filename: str, declarante_id: str) -> dict:
    """Normaliza la respuesta del extractor al formato de la API."""
    if "error_fatal" in result:
        raise HTTPException(status_code=422, detail=result["error_fatal"])
    if "error_tipo" in result:
        raise HTTPException(status_code=422, detail=result["error_tipo"])
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    if "error_extraccion" in result:
        # Excepción inesperada dentro del extractor. Sin esta comprobación el
        # registro seguía adelante sin ningún campo y aparecía como una fila en
        # blanco contada entre los documentos procesados, con el riesgo de
        # llegar así al anexo exportado.
        raise HTTPException(
            status_code=422,
            detail=f"No se pudo extraer el documento: {result['error_extraccion']}",
        )

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
    file: UploadFile = File(..., description="PDF o JSON firmado por Hacienda del DTE de ventas"),
    declarante_id: str = Form(..., description="ID del declarante (NIT sin guiones)"),
    nombre_declarante: str = Form("", description="Nombre/razón social del declarante"),
    nrc_declarante: str = Form("", description="NRC del declarante"),
    org: dict = Depends(get_current_org),
):
    """
    Extrae los datos de un DTE de ventas.
    Si se sube el JSON oficial firmado por Hacienda, se parsea contra el schema
    (sin regex/IA, confianza=100). Si se sube PDF, sigue el pipeline regex+IA.
    Devuelve un registro con estructura del Anexo 1 (contribuyentes) o Anexo 2 (consumidor final).
    """
    content, ext = _read_upload_bytes(file, permitir_json=True)
    if ext == "json":
        result = procesar_json_nativo_ventas(content)
    else:
        cliente = _build_cliente_activo(declarante_id, org["organizacion_id"],
                                        nombre=nombre_declarante, nrc=nrc_declarante)
        result = extraer_venta_nativo_pro(content, cliente)
    return _handle_extractor_result(result, "ventas", file.filename, declarante_id)


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------

@router.post("/compras")
async def procesar_compras(
    file: UploadFile = File(..., description="PDF o JSON firmado por Hacienda del DTE de compras"),
    declarante_id: str = Form(..., description="ID del declarante (NIT sin guiones)"),
    nombre_declarante: str = Form("", description="Nombre/razón social del declarante"),
    nrc_declarante: str = Form("", description="NRC del declarante"),
    org: dict = Depends(get_current_org),
):
    """
    Extrae los datos de un DTE de compras (incluye DTE-14 sujeto excluido vía JSON).
    Si se sube el JSON oficial firmado por Hacienda, se parsea contra el schema
    (sin regex/IA, confianza=100). Si se sube PDF, sigue el pipeline regex+IA.
    Devuelve un registro con estructura del Anexo 3 DGII.
    """
    content, ext = _read_upload_bytes(file, permitir_json=True)
    if ext == "json":
        result = procesar_json_nativo_compras(content)
    else:
        cliente = _build_cliente_activo(declarante_id, org["organizacion_id"],
                                        nombre=nombre_declarante, nrc=nrc_declarante)
        result = extraer_compra_nativo_pro(content, cliente)
    return _handle_extractor_result(result, "compras", file.filename, declarante_id)


# ---------------------------------------------------------------------------
# Retenciones
# ---------------------------------------------------------------------------

@router.post("/retenciones")
async def procesar_retenciones(
    file: UploadFile = File(..., description="PDF del DTE de retenciones"),
    declarante_id: str = Form(..., description="ID del declarante (NIT sin guiones)"),
    nombre_declarante: str = Form("", description="Nombre/razón social del declarante"),
    org: dict = Depends(get_current_org),
):
    """
    Extrae los datos de un DTE de retenciones (Comprobante de Retención DTE-07,
    o su corrección vía Nota de Crédito DTE-05 / Nota de Débito DTE-06 —
    casilla 162 / IVA 1%). Devuelve un registro con estructura del Anexo 7 DGII.
    """
    content, _ext = _read_upload_bytes(file, permitir_json=False)
    cliente = _build_cliente_activo(declarante_id, org["organizacion_id"], nombre=nombre_declarante)
    result = extraer_retencion_nativa(content, cliente)
    return _handle_extractor_result(result, "retenciones", file.filename, declarante_id)


# ---------------------------------------------------------------------------
# Sujetos Excluidos
# ---------------------------------------------------------------------------

@router.post("/sujetos-excluidos")
async def procesar_sujetos_excluidos(
    file: UploadFile = File(..., description="PDF del DTE de sujetos excluidos"),
    declarante_id: str = Form(..., description="ID del declarante (NIT sin guiones)"),
    nombre_declarante: str = Form("", description="Nombre/razón social del declarante"),
    org: dict = Depends(get_current_org),
):
    """
    Extrae los datos de un DTE de sujetos excluidos (DTE-14, casilla 66 / retención renta 10%).
    Devuelve un registro con estructura del Anexo 5 DGII.
    """
    content, _ext = _read_upload_bytes(file, permitir_json=False)
    cliente = _build_cliente_activo(declarante_id, org["organizacion_id"], nombre=nombre_declarante)
    result = extraer_sujetos_nativo(content, cliente)
    return _handle_extractor_result(result, "sujetos_excluidos", file.filename, declarante_id)


# ---------------------------------------------------------------------------
# Lote (multi-PDF/JSON)
# ---------------------------------------------------------------------------

def _procesar_uno_bytes(
    filename: str, content: bytes, ext: str, extractor_fn, json_fn, tipo: str,
    cliente: dict, declarante_id: str,
) -> tuple[bool, dict]:
    """Corre en threadpool — bloqueante (regex, pdfplumber, requests a Groq/
    Hacienda), a propósito fuera del event loop."""
    try:
        if ext == "json" and json_fn is not None:
            result = json_fn(content)
        else:
            result = extractor_fn(content, cliente)
        return True, _handle_extractor_result(result, tipo, filename, declarante_id)
    except HTTPException as e:
        return False, {"filename": filename, "error": e.detail}
    except Exception as e:
        return False, {"filename": filename, "error": str(e)}


async def _ejecutar_lote_job(
    job_id: str, archivos: list[tuple[str, bytes, str]], extractor_fn, json_fn,
    tipo: str, cliente: dict, declarante_id: str,
) -> None:
    """
    Tarea de background (FastAPI BackgroundTasks) — corre DESPUÉS de que la
    request ya respondió con el job_id, así que nada de esto puede generar
    un "Network Error": no hay ninguna conexión HTTP abierta esperándolo.

    Cada archivo corre en threadpool en paralelo (igual que antes), pero acá
    el progreso se va guardando en el job a medida que cada uno termina, en
    vez de esperar a que termine todo el lote para recién ahí devolver algo.
    """
    async def _uno(filename: str, content: bytes, ext: str) -> None:
        ok, r = await run_in_threadpool(
            _procesar_uno_bytes, filename, content, ext, extractor_fn, json_fn,
            tipo, cliente, declarante_id,
        )
        snapshot = jobs_store.actualizar_progreso(job_id, resultado=r if ok else None, error=None if ok else r)
        if snapshot is not None:
            await run_in_threadpool(jobs_store.guardar_snapshot, snapshot)

    try:
        await asyncio.gather(*(_uno(fn, c, e) for fn, c, e in archivos))
    finally:
        snapshot = jobs_store.finalizar_job(job_id)
        if snapshot is not None:
            await run_in_threadpool(jobs_store.guardar_snapshot, snapshot)


async def _iniciar_lote_job(
    background_tasks: BackgroundTasks, files: List[UploadFile], extractor_fn, tipo: str,
    declarante_id: str, organizacion_id: str, nombre_declarante: str = "",
    nrc_declarante: str = "", permitir_json: bool = False, json_fn=None,
) -> dict:
    if len(files) > _MAX_LOTE_ARCHIVOS:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {_MAX_LOTE_ARCHIVOS} archivos por lote (subiste {len(files)}).",
        )

    cliente = _build_cliente_activo(declarante_id, organizacion_id,
                                    nombre=nombre_declarante, nrc=nrc_declarante)

    # Los archivos se leen ACÁ, todavía con la conexión abierta — un UploadFile
    # deja de ser válido apenas la request termina, así que hay que sacarle
    # los bytes antes de agendar el trabajo de background.
    archivos: list[tuple[str, bytes, str]] = []
    for f in files:
        content, ext = _read_upload_bytes(f, permitir_json=permitir_json)
        archivos.append((f.filename, content, ext))

    job = jobs_store.crear_job(len(archivos), organizacion_id)
    job_id = job["job_id"]
    # Se respalda ACÁ (con la conexión todavía abierta) para que el job ya
    # exista en Supabase antes de responder — si el contenedor se reinicia
    # apenas después de crear el job (p. ej. un redeploy que arranca justo
    # en este instante), el primer polling del frontend igual lo encuentra.
    await run_in_threadpool(jobs_store.guardar_snapshot, job)
    background_tasks.add_task(
        _ejecutar_lote_job, job_id, archivos, extractor_fn, json_fn, tipo, cliente, declarante_id,
    )
    return {"job_id": job_id, "total": len(archivos)}


@router.post("/ventas/lote")
async def procesar_ventas_lote(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    declarante_id: str = Form(...),
    nombre_declarante: str = Form(""),
    nrc_declarante: str = Form(""),
    org: dict = Depends(get_current_org),
):
    return await _iniciar_lote_job(background_tasks, files, extraer_venta_nativo_pro, "ventas",
                         declarante_id, org["organizacion_id"], nombre_declarante, nrc_declarante,
                         permitir_json=True, json_fn=procesar_json_nativo_ventas)


@router.post("/compras/lote")
async def procesar_compras_lote(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    declarante_id: str = Form(...),
    nombre_declarante: str = Form(""),
    nrc_declarante: str = Form(""),
    org: dict = Depends(get_current_org),
):
    return await _iniciar_lote_job(background_tasks, files, extraer_compra_nativo_pro, "compras",
                         declarante_id, org["organizacion_id"], nombre_declarante, nrc_declarante,
                         permitir_json=True, json_fn=procesar_json_nativo_compras)


@router.post("/retenciones/lote")
async def procesar_retenciones_lote(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    declarante_id: str = Form(...),
    nombre_declarante: str = Form(""),
    org: dict = Depends(get_current_org),
):
    return await _iniciar_lote_job(background_tasks, files, extraer_retencion_nativa, "retenciones",
                         declarante_id, org["organizacion_id"], nombre_declarante)


@router.post("/sujetos-excluidos/lote")
async def procesar_sujetos_excluidos_lote(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    declarante_id: str = Form(...),
    nombre_declarante: str = Form(""),
    org: dict = Depends(get_current_org),
):
    return await _iniciar_lote_job(background_tasks, files, extraer_sujetos_nativo, "sujetos_excluidos",
                         declarante_id, org["organizacion_id"], nombre_declarante)


@router.get("/lote/jobs/{job_id}")
async def obtener_estado_lote(job_id: str, org: dict = Depends(get_current_org)):
    """
    Progreso/resultado de un lote en background. El frontend hace polling acá
    cada pocos segundos hasta que `status` sea "done" (o "error").

    El job solo se devuelve a la organización que lo creó: contiene los datos
    fiscales completos de los DTE extraídos, y estar autenticado no alcanza
    para leer el lote de otro tenant.
    """
    organizacion_id = org["organizacion_id"]
    job = jobs_store.obtener_job(job_id, organizacion_id)
    if not job:
        # No está en memoria — puede ser que el contenedor se haya
        # reiniciado (redeploy) mientras el job corría. Antes de darlo por
        # perdido, se intenta recuperar del respaldo en Supabase.
        job = await run_in_threadpool(jobs_store.cargar_de_supabase, job_id, organizacion_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado o expirado")
    return job


# ---------------------------------------------------------------------------
# Declarantes
# ---------------------------------------------------------------------------

@router.get("/declarantes")
async def listar_declarantes(org: dict = Depends(get_current_org)):
    """Lista los declarantes (clientes activos) de la organización del usuario."""
    try:
        from utils.local_db import cargar_clientes_db
        clientes = await run_in_threadpool(cargar_clientes_db, org["organizacion_id"])
        return {"declarantes": clientes, "total": len(clientes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
