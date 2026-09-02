"""
Extractor de DTEs de Sujetos Excluidos (DTE-14 — casilla 66 / retención renta 10%).
Lógica portada de pages/4_Extractor_DTE_Sujetos_Excluidos.py sin dependencias de Streamlit.
"""
import re
from concurrent.futures import ThreadPoolExecutor

import pdfplumber

from utils.pdf_utils import (
    limpiar_nit,
    limpiar_monto,
    extraer_y_formatear_fecha,
    extraer_texto_pdf,
)
from utils.ai_utils import gemini_disponible, procesar_dte_con_gemini, es_nombre_sospechoso
from utils.gemini_vision import extraer_dte_con_vision, vision_disponible
from utils.qr_reader import extraer_datos_qr as _extraer_qr
from utils.mh_consulta import consultar_dte_publico, estado_doc_alerta
from utils.qa_utils import calcular_confianza


def _leer_qr_y_consultar_mh(file_bytes: bytes) -> tuple[dict, dict | None]:
    """
    Lee el QR y, si trae código de generación, consulta el DTE completo en
    Hacienda — en un hilo aparte, en paralelo con Visión. Igual que en
    retenciones.py: a diferencia de ese caso, para DTE-14 Hacienda sí expone
    la identificación del sujeto excluido (`numeIdenRecep`), no solo los
    montos — no hay razón de privacidad para ocultarla, a diferencia del NIT
    del sujeto retenido en un DTE-07.
    """
    try:
        qr = _extraer_qr(file_bytes)
    except Exception:
        qr = {}
    gen = str(qr.get("codigo_generacion") or "").upper()
    fecha_qr_iso = str(qr.get("fecha_qr") or "").strip()
    consulta_mh = consultar_dte_publico(gen, fecha_qr_iso) if gen and fecha_qr_iso else None
    return qr, consulta_mh



def extraer_nombre_receptor(texto: str) -> str:
    """
    Los DTE-14 de FULLCHEM tienen EMISOR y RECEPTOR en la misma línea:
      "Nombre o razón social: INDUSTRIAS FULLCHEM... Nombre o razón social: CARLOS ENRIQUE SASSO LEMUS"
    
    La clave es tomar la SEGUNDA ocurrencia de "Nombre o razón social:" en la línea.
    También manejamos el caso donde están en líneas separadas (otros emisores).
    """
    # ── Estrategia 1: misma línea — buscar segunda ocurrencia del patrón en una sola línea ──
    # Patrón: dos "Nombre o razón social:" en la misma línea
    m = re.search(
        r"[Nn]ombre\s+o\s+raz[oó]n\s+social\s*:\s*.+?"   # primera (emisor)
        r"[Nn]ombre\s+o\s+raz[oó]n\s+social\s*:\s*"       # segunda etiqueta (receptor)
        r"([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑa-záéíóúüñ ,.\-]+)",   # nombre del receptor
        texto, re.I
    )
    if m:
        nombre = re.sub(r'\s+', ' ', m.group(1)).strip()
        # Cortar si llega a NIT: o DUI: u otro campo
        nombre = re.split(r'\s+(?:NIT|DUI|N[úu]mero|Direcci[oó]n|Correo|Tel[eé]fono)\s*[:\-]', nombre, flags=re.I)[0]
        nombre = nombre.strip()
        if 3 < len(nombre) <= 65 and not es_nombre_sospechoso(nombre):
            return nombre.upper()

    # ── Estrategia 2: líneas separadas — tomar el último "Nombre o razón social:" ──
    todas = re.findall(
        r"[Nn]ombre\s+o\s+raz[oó]n\s+social\s*[:\-]?\s*([^\n]+)",
        texto, re.I
    )
    if len(todas) >= 2:
        nombre = re.sub(r'\s+', ' ', todas[-1]).strip()
        nombre = re.split(r'\s+(?:NIT|DUI|N[úu]mero|Direcci[oó]n|Correo|Tel[eé]fono)\s*[:\-]', nombre, flags=re.I)[0]
        nombre = nombre.strip()
        if 3 < len(nombre) <= 65 and not es_nombre_sospechoso(nombre):
            return nombre.upper()
    elif len(todas) == 1:
        nombre = re.sub(r'\s+', ' ', todas[0]).strip()
        if 3 < len(nombre) <= 65 and not es_nombre_sospechoso(nombre):
            return nombre.upper()

    return "⚠️ REVISAR NOMBRE"


