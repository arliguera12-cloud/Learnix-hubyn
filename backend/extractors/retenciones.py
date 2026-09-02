"""
Extractor de DTEs de Retenciones (Anexo 7 DGII — casilla 162 / IVA 1%).
Admite Comprobante de Retención (DTE-07) y sus correcciones — Nota de
Crédito (DTE-05) y Nota de Débito (DTE-06) — según el rango de "Tipo de
Documento" que define el manual del Anexo 7 del Ministerio de Hacienda.
Lógica portada de pages/3_Extractor_DTE_retenciones.py sin dependencias de Streamlit.
"""
import re
from concurrent.futures import ThreadPoolExecutor

import pdfplumber

from utils.pdf_utils import (
    safe_str,
    limpiar_monto,
    extraer_y_formatear_fecha,
    extraer_texto_pdf,
)
from utils.ai_utils import gemini_disponible, procesar_dte_con_gemini
from utils.gemini_vision import extraer_dte_con_vision, vision_disponible
from utils.qr_reader import extraer_datos_qr as _extraer_qr
from utils.mh_consulta import consultar_dte_publico
from utils.qa_utils import calcular_confianza
from utils.local_db import cargar_proveedores_combinados



def cargar_proveedores_json() -> dict:
    """
    Retorna dict combinado {nit: {nombre, nrc}}:
    - Catálogo global (proveedores_globales) como base
    - Catálogo privado de la org encima con prioridad
    """
    try:
        from utils.local_db import cargar_proveedores_combinados
        return cargar_proveedores_combinados()
    except Exception:
        return {}


def extraer_sello(texto_original: str) -> str:
    """Extrae el Sello de Recepción MH: alfanumérico ~40 chars sin guiones."""

    def _valido(v: str) -> bool:
        v = v.strip().upper()
        return (
            25 <= len(v) <= 60
            and "-" not in v
            and re.search(r"[A-Z]", v)
            and re.search(r"[0-9]", v)
            and not v.startswith("DTE")
        )

    t_ns = re.sub(r"\s+", "", texto_original).upper()

    # 1. Etiqueta en la misma línea (valor inmediato)
    m = re.search(
        r"(?:Sello\s+de\s+Recepci[oó]n|SelloRecibido|Sello\s+Recibido)"
        r"[\s:=\-]*([A-Z0-9]{25,60})",
        texto_original, re.I,
    )
    if m and _valido(m.group(1)):
        return m.group(1).strip().upper()

    # 2. Sin espacios (PDF que colapsa whitespace entre etiqueta y valor)
    for pat_ns in (
        r"SELLODERECEPCI[O0]N[:\-=]?([A-Z0-9]{25,60})",
        r"SELLORECIBIDO[:\-=]?([A-Z0-9]{25,60})",
        r"SELLORECEIBIDO[:\-=]?([A-Z0-9]{25,60})",
        r"SELLORECE[PC]CION[:\-=]?([A-Z0-9]{25,60})",
    ):
        m = re.search(pat_ns, t_ns)
        if m and _valido(m.group(1)):
            return m.group(1).upper()

    # 3. JSON-like embebido en el texto del PDF
    for pat_json in (
        r'"[Ss]ello[Rr]ecibido"\s*:\s*"([A-Z0-9]{25,60})"',
        r"'[Ss]ello[Rr]ecibido'\s*:\s*'([A-Z0-9]{25,60})'",
        r"[Ss]ello[Rr]ecibido\s*[=:]\s*\"?([A-Z0-9]{25,60})\"?",
        r"respuesta[Hh]acienda[^\"']{0,120}[Ss]ello[Rr]ecibido[\"'\s:=]+([A-Z0-9]{25,60})",
        r"response[Mm][Hh][^\"']{0,120}[Ss]ello[Rr]ecibido[\"'\s:=]+([A-Z0-9]{25,60})",
    ):
        m = re.search(pat_json, texto_original)
        if m and _valido(m.group(1)):
            return m.group(1).upper()

    # 4. Etiqueta en una línea, sello en la siguiente (layout vertical)
    lineas = texto_original.splitlines()
    for i, linea in enumerate(lineas):
        if re.search(
            r"[Ss]ello\s+(?:de\s+)?[Rr]ecepci[oó]n|[Ss]ello\s*[Rr]ecibido",
            linea,
        ):
            for sig in lineas[i + 1 : i + 5]:
                cand = re.sub(r"[^A-Z0-9]", "", sig.strip().upper())
                if _valido(cand):
                    return cand

    # 5. Cerca de "Fecha Procesado", "Fecha y Hora de Generación" (zona del sello MH)
    for pat_ctx in (
        r"(?:Fecha\s+[Yy]\s+Hora\s+de\s+Generaci[oó]n|Fecha\s+Procesad[oa]|"
        r"Procesado\s+(?:por\s+)?MH|FechaHora\s*Recepci[oó]n)"
        r"[^\n]{0,200}?([A-Z0-9]{30,50})",
    ):
        m = re.search(pat_ctx, texto_original, re.I | re.S)
        if m and _valido(m.group(1)):
            return m.group(1).upper()

    # 6. Standalone 36-44 chars alfanumérico (no es UUID puro de 32 hex)
    for cand in re.findall(r"(?<![A-Z0-9])([A-Z0-9]{36,44})(?![A-Z0-9])", t_ns):
        if _valido(cand) and len(cand) != 32:   # 32 = UUID sin guiones (solo hex)
            return cand

    # 7. Heurística de inicio por año (sello suele comenzar con el año de emisión)
    for linea in lineas:
        mc = re.match(r"^\s*(20[2-9]\d[A-Z0-9]{28,38})\s*$", linea, re.I)
        if mc and _valido(mc.group(1)):
            return mc.group(1).upper()

    return ""


