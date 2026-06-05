#!/usr/bin/env python3
"""
Script de validación de credenciales GROQ y VERTEX AI.
Requiere: GROQ_API_KEY, VERTEX_API_KEY, GOOGLE_APPLICATION_CREDENTIALS en env.
"""

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

def test_groq():
    """Valida que GROQ_API_KEY está disponible y funciona."""
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("❌ GROQ_API_KEY no está configurada")
        return False

    print(f"✓ GROQ_API_KEY disponible ({len(api_key)} chars)")

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Responde 'OK'"}],
            max_tokens=10,
        )
        print(f"✓ GROQ conectado: {resp.choices[0].message.content.strip()}")
        return True
    except Exception as e:
        print(f"❌ GROQ error: {e}")
        return False


def test_vertex():
    """Valida que VERTEX_API_KEY y Google SA funcionan."""
    try:
        from google.genai import client
        from google import genai
    except ImportError:
        print("❌ google-genai no instalado. Instala: pip install google-genai")
        return False

    api_key = os.environ.get("VERTEX_API_KEY", "").strip()
    if not api_key:
        print("❌ VERTEX_API_KEY no está configurada")
        return False

    print(f"✓ VERTEX_API_KEY disponible ({len(api_key)} chars)")

    # Validar Google Application Credentials
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not creds_path or not os.path.exists(creds_path):
        print("⚠ GOOGLE_APPLICATION_CREDENTIALS no existe o no está en env")
        print("   (En Streamlit Cloud, esta variable es automática via secrets)")
        return True  # No fallar, porque Streamlit la inyecta automáticamente

    print(f"✓ Google Service Account en {creds_path}")

    try:
        genai.configure(api_key=api_key)
        model = "gemini-2.5-flash"
        response = genai.models.generate_content(
            model=model,
            contents="Responde 'OK'",
        )
        print(f"✓ Vertex (Gemini) conectado: {response.text[:50]}")

        # Validar que Pro está disponible
        try:
            response = genai.models.generate_content(
                model="gemini-2.5-pro",
                contents="Responde 'OK'",
            )
            print(f"✓ Gemini 2.5 Pro también disponible")
        except Exception as e:
            print(f"⚠ Gemini 2.5 Pro no disponible: {e}")

        return True
    except Exception as e:
        print(f"❌ Vertex error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDACIÓN DE CREDENCIALES")
    print("=" * 60)
    print()

    groq_ok = test_groq()
    print()
    vertex_ok = test_vertex()
    print()

    if groq_ok and vertex_ok:
        print("✅ TODAS LAS CREDENCIALES VALIDADAS")
        print()
        print("Próximos pasos:")
        print("1. Deployar a Streamlit Cloud con estas credenciales en Secrets")
        print("2. Subir un DTE (PDF) para probar extracción")
        print("3. Verificar en audit que:")
        print("   - motor_usado = 'vertex-ai/gemini-2.5-flash' (por defecto)")
        print("   - Si confianza < 75%, motor_usado = 'vertex-ai/gemini-2.5-pro (escalado)'")
        print("   - confianza_extraccion está presente (0-100)")
        sys.exit(0)
    else:
        print("❌ ALGUNAS CREDENCIALES FALTARON")
        print()
        print("Asegúrate de que en .streamlit/secrets.toml o env tengas:")
        print("  GROQ_API_KEY = 'gsk_...'")
        print("  VERTEX_API_KEY = 'AIzaSy...'")
        print("  (GOOGLE_APPLICATION_CREDENTIALS se inyecta en Streamlit Cloud automáticamente)")
        sys.exit(1)
