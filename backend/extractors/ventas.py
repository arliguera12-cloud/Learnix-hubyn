"""
Extractor de DTEs de Ventas (DTE-01/03/05/06).
Lógica portada de pages/1_Extractor_DTE_Ventas.py sin dependencias de Streamlit.
"""
import re
import pdfplumber

from utils.pdf_utils import (
    safe_str,
    limpiar_monto,
    extraer_y_formatear_fecha,
    extraer_texto_pdf,
    extraer_nombre_receptor_columna,
)
from utils.ai_utils import (
    gemini_disponible,
    procesar_dte_con_gemini,
    es_nombre_sospechoso,
)
from utils.gemini_vision import extraer_dte_con_vision, vision_disponible
from utils.qr_reader import extraer_datos_qr as _extraer_qr
from utils.constants import (
    TIPOS_CONTRIBUYENTES,
    TIPOS_CONSUMIDOR,
    TODOS_TIPOS_VALIDOS,
    WINDOW_BEFORE,
    WINDOW_AFTER,
)



import logging
_log = logging.getLogger(__name__)

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

def es_linea_direccion(texto: str) -> bool:
    L = safe_str(texto).upper().strip()
    return any(L.startswith(p) or (f" {p}" in L[:50]) for p in PREFIJOS_DIRECCION)



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
