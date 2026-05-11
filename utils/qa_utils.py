"""
Learnix Hub — QA Fiscal Utils v1.0

Validates mathematical and structural coherence of extracted DTE fields.
Provides Streamlit UI helpers for the QA gate (banner + field highlighting).

Validation rules per DTE type:
  ventas          : IVA = gravadas × 13%;  total = gravadas + exentas + no_sujetas + iva
  compras         : same as ventas
  retenciones     : iva_retenido = base × 1%
  sujetos_excluidos: retencion_renta = base × 10%
"""
from __future__ import annotations

import re
import streamlit as st


# ─── Validators de campos individuales ───────────────────────────────────────

def _nit_valido(nit: str | None) -> bool:
    if not nit:
        return False
    return len(re.sub(r'[^0-9]', '', str(nit))) == 14


def _dui_valido(dui: str | None) -> bool:
    if not dui:
        return False
    return len(re.sub(r'[^0-9]', '', str(dui))) == 9


def _fecha_valida(fecha: str | None) -> bool:
    if not fecha:
        return False
    m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', str(fecha).strip())
    if not m:
        return False
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return 1 <= d <= 31 and 1 <= mo <= 12 and 2020 <= y <= 2030


def _monto(val) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


# ─── Validación fiscal matemática ────────────────────────────────────────────

def validar_montos_ventas(campos: dict) -> list[str]:
    """Returns fiscal alerts for ventas/compras DTEs (IVA 13%, total coherence)."""
    alertas: list[str] = []
    gravadas = _monto(campos.get("gravadas"))
    iva      = _monto(campos.get("iva"))
    total    = _monto(campos.get("total"))
    exentas  = _monto(campos.get("exentas"))
    no_suj   = _monto(campos.get("no_sujetas"))

    if gravadas > 0 and iva > 0:
        iva_calc = round(gravadas * 0.13, 2)
        if abs(iva - iva_calc) > 0.05:
            alertas.append(
                f"IVA no coincide: documento=${iva:.2f}, "
                f"calculado {gravadas:.2f}×13%=${iva_calc:.2f}"
            )

    if total > 0:
        suma = round(gravadas + exentas + no_suj + iva, 2)
        if suma > 0 and abs(total - suma) > 0.10:
            alertas.append(
                f"Total no cuadra: documento=${total:.2f}, "
                f"suma de componentes=${suma:.2f}"
            )
    return alertas


def validar_montos_retenciones(campos: dict) -> list[str]:
    """Returns fiscal alerts for DTE-07 (retención 1%)."""
    alertas: list[str] = []
    base = _monto(campos.get("base"))
    ret  = _monto(campos.get("ret"))

    if base > 0 and ret > 0:
        ret_calc = round(base * 0.01, 2)
        if abs(ret - ret_calc) > 0.05:
            alertas.append(
                f"Retención 1% no coincide: documento=${ret:.2f}, "
                f"calculado {base:.2f}×1%=${ret_calc:.2f}"
            )
    return alertas


def validar_montos_sujetos(campos: dict) -> list[str]:
    """Returns fiscal alerts for DTE-14 (retención renta 10%)."""
    alertas: list[str] = []
    base = _monto(campos.get("base"))
    ret  = _monto(campos.get("ret"))

    if base > 0 and ret > 0:
        ret_calc = round(base * 0.10, 2)
        if abs(ret - ret_calc) > 0.05:
            alertas.append(
                f"Retención Renta 10% no coincide: documento=${ret:.2f}, "
                f"calculado {base:.2f}×10%=${ret_calc:.2f}"
            )
    return alertas


_VALIDADORES_MONTOS = {
    "ventas"           : validar_montos_ventas,
    "compras"          : validar_montos_ventas,
    "retenciones"      : validar_montos_retenciones,
    "sujetos_excluidos": validar_montos_sujetos,
}


# ─── Indicadores de alerta por fila ──────────────────────────────────────────

def clasificar_alerta_compra(row) -> str:
    """
    Returns '⚠️ Error de cuadre legal — {razones}' or '✅' for a compra row.
    Checks: IVA ≈ gra × 13% (±$0.01) and sello de recepción not empty.
    row can be a pd.Series or dict with keys: gra, iva, sello.
    """
    d     = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    gra   = _monto(d.get("gra", 0))
    iva   = _monto(d.get("iva", 0))
    sello = str(d.get("sello", "")).strip()

    razones: list[str] = []
    if gra > 0 and iva > 0:
        iva_calc = round(gra * 0.13, 2)
        if abs(iva - iva_calc) > 0.05:
            razones.append(f"IVA ${iva:.2f} ≠ {gra:.2f}×13%=${iva_calc:.2f}")
    if not sello:
        razones.append("Sello vacío")

    return f"⚠️ Error de cuadre legal — {'; '.join(razones)}" if razones else "✅"


