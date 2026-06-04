"""
drive_utils.py — Descarga de PDFs/JSON de facturas desde una carpeta de Google
Drive compartida con enlace público ("Cualquiera con el enlace").

Usa la API REST de Google Drive v3 con una **API Key** (sin OAuth) y la
librería `requests` (ya presente en el proyecto), por lo que NO añade
dependencias nuevas.

Requisitos:
    1. La carpeta debe estar compartida como "Cualquiera con el enlace → Lector".
    2. Una API Key creada en Google Cloud con la API de Google Drive habilitada:
       https://console.cloud.google.com/apis/credentials

La utilidad recorre la carpeta y sus subcarpetas, lista los archivos PDF/JSON y
los descarga como bytes, envueltos en `DriveFile` (compatible con el pipeline
existente: solo necesita `.name` y `.read()`).
"""
from __future__ import annotations

import io
import re
from urllib.parse import parse_qs, urlparse

import requests

API_BASE = "https://www.googleapis.com/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
TIPOS_DEFECTO = ("pdf", "json")

# Límite de seguridad para no recorrer un árbol enorme por accidente.
MAX_ARCHIVOS_HARD = 500
TIMEOUT = 30


class DriveError(Exception):
    """Error de acceso / configuración / red contra Google Drive."""


class DriveFile:
    """
    Envoltorio mínimo que imita la interfaz de `UploadedFile` (Streamlit) para
    inyectar archivos de Drive en el mismo pipeline que los subidos a mano.
    """

    __slots__ = ("name", "_data", "_buffer", "size", "origen", "carpeta", "file_id")

    def __init__(self, name: str, data: bytes, *, carpeta: str = "", file_id: str = ""):
        self.name = name
        self._data = data
        self._buffer = io.BytesIO(data)
        self.size = len(data)
        self.origen = "drive"
        self.carpeta = carpeta
        self.file_id = file_id

    def read(self, *args) -> bytes:
        return self._buffer.read(*args)

    def getvalue(self) -> bytes:
        return self._data

    def getbuffer(self):
        return memoryview(self._data)

    def seek(self, *args) -> int:
        return self._buffer.seek(*args)

    def __repr__(self) -> str:
        return f"<DriveFile {self.name!r} ({self.size} bytes)>"


def extraer_folder_id(url_o_id: str) -> tuple[str, str | None]:
    """
    Extrae el ID de carpeta (y el resourceKey opcional) de una URL de Drive.
    Acepta también un ID pegado directamente.

    Devuelve (folder_id, resource_key | None).
    """
    valor = (url_o_id or "").strip()
    if not valor:
        raise DriveError("Falta el enlace o el ID de la carpeta de Drive.")

    resource_key = None
    # /folders/<ID>
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", valor)
    if m:
        folder_id = m.group(1)
    elif valor.startswith("http"):
        # ?id=<ID>
        qs = parse_qs(urlparse(valor).query)
        if "id" in qs:
            folder_id = qs["id"][0]
        else:
            raise DriveError("No se pudo extraer el ID de la carpeta del enlace.")
    else:
        folder_id = valor  # se asume que ya es un ID

    # resourceKey puede venir como ?resourcekey=... en enlaces recientes.
    if "resourcekey" in valor.lower():
        qs = parse_qs(urlparse(valor).query)
        for k in qs:
            if k.lower() == "resourcekey":
                resource_key = qs[k][0]
                break

    if not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id):
        raise DriveError("El ID de carpeta extraído no es válido.")
    return folder_id, resource_key


def _headers(resource_key: str | None, folder_id: str | None = None) -> dict:
    if resource_key and folder_id:
        return {"X-Goog-Drive-Resource-Keys": f"{folder_id}/{resource_key}"}
    return {}