def _leer_qr_y_consultar_mh(file_bytes: bytes) -> tuple[dict, dict | None]:
    """
    Lee el QR y, si trae código de generación, consulta el DTE completo en
    Hacienda — todo en un solo paso pensado para correr en un hilo aparte,
    en paralelo con la llamada a Visión (la más lenta del pipeline). Ninguna
    de las dos depende del resultado de la otra, así que no tiene sentido
    pagar sus tiempos de espera en serie.
    """
    try:
        qr = _extraer_qr(file_bytes)
    except Exception:
        qr = {}
    gen = str(qr.get("codigo_generacion") or "").upper()
    fecha_qr_iso = str(qr.get("fecha_qr") or "").strip()
    consulta_mh = consultar_dte_publico(gen, fecha_qr_iso) if gen and fecha_qr_iso else None
    return qr, consulta_mh


def extraer_retencion_nativa(file_bytes: bytes, cliente_activo: dict) -> dict:
    if not file_bytes or len(file_bytes) < 512:
        return {"error": "Archivo vacío o corrupto."}

    # ── Vision-First: extraer con IA antes de pdfplumber ─────────────────────
    _nit_cliente_ctx = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
    _nom_cliente_ctx = cliente_activo.get('nombre', '')

    gemini_correcciones: list[str] = []
    _vision_campos: dict  = {}
    _vision_alertas: list = []
    _vision_audit: dict   = {}

    # El QR+Hacienda no depende del texto/regex del PDF — se lanza en un
    # hilo aparte para correr en paralelo con el parseo de texto+regex de
    # abajo. Visión YA NO se lanza aquí sin condición: antes se disparaba
    # para TODOS los documentos de un lote, saturando el rate limit de
    # Groq; ahora solo se llama más abajo si, tras regex + QR + Hacienda,
    # la confianza sigue baja.
    with ThreadPoolExecutor(max_workers=1) as _pool:
        _qr_future = _pool.submit(_leer_qr_y_consultar_mh, file_bytes)

        try:
            texto_lineal, texto_visual = extraer_texto_pdf(file_bytes)
            texto_completo = texto_lineal + "\n" + texto_visual

            t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
            t_no_sp = re.sub(r'\s+', '', t_clean).upper()

            m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]{1,20}-\d{9,18})", t_no_sp)
            tipo   = "07"
            if m_ctrl:
                ctrl   = m_ctrl.group(1).replace("O", "0")
                m_tipo = re.search(r"DTE-(\d{2})", ctrl)
                if m_tipo:
                    tipo = m_tipo.group(1)

            nit_cliente = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))

            gen = ""
            m_uuid = re.search(
                r"([A-Fa-f0-9]{8}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{12})",
                t_no_sp
            )
            if m_uuid:
                raw = m_uuid.group(1).replace("-", "")
                if len(raw) == 32:
                    gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}".upper()

            sello = extraer_sello(t_clean)
            fecha = extraer_y_formatear_fecha(t_clean)

            nit_prov = ""
            dui_agente = ""
            patron_ids = (
                r"\b\d{4}\s*-?\s*\d{6}\s*-?\s*\d{3}\s*-?\s*\d\b"
                r"|\b\d{14}\b"
            )
            # Buscar en texto_completo (con espacios, captura NITs con separadores)
            ids_raw  = re.findall(patron_ids, texto_completo)
            # Fallback: buscar 14 dígitos consecutivos en texto sin espacios
            ids_raw += re.findall(r'\d{14}', t_no_sp)
            ids_limp   = list(dict.fromkeys(re.sub(r'[^0-9]', '', n) for n in ids_raw))
            candidatos = [n for n in ids_limp if n != nit_cliente and len(n) == 14]

            proveedores_db = cargar_proveedores_json()
            for n in candidatos:
                if n in proveedores_db:
                    nit_prov = n
                    break

            if not nit_prov and candidatos:
                nit_prov = candidatos[0]

            # DUI del agente de retención (solo si no hay NIT) — el manual del
            # Anexo 7 acepta ambos identificadores (columnas A y H), para el
            # caso de un agente persona natural sin NIT. Mismo patrón que ya
            # usa compras.py para el DUI del proveedor.
            if not nit_prov:
                for m in re.finditer(r'\b(\d{8}[\s\-]?\d|\d{9})\b', texto_completo):
                    _dui_cand = re.sub(r'[^0-9]', '', m.group(0))
                    if _dui_cand != nit_cliente and len(_dui_cand) == 9:
                        dui_agente = _dui_cand
                        break

            base, ret = 0.0, 0.0

            m_base = re.search(
                r"(?:Monto\s+[Ss]ujeto|[Ss]ujeto\s+a\s+[Rr]etenci[oó]n|"
                r"[Tt]otal\s+[Mm]onto\s+[Ss]ujeto(?:\s+a\s+[Rr]etener?)?)"
                r"[^\d$]{0,30}\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+)",
                t_clean, re.I
            )
            m_ret = re.search(
                r"(?:[Tt]otal\s+IVA\s+[Rr]etenido|[Tt]otal\s+IVA\s+[Rr]eteni"
                r"|[Ii]mpuesto\s+[Rr]etenido|[Rr]etenci[oó]n\s+1%|[Mm]onto\s+[Rr]etenci[oó]n)"
                r"[^\d$]{0,30}\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+)",
                t_clean, re.I
            )

            if m_base:
                base = limpiar_monto(m_base.group(1))
            if m_ret:
                ret = limpiar_monto(m_ret.group(1))

            if base == 0.0:
                montos_raw = re.findall(
                    r"(?:US\$?|\$)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d{2,}(?:[.,]\d{1,2})?)",
                    t_clean
                )
                valores = sorted(
                    list({limpiar_monto(m) for m in montos_raw if limpiar_monto(m) > 0}),
                    reverse=True
                )
                for v in valores:
                    ret_calc = round(v * 0.01, 2)
                    if any(abs(r - ret_calc) <= 0.05 for r in valores if r < v):
                        base = v
                        ret  = ret_calc
                        break

            if base > 0 and ret == 0:
                ret = round(base * 0.01, 2)

            if ret > 0 and base == 0:
                base = round(ret * 100, 2)
        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
            return {"error": "PDF inválido o corrupto."}
        except Exception as err:
            return {"error": str(err)}

        # A este punto el parseo de texto+regex ya terminó.
        if len(texto_completo.strip()) < 50 and not m_ctrl:
            return {"error": "PDF de imagen — sin texto extraíble."}

        # El Anexo 7 admite Comprobante de Retención (07) y también Notas de
        # Crédito/Débito (05/06) que corrigen una retención ya declarada —
        # el manual del MH define ese mismo rango para la columna "Tipo de
        # Documento". El regex de montos de abajo es genérico (busca
        # "Monto Sujeto"/"Total IVA Retenido" en el texto) y Visión no
        # depende del tipo de documento, así que en principio funcionan
        # igual — pero no está verificado contra una Nota de Crédito/Débito
        # real todavía.
        if tipo not in ("05", "06", "07"):
            return {
                "error_tipo": (
                    f"Documento DTE-{tipo}. Solo se admiten DTE-07 (Comprobante de "
                    "Retención), DTE-05 (Nota de Crédito) o DTE-06 (Nota de Débito)."
                )
            }

        # ── Auditoría: qué método sacó cada campo (ver mismo patrón en compras.py) ──
        fuentes: dict[str, str] = {k: "regex" for k in ("fecha", "nit_prov", "sello", "base", "ret")}

        # ── QR ES EL REY: sobreescribe campos con datos confiables del QR ────────
        # (leído en paralelo con Visión más arriba — aquí solo se recoge el
        # resultado, ya listo, sin volver a leer el QR ni consultar Hacienda).
        _qr, _consulta_mh = _qr_future.result()
        _fecha_qr_iso = ""
        try:
            if _qr.get("codigo_generacion"):
                gen = _qr["codigo_generacion"].upper()
            # NIT del emisor del QR como respaldo
            if not nit_prov and _qr.get("nit_emisor_qr"):
                _nq = re.sub(r'[^0-9]', '', str(_qr["nit_emisor_qr"]))
                if len(_nq) == 14 and _nq != nit_cliente:
                    nit_prov = _nq
                    fuentes["nit_prov"] = "qr"
            # Fecha del QR como respaldo
            if _qr.get("fecha_qr"):
                _fecha_qr_iso = str(_qr["fecha_qr"]).strip()
                if not fecha:
                    _mf = re.match(r'(\d{4})-(\d{2})-(\d{2})', _fecha_qr_iso)
                    if _mf:
                        fecha = f"{_mf.group(3)}/{_mf.group(2)}/{_mf.group(1)}"
                        fuentes["fecha"] = "qr"
        except Exception:
            pass

        # ── Consulta pública de Hacienda: fuente más confiable que existe, y
        # corre ANTES que la IA a propósito — es gratis (un GET, sin gastar
        # tokens) y más confiable que cualquier inferencia sobre el PDF. Con
        # el código de generación del QR se puede pedir el DTE oficial
        # completo al MH — el mismo dato que muestra la página de
        # "consultaPublica" al escanear el QR con el celular. Si responde,
        # sus montos pisan lo que haya (regex/Vision) y el gate de la IA de
        # abajo ya no tiene nada que corregir en base/ret, ahorrando la
        # llamada. Hacienda no expone el NIT del sujeto retenido (privacidad),
        # así que ese campo sigue dependiendo de regex/Vision/IA.
        if _consulta_mh:
            _resumen_mh = (_consulta_mh.get("documento") or {}).get("resumen") or {}
            _base_mh = _resumen_mh.get("totalSujetoRetencion")
            _ret_mh  = _resumen_mh.get("totalIVAretenido")
            if _base_mh is not None:
                base = float(_base_mh)
                fuentes["base"] = "hacienda"
            if _ret_mh is not None:
                ret = float(_ret_mh)
                fuentes["ret"] = "hacienda"
            if _consulta_mh.get("selloVal"):
                sello = str(_consulta_mh["selloVal"]).upper()
                fuentes["sello"] = "hacienda"
            gemini_correcciones.append("Hacienda: montos verificados con la consulta pública")

        # ── Visión SOLO si Hacienda + regex no alcanzan ───────────────────────
        # Antes Visión se lanzaba SIEMPRE en paralelo para cada documento del
        # lote, sin importar si ya había datos suficientes — eso saturaba el
        # rate limit de Groq cuando el lote tenía 10-20 PDFs. Ahora se calcula
        # la confianza con lo que ya se tiene (regex + QR + Hacienda) y solo
        # se gasta una llamada a Visión si el documento sigue incompleto.
        _campos_pre_vision = {
            "nit_prov": nit_prov or dui_agente, "fecha": fecha, "sello": sello,
            "gen": gen, "base": base, "ret": ret,
        }
        _confianza_pre_vision = calcular_confianza(_campos_pre_vision, "retenciones")
        if _confianza_pre_vision["score"] < 85 and vision_disponible():
            _vision_campos, _vision_alertas, _vision_audit = extraer_dte_con_vision(
                file_bytes, "retenciones",
                {"nit": _nit_cliente_ctx, "nombre": _nom_cliente_ctx},
            )
            gemini_correcciones += [
                f"Visión: {a}" for a in _vision_alertas
            ] if _vision_alertas else (
                [f"Visión: extrajo {len(_vision_campos)} campo(s)"]
                if _vision_campos else []
            )
            if _vision_campos:
                if _vision_campos.get("fecha") and not fecha:
                    fecha    = _vision_campos["fecha"]
                    fuentes["fecha"] = "vision"
                if _vision_campos.get("nit_prov") and not nit_prov:
                    nit_prov = _vision_campos["nit_prov"]
                    fuentes["nit_prov"] = "vision"
                if _vision_campos.get("base") and base == 0.0:
                    base = float(_vision_campos["base"])
                    fuentes["base"] = "vision"
                if _vision_campos.get("ret") and ret == 0.0:
                    ret = float(_vision_campos["ret"])
                    fuentes["ret"] = "vision"
                v_sello = str(_vision_campos.get("sello_recepcion") or "").strip()
                if len(v_sello) >= 25 and "-" not in v_sello and len(sello) < 25:
                    sello = v_sello
                    fuentes["sello"] = "vision"

        # "nit_prov or dui_agente" solo para el cálculo de confianza — el
        # campo requerido es "algún identificador del agente", no
        # específicamente el NIT (que puede legítimamente estar vacío
        # cuando el agente es una persona natural identificada por DUI).
        _campos_pre_ia = {
            "nit_prov": nit_prov or dui_agente, "fecha": fecha, "sello": sello,
            "gen": gen, "base": base, "ret": ret,
        }
        _confianza_pre = calcular_confianza(_campos_pre_ia, "retenciones")
        if 50 <= _confianza_pre["score"] < 85 and gemini_disponible():
            _campos_act = {"fecha": fecha, "nit_prov": nit_prov, "base": base, "ret": ret}
            _texto_ia = (texto_visual + "\n\n" + texto_lineal) if texto_visual else texto_lineal
            _corr_dict, _correcciones_ia = procesar_dte_con_gemini(
                _texto_ia,
                "retenciones",
                _campos_act,
                {"nit": _nit_cliente_ctx, "nombre": _nom_cliente_ctx},
            )
            gemini_correcciones += [f"IA: {c}" for c in _correcciones_ia]
            if _corr_dict.get("fecha"):
                fecha    = _corr_dict["fecha"]
                fuentes["fecha"] = "ia"
            if _corr_dict.get("nit_prov"):
                nit_prov = _corr_dict["nit_prov"]
                fuentes["nit_prov"] = "ia"
            if _corr_dict.get("base"):
                base = _corr_dict["base"]
                fuentes["base"] = "ia"
            if _corr_dict.get("ret"):
                ret = _corr_dict["ret"]
                fuentes["ret"] = "ia"
            # Si la IA corrigió un solo lado del par base/1%, recalcula el otro
            # en vez de dejarlos inconsistentes entre sí.
            if _corr_dict.get("base") and not _corr_dict.get("ret") and ret == 0:
                ret = round(base * 0.01, 2)
            elif _corr_dict.get("ret") and not _corr_dict.get("base") and base == 0:
                base = round(ret * 100, 2)

        _campos_finales = {
            "nit_prov": nit_prov or dui_agente, "fecha": fecha, "sello": sello,
            "gen": gen, "base": base, "ret": ret,
        }
        _confianza = calcular_confianza(_campos_finales, "retenciones")
        if _confianza["score"] >= 85:
            estado = "OK"
        elif _confianza["score"] >= 50:
            estado = "REVISAR"
        else:
            estado = "REVISION_MANUAL"

        return {
            "nit_prov"            : nit_prov,
            "dui_agente"          : dui_agente,
            "fecha"               : fecha,
            "tipo"                : tipo,
            "sello"               : sello,
            "gen"                 : gen,
            "base"                : base,
            "ret"                 : ret,
            "fuentes"             : fuentes,
            "estado"              : estado,
            "confianza"           : _confianza["score"],
            "campos_faltantes"    : _confianza["campos_faltantes"],
            "validacion_montos"   : _confianza["validacion_montos"],
            "detalle_confianza"   : _confianza["detalle"],
            "gemini_correcciones" : gemini_correcciones,
            "_vision_campos"      : _vision_campos,
            "_vision_alertas"     : _vision_alertas,
            "_vision_audit"       : _vision_audit,
        }
