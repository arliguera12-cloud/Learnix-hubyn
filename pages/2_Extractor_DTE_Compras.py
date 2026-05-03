import streamlit as st
import pdfplumber
import pandas as pd
import re
import time
import json
import os
import gc
from io import BytesIO
import platform

# ─────────────────────────────────────────────
# 1. PAGE CONFIG — SIEMPRE PRIMERO
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Extractor DTE · Compras",
    layout="wide",
    page_icon="🛒"
)

# ─────────────────────────────────────────────
# 2. ESTILOS — VERDE OLIVA ARMONIZADO
# ─────────────────────────────────────────────
ESTILO = """
<style>
  /* ── Fondos ── */
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"]          { background-color: #0D0F07 !important; }
  [data-testid="stSidebar"]         { background-color: #141A08 !important;
                                      border-right: 1px solid #4A5520 !important; }

  /* ── Tipografía global ── */
  h1, h2, h3, h4, h5, h6           { color: #C8D87A !important; letter-spacing: 1px; }
  p, label, span, li, div           { color: #F0EDD8 !important; }
  [data-testid="stDataFrame"] span  { color: inherit !important; }

  /* ── Botones primarios ── */
  div.stButton > button[kind="primary"],
  div.stDownloadButton > button[kind="primary"] {
    background-color: #6B7A2A !important;
    border: 1px solid #8A9A35 !important;
    border-radius: 6px !important;
    transition: background-color 0.25s ease, transform 0.1s ease;
  }
  div.stButton > button[kind="primary"]:hover,
  div.stDownloadButton > button[kind="primary"]:hover {
    background-color: #8A9A35 !important;
    transform: scale(1.02);
  }
  div.stButton > button[kind="primary"] *,
  div.stDownloadButton > button[kind="primary"] * {
    color: #FFFFFF !important;
    font-weight: bold !important;
  }

  /* ── Botones secundarios ── */
  div.stButton > button[kind="secondary"] {
    background-color: transparent !important;
    border: 1px solid #4A5520 !important;
    border-radius: 6px !important;
    transition: 0.25s;
  }
  div.stButton > button[kind="secondary"]:hover {
    background-color: #1A2008 !important;
  }
  div.stButton > button[kind="secondary"] * { color: #C8D87A !important; }

  /* ── Tabs ── */
  button[data-baseweb="tab"]        { color: #8A9A35 !important; }
  button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom: 2px solid #8A9A35 !important;
    color: #F0EDD8 !important;
  }

  /* ── Alertas Streamlit ── */
  div[data-testid="stAlert"]        { min-height: 60px; display: flex; align-items: center; }
  .stAlert *                        { color: inherit !important; }

  /* ── Card receptor activo ── */
  .card-receptor {
    padding: 12px 16px;
    border-radius: 8px;
    border-left: 4px solid #8A9A35;
    background-color: #1A2008;
    color: #F0EDD8 !important;
    margin-bottom: 18px;
    font-size: 14px;
    line-height: 1.6;
  }
  .card-receptor strong { color: #C8D87A !important; }

  /* ── Bandeja de revisión manual ── */
  .inbox-revision {
    background-color: #1A1A08;
    border: 1px solid #8A7020;
    border-left: 4px solid #C8A020;
    border-radius: 10px;
    padding: 20px;
    margin-top: 20px;
    margin-bottom: 20px;
  }
  .inbox-titulo  { color: #C8D87A !important; margin-top: 0; }
  .inbox-subtxt  { color: #8A9A35 !important; margin-bottom: 0; }

  /* ── Lista scrollable ── */
  .scroll-list {
    max-height: 150px;
    overflow-y: auto;
    padding: 10px;
    background-color: #0D0F07;
    border-radius: 5px;
    border: 1px solid #4A5520;
    font-family: monospace;
    font-size: 13px;
    color: #A8BB45;
  }

  /* ── Expanders y widgets ── */
  [data-testid="stStatusWidget"],
  [data-testid="stExpander"] {
    background-color: #141A08 !important;
    border: 1px solid #4A5520 !important;
    border-radius: 6px;
  }

  /* ── Separador ── */
  hr { border-color: #4A5520 !important; opacity: 0.4; }
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
    st.warning("⚠️ Debes seleccionar un Cliente Activo antes de extraer Compras.")
    st.stop()

cliente = st.session_state.cliente_activo

# ─────────────────────────────────────────────
# 4. CONSTANTES
# ─────────────────────────────────────────────
TIPOS_VALIDOS_COMPRAS  = {"03", "05", "06"}
MAX_VALORES_LOOP       = 30          # 🔒 Límite O(n³)
PALABRAS_BASURA_NOMBRE = [
    "DOCUMENTO", "TRIBUTARIO", "ELECTRÓNICO", "REPRESENTACIÓN", "RECEPTOR",
    "CLIENTE", "EMISOR", "FACTURA", "CONSUMIDOR", "FACTURACION", "COMPROBANTE",
    "DIRECC", "CÓDIGO", "SELLO", "VERSIÓN", "TRANSMISIÓN", "MINISTERIO",
    "HACIENDA", "COLONIA", "BOULEVARD", "CALLE", "AVENIDA", "MUNICIPIO",
    "GIRO:", "ACTIVIDAD", "ECONOMICA", "TIPO ESTABLECIMIENTO", "SUCURSAL",
    "AGENCIA", "PAGO DE", "TARJETA", "EFECTIVO", "FECHA", "HORA",
    "EMISIÓN", "GENERACIÓN", "TELÉFONO"
]
BASURA_ESTRICTA        = ["@", "EMAIL", "CORREO", ".COM", "WWW."]
SUFIJOS_SOLOS          = {"S.A. DE C.V.", "C.V.", "SA DE CV", "LTDA", "LTDA.", "S.A.", "DE C.V."}
INDICADORES_COMERCIAL  = [
    "S.A.", "SA ", "C.V.", "CV ", "LTDA.", "LTDA", "SOCIEDAD",
    "DISTRIBUIDORA", "FARMACIA", "GRUPO", "LABORATORIOS", "INDUSTRIAS"
]

# ─────────────────────────────────────────────
# 5. FUNCIONES AUXILIARES
# ─────────────────────────────────────────────
def limpiar_monto(monto_str: str) -> float:
    """
    Convierte string de monto a float.
    Soporta formatos: 1,234.56 (anglosajón) y 1.234,56 (europeo).
    """
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


def cargar_proveedores_json() -> dict:
    """Carga la base de datos local de proveedores con manejo de errores."""
    archivo = "data/proveedores.json"
    if not os.path.exists(archivo):
        return {}
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Migración: si el valor es string simple, convertir a dict
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = {"nombre": v, "nrc": ""}
        return data
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Base de proveedores con error de formato: {e}")
        return {}
    except Exception as e:
        st.warning(f"⚠️ No se pudo cargar proveedores: {e}")
        return {}


def guardar_proveedor_rapido(nit: str, nombre: str) -> None:
    """Guarda o actualiza un proveedor en la base de datos local."""
    if not nit or not nombre:
        return
    archivo = "data/proveedores.json"
    os.makedirs("data", exist_ok=True)
    db = cargar_proveedores_json()
    nrc_existente = db.get(nit, {}).get("nrc", "")
    db[nit] = {"nombre": nombre.strip().upper(), "nrc": nrc_existente}
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)


def extraer_y_formatear_fecha(texto: str) -> str:
    """
    Extrae y normaliza fecha de emisión de un DTE.
    Retorna formato DD/MM/YYYY o string vacío.
    Valida días 01-31 y meses 01-12.
    """
    # Formato Hacienda: YYYY-MM-DD o YYYY/MM/DD
    m = re.search(
        r"\b(20[2-3]\d)\s*[-\/]\s*(0[1-9]|1[0-2])\s*[-\/]\s*(0[1-9]|[12]\d|3[01])\b",
        texto
    )
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"

    # Formato suelto: DD/MM/YYYY o MM/DD/YYYY
    m = re.search(
        r"\b(\d{1,2})\s*[\/\-\.]\s*(\d{1,2})\s*[\/\-\.]\s*(20[2-3]\d)\b",
        texto
    )
    if m:
        p1, p2, y = int(m.group(1)), int(m.group(2)), m.group(3)
        # Heurística: si p1 > 12 es definitivamente el día
        if p1 > 12 and p2 <= 12:
            return f"{p1:02d}/{p2:02d}/{y}"
        elif p2 > 12 and p1 <= 12:
            return f"{p2:02d}/{p1:02d}/{y}"
        elif p1 <= 12 and p2 <= 31:
            # Asumir DD/MM como estándar salvadoreño
            return f"{p1:02d}/{p2:02d}/{y}"

    # Formato explícito con etiqueta
    m = re.search(
        r"(?:FECHA\s*DE\s*EMISI[OÓ]N|FECHA\s*DE\s*GENERACI[OÓ]N|FECHA)"
        r"[^\d]*(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})",
        texto, re.I
    )
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if d > 12 and mo <= 12:
            pass  # d es día, mo es mes — correcto
        elif mo > 12 and d <= 12:
            d, mo = mo, d
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{d:02d}/{mo:02d}/{y}"

    return ""


def to_excel_hacienda_compras(df: pd.DataFrame) -> bytes:
    """
    Genera el Excel de Compras compatible con Hacienda El Salvador.
    ✅ Incluye cabeceras de columna (bug corregido).
    """
    output = BytesIO()
    # Rellenar NaN antes de calcular anchos
    df_clean = df.fillna("")

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_clean.to_excel(
            writer,
            index=False,
            header=True,   # ✅ CORREGIDO: header=True para incluir nombres de columna
            sheet_name='Compras_F07'
        )
        wb  = writer.book
        ws  = writer.sheets['Compras_F07']

        fmt_texto   = wb.add_format({'num_format': '@'})
        fmt_num_izq = wb.add_format({'num_format': '0.00', 'align': 'left'})
        fmt_header  = wb.add_format({
            'bold': True, 'bg_color': '#4A5520',
            'font_color': '#F0EDD8', 'border': 1
        })

        def get_max_len(col_idx: int) -> int:
            col_data = df_clean.iloc[:, col_idx].astype(str)
            return max(col_data.map(len).max() if not df_clean.empty else 15, 15) + 2

        # Escribir cabeceras con formato
        for col_idx, col_name in enumerate(df_clean.columns):
            ws.write(0, col_idx, col_name, fmt_header)

        ws.set_column(0, 0, 10,              fmt_texto)
        ws.set_column(1, 1,  2,              fmt_texto)
        ws.set_column(2, 2,  3,              fmt_texto)
        ws.set_column(3, 3,  get_max_len(3), fmt_texto)
        ws.set_column(4, 4,  16,             fmt_texto)
        ws.set_column(5, 5,  get_max_len(5), fmt_texto)
        ws.set_column(6, 14, 11,             fmt_num_izq)
        ws.set_column(15, 15, 10,            fmt_texto)
        ws.set_column(16, 20,  2,            fmt_texto)

    return output.getvalue()


def extraer_compras_nativo_pro(file_bytes: bytes, cliente_activo: dict) -> dict:
    """
    Extrae datos fiscales de un CCF/Nota de Crédito/Débito en PDF nativo.
    Retorna dict normalizado o con clave 'error' / 'error_tipo'.
    """
    # ── Validación básica ──
    if not file_bytes or len(file_bytes) < 500:
        return {"error": "Archivo vacío o muy pequeño."}

    try:
        # ── Extracción de texto dual ──
        texto_lineal = ""
        texto_visual = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            if len(pdf.pages) == 0:
                return {"error": "PDF sin páginas detectadas."}
            for page in pdf.pages:
                texto_lineal += (page.extract_text(layout=False) or "") + "\n"
                texto_visual += (page.extract_text() or "")            + "\n"

        texto_completo = texto_lineal + "\n" + texto_visual

        if len(texto_completo.strip()) < 50:
            return {"error": "PDF de imagen — sin texto extraíble. Se requiere OCR."}

        t_clean  = re.sub(r'[ \t]+', ' ', texto_completo)
        t_no_sp  = re.sub(r'\s+', '', t_clean).upper()

        # ── Tipo DTE y código de control ──
        m_ctrl = re.search(r"(DTE-[0-9O]{2}-[A-Z0-9]+-[A-Z0-9]+)", t_no_sp)
        if not m_ctrl:
            return {"error_tipo": "No se detectó un Número de Control DTE válido."}

        ctrl   = m_ctrl.group(1).replace("O", "0")
        m_tipo = re.search(r"DTE-(\d{2})", ctrl)
        tipo   = m_tipo.group(1) if m_tipo else "00"

        if tipo not in TIPOS_VALIDOS_COMPRAS:
            return {"error_tipo": f"DTE-{tipo} no admitido en Compras. Solo: 03, 05, 06."}

        # ── UUID / Código de generación ──
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
                limpio = m_uuid.group(1).replace("-", "")
                gen = f"{limpio[:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:]}"

        # ── Fecha ──
        fecha = extraer_y_formatear_fecha(t_clean)

        # ── Identificadores del receptor (nuestro cliente) ──
        nit_receptor = re.sub(r'[^0-9]', '', cliente_activo.get('nit', ''))
        dui_receptor = re.sub(r'[^0-9]', '', cliente_activo.get('dui', ''))

        # ── Aislar sección del EMISOR (proveedor) ──
        partes = re.split(
            r"(?i)\b(?:RECEPTOR|CLIENTE\s*:|CLIENTE\s|SOCIO/EMPRESA)\b",
            texto_lineal
        )
        texto_emisor = partes[0] if len(partes[0]) >= 100 else texto_lineal[:1500]

        # ── Búsqueda de NIT / DUI del proveedor ──
        patron_ids = (
            r"\b\d{4}\s*-?\s*\d{6}\s*-?\s*\d{3}\s*-?\s*\d\b"
            r"|\b\d{14}\b"
            r"|\b\d{8}\s*-?\s*\d\b"
            r"|\b\d{9}\b"
        )
        ids_raw     = re.findall(patron_ids, texto_emisor)
        ids_limpios = list(dict.fromkeys(re.sub(r'[^0-9]', '', n) for n in ids_raw))
        candidatos  = [
            n for n in ids_limpios
            if n not in (nit_receptor, dui_receptor) and len(n) >= 8
        ]

        proveedores_db = cargar_proveedores_json()
        nit_prov  = ""
        dui_prov  = ""
        nom_prov  = ""
        es_nuevo  = True

        # Verificar si ya existe en la BD local
        for n in candidatos:
            if n in proveedores_db:
                nit_prov = n
                nom_prov = proveedores_db[n].get("nombre", "")
                es_nuevo = False
                break

        if not nit_prov and candidatos:
            nit_prov = candidatos[0]

        if len(nit_prov) == 9:
            dui_prov = nit_prov

        # ── Detección de nombre para proveedores nuevos ──
        if es_nuevo and nit_prov:
            # Estrategia 1: Buscar por etiqueta "Nombre/Razón Social"
            m_etiqueta = re.search(
                r"(?:Nombre(?:\s+o\s+[Rr]az[oó]n\s+[Ss]ocial)?|"
                r"Raz[oó]n\s+Social)[:\s]+(.*?)"
                r"(?=\s*(?:NIT|NRC|Giro|Actividad|Direcci[oó]n|\n\n|$))",
                texto_emisor, re.I | re.DOTALL
            )
            if m_etiqueta:
                cand = re.sub(r'\s+', ' ', m_etiqueta.group(1)).strip()
                nombre_cliente_palabras = cliente_activo['nombre'].upper().split()[:2]
                if (
                    len(cand) > 5
                    and not any(b in cand.upper() for b in BASURA_ESTRICTA)
                    and not any(p in cand.upper() for p in nombre_cliente_palabras)
                ):
                    nom_prov = cand.upper()

            # Estrategia 2: Línea con denominación comercial
            if not nom_prov:
                for linea in texto_emisor.split('\n')[:30]:
                    L = linea.strip().upper()
                    if len(L) < 5:
                        continue
                    if sum(c.isdigit() for c in L) / len(L) > 0.3:
                        continue
                    if any(b in L for b in PALABRAS_BASURA_NOMBRE + BASURA_ESTRICTA):
                        continue
                    if any(w in L for w in INDICADORES_COMERCIAL):
                        candidato_nombre = re.split(r'\s{4,}|NIT|NRC', L)[0].strip()
                        palabras_cliente = cliente_activo['nombre'].upper().split()[:2]
                        if candidato_nombre and not any(p in candidato_nombre for p in palabras_cliente):
                            nom_prov = candidato_nombre
                            break

            # Limpieza de prefijos
            if nom_prov:
                nom_prov = re.sub(
                    r"^(?:(?:O\s*)?RAZ[OÓ]N\s*SOCIAL|NOMBRE(?: O RAZ[OÓ]N SOCIAL)?|"
                    r"CLIENTE|NOMBRE COMERCIAL|COMERCIAL)[\s:]*",
                    "", nom_prov, flags=re.I
                ).strip()
                nom_prov = re.sub(r'^[\s\-_.,;:]+', '', nom_prov).strip()

            # Validar longitud y calidad
            if (
                not nom_prov
                or len(nom_prov) > 65
                or len(nom_prov) < 4
                or nom_prov.upper() in SUFIJOS_SOLOS
            ):
                nom_prov = "ESCRIBE EL NOMBRE AQUÍ"

        # ── Extracción de montos ──
        exe, gra, iva_val, ret, perc, tot = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        iva_calculado = False

        # FOVIAL y COTRANS (exentos especiales)
        for termino in ["FOVIAL", "COTRANS"]:
            m_linea = re.search(rf"{termino}.{{0,40}}", texto_completo, re.I)
            if m_linea:
                nums = re.findall(r"\d+\.\d{2,4}", m_linea.group(0))
                if nums:
                    exe += max(float(n) for n in nums)
        exe = round(exe, 2)

        # Exentos declarados (tomar el mayor entre FOVIAL/COTRANS y etiqueta)
        m_exe = re.search(
            r"(?:Ventas?\s+Exentas?|Total\s+Exento)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_exe:
            val_exe = limpiar_monto(m_exe.group(1))
            if val_exe > exe:
                exe = val_exe

        # Retención
        m_ret = re.search(
            r"(?:IVA\s+)?(?:Retenido|Retenci[oó]n)[^\d]{0,20}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_ret:
            ret = limpiar_monto(m_ret.group(1))

        # IVA Percibido
        m_perc = re.search(
            r"(?:IVA\s+)?Percibido[^\d]{0,20}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_perc:
            perc = limpiar_monto(m_perc.group(1))

        # Total explícito
        m_tot = re.search(
            r"(?:TOTAL\s+A\s+PAGAR|TOTAL\s+PAGAR|MONTO\s+TOTAL|"
            r"TOTAL\s+OPERACI[OÓ]N|VENTA\s+TOTAL|TOTAL\s+\$|TOTAL\s+FACTURA)"
            r"[^\d]{0,30}(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_tot:
            tot = limpiar_monto(m_tot.group(1))

        # IVA explícito
        m_iva = re.search(
            r"(?:Impuesto\s+.*?Agregado|IVA\s+13%|13%\s+IVA|I\.V\.A\.?|"
            r"DÉBITO\s+FISCAL|CRÉDITO\s+FISCAL)[^\d]{0,30}"
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{1,2})",
            t_clean, re.I
        )
        if m_iva:
            iva_val = limpiar_monto(m_iva.group(1))

        # Triada g/i/t con límite O(n³) controlado
        encontrado = False
        if not (tot > 0 and iva_val > 0):
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
                        if (
                            abs(round(vg * 0.13, 2) - round(vi, 2)) <= 0.05
                            and abs(round(vg + vi + exe - ret, 2) - round(vt, 2)) <= 0.05
                        ):
                            gra, iva_val, tot = vg, vi, vt
                            encontrado = True
                            break

        # Fallback de cálculo
        if not encontrado:
            if tot > 0 and iva_val > 0:
                gra = round(tot - iva_val - exe + ret, 2)
            elif tot > 0 and tipo == "03":
                gra       = round((tot + ret - exe) / 1.13, 2)
                iva_val   = round(tot + ret - exe - gra, 2)
                iva_calculado = True

        # Validación de coherencia
        estado = "✅ OK"
        if tot == 0:
            estado = "⚠️ Sin total"
        elif abs(round(gra + iva_val + exe - ret, 2) - round(tot, 2)) > 0.10:
            estado = "⚠️ Descuadre"

        return {
            "fecha"    : fecha,
            "nit_prov" : nit_prov,
            "dui_prov" : dui_prov,
            "nom_prov" : nom_prov if nom_prov else "ESCRIBE EL NOMBRE AQUÍ",
            "tipo"     : tipo,
            "gen"      : gen,
            "exe"      : exe,
            "gra"      : gra,
            "iva"      : iva_val,
            "ret"      : ret,
            "perc"     : perc,      # ✅ Ahora se extrae activamente
            "tot"      : tot,
            "estado"   : estado,
            "iva_calc" : iva_calculado,
            "es_nuevo" : es_nuevo,
            "nit_nuevo": nit_prov,
        }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
        return {"error": "PDF inválido o con sintaxis corrupta."}
    except Exception as err:
        return {"error": f"Error inesperado: {str(err)}"}


# ─────────────────────────────────────────────
# 6. DIÁLOGO DE DESCARGA SEGURA
# ─────────────────────────────────────────────
@st.dialog("✅ Confirmar Descarga — F-07 Compras")
def ventana_descarga_compras(df_resultados: pd.DataFrame, nombre_archivo: str) -> None:
    st.markdown(
        "Asegúrate de haber procesado **únicamente** los comprobantes "
        "que deseas declarar en el Anexo de Compras."
    )
    st.markdown(f"**Total de registros:** `{len(df_resultados)}`")
    # ✅ Pre-generar bytes UNA SOLA VEZ para evitar re-cálculo en cada render
    excel_bytes = to_excel_hacienda_compras(df_resultados)
    st.download_button(
        label="📥 Confirmar y Descargar Excel F-07",
        data=excel_bytes,
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )


# ─────────────────────────────────────────────
# 7. ENCABEZADO DE PÁGINA
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
<div class="card-receptor">
    <strong>RECEPTOR ACTIVO:</strong> {cliente['nombre']}<br>
    <strong>NIT/DUI:</strong> {cliente['nit']}
</div>
""", unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# 8. SESSION STATE
# ─────────────────────────────────────────────
if 'cola_revision'      not in st.session_state: st.session_state.cola_revision      = []
if 'comp_uploader_key'  not in st.session_state: st.session_state.comp_uploader_key  = str(time.time())
if 'db_compras'         not in st.session_state: st.session_state.db_compras         = pd.DataFrame()
if 'archivos_comp'      not in st.session_state: st.session_state.archivos_comp      = []  # ✅ list, no set()
if 'reporte_compras'    not in st.session_state: st.session_state.reporte_compras    = None

