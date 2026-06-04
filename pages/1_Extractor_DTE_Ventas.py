import functools
import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import json
import os
import gc
import sys
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from styles import DARK_PRO_CSS
from utils.concurrent_processor import leer_archivos_uploaded, leer_y_procesar_lote, procesar_json_nativo_ventas
from utils.pdf_utils import (
    safe_str as _safe_str,
    safe_extract_text as _safe_extract_text,
    normalizar_unicode,
    limpiar_monto as _limpiar_monto,
    limpiar_numero as _limpiar_numero,
    extraer_y_formatear_fecha as _extraer_fecha,
    extraer_texto_pdf,
    extraer_nombre_receptor_columna,
)
from utils.constants import SK, TIPOS_CONTRIBUYENTES, TIPOS_CONSUMIDOR, TODOS_TIPOS_VALIDOS, MAX_VALORES_LOOP_VENTAS
from utils.ai_utils import (
    gemini_disponible,
    gemini_ultimo_error,
    procesar_dte_con_gemini,
    es_nombre_sospechoso,
)
from utils.training_examples import registrar_correccion
from utils.gemini_vision import (
    extraer_dte_con_vision,
    vision_disponible,
    vision_ultimo_error,
)
from utils.qa_utils import (
    campos_invalidos_dte,
    mostrar_banner_qa,
    mostrar_indicador_vision,
    requiere_revision_manual,
    validar_montos_ventas,
    calcular_estatus_venta,
    razones_revisar_venta,
    validar_periodo_ventas,
)
from utils.qr_reader import extraer_datos_qr as _extraer_qr

# ─────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Extractor DTE · Ventas", layout="wide", page_icon="📈")

# ─────────────────────────────────────────────
# 2. ESTILOS
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. SEGURIDAD — Multi-tenant SaaS
# ─────────────────────────────────────────────
from utils.auth_guard import check_auth
from components.gmail_import import render_gmail_import
check_auth()

