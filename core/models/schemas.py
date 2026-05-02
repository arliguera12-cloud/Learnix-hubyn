# core/modelos/schemas.py
"""
Esquemas de validación para datos tributarios.
"""

from typing import Optional, Dict, Any

# ═══════════════════════════════════════════════════════════════
# ESQUEMA DE DATO EXTRAÍDO GENÉRICO
# ═══════════════════════════════════════════════════════════════

class DTEExtraido:
    """Clase base para datos extraídos de DTE."""
    
    def __init__(self):
        self.fuente: str = "PDF"  # PDF, JSON, Manual
        self.motor: str = "Nativo"  # Motor que lo extrajo
        self.tipo: str = ""  # Tipo de DTE (01, 03, 05, 06, 07, 11, 14)
        self.fecha: str = ""
        self.nit: str = ""
        self.nombre: str = ""
        self.gra: float = 0.0  # Monto gravado
        self.iva: float = 0.0  # IVA
        self.exe: float = 0.0  # Exento
        self.tot: float = 0.0  # Total
        self.confianza_nit: str = "media"  # Nivel de confianza
        self.confianza_rs: str = "media"
        self.confianza_gemini: Optional[str] = None
        self.gemini_obs: Optional[str] = None
        self.iva_calculado: bool = False  # Flag si IVA fue calculado
        self.archivo: str = ""
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


# ═══════════════════════════════════════════════════════════════
# ESQUEMA ESPECÍFICO PARA VENTAS
# ═══════════════════════════════════════════════════════════════

class VentaExtraida(DTEExtraido):
    """Específico para ventas (DTE 01, 03, 05, 06, 11)."""
    
    def __init__(self):
        super().__init__()
        self.ctrl: str = ""  # Número de control DTE
        self.gen: str = ""  # Código de generación (UUID)
        self.sello: str = ""  # Sello de recepción
        self.nos: float = 0.0  # No sujetas
        self.exp_serv: float = 0.0  # Exportación servicios
        self.t_ing: str = "3"  # Tipo de ingreso
        self.clase: str = "4"


# ═══════════════════════════════════════════════════════════════
# ESQUEMA PARA COMPRAS
# ═══════════════════════════════════════════════════════════════

class CompraExtraida(DTEExtraido):
    """Específico para compras (DTE 03, 05, 06)."""
    
    def __init__(self):
        super().__init__()
        self.nit_prov: str = ""
        self.nom_prov: str = ""
        self.dui_prov: str = ""
        self.ret: float = 0.0  # Retenciones
        self.perc: float = 0.0  # Percepciones
        self.es_nuevo: bool = False
        self.nit_nuevo: str = ""
        self.estado: str = "OK"


# ═══════════════════════════════════════════════════════════════
# ESQUEMA PARA RETENCIONES
# ═══════════════════════════════════════════════════════════════

class RetencionExtraida(DTEExtraido):
    """Específico para retenciones (DTE-07)."""
    
    def __init__(self):
        super().__init__()
        self.nit_contraparte: str = ""
        self.nom_contraparte: str = ""
        self.monto_sujeto: float = 0.0
        self.monto_retenido: float = 0.0
        self.ret_calc: bool = False
        self.estado: str = "OK"