# ─────────────────────────────────────────────
# 9. SIDEBAR — CARGA Y PROCESAMIENTO
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Carga de Compras")
    st.divider()

    archivos = st.file_uploader(
        "Arrastra facturas de proveedores (PDF)",
        type="pdf",
        accept_multiple_files=True,
        key=st.session_state.comp_uploader_key,
        help="Soporta CCF (03), Notas de Crédito (05) y Notas de Débito (06)"
    )

    procesar = st.button(
        "🚀 Procesar Compras",
        type="primary",
        use_container_width=True,
        disabled=not archivos
    )
    limpiar = st.button(
        "🧹 Limpiar Todo",
        type="secondary",
        use_container_width=True
    )

    if limpiar:
        for key in ['db_compras', 'archivos_comp', 'reporte_compras', 'cola_revision']:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.comp_uploader_key = str(time.time())
        st.success("Memoria limpiada correctamente.")
        st.rerun()

    if procesar and archivos:
        procesados_set = set(st.session_state.archivos_comp)
        nuevos = [f for f in archivos if f.name not in procesados_set]

        if not nuevos:
            st.info("ℹ️ Todos los archivos ya fueron procesados.")
        else:
            extracted, duplicados  = [], []
            iva_calc_files         = []
            invalidos, corruptos   = [], []
            nuevos_proveedores     = {}

            bar        = st.progress(0)
            txt_estado = st.empty()
            t_inicio   = time.time()
            total      = len(nuevos)

            for idx, f in enumerate(nuevos):
                # GC periódico
                if idx > 0 and idx % 50 == 0:
                    gc.collect()

                # ETA
                if idx > 0:
                    secs_rest = int(((time.time() - t_inicio) / idx) * (total - idx))
                    mins, secs = divmod(secs_rest, 60)
                    txt_estado.markdown(
                        f"📄 **Procesando:** {idx+1}/{total} — `{f.name}`<br>"
                        f"⏳ **Restante:** {mins:02d}:{secs:02d}",
                        unsafe_allow_html=True
                    )
                else:
                    txt_estado.markdown(f"📄 **Procesando:** 1/{total} — `{f.name}`", unsafe_allow_html=True)

                file_bytes = f.read()

                if len(file_bytes) < 1024:
                    corruptos.append(f.name)
                    st.session_state.archivos_comp.append(f.name)
                    bar.progress((idx + 1) / total)
                    continue

                res = extraer_compras_nativo_pro(file_bytes, cliente)

                # Detección de duplicados por UUID
                codigo_gen      = res.get('gen', '')
                dup_en_memoria  = (
                    not st.session_state.db_compras.empty
                    and codigo_gen
                    and (st.session_state.db_compras['gen'] == codigo_gen).any()
                )
                dup_en_lote     = any(d.get('gen') == codigo_gen for d in extracted) if codigo_gen else False

                if "error_tipo" in res:
                    invalidos.append(f.name)
                elif dup_en_memoria or dup_en_lote:
                    duplicados.append(f.name)
                elif "error" not in res:
                    nom_str  = str(res.get('nom_prov', '')).strip()
                    fech_str = str(res.get('fecha', '')).strip()

                    necesita_revision = (
                        res.get('tot', 0.0) == 0.0
                        or not res.get('gen')
                        or not fech_str
                        or nom_str in ("ESCRIBE EL NOMBRE AQUÍ", "")
                    )

                    if necesita_revision:
                        # Guardar solo referencia de nombre, no bytes completos si es grande
                        st.session_state.cola_revision.append({
                            "archivo": f.name,
                            "bytes"  : file_bytes,
                            "datos"  : res
                        })
                    else:
                        if res.get('iva_calc'):
                            iva_calc_files.append(f.name)
                        if res.get('es_nuevo') and res.get('nit_nuevo'):
                            nuevos_proveedores[res['nit_nuevo']] = res['nom_prov']
                        res['archivo'] = f.name
                        extracted.append(res)
                else:
                    corruptos.append(f.name)

                st.session_state.archivos_comp.append(f.name)
                bar.progress((idx + 1) / total)

            txt_estado.empty()

            if extracted:
                new_df = pd.DataFrame(extracted)
                st.session_state.db_compras = (
                    new_df if st.session_state.db_compras.empty
                    else pd.concat([st.session_state.db_compras, new_df], ignore_index=True)
                )
                st.success(f"✅ {len(extracted)} DTE procesados correctamente.")

            if corruptos or invalidos or duplicados:
                st.warning(
                    f"⚠️ Ignorados: `{len(invalidos)}` tipo incorrecto · "
                    f"`{len(duplicados)}` duplicados · `{len(corruptos)}` dañados"
                )

            st.session_state.reporte_compras = {
                "invalidos"        : invalidos,
                "duplicados"       : duplicados,
                "iva_calc"         : iva_calc_files,
                "nuevos_proveedores": nuevos_proveedores,
                "corruptos"        : corruptos,
            }

    # Resumen rápido en sidebar
    if not st.session_state.db_compras.empty:
        st.divider()
        n_docs = len(st.session_state.db_compras)
        tot_ac = st.session_state.db_compras["tot"].sum()
        iva_ac = st.session_state.db_compras["iva"].sum()
        st.markdown(f"**📄 Documentos:** `{n_docs}`")
        st.markdown(f"**💰 Total compras:** `${tot_ac:,.2f}`")
        st.markdown(f"**🧾 Crédito fiscal:** `${iva_ac:,.2f}`")

