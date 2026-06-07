"""
training_examples.py — Sistema de aprendizaje por correcciones manuales.

Cuando el usuario aprueba una corrección en Revisión Manual, se guarda como
ejemplo de entrenamiento y se inyecta como few-shot en futuros prompts de Groq.

Formato de data/training_examples.json:
{
  "compras":  [ { "texto": "...", "campos": {...}, "ts": "..." }, ... ],
  "ventas":   [ ... ],
  "ret":      [ ... ],
  "sujetos":  [ ... ]
}
"""
from __future__ import annotations
import json
import os
import datetime

_MAX_EJEMPLOS_POR_TIPO = 20   # cap por tipo para no inflar el prompt
_MAX_CHARS_TEXTO       = 600  # snippet del PDF a guardar
_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "training_examples.json")


def _leer() -> dict:
    try:
        with open(_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _escribir(data: dict) -> None:
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    tmp = _FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FILE)


def registrar_correccion(
    tipo_dte: str,
    texto_pdf: str,
    campos_originales: dict,
    campos_corregidos: dict,
) -> None:
    """
    Guarda una corrección humana como ejemplo de entrenamiento.

    Args:
        tipo_dte:          "compras" | "ventas" | "ret" | "sujetos"
        texto_pdf:         Texto extraído del PDF (se guarda solo un snippet).
        campos_originales: Lo que el sistema extrajo (puede tener vacíos).
        campos_corregidos: Lo que el humano ingresó correctamente.
    """
    # Solo guardar si hubo cambios reales
    cambios = {
        k: v for k, v in campos_corregidos.items()
        if v and v != campos_originales.get(k, "")
    }
    if not cambios:
        return

    data = _leer()
    lista = data.get(tipo_dte, [])

    ejemplo = {
        "texto"    : texto_pdf[:_MAX_CHARS_TEXTO].strip(),
        "campos"   : {k: v for k, v in campos_corregidos.items() if v},
        "cambios"  : list(cambios.keys()),
        "ts"       : datetime.datetime.now().isoformat(timespec="seconds"),
    }

    # Insertar al frente (más recientes primero) y limitar tamaño
    lista.insert(0, ejemplo)
    lista = lista[:_MAX_EJEMPLOS_POR_TIPO]

    data[tipo_dte] = lista
    _escribir(data)


def cargar_ejemplos_prompt(tipo_dte: str, max_ejemplos: int = 3) -> str:
    """
    Retorna un bloque de texto con ejemplos few-shot para inyectar en el prompt.
    Retorna string vacío si no hay ejemplos.
    """
    data = _leer()
    lista = data.get(tipo_dte, [])[:max_ejemplos]
    if not lista:
        return ""

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"EJEMPLOS DE CORRECCIONES PREVIAS (aprende de estos — {len(lista)} ejemplos)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, ej in enumerate(lista, 1):
        campos_str = ", ".join(f'{k}="{v}"' for k, v in ej["campos"].items() if v)
        lines.append(f"Ejemplo {i} (campos corregidos por auditor): {campos_str}")
        lines.append(f"  Texto parcial: {ej['texto'][:200]}...")
        lines.append("")

    return "\n".join(lines)


def contar_ejemplos(tipo_dte: str | None = None) -> dict | int:
    """
    Retorna conteo de ejemplos. Si tipo_dte es None, retorna dict por tipo.
    """
    data = _leer()
    if tipo_dte:
        return len(data.get(tipo_dte, []))
    return {k: len(v) for k, v in data.items()}