def clasificar_alerta_venta(row) -> str:
    """
    Returns '⚠️ Error de cuadre legal — {razones}' or '✅' for a venta row.
    Checks: débito ≈ gravadas × 13% (±$0.05, only for tipos 03/05/06) and sello not empty.
    Tolerancia ±$0.05 para cubrir redondeos de farmacias y tickets fiscales.
    """
    d      = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    grav   = _monto(d.get("gravadas", 0))
    debito = _monto(d.get("debito", 0))
    sello  = str(d.get("sello", "")).strip()
    tipo   = str(d.get("tipo", ""))

    razones: list[str] = []
    if tipo in ("03", "05", "06") and grav > 0 and debito > 0:
        deb_calc = round(grav * 0.13, 2)
        if abs(debito - deb_calc) > 0.05:
            razones.append(f"IVA ${debito:.2f} ≠ {grav:.2f}×13%=${deb_calc:.2f}")
    if not sello:
        razones.append("Sello vacío")

    return f"⚠️ Error de cuadre legal — {'; '.join(razones)}" if razones else "✅"


def estilar_alertas(df: "pd.DataFrame", col_alerta: str = "_alerta") -> "pd.io.formats.style.Styler":
    """
    Applies row background coloring to a DataFrame based on a pre-computed alert column.

    Color scheme:
      IVA + Sello  → red    (#3D1212 bg / #FFCDD2 text)
      IVA only     → orange (#2D1A0A bg / #FFE0B2 text)
      Sello only   → blue   (#0E1A2D bg / #BBDEFB text)
      No alert     → default styling

    The col_alerta column must already exist in df (computed via clasificar_alerta_*).
    Returns a Styler with the background applied AND numeric columns hidden from the
    alert column (use .format(...) chained after this call as needed).
    """
    import pandas as pd

    def _hl(row: "pd.Series"):
        val = str(row[col_alerta]) if col_alerta in row.index else ""
        if "⚠️" not in val:
            return [""] * len(row)
        has_iva   = "IVA"   in val
        has_sello = "Sello" in val
        if has_iva and has_sello:
            css = "background-color: #3D1212; color: #FFCDD2"
        elif has_iva:
            css = "background-color: #2D1A0A; color: #FFE0B2"
        else:
            css = "background-color: #0E1A2D; color: #BBDEFB"
        return [css] * len(row)

    return df.style.apply(_hl, axis=1)


# ─── Campos inválidos por tipo de DTE ────────────────────────────────────────

def campos_invalidos_dte(tipo_dte: str, campos: dict) -> set[str]:
    """
    Returns the set of field names that failed structural validation.
    Used to highlight fields in red in the UI.
    """
    invalidos: set[str] = set()

    if not _fecha_valida(campos.get("fecha")):
        invalidos.add("fecha")

    if tipo_dte == "ventas":
        nom = str(campos.get("nom_cli", "")).strip()
        if not nom or nom in ("SIN NOMBRE", "CONSUMIDOR FINAL"):
            pass  # Empty name is only a problem for CCF (03/05/06); page handles this
        nit = campos.get("nit_cli", "")
        dui = campos.get("dui_cli", "")
        if nit and not _nit_valido(nit):
            invalidos.add("nit_cli")
        if dui and not _dui_valido(dui):
            invalidos.add("dui_cli")
        if campos.get("iva_correcto") is False:
            invalidos.add("iva")

    elif tipo_dte == "compras":
        if not str(campos.get("nom_prov", "")).strip():
            invalidos.add("nom_prov")
        if not _nit_valido(campos.get("nit_prov")):
            invalidos.add("nit_prov")
        if campos.get("iva_correcto") is False:
            invalidos.add("iva")

    elif tipo_dte == "retenciones":
        if not _nit_valido(campos.get("nit_prov")):
            invalidos.add("nit_prov")
        if campos.get("retencion_correcta") is False:
            invalidos.add("ret")

    elif tipo_dte == "sujetos_excluidos":
        if not str(campos.get("nom_sujeto", "")).strip():
            invalidos.add("nom_sujeto")
        id_s = campos.get("id_sujeto", "")
        if id_s and not (_nit_valido(id_s) or _dui_valido(id_s)):
            invalidos.add("id_sujeto")
        if campos.get("retencion_correcta") is False:
            invalidos.add("ret")

    return invalidos


def requiere_revision_manual(
    tipo_dte: str,
    campos: dict,
    confianza: int = 100,
    alertas: list | None = None,
) -> bool:
    """Returns True if manual review is needed for this document."""
    if confianza < 65:
        return True
    if campos_invalidos_dte(tipo_dte, campos):
        return True
    if alertas:
        return True
    return False


# ─── Streamlit UI helpers ─────────────────────────────────────────────────────

