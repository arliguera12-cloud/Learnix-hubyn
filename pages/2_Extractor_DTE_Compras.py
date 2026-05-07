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
from utils.pdf_utils import (
    safe_str as _safe_str,
    safe_extract_text as _safe_extract_text,
    normalizar_unicode,
    limpiar_monto as _limpiar_monto,
    extraer_y_formatear_fecha as _extraer_fecha,
    extraer_texto_pdf,
)
from utils.gemini_utils import (
    es_nombre_sospechoso,
    verificar_compra_con_gemini,
    necesita_verificacion,
    gemini_disponible,
)
# Alias para compatibilidad con código existente
limpiar_monto             = _limpiar_monto
extraer_y_formatear_fecha = _extraer_fecha



# ─────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Extractor DTE · Compras", layout="wide", page_icon="🛒")

# ─────────────────────────────────────────────
# 2. ESTILOS
# ─────────────────────────────────────────────
st.markdown(DARK_PRO_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. SEGURIDAD
# ─────────────────────────────────────────────
if not st.session_state.get("autenticado"):
    st.warning("Acceso denegado. Por favor, inicia sesion en la pagina principal.")
    st.stop()
if not st.session_state.get("cliente_activo"):
    st.warning("Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Compras.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. CONSTANTES
# ─────────────────────────────────────────────
MAX_VALORES_LOOP = 40

TIPOS_VALIDOS_COMPRAS = {"03", "05", "06", "11", "14", "01"}

SKIP_LINEAS = re.compile(
    r'^(?:DOCUMENTO|TRIBUTARIO|ELECTR[OÓ]NICO|ELECTRONICO|COMPROBANTE|'
    r'CR[EÉ]DITO|CREDITO|FISCAL|C[OÓ]DIGO|CODIGO|SELLO|N[UÚ]MERO|NUMERO|'
    r'MODELO\s+DE|M[OÓ]DULO\s+DE|TIPO\s+DE|'
    r'FECHA\s*[:\s]|FECHA\s+Y\s+HORA|FECHA\s+PROCESADO|'
    r'RECEPTOR|EMISOR|CLIENTE|DTE-|'
    r'P[AÁ]GINA|PAGINA|VER\.|VERSI[OÓ]N|VERSION|[A-F0-9]{8}-|'
    r'\d{2}[/\-]\d{2}[/\-]\d{4}|\d{2}:\d{2}:\d{2})',
    re.I
)

BASURA_ESTRICTA = {"@", "EMAIL", "CORREO", ".COM", "WWW.", "HTTP", "FACTURA.GOB"}

PREFIJOS_DIRECCION = (
    "KM ", "KM.", "AV.", "AV ", "AVENIDA", "CALLE ", "PASAJE",
    "COLONIA", "COL.", "URB.", "URB ", "URBANIZACION", "URBANIZACIÓN",
    "RESIDENCIAL", "LOTIFICACION", "BARRIO", "CANTON", "CANTÓN",
    "CARRETERA", "CARR.", "BULEVAR", "BOULEVARD", "BLVD", "BLVD.",
    "POLIGONO", "LOCAL ", "NIVEL ", "PISO ", "EDIFICIO",
    "CENTRO COMERCIAL", "COMPLEJO", "PARQUE INDUSTRIAL",
    "FINAL ", "ENTRE ", "#", "NO.", "S/N",
)

PALABRAS_COMERCIALES = (
    "S.A.", "S.A.S.", "S DE R.L.", "LTDA.", "LTDA",
    "SOCIEDAD", "DISTRIBUIDORA", "FARMACIA", "GRUPO",
    "LABORATORIOS", "INDUSTRIAS", "SERVICIOS", "COMERCIAL",
    "IMPORTADORA", "EXPORTADORA", "CONSTRUCTORA", "CONSULTORES",
    "INVERSIONES", "ALIMENTOS", "TECNOLOGIA", "TECNOLOGÍA",
    "FERRETERIA", "FERRETERÍA", "ALMACENES", "TIENDA", "EMPRESA",
    "GRANJA", "GASOLINERA", "COMBUSTIBLE", "CLINICA", "HOSPITAL",
)

NOMBRES_INVALIDOS = {
    "MATRIZ", "LOCAL", "SUCURSAL", "AGENCIA", "OFICINA",
    "ESTABLECIMIENTO", "PUNTO DE VENTA", "ALMACEN", "BODEGA",
}

# CORREGIDO: patrón solo, se aplica con .sub("", s) en la función limpiar()
CORTE_NOMBRE = re.compile(
    r"\s*(?:NIT|NRC|GIRO|ACTIVIDAD|DIRECCI[OÓ]N|CORREO|TEL[EÉ]F|"
    r"TIPO\s+ESTAB|MUNICIPIO|DEPARTAMENTO|NUMERO\s+DE\s+CONTROL|"
    r"MODELO\s+DE|TIPO\s+DE\s+TRANS|N\.?\s*I\.?\s*T\.?\s*[:\s]|"
    r"N\.?\s*R\.?\s*C\.?\s*[:\s]|N[UÚ]MERO\s+DE|REGISTRO|PROCESAMIENTO|"
    r"\d{4}[\s\-]\d{6})"
    r".*$",
    re.I | re.S,
)

# ─────────────────────────────────────────────
# 5. UTILIDADES BÁSICAS
# ─────────────────────────────────────────────
# Delegadas a utils.pdf_utils
safe_str                  = _safe_str
safe_extract_text         = _safe_extract_text

def es_linea_direccion(texto: str) -> bool:
    L = safe_str(texto).upper().strip()
    return any(L.startswith(p) or (f" {p}" in L[:60]) for p in PREFIJOS_DIRECCION)




# ─────────────────────────────────────────────
# 6. DATA PERSISTENCE
# ─────────────────────────────────────────────
def cargar_proveedores_json() -> dict:
    for ruta in ("data/proveedores.json", "data/clientes.json"):
        if os.path.exists(ruta):
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, str):
                        data[k] = {"nombre": v, "nrc": ""}
                return data
            except Exception:
                pass
    return {}


def guardar_proveedor_rapido(nit: str, nombre: str) -> None:
    if not nit or not safe_str(nombre).strip():
        return
    ruta = "data/proveedores.json"
    if not os.path.exists("data"):
        os.makedirs("data")
    db  = cargar_proveedores_json()
    nrc = db.get(nit, {}).get("nrc", "") if isinstance(db.get(nit), dict) else ""
    db[nit] = {"nombre": safe_str(nombre).strip().upper(), "nrc": nrc}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)


def actualizar_nombre_en_db(nit: str, nombre: str) -> None:
    if not nit or not safe_str(nombre).strip():
        return
    df = st.session_state.get("db_compras", pd.DataFrame())
    if df.empty or "nit_prov" not in df.columns:
        return
    mask = df["nit_prov"] == nit
    if mask.any():
        st.session_state.db_compras.loc[mask, "nom_prov"] = safe_str(nombre).strip().upper()


