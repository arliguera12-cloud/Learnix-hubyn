"""
Exportación al formato exacto F-07 — Ministerio de Hacienda El Salvador.
POST /exportar/excel → .xlsx con columnas exactas de cada Anexo.
Sin filas de título, sin metadata, primera fila = nombres de columnas.
"""
import io
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

_TIPOS_VALIDOS = {"ventas", "compras", "retenciones", "sujetos_excluidos"}

# Tipos DTE → Anexo al que pertenecen
_TIPOS_CONTRIBUYENTES = {"03", "05", "06"}
_TIPOS_CONSUMIDOR     = {"01", "02", "10", "11"}


# ─── Utilidades ────────────────────────────────────────────────────────────

def _fmt(v, decimals: int = 2) -> str:
    """Número como texto con punto decimal, sin separador de miles."""
    try:
        return f"{float(v or 0):.{decimals}f}"
    except (TypeError, ValueError):
        return "0.00"


def _clean(s) -> str:
    return re.sub(r"[-]", "", str(s or ""))


# ─── Anexo 1: Ventas a Contribuyentes (A-T, 20 cols) ──────────────────────

COLS_ANX1 = [
    "fecha_emision", "clase_documento", "tipo_documento",
    "numero_resolucion", "serie_documento", "numero_documento",
    "numero_control_interno",
    "nit_o_nrc_cliente", "nombre_razon_social",
    "ventas_exentas", "ventas_no_sujetas", "ventas_gravadas_locales",
    "debito_fiscal",
    "ventas_cuenta_terceros_no_domiciliados", "debito_fiscal_cuenta_terceros",
    "total_ventas",
    "dui_cliente", "tipo_operacion_renta", "tipo_ingreso_renta",
    "numero_anexo",
]

def _row_anx1(r: dict) -> dict:
    return {
        "fecha_emision":                         str(r.get("fecha") or ""),
        "clase_documento":                       "4",
        "tipo_documento":                        str(r.get("tipo") or ""),
        "numero_resolucion":                     _clean(r.get("num_control") or ""),
        "serie_documento":                       str(r.get("sello") or ""),
        "numero_documento":                      _clean(r.get("gen_sin_guiones") or r.get("gen") or ""),
        "numero_control_interno":                "",
        "nit_o_nrc_cliente":                     str(r.get("nit_cli") or ""),
        "nombre_razon_social":                   str(r.get("nom_cli") or ""),
        "ventas_exentas":                        _fmt(r.get("exentas")),
        "ventas_no_sujetas":                     _fmt(r.get("no_sujetas")),
        "ventas_gravadas_locales":               _fmt(r.get("gravadas")),
        "debito_fiscal":                         _fmt(r.get("debito")),
        "ventas_cuenta_terceros_no_domiciliados": _fmt(r.get("terceros")),
        "debito_fiscal_cuenta_terceros":         _fmt(r.get("deb_terc")),
        "total_ventas":                          _fmt(r.get("total")),
        "dui_cliente":                           str(r.get("dui_cli") or ""),
        "tipo_operacion_renta":                  str(r.get("tipo_operacion_renta") or "0"),
        "tipo_ingreso_renta":                    str(r.get("tipo_ingreso_renta") or "0"),
        "numero_anexo":                          "1",
    }


# ─── Anexo 2: Ventas a Consumidor Final (A-W, 23 cols) ────────────────────

COLS_ANX2 = [
    "fecha_emision", "clase_documento", "tipo_documento",
    "numero_resolucion", "serie_documento",
    "numero_control_interno_del", "numero_control_interno_al",
    "numero_documento_del", "numero_documento_al",
    "numero_maquina_registradora",
    "ventas_exentas", "ventas_internas_exentas_no_proporcionalidad",
    "ventas_no_sujetas", "ventas_gravadas_locales",
    "exportaciones_dentro_centroamerica", "exportaciones_fuera_centroamerica",
    "exportaciones_servicios", "ventas_zonas_francas_dpa",
    "ventas_cuenta_terceros_no_domiciliados",
    "total_ventas",
    "tipo_operacion_renta", "tipo_ingreso_renta",
    "numero_anexo",
]

