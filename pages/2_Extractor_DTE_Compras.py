import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import json
import os
import gc
from io import BytesIO

# ─────────────────────────────────────────────
# 1. PAGE CONFIG — SIEMPRE PRIMERO
# ─────────────────────────────────────────────
st.set_page_config(page_title="Extractor DTE · Compras", layout="wide", page_icon="🛒")

# ─────────────────────────────────────────────
# 2. ESTILOS — VERDE OLIVA UNIFICADO
# ─────────────────────────────────────────────
ESTILO = """
<style>
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"]          { background-color: #0D0F07 !important; }
  [data-testid="stSidebar"]         { background-color: #141A08 !important;
                                      border-right: 1px solid #4A5520 !important; }

  h1, h2, h3, h4, h5, h6           { color: #C8D87A !important; letter-spacing: 0.5px; }
  p, label, span, li                { color: #F0EDD8 !important; }
  [data-testid="stDataFrame"] span  { color: inherit !important; }

  div.stButton > button[kind="primary"],
  div.stDownloadButton > button[kind="primary"] {
    background-color : #6B7A2A !important;
    border           : 1px solid #8A9A35 !important;
    border-radius    : 6px !important;
    transition       : background-color 0.25s ease, transform 0.1s ease;
  }
  div.stButton > button[kind="primary"]:hover,
  div.stDownloadButton > button[kind="primary"]:hover {
    background-color : #8A9A35 !important;
    transform        : scale(1.02);
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #FFFFFF !important; font-weight: bold !important;
  }

  div.stButton > button[kind="secondary"] {
    background-color : transparent !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    transition       : 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover { background-color: #1A2008 !important; }
  div.stButton > button[kind="secondary"] *     { color: #C8D87A !important; }

  div[data-testid="stTextInput"] input,
  div[data-testid="stNumberInput"] input {
    background-color : #1A2008 !important;
    border           : 1px solid #4A5520 !important;
    border-radius    : 6px !important;
    color            : #F0EDD8 !important;
    caret-color      : #C8D87A;
  }
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stNumberInput"] input:focus {
    border-color : #8A9A35 !important;
    box-shadow   : 0 0 0 2px rgba(138,154,53,0.25) !important;
  }

  button[data-baseweb="tab"]                       { color: #8A9A35 !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom : 2px solid #8A9A35 !important;
    color         : #F0EDD8 !important;
  }

  div[data-testid="stAlert"]  { display: flex; align-items: center; min-height: 56px; }
  hr                          { border-color: #4A5520 !important; opacity: 0.4; }

  .card-emisor {
    padding          : 12px 16px;
    border-radius    : 8px;
    border-left      : 4px solid #8A9A35;
    background-color : #1A2008;
    color            : #F0EDD8 !important;
    margin-bottom    : 18px;
    font-size        : 14px;
    line-height      : 1.6;
    border           : 1px solid #2A3010;
    border-left      : 4px solid #8A9A35;
  }
  .card-emisor strong { color: #C8D87A !important; }

  .scroll-list {
    max-height       : 150px;
    overflow-y       : auto;
    padding          : 8px 12px;
    background-color : #1A2008;
    border-radius    : 6px;
    border           : 1px solid #2A3010;
    font-family      : monospace;
    font-size        : 12px;
    color            : #A8BB45;
  }

  .inbox-revision {
    background-color : #1A2008;
    border           : 1px solid #8A9A35;
    border-radius    : 10px;
    padding          : 20px;
    margin-top       : 20px;
    margin-bottom    : 20px;
  }
  .inbox-revision h3 { color: #C8D87A !important; margin-top: 0; }
  .inbox-revision p  { color: #8A9A35 !important; }
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. VERIFICACIÓN DE SEGURIDAD
# ─────────────────────────────────────────────
if not st.session_state.get("autenticado"):
    st.warning("⚠️ Acceso denegado. Por favor, inicia sesión en la página principal.")
    st.stop()

if not st.session_state.get("cliente_activo"):
    st.warning("⚠️ Debes seleccionar un Cliente Activo en el Dashboard antes de extraer Compras.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. CONSTANTES
# ─────────────────────────────────────────────
MAX_VALORES_LOOP = 30   # Límite O(n³) controlado
PALABRAS_BASURA  = [
    "DOCUMENTO", "TRIBUTARIO", "ELECTRÓNICO", "REPRESENTACIÓN", "RECEPTOR",
    "CLIENTE", "EMISOR", "FACTURA", "CONSUMIDOR", "COMPROBANTE", "CÓDIGO",
    "SELLO", "VERSIÓN", "TRANSMISIÓN", "MINISTERIO", "HACIENDA", "COLONIA",
    "BOULEVARD", "CALLE", "AVENIDA", "MUNICIPIO", "GIRO:", "ACTIVIDAD",
    "ECONOMICA", "SUCURSAL", "AGENCIA", "EFECTIVO", "FECHA", "HORA",
    "EMISIÓN", "GENERACIÓN", "TELÉFONO"
]
BASURA_ESTRICTA  = ["@", "EMAIL", "CORREO", ".COM", "WWW."]
PALABRAS_COMERCIALES = [
    "S.A.", "SA ", "C.V.", "CV ", "LTDA.", "LTDA", "SOCIEDAD",
    "DISTRIBUIDORA", "FARMACIA", "GRUPO", "LABORATORIOS", "INDUSTRIAS"
]

# ─────────────────────────────────────────────
# 5. FUNCIONES AUXILIARES
# ─────────────────────────────────────────────
def cargar_proveedores_json() -> dict:
    archivo = "data/proveedores.json"
    if not os.path.exists(archivo):
        return {}
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Migración formato antiguo (valor string → dict)
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = {"nombre": v, "nrc": ""}
        return data
    except Exception:
        return {}


def guardar_proveedor_rapido(nit: str, nombre: str) -> None:
    archivo = "data/proveedores.json"
    if not os.path.exists("data"):
        os.makedirs("data")
    db = cargar_proveedores_json()
    nrc_existente = db.get(nit, {}).get("nrc", "")
    db[nit] = {"nombre": nombre.strip().upper(), "nrc": nrc_existente}
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)


def limpiar_monto(monto_str: str) -> float:
    s = re.sub(r'[^\d.,]', '', str(monto_str).strip())
    if not s:
        return 0.0
    ultimo_coma  = s.rfind(',')
    ultimo_punto = s.rfind('.')
    if ultimo_coma > ultimo_punto:
        s = s.replace('.', '').replace(',', '.')
    elif ultimo_punto > ultimo_coma:
        s = s.replace(',', '')
    else:
        s = s.replace(',', '').replace('.', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


def extraer_y_formatear_fecha(texto: str) -> str:
    m = re.search(
        r"\b(20[2-3]\d)\s*[-\/]\s*(0[1-9]|1[0-2])\s*[-\/]\s*([0-2]\d|3[01])\b",
        texto
    )
    if m:
        return f"{int(m.group(3)):02d}/{int(m.group(2)):02d}/{m.group(1)}"

    m = re.search(
        r"(?:FECHA\s*(?:DE\s*)?(?:EMISI[OÓ]N|GENERACI[OÓ]N)?)[^\d]*"
        r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})",
        texto, re.I
    )
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if d <= 12 and mo > 12:
            d, mo = mo, d
        if mo <= 12:
            return f"{d:02d}/{mo:02d}/{y}"

    m = re.search(
        r"\b(\d{1,2})\s*[\/\-\.]\s*(\d{1,2})\s*[\/\-\.]\s*(20[2-3]\d)\b",
        texto
    )
    if m:
        p1, p2, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if p1 <= 12 and p2 > 12:
            return f"{p2:02d}/{p1:02d}/{y}"
        elif p2 <= 12 and p1 > 12:
            return f"{p1:02d}/{p2:02d}/{y}"
        elif p2 <= 12 and p1 <= 31:
            return f"{p1:02d}/{p2:02d}/{y}"

    return ""


def extraer_compras_nativo_pro(file_bytes: bytes, cliente_activo: dict) -> dict:
    if not file_bytes or len(file_bytes) < 512:
        return {"error": "Archivo vacío o demasiado pequeño."}

    try:
        texto_lineal = ""
        texto_visual = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                return {"error": "PDF sin páginas."}
            for page in pdf.pages:
                texto_lineal += (page.extract_text(layout=False) or "") + "\n"
                texto_visual  += (page.extract_text() or "") + "\n"

        texto_completo = texto_lineal + "\n" + texto_visual

        if len(texto_completo.strip()) < 50:
            return {"error": "PDF de imagen — sin texto extraíble. Usa OCR."}

        t_clean    = re.sub(r'[ \t]+', ' ', texto_completo)
        t_no_sp    = re.sub(r'\s+', '', t_clean).upper()

        # ── Código de control / Tipo DTE ──
        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_sp)
        tipo   = "01"
        ctrl   = ""
        if m_ctrl:
            ctrl   = m_ctrl.group(1).replace("O", "0")
            m_tipo = re.search(r"DTE-(\d{2})", ctrl)
            if m_tipo:
                tipo = m_tipo.group(1)

        if not ctrl:
            return {"error_tipo": "No se detectó un Número de Control DTE válido."}
        if tipo not in ("03", "05", "06"):
            return {"error_tipo": f"Documento DTE-{tipo}. Solo se admiten 03, 05 y 06."}

        nit_receptor = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
        dui_receptor = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))

        # ── UUID / Código de Generación ──
        gen = ""
        m_url = re.search(r"CODGEN=([A-F0-9\-]{36})", t_no_sp)
        if m_url:
            gen = m_url.group(1).upper()
        else:
            m_uuid = re.search(
                r"([A-F0-9]{8}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{4}-?[A-F0-9]{12})",
                t_no_sp
            )
            if m_uuid:
                raw = m_uuid.group(1).replace("-", "")
                gen = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

        fecha = extraer_y_formatear_fecha(t_clean)

        # ── Datos del proveedor (emisor del DTE) ──
        nit_prov = ""
        dui_prov = ""
        nom_prov = "⚠️ PROVEEDOR NUEVO"
        es_nuevo = True

        excluir_nits = {nit_receptor, dui_receptor} - {""}
        pos_nit_emisor = -1   # posición en texto donde se encontró el NIT del emisor

        proveedores_db = cargar_proveedores_json()

        # ═══ ESTRATEGIA 1: Etiqueta "NIT:" explícita ═══════════════════════
        # En cada DTE la etiqueta "NIT:" aparece al menos dos veces
        # (emisor y receptor). El PRIMER match que no sea el NIT del cliente
        # es el NIT del emisor (proveedor).
        patron_etq_nit = re.compile(
            r"N\.?\s*I\.?\s*T\.?\s*[:\s]\s*"
            r"((?:\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d)"   # formato 4-6-3-1
            r"|(?:\d{14})"                                       # 14 dígitos planos
            r"|(?:\d{8}[\s\-]?\d))",                            # DUI 8-1
            re.I
        )
        for m_etq in patron_etq_nit.finditer(texto_completo):
            nit_cand = re.sub(r'[^0-9]', '', m_etq.group(1))
            if nit_cand not in excluir_nits and len(nit_cand) in (9, 14):
                nit_prov = nit_cand
                pos_nit_emisor = m_etq.start()
                break

        # ═══ ESTRATEGIA 2: Búsqueda en sección del emisor (más permisiva) ══
        if not nit_prov:
            # Aislar emisor con múltiples patrones de separador
            partes = re.split(
                r"(?i)\b(?:DATOS\s+DEL\s+RECEPTOR|RECEPTOR\s*[:\-]|"
                r"DATOS\s+DEL\s+ADQUIRIENTE|ADQUIRIENTE\s*[:\-]|"
                r"RECEPTOR\b|CLIENTE\s*:|COMPRADOR\b)\b",
                texto_completo, maxsplit=1
            )
            texto_emisor = partes[0] if len(partes[0]) > 80 else texto_completo[:2500]

            # Patrón amplio: NIT con espacios o guiones variables
            patron_nit_raw = re.compile(
                r"\b(\d{4})[\s\-]?(\d{3,6})[\s\-]?(\d{2,6})[\s\-]?(\d)\b"
                r"|\b(\d{14})\b"
            )
            for m_raw in patron_nit_raw.finditer(texto_emisor):
                gs = m_raw.groups()
                nit_cand = re.sub(r'[^0-9]', '', m_raw.group(0))
                if nit_cand not in excluir_nits and len(nit_cand) == 14:
                    nit_prov = nit_cand
                    pos_nit_emisor = m_raw.start()
                    break

        # ═══ ESTRATEGIA 3: URL/QR code (algunos PDFs incluyen NIT en URL) ══
        if not nit_prov:
            m_url_nit = re.search(r"NIT[=\s]?(\d{14})", t_no_sp)
            if m_url_nit:
                nit_cand = m_url_nit.group(1)
                if nit_cand not in excluir_nits:
                    nit_prov = nit_cand

        # ═══ ESTRATEGIA 4: Cualquier NIT en el documento, excluir receptor ═
        if not nit_prov:
            patron_todos = re.compile(
                r"\b\d{4}[\s\-]?\d{6}[\s\-]?\d{3}[\s\-]?\d\b"
                r"|\b\d{14}\b"
                r"|\b\d{8}[\s\-]?\d\b"
                r"|\b\d{9}\b"
            )
            for m_any in patron_todos.finditer(texto_completo):
                nit_cand = re.sub(r'[^0-9]', '', m_any.group(0))
                if nit_cand not in excluir_nits and len(nit_cand) in (9, 14):
                    nit_prov = nit_cand
                    pos_nit_emisor = m_any.start()
                    break

        # ── Determinar si es DUI ──
        if len(nit_prov) == 9:
            dui_prov = nit_prov

        # ── Consultar base de datos de proveedores ──
        if nit_prov and nit_prov in proveedores_db:
            nom_prov = proveedores_db[nit_prov].get("nombre", "")
            es_nuevo = False

        # ═══ EXTRACCIÓN DE NOMBRE — solo si es proveedor nuevo ═════════════
        if es_nuevo and nit_prov:
            nombre_encontrado = ""

            # Ventana de texto ANTES del NIT del emisor (1000 chars)
            if pos_nit_emisor >= 0:
                inicio_ventana = max(0, pos_nit_emisor - 1200)
                ventana_antes  = texto_completo[inicio_ventana:pos_nit_emisor]
            else:
                # Sin posición, usar primeras 2000 chars
                ventana_antes = texto_completo[:2000]

            # --- Intento 1: Etiqueta "Nombre:" o "Razón Social:" ---
            m_nombre_etq = re.search(
                r"(?:Nombre(?:\s+o\s+[Rr]az[oó]n\s+[Ss]ocial)?|"
                r"[Rr]az[oó]n\s+[Ss]ocial|Nombre\s+Comercial)"
                r"\s*[:\s]\s*(.*?)(?=\s*(?:NIT|NRC|Giro|Actividad|Direcci[oó]n|\n\n|$))",
                ventana_antes, re.I | re.DOTALL
            )
            if m_nombre_etq:
                candidato = re.sub(r'\s+', ' ', m_nombre_etq.group(1)).strip()
                partes_cli = cliente_activo.get('nombre', '').upper().split()[:2]
                if (
                    4 < len(candidato) <= 80
                    and not any(b in candidato.upper() for b in BASURA_ESTRICTA)
                    and not any(p in candidato.upper() for p in partes_cli)
                ):
                    nombre_encontrado = candidato

            # --- Intento 2: Líneas próximas antes del NIT (hacia atrás) ---
            if not nombre_encontrado:
                lineas_antes = [l.strip() for l in ventana_antes.split('\n') if l.strip()]
                for linea in reversed(lineas_antes[-15:]):
                    L = linea.upper()
                    if len(L) < 5:
                        continue
                    # Descartar si tiene demasiados dígitos (códigos, NITs, fechas)
                    if sum(c.isdigit() for c in L) / len(L) > 0.38:
                        continue
                    # Descartar palabras de encabezado/basura
                    if any(b in L for b in PALABRAS_BASURA + BASURA_ESTRICTA):
                        continue
                    # Descartar si contiene partes del nombre del cliente (receptor)
                    partes_cli = cliente_activo.get('nombre', '').upper().split()[:2]
                    if any(p in L for p in partes_cli if len(p) > 3):
                        continue
                    # Línea válida
                    nombre_encontrado = linea
                    break

            # --- Intento 3: Buscar cualquier línea con sufijo comercial ---
            if not nombre_encontrado:
                for linea in ventana_antes.split('\n'):
                    L = linea.strip().upper()
                    if len(L) < 5 or sum(c.isdigit() for c in L) / len(L) > 0.3:
                        continue
                    if any(b in L for b in PALABRAS_BASURA + BASURA_ESTRICTA):
                        continue
                    if any(w in L for w in PALABRAS_COMERCIALES):
                        clean = re.split(r'\s{4,}|(?:NIT|NRC)\s', L)[0].strip()
                        partes_cli = cliente_activo.get('nombre', '').upper().split()[:2]
                        if clean and not any(p in clean for p in partes_cli if len(p) > 3):
                            nombre_encontrado = clean
                            break

            # --- Limpiar y validar el nombre ---
            if nombre_encontrado:
                nombre_encontrado = re.sub(
                    r"^(?:RAZ[OÓ]N\s*SOCIAL|NOMBRE(?:\s+O\s+RAZ[OÓ]N\s+SOCIAL)?|"
                    r"NOMBRE\s+COMERCIAL|EMISOR|DATOS\s+DEL\s+EMISOR)[\s:]*",
                    "", nombre_encontrado, flags=re.I
                ).strip()
                nombre_encontrado = re.sub(r"^[-_.,;:]+", "", nombre_encontrado).strip()
                nombre_encontrado = re.sub(r'\s+', ' ', nombre_encontrado)

                if 4 <= len(nombre_encontrado) <= 80:
                    nom_prov = nombre_encontrado.upper()
                else:
                    nom_prov = "ESCRIBE EL NOMBRE AQUÍ"
            else:
                nom_prov = "ESCRIBE EL NOMBRE AQUÍ"

        # ── Extracción de montos ──
        e, g, i, ret, perc, t = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        iva_calculado = False

        # Exentos: FOVIAL / COTRANS / etiqueta explícita
        m_fovial = re.search(r"FOVIAL.{0,50}", t_clean, re.I)
        if m_fovial:
            nums = re.findall(r"\d+\.\d{2}", m_fovial.group(0))
            if nums:
                e += max(float(n) for n in nums)

        m_cotrans = re.search(r"COTRANS.{0,50}", t_clean, re.I)
        if m_cotrans:
            nums = re.findall(r"\d+\.\d{2}", m_cotrans.group(0))
            if nums:
                e += max(float(n) for n in nums)

        m_exe = re.search(
            r"(?:Ventas?\s+Exentas?|Total\s+Exento)[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_exe:
            val_exe = limpiar_monto(m_exe.group(1))
            if val_exe > e:
                e = val_exe

        e = round(e, 2)

        # Retención explícita
        m_ret = re.search(
            r"(?:Retenido|Retenci[oó]n)[^\d]{0,25}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_ret:
            ret = limpiar_monto(m_ret.group(1))

        # Total e IVA explícitos (antes del bucle O(n³))
        m_tot = re.search(
            r"(?:TOTAL\s+A\s+PAGAR|TOTAL\s+PAGAR|MONTO\s+TOTAL|"
            r"TOTAL\s+OPERACI[OÓ]N|VENTA\s+TOTAL|TOTAL\s*\$)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_tot:
            t = limpiar_monto(m_tot.group(1))

        m_iva = re.search(
            r"(?:Impuesto\s+.*?Agregado|IVA\s+13%|13%\s+IVA|I\.V\.A\.?|DÉBITO\s+FISCAL)"
            r"[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_iva:
            i = limpiar_monto(m_iva.group(1))

        # Reconciliación O(n³) con límite de seguridad
        encontrado = False
        if not (t > 0 and i > 0):
            montos_raw = re.findall(
                r"(?:US\$?|\$)?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
                t_clean
            )
            valores = sorted(
                list({limpiar_monto(m) for m in montos_raw if limpiar_monto(m) > 0}),
                reverse=True
            )[:MAX_VALORES_LOOP]

            for vt in valores:
                if encontrado: break
                for vg in valores:
                    if vg >= vt: continue
                    if encontrado: break
                    for vi in valores:
                        if vi >= vg: continue
                        if abs(round(vg * 0.13, 2) - round(vi, 2)) <= 0.05:
                            if abs(round(vg + vi + e - ret, 2) - round(vt, 2)) <= 0.05:
                                g, i, t = vg, vi, vt
                                encontrado = True
                                break

        # Fallback si tenemos total e IVA explícitos
        if not encontrado:
            if t > 0 and i > 0:
                g = round(t - i - e + ret, 2)
                encontrado = True
            elif t > 0 and i == 0.0 and tipo == "03":
                g = round((t + ret - e) / 1.13, 2)
                i = round(t + ret - e - g, 2)
                iva_calculado = True
                encontrado = True

        return {
            "fecha"    : fecha,
            "nit_prov" : nit_prov,
            "dui_prov" : dui_prov,
            "nom_prov" : nom_prov,
            "tipo"     : tipo,
            "gen"      : gen,
            "exe"      : e,
            "gra"      : g,
            "iva"      : i,
            "ret"      : ret,
            "perc"     : perc,
            "tot"      : t,
            "estado"   : "✅ OK",
            "iva_calc" : iva_calculado,
            "es_nuevo" : es_nuevo,
            "nit_nuevo": nit_prov,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error": "PDF inválido o con sintaxis corrupta."}
    except Exception as err:
        return {"error": str(err)}


def to_excel_hacienda_compras(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, header=False, sheet_name='Compras_F07')
        wb  = writer.book
        ws  = writer.sheets['Compras_F07']
        fmt_txt = wb.add_format({'num_format': '@'})
        fmt_num = wb.add_format({'num_format': '0.00', 'align': 'left'})

        def col_width(idx: int) -> int:
            return max(df.iloc[:, idx].astype(str).map(len).max() if not df.empty else 15, 15) + 2

        ws.set_column(0, 0, 10,  fmt_txt)
        ws.set_column(1, 2, 2,   fmt_txt)
        ws.set_column(3, 3, col_width(3), fmt_txt)
        ws.set_column(4, 4, 14,  fmt_txt)
        ws.set_column(5, 5, col_width(5), fmt_txt)
        ws.set_column(6, 14, 10.71, fmt_num)
        ws.set_column(15, 20, 8, fmt_txt)
    return output.getvalue()


@st.dialog("⚠️ Seguro de Calidad de Compras")
def ventana_descarga_compras(df_resultados: pd.DataFrame, nombre_archivo: str) -> None:
    st.write(
        "Asegúrate de haber procesado únicamente los comprobantes que deseas "
        "declarar en el anexo de Compras antes de descargar."
    )
    st.download_button(
        "📥 Confirmar y Descargar Anexo F-07",
        data=to_excel_hacienda_compras(df_resultados),
        file_name=nombre_archivo,
        type="primary"
    )

# ─────────────────────────────────────────────
# 6. ENCABEZADO DE PÁGINA
# ─────────────────────────────────────────────
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<h2 style='font-family: Courier New, monospace; color: #8A9A35;"
        " letter-spacing: 3px; margin-top:8px;'>YN</h2>",
        unsafe_allow_html=True
    )
with col_titulo:
    st.title("🛒 Extractor DTE — Compras")

st.markdown(f"""
<div class="card-emisor">
    <strong>RECEPTOR ACTIVO:</strong> {cliente['nombre']}<br>
    <strong>NIT:</strong> {cliente['nit']}
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 7. SESSION STATE
# ─────────────────────────────────────────────
if 'cola_revision'       not in st.session_state: st.session_state.cola_revision       = []
if 'comp_uploader_key'   not in st.session_state: st.session_state.comp_uploader_key   = 0
if 'db_compras'          not in st.session_state: st.session_state.db_compras          = pd.DataFrame()
if 'archivos_comp'       not in st.session_state: st.session_state.archivos_comp       = []
if 'reporte_compras'     not in st.session_state: st.session_state.reporte_compras     = None