def _listar_hijos(api_key: str, folder_id: str, resource_key: str | None) -> list[dict]:
    """Lista los hijos directos de una carpeta (archivos y subcarpetas)."""
    items: list[dict] = []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed=false",
            "key": api_key,
            "fields": "nextPageToken, files(id, name, mimeType, size, resourceKey)",
            "pageSize": 1000,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        try:
            resp = requests.get(
                f"{API_BASE}/files",
                params=params,
                headers=_headers(resource_key, folder_id),
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            raise DriveError(f"Error de red al listar la carpeta: {e}") from e

        if resp.status_code == 403:
            raise DriveError(
                "Acceso denegado (403). Revisa que la API Key sea válida, que la "
                "API de Google Drive esté habilitada y que la carpeta esté "
                "compartida como 'Cualquiera con el enlace'."
            )
        if resp.status_code == 404:
            raise DriveError("Carpeta no encontrada (404). Verifica el enlace/ID.")
        if resp.status_code != 200:
            raise DriveError(f"Drive respondió {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        items.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items


def listar_archivos(
    api_key: str,
    url_o_id: str,
    *,
    tipos: tuple[str, ...] = TIPOS_DEFECTO,
    recursivo: bool = True,
    max_archivos: int = MAX_ARCHIVOS_HARD,
) -> list[dict]:
    """
    Recorre la carpeta (y subcarpetas si `recursivo`) y devuelve los archivos
    cuyo nombre termina en alguna de las extensiones `tipos`.

    Cada item: {id, name, mimeType, size, resourceKey, carpeta}
    """
    if not api_key:
        raise DriveError("Falta la API Key de Google.")
    tipos_norm = tuple(t.lower().lstrip(".") for t in tipos)
    max_archivos = max(1, min(int(max_archivos), MAX_ARCHIVOS_HARD))

    folder_id, resource_key = extraer_folder_id(url_o_id)
    encontrados: list[dict] = []
    # Pila de (folder_id, resource_key, ruta_legible)
    pila = [(folder_id, resource_key, "")]
    visitados: set[str] = set()

    while pila and len(encontrados) < max_archivos:
        fid, rkey, ruta = pila.pop()
        if fid in visitados:
            continue
        visitados.add(fid)

        for item in _listar_hijos(api_key, fid, rkey):
            if item.get("mimeType") == FOLDER_MIME:
                if recursivo:
                    sub_ruta = f"{ruta}/{item['name']}" if ruta else item["name"]
                    pila.append((item["id"], item.get("resourceKey"), sub_ruta))
                continue
            nombre = item.get("name", "")
            ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
            if ext in tipos_norm:
                item["carpeta"] = ruta or "(raíz)"
                encontrados.append(item)
                if len(encontrados) >= max_archivos:
                    break

    return encontrados


def _es_contenido_binario(resp: "requests.Response") -> bool:
    """True si la respuesta parece un archivo y no una página HTML de Drive."""
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" in ctype:
        return False
    # Una página de aviso de Drive suele ser pequeña y HTML; un PDF empieza con %PDF.
    return bool(resp.content)


def _descargar_publico(file_id: str) -> bytes | None:
    """
    Descarga vía el endpoint público de Drive (el que usa el navegador para
    enlaces 'Cualquiera con el enlace'). No requiere API Key. Maneja el token de
    confirmación para archivos grandes. Devuelve None si no se pudo.
    """
    session = requests.Session()
    base = "https://drive.usercontent.google.com/download"
    try:
        resp = session.get(
            base,
            params={"id": file_id, "export": "download", "confirm": "t"},
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        return None

    if resp.status_code == 200 and _es_contenido_binario(resp):
        return resp.content

    # Si devolvió HTML, puede traer un formulario con token de confirmación.
    if "text/html" in (resp.headers.get("Content-Type") or "").lower():
        html = resp.text
        token = None
        m = re.search(r'name="confirm"\s+value="([^"]+)"', html)
        if m:
            token = m.group(1)
        m_uuid = re.search(r'name="uuid"\s+value="([^"]+)"', html)
        params = {"id": file_id, "export": "download", "confirm": token or "t"}
        if m_uuid:
            params["uuid"] = m_uuid.group(1)
        try:
            resp2 = session.get(base, params=params, timeout=TIMEOUT)
        except requests.RequestException:
            return None
        if resp2.status_code == 200 and _es_contenido_binario(resp2):
            return resp2.content
    return None


def descargar_archivo(api_key: str, file_id: str, resource_key: str | None = None) -> bytes:
    """
    Descarga el contenido binario de un archivo de Drive.

    Intenta primero la API REST (alt=media + API Key). Si Google la rechaza
    (403 u otro), recurre al endpoint público de descarga, que funciona para
    archivos compartidos con enlace 'Cualquiera con el enlace'.
    """
    params = {"alt": "media", "key": api_key, "supportsAllDrives": "true"}
    api_status = None
    try:
        resp = requests.get(
            f"{API_BASE}/files/{file_id}",
            params=params,
            headers=_headers(resource_key, file_id),
            timeout=TIMEOUT,
        )
        api_status = resp.status_code
        if resp.status_code == 200:
            return resp.content
    except requests.RequestException:
        pass  # se intenta el fallback público

    # Fallback: descarga pública (sin API Key).
    contenido = _descargar_publico(file_id)
    if contenido is not None:
        return contenido

    raise DriveError(
        f"No se pudo descargar el archivo {file_id} "
        f"(API: {api_status}). Verifica que la carpeta y sus archivos estén "
        f"compartidos como 'Cualquiera con el enlace'."
    )


def descargar_como_drivefiles(
    api_key: str,
    items: list[dict],
    *,
    max_workers: int = 8,
    progreso=None,
) -> tuple[list[DriveFile], list[tuple[str, str]]]:
    """
    Descarga una lista de items (de `listar_archivos`) en paralelo y los envuelve.

    Es tolerante a fallos: si un archivo no se puede descargar, los demás siguen.

    Args:
        max_workers: nº de descargas simultáneas.
        progreso: callback opcional progreso(hechos:int, total:int) que se llama
                  en el hilo principal tras cada archivo terminado.

    Devuelve (archivos_ok, errores) donde errores es [(nombre, mensaje), ...].
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total = len(items)
    if total == 0:
        return [], []

    def _descargar_uno(it: dict) -> DriveFile:
        data = descargar_archivo(api_key, it["id"], it.get("resourceKey"))
        return DriveFile(
            it.get("name", it["id"]),
            data,
            carpeta=it.get("carpeta", ""),
            file_id=it["id"],
        )

    archivos: list[DriveFile] = []
    errores: list[tuple[str, str]] = []
    workers = max(1, min(int(max_workers), 16))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futuros = {ex.submit(_descargar_uno, it): it for it in items}
        hechos = 0
        for fut in as_completed(futuros):
            it = futuros[fut]
            hechos += 1
            try:
                archivos.append(fut.result())
            except Exception as e:  # noqa: BLE001
                errores.append((it.get("name", it.get("id", "?")), str(e)))
            if progreso:
                try:
                    progreso(hechos, total)
                except Exception:  # noqa: BLE001
                    pass

    return archivos, errores
