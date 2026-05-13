"""
tools/upload_manuales.py — Sube manuales de anexos Hacienda a Gemini Files API.

Uso:
    python tools/upload_manuales.py [carpeta]

Por defecto busca PDFs en data/manuales/.
Imprime las URIs resultantes listas para pegar en .streamlit/secrets.toml
bajo la sección [manuales].

Requisitos:
    GEMINI_API_KEY en variable de entorno, o se pide interactivamente.

Notas:
    Los archivos en Gemini Files API expiran a las 48 horas de subida.
    Ejecuta este script de nuevo antes de cada sesión si han pasado 48h.
"""
import argparse
import os
import sys
import time
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' no está instalado. Ejecuta: pip install requests")
    sys.exit(1)

# ─── Claves de manuales y tipos DTE asociados ─────────────────────────────────

MANUAL_KEYS = [
    "ventas_contribuyentes",     # DTE 03, 05, 06 ventas
    "ventas_consumidor",         # DTE 01
    "compras_contribuyentes",    # DTE 03, 05, 06 compras
    "retencion_1pct",            # DTE 07
    "percepcion_1pct",           # Anexo 8
    "compras_sujetos_excluidos", # DTE 14 (casilla 66)
    "f14_retenciones",           # F-14 retenciones
]

_UPLOAD_URL = (
    "https://generativelanguage.googleapis.com/upload/v1beta/files"
    "?uploadType=multipart&key={api_key}"
)
_MAX_RETRIES = 3
_BACKOFF_DELAYS = [2, 4, 8]  # seconds


# ─── Subida de un PDF ─────────────────────────────────────────────────────────

def _subir_pdf(pdf_path: Path, key: str, api_key: str) -> dict | None:
    """
    Sube un PDF a Gemini Files API usando multipart/related.

    Returns dict with keys: uri, name, expireTime  — or None on failure.
    """
    boundary = f"boundary_{uuid.uuid4().hex}"
    url = _UPLOAD_URL.format(api_key=api_key)

    metadata_json = f'{{"file": {{"display_name": "{key}"}}}}'.encode()
    pdf_bytes = pdf_path.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode() + metadata_json + (
        f"\r\n--{boundary}\r\n"
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + pdf_bytes + f"\r\n--{boundary}--".encode()

    headers = {
        "Content-Type": f"multipart/related; boundary={boundary}",
        "Content-Length": str(len(body)),
    }

    last_error = ""
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(url, headers=headers, data=body, timeout=120)

            if resp.status_code == 200:
                data = resp.json()
                file_info = data.get("file", data)
                return {
                    "uri"       : file_info.get("uri", ""),
                    "name"      : file_info.get("name", ""),
                    "expireTime": file_info.get("expireTime", "desconocido"),
                }

            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_DELAYS[attempt]
                    print(
                        f"    [intento {attempt+1}/{_MAX_RETRIES}] Error transitorio "
                        f"({resp.status_code}). Reintentando en {wait}s…"
                    )
                    time.sleep(wait)
                    continue
                print(f"    ERROR tras {_MAX_RETRIES} intentos: {last_error}")
                return None

            # Error no transitorio
            print(
                f"    ERROR HTTP {resp.status_code}: "
                f"{resp.text[:300]}"
            )
            return None

        except requests.exceptions.Timeout:
            last_error = "Timeout (120s) al subir el archivo."
            print(f"    [intento {attempt+1}/{_MAX_RETRIES}] {last_error}")
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BACKOFF_DELAYS[attempt])
                continue
            return None

        except requests.exceptions.ConnectionError as exc:
            print(f"    ERROR de conexión: {exc}")
            return None

        except Exception as exc:
            print(f"    ERROR inesperado: {exc}")
            return None

    return None


# ─── Obtención de la API key ──────────────────────────────────────────────────

def _obtener_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        print(f"  API key obtenida de GEMINI_API_KEY (***{key[-4:]})")
        return key
    try:
        key = input("Ingresa tu GEMINI_API_KEY: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelado por el usuario.")
        sys.exit(0)
    if not key:
        print("ERROR: no se proporcionó API key.")
        sys.exit(1)
    return key


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sube manuales de anexos Hacienda a Gemini Files API.",
    )
    parser.add_argument(
        "carpeta",
        nargs="?",
        default="data/manuales",
        help="Carpeta con los PDFs (por defecto: data/manuales/)",
    )
    args = parser.parse_args()

    carpeta = Path(args.carpeta)
    if not carpeta.exists():
        print(f"ERROR: La carpeta '{carpeta}' no existe.")
        sys.exit(1)

    api_key = _obtener_api_key()

    print(f"\nBuscando PDFs en: {carpeta.resolve()}")
    print("─" * 60)

    resultados: dict[str, str] = {}
    no_encontrados: list[str] = []

    for key in MANUAL_KEYS:
        pdf_path = carpeta / f"{key}.pdf"
        if not pdf_path.exists():
            print(f"  [OMITIDO] {key}.pdf — no encontrado en {carpeta}")
            no_encontrados.append(key)
            continue

        size_kb = pdf_path.stat().st_size // 1024
        print(f"  Subiendo {key}.pdf ({size_kb} KB)…")

        info = _subir_pdf(pdf_path, key, api_key)
        if info:
            resultados[key] = info["uri"]
            print(f"    OK  URI:    {info['uri']}")
            print(f"        Expira: {info['expireTime']}")
        else:
            print(f"    FALLO al subir {key}.pdf")

    # ─── Salida para secrets.toml ─────────────────────────────────────────────
    if resultados:
        print("\n" + "═" * 60)
        print("Pega esto en .streamlit/secrets.toml:")
        print("═" * 60)
        print("[manuales]")
        for key, uri in resultados.items():
            print(f'{key} = "{uri}"')
        print("═" * 60)
    else:
        print("\nNo se subió ningún manual.")

    if no_encontrados:
        print(
            f"\nManuales no encontrados ({len(no_encontrados)}): "
            + ", ".join(no_encontrados)
        )
        print(
            f"Coloca los PDFs en '{carpeta}/' con los nombres exactos:\n"
            + "\n".join(f"  {k}.pdf" for k in no_encontrados)
        )

    print(
        "\nNOTA: Los archivos en Gemini Files API expiran a las 48h. "
        "Vuelve a ejecutar este script si las URIs dejan de funcionar."
    )


if __name__ == "__main__":
    main()