def extraer_nit_receptor(texto: str, nit_cliente: str) -> str:
    """
    Similar al nombre: en DTE-14 FULLCHEM el NIT del receptor está en la MISMA línea
    que el NIT del emisor: "NIT: 0614-270815-107-7  NIT: 07515732-7"
    Tomamos el último NIT que NO sea el del cliente/emisor.
    """
    # Buscar todos los NITs/DUIs del texto
    patron = (
        r"\b\d{4}\s*-\s*\d{6}\s*-\s*\d{3}\s*-\s*\d\b"   # NIT empresa 0614-270815-107-7
        r"|\b\d{8}\s*-\s*\d\b"                              # DUI 07515732-7
        r"|\b\d{14}\b"                                       # NIT sin guiones
        r"|\b\d{9}\b"                                        # DUI sin guión
    )
    ids_raw   = re.findall(patron, texto)
    ids_limp  = list(dict.fromkeys(limpiar_nit(n) for n in ids_raw))
    candidatos = [n for n in ids_limp if n != nit_cliente and len(n) >= 8]

    # El receptor suele ser el ÚLTIMO NIT distinto al emisor (que va primero)
    if candidatos:
        return candidatos[-1]
    return ""


def extraer_sello_dte14(texto: str) -> str:
    """Extrae el Sello de Recepción del DTE-14."""
    # Intento 1: etiqueta explícita
    m = re.search(
        r"[Ss]ello\s+(?:de\s+)?[Rr]ecepci[oó]n\s*[:\-]?\s*([A-Z0-9]{20,50})",
        texto, re.I
    )
    if m:
        return m.group(1).strip()[:40]

    # Intento 2: cadena año + 36 chars alfanuméricos en texto sin espacios
    t_ns = re.sub(r'\s+', '', texto).upper()
    m2 = re.search(r'(20[2-3]\d[A-Z0-9]{36})', t_ns)
    if m2:
        return m2.group(1)

    # Intento 3: "SELLO" seguido de la cadena en texto compacto
    m3 = re.search(r'SELLO[A-Z]*:?([A-Z0-9]{30,50})', t_ns)
    if m3:
        return m3.group(1)[:40]

    # Intento 4: línea que sea exactamente un sello (año + alfanumérico, sin guiones)
    for linea in texto.splitlines():
        linea_s = linea.strip()
        mc = re.match(r'^(20[2-3]\d[A-Z0-9]{26,})$', linea_s, re.I)
        if mc:
            candidato = mc.group(1).upper()
            if '-' not in candidato:
                return candidato

    return ""