# ─────────────────────────────────────────────
# 10. BANDEJA DE REVISIÓN MANUAL
# ─────────────────────────────────────────────
if st.session_state.cola_revision:
    st.markdown("""
    <div class="inbox-revision">
        <h3 class="inbox-titulo">📥 Bandeja de Revisión Manual</h3>
        <p class="inbox-subtxt">
            Se encontraron datos incompletos o borrosos.
            Revisa la vista previa y completa los campos requeridos.
        </p>
    </div>
    """, unsafe_allow_html=True)

    total_cola  = len(st.session_state.cola_revision)
    item_actual = st.session_state.cola_revision[0]
    datos       = item_actual["datos"]

    st.info(f"Quedan **{total_cola}** documento(s) en revisión. Mostrando: `{item_actual['archivo']}`")

    col_img, col_form = st.columns([1.2, 1], gap="large")

    with col_img:
        try:
            with pdfplumber.open(BytesIO(item_actual["bytes"])) as pdf:
                img = pdf.pages[0].to_image(resolution=250).original
                st.image(img, caption=f"📄 {item_actual['archivo']}", use_container_width=True)

                texto_crudo = ""
                for page in pdf.pages:
                    texto_crudo += (page.extract_text(layout=True) or page.extract_text() or "") + "\n"

                st.markdown("**📝 Texto extraído del PDF:**")
                st.text_area(
                    "texto_pdf",
                    value=texto_crudo.strip(),
                    height=200,
                    label_visibility="collapsed"
                )
        except Exception:
            st.error("No se pudo cargar la vista previa.")

    with col_form:
        st.markdown("### ✍️ Corrección de Datos")
        with st.form(key=f"form_rev_{item_actual['archivo']}"):
            f_fecha = st.text_input("📅 Fecha (DD/MM/YYYY) *", value=datos.get("fecha", ""))
            f_gen   = st.text_input("🔑 Código Generación (UUID) *", value=datos.get("gen", ""))

            nom_ini = datos.get("nom_prov", "")
            if nom_ini == "ESCRIBE EL NOMBRE AQUÍ":
                nom_ini = ""
            f_nom = st.text_input("🏢 Razón Social del Proveedor *", value=nom_ini)

            c1_m, c2_m = st.columns(2)
            with c1_m:
                f_tot = st.number_input(
                    "💰 Total a Pagar ($) *",
                    value=float(datos.get("tot", 0.0)),
                    format="%.2f", min_value=0.0
                )
            with c2_m:
                f_exe = st.number_input(
                    "⛽ Exento/Fovial ($)",
                    value=float(datos.get("exe", 0.0)),
                    format="%.2f", min_value=0.0
                )

            st.markdown("")
            c_ap, c_desc = st.columns(2)

            with c_ap:
                aprobar = st.form_submit_button(
                    "✅ Aprobar y Guardar",
                    type="primary",
                    use_container_width=True
                )
            with c_desc:
                descartar = st.form_submit_button(
                    "🗑️ Descartar",
                    use_container_width=True
                )

            if aprobar:
                if not f_fecha or not f_gen or not f_nom or f_tot <= 0:
                    st.error("⚠️ Completa todos los campos marcados con * para continuar.")
                else:
                    nit_actual = datos.get("nit_prov", "")
                    if nit_actual:
                        guardar_proveedor_rapido(nit_actual, f_nom.upper())
                        # Propagar nombre a otros items en cola del mismo NIT
                        for cola_idx in range(1, len(st.session_state.cola_revision)):  # ✅ Var renombrada
                            otro = st.session_state.cola_revision[cola_idx]["datos"]
                            if otro.get("nit_prov") == nit_actual:
                                otro["nom_prov"] = f_nom.upper()

                    datos["fecha"]    = f_fecha
                    datos["gen"]      = f_gen.strip().upper()
                    datos["nom_prov"] = f_nom.strip().upper()
                    datos["tot"]      = f_tot
                    datos["exe"]      = f_exe

                    if f_tot > 0 and datos.get("iva", 0) == 0:
                        datos["gra"]      = round((f_tot - f_exe) / 1.13, 2)
                        datos["iva"]      = round(f_tot - f_exe - datos["gra"], 2)
                        datos["iva_calc"] = True

                    datos["archivo"] = item_actual["archivo"]
                    nuevo_df = pd.DataFrame([datos])
                    st.session_state.db_compras = (
                        nuevo_df if st.session_state.db_compras.empty
                        else pd.concat([st.session_state.db_compras, nuevo_df], ignore_index=True)
                    )
                    st.session_state.cola_revision.pop(0)
                    st.rerun()

            if descartar:
                st.session_state.cola_revision.pop(0)
                st.rerun()

    st.stop()