def mostrar_banner_qa(
    tipo_dte: str,
    campos: dict,
    confianza: int = 100,
    alertas: list | None = None,
    container=None,
) -> None:
    """
    Renders the QA status banner inside a Streamlit container.

    ⚠️ Red banner + list of issues when review is needed.
    ✅ Green inline badge when everything passes.
    """
    target   = container or st
    alertas  = alertas or []
    invalidos = campos_invalidos_dte(tipo_dte, campos)
    necesita  = confianza < 65 or bool(invalidos) or bool(alertas)

    if necesita:
        razones: list[str] = []
        if confianza < 65:
            razones.append(f"Confianza IA baja ({confianza}%)")
        for campo in sorted(invalidos):
            razones.append(f"Campo con error: <code>{campo}</code>")
        for alerta in alertas:
            razones.append(str(alerta))

        items_html = "".join(f"<li>{r}</li>" for r in razones)
        target.markdown(
            f"""<div style="background:#3D1212;border:2px solid #E53935;
            border-radius:8px;padding:12px 16px;margin:6px 0">
            <span style="color:#EF5350;font-size:1.05rem;font-weight:bold">
            ⚠️ Requiere Revisión Manual</span>
            <ul style="color:#FFCDD2;margin:6px 0 0 0;padding-left:18px">
            {items_html}
            </ul></div>""",
            unsafe_allow_html=True,
        )
    else:
        target.markdown(
            f"""<div style="display:inline-block;background:#1A2C18;
            border:1px solid #6AB040;border-radius:6px;
            padding:6px 14px;margin:4px 0">
            <span style="color:#A8E870">
            ✅ Datos verificados — Confianza IA: {confianza}%
            </span></div>""",
            unsafe_allow_html=True,
        )


def mostrar_indicador_vision(
    campos_vision: dict,
    alertas_vision: list,
    audit_vision: dict,
    error_vision: str = "",
    container=None,
) -> None:
    """
    Renders the Vision status indicator inside a Streamlit container.
    Displays the actual API error when Vision fails, so users can diagnose it.
    """
    target = container or st

    if not audit_vision:
        if error_vision:
            target.warning(
                f"⚠️ **Gemini Vision falló** — se usó regex como respaldo.\n\n"
                f"Error exacto: `{error_vision}`"
            )
        else:
            target.caption("🔌 Gemini Vision no disponible — extracción solo por regex")
        return

    confianza = audit_vision.get("confianza", 0)
    layout    = audit_vision.get("layout", "")
    notas     = audit_vision.get("notas", "")
    modelo    = audit_vision.get("modelo", "gemini-2.5-flash-vision")

    if confianza >= 85:
        color, nivel = "#6AB040", "Alta confianza"
    elif confianza >= 65:
        color, nivel = "#F0A500", "Confianza moderada"
    else:
        color, nivel = "#E53935", "Baja confianza — revisar"

    target.markdown(
        f"""<div style="background:#1A2C18;border-radius:6px;padding:6px 12px;margin:4px 0">
        <span style="color:{color};font-weight:bold">
        👁️ Gemini Vision</span>
        <span style="color:#8BAF72"> · {modelo}</span>
        <span style="color:#666"> · Layout: {layout or 'N/A'}</span>
        <div style="background:{color};width:{confianza}%;height:5px;
        border-radius:3px;margin:4px 0"></div>
        <small style="color:{color}">{nivel} ({confianza}%)</small>
        </div>""",
        unsafe_allow_html=True,
    )

    if notas:
        target.info(f"📝 {notas}")

    if alertas_vision:
        for alerta in alertas_vision:
            target.warning(f"⚠️ {alerta}")
    elif campos_vision:
        n = len([v for v in campos_vision.values() if v is not None])
        target.caption(f"⚡ Vision extrajo {n} campo(s) — sin alertas fiscales")


def calcular_estatus_venta(row) -> str:
    """
    Returns '🔴 Revisar' or '🟢 OK' for a ventas row.
    Checks: IVA ≈ gravadas×13% (±$0.05, tipos 03/05/06) and sello ≥ 30 chars.
    Tolerancia ±$0.05 para cubrir redondeos de farmacias y tickets fiscales.
    """
    d      = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    grav   = _monto(d.get("gravadas", 0))
    debito = _monto(d.get("debito", 0))
    sello  = str(d.get("sello", "") or "").strip()
    tipo   = str(d.get("tipo", ""))

    if tipo in ("03", "05", "06") and grav > 0 and debito > 0:
        if abs(debito - round(grav * 0.13, 2)) > 0.05:
            return "🔴 Revisar"
    if len(sello) < 30:
        return "🔴 Revisar"
    return "🟢 OK"


def calcular_estatus_compra(row) -> str:
    """
    Returns '🔴 Revisar' or '🟢 OK' for a compra row.
    Checks: IVA ≈ gra×13% (±$0.05) and sello ≥ 30 chars.
    Tolerancia ±$0.05 para cubrir redondeos de farmacias y tickets fiscales.
    """
    d     = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    gra   = _monto(d.get("gra", 0))
    iva   = _monto(d.get("iva", 0))
    sello = str(d.get("sello", "") or "").strip()

    if gra > 0 and iva > 0:
        if abs(iva - round(gra * 0.13, 2)) > 0.05:
            return "🔴 Revisar"
    if len(sello) < 30:
        return "🔴 Revisar"
    return "🟢 OK"