def extraer_sujetos_nativo(file_bytes: bytes, cliente_activo: dict) -> dict:
    if not file_bytes or len(file_bytes) < 512:
        return {"error": "Archivo vacío o corrupto."}

    # ── Vision-First: extraer con IA antes de pdfplumber ─────────────────────
    _nit_cliente_ctx = limpiar_nit(cliente_activo.get('nit', ''))
    _nom_cliente_ctx = cliente_activo.get('nombre', '')

    gemini_correcciones: list[str] = []
    _vision_campos: dict  = {}
    _vision_alertas: list = []
    _vision_audit: dict   = {}

    # QR+Hacienda no depende del texto/regex del PDF — se lanza en un hilo
    # aparte para correr en paralelo con el parseo de texto de abajo. Visión
    # YA NO se lanza aquí sin condición: antes se disparaba para TODOS los
    # documentos de un lote, saturando el rate limit de Groq; ahora solo se
    # llama más abajo si, tras regex + QR + Hacienda, la confianza sigue baja.
    with ThreadPoolExecutor(max_workers=1) as _pool:
        _qr_future = _pool.submit(_leer_qr_y_consultar_mh, file_bytes)

        try:
            texto_lineal, texto_visual = extraer_texto_pdf(file_bytes)
            texto_completo = texto_lineal + "\n" + texto_visual

            t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
            t_no_sp = re.sub(r'\s+', '', t_clean).upper()

            # ── Tipo DTE ──
            m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]{1,20}-\d{9,18})", t_no_sp)
            tipo   = "14"
            if m_ctrl:
                ctrl   = m_ctrl.group(1).replace("O", "0")
                m_tipo = re.search(r"DTE-(\d{2})", ctrl)
                if m_tipo:
                    tipo = m_tipo.group(1)

            nit_cliente = limpiar_nit(cliente_activo.get('nit', ''))

            # ── UUID / Código de Generación ──
            gen = ""
            m_uuid = re.search(
                r"([A-Fa-f0-9]{8}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{12})",
                t_no_sp
            )
            if m_uuid:
                raw = m_uuid.group(1).replace("-", "")
                if len(raw) == 32:
                    gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}".upper()

            # ── Número de Control ──
            num_control = ""
            m_nc = re.search(r"(DTE-14-[A-Z0-9]+-\d+)", t_no_sp)
            if m_nc:
                num_control = m_nc.group(1)

            # ── Sello de Recepción ──
            sello = extraer_sello_dte14(t_clean)

            fecha = extraer_y_formatear_fecha(t_clean)

            # ── Nombre del receptor ──
            nom_sujeto = extraer_nombre_receptor(t_clean)

            # ── NIT/DUI del receptor ──
            id_sujeto = extraer_nit_receptor(t_clean, nit_cliente)

            # ── Montos: Base (Sumatoria ventas / Sub-Total) y Retención Renta 10% ──
            base = 0.0
            ret  = 0.0

            # Retención Renta — etiqueta explícita
            m_ret_renta = re.search(
                r"[Rr]etenci[oó]n\s+[Rr]enta\s*[:\-]?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)",
                t_clean
            )
            if m_ret_renta:
                ret = limpiar_monto(m_ret_renta.group(1))

            # Sub-Total o Sumatoria de ventas
            m_base = re.search(
                r"(?:[Ss]umatoria\s+de\s+[Vv]entas|[Ss]ub[-\s]?[Tt]otal)\s*[:\-]?\s*"
                r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)",
                t_clean
            )
            if m_base:
                base = limpiar_monto(m_base.group(1))

            # Fallback: relación matemática 10%
            if base == 0.0 and ret > 0:
                base = round(ret * 10, 2)

            if base == 0.0:
                montos_raw = re.findall(
                    r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                    t_clean
                )
                valores = sorted(
                    list({limpiar_monto(m) for m in montos_raw if limpiar_monto(m) > 0}),
                    reverse=True
                )
                for v in valores:
                    ret_calc = round(v * 0.10, 2)
                    if any(abs(r - ret_calc) <= 0.05 for r in valores if r < v):
                        base = v
                        if ret == 0:
                            ret = ret_calc
                        break

            if base > 0 and ret == 0:
                ret = round(base * 0.10, 2)
        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
            return {"error": "PDF inválido o corrupto."}
        except Exception as err:
            return {"error": str(err)}

        # A este punto el parseo de texto+regex ya terminó.
        if len(texto_completo.strip()) < 50 and not m_ctrl:
            return {"error": "PDF de imagen — sin texto extraíble."}

        if tipo != "14":
            return {"error_tipo": f"Documento DTE-{tipo}. Solo se admiten DTE-14 (Sujetos Excluidos)."}

        # ── Auditoría: qué método sacó cada campo (ver mismo patrón en compras.py) ──
        fuentes: dict[str, str] = {k: "regex" for k in ("fecha", "id_sujeto", "nom_sujeto", "sello", "base", "ret")}

        # ── QR ES EL REY: sobreescribe campos con datos confiables del QR ────────
        # (leído en paralelo con Visión más arriba — aquí solo se recoge el
        # resultado, ya listo, sin volver a leer el QR ni consultar Hacienda).
        _qr, _consulta_mh = _qr_future.result()
        _fecha_qr_iso = ""
        try:
            if _qr.get("codigo_generacion"):
                gen = _qr["codigo_generacion"].upper()
            if _qr.get("num_control") and not num_control:
                _qc = _qr["num_control"].upper()
                _mq = re.search(r'DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18}', _qc, re.I)
                if _mq:
                    num_control = _qc.replace("-", "")
                    tipo        = _mq.group(1)
            # NIT del sujeto excluido del QR como respaldo
            if not id_sujeto and _qr.get("nit_emisor_qr"):
                _nq = re.sub(r'[^0-9]', '', str(_qr["nit_emisor_qr"]))
                if len(_nq) >= 9 and _nq != nit_cliente:
                    id_sujeto = _nq
                    fuentes["id_sujeto"] = "qr"
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

        # ── Consulta pública de Hacienda: corre ANTES que la IA a propósito —
        # es gratis y más confiable que cualquier inferencia sobre el PDF.
        # A diferencia de retenciones, acá Hacienda sí expone la
        # identificación del sujeto excluido (numeIdenRecep) — no hay razón
        # de privacidad para ocultarla como con el NIT de un sujeto retenido.
        _mh_alerta = estado_doc_alerta(_consulta_mh)
        if _mh_alerta:
            gemini_correcciones.append(f"Hacienda: {_mh_alerta}")

        if _consulta_mh:
            _resumen_mh = (_consulta_mh.get("documento") or {}).get("resumen") or {}
            _base_mh = _resumen_mh.get("subTotal")
            _ret_mh  = _resumen_mh.get("reteRenta")
            _id_mh   = str(_consulta_mh.get("numeIdenRecep") or "").strip()
            if _base_mh is not None:
                base = float(_base_mh)
                fuentes["base"] = "hacienda"
            if _ret_mh is not None:
                ret = float(_ret_mh)
                fuentes["ret"] = "hacienda"
            if _id_mh:
                id_sujeto = _id_mh
                fuentes["id_sujeto"] = "hacienda"
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
            "id_sujeto": id_sujeto, "nom_sujeto": nom_sujeto, "fecha": fecha,
            "sello": sello, "gen": gen, "base": base, "ret": ret,
        }
        _confianza_pre_vision = calcular_confianza(_campos_pre_vision, "sujetos_excluidos")
        if _confianza_pre_vision["score"] < 85 and vision_disponible():
            _vision_campos, _vision_alertas, _vision_audit = extraer_dte_con_vision(
                file_bytes, "sujetos_excluidos",
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
                    fecha = _vision_campos["fecha"]
                    fuentes["fecha"] = "vision"
                if _vision_campos.get("nom_sujeto") and nom_sujeto == "⚠️ REVISAR NOMBRE":
                    nom_sujeto = _vision_campos["nom_sujeto"]
                    fuentes["nom_sujeto"] = "vision"
                if _vision_campos.get("id_sujeto") and not id_sujeto:
                    id_sujeto = _vision_campos["id_sujeto"]
                    fuentes["id_sujeto"] = "vision"
                if _vision_campos.get("base") and base == 0.0:
                    base = float(_vision_campos["base"])
                    fuentes["base"] = "vision"
                if _vision_campos.get("ret") and ret == 0.0:
                    ret = float(_vision_campos["ret"])
                    fuentes["ret"] = "vision"

        _campos_pre_ia = {
            "id_sujeto": id_sujeto, "nom_sujeto": nom_sujeto, "fecha": fecha,
            "sello": sello, "gen": gen, "base": base, "ret": ret,
        }
        _confianza_pre = calcular_confianza(_campos_pre_ia, "sujetos_excluidos")
        if 50 <= _confianza_pre["score"] < 85 and gemini_disponible():
            _nit_suj = id_sujeto if len(id_sujeto) == 14 else ""
            _dui_suj = id_sujeto if len(id_sujeto) == 9  else ""
            _campos_act = {
                "fecha"     : fecha,
                "nom_sujeto": nom_sujeto,
                "nit_sujeto": _nit_suj,
                "dui_sujeto": _dui_suj,
            }
            _texto_ia = (texto_visual + "\n\n" + texto_lineal) if texto_visual else texto_lineal
            _corr_dict, _correcciones_ia = procesar_dte_con_gemini(
                _texto_ia,
                "sujetos_excluidos",
                _campos_act,
                {"nit": _nit_cliente_ctx, "nombre": _nom_cliente_ctx},
            )
            gemini_correcciones += [f"IA: {c}" for c in _correcciones_ia]
            if _corr_dict.get("fecha"):
                fecha = _corr_dict["fecha"]
                fuentes["fecha"] = "ia"
            if _corr_dict.get("nom_sujeto"):
                nom_sujeto = _corr_dict["nom_sujeto"]
                fuentes["nom_sujeto"] = "ia"
            if _corr_dict.get("nit_sujeto"):
                id_sujeto = _corr_dict["nit_sujeto"]
                fuentes["id_sujeto"] = "ia"
            elif _corr_dict.get("dui_sujeto"):
                id_sujeto = _corr_dict["dui_sujeto"]
                fuentes["id_sujeto"] = "ia"

        _campos_finales = {
            "id_sujeto": id_sujeto, "nom_sujeto": nom_sujeto, "fecha": fecha,
            "sello": sello, "gen": gen, "base": base, "ret": ret,
        }
        _confianza = calcular_confianza(_campos_finales, "sujetos_excluidos")
        if _confianza["score"] >= 85:
            estado = "OK"
        elif _confianza["score"] >= 50:
            estado = "REVISAR"
        else:
            estado = "REVISION_MANUAL"
        _detalle_confianza = _confianza["detalle"]
        if _mh_alerta:
            estado = "REVISION_MANUAL"
            _detalle_confianza = f"Hacienda: {_mh_alerta}. " + _detalle_confianza

        return {
            "fecha"               : fecha,
            "id_sujeto"           : id_sujeto,
            "nom_sujeto"          : nom_sujeto,
            "tipo"                : tipo,
            "sello"               : sello,
            "gen"                 : gen,
            "num_control"         : num_control,
            "fuentes"             : fuentes,
            "base"                : base,
            "ret"                 : ret,
            "estado"              : estado,
            "confianza"           : _confianza["score"],
            "campos_faltantes"    : _confianza["campos_faltantes"],
            "validacion_montos"   : _confianza["validacion_montos"],
            "detalle_confianza"   : _detalle_confianza,
            "gemini_correcciones" : gemini_correcciones,
            "_vision_campos"      : _vision_campos,
            "_vision_alertas"     : _vision_alertas,
            "_vision_audit"       : _vision_audit,
        }