# ─────────────────────────────────────────────
# 8. SIDEBAR — CARGA Y PROCESAMIENTO
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga de Compras")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra facturas de proveedores (PDF)",
        type="pdf",
        accept_multiple_files=True,
        key=str(st.session_state.comp_uploader_key)
    )

    procesar = st.button(
        "🚀 Procesar Compras",
        type="primary",
        use_container_width=True,
        disabled=not archivos
    )

    if procesar and archivos:
        nombres_procesados = set(st.session_state.archivos_comp)
        nuevos = [f for f in archivos if f.name not in nombres_procesados]

        if not nuevos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            extracted, duplicados, iva_calc_files = [], [], []
            invalidos, corruptos, nuevos_proveedores = [], [], {}

            bar           = st.progress(0)
            txt_progreso  = st.empty()
            t_inicio      = time.time()
            total         = len(nuevos)

            for idx, f in enumerate(nuevos):
                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                if idx > 0:
                    elapsed   = time.time() - t_inicio
                    remaining = int((elapsed / idx) * (total - idx))
                    m, s      = divmod(remaining, 60)
                    txt_progreso.caption(f"⏳ {idx+1}/{total} — Restante: {m:02d}:{s:02d}")
                else:
                    txt_progreso.caption(f"⏳ Procesando 1 de {total}…")

                file_bytes = f.read()

                if len(file_bytes) < 512:
                    corruptos.append(f.name)
                    st.session_state.archivos_comp.append(f.name)
                    bar.progress((idx + 1) / total)
                    continue

                res = extraer_compras_nativo_pro(file_bytes, cliente)

                cod_gen         = res.get('gen', '')
                dup_memoria     = (
                    not st.session_state.db_compras.empty
                    and cod_gen
                    and (st.session_state.db_compras['gen'] == cod_gen).any()
                )
                dup_lote        = cod_gen and any(d.get('gen') == cod_gen for d in extracted)

                if "error_tipo" in res:
                    invalidos.append(f.name)
                elif dup_memoria or dup_lote:
                    duplicados.append(f.name)
                elif "error" in res:
                    corruptos.append(f.name)
                else:
                    nom = str(res.get('nom_prov', '')).strip()
                    va_a_revision = (
                        res.get('tot', 0.0) == 0.0
                        or not res.get('gen')
                        or not str(res.get('fecha', '')).strip()
                        or nom in ("ESCRIBE EL NOMBRE AQUÍ", "")
                    )
                    if va_a_revision:
                        st.session_state.cola_revision.append({
                            "archivo": f.name,
                            "bytes"  : file_bytes,
                            "datos"  : res
                        })
                    else:
                        if res.get('iva_calc'):
                            iva_calc_files.append(f.name)
                        if res.get("es_nuevo") and res.get("nit_nuevo"):
                            nuevos_proveedores[res["nit_nuevo"]] = res["nom_prov"]
                        res["archivo"] = f.name
                        extracted.append(res)

                st.session_state.archivos_comp.append(f.name)
                bar.progress((idx + 1) / total)

            txt_progreso.success(f"✅ {total} facturas escaneadas.")

            st.session_state.reporte_compras = {
                "invalidos"         : invalidos,
                "duplicados"        : duplicados,
                "iva_calc"          : iva_calc_files,
                "nuevos_proveedores": nuevos_proveedores,
                "corruptos"         : corruptos,
            }

            if extracted:
                new_df = pd.DataFrame(extracted)
                if st.session_state.db_compras.empty:
                    st.session_state.db_compras = new_df
                else:
                    st.session_state.db_compras = pd.concat(
                        [st.session_state.db_compras, new_df], ignore_index=True
                    )

    st.divider()
    if st.button("🧹 Limpiar Memoria Compras", type="secondary", use_container_width=True):
        for key in ('db_compras', 'archivos_comp', 'reporte_compras', 'cola_revision'):
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.comp_uploader_key = st.session_state.get('comp_uploader_key', 0) + 1
        st.rerun()

    if not st.session_state.db_compras.empty:
        st.divider()
        total_docs  = len(st.session_state.db_compras)
        total_monto = st.session_state.db_compras["tot"].sum()
        st.markdown(f"**📄 Documentos:** `{total_docs}`")
        st.markdown(f"**💰 Total:** `${total_monto:,.2f}`")