if not st.session_state.get("cliente_activo"):
    st.warning("Debes seleccionar un Cliente Activo en el Dashboard.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. CONSTANTES
# ─────────────────────────────────────────────
MAX_VALORES_LOOP = MAX_VALORES_LOOP_VENTAS

PALABRAS_BASURA_NOMBRE = [
    "DOCUMENTO", "TRIBUTARIO", "ELECTRONICO", "ELECTRÓNICO",
    "REPRESENTACIÓN", "REPRESENTACION", "EMISOR", "FACTURA",
    "CONSUMIDOR", "COMPROBANTE", "CODIGO", "CÓDIGO", "SELLO",
    "VERSION", "VERSIÓN", "TRANSMISION", "TRANSMISIÓN",
    "MINISTERIO", "HACIENDA", "MUNICIPIO", "ACTIVIDAD",
    "ECONOMICA", "AGENCIA", "EFECTIVO", "HORA", "EMISIÓN",
    "EMISION", "GENERACIÓN", "GENERACION", "TELÉFONO",
    "TELEFONO", "TIPO ESTABLECIMIENTO", "ESTABLECIMIENTO",
    "CASA MATRIZ", "SUCURSAL:", "NIT:", "NRC:",
    "NUMERO DE CONTROL", "NÚMERO DE CONTROL",
    "MODELO DE FACTURACION", "TIPO DE TRANSMISION",
]
BASURA_ESTRICTA = ["@", "EMAIL", "CORREO", ".COM", "WWW.", "HTTP"]
PREFIJOS_DIRECCION = (
    "KM ", "KM.", "AV.", "AV ", "AVENIDA", "CALLE ", "PASAJE",
    "COLONIA", "COL.", "COL ", "URB.", "URB ", "URBANIZACION",
    "URBANIZACIÓN", "RESIDENCIAL", "LOTIFICACION", "BARRIO",
    "CANTON", "CANTÓN", "CARRETERA", "CARR.", "BULEVAR",
    "BOULEVARD", "BLVD", "POLIGONO", "POLÍGONO", "LOCAL ",
    "NIVEL ", "PISO ", "EDIFICIO", "CENTRO COMERCIAL",
    "COMPLEJO", "PARQUE INDUSTRIAL", "FINAL ", "ENTRE ", "#",
    "BLVD ", "BLVD.",
)
NOMBRES_INVALIDOS = {
    "MATRIZ", "LOCAL", "SUCURSAL", "AGENCIA", "OFICINA",
    "ESTABLECIMIENTO", "PUNTO DE VENTA", "TIENDA", "ALMACEN",
    "ALMACÉN", "BODEGA", "CONTRIBUYENTE", "DATOS", "RECEPTOR",
    "CLIENTE", "ADQUIRIENTE",
}
CORTE_NOMBRE = re.compile(
    r"\s*(?:NIT|NRC|GIRO|ACTIVIDAD|DIRECCI[OÓ]N|CORREO|TEL[EÉ]F|FONO|"
    r"TIPO\s+ESTAB|MUNICIPIO|DEPARTAMENTO|NUMERO\s+DE\s+CONTROL|"
    r"MODELO\s+DE|TIPO\s+DE\s+TRANS|N\.?\s*I\.?\s*T\.?\s*[:\s]|"
    r"N\.?\s*R\.?\s*C\.?\s*[:\s]|\d{4}[\s\-]\d{6})"
    r".*$",
    re.I | re.S
)

# ─────────────────────────────────────────────
# 5. UTILIDADES SEGURAS
# ─────────────────────────────────────────────
# Delegadas a utils.pdf_utils
safe_str                  = _safe_str
safe_extract_text         = _safe_extract_text
limpiar_monto             = _limpiar_monto
extraer_y_formatear_fecha = _extraer_fecha

def es_linea_direccion(texto: str) -> bool:
    L = safe_str(texto).upper().strip()
    return any(L.startswith(p) or (f" {p}" in L[:50]) for p in PREFIJOS_DIRECCION)


# ─────────────────────────────────────────────
# 6. FUNCIONES AUXILIARES
# ─────────────────────────────────────────────
def cargar_clientes_json() -> dict:
    """Carga los clientes desde almacenamiento local y los retorna como dict{nit: {...}}."""
    try:
        from utils.local_db import cargar_clientes_db
        lista = cargar_clientes_db()
        return {
            c["nit"]: {
                "nombre":    c.get("nombre_comercial", ""),
                "nrc":       c.get("nrc", ""),
                "dui":       c.get("dui", ""),
                "actividad": c.get("actividad", ""),
            }
            for c in lista
        }
    except Exception:
        return {}

def guardar_cliente_rapido(nit: str, nombre: str) -> None:
    """Registra o actualiza un cliente en el almacenamiento local."""
    if not nit or not safe_str(nombre).strip():
        return
    try:
        from utils.local_db import guardar_cliente_db
        guardar_cliente_db(nit=nit, nombre=safe_str(nombre).strip())
    except Exception:
        pass

def actualizar_nombre_en_db_ventas(nit: str, nombre: str) -> None:
    if not nit or not safe_str(nombre).strip():
        return
    df = st.session_state.get("db_ventas", pd.DataFrame())
    if df.empty or "nit_cli" not in df.columns:
        return
    mask = df["nit_cli"] == nit
    if mask.any():
        st.session_state.db_ventas.loc[mask, "nom_cli"] = safe_str(nombre).strip().upper()



# ══════════════════════════════════════════════════════════════
# EXTRACCIÓN DE NOMBRE DEL RECEPTOR/CLIENTE
# ══════════════════════════════════════════════════════════════
def extraer_nombre_receptor(texto_completo: str, pos_nit: int, cliente_activo: dict) -> str:
    texto_completo = safe_str(texto_completo)
    nombre_emisor = safe_str(cliente_activo.get('nombre', '')).strip().upper()

    def limpiar(s: str) -> str:
        try:
            s = safe_str(s)
            if nombre_emisor and len(nombre_emisor) > 3:
                s = re.compile(re.escape(nombre_emisor), re.I).sub("", s)
            s = re.split(r"(?i)(?:NOMBRE\s+O\s+RAZ[OÓ]N\s+SOCIAL|RAZ[OÓ]N\s+SOCIAL|CLIENTE)\s*[:\-]*\s*", s)[-1]
            s = re.sub(
                r"^[\s\-:]*(?:NOMBRE(?:\s+O\s+RAZ[OÓ]N\s+SOCIAL)?|"
                r"NOMBRE\s+COMERCIAL|RECEPTOR|ADQUIRIENTE|DATOS\s+DEL\s+RECEPTOR|"
                r"DATOS\s+DEL\s+ADQUIRIENTE|NOMBRE\s+DEL\s+CLIENTE|"
                r"CONTRIBUYENTE\s+RECEPTOR)[\s:]*",
                s, flags=re.I
            ).strip()
            s = CORTE_NOMBRE.sub("", s).strip()
            s = re.sub(r"^[-_.,;:\s]+|[-_.,;:\s]+$", "", s)
            s = re.sub(r'\s{2,}', ' ', s)
            return s.upper()
        except Exception:
            return ""

    def valido(s: str) -> bool:
        try:
            T = safe_str(s).strip().upper()
            if len(T) < 3 or len(T) > 100:
                return False
            if nombre_emisor and (T == nombre_emisor or T.startswith(nombre_emisor[:15])):
                return False
            if any(b in T for b in BASURA_ESTRICTA):
                return False
            if es_linea_direccion(T):
                return False
            for b in PALABRAS_BASURA_NOMBRE:
                if b in T and len(b) > 5:
                    return False
            if T in NOMBRES_INVALIDOS:
                return False
            digitos = sum(c.isdigit() for c in T)
            if len(T) > 0 and digitos / len(T) > 0.45:
                return False
            if re.fullmatch(r'[\d\s\-\.\/]+', T):
                return False
            if not re.search(r'[A-ZÁÉÍÓÚÑÜ]', T):
                return False
            # Red de seguridad: rechazar metadata fiscal (MODELO FACTURACIÓN, etc.)
            if es_nombre_sospechoso(T):
                return False
            return True
        except Exception:
            return False

    try:
        inicio  = max(0, pos_nit - 600)
        fin     = min(len(texto_completo), pos_nit + 1500)
        ventana = texto_completo[inicio:fin]

        partes_rec = re.split(r"(?i)\bRECEPTOR\b", ventana, maxsplit=1)
        ventana_receptor = partes_rec[1] if len(partes_rec) > 1 else ventana

        patron_etq = re.compile(
            r"(?:Nombre(?:\s+[Oo]\s+[Rr]az[oó]n\s+[Ss]ocial)?|"
            r"[Rr]az[oó]n\s+[Ss]ocial|Nombre\s+[Cc]omercial|"
            r"Nombre\s+[Dd]el\s+[Cc]liente|Nombre\s+[Dd]el\s+[Rr]eceptor|"
            r"Nombre\s+[Dd]el\s+[Aa]dquiriente|[Aa]dquiriente|[Rr]eceptor)"
            r"\s*[:\s]+\s*([^\n]{3,90}(?:\n[^\n]{3,60})?)",
            re.I
        )
        for m_etq in patron_etq.finditer(ventana_receptor):
            raw_cap = safe_str(m_etq.group(1))
            lineas_cap = raw_cap.split('\n')
            candidato  = limpiar(lineas_cap[0])
            if len(candidato) < 4 and len(lineas_cap) > 1:
                candidato = limpiar(lineas_cap[0] + " " + lineas_cap[1])
            if valido(candidato):
                return candidato

        ventana_despues = texto_completo[pos_nit:fin]
        lineas_despues  = [ln.strip() for ln in ventana_despues.split('\n') if ln.strip()]
        for linea in lineas_despues[:15]:
            candidato = limpiar(linea)
            if valido(candidato):
                return candidato

        ventana_antes = texto_completo[inicio:pos_nit]
        lineas_antes  = [ln.strip() for ln in ventana_antes.split('\n') if ln.strip()]
        for linea in reversed(lineas_antes[-15:]):
            candidato = limpiar(linea)
            if valido(candidato):
                return candidato

        m_sec = re.search(
            r"(?i)(?:DATOS\s+DEL\s+(?:RECEPTOR|ADQUIRIENTE|CLIENTE)|"
            r"RECEPTOR\s*[:\-]|ADQUIRIENTE\s*[:\-]|CLIENTE\s*:)"
            r"(.{10,800}?)(?:DESCRIPCI[OÓ]N|DETALLE|CANT\.|CANTIDAD|"
            r"PRECIO|COD\.|ARTICULO|ITEM\b|\n\s*\n)",
            texto_completo, re.S | re.I
        )
        if m_sec:
            seccion = safe_str(m_sec.group(1))
            for linea in seccion.split('\n'):
                candidato = limpiar(linea.strip())
                if valido(candidato):
                    return candidato

    except Exception:
        pass
    return ""


# ══════════════════════════════════════════════════════════════
# EXTRACTOR PRINCIPAL DE VENTAS
# Maneja DTE-01 (Factura), DTE-03 (CCF), DTE-05 (NC), DTE-06 (ND)
# ══════════════════════════════════════════════════════════════
def extraer_venta_nativo_pro(file_bytes: bytes, cliente_activo: dict, clientes_db: dict = None) -> dict:
    """
    Extrae datos de un DTE PDF de ventas.
    
    Retorna dict con:
      - tipo: '01', '03', '05', '06'
      - anexo: '1' (contribuyentes: 03,05,06) o '2' (consumidor: 01,02,10,11)
      - Para tipo 03/05/06: nit_cli, dui_cli, nom_cli (datos del receptor)
      - Para tipo 01: dui_cli (DUI del consumidor, NIT vacío según manual)
      - sello: sello de recepción (40 chars)
      - gen: UUID/código de generación
      - num_control: número de control DTE sin guiones
    """
    if not file_bytes or len(file_bytes) < 512:
        return {"error_fatal": "Archivo vacio o demasiado pequeño."}

    # ── Vision-First: extraer con IA antes de pdfplumber ─────────────────────
    _nit_emisor_ctx = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nit', '')))
    _nom_emisor_ctx = safe_str(cliente_activo.get('nombre', '')).strip().upper()

    gemini_correcciones: list[str] = []
    _vision_campos: dict  = {}
    _vision_alertas: list = []
    _vision_audit: dict   = {}

    if vision_disponible():
        _vision_campos, _vision_alertas, _vision_audit = extraer_dte_con_vision(
            file_bytes,
            "ventas",
            {"nit": _nit_emisor_ctx, "nombre": _nom_emisor_ctx},
        )
        gemini_correcciones = [
            f"Vision: {a}" for a in _vision_alertas
        ] if _vision_alertas else (
            [f"Vision extrajo {len(_vision_campos)} campo(s)"]
            if _vision_campos else []
        )

    try:
        try:
            texto_lineal, texto_visual = extraer_texto_pdf(file_bytes)
        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
            if not _vision_campos.get("num_control"):
                return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
            texto_lineal = texto_visual = ""
        except Exception as e:
            if "password" in str(e).lower() or "encrypt" in str(e).lower():
                return {"error_fatal": "PDF protegido con contraseña. Desbloquéalo antes de subir."}
            raise

        texto_completo = texto_lineal + "\n" + texto_visual

        if len(texto_completo.strip()) < 50 and not _vision_campos.get("num_control"):
            return {"error_fatal": "PDF de imagen sin texto extraible. Usa OCR."}

        t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
        t_no_sp = re.sub(r'\s+', '', t_clean).upper()

        # ── Número de Control DTE ─────────────────────────────────────────────
        tipo        = ""
        ctrl        = ""
        num_control = ""

        m_ctrl = re.search(
            r"\b(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})\b",
            t_clean, re.I
        )
        if not m_ctrl:
            m_ctrl = re.search(
                r"(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})(?=[^0-9]|$)",
                t_no_sp
            )

        if m_ctrl:
            ctrl        = m_ctrl.group(1).upper()
            tipo        = m_ctrl.group(2) if m_ctrl.lastindex >= 2 else ""
            # Si el match fue en t_no_sp, grupo 2 no existe, extraer del ctrl
            if not tipo:
                m_tipo_aux = re.search(r"DTE-(\d{2})", ctrl)
                tipo = m_tipo_aux.group(1) if m_tipo_aux else ""
            # Número de control sin guiones (para columna D del anexo)
            num_control = ctrl.replace("-", "")

        if not ctrl:
            return {"error_tipo": "No se detecto un Numero de Control DTE valido."}

        # ── Validar tipo de documento ──────────────────────────────────────────
        if tipo not in TODOS_TIPOS_VALIDOS:
            return {"error_tipo": f"Documento DTE-{tipo}. Solo se admiten: {', '.join(sorted(TODOS_TIPOS_VALIDOS))}."}

        # Determinar a qué anexo pertenece
        if tipo in TIPOS_CONTRIBUYENTES:
            anexo = "1"  # Ventas a Contribuyentes
        else:
            anexo = "2"  # Ventas a Consumidor Final

        # ── Sello de Recepción (40 chars alfanuméricos, empieza con año) ───────
        # NOTA: NO se busca en t_no_sp (sin espacios) porque ahí el sello queda
        # pegado al texto vecino y los bordes \b fallan (el carácter contiguo es
        # alfanumérico). Se busca en t_clean, que conserva los saltos de línea.
        sello = ""
        # 1) Anclado a la etiqueta (layout en línea: "Sello de Recepción: XXXX")
        m_sello = re.search(
            r"Sello\s+de\s+Recepci[oó]n\s*:?\s*([A-Z0-9]{36,44})",
            t_clean, re.I
        )
        if m_sello:
            sello = m_sello.group(1).upper()
        # 2) Token con prefijo de año delimitado por no-alfanuméricos
        #    (layout apilado: etiquetas y luego valores en líneas separadas)
        if not sello:
            m_sello2 = re.search(
                r"(?<![A-Z0-9])(20[2-3]\d[A-Z0-9]{36})(?![A-Z0-9])",
                t_clean.upper()
            )
            if m_sello2:
                sello = m_sello2.group(1)
        # 3) Último recurso: cualquier cadena de 40 alfanuméricos aislada
        if not sello:
            m_sello3 = re.search(
                r"(?<![A-Z0-9])([A-Z0-9]{40})(?![A-Z0-9])",
                t_clean.upper()
            )
            if m_sello3:
                sello = m_sello3.group(1)

        # ── Código de Generación / UUID ────────────────────────────────────────
        gen = ""
        m_gen_etq = re.search(
            r"C[oó]digo\s+de\s+Generaci[oó]n\s*:\s*"
            r"([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})",
            t_clean, re.I
        )
        if m_gen_etq:
            gen = safe_str(m_gen_etq.group(1)).upper()

        if not gen:
            m_url = re.search(r"CODGEN=([A-F0-9\-]{36})", t_no_sp)
            if m_url:
                gen = safe_str(m_url.group(1)).upper()

        if not gen:
            m_uuid = re.search(
                r"([A-Fa-f0-9]{8}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{12})",
                t_no_sp
            )
            if m_uuid:
                raw = safe_str(m_uuid.group(1)).replace("-", "")
                if len(raw) == 32:
                    gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}".upper()

        # Gen sin guiones para columna F del anexo
        gen_sin_guiones = gen.replace("-", "")

        # ── Fecha ──────────────────────────────────────────────────────────────
        fecha = extraer_y_formatear_fecha(t_clean)

        # ── Exclusiones del emisor ─────────────────────────────────────────────
        nit_emisor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nit', '')))
        dui_emisor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('dui', '')))
        nrc_emisor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nrc', '')))
        excluir_numeros = {nit_emisor, dui_emisor, nrc_emisor} - {""}

        # ── Datos del Receptor ─────────────────────────────────────────────────
        nit_cli     = ""
        dui_cli     = ""
        nom_cli     = "SIN NOMBRE"
        es_nuevo    = True
        pos_nit_rec = -1
        if clientes_db is None:
            clientes_db = cargar_clientes_json()

        # Separar sección del receptor del texto
        partes_doc = re.split(
            r"(?i)\b(?:DATOS\s+DEL\s+RECEPTOR|RECEPTOR\s*[:\-]|"
            r"DATOS\s+DEL\s+ADQUIRIENTE|ADQUIRIENTE\s*[:\-]|"
            r"DATOS\s+DEL\s+CLIENTE|CLIENTE\s*:|COMPRADOR\b)\b",
            texto_completo, maxsplit=1
        )

        texto_receptor  = ""
        offset_receptor = 0

        if len(partes_doc) >= 2:
            texto_receptor_raw = partes_doc[1]
            corte_det = re.search(
                r"(?i)(?:DESCRIPCI[OÓ]N|CANT\.|CANTIDAD|PRECIO|COD\.|"
                r"ARTICULO|ITEM\b|DETALLE\b|\n\s*\n)",
                texto_receptor_raw
            )
            texto_receptor = texto_receptor_raw[:corte_det.start()] if corte_det else texto_receptor_raw[:1500]
            offset_receptor = texto_completo.find(texto_receptor[:50])
            if offset_receptor == -1:
                offset_receptor = len(partes_doc[0])
        else:
            m_rec_lineal = re.search(r"(?i)\bRECEPTOR\b", texto_lineal)
            if m_rec_lineal:
                texto_receptor = texto_lineal[m_rec_lineal.start():][:1500]
                offset_receptor = texto_completo.find(texto_receptor[:50])
            else:
                offset_receptor = len(texto_completo) // 2
                texto_receptor = texto_completo[offset_receptor:][:1500]

        # ── Buscar NIT (14 dígitos) o DUI (9 dígitos) del receptor ────────────
        patron_universal = re.compile(
            r"\b(?:\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d"  # NIT con separadores
            r"|\d{14}"                                          # NIT sin separadores
            r"|\d{8}[\s\-]?\d"                                 # DUI con separador
            r"|\d{9})\b"                                       # DUI sin separadores
        )

        candidatos_validos = []
        for match in patron_universal.finditer(texto_completo):
            num_limpio = re.sub(r'[^0-9]', '', match.group(0))
            if num_limpio not in excluir_numeros and len(num_limpio) in (9, 14):
                candidatos_validos.append((num_limpio, match.start()))

        cands_en_receptor = [
            c for c in candidatos_validos
            if offset_receptor <= c[1] <= (offset_receptor + len(texto_receptor) + 200)
        ]

        if cands_en_receptor:
            nit_cli, pos_nit_rec = cands_en_receptor[0]
        elif candidatos_validos:
            nit_cli, pos_nit_rec = candidatos_validos[0]

        # ── Para DTE-01 (consumidor final): si es DUI (9 dígitos) ─────────────
        # Según manual F-07 V14: si completa DUI, campo NIT debe quedar VACÍO
        if len(nit_cli) == 9:
            dui_cli = nit_cli
            if tipo in TIPOS_CONSUMIDOR:
                # Para consumidor final: NIT vacío, solo DUI
                nit_cli = ""
            # Para contribuyentes con DUI: también guardar en dui_cli
        elif len(nit_cli) == 14:
            dui_cli = ""  # Es NIT, no DUI

        # ── Buscar nombre del receptor ─────────────────────────────────────────
        id_busqueda = dui_cli if (tipo in TIPOS_CONSUMIDOR and dui_cli) else nit_cli
        if id_busqueda and id_busqueda in clientes_db:
            nom_cli  = safe_str(clientes_db[id_busqueda].get("nombre", "SIN NOMBRE"))
            es_nuevo = False
        elif nit_cli and nit_cli in clientes_db:
            nom_cli  = safe_str(clientes_db[nit_cli].get("nombre", "SIN NOMBRE"))
            es_nuevo = False

        if es_nuevo:
            # Fuente primaria: extracción por columnas (robusta ante el
            # entrelazado de caracteres que produce pdfplumber cuando los
            # nombres de EMISOR y RECEPTOR comparten la misma línea).
            nombre_encontrado = ""
            try:
                nom_col = extraer_nombre_receptor_columna(file_bytes)
            except Exception:
                nom_col = ""
            if nom_col:
                nc = nom_col.strip().upper()
                # Descartar si coincide con el emisor o es claramente inválido
                mismo_emisor = bool(
                    _nom_emisor_ctx and (
                        nc == _nom_emisor_ctx or nc.startswith(_nom_emisor_ctx[:15])
                    )
                )
                if (4 <= len(nc) <= 100 and re.search(r"[A-ZÁÉÍÓÚÑÜ]", nc)
                        and not mismo_emisor and not es_nombre_sospechoso(nc)):
                    nombre_encontrado = nc

            # Respaldo: heurística textual sobre el texto lineal/visual
            pos_busqueda = pos_nit_rec if pos_nit_rec >= 0 else len(texto_completo) // 2
            if not nombre_encontrado:
                nombre_encontrado = extraer_nombre_receptor(
                    texto_completo, pos_busqueda, cliente_activo
                )
            if not nombre_encontrado and texto_visual.strip():
                pos_vis = pos_nit_rec
                if pos_vis < 0:
                    m_crudo = re.search(
                        re.escape((dui_cli or nit_cli)[:8]) if (dui_cli or nit_cli) else "RECEPTOR",
                        texto_visual
                    )
                    pos_vis = m_crudo.start() if m_crudo else len(texto_visual) // 2
                nombre_encontrado = extraer_nombre_receptor(
                    texto_visual, pos_vis, cliente_activo
                )
            nom_cli = nombre_encontrado if nombre_encontrado else "SIN NOMBRE"

        # ── Aplicar Vision con prioridad sobre regex ──────────────────────────
        if _vision_campos.get("fecha"):
            fecha   = _vision_campos["fecha"]
        if _vision_campos.get("nom_cli"):
            nom_cli = _vision_campos["nom_cli"]
        if _vision_campos.get("nit_cli"):
            nit_cli = _vision_campos["nit_cli"]
        if _vision_campos.get("dui_cli"):
            dui_cli = _vision_campos["dui_cli"]

        if not _vision_campos and gemini_disponible():
            # Fallback textual solo cuando Vision no está disponible
            _campos_act = {
                "fecha"  : fecha,
                "nom_cli": nom_cli,
                "nit_cli": nit_cli,
                "dui_cli": dui_cli,
            }
            _texto_ia = (texto_visual + "\n\n" + texto_lineal) if texto_visual else texto_lineal
            _corr_dict, gemini_correcciones = procesar_dte_con_gemini(
                _texto_ia,
                "ventas",
                _campos_act,
                {"nit": _nit_emisor_ctx, "nombre": _nom_emisor_ctx},
            )
            if _corr_dict.get("fecha"):
                fecha   = _corr_dict["fecha"]
            if _corr_dict.get("nom_cli"):
                nom_cli = _corr_dict["nom_cli"]
            if _corr_dict.get("nit_cli"):
                nit_cli = _corr_dict["nit_cli"]
            if _corr_dict.get("dui_cli"):
                dui_cli = _corr_dict["dui_cli"]

        # ── Montos ────────────────────────────────────────────────────────────
        exentas    = 0.0
        no_sujetas = 0.0
        gravadas   = 0.0
        debito     = 0.0
        terceros   = 0.0
        deb_terc   = 0.0
        total      = 0.0
        iva_calc   = False

        m_exe = re.search(
            r"(?:Ventas?\s+Exentas?|Total\s+Exento|Exentas?)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_exe:
            exentas = limpiar_monto(m_exe.group(1))

        m_ns = re.search(
            r"(?:No\s+Sujetas?|Ventas?\s+No\s+Sujetas?)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_ns:
            no_sujetas = limpiar_monto(m_ns.group(1))

        # Total a pagar (varios patrones por orden de prioridad)
        for pat in [
            r"(?:TOTAL\s+A\s+PAGAR)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:MONTO\s+TOTAL\s+DE\s+LA\s+OPERACI[OÓ]N)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:TOTAL\s+A\s+PAGAR|TOTAL\s+PAGAR|MONTO\s+TOTAL)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:TOTAL\s+OPERACI[OÓ]N|VENTA\s+TOTAL|TOTAL\s*\$)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:VALOR\s+TOTAL|TOTAL\s+FACTURA)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
        ]:
            m_tot = re.search(pat, t_clean, re.I)
            if m_tot:
                total = limpiar_monto(m_tot.group(1))
                if total > 0:
                    break

        # Débito fiscal / IVA
        for pat in [
            r"(?:D[EÉ]BITO\s+FISCAL|Débito\s+Fiscal|Debito\s+Fiscal)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:Impuesto\s+al\s+Valor\s+Agregado\s*(?:13\s*%)?)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"(?:IVA\s*13\s*%|13\s*%\s*IVA|I\.V\.A\.?)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
        ]:
            m_iva = re.search(pat, t_clean, re.I)
            if m_iva:
                debito = limpiar_monto(m_iva.group(1))
                if debito > 0:
                    break

        # Ventas gravadas
        _PATS_GRAVADAS = [
            r"Ventas?\s+Gravadas?\s+Locales?[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"Subtotal\s+Gravado[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"Ventas?\s+Gravadas?[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"Monto\s+Sujeto\s+a\s+(?:IVA|Gravar)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"Ventas?\s+Netas?[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"Base\s+Imponible[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"Monto\s+Gravado[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            r"Total\s+Operacion(?:es)?[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
        ]
        for _pg in _PATS_GRAVADAS:
            m_grav = re.search(_pg, t_clean, re.I)
            if m_grav:
                gravadas = limpiar_monto(m_grav.group(1))
                if gravadas > 0:
                    break

        # Para DTE-01 (factura consumidor): gravadas incluyen IVA (campo N del anexo)
        # El total incluye IVA, las gravadas se reportan CON IVA incluido
        if tipo in TIPOS_CONSUMIDOR and gravadas == 0.0 and total > 0:
            # Para facturas consumidor: total = gravadas (con IVA incluido)
            gravadas = total
            debito   = 0.0  # El anexo 2 no pide débito fiscal separado

        if tipo in TIPOS_CONTRIBUYENTES:
            # Para CCF: calcular gravadas sin IVA si no se encontraron
            if gravadas == 0.0 and total > 0 and debito > 0:
                gravadas = round(total - debito - exentas - no_sujetas, 2)

            if gravadas == 0.0:
                m_sub = re.search(
                    r"Sub[\s\-]?Total\s*:\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                    t_clean, re.I
                )
                if m_sub:
                    gravadas = limpiar_monto(m_sub.group(1))

            encontrado = total > 0 and debito > 0 and gravadas > 0

            if not encontrado:
                # Algoritmo O(n²) con índice de IVA (igual que Compras)
                montos_raw = re.findall(
                    r'(?<![A-Z\-])(\d{1,3}(?:[,\.]\d{3})*[,\.]\d{2}|\d+\.\d{2}|\d+,\d{2})',
                    t_clean,
                )
                set_montos: set = set()
                for rv in montos_raw:
                    v = limpiar_monto(rv)
                    if 0.01 < v < 1_000_000:
                        set_montos.add(round(v, 2))
                valores = sorted(list(set_montos), reverse=True)[:MAX_VALORES_LOOP]
                set_valores = set(valores)

                for vg in valores:
                    vi_esperado = round(vg * 0.13, 2)
                    for delta in [0, 0.01, -0.01, 0.02, -0.02]:
                        vi_cand = round(vi_esperado + delta, 2)
                        if vi_cand not in set_valores:
                            continue
                        vt_cand = round(vg + vi_cand + exentas + no_sujetas, 2)
                        for vt in valores:
                            if abs(vt - vt_cand) <= 0.10 and vt > vg:
                                gravadas   = vg
                                debito     = vi_cand
                                total      = vt
                                encontrado = True
                                break
                        if encontrado:
                            break
                    if encontrado:
                        break

            if not encontrado:
                if total > 0 and debito > 0 and gravadas == 0.0:
                    gravadas   = round(total - debito - exentas - no_sujetas, 2)
                    encontrado = True
                elif total > 0 and debito == 0.0 and gravadas == 0.0:
                    # CCF sin IVA detectado: calcular
                    gravadas  = round((total - exentas - no_sujetas) / 1.13, 2)
                    debito    = round(total - exentas - no_sujetas - gravadas, 2)
                    iva_calc  = True
                    encontrado = True
                elif total == 0.0 and gravadas > 0 and debito > 0:
                    total = round(gravadas + debito + exentas + no_sujetas, 2)

        # ── Completar campos desde Vision cuando regex obtuvo vacío/0 ─────────
        if _vision_campos:
            if _vision_campos.get("gravadas") and gravadas == 0.0:
                gravadas = round(float(_vision_campos["gravadas"]), 2)
            if _vision_campos.get("iva") and debito == 0.0:
                debito = round(float(_vision_campos["iva"]), 2)
            if _vision_campos.get("total") and total == 0.0:
                total = round(float(_vision_campos["total"]), 2)
            if _vision_campos.get("exentas") and exentas == 0.0:
                exentas = round(float(_vision_campos["exentas"]), 2)
            if _vision_campos.get("no_sujetas") and no_sujetas == 0.0:
                no_sujetas = round(float(_vision_campos["no_sujetas"]), 2)
            # Sello: Vision es la fuente primaria (~40 chars); regex como respaldo
            v_sello = str(_vision_campos.get("sello_recepcion") or "").strip()
            if len(v_sello) >= 30 and len(v_sello) <= 45 and "-" not in v_sello:
                sello = v_sello

        # ── QR ES EL REY: sobreescribe campos con datos confiables del QR ────────
        try:
            _qr = _extraer_qr(file_bytes)
            if _qr.get("codigo_generacion"):
                gen = _qr["codigo_generacion"].upper()
                gen_sin_guiones = gen.replace("-", "")
            if _qr.get("num_control") and not ctrl:
                _qc = _qr["num_control"].upper()
                _mq = re.search(r'DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18}', _qc, re.I)
                if _mq:
                    ctrl        = _qc
                    tipo        = _mq.group(1)
                    num_control = ctrl.replace("-", "")
            # Fecha del QR como respaldo si regex no la encontró
            if not fecha and _qr.get("fecha_qr"):
                _fq = str(_qr["fecha_qr"]).strip()
                _mf = re.match(r'(\d{4})-(\d{2})-(\d{2})', _fq)
                if _mf:
                    fecha = f"{_mf.group(3)}/{_mf.group(2)}/{_mf.group(1)}"
        except Exception:
            pass

        return {
            "fecha"         : fecha,
            "tipo"          : tipo,
            "anexo"         : anexo,
            "num_control"   : num_control,   # Sin guiones
            "num_control_raw": ctrl,          # Con guiones (para mostrar)
            "sello"         : sello,
            "gen"           : gen,            # Con guiones (UUID)
            "gen_sin_guiones": gen_sin_guiones, # Sin guiones
            "nit_cli"       : nit_cli,        # Vacío si consumidor con DUI
            "dui_cli"       : dui_cli,
            "nom_cli"       : nom_cli,
            "exentas"       : round(exentas, 2),
            "no_sujetas"    : round(no_sujetas, 2),
            "gravadas"      : round(gravadas, 2),
            "debito"        : round(debito, 2),
            "terceros"      : round(terceros, 2),
            "deb_terc"      : round(deb_terc, 2),
            "total"         : round(total, 2),
            "estado"              : "OK",
            "iva_calc"            : iva_calc,
            "es_nuevo"            : es_nuevo,
            "gemini_correcciones" : gemini_correcciones,
            "_vision_campos"      : _vision_campos,
            "_vision_alertas"     : _vision_alertas,
            "_vision_audit"       : _vision_audit,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
    except Exception as err:
        return {"error_extraccion": safe_str(err)}


# ══════════════════════════════════════════════════════════════
# CONSTRUCCIÓN DE DATAFRAMES F-07 SEGÚN MANUAL DGII
# ══════════════════════════════════════════════════════════════

def construir_df_f07_contribuyentes(
    df_in: pd.DataFrame,
    tipo_op_renta: str = "1",
    tipo_ingreso_renta: str = "3",
    periodo_ene2025: bool = True,
) -> pd.DataFrame:
    """
    Anexo 1: Detalle de Ventas a Contribuyentes (DTE-03, 05, 06)
    Columnas: A-T (20 columnas según manual F-07 V14 enero 2025)

    D. Número de Resolución = num_control SIN guiones
    E. Número de Serie      = sello de recepción
    F. Número de Documento  = código de generación SIN guiones
    G. Control Interno      = en blanco (DTE)
    H. NIT o NRC            = nit_cli (vacío si persona natural con DUI)
    Q. DUI                  = dui_cli (solo persona natural desde ene 2022)
    R. Tipo Operación Renta = usuario selecciona (0 si periodo < ene 2025)
    S. Tipo Ingreso Renta   = usuario selecciona (0 si periodo < ene 2025)
    T. Número Anexo         = 1
    """
    df_out = pd.DataFrame()
    df_out["A. Fecha Emisión"]            = df_in["fecha"]
    df_out["B. Clase Documento"]          = "4"
    df_out["C. Tipo Documento"]           = df_in["tipo"]
    df_out["D. Num Resolución"]           = df_in["num_control"].astype(str)
    df_out["E. Serie (Sello)"]            = df_in.get("sello", pd.Series([""] * len(df_in), index=df_in.index))
    df_out["F. Num Documento (UUID)"]     = df_in["gen_sin_guiones"].astype(str)
    df_out["G. Control Interno"]          = ""
    df_out["H. NIT/NRC Cliente"]          = df_in["nit_cli"].astype(str)
    df_out["I. Nombre Cliente"]           = df_in["nom_cli"].astype(str)
    df_out["J. Ventas Exentas"]           = df_in["exentas"]
    df_out["K. Ventas No Sujetas"]        = df_in["no_sujetas"]
    df_out["L. Ventas Gravadas"]          = df_in["gravadas"]
    df_out["M. Débito Fiscal"]            = df_in["debito"]
    df_out["N. Vtas Cuenta Terceros"]     = df_in["terceros"]
    df_out["O. Déb. Fiscal Terceros"]     = df_in["deb_terc"]
    df_out["P. Total Ventas"]             = df_in["total"]
    df_out["Q. DUI Cliente"]              = df_in["dui_cli"].astype(str)
    df_out["R. Tipo Operación (Renta)"]   = tipo_op_renta   if periodo_ene2025 else "0"
    df_out["S. Tipo Ingreso (Renta)"]     = tipo_ingreso_renta if periodo_ene2025 else "0"
    df_out["T. Num Anexo"]                = "1"
    return df_out


def construir_df_f07_consumidor(
    df_in: pd.DataFrame,
    tipo_op_renta: str = "1",
    tipo_ingreso_renta: str = "3",
    periodo_ene2025: bool = True,
) -> pd.DataFrame:
    """
    Anexo 2: Detalle de Ventas a Consumidor Final (DTE-01, 02, 10, 11)
    Columnas: A-W (23 columnas según manual F-07 V14 enero 2025)

    Los DTE se exportan individuales; el usuario puede agrupar por día
    manualmente si el portal lo exige (factura.gob.sv lo acepta individual).
    D/E/F/G = N/A para DTE · H/I = UUID DTE (sin guiones) · J = vacío
    N = Ventas Gravadas CON IVA incluido · U/V = 0 si periodo < ene 2025
    W = 2
    """
    df_in = df_in.copy()
    df_out = pd.DataFrame()
    df_out["A. Fecha Emisión"]                  = df_in["fecha"]
    df_out["B. Clase Documento"]                = "4"
    df_out["C. Tipo Documento"]                 = df_in["tipo"]
    df_out["D. Num Resolución"]                 = "N/A"
    df_out["E. Serie Documento"]                = "N/A"
    df_out["F. N° Control Interno DEL"]         = "N/A"
    df_out["G. N° Control Interno AL"]          = "N/A"
    df_out["H. N° Documento DEL (UUID)"]        = df_in["gen_sin_guiones"].astype(str)
    df_out["I. N° Documento AL (UUID)"]         = df_in["gen_sin_guiones"].astype(str)
    df_out["J. N° Máquina Registradora"]        = ""
    df_out["K. Ventas Exentas"]                 = df_in["exentas"]
    df_out["L. Exentas No Prop."]               = 0.0
    df_out["M. Ventas No Sujetas"]              = df_in["no_sujetas"]
    # N: Ventas Gravadas CON IVA incluido (campo 'gravadas' ya lo trae así para consumidor)
    df_out["N. Ventas Gravadas (c/IVA)"]        = df_in["gravadas"]
    df_out["O. Export. dentro CA"]              = 0.0
    df_out["P. Export. fuera CA"]               = 0.0
    df_out["Q. Export. Servicios"]              = 0.0
    df_out["R. Vtas Zonas Francas DPA"]         = 0.0
    df_out["S. Vtas Cuenta Terceros"]           = df_in["terceros"]
    df_out["T. Total Ventas"]                   = df_in["total"]
    df_out["U. Tipo Operación (Renta)"]         = tipo_op_renta    if periodo_ene2025 else "0"
    df_out["V. Tipo Ingreso (Renta)"]           = tipo_ingreso_renta if periodo_ene2025 else "0"
    df_out["W. Num Anexo"]                      = "2"
    return df_out


def construir_df_f07_ventas_combinado(df_in: pd.DataFrame) -> pd.DataFrame:
    """Vista combinada para auditoría interna (no para subir a Hacienda)."""
    df_out = pd.DataFrame()
    df_out["Fecha"]       = df_in["fecha"]
    df_out["Tipo DTE"]    = df_in["tipo"]
    df_out["Anexo"]       = df_in["anexo"]
    df_out["Num Control"] = df_in.get("num_control_raw", df_in["num_control"])
    df_out["Sello"]       = df_in.get("sello", "")
    df_out["UUID"]        = df_in["gen"]
    df_out["NIT/DUI CLI"] = df_in.apply(
        lambda r: r["nit_cli"] if r["nit_cli"] else r["dui_cli"], axis=1
    )
    df_out["Nombre"]      = df_in["nom_cli"]
    df_out["Exentas"]     = df_in["exentas"]
    df_out["No Sujetas"]  = df_in["no_sujetas"]
    df_out["Gravadas"]    = df_in["gravadas"]
    df_out["Débito"]      = df_in["debito"]
    df_out["Total"]       = df_in["total"]
    df_out["Archivo"]     = df_in.get("archivo", "")
    return df_out


# ─────────────────────────────────────────────
# EXPORTAR EXCEL F-07
# ─────────────────────────────────────────────
def _aplicar_formato_numerico(ws, col_inicio: int, col_fin: int):
    """Aplica formato numérico #,##0.00 a columnas de montos."""
    for fila in ws.iter_rows(min_row=1, max_row=ws.max_row,
                              min_col=col_inicio, max_col=col_fin):
        for celda in fila:
            if isinstance(celda.value, (int, float)):
                celda.number_format = '#,##0.00'


def to_excel_hacienda_contribuyentes(df: pd.DataFrame) -> bytes:
    """Genera Excel para Anexo 1 (Contribuyentes) listo para Hacienda."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Ventas_Contribuyentes')
        ws = writer.sheets['Ventas_Contribuyentes']
        # Anchos: A=12, B=3, C=3, D=35, E=45, F=35, G=12, H=16, I=45, J=12, K=12,
        #         L=12, M=12, N=12, O=12, P=14, Q=14, R=4, S=4, T=3
        anchos = [12,3,3,35,45,35,12,16,45,12,12,12,12,12,12,14,14,4,4,3]
        for idx, ancho in enumerate(anchos, 1):
            ws.column_dimensions[ws.cell(1, idx).column_letter].width = ancho
        _aplicar_formato_numerico(ws, 10, 16)  # Columnas J a P
    return output.getvalue()


def to_excel_hacienda_consumidor(df: pd.DataFrame) -> bytes:
    """Genera Excel para Anexo 2 (Consumidor Final) listo para Hacienda."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Ventas_Consumidor')
        ws = writer.sheets['Ventas_Consumidor']
        # Anchos: A=12, B=3, C=3, D=8, E=8, F=8, G=8, H=35, I=35, J=16,
        #         K=12, L=12, M=12, N=14, O=12, P=12, Q=12, R=12, S=12, T=14, U=4, V=4, W=3
        anchos = [12,3,3,8,8,8,8,35,35,16,12,12,12,14,12,12,12,12,12,14,4,4,3]
        for idx, ancho in enumerate(anchos, 1):
            ws.column_dimensions[ws.cell(1, idx).column_letter].width = ancho
        _aplicar_formato_numerico(ws, 11, 20)  # Columnas K a T
    return output.getvalue()


def to_excel_auditoria(df: pd.DataFrame) -> bytes:
    """Genera Excel de auditoría combinado."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Auditoria')
        ws = writer.sheets['Auditoria']
        anchos = [12,8,5,35,42,38,18,45,12,12,12,10,14,35]
        for idx, ancho in enumerate(anchos, 1):
            try:
                ws.column_dimensions[ws.cell(1, idx).column_letter].width = ancho
            except Exception:
                pass
        _aplicar_formato_numerico(ws, 9, 13)
    return output.getvalue()


# ─────────────────────────────────────────────
# DIÁLOGO DE DESCARGA
# ─────────────────────────────────────────────
def _validar_matematica_ventas(df: pd.DataFrame) -> list:
    """Devuelve lista de filas con inconsistencias matemáticas (gravadas+debito≠total)."""
    alertas = []
    for _, row in df.iterrows():
        if row.get('tipo', '') not in TIPOS_CONTRIBUYENTES:
            continue
        esperado = round(row.get('gravadas', 0) + row.get('debito', 0)
                         + row.get('exentas', 0) + row.get('no_sujetas', 0), 2)
        real     = round(row.get('total', 0), 2)
        if real > 0 and abs(esperado - real) > 0.50:
            alertas.append({
                "ctrl": row.get('num_control_raw', '—'),
                "esperado": esperado,
                "real": real,
                "diff": abs(esperado - real),
            })
    return alertas


@st.dialog("Confirmar Descarga de Anexos F-07")
def ventana_descarga_ventas(df_contribuyentes: pd.DataFrame,
                             df_consumidor: pd.DataFrame,
                             nombre_base: str) -> None:
    st.write("Verifica los totales antes de descargar. Los archivos están listos para cargar en el portal de Hacienda.")

    # ── Validación matemática Anexo 1 ────────────────────────────────────────
    if not df_contribuyentes.empty:
        alertas = _validar_matematica_ventas(df_contribuyentes)
        if alertas:
            with st.expander(f"⚠️ {len(alertas)} documento(s) con posible inconsistencia matemática"):
                for a in alertas[:10]:
                    st.markdown(
                        f'<div class="math-warn">📄 <code>{a["ctrl"]}</code> — '
                        f'Gravadas+IVA+Exentas = <strong>${a["esperado"]:,.2f}</strong> '
                        f'vs Total = <strong>${a["real"]:,.2f}</strong> '
                        f'(diferencia: ${a["diff"]:,.2f})</div>',
                        unsafe_allow_html=True
                    )

    # ── Configuración columnas R/S (Renta — desde ene 2025) ──────────────────
    st.markdown("##### Columnas Renta (R/S · U/V)")
    st.caption("Aplica desde enero 2025. Para periodos anteriores selecciona 'Anterior a ene 2025'.")
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        sel_periodo_r = st.selectbox(
            "Periodo declaración",
            ["Ene 2025 en adelante", "Anterior a ene 2025"],
            key="vta_periodo_renta",
        )
    with rc2:
        sel_tipo_op_r = st.selectbox(
            "Tipo de Operación (R/U)",
            ["1 — Gravada", "2 — No Gravada o Exento", "3 — Excluido/No Renta",
             "4 — Mixta", "12 — Retención F14/F910", "13 — Sujeto excluido art.6 LISR"],
            key="vta_tipo_op_renta",
        )
    with rc3:
        sel_tipo_ing_r = st.selectbox(
            "Tipo de Ingreso (S/V)",
            ["1 — Prof./Artes/Oficios", "2 — Act. Servicios", "3 — Act. Comerciales",
             "4 — Act. Industriales", "5 — Act. Agropecuarias", "6 — Utilidades/Dividendos",
             "7 — Export. bienes", "8 — Serv. exterior/SV", "9 — Export. servicios",
             "10 — Otras Rentas Grav.", "12 — Ret. F14/F910", "13 — Sujeto excluido art.6"],
            index=2,
            key="vta_tipo_ing_renta",
        )

    periodo_ene2025 = (sel_periodo_r == "Ene 2025 en adelante")
    tipo_op_r  = sel_tipo_op_r.split(" — ")[0]
    tipo_ing_r = sel_tipo_ing_r.split(" — ")[0]

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Anexo 1 — Contribuyentes (CCF/NC/ND)**")
        if not df_contribuyentes.empty:
            f07_contrib = construir_df_f07_contribuyentes(
                df_contribuyentes,
                tipo_op_renta=tipo_op_r,
                tipo_ingreso_renta=tipo_ing_r,
                periodo_ene2025=periodo_ene2025,
            )
            st.caption(f"📄 {len(f07_contrib)} documentos")
            total_c = df_contribuyentes['total'].sum()
            st.caption(f"Total: ${total_c:,.2f}")
            st.download_button(
                "📥 Descargar Anexo 1 (Contribuyentes)",
                data=to_excel_hacienda_contribuyentes(f07_contrib),
                file_name=f"F07_Anexo1_Contribuyentes_{nombre_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", use_container_width=True
            )
        else:
            st.info("Sin documentos de contribuyentes.")

    with col2:
        st.markdown("**Anexo 2 — Consumidor Final (Facturas)**")
        if not df_consumidor.empty:
            f07_cons = construir_df_f07_consumidor(
                df_consumidor,
                tipo_op_renta=tipo_op_r,
                tipo_ingreso_renta=tipo_ing_r,
                periodo_ene2025=periodo_ene2025,
            )
            st.caption(f"📄 {len(f07_cons)} documentos")
            total_cons = df_consumidor['total'].sum()
            st.caption(f"💰 Total: ${total_cons:,.2f}")
            st.download_button(
                "📥 Descargar Anexo 2 (Consumidor Final)",
                data=to_excel_hacienda_consumidor(f07_cons),
                file_name=f"F07_Anexo2_Consumidor_{nombre_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", use_container_width=True
            )
        else:
            st.info("Sin facturas de consumidor final.")


# ─────────────────────────────────────────────
# HELPERS UI
# ─────────────────────────────────────────────
def alerta_con_lista(tipo_alerta: str, icono: str, titulo: str, archivos: list) -> None:
    fn = getattr(st, tipo_alerta)
    if archivos:
        fn(f"{icono} **{len(archivos)} {titulo}**")
        with st.expander(f"Ver {len(archivos)} archivo(s)"):
            items_html = "".join(f"<div>📄 {safe_str(a)}</div>" for a in archivos)
            st.markdown(f'<div class="scroll-list">{items_html}</div>', unsafe_allow_html=True)
    else:
        st.success(f"✅ 0 {titulo}")


def datos_revision_vacio_ventas(causa: str = "", tipo: str = "03") -> dict:
    return {
        "fecha"          : "",
        "tipo"           : tipo,
        "anexo"          : "1" if tipo in TIPOS_CONTRIBUYENTES else "2",
        "num_control"    : "",
        "num_control_raw": "",
        "sello"          : "",
        "gen"            : "",
        "gen_sin_guiones": "",
        "nit_cli"        : "",
        "dui_cli"        : "",
        "nom_cli"        : "",
        "exentas"        : 0.0,
        "no_sujetas"     : 0.0,
        "gravadas"       : 0.0,
        "debito"         : 0.0,
        "terceros"       : 0.0,
        "deb_terc"       : 0.0,
        "total"          : 0.0,
        "estado"         : "REVISION",
        "iva_calc"       : False,
        "es_nuevo"       : True,
        "_error"         : safe_str(causa),
    }


def tipo_badge(tipo: str) -> str:
    badges = {
        "03": "🟢 CCF (03)",
        "01": "🔵 Factura (01)",
        "05": "🟠 Nota Crédito (05)",
        "06": "🔴 Nota Débito (06)",
        "02": "🔵 Fac. Simplif. (02)",
    }
    return badges.get(tipo, f"📄 DTE-{tipo}")


# ─────────────────────────────────────────────
# 7. ENCABEZADO
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family:Courier New,monospace;color:#6AB040;"
        "letter-spacing:3px;margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_titulo:
    st.title("📋 Extractor DTE — Ventas")

st.markdown(f"""
<div class="card-emisor">
    <strong>EMISOR ACTIVO:</strong> {safe_str(cliente.get('nombre',''))}<br>
    <strong>NIT:</strong> {safe_str(cliente.get('nit',''))} &nbsp;|&nbsp;
    <strong>NRC:</strong> {safe_str(cliente.get('nrc',''))}
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 8. SESSION STATE
# ─────────────────────────────────────────────
if 'cola_revision_v'  not in st.session_state: st.session_state.cola_revision_v  = []
if 'ventas_uploader'  not in st.session_state: st.session_state.ventas_uploader  = 0
if 'db_ventas'        not in st.session_state: st.session_state.db_ventas        = pd.DataFrame()
if 'archivos_ventas'  not in st.session_state: st.session_state.archivos_ventas  = []
if 'reporte_ventas'   not in st.session_state: st.session_state.reporte_ventas   = None

# ─────────────────────────────────────────────
# 9. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga de Ventas")
    st.markdown(
        "<small style='color:#6AB040'>Acepta: DTE-01 (Factura), DTE-03 (CCF), "
        "DTE-05 (NC), DTE-06 (ND)</small>",
        unsafe_allow_html=True
    )
    st.divider()

    tab_arch, tab_gmail = st.tabs(["📁 Archivos", "📧 Desde Gmail"])
    with tab_arch:
        archivos = st.file_uploader(
            "Arrastra PDFs o JSONs de ventas",
            type=["pdf", "json"],
            accept_multiple_files=True,
            key=str(st.session_state.ventas_uploader)
        )
    with tab_gmail:
        gmail_files = render_gmail_import("ventas")

    # Une los archivos subidos a mano con los traídos de Gmail.
    archivos = (archivos or []) + gmail_files

    procesar = st.button(
        "🚀 Procesar Ventas",
        type="primary",
        use_container_width=True,
        disabled=not archivos
    )

    if procesar and archivos:
        ya_procesados = set(st.session_state.archivos_ventas)
        nuevos        = [f for f in archivos if f.name not in ya_procesados]

        if not nuevos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            extracted, duplicados, iva_calc_files   = [], [], []
            invalidos, corruptos, ignorados_nit     = [], [], []
            nuevos_clientes_d = {}

            # Carga única de BD (evita leer el JSON en disco por cada PDF)
            _clientes_db_cache = cargar_clientes_json()

            bar          = st.progress(0)
            txt_progreso = st.empty()
            total_arch   = len(nuevos)

            # ── Pre-lectura en hilo principal (UploadedFile no es thread-safe) ──
            nombres_y_bytes_validos : list[tuple[str, bytes]] = []
            nombres_y_bytes_json    : list[tuple[str, bytes]] = []
            for f in nuevos:
                fb = f.read()
                if f.name.lower().endswith(".json"):
                    if len(fb) < 10:
                        corruptos.append(f.name)
                        st.session_state.archivos_ventas.append(f.name)
                    else:
                        nombres_y_bytes_json.append((f.name, fb))
                else:
                    if len(fb) < 512:
                        corruptos.append(f.name)
                        st.session_state.archivos_ventas.append(f.name)
                    else:
                        nombres_y_bytes_validos.append((f.name, fb))

            bar.progress(0)
            txt_progreso.caption(
                f"⏳ Enviando {len(nombres_y_bytes_validos)} PDF(s) y "
                f"{len(nombres_y_bytes_json)} JSON(s) a procesar..."
            )

            # ── JSON nativo: procesar directo ───────────────────────────────────
            resultados_json: list[tuple[str, bytes, dict]] = [
                (fname, fb, procesar_json_nativo_ventas(fb))
                for fname, fb in nombres_y_bytes_json
            ]

            # ── PDFs: extracción paralela ────────────────────────────────────────
            fn_extraer = functools.partial(
                extraer_venta_nativo_pro, cliente_activo=cliente, clientes_db=_clientes_db_cache
            )

            def _progreso_ventas(comp: int, tot: int, fname: str) -> None:
                bar.progress(comp / tot)
                txt_progreso.caption(f"⏳ {comp}/{tot} completados — `{fname}`")

            resultados_pdf = leer_y_procesar_lote(
                nombres_y_bytes_validos,
                fn_extraer,
                progreso_cb=_progreso_ventas,
            )

            resultados = resultados_json + resultados_pdf

            # ── Clasificación secuencial en hilo principal ──────────────────────
            for fname, file_bytes, res in resultados:
                cod_gen  = safe_str(res.get('gen', ''))
                num_ctrl = safe_str(res.get('num_control', ''))
                dup_id   = cod_gen or num_ctrl

                dup_memoria = (
                    not st.session_state.db_ventas.empty
                    and dup_id
                    and 'gen' in st.session_state.db_ventas.columns
                    and (
                        (st.session_state.db_ventas['gen'] == cod_gen).any()
                        if cod_gen else
                        (st.session_state.db_ventas['num_control'] == num_ctrl).any()
                        if num_ctrl else False
                    )
                )
                dup_lote = dup_id and any(
                    (d.get('gen') == cod_gen and cod_gen)
                    or (d.get('num_control') == num_ctrl and num_ctrl)
                    for d in extracted
                )

                if "error_tipo" in res:
                    invalidos.append(fname)

                elif dup_memoria or dup_lote:
                    duplicados.append(fname)

                elif "error_fatal" in res:
                    corruptos.append(fname)

                elif "error_extraccion" in res:
                    st.session_state.cola_revision_v.append({
                        "archivo": fname,
                        "bytes"  : file_bytes,
                        "datos"  : datos_revision_vacio_ventas(res["error_extraccion"]),
                    })

                else:
                    # ── Filtro de Pertenencia ────────────────────────────────────
                    _nit_activo = re.sub(r"[^0-9]", "", safe_str(cliente.get("nit", "")))
                    _nom_activo = safe_str(cliente.get("nombre", "")).upper()
                    _sandbox = (
                        _nit_activo == "00000000000000"
                        or "PRUEBA" in _nom_activo
                    )
                    if not _sandbox:
                        # En ventas el emisor del DTE = empresa activa
                        _nit_emisor_dte = re.sub(
                            r"[^0-9]", "",
                            safe_str(res.get("_nit_emisor", ""))
                        )
                        if _nit_emisor_dte and _nit_emisor_dte != _nit_activo:
                            ignorados_nit.append(fname)
                            st.session_state.archivos_ventas.append(fname)
                            continue
                    # ─────────────────────────────────────────────────────────────
                    nom_res  = safe_str(res.get('nom_cli', '')).strip()
                    tipo_res = safe_str(res.get('tipo', ''))
                    requiere_nombre = tipo_res in TIPOS_CONTRIBUYENTES
                    va_revision = (
                        res.get('total', 0.0) == 0.0
                        or not res.get('num_control')
                        or not safe_str(res.get('fecha', '')).strip()
                        or (requiere_nombre and nom_res in ("SIN NOMBRE", ""))
                    )
                    if va_revision:
                        st.session_state.cola_revision_v.append({
                            "archivo": fname,
                            "bytes"  : file_bytes,
                            "datos"  : res,
                        })
                    else:
                        if res.get('iva_calc'):
                            iva_calc_files.append(fname)
                        if res.get("es_nuevo") and (res.get("nit_cli") or res.get("dui_cli")):
                            id_clave = res.get("nit_cli") or res.get("dui_cli")
                            nom_n    = res["nom_cli"]
                            nuevos_clientes_d[id_clave] = nom_n
                            guardar_cliente_rapido(id_clave, nom_n)
                        res["archivo"] = fname
                        extracted.append(res)

                st.session_state.archivos_ventas.append(fname)

            gc.collect()

            txt_progreso.success(f"✅ {total_arch} documentos escaneados.")

            st.session_state.reporte_ventas = {
                "invalidos"       : invalidos,
                "duplicados"      : duplicados,
                "iva_calc"        : iva_calc_files,
                "nuevos_clientes" : nuevos_clientes_d,
                "corruptos"       : corruptos,
                "ignorados_nit"   : ignorados_nit,
            }

            if extracted:
                new_df = pd.DataFrame(extracted)
                # Asegurar columnas necesarias existen
                for col in ['gen_sin_guiones', 'num_control_raw', 'sello', 'anexo', 'dui_cli']:
                    if col not in new_df.columns:
                        new_df[col] = ""
                
                if st.session_state.db_ventas.empty:
                    st.session_state.db_ventas = new_df
                else:
                    st.session_state.db_ventas = pd.concat(
                        [st.session_state.db_ventas, new_df], ignore_index=True
                    )

    st.divider()
    if st.button("🧹 Limpiar Memoria Ventas", type="secondary", use_container_width=True):
        for key in ('db_ventas', 'archivos_ventas', 'reporte_ventas', 'cola_revision_v'):
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.ventas_uploader = st.session_state.get('ventas_uploader', 0) + 1
        st.rerun()

    if not st.session_state.db_ventas.empty:
        df_sidebar = st.session_state.db_ventas
        st.divider()
        total_docs = len(df_sidebar)
        n_ccf  = len(df_sidebar[df_sidebar['tipo'] == '03']) if 'tipo' in df_sidebar.columns else 0
        n_fac  = len(df_sidebar[df_sidebar['tipo'] == '01']) if 'tipo' in df_sidebar.columns else 0
        n_otros = total_docs - n_ccf - n_fac
        st.markdown(f"**📄 Total docs:** `{total_docs}`")
        st.markdown(f"**🟢 CCF (03):** `{n_ccf}` | **🔵 Facturas (01):** `{n_fac}` | **Otros:** `{n_otros}`")
        if 'total' in df_sidebar.columns:
            st.markdown(f"**💰 Total:** `${df_sidebar['total'].sum():,.2f}`")

# ─────────────────────────────────────────────
# 10. BANDEJA DE REVISIÓN MANUAL
# ─────────────────────────────────────────────
if st.session_state.cola_revision_v:
    st.markdown("""
    <div class="inbox-revision">
        <h3>📥 Bandeja de Revisión Manual</h3>
        <p>Datos incompletos o fallo de extracción. Revisa y corrige antes de agregar al libro.</p>
    </div>
    """, unsafe_allow_html=True)

    total_cola = len(st.session_state.cola_revision_v)

    col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
    with col_nav2:
        st.info(f"📄 Documento **1 de {total_cola}** en revisión | Quedan **{total_cola}** por revisar")

    with st.expander("🗑️ Gestión masiva de cola"):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("🗑️ Descartar TODOS los pendientes", type="secondary", use_container_width=True):
                st.session_state.cola_revision_v = []
                st.rerun()
        with col_m2:
            st.caption(f"Total en cola: {total_cola} documentos")

    if not st.session_state.cola_revision_v:
        st.stop()
    item_actual = st.session_state.cola_revision_v[0]
    datos_act   = item_actual["datos"]
    tipo_actual = safe_str(datos_act.get("tipo", "03"))

    st.divider()

    col_img, col_form = st.columns([1.2, 1], gap="large")

    with col_img:
        if item_actual["archivo"].lower().endswith(".json"):
            st.info(
                "Vista previa de PDF no aplicable para archivos JSON nativos. "
                "Los datos se extrajeron con 100% de precisión."
            )
            with st.expander("🔍 Datos extraídos automáticamente"):
                _v_campos  = datos_act.get("_vision_campos", {})
                _v_alertas = datos_act.get("_vision_alertas", [])
                _v_audit   = datos_act.get("_vision_audit", {})
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.caption(f"**Tipo DTE:** `{tipo_badge(tipo_actual)}`")
                    st.caption(f"**Num Control:** `{datos_act.get('num_control_raw', datos_act.get('num_control','—'))}`")
                    st.caption(f"**UUID:** `{datos_act.get('gen','—')}`")
                    st.caption(f"**Sello:** `{datos_act.get('sello','—')}`")
                    st.caption(f"**Fecha:** `{datos_act.get('fecha','—')}`")
                with col_d2:
                    st.caption(f"**NIT receptor:** `{datos_act.get('nit_cli','—')}`")
                    st.caption(f"**DUI receptor:** `{datos_act.get('dui_cli','—')}`")
                    st.caption(f"**Nombre:** `{datos_act.get('nom_cli','—')}`")
                    st.caption(f"**Total:** `${datos_act.get('total',0):.2f}`")
                    st.caption(f"**Gravadas:** `${datos_act.get('gravadas',0):.2f}`")
                    st.caption(f"**Débito:** `${datos_act.get('debito',0):.2f}`")
        else:
            try:
                with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                    if not pdf.pages:
                        st.error("El PDF no contiene páginas.")
                        st.stop()
                    img = pdf.pages[0].to_image(resolution=200).original
                    st.image(img, caption=item_actual['archivo'], use_container_width=True)
                    texto_crudo = ""
                    for page in pdf.pages:
                        texto_crudo += safe_extract_text(page, layout=True) + "\n"

                    with st.expander("🔍 Datos extraídos automáticamente"):
                        # ── QA Banner + Vision indicator ──────────────────────────
                        _v_campos = datos_act.get("_vision_campos", {})
                        _v_alertas = datos_act.get("_vision_alertas", [])
                        _v_audit   = datos_act.get("_vision_audit", {})
                        _confianza = _v_audit.get("confianza", 100) if _v_audit else 100
                        _alertas_qa = validar_montos_ventas(datos_act)
                        mostrar_banner_qa(
                            "ventas", datos_act,
                            confianza=_confianza,
                            alertas=_v_alertas + _alertas_qa,
                        )
                        mostrar_indicador_vision(
                            _v_campos, _v_alertas, _v_audit,
                            error_vision=vision_ultimo_error(),
                        )
                        # ─────────────────────────────────────────────────────────
                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            st.caption(f"**Tipo DTE:** `{tipo_badge(tipo_actual)}`")
                            st.caption(f"**Num Control:** `{datos_act.get('num_control_raw', datos_act.get('num_control','—'))}`")
                            st.caption(f"**UUID:** `{datos_act.get('gen','—')}`")
                            st.caption(f"**Sello:** `{datos_act.get('sello','—')}`")
                            st.caption(f"**Fecha:** `{datos_act.get('fecha','—')}`")
                        with col_d2:
                            st.caption(f"**NIT receptor:** `{datos_act.get('nit_cli','—')}`")
                            st.caption(f"**DUI receptor:** `{datos_act.get('dui_cli','—')}`")
                            st.caption(f"**Nombre:** `{datos_act.get('nom_cli','—')}`")
                            st.caption(f"**Total:** `${datos_act.get('total',0):.2f}`")
                            st.caption(f"**Gravadas:** `${datos_act.get('gravadas',0):.2f}`")
                            st.caption(f"**Débito:** `${datos_act.get('debito',0):.2f}`")

                    st.markdown("**📝 Texto extraído del PDF:**")
                    st.text_area("", value=texto_crudo.strip(),
                                 height=220, label_visibility="collapsed")
            except Exception as ex_prev:
                st.error(f"No se pudo cargar la vista previa: {safe_str(ex_prev)}")

    with col_form:
        st.markdown("### ✍️ Corrección Manual")

        error_causa = safe_str(datos_act.get("_error", ""))
        if error_causa:
            st.warning(f"⚠️ **Causa del fallo:** `{error_causa}`")

        campos_faltantes = []
        if not safe_str(datos_act.get("fecha","")).strip():       campos_faltantes.append("Fecha")
        if not safe_str(datos_act.get("num_control","")).strip(): campos_faltantes.append("Núm. Control")
        if datos_act.get('tipo','') in TIPOS_CONTRIBUYENTES and datos_act.get("nom_cli","") in ("SIN NOMBRE",""):
            campos_faltantes.append("Nombre cliente")
        if datos_act.get("total", 0.0) == 0.0:                   campos_faltantes.append("Total")
        if campos_faltantes:
            st.error(f"❌ Campos requeridos: **{', '.join(campos_faltantes)}**")

        with st.form(key=f"form_rev_v_{item_actual['archivo']}"):
            st.markdown("**📋 Identificación del documento**")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_fecha = st.text_input(
                    "📅 Fecha (DD/MM/YYYY) *",
                    value=safe_str(datos_act.get("fecha", "")),
                    placeholder="13/03/2026"
                )
                tipos_opciones = ["03", "01", "05", "06", "02"]
                tipo_idx = tipos_opciones.index(tipo_actual) if tipo_actual in tipos_opciones else 0
                f_tipo = st.selectbox("📄 Tipo DTE", options=tipos_opciones, index=tipo_idx)
            with col_f2:
                f_ctrl = st.text_input(
                    "🔢 Número de Control DTE *",
                    value=safe_str(datos_act.get("num_control_raw", datos_act.get("num_control", ""))),
                    placeholder="DTE-03-M001P001-000000000000033"
                )
                f_gen = st.text_input(
                    "🔑 UUID / Código de Generación",
                    value=safe_str(datos_act.get("gen", "")),
                    placeholder="25AA41EA-0412-40BC-803D-405272AC7891"
                )

            f_sello = st.text_input(
                "🛡️ Sello de Recepción",
                value=safe_str(datos_act.get("sello", "")),
                placeholder="20261A71A6D9E53A4BE59631B7BED69D231B6PHP"
            )

            # Determinar si es contribuyente o consumidor según tipo seleccionado
            es_contribuyente_form = f_tipo in TIPOS_CONTRIBUYENTES

            if es_contribuyente_form:
                st.markdown("**🏢 Receptor (Contribuyente)**")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    f_nit = st.text_input(
                        "🆔 NIT del Cliente",
                        value=safe_str(datos_act.get("nit_cli", "")),
                        placeholder="12172810871033"
                    )
                with col_r2:
                    f_dui = st.text_input(
                        "🪪 DUI (si persona natural)",
                        value=safe_str(datos_act.get("dui_cli", "")),
                        placeholder="opcional"
                    )
                nom_sug = safe_str(datos_act.get("nom_cli", ""))
                if nom_sug in ("SIN NOMBRE", ""):
                    nom_sug = ""
                f_nom = st.text_input(
                    "🏢 Nombre / Razón Social *",
                    value=nom_sug,
                    placeholder="JONATHAN NEFTALI RIVAS HERRERA"
                )
            else:
                st.markdown("**👤 Receptor (Consumidor Final)**")
                st.caption("ℹ️ Para facturas consumidor: ingresa DUI si está disponible. NIT se deja vacío.")
                f_nit = ""  # Para consumidor: NIT vacío
                f_dui = st.text_input(
                    "🪪 DUI del Consumidor (opcional)",
                    value=safe_str(datos_act.get("dui_cli", "")),
                    placeholder="03125700-4 → 031257004"
                )
                f_nom = st.text_input(
                    "👤 Nombre del Consumidor (opcional)",
                    value=safe_str(datos_act.get("nom_cli", "")).replace("SIN NOMBRE", ""),
                    placeholder="FRANCISCO ANTONIO HERNANDEZ"
                )

            st.markdown("**💰 Montos**")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                f_total = st.number_input(
                    "💰 Total a Pagar ($) *",
                    value=float(datos_act.get("total", 0.0)),
                    format="%.2f", min_value=0.0
                )
            with col_m2:
                f_gravadas = st.number_input(
                    "🧾 Ventas Gravadas ($)",
                    value=float(datos_act.get("gravadas", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="CCF: sin IVA. Factura consumidor: con IVA incluido. Dejar en 0 para calcular."
                )
            with col_m3:
                f_debito = st.number_input(
                    "🏦 Débito Fiscal ($)",
                    value=float(datos_act.get("debito", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Solo aplica para CCF (DTE-03, 05, 06). Dejar en 0 para calcular."
                )

            col_m4, col_m5 = st.columns(2)
            with col_m4:
                f_exentas = st.number_input(
                    "🔹 Ventas Exentas ($)",
                    value=float(datos_act.get("exentas", 0.0)),
                    format="%.2f", min_value=0.0
                )
            with col_m5:
                f_no_sujetas = st.number_input(
                    "🔸 Ventas No Sujetas ($)",
                    value=float(datos_act.get("no_sujetas", 0.0)),
                    format="%.2f", min_value=0.0
                )

            if f_total > 0:
                if es_contribuyente_form:
                    grav_preview = f_gravadas if f_gravadas > 0 else round(
                        (f_total - f_exentas - f_no_sujetas) / 1.13, 2
                    )
                    deb_preview = f_debito if f_debito > 0 else round(grav_preview * 0.13, 2)
                    st.caption(
                        f"📊 Preview CCF: Gravadas `${grav_preview:.2f}` | "
                        f"IVA `${deb_preview:.2f}` | Total `${f_total:.2f}`"
                    )
                else:
                    st.caption(
                        f"📊 Preview Factura: Gravadas c/IVA `${f_total:.2f}` | "
                        f"Total `${f_total:.2f}`"
                    )

            actualizar_otros = st.checkbox(
                "🔄 Actualizar nombre en registros existentes con este NIT/DUI", value=True
            )

            st.markdown("")
            b1, b2, b3 = st.columns([2, 1, 1])
            with b1:
                submit_ok   = st.form_submit_button("✅ Aprobar y Agregar al Libro", type="primary", use_container_width=True)
            with b2:
                submit_skip = st.form_submit_button("⏭️ Saltar", use_container_width=True)
            with b3:
                submit_del  = st.form_submit_button("🗑️ Descartar", use_container_width=True)

            if submit_ok:
                errores = []
                if not f_fecha.strip():  errores.append("Fecha requerida.")
                if not f_ctrl.strip():   errores.append("Número de Control requerido.")
                if f_total <= 0:         errores.append("Total debe ser mayor a 0.")
                if es_contribuyente_form and not f_nom.strip():
                    errores.append("Nombre del Cliente requerido para CCF.")
                if f_fecha.strip() and not re.match(r'\d{2}/\d{2}/\d{4}', f_fecha.strip()):
                    errores.append("Formato de fecha inválido. Use DD/MM/YYYY.")

                if errores:
                    for e_msg in errores:
                        st.error(e_msg)
                else:
                    nombre_limpio = f_nom.strip().upper() if f_nom.strip() else "SIN NOMBRE"
                    nit_act = f_nit.strip() if es_contribuyente_form else ""
                    dui_act = re.sub(r'[^0-9]', '', f_dui.strip()) if f_dui.strip() else ""
                    
                    # Número de control: guardar sin guiones y con guiones
                    ctrl_raw  = f_ctrl.strip().upper()
                    ctrl_limpio = ctrl_raw.replace("-", "")

                    # UUID sin guiones
                    gen_raw      = f_gen.strip().upper()
                    gen_sin_g    = gen_raw.replace("-", "")

                    id_guardar = nit_act or dui_act
                    if id_guardar and nombre_limpio != "SIN NOMBRE":
                        guardar_cliente_rapido(id_guardar, nombre_limpio)

                    for item_pend in st.session_state.cola_revision_v[1:]:
                        pend_nit = item_pend["datos"].get("nit_cli", "")
                        pend_dui = item_pend["datos"].get("dui_cli", "")
                        if (pend_nit and pend_nit == nit_act) or (pend_dui and pend_dui == dui_act):
                            item_pend["datos"]["nom_cli"] = nombre_limpio
                            item_pend["datos"]["es_nuevo"] = False

                    if actualizar_otros and id_guardar:
                        actualizar_nombre_en_db_ventas(id_guardar, nombre_limpio)

                    grav_f = f_gravadas
                    deb_f  = f_debito
                    ic     = datos_act.get("iva_calc", False)

                    if es_contribuyente_form:
                        if f_total > 0 and grav_f == 0.0 and deb_f == 0.0:
                            grav_f = round((f_total - f_exentas - f_no_sujetas) / 1.13, 2)
                            deb_f  = round(f_total - f_exentas - f_no_sujetas - grav_f, 2)
                            ic     = True
                        elif f_total > 0 and deb_f == 0.0 and grav_f > 0.0:
                            deb_f  = round(grav_f * 0.13, 2)
                            ic     = True
                    else:
                        # Consumidor final: gravadas = total (con IVA)
                        if grav_f == 0.0:
                            grav_f = f_total
                        deb_f = 0.0

                    tipo_final = f_tipo
                    anexo_final = "1" if tipo_final in TIPOS_CONTRIBUYENTES else "2"

                    datos_act.update({
                        "fecha"          : f_fecha.strip(),
                        "tipo"           : tipo_final,
                        "anexo"          : anexo_final,
                        "num_control"    : ctrl_limpio,
                        "num_control_raw": ctrl_raw,
                        "sello"          : f_sello.strip().upper(),
                        "gen"            : gen_raw,
                        "gen_sin_guiones": gen_sin_g,
                        "nit_cli"        : nit_act,
                        "dui_cli"        : dui_act,
                        "nom_cli"        : nombre_limpio,
                        "total"          : f_total,
                        "exentas"        : f_exentas,
                        "no_sujetas"     : f_no_sujetas,
                        "gravadas"       : grav_f,
                        "debito"         : deb_f,
                        "iva_calc"       : ic,
                        "es_nuevo"       : False,
                        "archivo"        : item_actual["archivo"],
                    })

                    nuevo_df = pd.DataFrame([datos_act])
                    if st.session_state.db_ventas.empty:
                        st.session_state.db_ventas = nuevo_df
                    else:
                        st.session_state.db_ventas = pd.concat(
                            [st.session_state.db_ventas, nuevo_df], ignore_index=True
                        )

                    if id_guardar:
                        rep_act = st.session_state.get("reporte_ventas") or {}
                        nc_dict = rep_act.get("nuevos_clientes", {})
                        nc_dict[id_guardar] = nombre_limpio
                        if st.session_state.reporte_ventas:
                            st.session_state.reporte_ventas["nuevos_clientes"] = nc_dict

                    # ── Guardar como ejemplo de entrenamiento ────────────────
                    try:
                        _texto_train = ""
                        with pdfplumber.open(BytesIO(item_actual["bytes"])) as _pdf_t:
                            for _pg in _pdf_t.pages:
                                _texto_train += safe_extract_text(_pg) + "\n"
                        registrar_correccion(
                            tipo_dte          = "ventas",
                            texto_pdf         = _texto_train,
                            campos_originales = {
                                "fecha"  : datos_act.get("fecha", ""),
                                "nit_cli": datos_act.get("nit_cli", ""),
                                "nom_cli": datos_act.get("nom_cli", ""),
                            },
                            campos_corregidos = {
                                "fecha"  : datos_act.get("fecha", ""),
                                "nit_cli": nit_act,
                                "nom_cli": nombre_limpio,
                            },
                        )
                    except Exception:
                        pass
                    # ─────────────────────────────────────────────────────────

                    st.session_state.cola_revision_v.pop(0)
                    st.success("✅ Documento aprobado y agregado al libro.")
                    st.rerun()

            if submit_skip:
                item = st.session_state.cola_revision_v.pop(0)
                st.session_state.cola_revision_v.append(item)
                st.rerun()

            if submit_del:
                st.session_state.cola_revision_v.pop(0)
                st.rerun()

    st.stop()

# ─────────────────────────────────────────────
# 11. REPORTE DE PROCESAMIENTO
# ─────────────────────────────────────────────
if st.session_state.reporte_ventas:
    rep = st.session_state.reporte_ventas
    st.markdown("### 📋 Alertas de Procesamiento")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        alerta_con_lista("error" if rep.get("corruptos") else "success",
                         "💀", "Dañados", rep.get("corruptos", []))
    with c2:
        alerta_con_lista("warning" if rep.get("invalidos") else "success",
                         "⚠️", "Ignorados (tipo incorrecto)", rep.get("invalidos", []))
    with c3:
        alerta_con_lista("error" if rep.get("duplicados") else "success",
                         "🛑", "Duplicados", rep.get("duplicados", []))
    with c4:
        alerta_con_lista("info" if rep.get("iva_calc") else "success",
                         "🧮", "IVA Calculado", rep.get("iva_calc", []))
    with c5:
        alerta_con_lista("warning" if rep.get("ignorados_nit") else "success",
                         "🚫", "Ignorados (NIT no coincide)", rep.get("ignorados_nit", []))

    nc_dict = rep.get("nuevos_clientes", {})
    if nc_dict:
        st.markdown(f"**🆕 Clientes nuevos guardados:** `{len(nc_dict)}`")
        with st.expander("Ver clientes nuevos registrados"):
            for nit_k, nom_k in nc_dict.items():
                st.markdown(f"- `{nit_k}` — **{nom_k}**")

    st.divider()

# ─────────────────────────────────────────────
# 12. TABLA PRINCIPAL Y EXPORT
# ─────────────────────────────────────────────
if not st.session_state.db_ventas.empty:
    df = st.session_state.db_ventas.copy()

    # Asegurar columnas críticas
    for col in ['gen_sin_guiones', 'num_control_raw', 'sello', 'anexo', 'dui_cli', 'num_control']:
        if col not in df.columns:
            df[col] = ""

    # Separar por anexo
    df_contribuyentes = df[df['anexo'] == '1'].copy() if 'anexo' in df.columns else pd.DataFrame()
    df_consumidor     = df[df['anexo'] == '2'].copy() if 'anexo' in df.columns else pd.DataFrame()

    # ── Panel de Filtros Avanzado ────────────────────────────────────────────
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    st.markdown('<span class="filter-title">🔍 Filtros de Auditoría — F-07 Ventas</span>', unsafe_allow_html=True)

    fc1, fc2, fc3 = st.columns([3, 1, 1])
    with fc1:
        busqueda = st.text_input(
            "busqueda_v", label_visibility="collapsed",
            placeholder="Buscar por nombre, NIT, DUI, Núm. Control o UUID…"
        )
    with fc2:
        tipos_disponibles = sorted(df['tipo'].unique().tolist()) if 'tipo' in df.columns else []
        filtro_tipo = st.multiselect(
            "Tipo DTE", options=tipos_disponibles,
            default=tipos_disponibles, placeholder="Todos los tipos"
        )
    with fc3:
        filtro_anexo = st.multiselect(
            "Anexo F-07",
            options=["1 - Contribuyentes", "2 - Consumidor"],
            default=["1 - Contribuyentes", "2 - Consumidor"],
            placeholder="Todos"
        )

    fd1, fd2, fd3, fd4 = st.columns(4)
    with fd1:
        fecha_desde = st.date_input("Desde", value=None, format="DD/MM/YYYY", key="vta_fd")
    with fd2:
        fecha_hasta = st.date_input("Hasta", value=None, format="DD/MM/YYYY", key="vta_fh")
    with fd3:
        monto_min = st.number_input("Monto mín. ($)", min_value=0.0, value=0.0, step=10.0, key="vta_mm")
    with fd4:
        monto_max = st.number_input("Monto máx. ($)", min_value=0.0, value=0.0, step=100.0,
                                     key="vta_mx", help="0 = sin límite superior")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Aplicar filtros ──────────────────────────────────────────────────────
    df_filtrado = df.copy()

    if busqueda:
        t_bus = busqueda.strip()
        mask = (
            df_filtrado['nom_cli'].str.contains(t_bus, case=False, na=False, regex=False)        |
            df_filtrado['nit_cli'].str.contains(t_bus, na=False, regex=False)                    |
            df_filtrado['dui_cli'].str.contains(t_bus, na=False, regex=False)                    |
            df_filtrado['num_control'].str.contains(t_bus, case=False, na=False, regex=False)    |
            df_filtrado['gen'].str.contains(t_bus, case=False, na=False, regex=False)
        )
        df_filtrado = df_filtrado[mask]

    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]

    if filtro_anexo:
        anexos_sel = [a[0] for a in filtro_anexo]
        df_filtrado = df_filtrado[df_filtrado['anexo'].isin(anexos_sel)]

    def _dmy_ts(fecha_str: str):
        try:
            p = str(fecha_str).strip().split('/')
            if len(p) == 3:
                return pd.Timestamp(int(p[2]), int(p[1]), int(p[0]))
        except Exception:
            pass
        return pd.NaT

    if (fecha_desde or fecha_hasta) and 'fecha' in df_filtrado.columns:
        df_filtrado['_fts'] = df_filtrado['fecha'].apply(_dmy_ts)
        if fecha_desde:
            df_filtrado = df_filtrado[df_filtrado['_fts'] >= pd.Timestamp(fecha_desde)]
        if fecha_hasta:
            df_filtrado = df_filtrado[df_filtrado['_fts'] <= pd.Timestamp(fecha_hasta)]
        df_filtrado = df_filtrado.drop(columns=['_fts'], errors='ignore')

    col_total = 'total' if 'total' in df_filtrado.columns else ('tot' if 'tot' in df_filtrado.columns else None)
    if col_total:
        if monto_min > 0:
            df_filtrado = df_filtrado[df_filtrado[col_total] >= monto_min]
        if monto_max > 0:
            df_filtrado = df_filtrado[df_filtrado[col_total] <= monto_max]

    # ── Badge de resultados ──────────────────────────────────────────────────
    n_tot = len(df)
    n_fil = len(df_filtrado)
    filtros_activos = sum([
        bool(busqueda),
        bool(filtro_tipo and len(filtro_tipo) < len(tipos_disponibles)),
        bool(len(filtro_anexo) < 2),
        bool(fecha_desde), bool(fecha_hasta),
        bool(monto_min > 0), bool(monto_max > 0),
    ])
    badge_extra = (f'<span class="active-filters"> · {filtros_activos} filtro(s) activo(s)</span>'
                   if filtros_activos else "")
    st.markdown(
        f'<div class="results-badge"><span class="cnt">{n_fil}</span> de {n_tot} registros{badge_extra}</div>',
        unsafe_allow_html=True
    )

    # Separar filtrados
    df_fil_contrib = df_filtrado[df_filtrado['anexo'] == '1'].copy()
    df_fil_cons    = df_filtrado[df_filtrado['anexo'] == '2'].copy()

    # ── Métricas resumen ─────────────────────────────────────────────────────
    if not df_filtrado.empty:
        _vm1, _vm2, _vm3, _vm4 = st.columns(4)
        with _vm1:
            st.metric("📤 Documentos", n_fil)
        with _vm2:
            _grav_tot = df_filtrado["gravadas"].sum() if "gravadas" in df_filtrado.columns else 0.0
            st.metric("📦 Ventas Gravadas", f"${_grav_tot:,.2f}")
        with _vm3:
            _deb_tot = df_filtrado["debito"].sum() if "debito" in df_filtrado.columns else 0.0
            st.metric("🧾 Débito Fiscal (IVA)", f"${_deb_tot:,.2f}")
        with _vm4:
            _vtot = df_filtrado["total"].sum() if "total" in df_filtrado.columns else 0.0
            st.metric("💰 Total Ventas", f"${_vtot:,.2f}")
    st.markdown("")

    _n_contrib = len(df_fil_contrib)
    _n_cons    = len(df_fil_cons)
    _n_rev_v   = int((df_filtrado.apply(calcular_estatus_venta, axis=1) == "🔴 Revisar").sum()) if not df_filtrado.empty else 0
    _alerta_lbl_v = f"⚠️ Alertas ({_n_rev_v})" if _n_rev_v else "✅ Alertas"
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"🟢 Anexo 1 — Contribuyentes ({_n_contrib})",
        f"🔵 Anexo 2 — Consumidor Final ({_n_cons})",
        "🔍 Auditoría Completa",
        "📈 Resumen por Tipo",
        _alerta_lbl_v,
    ])

    with tab1:
        st.markdown("#### 🧾 Detalle de Ventas a Contribuyentes (CCF / NC / ND)")
        if not df_fil_contrib.empty:
            df_f07_c = construir_df_f07_contribuyentes(df_fil_contrib)
            df_f07_c.insert(0, "Estatus", df_fil_contrib.apply(calcular_estatus_venta, axis=1).values)
            COLS_NUM_C = [c for c in df_f07_c.columns if df_f07_c[c].dtype == float]
            st.dataframe(
                df_f07_c.style.format({c: "{:.2f}" for c in COLS_NUM_C}),
                hide_index=True, use_container_width=True
            )
            # Resumen
            sumas = []
            for lbl, col_key in [
                ("Exentas", "J. Ventas Exentas"),
                ("No Sujetas", "K. Ventas No Sujetas"),
                ("Gravadas", "L. Ventas Gravadas"),
                ("Débito Fiscal", "M. Débito Fiscal"),
                ("Total", "P. Total Ventas"),
            ]:
                if col_key in df_f07_c.columns:
                    v = df_f07_c[col_key].sum()
                    if v > 0 or lbl == "Total":
                        sumas.append(f"**{lbl}:** `${v:,.2f}`")
            if sumas:
                st.markdown("> " + " &nbsp;|&nbsp; ".join(sumas))
        else:
            st.info("Sin documentos de contribuyentes en el filtro actual.")

    with tab2:
        st.markdown("#### 🧾 Detalle de Ventas a Consumidor Final (Facturas)")
        st.caption("ℹ️ Según manual F-07: los DTE de consumidor se agrupan por día. Aquí se muestran individuales para auditoría.")
        if not df_fil_cons.empty:
            df_f07_cons = construir_df_f07_consumidor(df_fil_cons)
            COLS_NUM_CONS = [c for c in df_f07_cons.columns if df_f07_cons[c].dtype == float]
            st.dataframe(
                df_f07_cons.style.format({c: "{:.2f}" for c in COLS_NUM_CONS}),
                hide_index=True, use_container_width=True
            )
            sumas_cons = []
            for lbl, col_key in [
                ("Exentas", "K. Ventas Exentas"),
                ("No Sujetas", "M. Ventas No Sujetas"),
                ("Gravadas c/IVA", "N. Ventas Gravadas (c/IVA)"),
                ("Total", "T. Total Ventas"),
            ]:
                if col_key in df_f07_cons.columns:
                    v = df_f07_cons[col_key].sum()
                    if v > 0 or lbl == "Total":
                        sumas_cons.append(f"**{lbl}:** `${v:,.2f}`")
            if sumas_cons:
                st.markdown("> " + " &nbsp;|&nbsp; ".join(sumas_cons))
        else:
            st.info("Sin facturas de consumidor final en el filtro actual.")

        if not df_fil_cons.empty:
            st.markdown("---")
            st.markdown("##### 📅 Agrupado por Día (vista previa para Hacienda)")
            st.caption("El portal de Hacienda requiere los DTE-01 agrupados por día con UUID del primero y último DTE.")
            try:
                df_agrup = df_fil_cons.groupby('fecha').agg(
                    Documentos=('total', 'count'),
                    UUID_primero=('gen_sin_guiones', 'first'),
                    UUID_ultimo=('gen_sin_guiones', 'last'),
                    Exentas=('exentas', 'sum'),
                    No_Sujetas=('no_sujetas', 'sum'),
                    Gravadas_con_IVA=('gravadas', 'sum'),
                    Total=('total', 'sum'),
                ).reset_index()
                st.dataframe(df_agrup, hide_index=True, use_container_width=True)
            except Exception:
                st.info("No se pudo generar agrupado por día.")

    with tab3:
        st.write(f"📊 Registros: **{len(df_filtrado)}** de **{len(df)}**")
        df_auditoria = construir_df_f07_ventas_combinado(df_filtrado)
        df_auditoria.insert(0, "Estatus", df_filtrado.apply(calcular_estatus_venta, axis=1).values)
        COLS_NUM_AUD_V = ["Exentas", "No Sujetas", "Gravadas", "Débito", "Total"]
        cols_fmt_aud   = {c: "{:,.2f}" for c in COLS_NUM_AUD_V if c in df_auditoria.columns}
        st.dataframe(
            df_auditoria.style.format(cols_fmt_aud),
            use_container_width=True,
            hide_index=True,
        )

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "📥 Descargar Auditoría Excel",
                data=to_excel_auditoria(df_auditoria),
                file_name=f"Auditoria_Ventas_{safe_str(cliente.get('nombre','')).replace(' ','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="secondary", use_container_width=True
            )

    with tab4:
        if not df_filtrado.empty:
            resumen_tipo = df_filtrado.groupby('tipo').agg(
                Documentos=('total', 'count'),
                Exentas=('exentas', 'sum'),
                No_Sujetas=('no_sujetas', 'sum'),
                Gravadas=('gravadas', 'sum'),
                Debito_Fiscal=('debito', 'sum'),
                Total=('total', 'sum'),
            ).reset_index()
            
            # Agregar descripción
            desc_tipo = {
                "01": "Factura Consumidor Final",
                "03": "Comprobante Crédito Fiscal",
                "05": "Nota de Crédito",
                "06": "Nota de Débito",
                "02": "Factura Simplificada",
            }
            resumen_tipo['Descripción'] = resumen_tipo['tipo'].map(lambda x: desc_tipo.get(x, f"DTE-{x}"))
            resumen_tipo['Anexo']       = resumen_tipo['tipo'].map(
                lambda x: "Anexo 1 (Contrib.)" if x in TIPOS_CONTRIBUYENTES else "Anexo 2 (Consumidor)"
            )
            resumen_tipo = resumen_tipo[['tipo', 'Descripción', 'Anexo', 'Documentos',
                                          'Exentas', 'No_Sujetas', 'Gravadas', 'Debito_Fiscal', 'Total']]
            resumen_tipo.columns = ['Tipo', 'Descripción', 'Anexo', 'Docs',
                                     'Exentas', 'No Sujetas', 'Gravadas', 'Débito Fiscal', 'Total']
            COLS_NUM_R = ['Exentas', 'No Sujetas', 'Gravadas', 'Débito Fiscal', 'Total']
            st.dataframe(
                resumen_tipo.style.format({c: "${:,.2f}" for c in COLS_NUM_R}),
                hide_index=True, use_container_width=True
            )

            # Total general
            st.markdown("---")
            col_tot1, col_tot2 = st.columns(2)
            with col_tot1:
                total_contrib = df_filtrado[df_filtrado['anexo'] == '1']['total'].sum()
                st.metric("Anexo 1 — Total Contribuyentes", f"${total_contrib:,.2f}")
            with col_tot2:
                total_cons = df_filtrado[df_filtrado['anexo'] == '2']['total'].sum()
                st.metric("Anexo 2 — Total Consumidor Final", f"${total_cons:,.2f}")
        else:
            st.info("Sin datos para mostrar.")

    with tab5:
        st.markdown("#### ⚠️ Detalle de Alertas por Documento")

        if not df_filtrado.empty:
            # Validación de período — regla estricta para Ventas
            alerta_per = validar_periodo_ventas(df_filtrado)
            if alerta_per:
                st.warning(f"⚠️ **Alerta de período**: {alerta_per}")

            # Nota informativa sobre NC (DTE-05) en Ventas
            n_nc_v = (df_filtrado["tipo"] == "05").sum() if "tipo" in df_filtrado.columns else 0
            if n_nc_v > 0:
                st.info(
                    f"ℹ️ **{n_nc_v} Nota(s) de Crédito (DTE-05)** en este período: "
                    "reducen el débito fiscal IVA declarado. Asegúrate de que corresponden "
                    "a un CCF (DTE-03) previamente emitido."
                )

            filas_alerta = []
            for _, row in df_filtrado.iterrows():
                motivo = razones_revisar_venta(row)
                if motivo:
                    sello = str(row.get("sello", "") or "").strip()
                    filas_alerta.append({
                        "Archivo"     : str(row.get("archivo", "")),
                        "Fecha"       : str(row.get("fecha", "")),
                        "Tipo"        : str(row.get("tipo", "")),
                        "Num Control" : str(row.get("num_control_raw", row.get("num_control", ""))),
                        "Cliente"     : str(row.get("nom_cli", "")),
                        "Sello"       : sello or "(vacío)",
                        "Motivo"      : motivo,
                    })
            if filas_alerta:
                df_alertas = pd.DataFrame(filas_alerta)
                st.warning(f"⚠️ **{len(df_alertas)} documento(s) requieren revisión**")
                st.dataframe(df_alertas, hide_index=True, use_container_width=True)
                csv_al = df_alertas.to_csv(index=False).encode("utf-8")
                st.download_button("📄 Exportar Alertas CSV", data=csv_al,
                    file_name="alertas_ventas.csv", mime="text/csv")
            else:
                st.success("✅ Todos los documentos pasaron la validación.")
        else:
            st.info("Sin datos procesados.")

    # ── Botón de descarga principal ────────────────────────────────────────────
    st.markdown("---")
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        if st.button("📥 Generar Archivos para Hacienda", type="primary", use_container_width=True):
            ventana_descarga_ventas(
                df_contribuyentes if not df_contribuyentes.empty else df_fil_contrib,
                df_consumidor     if not df_consumidor.empty else df_fil_cons,
                safe_str(cliente.get('nombre', '')).replace(' ', '_')
            )

else:
    st.markdown("""
    <div style="text-align:center; padding:60px 20px;">
        <h3 style="color:#6AB040 !important;">📂 Sin documentos cargados</h3>
        <p style="color:#3A5830 !important;">
            Usa el panel lateral para cargar y procesar PDFs de ventas.<br>
            Acepta: DTE-01 (Factura), DTE-03 (CCF), DTE-05 (NC), DTE-06 (ND)
        </p>
    </div>
    """, unsafe_allow_html=True)