# ─────────────────────────────────────────────
# 7. EXTRACCIÓN DE FECHA
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# 8. EXTRACCIÓN DE NOMBRE DEL EMISOR
# ─────────────────────────────────────────────
def extraer_nombre_emisor(texto: str, nit_prov: str, receptor_nombre: str) -> str:
    """
    Extrae el nombre del EMISOR (proveedor) del DTE.

    Bugs corregidos vs. versión original:
    - limpiar(): re.sub usaba `s` como patrón en lugar de "" como reemplazo.
    - Estrategia 1: el split cortaba el nombre antes de retornarlo.
    - Se agrega Estrategia 0: buscar entre sección [EMISOR] … [RECEPTOR].
    """
    texto       = safe_str(texto)
    receptor_up = safe_str(receptor_nombre).strip().upper()

    # ── Función interna de limpieza (CORREGIDA) ──────────────────────────────
    def limpiar(s: str) -> str:
        s = safe_str(s)
        # Quitar nombre del receptor si se coló
        if receptor_up and len(receptor_up) > 3:
            s = re.compile(re.escape(receptor_up), re.I).sub("", s)
        # Cortar en segunda ocurrencia de "Nombre o Razón" (layout columnar)
        partes = re.split(r'\s+[Nn]ombre\s+[Oo]\s+[Rr]az', s, maxsplit=1)
        s = partes[0]
        # Quitar etiquetas de campo al inicio
        s = re.sub(
            r'^[\s\-:]*(?:RAZ[OÓ]N\s*SOCIAL|NOMBRE(?:\s+O\s+RAZ[OÓ]N\s+SOCIAL)?|'
            r'NOMBRE\s+COMERCIAL|EMISOR|DATOS\s+DEL\s+EMISOR)[\s:]*',
            "", s, flags=re.I,           # ← CORREGIDO: reemplazo es "", no s
        ).strip()
        # CORTE_NOMBRE: quitar todo desde keywords contables en adelante
        s = CORTE_NOMBRE.sub("", s).strip()   # ← CORREGIDO: .sub("", s)
        s = re.sub(r'^[-_.,;:\s]+|[-_.,;:\s]+$', "", s)
        # Quitar NIT/NRC inline
        s = re.sub(r'\b(?:NIT|NRC)\s*:?\s*[\d\-]+', '', s, flags=re.I).strip()
        s = re.sub(r'\s{2,}', ' ', s)
        return s.upper()

    # ── Validador ─────────────────────────────────────────────────────────────
    def valido(s: str) -> bool:
        T = safe_str(s).strip().upper()
        if len(T) < 4 or len(T) > 90:
            return False
        if receptor_up and (T == receptor_up or T.startswith(receptor_up[:12])):
            return False
        if any(b in T for b in BASURA_ESTRICTA):
            return False
        if es_linea_direccion(T):
            return False
        if T in NOMBRES_INVALIDOS:
            return False
        digitos = sum(c.isdigit() for c in T)
        if len(T) > 0 and digitos / len(T) > 0.40:
            return False
        if re.fullmatch(r'[\d\s\-\.\/\(\)]+', T):
            return False
        if not re.search(r'[A-ZÁÉÍÓÚÑÜ]', T):
            return False
        if SKIP_LINEAS.match(T):
            return False
        return True

    # ── Estrategia 0: sección explícita [EMISOR] … [RECEPTOR] ────────────────
    # Busca un bloque etiquetado "EMISOR" y extrae el nombre dentro de él
    m_bloque = re.search(
        r'(?:DATOS\s+DEL\s+)?EMISOR\s*\n([\s\S]{10,400}?)(?:DATOS\s+DEL\s+)?(?:RECEPTOR|CLIENTE)',
        texto, re.I,
    )
    if m_bloque:
        bloque = m_bloque.group(1)
        for linea in bloque.split('\n'):
            l = safe_str(linea).strip()
            if not l or len(l) < 4:
                continue
            if SKIP_LINEAS.match(l):
                continue
            if any(b in l.upper() for b in BASURA_ESTRICTA):
                continue
            candidato = limpiar(l)
            if valido(candidato):
                return candidato

    # ── Estrategia 1: etiqueta "Nombre o Razón Social:" (primer match = emisor)
    # CORREGIDO: tomamos group(1) directamente sin re-split innecesario
    for m_nom in re.finditer(
        r'[Nn]ombre\s+[Oo]\s+[Rr]az[oó]n\s+[Ss]ocial\s*:\s*([^\n]{4,120})',
        texto,
    ):
        # Ignorar si el contexto anterior indica que es sección RECEPTOR
        ctx_prev = texto[max(0, m_nom.start() - 120):m_nom.start()].upper()
        if any(w in ctx_prev for w in ['RECEPTOR', 'CLIENTE', 'DATOS DEL RECEPTOR']):
            continue
        candidato = limpiar(m_nom.group(1))
        if valido(candidato):
            return candidato

    # ── Estrategia 2: texto antes del receptor ───────────────────────────────
    parte_emisor = texto
    for pat in [
        r'(?i)\bEMISOR\s+RECEPTOR\b',
        r'(?i)DATOS\s+DEL\s+RECEPTOR',
        r'(?i)DATOS\s+DEL\s+CLIENTE',
        r'(?i)\bRECEPTOR\b',
        r'(?i)\bCLIENTE\b',
    ]:
        parts = re.split(pat, texto, maxsplit=1)
        if len(parts) >= 2:
            parte_emisor = parts[0]
            break

    # ── Estrategia 3: palabras comerciales en bloque emisor ──────────────────
    for linea in parte_emisor.split('\n'):
        l = safe_str(linea).strip()
        if not l or len(l) < 4:
            continue
        if SKIP_LINEAS.match(l):
            continue
        if any(b in l.upper() for b in BASURA_ESTRICTA):
            continue
        tiene_comercial = any(w in l.upper() for w in PALABRAS_COMERCIALES)
        candidato = limpiar(l)
        if valido(candidato) and (tiene_comercial or len(candidato) >= 8):
            return candidato

    # ── Estrategia 4: primera línea no-metadata del documento ────────────────
    for linea in texto.split('\n')[:20]:
        l = safe_str(linea).strip()
        if not l or len(l) < 4:
            continue
        if SKIP_LINEAS.match(l):
            continue
        if any(b in l.upper() for b in BASURA_ESTRICTA):
            continue
        candidato = limpiar(l)
        if valido(candidato):
            return candidato

    # ── Estrategia 5: líneas anteriores al NIT del proveedor ─────────────────
    if nit_prov and len(nit_prov) >= 9:
        lineas = texto.split('\n')
        for i, linea in enumerate(lineas):
            if nit_prov in re.sub(r'[^0-9]', '', linea):
                for offset in [1, 2, 3]:
                    if i - offset >= 0:
                        candidato = limpiar(lineas[i - offset].strip())
                        if valido(candidato):
                            return candidato

    return ""


