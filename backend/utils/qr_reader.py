"""
utils/qr_reader.py — Lector QR para DTEs de El Salvador.

Los DTEs del MH incluyen un código QR con URL tipo:
  https://admin.factura.gob.sv/consultaPublica?ambiente=01&codGen=UUID&...

Cascada de 4 estrategias (cada una aislada con try/except):
  1. fitz (PyMuPDF) + zxingcpp    — pure Python, sin deps de sistema
  2. fitz (PyMuPDF) + pyzbar      — requiere libzbar0 instalado en el SO
  3. fitz (PyMuPDF) + cv2         — opencv-python-headless
  4. Regex en texto pdfplumber    — solo PDFs con texto seleccionable (no escaneados)

Instalación recomendada (Streamlit Cloud, sin deps de sistema):
  PyMuPDF  zxingcpp  opencv-python-headless  (ya en requirements.txt)
"""
from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs

log = logging.getLogger(__name__)

# ── Parámetros URL del MH El Salvador ────────────────────────────────────────

_P_UUID  = ("codGen", "codigoGeneracion", "codigo_generacion", "uuid")
_P_CTRL  = ("numControl", "numeroControl", "numero_control")
_P_TIPO  = ("tipodte", "tipoDte", "tipo_dte")
_P_FECHA = ("fechaEmi", "fecha_emision", "fecha")
_P_NIT   = ("nitEmisor", "nit", "emisorNit")

_UUID_RE = re.compile(
    r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}'
    r'-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}',
    re.I,
)
_CTRL_RE = re.compile(r'DTE-\d{2}-[A-Z0-9]{1,20}-\d{12,18}', re.I)


# ── Parseo del texto del QR ───────────────────────────────────────────────────

def _parse_qr_text(text: str) -> dict:
    """Extract DTE fields from a QR URL string or raw text."""
    result: dict = {}
    if not text:
        return result

    # Intento 1: query-string URL
    try:
        query  = text.split("?", 1)[1] if "?" in text else text
        params = parse_qs(query, keep_blank_values=False)
        plower = {k.lower(): v for k, v in params.items()}

        for key in _P_UUID:
            vals = plower.get(key.lower(), [])
            if vals:
                val = vals[0].strip().upper()
                if _UUID_RE.fullmatch(val):
                    result["codigo_generacion"] = val
                    break

        for key in _P_CTRL:
            vals = plower.get(key.lower(), [])
            if vals:
                result["num_control"] = vals[0].strip().upper()
                break

        for key in _P_TIPO:
            vals = plower.get(key.lower(), [])
            if vals:
                result["tipo"] = vals[0].strip().zfill(2)
                break

        for key in _P_FECHA:
            vals = plower.get(key.lower(), [])
            if vals:
                result["fecha_qr"] = vals[0].strip()
                break

        for key in _P_NIT:
            vals = plower.get(key.lower(), [])
            if vals:
                nit = re.sub(r'[^0-9]', '', vals[0])
                if len(nit) in (9, 14):
                    result["nit_emisor_qr"] = nit
                break
    except Exception as exc:
        log.debug("QR URL parse: %s", exc)

    # Intento 2: regex UUID directo (con corrección O→0, I→1)
    if not result.get("codigo_generacion"):
        t = text.upper().replace("O", "0").replace("I", "1")
        m = _UUID_RE.search(t)
        if m:
            result["codigo_generacion"] = m.group(0).upper()

    # Intento 3: regex num_control directo
    if not result.get("num_control"):
        m2 = _CTRL_RE.search(text.upper())
        if m2:
            result["num_control"] = m2.group(0)

    return result


# ── Conversión PDF → imágenes PIL ────────────────────────────────────────────

def _pdf_to_pil_images(pdf_bytes: bytes) -> list:
    """
    Renders first + last PDF pages to PIL Images at 2× zoom (~144 DPI).
    Requires: PyMuPDF (fitz) + Pillow.
    """
    import fitz
    from PIL import Image

    doc     = fitz.open(stream=pdf_bytes, filetype="pdf")
    idxs    = sorted({0, len(doc) - 1}) if len(doc) > 1 else [0]
    images  = []
    for i in idxs:
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), colorspace=fitz.csRGB)
        images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    doc.close()
    return images


# ── Decodificadores QR (uno por librería) ────────────────────────────────────

def _dec_zxingcpp(images: list) -> list[str]:
    """zxingcpp — pure Python wheel, sin deps de sistema."""
    import zxingcpp
    import numpy as np
    texts = []
    for img in images:
        try:
            results = zxingcpp.read_barcodes(np.array(img))
            texts.extend(r.text for r in results if r.text)
        except Exception as exc:
            log.debug("zxingcpp: %s", exc)
    return texts