def _row_anx2(r: dict) -> dict:
    tipo   = str(r.get("tipo") or "")
    gen_sg = _clean(r.get("gen_sin_guiones") or r.get("gen") or "")
    return {
        "fecha_emision":                         str(r.get("fecha") or ""),
        "clase_documento":                       "4",
        "tipo_documento":                        tipo,
        "numero_resolucion":                     "N/A",
        "serie_documento":                       "N/A",
        "numero_control_interno_del":            "N/A",
        "numero_control_interno_al":             "N/A",
        "numero_documento_del":                  gen_sg,
        "numero_documento_al":                   gen_sg,
        "numero_maquina_registradora":           str(r.get("num_maq") or "") if tipo == "10" else "",
        "ventas_exentas":                        _fmt(r.get("exentas")),
        "ventas_internas_exentas_no_proporcionalidad": "0.00",
        "ventas_no_sujetas":                     _fmt(r.get("no_sujetas")),
        "ventas_gravadas_locales":               _fmt(r.get("gravadas")),
        "exportaciones_dentro_centroamerica":    "0.00",
        "exportaciones_fuera_centroamerica":     "0.00",
        "exportaciones_servicios":               "0.00",
        "ventas_zonas_francas_dpa":              "0.00",
        "ventas_cuenta_terceros_no_domiciliados": _fmt(r.get("terceros")),
        "total_ventas":                          _fmt(r.get("total")),
        "tipo_operacion_renta":                  str(r.get("tipo_operacion_renta") or "0"),
        "tipo_ingreso_renta":                    str(r.get("tipo_ingreso_renta") or "0"),
        "numero_anexo":                          "2",
    }


# ─── Anexo 3: Compras (A-U, 21 cols) ──────────────────────────────────────

COLS_ANX3 = [
    "fecha_emision", "clase_documento", "tipo_documento", "numero_documento",
    "nit_o_nrc_proveedor", "nombre_proveedor",
    "compras_internas_exentas_no_sujetas",
    "internaciones_exentas_no_sujetas",
    "importaciones_exentas_no_sujetas",
    "compras_internas_gravadas",
    "internaciones_gravadas_bienes",
    "importaciones_gravadas_bienes",
    "importaciones_gravadas_servicios",
    "credito_fiscal", "total_compras",
    "dui_proveedor",
    "tipo_operacion", "clasificacion", "sector", "tipo_costo_gasto",
    "numero_anexo",
]

def _row_anx3(r: dict) -> dict:
    exe = float(r.get("exe") or 0)
    gra = float(r.get("gra") or 0)
    iva = float(r.get("iva") or 0)
    tot = float(r.get("tot") or 0) or (exe + gra)
    return {
        "fecha_emision":                          str(r.get("fecha") or ""),
        "clase_documento":                        "4",
        "tipo_documento":                         str(r.get("tipo") or ""),
        "numero_documento":                       _clean(r.get("gen_sin_guiones") or r.get("gen") or ""),
        "nit_o_nrc_proveedor":                    str(r.get("nit_prov") or ""),
        "nombre_proveedor":                       str(r.get("nom_prov") or ""),
        "compras_internas_exentas_no_sujetas":    _fmt(exe),
        "internaciones_exentas_no_sujetas":       "0.00",
        "importaciones_exentas_no_sujetas":       "0.00",
        "compras_internas_gravadas":              _fmt(gra),
        "internaciones_gravadas_bienes":          "0.00",
        "importaciones_gravadas_bienes":          "0.00",
        "importaciones_gravadas_servicios":       "0.00",
        "credito_fiscal":                         _fmt(iva),
        "total_compras":                          _fmt(tot),
        "dui_proveedor":                          str(r.get("dui_prov") or ""),
        "tipo_operacion":                         str(r.get("tipo_operacion") or "0"),
        "clasificacion":                          str(r.get("clasificacion") or "0"),
        "sector":                                 str(r.get("sector") or "0"),
        "tipo_costo_gasto":                       str(r.get("tipo_costo_gasto") or "0"),
        "numero_anexo":                           "3",
    }


# ─── Anexo 5: Sujetos Excluidos (A-M, 13 cols) ────────────────────────────

COLS_ANX5 = [
    "tipo_documento_identidad", "numero_identificacion",
    "nombre_sujeto_excluido", "fecha_emision",
    "serie_documento", "numero_documento",
    "monto_operacion", "monto_retencion_iva_13pct",
    "tipo_operacion", "clasificacion", "sector", "tipo_costo_gasto",
    "numero_anexo",
]

def _row_anx5(r: dict) -> dict:
    id_raw   = str(r.get("id_sujeto") or "")
    id_clean = re.sub(r"[-\s]", "", id_raw)
    if len(id_clean) == 14 and id_clean.isdigit():
        tipo_id = "1"
    elif len(id_clean) == 9 and id_clean.isdigit():
        tipo_id = "2"
    else:
        tipo_id = "3"
    gen_sg = _clean(r.get("gen") or r.get("num_control") or "")
    return {
        "tipo_documento_identidad":  tipo_id,
        "numero_identificacion":     id_clean,
        "nombre_sujeto_excluido":    str(r.get("nom_sujeto") or ""),
        "fecha_emision":             str(r.get("fecha") or ""),
        "serie_documento":           str(r.get("sello") or ""),
        "numero_documento":          gen_sg,
        "monto_operacion":           _fmt(r.get("base")),
        "monto_retencion_iva_13pct": _fmt(r.get("ret")),
        "tipo_operacion":            str(r.get("tipo_operacion") or "0"),
        "clasificacion":             str(r.get("clasificacion") or "0"),
        "sector":                    str(r.get("sector") or "0"),
        "tipo_costo_gasto":          str(r.get("tipo_costo_gasto") or "0"),
        "numero_anexo":              "5",
    }