# ══════════════════════════════════════════════════════════════
# 9. EXTRACTOR PRINCIPAL DE COMPRAS
# ══════════════════════════════════════════════════════════════
def extraer_compra_nativo_pro(file_bytes: bytes, cliente_activo: dict, proveedores_db: dict = None) -> dict:
    """
    Extrae datos de un DTE de compra.
    Correcciones aplicadas:
    - Sello: regex sin \\b en t_no_sp (no funciona en strings sin espacios).
    - UUID fallback: separado del sello para no mezclar hex puro con alfanumérico.
    - Montos: loop de reconciliación O(n²) con índice de IVA, más rápido y preciso.
    - Sub-Total: patrón más restrictivo para no capturar subtotales de línea.
    - DTE-01 de compra: exentas = tot (sin IVA).
    """
    if not file_bytes or len(file_bytes) < 512:
        return {"error_fatal": "Archivo vacio o demasiado pequeño."}

    try:
        try:
            texto_lineal, texto_visual = extraer_texto_pdf(file_bytes)
        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
            return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
        except Exception as e:
            if "password" in str(e).lower() or "encrypt" in str(e).lower():
                return {"error_fatal": "PDF protegido con contraseña. Desbloquéalo antes de subir."}
            raise

        texto_completo = texto_lineal + "\n" + texto_visual

        if len(texto_completo.strip()) < 50:
            return {"error_fatal": "PDF de imagen sin texto extraible. Usa OCR."}

        t_clean = re.sub(r'[ \t]+', ' ', texto_completo)
        t_no_sp = re.sub(r'\s+', '', t_clean).upper()

        # ── Número de Control DTE ─────────────────────────────────────────────
        tipo        = ""
        ctrl        = ""
        num_control = ""

        m_ctrl = re.search(r'(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})', t_clean, re.I)
        if not m_ctrl:
            m_ctrl = re.search(r'(DTE-(\d{2})-[A-Z0-9]{1,20}-\d{12,18})', t_no_sp)

        if m_ctrl:
            ctrl = m_ctrl.group(1).upper()
            tipo = m_ctrl.group(2) if m_ctrl.lastindex and m_ctrl.lastindex >= 2 else ""
            if not tipo:
                m_tipo = re.search(r'DTE-(\d{2})', ctrl)
                tipo   = m_tipo.group(1) if m_tipo else ""
            num_control = ctrl.replace("-", "")

        if not ctrl:
            return {"error_tipo": "No se detecto Numero de Control DTE valido."}
        if tipo not in TIPOS_VALIDOS_COMPRAS:
            return {
                "error_tipo": (
                    f"DTE-{tipo} no admitido en compras. "
                    f"Validos: {', '.join(sorted(TIPOS_VALIDOS_COMPRAS))}."
                )
            }

        # ── Sello de Recepción ─────────────────────────────────────────────────
        # CORREGIDO: no usar \b en t_no_sp (cadena sin espacios).
        # Los sellos son ~40 chars alfanuméricos (pueden incluir Q,T,I,K…).
        sello = ""

        # Intento 1: etiqueta explícita en texto con espacios
        m_sello1 = re.search(
            r'[Ss]ello\s+(?:[Dd][Gg][Ii]|de\s+[Rr]ecepci[oó]n)\s*:?\s*([A-Z0-9]{30,50})',
            t_clean, re.I,
        )
        if m_sello1:
            sello = m_sello1.group(1)[:40]

        # Intento 2: año + 36 alfanuméricos en texto sin espacios (sin \b)
        if not sello:
            m_sello2 = re.search(r'(20[2-3]\d[A-Z0-9]{36})', t_no_sp)
            if m_sello2:
                sello = m_sello2.group(1)

        # Intento 3: buscar "SELLO" en t_no_sp y capturar lo que sigue
        if not sello:
            m_sello3 = re.search(r'SELLO[A-Z]*:?([A-Z0-9]{30,50})', t_no_sp)
            if m_sello3:
                sello = m_sello3.group(1)[:40]

        # ── Código de Generación (UUID) ────────────────────────────────────────
        # CORREGIDO: separado completamente del sello. UUID = hex puro 8-4-4-4-12.
        gen           = ""
        UUID_PATTERN  = (
            r'([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}'
            r'-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})'
        )

        # Con etiqueta
        m_gen1 = re.search(
            r'[Cc][oó]digo\s+(?:de\s+)?[Gg]eneraci[oó]n\s*:?\s*' + UUID_PATTERN,
            t_clean,
        )
        if m_gen1:
            gen = m_gen1.group(1).upper()

        # Sin etiqueta en texto con espacios
        if not gen:
            m_gen2 = re.search(UUID_PATTERN, t_clean)
            if m_gen2:
                gen = m_gen2.group(1).upper()

        # Fallback: buscar 32 hex puros en t_no_sp y formatear como UUID
        if not gen:
            m_gen3 = re.search(r'(?<![A-Z0-9])([0-9A-F]{32})(?![A-Z0-9])', t_no_sp)
            if m_gen3:
                raw = m_gen3.group(1)
                gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}".upper()

        gen_sin_guiones = gen.replace("-", "")

        # ── Fecha de emisión ────────────────────────────────────────────────────
        fecha = extraer_y_formatear_fecha(texto_lineal)
        if not fecha:
            fecha = extraer_y_formatear_fecha(texto_completo)

        # ── Datos del Receptor ─────────────────────────────────────────────────
        nit_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nit', '')))
        dui_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('dui', '')))
        nrc_receptor = re.sub(r'[^0-9]', '', safe_str(cliente_activo.get('nrc', '')))
        nom_receptor = safe_str(cliente_activo.get('nombre', '')).strip().upper()
        excluir_nits = {nit_receptor, dui_receptor, nrc_receptor} - {""}

        # ── NIT del Proveedor/Emisor ───────────────────────────────────────────
        nit_prov     = ""
        dui_prov     = ""
        nom_prov     = ""
        es_nuevo     = True
        if proveedores_db is None:
            proveedores_db = cargar_proveedores_json()

        # Separar sección EMISOR del texto
        parte_emisor = texto_lineal
        for pat in [
            r'(?i)\bEMISOR\s+RECEPTOR\b',
            r'(?i)DATOS\s+DEL\s+RECEPTOR',
            r'(?i)DATOS\s+DEL\s+CLIENTE',
            r'(?i)\bRECEPTOR\b',
            r'(?i)\bCLIENTE\b',
        ]:
            parts = re.split(pat, texto_lineal, maxsplit=1)
            if len(parts) >= 2:
                parte_emisor = parts[0]
                break

        PATRON_NIT = re.compile(
            r'N\.?\s*I\.?\s*T\.?\s*[:\s]\s*'
            r'((?:\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d)|\d{14})',
            re.I,
        )

        # Buscar NIT con etiqueta en sección emisor
        m_nit = PATRON_NIT.search(parte_emisor)
        if m_nit:
            nit_cand = re.sub(r'[^0-9]', '', m_nit.group(1))
            if nit_cand not in excluir_nits and len(nit_cand) == 14:
                nit_prov = nit_cand

        # Si no, buscar en todo el texto
        if not nit_prov:
            for m in PATRON_NIT.finditer(texto_completo):
                nit_cand = re.sub(r'[^0-9]', '', m.group(1))
                if nit_cand not in excluir_nits and len(nit_cand) == 14:
                    nit_prov = nit_cand
                    break

        # Fallback: cualquier número de 14 dígitos no excluido
        if not nit_prov:
            for m in re.finditer(
                r'\b(\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d|\d{14})\b', texto_completo
            ):
                nit_cand = re.sub(r'[^0-9]', '', m.group(0))
                if nit_cand not in excluir_nits and len(nit_cand) == 14:
                    nit_prov = nit_cand
                    break

        # DUI del proveedor (solo si no hay NIT)
        if not nit_prov:
            for m in re.finditer(r'\b(\d{8}[\s\-]?\d|\d{9})\b', parte_emisor):
                nit_cand = re.sub(r'[^0-9]', '', m.group(0))
                if nit_cand not in excluir_nits and len(nit_cand) == 9:
                    dui_prov = nit_cand
                    break

        # ── Nombre del Proveedor ───────────────────────────────────────────────
        id_lookup = nit_prov or dui_prov
        if id_lookup and id_lookup in proveedores_db:
            entrada = proveedores_db[id_lookup]
            nom_prov = safe_str(
                entrada.get("nombre", "") if isinstance(entrada, dict) else entrada
            )
            es_nuevo = False

        if es_nuevo:
            nombre_encontrado = extraer_nombre_emisor(texto_lineal, nit_prov, nom_receptor)
            if not nombre_encontrado:
                nombre_encontrado = extraer_nombre_emisor(texto_visual, nit_prov, nom_receptor)
            nom_prov = nombre_encontrado if nombre_encontrado else ""

        # ── Guard: emisor no puede ser el mismo que el receptor ──────────────
        if nit_prov and nit_prov == nit_receptor:
            nit_prov = ""
            nom_prov = ""

        # ── Verificación y corrección con Gemini ─────────────────────────────
        gemini_correcciones: list[str] = []
        if gemini_disponible():
            _campos_act = {"fecha": fecha, "nit_prov": nit_prov, "nom_prov": nom_prov}
            _necesita, _ = necesita_verificacion(_campos_act, nit_receptor)
            if _necesita:
                _corr_dict, gemini_correcciones = verificar_compra_con_gemini(
                    texto_lineal,
                    _campos_act,
                    nit_receptor,
                    nom_receptor,
                )
                if _corr_dict.get("fecha"):
                    fecha    = _corr_dict["fecha"]
                if _corr_dict.get("nom_prov"):
                    nom_prov = _corr_dict["nom_prov"]
                if _corr_dict.get("nit_prov"):
                    nit_prov = _corr_dict["nit_prov"]

        # ── FOVIAL y COTRANS ───────────────────────────────────────────────────
        fovial  = 0.0
        cotrans = 0.0
        m_fov = re.search(r'[Ff][Oo][Vv][Ii][Aa][Ll]\s*:?\s*\$?\s*(\d[\d,.]*)', t_clean)
        m_cot = re.search(r'[Cc][Oo][Tt][Rr][Aa][Nn][Ss]\s*:?\s*\$?\s*(\d[\d,.]*)', t_clean)
        if m_fov:
            fovial = limpiar_monto(m_fov.group(1))
        if m_cot:
            cotrans = limpiar_monto(m_cot.group(1))
        fovial_cotrans = round(fovial + cotrans, 2)

        # ── Exentas / No Sujetas ───────────────────────────────────────────────
        exe = 0.0
        for pat in [
            r'[Vv]tas?\.?\s+[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Vv]entas?\s+[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Tt]otal\s+[Ee]xento\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'\b[Ee]xentas?\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_exe = re.search(pat, t_clean)
            if m_exe:
                val = limpiar_monto(m_exe.group(1))
                if val > 0:
                    exe = val
                    break
        exe = max(exe, fovial_cotrans)

        # ── IVA Retenido ───────────────────────────────────────────────────────
        ret = 0.0
        for pat in [
            r'[Ii][Vv][Aa]\s+[Rr]etenido\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Rr]etenci[oó]n\s+[Ii][Vv][Aa]\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Rr]etenci[oó]n\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_ret = re.search(pat, t_clean)
            if m_ret:
                ret = limpiar_monto(m_ret.group(1))
                if ret > 0:
                    break

        # ── IVA Percibido ──────────────────────────────────────────────────────
        perc   = 0.0
        m_perc = re.search(
            r'[Ii][Vv][Aa]\s+[Pp]ercibido\s*:?\s*\$?\s*(\d[\d,.]+)', t_clean
        )
        if m_perc:
            perc = limpiar_monto(m_perc.group(1))

        # ── Total a Pagar ──────────────────────────────────────────────────────
        tot = 0.0
        for pat in [
            r'[Tt]otal\s+a\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Tt]otal\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Mm]onto\s+[Tt]otal\s+de\s+la\s+[Oo]peraci[oó]n\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Vv]alor\s+[Tt]otal\s+a\s+[Pp]agar\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Tt]OTAL\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_tot = re.search(pat, t_clean)
            if m_tot:
                tot = limpiar_monto(m_tot.group(1))
                if tot > 0:
                    break

        # ── IVA / Crédito Fiscal ───────────────────────────────────────────────
        iva = 0.0
        for pat in [
            r'[Ii]mpuesto\s+al\s+[Vv]alor\s+[Aa]gregado\s*13\s*%?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Ii]mpuesto\s+al\s+[Vv]alor\s+[Aa]gregado\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Ii][Vv][Aa]\s*13\s*%?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'13\s*%\s*[Ii][Vv][Aa]\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Cc]r[eé]dito\s+[Ff]iscal\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Dd][eé]bito\s+[Ff]iscal\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_iva = re.search(pat, t_clean)
            if m_iva:
                iva = limpiar_monto(m_iva.group(1))
                if iva > 0:
                    break

        # ── Gravadas ───────────────────────────────────────────────────────────
        gra = 0.0
        for pat in [
            r'[Vv]ta\.?\s+[Gg]ravada\s+[Nn]eta\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Vv]entas?\s+[Gg]ravadas?\s+[Ll]ocales?\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'[Tt]otal\s+[Gg]ravad[ao]\s*:?\s*\$?\s*(\d[\d,.]+)',
            r'\b[Gg]ravado\s*:?\s*(\d[\d,.]+)',
            r'[Ss]umatoria\s+de\s+[Vv]entas\s*:?\s*\$?\s*(\d[\d,.]+)',
            # CORREGIDO: Sub-Total solo cuando va seguido de dígito y es línea total,
            # no subtotales de items individuales (evitar capturar cantidades de línea)
            r'[Ss]ub[\s\-]?[Tt]otal\s+(?:[Gg]ravad[ao]|[Vv]entas?)\s*:?\s*\$?\s*(\d[\d,.]+)',
        ]:
            m_grav = re.search(pat, t_clean)
            if m_grav:
                gra = limpiar_monto(m_grav.group(1))
                if gra > 0:
                    break

        # ── Lógica de Reconciliación ───────────────────────────────────────────
        iva_calculado = False
        encontrado    = tot > 0 and iva > 0 and gra > 0

        # DTE-01 de compra: factura de sujeto excluido, sin crédito fiscal
        if not encontrado and tipo == "01":
            iva       = 0.0
            gra       = max(round(tot - exe, 2), 0.0)
            encontrado = tot > 0

        # DTE-14: sujeto excluido (igual, sin IVA)
        if not encontrado and tipo == "14":
            iva       = 0.0
            gra       = max(round(tot - exe, 2), 0.0)
            encontrado = tot > 0

        # ── Búsqueda por consistencia matemática (O(n²) con índice IVA) ────────
        # CORREGIDO: en lugar de triple loop O(n³), construir índice de IVA
        # para buscar pares (gravadas, iva) que cumplan la relación 13%.
        if not encontrado:
            montos_raw = re.findall(
                r'(?<![A-Z\-])(\d{1,3}(?:[,\.]\d{3})*[,\.]\d{2}|\d+\.\d{2}|\d+,\d{2})',
                t_clean,
            )
            set_montos: set[float] = set()
            for rv in montos_raw:
                v = limpiar_monto(rv)
                if 0.01 < v < 1_000_000:
                    set_montos.add(round(v, 2))

            valores = sorted(list(set_montos), reverse=True)[:MAX_VALORES_LOOP]
            # Construir set para búsqueda O(1)
            set_valores = set(valores)

            for vg in valores:
                vi_esperado = round(vg * 0.13, 2)
                # Tolerancia ±1 centavo
                for delta in [0, 0.01, -0.01, 0.02, -0.02]:
                    vi_cand = round(vi_esperado + delta, 2)
                    if vi_cand not in set_valores:
                        continue
                    vt_cand = round(vg + vi_cand + exe - ret + perc, 2)
                    # Buscar total dentro de ±0.10
                    for vt in valores:
                        if abs(vt - vt_cand) <= 0.10 and vt > vg:
                            gra       = vg
                            iva       = vi_cand
                            tot       = vt
                            encontrado = True
                            break
                    if encontrado:
                        break
                if encontrado:
                    break

        # ── Ajustes finales ───────────────────────────────────────────────────
        if not encontrado:
            if tot > 0 and iva > 0 and gra == 0.0:
                gra       = max(round(tot - iva - exe + ret - perc, 2), 0.0)
                encontrado = True
            elif tot > 0 and iva == 0.0 and gra == 0.0 and tipo == "03":
                gra           = round((tot - exe + ret - perc) / 1.13, 2)
                iva           = round(tot - exe + ret - perc - gra, 2)
                iva_calculado = True
                encontrado    = True
            elif tot == 0.0 and gra > 0 and iva > 0:
                tot = round(gra + iva + exe - ret + perc, 2)

        gra = max(gra, 0.0)
        iva = max(iva, 0.0)
        tot = max(tot, 0.0)

        return {
            "fecha"          : fecha,
            "tipo"           : tipo,
            "num_control"    : num_control,
            "num_control_raw": ctrl,
            "sello"          : sello,
            "gen"            : gen,
            "gen_sin_guiones": gen_sin_guiones,
            "nit_prov"       : nit_prov,
            "dui_prov"       : dui_prov,
            "nom_prov"       : nom_prov,
            "exe"            : round(exe,  2),
            "gra"            : round(gra,  2),
            "iva"            : round(iva,  2),
            "ret"            : round(ret,  2),
            "perc"           : round(perc, 2),
            "tot"            : round(tot,  2),
            "fovial"         : round(fovial,  2),
            "cotrans"        : round(cotrans, 2),
            "estado"              : "OK",
            "iva_calc"            : iva_calculado,
            "es_nuevo"            : es_nuevo,
            "gemini_correcciones" : gemini_correcciones,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error_fatal": "PDF invalido o con sintaxis corrupta."}
    except Exception as err:
        return {"error_extraccion": safe_str(err)}


# ─────────────────────────────────────────────
# 10. CONSTRUCCIÓN DEL DATAFRAME F-07 COMPRAS
# ─────────────────────────────────────────────
def construir_df_f07_compras(df_in: pd.DataFrame) -> pd.DataFrame:
    df_out = pd.DataFrame()
    df_out["A. Fecha Emisión"]           = df_in["fecha"]
    df_out["B. Clase Documento"]         = "4"
    df_out["C. Tipo Documento"]          = df_in["tipo"]
    df_out["D. Num Documento (UUID)"]    = df_in["gen_sin_guiones"].astype(str)
    df_out["E. NIT/NRC Proveedor"]       = df_in["nit_prov"].astype(str)
    df_out["F. Nombre Proveedor"]        = df_in["nom_prov"].astype(str)
    df_out["G. Compras Exentas/NS"]      = df_in["exe"]
    df_out["H. Internac. Exentas/NS"]    = 0.0
    df_out["I. Import. Exentas/NS"]      = 0.0
    df_out["J. Compras Gravadas"]        = df_in["gra"]
    df_out["K. Internac. Grav. Bienes"]  = 0.0
    df_out["L. Import. Grav. Bienes"]    = 0.0
    df_out["M. Import. Grav. Servicios"] = 0.0
    df_out["N. Crédito Fiscal (IVA)"]    = df_in["iva"]
    df_out["O. Total Compras"]           = df_in["tot"]
    df_out["P. DUI Proveedor"]           = df_in["dui_prov"].astype(str)
    df_out["Q. Tipo Operación"]          = "1"
    df_out["R. Clasificación"]           = "2"
    df_out["S. Sector"]                  = "4"
    df_out["T. Tipo Costo/Gasto"]        = "2"
    df_out["U. Num Anexo"]               = "3"
    return df_out


# ─────────────────────────────────────────────
# 11. EXPORTAR EXCEL HACIENDA
# ─────────────────────────────────────────────
def to_excel_hacienda_compras(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Compras_F07')
        ws     = writer.sheets['Compras_F07']
        anchos = [12,2,3,38,16,45,12,12,12,12,12,12,12,12,14,10,2,2,2,2,3]
        for idx_col, ancho in enumerate(anchos, start=1):
            ws.column_dimensions[ws.cell(1, idx_col).column_letter].width = ancho
        for fila in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=7, max_col=15):
            for celda in fila:
                if isinstance(celda.value, (int, float)):
                    celda.number_format = '#,##0.00'
    return output.getvalue()


@st.dialog("Confirmar Descarga de Compras")
def ventana_descarga_compras(df_f07: pd.DataFrame, nombre_archivo: str) -> None:
    st.write(
        "Verifica los totales. El archivo está listo para cargar en el portal "
        "de Hacienda como **Anexo 3**."
    )

    # Validación matemática: Gravadas + IVA + Exentas ≠ Total
    if "J. Compras Gravadas" in df_f07.columns and "O. Total Compras" in df_f07.columns:
        alertas_c = []
        for _, row in df_f07.iterrows():
            esperado = round(
                float(row.get("J. Compras Gravadas", 0))
                + float(row.get("N. Crédito Fiscal (IVA)", 0))
                + float(row.get("G. Compras Exentas/NS", 0)), 2
            )
            real = round(float(row.get("O. Total Compras", 0)), 2)
            if real > 0 and abs(esperado - real) > 0.50:
                alertas_c.append({"doc": row.get("D. Num Documento (UUID)", "—"), "diff": abs(esperado - real)})
        if alertas_c:
            with st.expander(f"⚠️ {len(alertas_c)} fila(s) con posible inconsistencia matemática"):
                for a in alertas_c[:8]:
                    st.markdown(
                        f'<div class="math-warn">📄 <code>{safe_str(a["doc"])[:20]}…</code> '
                        f'— diferencia: <strong>${a["diff"]:,.2f}</strong></div>',
                        unsafe_allow_html=True
                    )

    resumen_cols = {
        "G. Compras Exentas/NS"  : "Exentas/NS",
        "J. Compras Gravadas"    : "Gravadas",
        "N. Crédito Fiscal (IVA)": "IVA",
        "O. Total Compras"       : "Total",
    }
    col1, col2, col3, col4 = st.columns(4)
    for col_key, label, col_obj in zip(
        resumen_cols.keys(), resumen_cols.values(), [col1, col2, col3, col4]
    ):
        if col_key in df_f07.columns:
            col_obj.metric(label, f"${df_f07[col_key].sum():,.2f}")

    st.download_button(
        "📥 Confirmar y Descargar Anexo 3",
        data=to_excel_hacienda_compras(df_f07),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )


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


def datos_revision_vacio(causa: str = "") -> dict:
    return {
        "fecha": "", "tipo": "03",
        "num_control": "", "num_control_raw": "",
        "sello": "", "gen": "", "gen_sin_guiones": "",
        "nit_prov": "", "dui_prov": "", "nom_prov": "",
        "exe": 0.0, "gra": 0.0, "iva": 0.0,
        "ret": 0.0, "perc": 0.0, "tot": 0.0,
        "fovial": 0.0, "cotrans": 0.0,
        "estado": "REVISION", "iva_calc": False, "es_nuevo": True,
        "_error": safe_str(causa),
    }


def tipo_badge_compra(tipo: str) -> str:
    badges = {
        "03": "🟢 CCF (03)",
        "05": "🟠 Nota Crédito (05)",
        "06": "🔴 Nota Débito (06)",
        "01": "🔵 Factura (01)",
        "11": "🟡 Fac. Export. (11)",
        "14": "⚪ Suj. Excluido (14)",
    }
    return badges.get(tipo, f"📄 DTE-{tipo}")


# ─────────────────────────────────────────────
# 12. ENCABEZADO
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family:Courier New,monospace;color:#6AB040;"
        "letter-spacing:3px;margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True,
    )
with col_titulo:
    st.title("🛒 Extractor DTE — Compras")

st.markdown(f"""
<div class="card-emisor">
    <strong>RECEPTOR ACTIVO:</strong> {safe_str(cliente.get('nombre',''))}<br>
    <strong>NIT:</strong> {safe_str(cliente.get('nit',''))} &nbsp;|&nbsp;
    <strong>NRC:</strong> {safe_str(cliente.get('nrc',''))}
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 13. SESSION STATE
# ─────────────────────────────────────────────
if 'cola_revision'     not in st.session_state: st.session_state.cola_revision     = []
if 'comp_uploader_key' not in st.session_state: st.session_state.comp_uploader_key = 0
if 'db_compras'        not in st.session_state: st.session_state.db_compras        = pd.DataFrame()
if 'archivos_comp'     not in st.session_state: st.session_state.archivos_comp     = []
if 'reporte_compras'   not in st.session_state: st.session_state.reporte_compras   = None

# ─────────────────────────────────────────────
# 14. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga de Compras")
    st.markdown(
        "<small style='color:#6AB040'>Acepta: CCF (03), NC (05), ND (06), "
        "Fac. (01/11), Suj. Excluido (14)</small>",
        unsafe_allow_html=True,
    )
    st.divider()

    archivos = st.file_uploader(
        "Arrastra facturas de proveedores (PDF)",
        type="pdf",
        accept_multiple_files=True,
        key=str(st.session_state.comp_uploader_key),
    )

    procesar = st.button(
        "🚀 Procesar Compras",
        type="primary",
        use_container_width=True,
        disabled=not archivos,
    )

    if procesar and archivos:
        ya_procesados = set(st.session_state.archivos_comp)
        nuevos        = [f for f in archivos if f.name not in ya_procesados]

        if not nuevos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            _proveedores_db_cache = cargar_proveedores_json()  # carga única
            extracted, duplicados, iva_calc_files    = [], [], []
            invalidos, corruptos, nuevos_proveedores = [], [], {}

            bar          = st.progress(0)
            txt_progreso = st.empty()
            t_inicio     = time.time()
            total_arch   = len(nuevos)

            for idx, f in enumerate(nuevos):
                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                if idx > 0:
                    elapsed   = time.time() - t_inicio
                    remaining = int((elapsed / idx) * (total_arch - idx))
                    m_t, s_t  = divmod(remaining, 60)
                    txt_progreso.caption(
                        f"⏳ {idx+1}/{total_arch} — Restante: {m_t:02d}:{s_t:02d}"
                    )
                else:
                    txt_progreso.caption(f"⏳ Procesando 1 de {total_arch}...")

                file_bytes = f.read()

                if len(file_bytes) < 512:
                    corruptos.append(f.name)
                    st.session_state.archivos_comp.append(f.name)
                    bar.progress((idx + 1) / total_arch)
                    continue

                res = extraer_compra_nativo_pro(file_bytes, cliente, proveedores_db=_proveedores_db_cache)

                cod_gen  = safe_str(res.get('gen', ''))
                num_ctrl = safe_str(res.get('num_control', ''))
                dup_id   = cod_gen or num_ctrl

                dup_memoria = (
                    not st.session_state.db_compras.empty
                    and dup_id
                    and 'gen' in st.session_state.db_compras.columns
                    and (
                        (st.session_state.db_compras['gen'] == cod_gen).any()
                        if cod_gen else
                        (st.session_state.db_compras['num_control'] == num_ctrl).any()
                        if num_ctrl else False
                    )
                )
                dup_lote = dup_id and any(
                    (d.get('gen') == cod_gen and cod_gen)
                    or (d.get('num_control') == num_ctrl and num_ctrl)
                    for d in extracted
                )

                if "error_tipo" in res:
                    invalidos.append(f.name)
                elif dup_memoria or dup_lote:
                    duplicados.append(f.name)
                elif "error_fatal" in res:
                    corruptos.append(f.name)
                elif "error_extraccion" in res:
                    st.session_state.cola_revision.append({
                        "archivo": f.name,
                        "bytes"  : file_bytes,
                        "datos"  : datos_revision_vacio(res["error_extraccion"]),
                    })
                else:
                    nom_res     = safe_str(res.get('nom_prov', '')).strip()
                    va_revision = (
                        res.get('tot', 0.0) == 0.0
                        or not res.get('num_control')
                        or not safe_str(res.get('fecha', '')).strip()
                        or not nom_res
                    )

                    if va_revision:
                        st.session_state.cola_revision.append({
                            "archivo": f.name,
                            "bytes"  : file_bytes,
                            "datos"  : res,
                        })
                    else:
                        if res.get('iva_calc'):
                            iva_calc_files.append(f.name)
                        if res.get("es_nuevo") and (res.get("nit_prov") or res.get("dui_prov")):
                            id_prov = res.get("nit_prov") or res.get("dui_prov")
                            nuevos_proveedores[id_prov] = res["nom_prov"]
                            guardar_proveedor_rapido(id_prov, res["nom_prov"])
                        res["archivo"] = f.name
                        for col in ['gen_sin_guiones','num_control_raw','sello',
                                    'dui_prov','fovial','cotrans']:
                            if col not in res:
                                res[col] = ""
                        extracted.append(res)

                st.session_state.archivos_comp.append(f.name)
                bar.progress((idx + 1) / total_arch)

            txt_progreso.success(f"✅ {total_arch} facturas escaneadas.")

            st.session_state.reporte_compras = {
                "invalidos"         : invalidos,
                "duplicados"        : duplicados,
                "iva_calc"          : iva_calc_files,
                "nuevos_proveedores": nuevos_proveedores,
                "corruptos"         : corruptos,
            }

            if extracted:
                new_df = pd.DataFrame(extracted)
                for col in ['gen_sin_guiones','num_control_raw','sello',
                            'dui_prov','fovial','cotrans']:
                    if col not in new_df.columns:
                        new_df[col] = ""

                if st.session_state.db_compras.empty:
                    st.session_state.db_compras = new_df
                else:
                    st.session_state.db_compras = pd.concat(
                        [st.session_state.db_compras, new_df], ignore_index=True
                    )

    st.divider()
    if st.button("🧹 Limpiar Memoria Compras", type="secondary", use_container_width=True):
        for key in ('db_compras','archivos_comp','reporte_compras','cola_revision'):
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.comp_uploader_key = st.session_state.get('comp_uploader_key', 0) + 1
        st.rerun()

    if not st.session_state.db_compras.empty:
        df_sb  = st.session_state.db_compras
        n_ccf  = len(df_sb[df_sb['tipo'] == '03']) if 'tipo' in df_sb.columns else 0
        n_otros = len(df_sb) - n_ccf
        st.divider()
        st.markdown(f"**📄 Total docs:** `{len(df_sb)}`")
        st.markdown(f"**🟢 CCF (03):** `{n_ccf}` | **Otros:** `{n_otros}`")
        if 'tot' in df_sb.columns:
            st.markdown(f"**💰 Total Compras:** `${df_sb['tot'].sum():,.2f}`")
        if 'iva' in df_sb.columns:
            st.markdown(f"**🏦 Crédito Fiscal:** `${df_sb['iva'].sum():,.2f}`")


# ─────────────────────────────────────────────
# 15. BANDEJA DE REVISIÓN MANUAL
# ─────────────────────────────────────────────
if st.session_state.cola_revision:
    st.markdown("""
    <div class="inbox-revision">
        <h3>📥 Bandeja de Revisión Manual</h3>
        <p>Datos incompletos o fallo de extracción. Revisa y corrige antes de agregar al libro.</p>
    </div>
    """, unsafe_allow_html=True)

    total_cola = len(st.session_state.cola_revision)

    _, col_nav2, _ = st.columns([1, 3, 1])
    with col_nav2:
        st.info(
            f"📄 Documento **1 de {total_cola}** en revisión | "
            f"Quedan **{total_cola}** por revisar"
        )

    with st.expander("🗑️ Gestión masiva"):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("🗑️ Descartar TODOS los pendientes", type="secondary", use_container_width=True):
                st.session_state.cola_revision = []
                st.rerun()
        with col_m2:
            st.caption(f"Total en cola: {total_cola} documentos")

    item_actual = st.session_state.cola_revision[0]
    datos_act   = item_actual["datos"]
    tipo_actual = safe_str(datos_act.get("tipo", "03"))

    st.divider()
    col_img, col_form = st.columns([1.2, 1], gap="large")

    with col_img:
        try:
            with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                img = pdf.pages[0].to_image(resolution=200).original
                st.image(img, caption=item_actual['archivo'], use_container_width=True)
                texto_crudo = ""
                for page in pdf.pages:
                    texto_crudo += safe_extract_text(page, layout=True) + "\n"

                with st.expander("🔍 Datos extraídos automáticamente"):
                    # ── Indicador Gemini ──────────────────────────────────────
                    _g_corr = datos_act.get("gemini_correcciones", [])
                    if _g_corr:
                        st.markdown(
                            "⚡ **Gemini corrigió:** " +
                            " · ".join(f"`{c}`" for c in _g_corr),
                            help="Correcciones aplicadas automáticamente por Gemini 1.5 Flash"
                        )
                    elif gemini_disponible():
                        st.caption("⚡ Gemini activo — datos verificados sin correcciones")
                    else:
                        st.caption("🔌 Gemini no configurado — extracción solo por regex")

                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.caption(f"**Tipo:** `{tipo_badge_compra(tipo_actual)}`")
                        st.caption(f"**Ctrl:** `{datos_act.get('num_control_raw', datos_act.get('num_control','—'))}`")
                        st.caption(f"**UUID:** `{datos_act.get('gen','—')}`")
                        st.caption(f"**Sello:** `{datos_act.get('sello','—')}`")
                        st.caption(f"**Fecha:** `{datos_act.get('fecha','—')}`")
                    with col_d2:
                        st.caption(f"**NIT prov:** `{datos_act.get('nit_prov','—')}`")
                        st.caption(f"**Nombre:** `{datos_act.get('nom_prov','—')}`")
                        st.caption(f"**Total:** `${datos_act.get('tot',0):.2f}`")
                        st.caption(f"**Gravadas:** `${datos_act.get('gra',0):.2f}`")
                        st.caption(f"**IVA:** `${datos_act.get('iva',0):.2f}`")
                        st.caption(
                            f"**Exentas:** `${datos_act.get('exe',0):.2f}` "
                            f"(Fov: {datos_act.get('fovial',0):.2f} | "
                            f"Cot: {datos_act.get('cotrans',0):.2f})"
                        )
                        err = datos_act.get('_error', '')
                        if err:
                            st.caption(f"**⚠️ Error:** `{err}`")

                st.markdown("**📝 Texto extraído:**")
                st.text_area(
                    "", value=texto_crudo.strip(),
                    height=220, label_visibility="collapsed"
                )
        except Exception as ex_prev:
            st.error(f"Vista previa no disponible: {safe_str(ex_prev)}")

    with col_form:
        st.markdown("### ✍️ Corrección Manual")

        with st.form(key=f"form_rev_c_{item_actual['archivo']}"):
            st.markdown("**📋 Identificación**")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_fecha = st.text_input(
                    "📅 Fecha (DD/MM/YYYY) *",
                    value=safe_str(datos_act.get("fecha", "")),
                    placeholder="14/04/2026",
                )
                tipos_op = ["03","05","06","01","11","14"]
                tipo_idx = tipos_op.index(tipo_actual) if tipo_actual in tipos_op else 0
                f_tipo   = st.selectbox("📄 Tipo DTE", options=tipos_op, index=tipo_idx)
            with col_f2:
                f_ctrl = st.text_input(
                    "🔢 Número de Control DTE *",
                    value=safe_str(datos_act.get("num_control_raw", datos_act.get("num_control",""))),
                    placeholder="DTE-03-M001P003-000000000005389",
                )
                f_gen = st.text_input(
                    "🔑 UUID / Código de Generación",
                    value=safe_str(datos_act.get("gen", "")),
                    placeholder="D5DD509F-AF83-4F12-9F52-0B06F528F3E2",
                )

            f_sello = st.text_input(
                "🛡️ Sello de Recepción",
                value=safe_str(datos_act.get("sello", "")),
                placeholder="2026909C551E98104C669F113E36495EFC10AQC7",
            )

            st.markdown("**🏢 Proveedor / Emisor**")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                f_nit = st.text_input(
                    "🆔 NIT del Proveedor",
                    value=safe_str(datos_act.get("nit_prov", "")),
                    placeholder="06141911921043",
                )
            with col_r2:
                f_dui = st.text_input(
                    "🪪 DUI (si persona natural)",
                    value=safe_str(datos_act.get("dui_prov", "")),
                    placeholder="opcional",
                )
            f_nom = st.text_input(
                "🏢 Razón Social del Proveedor *",
                value=safe_str(datos_act.get("nom_prov", "")),
                placeholder="GRANJA SAN DIEGO, S.A. DE C.V.",
            )

            st.markdown("**💰 Montos**")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                f_tot = st.number_input(
                    "💰 Total a Pagar ($) *",
                    value=float(datos_act.get("tot", 0.0)),
                    format="%.2f", min_value=0.0,
                )
            with col_m2:
                f_gra = st.number_input(
                    "🧾 Compra Gravada ($)",
                    value=float(datos_act.get("gra", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Sin IVA. Dejar en 0 para calcular.",
                )
            with col_m3:
                f_iva = st.number_input(
                    "🏦 IVA Crédito Fiscal ($)",
                    value=float(datos_act.get("iva", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Dejar en 0 para calcular (13% de gravadas).",
                )

            col_m4, col_m5 = st.columns(2)
            with col_m4:
                f_exe = st.number_input(
                    "⛽ Compras Exentas/NS ($)",
                    value=float(datos_act.get("exe", 0.0)),
                    format="%.2f", min_value=0.0,
                    help="Incluye Fovial + Cotrans para combustible.",
                )
            with col_m5:
                f_ret = st.number_input(
                    "🔻 IVA Retenido ($)",
                    value=float(datos_act.get("ret", 0.0)),
                    format="%.2f", min_value=0.0,
                )

            if f_tot > 0:
                gra_p = f_gra if f_gra > 0 else round((f_tot - f_exe + f_ret) / 1.13, 2)
                iva_p = f_iva if f_iva > 0 else round(gra_p * 0.13, 2)
                st.caption(
                    f"📊 Preview: Gravadas `${gra_p:.2f}` | IVA `${iva_p:.2f}` | "
                    f"Exentas `${f_exe:.2f}` | Total `${f_tot:.2f}`"
                )

            actualizar_otros = st.checkbox(
                "🔄 Actualizar nombre en todos los registros del proveedor", value=True
            )

            st.markdown("")
            b1, b2, b3 = st.columns([2, 1, 1])
            with b1:
                submit_ok   = st.form_submit_button(
                    "✅ Aprobar y Agregar", type="primary", use_container_width=True
                )
            with b2:
                submit_skip = st.form_submit_button("⏭️ Saltar", use_container_width=True)
            with b3:
                submit_del  = st.form_submit_button("🗑️ Descartar", use_container_width=True)

            if submit_ok:
                errores = []
                if not f_fecha.strip():
                    errores.append("Fecha requerida.")
                if not f_ctrl.strip():
                    errores.append("Número de Control requerido.")
                if not f_nom.strip():
                    errores.append("Razón Social del Proveedor requerida.")
                if f_tot <= 0:
                    errores.append("Total debe ser mayor a 0.")
                if f_fecha.strip() and not re.match(r'\d{2}/\d{2}/\d{4}', f_fecha.strip()):
                    errores.append("Formato de fecha inválido. Use DD/MM/YYYY.")

                if errores:
                    for e_msg in errores:
                        st.error(e_msg)
                else:
                    nombre_limpio = f_nom.strip().upper()
                    nit_act       = f_nit.strip()
                    dui_act       = re.sub(r'[^0-9]', '', f_dui.strip()) if f_dui.strip() else ""
                    ctrl_raw      = f_ctrl.strip().upper()
                    ctrl_limpio   = ctrl_raw.replace("-", "")
                    gen_raw       = f_gen.strip().upper()
                    gen_sin_g     = gen_raw.replace("-", "")
                    id_guardar    = nit_act or dui_act

                    if id_guardar:
                        guardar_proveedor_rapido(id_guardar, nombre_limpio)

                    # Propagar nombre a cola pendiente
                    for item_pend in st.session_state.cola_revision[1:]:
                        if item_pend["datos"].get("nit_prov") == nit_act and nit_act:
                            item_pend["datos"]["nom_prov"] = nombre_limpio
                            item_pend["datos"]["es_nuevo"] = False

                    if actualizar_otros and id_guardar:
                        actualizar_nombre_en_db(id_guardar, nombre_limpio)

                    gra_f = f_gra
                    iva_f = f_iva
                    ic    = datos_act.get("iva_calc", False)

                    if f_tot > 0 and gra_f == 0.0 and iva_f == 0.0:
                        gra_f = round((f_tot - f_exe + f_ret) / 1.13, 2)
                        iva_f = round(f_tot - f_exe + f_ret - gra_f, 2)
                        ic    = True
                    elif f_tot > 0 and iva_f == 0.0 and gra_f > 0.0:
                        iva_f = round(gra_f * 0.13, 2)
                        ic    = True
                      
                    datos_act.update({
                        "fecha"          : f_fecha.strip(),
                        "tipo"           : f_tipo,
                        "num_control"    : ctrl_limpio,
                        "num_control_raw": ctrl_raw,
                        "sello"          : f_sello.strip().upper(),
                        "gen"            : gen_raw,
                        "gen_sin_guiones": gen_sin_g,
                        "nit_prov"       : nit_act,
                        "dui_prov"       : dui_act,
                        "nom_prov"       : nombre_limpio,
                        "exe"            : f_exe,
                        "gra"            : gra_f,
                        "iva"            : iva_f,
                        "ret"            : f_ret,
                        "perc"           : float(datos_act.get("perc", 0.0)),
                        "tot"            : f_tot,
                        "fovial"         : float(datos_act.get("fovial", 0.0)),
                        "cotrans"        : float(datos_act.get("cotrans", 0.0)),
                        "iva_calc"       : ic,
                        "es_nuevo"       : False,
                        "archivo"        : item_actual["archivo"],
                        "estado"         : "OK",
                    })

                    nuevo_df = pd.DataFrame([datos_act])
                    # Asegurar columnas necesarias
                    for col in ['gen_sin_guiones','num_control_raw','sello',
                                'dui_prov','fovial','cotrans']:
                        if col not in nuevo_df.columns:
                            nuevo_df[col] = ""

                    if st.session_state.db_compras.empty:
                        st.session_state.db_compras = nuevo_df
                    else:
                        st.session_state.db_compras = pd.concat(
                            [st.session_state.db_compras, nuevo_df], ignore_index=True
                        )

                    # Registrar en reporte de nuevos proveedores
                    if id_guardar:
                        rep_act = st.session_state.get("reporte_compras") or {}
                        np_dict = rep_act.get("nuevos_proveedores", {})
                        np_dict[id_guardar] = nombre_limpio
                        if st.session_state.reporte_compras:
                            st.session_state.reporte_compras["nuevos_proveedores"] = np_dict
                        else:
                            st.session_state.reporte_compras = {
                                "invalidos": [], "duplicados": [], "iva_calc": [],
                                "nuevos_proveedores": np_dict, "corruptos": [],
                            }

                    st.session_state.cola_revision.pop(0)
                    st.success("✅ Documento aprobado y agregado al libro.")
                    time.sleep(0.5)
                    st.rerun()

            if submit_skip:
                item = st.session_state.cola_revision.pop(0)
                st.session_state.cola_revision.append(item)
                st.rerun()

            if submit_del:
                st.session_state.cola_revision.pop(0)
                st.rerun()

    st.stop()


# ─────────────────────────────────────────────
# 16. REPORTE DE PROCESAMIENTO
# ─────────────────────────────────────────────
if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### 📋 Alertas de Procesamiento")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        alerta_con_lista(
            "error" if rep.get("corruptos") else "success",
            "💀", "Dañados", rep.get("corruptos", [])
        )
    with c2:
        alerta_con_lista(
            "warning" if rep.get("invalidos") else "success",
            "⚠️", "Ignorados (tipo incorrecto)", rep.get("invalidos", [])
        )
    with c3:
        alerta_con_lista(
            "error" if rep.get("duplicados") else "success",
            "🛑", "Duplicados", rep.get("duplicados", [])
        )
    with c4:
        alerta_con_lista(
            "info" if rep.get("iva_calc") else "success",
            "🧮", "IVA Calculado (estimado)", rep.get("iva_calc", [])
        )

    np_dict = rep.get("nuevos_proveedores", {})
    if np_dict:
        st.markdown(f"**🆕 Proveedores nuevos guardados:** `{len(np_dict)}`")
        with st.expander("Ver proveedores registrados"):
            for nit_k, nom_k in np_dict.items():
                st.markdown(f"- `{nit_k}` — **{nom_k}**")

    st.divider()


# ─────────────────────────────────────────────
# 17. TABLA PRINCIPAL Y EXPORT
# ─────────────────────────────────────────────
if not st.session_state.db_compras.empty:
    df = st.session_state.db_compras.copy()

    # Asegurar columnas necesarias con valores por defecto
    COLS_REQUERIDAS = {
        'gen_sin_guiones': "", 'num_control_raw': "", 'sello'  : "",
        'dui_prov'       : "", 'fovial'         : 0.0,'cotrans': 0.0,
        'num_control'    : "", 'gen'             : "", 'ret'    : 0.0,
        'perc'           : 0.0,'exe'             : 0.0,'gra'   : 0.0,
        'iva'            : 0.0,'tot'             : 0.0,
    }
    for col, default in COLS_REQUERIDAS.items():
        if col not in df.columns:
            df[col] = default

    # ── Panel de Filtros Avanzado ────────────────────────────────────────────
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    st.markdown('<span class="filter-title">🔍 Filtros de Auditoría — F-07 Compras</span>', unsafe_allow_html=True)

    fc1, fc2 = st.columns([3, 1])
    with fc1:
        busqueda = st.text_input(
            "busqueda_c", label_visibility="collapsed",
            placeholder="Buscar por nombre, NIT, DUI, Núm. Control o UUID…"
        )
    with fc2:
        tipos_disponibles = sorted(df['tipo'].unique().tolist()) if 'tipo' in df.columns else []
        filtro_tipo = st.multiselect(
            "Tipo DTE", options=tipos_disponibles,
            default=tipos_disponibles, placeholder="Todos los tipos"
        )

    fd1, fd2, fd3, fd4 = st.columns(4)
    with fd1:
        fecha_desde = st.date_input("Desde", value=None, format="DD/MM/YYYY", key="cmp_fd")
    with fd2:
        fecha_hasta = st.date_input("Hasta", value=None, format="DD/MM/YYYY", key="cmp_fh")
    with fd3:
        monto_min = st.number_input("Monto mín. ($)", min_value=0.0, value=0.0, step=10.0, key="cmp_mm")
    with fd4:
        monto_max = st.number_input("Monto máx. ($)", min_value=0.0, value=0.0, step=100.0,
                                     key="cmp_mx", help="0 = sin límite superior")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Aplicar filtros ──────────────────────────────────────────────────────
    df_filtrado = df.copy()

    if busqueda:
        t_bus = busqueda.strip()
        mask = (
            df_filtrado['nom_prov'].str.contains(t_bus, case=False, na=False)    |
            df_filtrado['nit_prov'].str.contains(t_bus, case=False, na=False)    |
            df_filtrado['dui_prov'].str.contains(t_bus, case=False, na=False)    |
            df_filtrado['gen'].str.contains(t_bus, case=False, na=False)         |
            df_filtrado['num_control'].str.contains(t_bus, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask]

    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]

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

    if 'tot' in df_filtrado.columns:
        if monto_min > 0:
            df_filtrado = df_filtrado[df_filtrado['tot'] >= monto_min]
        if monto_max > 0:
            df_filtrado = df_filtrado[df_filtrado['tot'] <= monto_max]

    # ── Badge de resultados ──────────────────────────────────────────────────
    n_tot = len(df)
    n_fil = len(df_filtrado)
    filtros_activos = sum([
        bool(busqueda),
        bool(filtro_tipo and len(filtro_tipo) < len(tipos_disponibles)),
        bool(fecha_desde), bool(fecha_hasta),
        bool(monto_min > 0), bool(monto_max > 0),
    ])
    badge_extra = (f'<span class="active-filters"> · {filtros_activos} filtro(s) activo(s)</span>'
                   if filtros_activos else "")
    st.markdown(
        f'<div class="results-badge"><span class="cnt">{n_fil}</span> de {n_tot} registros{badge_extra}</div>',
        unsafe_allow_html=True
    )
    st.markdown("")

    tab1, tab2, tab3 = st.tabs([
        "📊 Libro F-07 Compras (Anexo 3)",
        "🔍 Auditoría Completa",
        "📈 Resumen por Proveedor",
    ])

    # ── Tab 1: F-07 ───────────────────────────────────────────────────────────
    with tab1:
        if not df_filtrado.empty:
            df_f07    = construir_df_f07_compras(df_filtrado)
            COLS_NUM  = [c for c in df_f07.columns if df_f07[c].dtype == float]

            st.dataframe(
                df_f07.style.format({c: "{:,.2f}" for c in COLS_NUM}),
                hide_index=True,
                use_container_width=True,
            )

            # Resumen de totales
            ETIQUETAS = {
                "G. Compras Exentas/NS"  : "Exentas/NS",
                "J. Compras Gravadas"    : "Gravadas",
                "N. Crédito Fiscal (IVA)": "IVA",
                "O. Total Compras"       : "Total General",
            }
            partes = []
            for col_key, etiqueta in ETIQUETAS.items():
                if col_key in df_f07.columns:
                    suma = df_f07[col_key].sum()
                    if suma > 0 or etiqueta == "Total General":
                        partes.append(f"**{etiqueta}:** `${suma:,.2f}`")
            if partes:
                st.markdown("> " + " &nbsp;|&nbsp; ".join(partes))

            st.markdown("---")
            st.caption(
                "ℹ️ **Columnas Q-T** (Tipo Operación, Clasificación, Sector, Tipo Costo/Gasto) "
                "tienen valores por defecto. Ajústalos según la naturaleza del gasto "
                "antes de subir a Hacienda."
            )

            if st.button("📥 Generar Excel para Hacienda", type="primary"):
                ventana_descarga_compras(
                    df_f07,
                    f"F07_Compras_{safe_str(cliente.get('nombre','')).replace(' ','_')}.xlsx",
                )
        else:
            st.info("Sin compras que mostrar con el filtro actual.")

    # ── Tab 2: Auditoría Completa ─────────────────────────────────────────────
    with tab2:
        st.write(f"📊 Registros: **{len(df_filtrado)}** de **{len(df)}**")

        cols_auditoria = [
            'fecha', 'tipo', 'nom_prov', 'nit_prov', 'dui_prov',
            'exe', 'gra', 'iva', 'ret', 'perc', 'tot',
            'fovial', 'cotrans', 'sello', 'gen', 'num_control_raw', 'archivo',
        ]
        cols_disp = [c for c in cols_auditoria if c in df_filtrado.columns]

        COLS_NUM_AUD = ['exe','gra','iva','ret','perc','tot','fovial','cotrans']
        cols_fmt     = {c: "{:,.2f}" for c in COLS_NUM_AUD if c in df_filtrado.columns}

        st.dataframe(
            df_filtrado[cols_disp].style.format(cols_fmt),
            use_container_width=True,
            hide_index=True,
        )

        # Mini-descarga de auditoría en CSV
        csv_bytes = df_filtrado[cols_disp].to_csv(index=False).encode("utf-8")
        st.download_button(
            "📄 Descargar Auditoría CSV",
            data=csv_bytes,
            file_name=f"auditoria_compras_{safe_str(cliente.get('nombre','')).replace(' ','_')}.csv",
            mime="text/csv",
        )

    # ── Tab 3: Resumen por Proveedor ──────────────────────────────────────────
    with tab3:
        if not df_filtrado.empty:
            resumen = (
                df_filtrado
                .groupby('nom_prov', as_index=False)
                .agg(
                    Docs    =('tot',     'count'),
                    NIT     =('nit_prov','first'),
                    DUI     =('dui_prov','first'),
                    Exentas =('exe',     'sum'),
                    Gravadas=('gra',     'sum'),
                    IVA     =('iva',     'sum'),
                    Total   =('tot',     'sum'),
                )
            )
            resumen.columns = [
                'Proveedor','Docs','NIT','DUI',
                'Exentas','Gravadas','IVA','Total'
            ]
            resumen = resumen.sort_values('Total', ascending=False)

            COLS_MONTO = ['Exentas','Gravadas','IVA','Total']
            st.dataframe(
                resumen.style.format({c: "${:,.2f}" for c in COLS_MONTO}),
                hide_index=True,
                use_container_width=True,
            )

            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            col_r1.metric("Proveedores",    f"{resumen.shape[0]}")
            col_r2.metric("Total Compras",  f"${df_filtrado['tot'].sum():,.2f}")
            col_r3.metric("Crédito Fiscal", f"${df_filtrado['iva'].sum():,.2f}")
            col_r4.metric("Exentas/NS",     f"${df_filtrado['exe'].sum():,.2f}")
        else:
            st.info("Sin datos para mostrar con el filtro actual.")

else:
    # ── Estado vacío ──────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center; padding:60px 20px;">
        <h3 style="color:#6AB040 !important;">📂 Sin documentos cargados</h3>
        <p style="color:#3A5830 !important;">
            Usa el panel lateral para cargar y procesar PDFs de compras.<br>
            Acepta: CCF (03), NC (05), ND (06), Factura (01/11), Suj. Excluido (14)
        </p>
    </div>
    """, unsafe_allow_html=True)

