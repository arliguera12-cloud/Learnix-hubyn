"""
Endpoints de exportación de datos a Excel.
Acepta los registros directamente en el cuerpo (POST) para no depender de Supabase.
"""
import io
import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

_TIPOS_VALIDOS = {"ventas", "compras", "retenciones", "sujetos_excluidos"}

_TITULO_TIPO = {
    "ventas":           "Ventas",
    "compras":          "Compras",
    "retenciones":      "Retenciones",
    "sujetos_excluidos": "Sujetos Excluidos",
}


class ExportarRequest(BaseModel):
    tipo: str
    declarante_id: str
    periodo: Optional[str] = None
    registros: List[Dict[str, Any]]


def _build_excel(registros: List[Dict[str, Any]], titulo: str,
                 declarante_id: str, periodo: Optional[str]) -> bytes:
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas no está instalado")

    df = pd.DataFrame(registros) if registros else pd.DataFrame()

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")

        ws = writer.sheets["Datos"]
        for col_cells in ws.columns:
            max_len = max(
                (len(str(c.value)) if c.value is not None else 0) for c in col_cells
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 60)

        meta_rows = [
            ("Campo", "Valor"),
            ("Fecha de exportación", datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
            ("Sistema", "Learnix DTE Hub v2.0"),
            ("Tipo de DTE", titulo),
            ("Declarante ID", declarante_id),
            ("Período", periodo or "—"),
            ("Total registros", len(registros)),
        ]
        pd.DataFrame(meta_rows[1:], columns=meta_rows[0]).to_excel(
            writer, index=False, sheet_name="Metadata"
        )
        ws_meta = writer.sheets["Metadata"]
        ws_meta.column_dimensions["A"].width = 30
        ws_meta.column_dimensions["B"].width = 45

    return buf.getvalue()


@router.post("/excel")
async def exportar_excel(body: ExportarRequest):
    """
    Genera un Excel con los registros recibidos.
    No requiere Supabase — los registros se envían directamente en el body.
    """
    if body.tipo not in _TIPOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido. Debe ser uno de: {', '.join(_TIPOS_VALIDOS)}",
        )

    titulo = _TITULO_TIPO[body.tipo]
    nombre_periodo = body.periodo or "sin_periodo"
    filename = f"DTE_{titulo}_{body.declarante_id}_{nombre_periodo}.xlsx"
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    xlsx_bytes = _build_excel(body.registros, titulo, body.declarante_id, body.periodo)

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