# ─── Anexo 7: Retenciones (A-I, 9 cols) ────────────────────────────────────

COLS_ANX7 = [
    "nit_agente", "fecha_emision", "tipo_documento",
    "serie_documento", "numero_documento",
    "monto_sujeto", "monto_retencion_1pct",
    "dui_agente", "numero_anexo",
]

def _row_anx7(r: dict) -> dict:
    return {
        "nit_agente":            str(r.get("nit_prov") or ""),
        "fecha_emision":         str(r.get("fecha") or ""),
        "tipo_documento":        str(r.get("tipo") or "07"),
        "serie_documento":       str(r.get("sello") or ""),
        "numero_documento":      _clean(r.get("gen") or ""),
        "monto_sujeto":          _fmt(r.get("base")),
        "monto_retencion_1pct":  _fmt(r.get("ret")),
        "dui_agente":            str(r.get("dui_agente") or ""),
        "numero_anexo":          "7",
    }


# ─── Excel builder ──────────────────────────────────────────────────────────

def _build_xlsx(sheets: dict) -> bytes:
    """
    sheets: {nombre_hoja: (columnas_list, filas_list)}
    Genera xlsx con encabezados como primera fila, sin títulos extras.
    """
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas no instalado")

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for nombre, (cols, filas) in sheets.items():
            df = pd.DataFrame(filas, columns=cols) if filas else pd.DataFrame(columns=cols)
            df.to_excel(writer, index=False, sheet_name=nombre[:31])

            ws = writer.sheets[nombre[:31]]
            # Auto-ancho de columnas
            for col_cells in ws.columns:
                max_len = max(
                    (len(str(c.value)) if c.value is not None else 0)
                    for c in col_cells
                )
                ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 3, 55)

            # Estilo de encabezado (primera fila)
            try:
                from openpyxl.styles import Font, PatternFill
                header_fill = PatternFill("solid", fgColor="1C2333")
                for cell in ws[1]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = header_fill
            except Exception:
                pass  # openpyxl styles opcionales

    return buf.getvalue()


# ─── Request model ──────────────────────────────────────────────────────────

class ExportarRequest(BaseModel):
    tipo: str
    declarante_id: str
    periodo: Optional[str] = None
    registros: List[Dict[str, Any]]


# ─── Endpoint ───────────────────────────────────────────────────────────────

@router.post("/excel")
async def exportar_excel(body: ExportarRequest):
    """
    Genera xlsx F-07 con las columnas exactas del Anexo correspondiente.
    Sin filas de título, sin metadata — primera fila = nombres de columnas.
    """
    if body.tipo not in _TIPOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido. Debe ser uno de: {', '.join(_TIPOS_VALIDOS)}",
        )

    periodo_str = body.periodo or "sin_periodo"
    sheets: dict = {}

    if body.tipo == "ventas":
        anx1 = [_row_anx1(r) for r in body.registros
                if str(r.get("tipo") or "") in _TIPOS_CONTRIBUYENTES]
        anx2 = [_row_anx2(r) for r in body.registros
                if str(r.get("tipo") or "") in _TIPOS_CONSUMIDOR]
        # Registros sin tipo conocido → contribuyentes por defecto
        sin_tipo = [_row_anx1(r) for r in body.registros
                    if str(r.get("tipo") or "") not in _TIPOS_CONTRIBUYENTES | _TIPOS_CONSUMIDOR]
        anx1.extend(sin_tipo)
        sheets["Anexo1_Contribuyentes"] = (COLS_ANX1, anx1)
        sheets["Anexo2_ConsumidorFinal"] = (COLS_ANX2, anx2)

    elif body.tipo == "compras":
        filas = [_row_anx3(r) for r in body.registros]
        sheets["Anexo3_Compras"] = (COLS_ANX3, filas)

    elif body.tipo == "retenciones":
        filas = [_row_anx7(r) for r in body.registros]
        sheets["Anexo7_Retenciones"] = (COLS_ANX7, filas)

    elif body.tipo == "sujetos_excluidos":
        filas = [_row_anx5(r) for r in body.registros]
        sheets["Anexo5_SujetosExcluidos"] = (COLS_ANX5, filas)

    nombre_tipo = {
        "ventas": "Ventas", "compras": "Compras",
        "retenciones": "Retenciones", "sujetos_excluidos": "SujetosExcluidos",
    }[body.tipo]
    filename = f"F07_Anexo_{nombre_tipo}_{body.declarante_id}_{periodo_str}.xlsx"
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    xlsx_bytes = _build_xlsx(sheets)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
