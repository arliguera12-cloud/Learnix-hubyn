"""
Pilar 4 — Validación RAG con manuales oficiales de Hacienda.

Flujo:
  1. Los PDFs de manuales se convierten a texto y se fragmentan (chunks).
  2. Al validar un DTE, se buscan los chunks más relevantes (búsqueda por palabras clave).
  3. Groq (llama3-8b-8192) compara el DTE contra esos fragmentos y emite alertas de auditoría.
"""
from __future__ import annotations

import os
import re
import json
import hashlib
import pdfplumber
import streamlit as st

from utils.gemini_utils import _get_api_key


# ─────────────────────────────────────────────
# 1. CARGA Y FRAGMENTACIÓN DE MANUALES
# ─────────────────────────────────────────────
_MANUALES_DIR = os.path.join(os.path.dirname(__file__), "..", "manuales_hacienda")
_CHUNK_SIZE   = 800   # caracteres por fragmento
_CHUNK_OVERLAP = 150  # solapamiento entre fragmentos


def _extraer_texto_pdf(path: str) -> str:
    texto = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texto.append(t)
    except Exception:
        pass
    return "\n".join(texto)


def _fragmentar(texto: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    chunks, i = [], 0
    while i < len(texto):
        chunks.append(texto[i: i + size])
        i += size - overlap
    return chunks


@st.cache_data(show_spinner=False)
def cargar_base_conocimiento() -> list[dict]:
    """
    Lee todos los PDFs en /manuales_hacienda/ y devuelve una lista de chunks:
      [{"fuente": "nombre.pdf", "texto": "...", "hash": "..."}]

    Cacheado por Streamlit — se ejecuta una sola vez por sesión.
    Coloca aquí los 7 PDFs de Hacienda que subiste.
    """
    if not os.path.exists(_MANUALES_DIR):
        os.makedirs(_MANUALES_DIR)
        return []

    base: list[dict] = []
    for fname in os.listdir(_MANUALES_DIR):
        if not fname.lower().endswith(".pdf"):
            continue
        path  = os.path.join(_MANUALES_DIR, fname)
        texto = _extraer_texto_pdf(path)
        if not texto.strip():
            continue
        for chunk in _fragmentar(texto):
            base.append({
                "fuente": fname,
                "texto":  chunk,
                "hash":   hashlib.md5(chunk.encode()).hexdigest(),
            })

    return base


# ─────────────────────────────────────────────
# 2. RECUPERACIÓN DE CONTEXTO RELEVANTE
# ─────────────────────────────────────────────
_STOPWORDS = {"de", "la", "el", "en", "que", "y", "a", "los", "las", "por", "con", "se"}


def _recuperar_chunks(consulta: str, base: list[dict], top_k: int = 5) -> list[dict]:
    """
    Búsqueda por palabras clave (TF simplificado).
    Reemplazar con pgvector para semántica real.
    """
    palabras = {
        w.lower() for w in re.findall(r"\w+", consulta)
        if len(w) > 3 and w.lower() not in _STOPWORDS
    }
    if not palabras:
        return base[:top_k]

    scored = []
    for chunk in base:
        texto_low = chunk["texto"].lower()
        score = sum(1 for p in palabras if p in texto_low)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


# ─────────────────────────────────────────────
# 3. VALIDACIÓN CON GEMINI
# ─────────────────────────────────────────────
_PROMPT_AUDITORIA = """
Eres un auditor fiscal experto en El Salvador. Analiza el DTE procesado
y compáralo ESTRICTAMENTE contra las reglas de los manuales oficiales del
Ministerio de Hacienda proporcionados como contexto.

=== CONTEXTO (fragmentos de manuales oficiales) ===
{contexto}

=== DTE PROCESADO ===
{dte_json}

=== INSTRUCCIONES ===
Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{{
  "alertas": [
    {{
      "nivel":   "ERROR" | "ADVERTENCIA" | "INFO",
      "campo":   "nombre del campo afectado",
      "mensaje": "descripción clara de la violación o inconsistencia",
      "regla":   "referencia al manual o artículo (si aplica)"
    }}
  ],
  "valido": true | false,
  "resumen": "una sola oración de resumen"
}}

Si el DTE cumple todas las reglas, devuelve alertas = [] y valido = true.
No incluyas texto fuera del JSON.
""".strip()


def validar_dte_con_rag(
    dte_data: dict,
    tipo_dte: str,
    base_conocimiento: list[dict] | None = None,
) -> dict:
    """
    Valida un DTE procesado contra los manuales de Hacienda usando Groq.

    Args:
        dte_data:          Dict con los campos extraídos del DTE.
        tipo_dte:          '01','03','07', etc.
        base_conocimiento: Lista de chunks; si None, carga automáticamente.

    Returns:
        Dict con claves: 'valido', 'alertas', 'resumen'.
        En caso de error retorna {'valido': None, 'alertas': [], 'resumen': str(error)}.
    """
    from groq import Groq

    api_key = _get_api_key()
    if not api_key:
        return {
            "valido":  None,
            "alertas": [],
            "resumen": "GROQ_API_KEY no configurada — validación RAG no disponible.",
        }

    if base_conocimiento is None:
        base_conocimiento = cargar_base_conocimiento()

    if not base_conocimiento:
        return {
            "valido":  None,
            "alertas": [],
            "resumen": "Sin manuales cargados. Copia los PDFs a /manuales_hacienda/.",
        }

    consulta = f"DTE tipo {tipo_dte} {json.dumps(dte_data, ensure_ascii=False)}"
    chunks   = _recuperar_chunks(consulta, base_conocimiento)
    contexto = "\n\n---\n\n".join(
        f"[{c['fuente']}]\n{c['texto']}" for c in chunks
    )

    prompt = _PROMPT_AUDITORIA.format(
        contexto=contexto,
        dte_json=json.dumps(dte_data, ensure_ascii=False, indent=2),
    )

    try:
        client   = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un auditor fiscal. Responde ÚNICAMENTE con JSON válido, sin texto adicional.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        raw = re.sub(r"^```json\s*|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"valido": None, "alertas": [], "resumen": "Respuesta de Groq no parseable."}
    except Exception as e:
        return {"valido": None, "alertas": [], "resumen": f"Error RAG: {str(e)[:120]}"}


# ─────────────────────────────────────────────
# 4. HELPER UI — MOSTRAR ALERTAS EN STREAMLIT
# ─────────────────────────────────────────────
def mostrar_alertas_rag(resultado: dict) -> None:
    """
    Renderiza las alertas de auditoría RAG en Streamlit.
    Llama después de validar_dte_con_rag().
    """
    if resultado.get("valido") is None:
        st.caption(f"⚠️ RAG: {resultado.get('resumen', '')}")
        return

    alertas = resultado.get("alertas", [])
    resumen = resultado.get("resumen", "")

    if not alertas:
        st.success(f"✅ Auditoría RAG: {resumen}", icon="✅")
        return

    colores = {"ERROR": "#F85149", "ADVERTENCIA": "#D29922", "INFO": "#58A6FF"}
    iconos  = {"ERROR": "🔴", "ADVERTENCIA": "⚠️", "INFO": "ℹ️"}

    with st.expander(f"🔍 Auditoría RAG — {len(alertas)} alerta(s)", expanded=True):
        st.caption(resumen)
        for a in alertas:
            nivel  = a.get("nivel", "INFO")
            color  = colores.get(nivel, "#58A6FF")
            icono  = iconos.get(nivel, "ℹ️")
            regla  = f" · <em>{a.get('regla','')}</em>" if a.get("regla") else ""
            st.markdown(
                f'<div style="padding:8px 12px; margin:4px 0; border-left:3px solid {color};'
                f' background:#0d1117; border-radius:4px; font-size:0.83rem;">'
                f'{icono} <strong>{a.get("campo","—")}</strong>{regla}<br>'
                f'<span style="color:{color};">{a.get("mensaje","")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