# ─────────────────────────────────────────────
# 9. BANDEJA DE REVISIÓN MANUAL
# ─────────────────────────────────────────────
if st.session_state.cola_revision:
    st.markdown("""
    <div class="inbox-revision">
        <h3>📥 Bandeja de Revisión Manual</h3>
        <p>Datos borrosos o incompletos detectados. Revisa y corrige antes de agregar al libro.</p>
    </div>
    """, unsafe_allow_html=True)

    total_cola  = len(st.session_state.cola_revision)
    st.info(f"Quedan **{total_cola}** documento(s) por revisar.")

    item_actual  = st.session_state.cola_revision[0]
    datos_act    = item_actual["datos"]

    col_img, col_form = st.columns([1.2, 1], gap="large")

    with col_img:
        try:
            with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                img = pdf.pages[0].to_image(resolution=200).original
                st.image(img, caption=f"📄 {item_actual['archivo']}", use_container_width=True)
                texto_crudo = ""
                for page in pdf.pages:
                    texto_crudo += (page.extract_text(layout=True) or page.extract_text() or "") + "\n"
                st.markdown("📝 **Texto extraído:**")
                st.text_area("", value=texto_crudo.strip(), height=200, label_visibility="collapsed")
        except Exception:
            st.error("No se pudo cargar la vista previa.")

    with col_form:
        st.markdown("### ✍️ Corrección Rápida")
        with st.form(key=f"form_revision_{item_actual['archivo']}"):
            f_fecha = st.text_input("📅 Fecha (DD/MM/YYYY) *", value=datos_act.get("fecha", ""))
            f_gen   = st.text_input("🔑 Código de Generación (UUID) *", value=datos_act.get("gen", ""))

            nom_sug = datos_act.get("nom_prov", "")
            if nom_sug == "ESCRIBE EL NOMBRE AQUÍ":
                nom_sug = ""
            f_nom = st.text_input("🏢 Razón Social del Proveedor *", value=nom_sug)

            c1, c2 = st.columns(2)
            with c1:
                f_tot = st.number_input("💰 Total a Pagar ($) *", value=float(datos_act.get("tot", 0.0)), format="%.2f")
            with c2:
                f_exe = st.number_input("⛽ Exento/Fovial ($)", value=float(datos_act.get("exe", 0.0)), format="%.2f")

            st.markdown("")
            b1, b2 = st.columns(2)

            with b1:
                if st.form_submit_button("✅ Aprobar y Guardar", type="primary", use_container_width=True):
                    if not f_fecha or not f_gen or not f_nom or f_tot <= 0:
                        st.error("Completa todos los campos marcados con (*).")
                    else:
                        nit_act = datos_act.get("nit_prov", "")
                        if nit_act:
                            guardar_proveedor_rapido(nit_act, f_nom)
                            for item in st.session_state.cola_revision[1:]:
                                if item["datos"].get("nit_prov") == nit_act:
                                    item["datos"]["nom_prov"] = f_nom.upper()

                        datos_act.update({
                            "fecha"   : f_fecha,
                            "gen"     : f_gen.upper(),
                            "nom_prov": f_nom.upper(),
                            "tot"     : f_tot,
                            "exe"     : f_exe,
                            "archivo" : item_actual["archivo"],
                        })

                        if f_tot > 0 and datos_act.get("iva", 0) == 0:
                            datos_act["gra"] = round((f_tot - f_exe) / 1.13, 2)
                            datos_act["iva"] = round(f_tot - f_exe - datos_act["gra"], 2)
                            datos_act["iva_calc"] = True

                        nuevo_df = pd.DataFrame([datos_act])
                        if st.session_state.db_compras.empty:
                            st.session_state.db_compras = nuevo_df
                        else:
                            st.session_state.db_compras = pd.concat(
                                [st.session_state.db_compras, nuevo_df], ignore_index=True
                            )
                        st.session_state.cola_revision.pop(0)
                        st.rerun()

            with b2:
                if st.form_submit_button("🗑️ Descartar Archivo", use_container_width=True):
                    st.session_state.cola_revision.pop(0)
                    st.rerun()

    st.stop()