# ─────────────────────────────────────────────
# 11. PANEL DE ALERTAS
# ─────────────────────────────────────────────
if st.session_state.reporte_compras:
    rep = st.session_state.reporte_compras
    st.markdown("### 📋 Reporte de Procesamiento")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        n = len(rep.get("corruptos", []))
        (st.error if n else st.success)(f"{'💀' if n else '✅'} **{n} Dañados**")
    with c2:
        n = len(rep.get("invalidos", []))
        (st.error if n else st.success)(f"{'⚠️' if n else '✅'} **{n} Ignorados**")
    with c3:
        n = len(rep.get("duplicados", []))
        (st.error if n else st.success)(f"{'🛑' if n else '✅'} **{n} Duplicados**")
    with c4:
        n = len(rep.get("iva_calc", []))
        (st.info if n else st.success)(f"{'🧮' if n else '✅'} **{n} IVA Calculado**")

    # Nuevos proveedores detectados
    nuevos = rep.get("nuevos_proveedores", {})
    if nuevos:
        with st.expander(f"🆕 {len(nuevos)} proveedores nuevos detectados"):
            for nit_np, nom_np in nuevos.items():
                st.markdown(f"- `{nit_np}` → **{nom_np}**")

    st.divider()

# ─────────────────────────────────────────────
# 12. CONTENIDO PRINCIPAL
# ─────────────────────────────────────────────
if not st.session_state.db_compras.empty:
    df = st.session_state.db_compras.copy()

    # ── Filtros ──
    st.markdown("### 🔍 Filtros de Auditoría")
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("Buscar por Proveedor, NIT o UUID 🔎")
    with col_f2:
        tipos_disponibles = sorted(df['tipo'].unique().tolist())
        filtro_tipo = st.multiselect(
            "Tipo DTE 📄",
            options=tipos_disponibles,
            default=tipos_disponibles
        )

    df_f = df.copy()
    if busqueda:
        t = busqueda.upper()
        mask = (
            df_f['nom_prov'].str.contains(t, case=False, na=False)
            | df_f['nit_prov'].str.contains(t, na=False)
            | df_f['dui_prov'].str.contains(t, na=False)
            | df_f['gen'].str.contains(t, case=False, na=False)
        )
        df_f = df_f[mask]
    if filtro_tipo:
        df_f = df_f[df_f['tipo'].isin(filtro_tipo)]

    st.divider()

    tab1, tab2, tab3 = st.tabs([
        "📊 F-07 Compras",
        "🔍 Auditoría Detalle",
        "📈 Resumen por Proveedor"
    ])

    # ── TAB 1: Libro F-07 ──
    with tab1:
        st.markdown("#### 📋 Libro de Compras — Formato F-07")

        COLS_NUM_C = [
            "G. Compra Ext/NS", "H. Internacion Ext/NS", "I. Importacion Ext/NS",
            "J. Compra Gravada", "K. Inter. Gravada Bienes", "L. Impor. Gravada Bienes",
            "M. Impor. Gravada Serv", "N. Crédito Fiscal (IVA)", "O. Total Compras"
        ]

        df_h = pd.DataFrame({
            "A. Fecha Emisión"        : df_f["fecha"],
            "B. Clase"                : "4",
            "C. Tipo Doc"             : df_f["tipo"],
            "D. Num Documento"        : df_f["gen"],
            "E. NIT/NRC Prov"         : df_f["nit_prov"],
            "F. Nombre Prov"          : df_f["nom_prov"],
            "G. Compra Ext/NS"        : df_f["exe"],
            "H. Internacion Ext/NS"   : 0.00,
            "I. Importacion Ext/NS"   : 0.00,
            "J. Compra Gravada"       : df_f["gra"],
            "K. Inter. Gravada Bienes": 0.00,
            "L. Impor. Gravada Bienes": 0.00,
            "M. Impor. Gravada Serv"  : 0.00,
            "N. Crédito Fiscal (IVA)" : df_f["iva"],
            "O. Total Compras"        : df_f["tot"],
            "P. DUI Prov"             : df_f["dui_prov"],
            "Q. Tipo Operacion"       : "1",
            "R. Clasificacion"        : "1",
            "S. Sector"               : "1",
            "T. Tipo Costo/Gasto"     : "1",
            "U. Num Anexo"            : "3",
        })

        st.dataframe(
            df_h.style.format({c: "{:.2f}" for c in COLS_NUM_C if c in df_h.columns}),
            hide_index=True, use_container_width=True
        )

        # Totales resumen
        st.markdown(
            f"> **Total Gravadas:** `${df_h['J. Compra Gravada'].sum():,.2f}` &nbsp;|&nbsp;"
            f"**Crédito Fiscal:** `${df_h['N. Crédito Fiscal (IVA)'].sum():,.2f}` &nbsp;|&nbsp;"
            f"**Total General:** `${df_h['O. Total Compras'].sum():,.2f}`"
        )

        st.markdown("---")
        if st.button("📥 Generar Excel para Hacienda", type="primary"):
            ventana_descarga_compras(
                df_h,
                f"F07_Compras_{cliente['nombre'].replace(' ', '_')}.xlsx"
            )

    # ── TAB 2: Auditoría ──
    with tab2:
        st.markdown("#### 🔍 Detalle Completo de Extracción")
        st.write(f"Mostrando **{len(df_f)}** de **{len(df)}** registros.")

        cols_audit = [c for c in [
            "archivo", "fecha", "tipo", "nom_prov", "nit_prov",
            "exe", "gra", "iva", "ret", "perc", "tot",
            "iva_calc", "estado"
        ] if c in df_f.columns]

        st.dataframe(
            df_f[cols_audit].style.applymap(
                lambda v: "color: #C8D87A" if v == "✅ OK"
                          else ("color: #FF8C69" if "⚠️" in str(v) else ""),
                subset=["estado"] if "estado" in cols_audit else []
            ),
            use_container_width=True, hide_index=True
        )

    # ── TAB 3: Resumen por proveedor ──
    with tab3:
        st.markdown("#### 📈 Resumen Consolidado por Proveedor")
        resumen = df_f.groupby(["nit_prov", "nom_prov"]).agg(
            Documentos   = ("tot", "count"),
            Total_Exento = ("exe", "sum"),
            Total_Grav   = ("gra", "sum"),
            Credito_IVA  = ("iva", "sum"),
            Total_Compras= ("tot", "sum"),
        ).reset_index().sort_values("Total_Compras", ascending=False)

        st.dataframe(
            resumen.style.format({
                "Total_Exento" : "${:,.2f}",
                "Total_Grav"   : "${:,.2f}",
                "Credito_IVA"  : "${:,.2f}",
                "Total_Compras": "${:,.2f}",
            }),
            use_container_width=True, hide_index=True
        )

else:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #6B7A2A;">
        <h3>📂 Sin compras cargadas</h3>
        <p style="color:#4A5520;">
            Usa el panel lateral para cargar y procesar PDFs de compras (CCF, Notas de Crédito/Débito).
        </p>
    </div>
    """, unsafe_allow_html=True)
