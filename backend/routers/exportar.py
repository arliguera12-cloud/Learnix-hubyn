"""
Endpoints de exportación de datos a Excel / CSV.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/excel")
async def exportar_excel(
    tipo: str = Query(..., description="Tipo de DTE: ventas | compras | retenciones | sujetos_excluidos"),
    declarante_id: str = Query(..., description="ID del declarante"),
    periodo: str = Query(None, description="Período fiscal YYYY-MM (opcional)"),
):
    """
    Exporta los registros del tipo y declarante indicados a un archivo Excel (.xlsx).
    Devuelve el archivo como descarga directa.
    """
    tipos_validos = {"ventas", "compras", "retenciones", "sujetos_excluidos"}
    if tipo not in tipos_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido. Debe ser uno de: {', '.join(tipos_validos)}",
        )

    # TODO: obtener registros de Supabase y generar Excel con export_utils
    raise HTTPException(status_code=501, detail="Exportación pendiente de implementación")