# ─────────────────────────────────────────────
# 10. REPORTE DE PROCESAMIENTO
# ─────────────────────────────────────────────
if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### 📋 Alertas de Procesamiento")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if rep.get("corruptos"):
            st.error(f"💀 **{len(rep['corruptos'])} Dañados**")
        else:
            st.success("✅ 0 Dañados")
    with c2:
        if rep.get("invalidos"):
            st.warning(f"⚠️ **{len(rep['invalidos'])} Ignorados** (tipo incorrecto)")
        else:
            st.success("✅ 0 Ignorados")
    with c3:
        if rep.get("duplicados"):
            st.error(f"🛑 **{len(rep['duplicados'])} Duplicados**")
        else:
            st.success("✅ 0 Duplicados")
    with c4:
        if rep.get("iva_calc"):
            st.info(f"🧮 **{len(rep['iva_calc'])} IVA Calculado**")
        else:
            st.success("✅ IVA directo")
    st.divider()

# ─────────────────────────────────────────────
# 11. TABLA PRINCIPAL Y EXPORT
# ─────────────────────────────────────────────
if not st.session_state.db_compras.empty:
    df = st.session_state.db_compras.copy()

    st.markdown("### 🔍 Filtros de Auditoría")
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("Buscar proveedor 🔎", placeholder="Nombre, NIT o UUID…")
    with col_f2:
        filtro_tipo = st.multiselect(
            "Tipo DTE 📄",
            options=df['tipo'].unique().tolist(),
            default=df['tipo'].unique().tolist()
        )

    df_filtrado = df.copy()
    if busqueda:
        t = busqueda.upper()
        mask = (
            df_filtrado['nom_prov'].str.contains(t, case=False, na=False) |
            df_filtrado['nit_prov'].str.contains(t, na=False) |
            df_filtrado['dui_prov'].str.contains(t, na=False) |
            df_filtrado['gen'].str.contains(t, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask]
    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]

    st.divider()

    tab1, tab2 = st.tabs(["📊 Libro F-07 Compras", "🔍 Auditoría Completa"])

    with tab1:
        df_f07 = pd.DataFrame()
        df_f07["A. Fecha Emisión"]       = df_filtrado["fecha"]
        df_f07["B. Clase"]               = "4"
        df_f07["C. Tipo Doc"]            = df_filtrado["tipo"]
        df_f07["D. Num Documento"]       = df_filtrado["gen"]
        df_f07["E. NIT/NRC Prov"]        = df_filtrado["nit_prov"]
        df_f07["F. Nombre Prov"]         = df_filtrado["nom_prov"]
        df_f07["G. Compra Ext/NS"]       = df_filtrado["exe"]
        df_f07["H. Internacion Ext/NS"]  = 0.00
        df_f07["I. Importacion Ext/NS"]  = 0.00
        df_f07["J. Compra Gravada"]      = df_filtrado["gra"]
        df_f07["K. Inter. Grav Bienes"]  = 0.00
        df_f07["L. Impor. Grav Bienes"]  = 0.00
        df_f07["M. Impor. Grav Serv"]    = 0.00
        df_f07["N. Crédito Fiscal (IVA)"]= df_filtrado["iva"]
        df_f07["O. Total Compras"]       = df_filtrado["tot"]
        df_f07["P. DUI Prov"]            = df_filtrado["dui_prov"]
        df_f07["Q. Tipo Operacion"]      = "1"
        df_f07["R. Clasificacion"]       = "1"
        df_f07["S. Sector"]              = "1"
        df_f07["T. Tipo Costo/Gasto"]    = "1"
        df_f07["U. Num Anexo"]           = "3"

        COLS_NUM = [c for c in df_f07.columns if df_f07[c].dtype == float]
        st.dataframe(
            df_f07.style.format({c: "{:.2f}" for c in COLS_NUM}),
            hide_index=True,
            use_container_width=True
        )

        st.markdown(
            f"> **Total Gravadas:** `${df_f07['J. Compra Gravada'].sum():,.2f}` &nbsp;|&nbsp;"
            f"**IVA:** `${df_f07['N. Crédito Fiscal (IVA)'].sum():,.2f}` &nbsp;|&nbsp;"
            f"**Total General:** `${df_f07['O. Total Compras'].sum():,.2f}`"
        )

        st.markdown("---")
        if st.button("📥 Generar Excel para Hacienda", type="primary"):
            ventana_descarga_compras(
                df_f07,
                f"F07_Compras_{cliente['nombre'].replace(' ','_')}.xlsx"
            )

    with tab2:
        st.write(f"📊 Registros: **{len(df_filtrado)}** de **{len(df)}**")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

else:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #6B7A2A;">
        <h3 style="color:#8A9A35 !important;">📂 Sin documentos cargados</h3>
        <p style="color:#4A5520 !important;">Usa el panel lateral para cargar y procesar PDFs de compras.</p>
    </div>
    """, unsafe_allow_html=True)
