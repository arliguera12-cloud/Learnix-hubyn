"""
Learnix Hub — QA Fiscal Utils v2.0

Validates mathematical and structural coherence of extracted DTE fields.
Provides Streamlit UI helpers for the QA gate (banner + field highlighting).

v2.0: agrega funciones de auto-corrección (auto_corregir_*) que calculan
y proponen los valores correctos según las fórmulas DGII.

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
    Checks: IVA ≈ gra × 13% (±$0.05) and sello de recepción not empty.
    Tolerancia ±$0.05 para cubrir redondeos de farmacias y tickets fiscales.
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
                f"⚠️ **IA Vision falló** — se usó regex como respaldo.\n\n"
                f"Error exacto: `{error_vision}`"
            )
        else:
            target.caption("🔌 IA Vision no disponible — extracción solo por regex")
        return

    confianza = audit_vision.get("confianza", 0)
    layout    = audit_vision.get("layout", "")
    notas     = audit_vision.get("notas", "")
    modelo    = audit_vision.get("modelo", "ai-vision")

    if confianza >= 85:
        color, nivel = "#6AB040", "Alta confianza"
    elif confianza >= 65:
        color, nivel = "#F0A500", "Confianza moderada"
    else:
        color, nivel = "#E53935", "Baja confianza — revisar"

    target.markdown(
        f"""<div style="background:#1A2C18;border-radius:6px;padding:6px 12px;margin:4px 0">
        <span style="color:{color};font-weight:bold">
        👁️ IA Vision</span>
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
    - DTE-03/05/06: débito ≈ gravadas×13% (±$0.05) y sello ≥ 30 chars
    - DTE-01: solo valida sello
    - DTE-05 (NC): siempre OK si tiene sello (reduce débito, no genera)
    """
    d      = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    grav   = _monto(d.get("gravadas", 0))
    debito = _monto(d.get("debito", 0))
    sello  = str(d.get("sello", "") or "").strip()
    tipo   = str(d.get("tipo", ""))

    if tipo == "03" and grav > 0 and debito > 0:
        if abs(debito - round(grav * 0.13, 2)) > 0.05:
            return "🔴 Revisar"
    if len(sello) < 30:
        return "🔴 Revisar"
    return "🟢 OK"


def calcular_estatus_compra(row) -> str:
    """
    Returns '🔴 Revisar' or '🟢 OK' for a compra row.
    - DTE-03: iva ≈ gra×13% (±$0.05) y sello ≥ 30 chars
    - DTE-05 (NC): reduce crédito — solo valida sello
    - DTE-06 (ND): aumenta crédito — valida IVA 13% y sello
    - DTE-11 (Factura exenta): solo valida sello
    """
    d     = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    gra   = _monto(d.get("gra", 0))
    iva   = _monto(d.get("iva", 0))
    sello = str(d.get("sello", "") or "").strip()
    tipo  = str(d.get("tipo", ""))

    if tipo in ("03", "06") and gra > 0 and iva > 0:
        if abs(iva - round(gra * 0.13, 2)) > 0.05:
            return "🔴 Revisar"
    if len(sello) < 30:
        return "🔴 Revisar"
    return "🟢 OK"


def _parse_fecha_dmy(fecha_str: str):
    """Parsea DD/MM/YYYY → datetime.date. Retorna None en cualquier fallo."""
    import datetime
    try:
        p = str(fecha_str or "").strip().split("/")
        if len(p) == 3:
            d, m, y = int(p[0]), int(p[1]), int(p[2])
            if 1 <= d <= 31 and 1 <= m <= 12 and 2000 <= y <= 2100:
                return datetime.date(y, m, d)
    except (ValueError, TypeError):
        pass
    return None


def validar_periodo_ventas(df) -> str:
    """
    VENTAS — Regla estricta: todos los documentos deben pertenecer al mismo mes/año.
    El F-07 Ventas es mensual; mezclar períodos genera inconsistencias con la declaración.

    Returns: string de alerta si hay más de un mes; '' si todo OK.
    """
    if df is None or (hasattr(df, "empty") and df.empty) or "fecha" not in df.columns:
        return ""
    meses: set = set()
    for f in df["fecha"]:
        parsed = _parse_fecha_dmy(str(f))
        if parsed:
            meses.add(f"{parsed.month:02d}/{parsed.year}")
    if len(meses) > 1:
        meses_s = sorted(meses, key=lambda x: (x.split("/")[1], x.split("/")[0]))
        return (
            f"Los documentos abarcan {len(meses)} meses distintos "
            f"({', '.join(meses_s)}). El F-07 Ventas se presenta por período mensual."
        )
    return ""


def validar_periodo_compras(df) -> str:
    """
    COMPRAS — Art. 65 Ley IVA El Salvador: el crédito fiscal puede reclamarse
    hasta en los 3 meses calendario siguientes al período en que se originó.
    → Ventana permitida: mes de declaración + 3 meses anteriores (4 meses en total).

    Mes de declaración = mes más reciente encontrado en el lote.
    Lanza alerta solo si hay documentos más antiguos a esa ventana o fechas futuras.

    Returns: string de alerta si hay problema; '' si todo está dentro del rango legal.
    """
    import datetime
    if df is None or (hasattr(df, "empty") and df.empty) or "fecha" not in df.columns:
        return ""

    hoy    = datetime.date.today()
    fechas = [_parse_fecha_dmy(str(f)) for f in df["fecha"]]
    fechas = [f for f in fechas if f is not None]
    if not fechas:
        return ""

    max_fecha = max(fechas)

    # Límite inferior: 3 meses antes del mes de declaración
    mes_min   = max_fecha.month - 3
    anio_min  = max_fecha.year
    if mes_min <= 0:
        mes_min  += 12
        anio_min -= 1
    min_permitido = datetime.date(anio_min, mes_min, 1)

    fuera: list[str] = []
    futuras: list[str] = []
    for f in fechas:
        etiqueta = f"{f.month:02d}/{f.year}"
        hoy_mes  = datetime.date(hoy.year, hoy.month, 1)
        if f > hoy_mes:
            futuras.append(etiqueta)
        elif f < min_permitido:
            fuera.append(etiqueta)

    fuera   = sorted(set(fuera),   key=lambda x: (x.split("/")[1], x.split("/")[0]))
    futuras = sorted(set(futuras), key=lambda x: (x.split("/")[1], x.split("/")[0]))

    partes: list[str] = []
    if fuera:
        mes_min_s = f"{min_permitido.month:02d}/{min_permitido.year}"
        mes_max_s = f"{max_fecha.month:02d}/{max_fecha.year}"
        partes.append(
            f"Documentos de {', '.join(fuera)} exceden la ventana legal de 4 meses "
            f"(Art. 65 Ley IVA: se permiten {mes_min_s}–{mes_max_s})."
        )
    if futuras:
        partes.append(f"Fechas futuras inválidas detectadas: {', '.join(futuras)}.")
    return " | ".join(partes)


def razones_revisar_venta(row) -> str:
    """Devuelve string con el/los motivos de 🔴 Revisar, o '' si todo OK."""
    d      = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    grav   = _monto(d.get("gravadas", 0))
    debito = _monto(d.get("debito", 0))
    sello  = str(d.get("sello", "") or "").strip()
    tipo   = str(d.get("tipo", ""))
    razones = []
    if tipo in ("03", "05", "06") and grav > 0 and debito > 0:
        iva_calc = round(grav * 0.13, 2)
        if abs(debito - iva_calc) > 0.05:
            razones.append(f"IVA ${debito:.2f} ≠ {grav:.2f}×13%=${iva_calc:.2f}")
    if len(sello) < 30:
        razones.append(f"Sello vacío o corto ({len(sello)} chars)")
    return " | ".join(razones)


# ─── Auto-corrección fiscal ───────────────────────────────────────────────────

def auto_corregir_iva_ventas(row: dict) -> dict:
    """
    Calcula el IVA correcto (gravadas × 13%) y el total correcto.
    Retorna un dict con los campos corregidos (solo los que cambian).
    Si no hay inconsistencia, retorna {}.
    """
    grav    = _monto(row.get("gravadas"))
    iva_doc = _monto(row.get("debito") or row.get("iva"))
    exe     = _monto(row.get("exentas"))
    no_suj  = _monto(row.get("no_sujetas"))
    tipo    = str(row.get("tipo", ""))

    if tipo not in ("03", "05", "06") or grav <= 0:
        return {}

    iva_correcto = round(grav * 0.13, 2)
    if abs(iva_doc - iva_correcto) <= 0.05:
        return {}

    total_correcto = round(grav + exe + no_suj + iva_correcto, 2)
    return {
        "debito": iva_correcto,
        "iva"   : iva_correcto,
        "total" : total_correcto,
        "_autocorregido_iva": True,
    }


def auto_corregir_iva_compras(row: dict) -> dict:
    """
    Calcula el IVA correcto (gra × 13%) para una fila de compras.
    Retorna {} si no hay inconsistencia.
    """
    gra     = _monto(row.get("gra"))
    iva_doc = _monto(row.get("iva"))
    tipo    = str(row.get("tipo", ""))

    if tipo not in ("03", "06") or gra <= 0:
        return {}

    iva_correcto = round(gra * 0.13, 2)
    if abs(iva_doc - iva_correcto) <= 0.05:
        return {}

    return {
        "iva"            : iva_correcto,
        "_autocorregido_iva": True,
    }


def auto_corregir_retencion_07(row: dict) -> dict:
    """Calcula retención correcta DTE-07 (base × 1%)."""
    base    = _monto(row.get("base"))
    ret_doc = _monto(row.get("ret"))
    if base <= 0:
        return {}
    ret_correcto = round(base * 0.01, 2)
    if abs(ret_doc - ret_correcto) <= 0.05:
        return {}
    return {"ret": ret_correcto, "_autocorregido_ret": True}


def auto_corregir_retencion_14(row: dict) -> dict:
    """Calcula retención correcta DTE-14 (base × 10%) y líquido (base × 90%)."""
    base    = _monto(row.get("base"))
    ret_doc = _monto(row.get("ret"))
    if base <= 0:
        return {}
    ret_correcto    = round(base * 0.10, 2)
    liquido_correcto = round(base * 0.90, 2)
    if abs(ret_doc - ret_correcto) <= 0.05:
        return {}
    return {
        "ret"               : ret_correcto,
        "liquido"           : liquido_correcto,
        "_autocorregido_ret": True,
    }


def aplicar_autocorrecciones_df(df: "pd.DataFrame", tipo_dte: str) -> "pd.DataFrame":
    """
    Aplica auto-correcciones fiscales a todo un DataFrame en memoria.
    Marca las filas corregidas con _autocorregido_iva o _autocorregido_ret.

    Args:
        df       : DataFrame de resultados procesados.
        tipo_dte : "ventas" | "compras" | "retenciones" | "sujetos_excluidos"

    Returns:
        DataFrame con filas corregidas (no modifica las correctas).
    """
    import pandas as pd

    _fn_map = {
        "ventas"           : auto_corregir_iva_ventas,
        "compras"          : auto_corregir_iva_compras,
        "retenciones"      : auto_corregir_retencion_07,
        "sujetos_excluidos": auto_corregir_retencion_14,
    }
    fn = _fn_map.get(tipo_dte)
    if fn is None or df.empty:
        return df

    df = df.copy()
    for idx, row in df.iterrows():
        correcciones = fn(row.to_dict() if hasattr(row, "to_dict") else dict(row))
        for campo, valor in correcciones.items():
            if campo not in df.columns:
                df[campo] = None
            df.at[idx, campo] = valor

    return df


def mostrar_boton_autocorreccion(
    df: "pd.DataFrame",
    tipo_dte: str,
    session_key: str,
    container=None,
) -> "pd.DataFrame":
    """
    Muestra un botón "⚡ Auto-corregir IVA/Retención" en Streamlit.
    Al presionarlo, aplica las correcciones fiscales al DataFrame y lo guarda
    en session_state[session_key].

    Returns:
        DataFrame corregido (o el original si no se presionó el botón).
    """
    import streamlit as _st
    target = container or _st

    filas_con_error = _contar_filas_con_error(df, tipo_dte)
    if filas_con_error == 0:
        return df

    label = (
        f"⚡ Auto-corregir IVA ({filas_con_error} fila{'s' if filas_con_error > 1 else ''})"
        if tipo_dte in ("ventas", "compras")
        else f"⚡ Auto-corregir Retención ({filas_con_error} fila{'s' if filas_con_error > 1 else ''})"
    )

    if target.button(label, type="secondary", help="Recalcula IVA/retención según fórmulas DGII y actualiza las filas con error"):
        df_corr = aplicar_autocorrecciones_df(df, tipo_dte)
        try:
            import streamlit as _st2
            _st2.session_state[session_key] = df_corr
        except Exception:
            pass
        target.success(f"✅ {filas_con_error} fila(s) corregida(s) automáticamente.")
        return df_corr

    return df


def _contar_filas_con_error(df: "pd.DataFrame", tipo_dte: str) -> int:
    """Cuenta cuántas filas tienen errores de cuadre fiscal."""
    if df is None or (hasattr(df, "empty") and df.empty):
        return 0
    n = 0
    for _, row in df.iterrows():
        d = row.to_dict()
        if tipo_dte == "ventas":
            grav = _monto(d.get("gravadas")); iva = _monto(d.get("debito", 0))
            tipo = str(d.get("tipo", ""))
            if tipo in ("03", "05", "06") and grav > 0 and iva > 0 and abs(iva - round(grav * 0.13, 2)) > 0.05:
                n += 1
        elif tipo_dte == "compras":
            gra = _monto(d.get("gra")); iva = _monto(d.get("iva")); tipo = str(d.get("tipo", ""))
            if tipo in ("03", "06") and gra > 0 and iva > 0 and abs(iva - round(gra * 0.13, 2)) > 0.05:
                n += 1
        elif tipo_dte == "retenciones":
            base = _monto(d.get("base")); ret = _monto(d.get("ret"))
            if base > 0 and ret > 0 and abs(ret - round(base * 0.01, 2)) > 0.05:
                n += 1
        elif tipo_dte == "sujetos_excluidos":
            base = _monto(d.get("base")); ret = _monto(d.get("ret"))
            if base > 0 and ret > 0 and abs(ret - round(base * 0.10, 2)) > 0.05:
                n += 1
    return n


def razones_revisar_compra(row) -> str:
    """Devuelve string con el/los motivos de 🔴 Revisar, o '' si todo OK."""
    d     = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    gra   = _monto(d.get("gra", 0))
    iva   = _monto(d.get("iva", 0))
    sello = str(d.get("sello", "") or "").strip()
    tipo  = str(d.get("tipo", ""))
    razones = []
    if tipo in ("03", "06") and gra > 0 and iva > 0:
        iva_calc = round(gra * 0.13, 2)
        if abs(iva - iva_calc) > 0.05:
            razones.append(f"IVA ${iva:.2f} ≠ {gra:.2f}×13%=${iva_calc:.2f}")
    if len(sello) < 30:
        razones.append(f"Sello vacío o corto ({len(sello)} chars)")
    return " | ".join(razones)
