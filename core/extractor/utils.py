# core/extractores/utils.py
"""
Utilidades compartidas entre extractores.
"""

import re
from datetime import datetime


def limpiar_monto(monto_str) -> float:
    """
    Convierte string de monto a float de forma segura.
    Maneja formatos: 1,234.56 / 1.234,56 / 1234.56 / $1,234.56
    """
    try:
        if not monto_str:
            return 0.0

        s = str(monto_str).replace(' ', '').replace('$', '').strip()
        
        if not s:
            return 0.0

        # Formato 1,234.56 (coma como millar, punto como decimal)
        if ',' in s and '.' in s:
            return round(float(s.replace(',', '')), 2)
        
        # Formato 1.234,56 (punto como millar, coma como decimal)
        if ',' in s and '.' not in s:
            return round(float(s.replace(',', '.')), 2)
        
        return round(float(s), 2)

    except (ValueError, AttributeError, TypeError):
        return 0.0


def extraer_y_formatear_fecha(texto: str) -> str:
    """
    Extractor de fechas en cascada.
    Soporta múltiples formatos: YYYY-MM-DD, DD/MM/YYYY, texto con nombres de mes, etc.
    """
    meses = {
        'ENE': '01', 'ENERO': '01',
        'FEB': '02', 'FEBRERO': '02',
        'MAR': '03', 'MARZO': '03',
        'ABR': '04', 'ABRIL': '04',
        'MAY': '05', 'MAYO': '05',
        'JUN': '06', 'JUNIO': '06',
        'JUL': '07', 'JULIO': '07',
        'AGO': '08', 'AGOSTO': '08',
        'SEP': '09', 'SEPTIEMBRE': '09',
        'OCT': '10', 'OCTUBRE': '10',
        'NOV': '11', 'NOVIEMBRE': '11',
        'DIC': '12', 'DICIEMBRE': '12'
    }

    # Intento 1: Formato explícito con nombre de mes
    for m in re.finditer(
        r"\b(\d{1,2})\s*(?:de\s*|/|-)?\s*([a-zA-Z]{3,})\s*(?:de\s*|/|-)?\s*(\d{4})\b",
        texto, re.I
    ):
        d, mes_str, y = m.groups()
        if int(y) < 2020:
            continue
        for key, value in meses.items():
            if mes_str.upper().startswith(key):
                return f"{int(d):02d}/{value}/{y}"

    # Intento 2: Formato numérico estándar YYYY-MM-DD
    for m in re.finditer(
        r"\b(20[2-3]\d)\s*[-/]\s*(0[1-9]|1[0-2])\s*[-/]\s*([0-2]\d|3[01])\b",
        texto
    ):
        y, mo, d = m.groups()
        return f"{int(d):02d}/{int(mo):02d}/{y}"

    # Intento 3: Formato flexible DD/MM/YYYY o DD-MM-YYYY
    for m in re.finditer(
        r"\b(\d{1,4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,4})\b",
        texto
    ):
        p1, p2, p3 = m.groups()
        
        # Detectar año de 4 dígitos
        if len(p1) == 4 and 2020 <= int(p1) <= 2030:
            y, mo, d = p1, p2, p3
        elif len(p3) in [2, 4]:
            y, d, mo = p3, p1, p2
            if len(y) == 2:
                y = f"20{y}"
            if int(mo) > 12 and int(d) <= 12:
                mo, d = d, mo
        else:
            continue

        try:
            if 2020 <= int(y) <= 2030 and 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
                return f"{int(d):02d}/{int(mo):02d}/{y}"
        except ValueError:
            continue

    return ""


def formatear_uuid(raw_str: str) -> str:
    """
    Convierte un UUID sin guiones al formato estándar con guiones.
    Entrada: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    Salida: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    """
    if not raw_str:
        return ""

    limpio = re.sub(r'[^A-F0-9]', '', str(raw_str).upper())
    
    if len(limpio) >= 32:
        return f"{limpio[:8]}-{limpio[8:12]}-{limpio[12:16]}-{limpio[16:20]}-{limpio[20:32]}"
    
    return raw_str.upper()


def normalizar_nit(nit_raw: str) -> str:
    """
    Normaliza NIT: extrae solo dígitos.
    """
    return re.sub(r'[^0-9]', '', str(nit_raw))


def es_nit_valido(nit: str) -> bool:
    """
    Valida que un NIT tenga 14 dígitos.
    """
    nit_limpio = normalizar_nit(nit)
    return len(nit_limpio) == 14


def es_dui_valido(dui: str) -> bool:
    """
    Valida que un DUI tenga 9 dígitos.
    """
    dui_limpio = normalizar_nit(dui)
    return len(dui_limpio) == 9