def _dec_pyzbar(images: list) -> list[str]:
    """pyzbar — requiere libzbar0 en el sistema operativo."""
    from pyzbar.pyzbar import decode
    texts = []
    for img in images:
        try:
            texts.extend(
                c.data.decode("utf-8", errors="replace")
                for c in decode(img) if c.data
            )
        except Exception as exc:
            log.debug("pyzbar: %s", exc)
    return texts


def _dec_cv2(images: list) -> list[str]:
    """OpenCV QRCodeDetector — opencv-python-headless."""
    import cv2
    import numpy as np
    det   = cv2.QRCodeDetector()
    texts = []
    for img in images:
        try:
            arr  = np.array(img)
            bgr  = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            data, _, _ = det.detectAndDecode(bgr)
            if data:
                texts.append(data)
            # Second pass con escala de grises (mejora contraste bajo)
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            d2, _, _ = det.detectAndDecode(gray)
            if d2 and d2 != data:
                texts.append(d2)
        except Exception as exc:
            log.debug("cv2: %s", exc)
    return texts


def _dec_pdfplumber_text(pdf_bytes: bytes) -> list[str]:
    """
    Fallback sin imagen: busca la URL del QR en texto seleccionable del PDF.
    Útil para PDFs digitales donde la URL del QR es texto extraíble.
    """
    import io
    import pdfplumber
    texts = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = pdf.pages
            idxs  = sorted({0, len(pages) - 1}) if len(pages) > 1 else [0]
            for i in idxs:
                raw = pages[i].extract_text() or ""
                for line in raw.splitlines():
                    lo = line.lower()
                    if "factura.gob.sv" in lo or "codgen" in lo or "codigogeneracion" in lo:
                        texts.append(line.strip())
    except Exception as exc:
        log.debug("pdfplumber QR text: %s", exc)
    return texts


# ── Función pública ───────────────────────────────────────────────────────────

def extraer_datos_qr(pdf_bytes: bytes) -> dict:
    """
    Extrae UUID y número de control del código QR incrustado en el DTE.

    Cascada de 4 estrategias (cada una aislada con try/except):
      1. fitz + zxingcpp  (pure Python, preferido)
      2. fitz + pyzbar
      3. fitz + cv2
      4. Regex en texto pdfplumber (sin imagen)

    Returns:
      {"codigo_generacion": "XXXX-...", "num_control": "DTE-...", ...}
      {} si no se encontró QR o ninguna librería está disponible.
    """
    if not pdf_bytes or len(pdf_bytes) < 512:
        return {}

    # Diagnóstico por método — antes cada fallo intermedio se tragaba con
    # log.debug(), invisible con el nivel INFO configurado en main.py, así
    # que un lote con muchos QR sin leer no dejaba ningún rastro de POR QUÉ
    # (¿falta una librería? ¿el decoder no encontró nada? ¿el PDF→imagen
    # falló?). Se arma un resumen y se loguea como WARNING solo si al final
    # no se encontró nada — para no ensuciar el log en el caso normal (OK).
    _diag: dict[str, str] = {}

    # Convertir a imágenes (solo falla si fitz/PIL no están instalados)
    images: list = []
    try:
        images = _pdf_to_pil_images(pdf_bytes)
    except ImportError as exc:
        _diag["pdf_a_imagen"] = f"fitz/PIL no disponible: {exc}"
    except Exception as exc:
        _diag["pdf_a_imagen"] = f"error: {exc}"
        log.warning("QR: PDF→imagen: %s", exc)

    # Decodificar QR en cascada
    qr_texts: list[str] = []
    if images:
        for fn, name in [(_dec_zxingcpp, "zxingcpp"), (_dec_pyzbar, "pyzbar"), (_dec_cv2, "cv2")]:
            if qr_texts:
                break
            try:
                qr_texts = fn(images)
                if not qr_texts:
                    _diag[name] = "sin resultados"
            except ImportError as exc:
                _diag[name] = f"no disponible: {exc}"
            except Exception as exc:
                _diag[name] = f"error: {exc}"
    elif "pdf_a_imagen" not in _diag:
        _diag["imagenes"] = "PDF→imagen no produjo páginas"

    # Fallback texto (sin imagen)
    if not qr_texts:
        try:
            qr_texts = _dec_pdfplumber_text(pdf_bytes)
            if not qr_texts:
                _diag["texto"] = "sin URL de QR en el texto del PDF"
        except ImportError as exc:
            _diag["texto"] = f"no disponible: {exc}"

    # Parsear y devolver el primero que tenga UUID válido
    for text in qr_texts:
        parsed = _parse_qr_text(text)
        if parsed.get("codigo_generacion"):
            log.info("QR OK: %s…", parsed["codigo_generacion"][:13])
            return parsed

    log.warning("QR: no se encontró código válido — %s", _diag or "sin datos de diagnóstico")
    return {}
