"""
gmail_utils.py — Descarga de adjuntos (facturas/DTEs) desde Gmail vía IMAP.

Usa la librería estándar de Python (`imaplib` + `email`), por lo que NO añade
dependencias nuevas al proyecto.

Autenticación: el usuario debe activar la verificación en 2 pasos en su cuenta
Google y generar una "Contraseña de aplicación" (App Password):
    https://myaccount.google.com/apppasswords
Esa contraseña de 16 caracteres es la que se usa aquí (NUNCA la contraseña
normal de Gmail).

Búsqueda: se aprovecha la extensión de Gmail `X-GM-RAW`, que permite usar la
misma sintaxis de búsqueda de la interfaz web (from:, subject:, has:attachment,
filename:, newer_than:, etc.).
"""
from __future__ import annotations

import email
import imaplib
import io
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

# Límite de seguridad para no descargar correos gigantes por accidente.
MAX_CORREOS_HARD = 200


class GmailError(Exception):
    """Error de conexión / autenticación / búsqueda en Gmail."""


class GmailFile:
    """
    Envoltorio mínimo que imita la interfaz de `st.runtime.uploaded_file_manager
    .UploadedFile` para que los adjuntos de Gmail puedan inyectarse en el mismo
    pipeline que los archivos subidos a mano (solo necesita `.name` y `.read()`).
    """

    __slots__ = ("name", "_data", "_buffer", "size", "origen", "remitente", "asunto")

    def __init__(self, name: str, data: bytes, *, remitente: str = "", asunto: str = ""):
        self.name = name
        self._data = data
        self._buffer = io.BytesIO(data)
        self.size = len(data)
        self.origen = "gmail"
        self.remitente = remitente
        self.asunto = asunto

    def read(self, *args) -> bytes:
        return self._buffer.read(*args)

    def getvalue(self) -> bytes:
        return self._data

    def getbuffer(self):
        return memoryview(self._data)

    def seek(self, *args) -> int:
        return self._buffer.seek(*args)

    def __repr__(self) -> str:
        return f"<GmailFile {self.name!r} ({self.size} bytes)>"


def _decodificar(valor: str | None) -> str:
    """Decodifica encabezados MIME (RFC 2047) a texto legible."""
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor)))
    except Exception:
        return valor


def _construir_query(
    remitente: str = "",
    texto: str = "",
    dias: int | None = 30,
    tipos: tuple[str, ...] = ("pdf", "json"),
    solo_adjuntos: bool = True,
) -> str:
    """Arma una consulta estilo Gmail (X-GM-RAW)."""
    partes: list[str] = []

    if solo_adjuntos:
        partes.append("has:attachment")

    if tipos:
        filtros_tipo = " OR ".join(f"filename:{t.lstrip('.')}" for t in tipos)
        partes.append(f"({filtros_tipo})")

    if remitente.strip():
        # Permite varios remitentes separados por coma/espacio.
        remitentes = [r.strip() for r in remitente.replace(",", " ").split() if r.strip()]
        if len(remitentes) == 1:
            partes.append(f"from:{remitentes[0]}")
        elif remitentes:
            partes.append("(" + " OR ".join(f"from:{r}" for r in remitentes) + ")")

    if texto.strip():
        partes.append(texto.strip())

    if dias and dias > 0:
        partes.append(f"newer_than:{int(dias)}d")

    return " ".join(partes).strip() or "has:attachment"


def conectar(email_addr: str, app_password: str, mailbox: str = '"[Gmail]/All Mail"') -> imaplib.IMAP4_SSL:
    """Abre una conexión IMAP autenticada y selecciona el buzón."""
    if not email_addr or not app_password:
        raise GmailError("Faltan el correo o la contraseña de aplicación.")
    try:
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    except Exception as e:  # noqa: BLE001
        raise GmailError(f"No se pudo conectar a Gmail: {e}") from e

    try:
        conn.login(email_addr.strip(), app_password.strip().replace(" ", ""))
    except imaplib.IMAP4.error as e:
        raise GmailError(
            "Autenticación fallida. Verifica el correo y la **contraseña de "
            "aplicación** (no la normal), y que el acceso IMAP esté activado en "
            "Gmail → Configuración → Reenvío y correo POP/IMAP."
        ) from e

    estado, _ = conn.select(mailbox, readonly=True)
    if estado != "OK":
        # Fallback a INBOX si el buzón "All Mail" tiene otro nombre por idioma.
        estado, _ = conn.select("INBOX", readonly=True)
        if estado != "OK":
            conn.logout()
            raise GmailError(f"No se pudo abrir el buzón ({mailbox}).")
    return conn


def buscar_adjuntos(
    email_addr: str,
    app_password: str,
    *,
    remitente: str = "",
    texto: str = "",
    dias: int = 30,
    tipos: tuple[str, ...] = ("pdf", "json"),
    max_correos: int = 50,
    mailbox: str = '"[Gmail]/All Mail"',
) -> list[dict]:
    """
    Busca correos que cumplan el filtro y devuelve sus adjuntos (PDF/JSON).

    Retorna una lista de dicts:
        {filename, data (bytes), size, remitente, asunto, fecha}
    """
    max_correos = max(1, min(int(max_correos), MAX_CORREOS_HARD))
    tipos_norm = tuple(t.lower().lstrip(".") for t in tipos)

    conn = conectar(email_addr, app_password, mailbox)
    adjuntos: list[dict] = []
    try:
        query = _construir_query(remitente, texto, dias, tipos_norm)
        try:
            estado, datos = conn.search(None, "X-GM-RAW", f'"{query}"')
        except imaplib.IMAP4.error as e:
            raise GmailError(f"Búsqueda inválida en Gmail: {e}") from e

        if estado != "OK":
            raise GmailError("La búsqueda en Gmail no devolvió un resultado válido.")

        ids = datos[0].split()
        if not ids:
            return []

        # Más recientes primero, limitado a max_correos.
        ids = list(reversed(ids))[:max_correos]

        for uid in ids:
            estado, raw = conn.fetch(uid, "(RFC822)")
            if estado != "OK" or not raw or not raw[0]:
                continue
            mensaje = email.message_from_bytes(raw[0][1])
            remite = _decodificar(mensaje.get("From"))
            asunto = _decodificar(mensaje.get("Subject"))
            try:
                fecha = parsedate_to_datetime(mensaje.get("Date"))
                fecha_str = fecha.strftime("%Y-%m-%d %H:%M") if fecha else ""
            except Exception:  # noqa: BLE001
                fecha_str = ""

            for parte in mensaje.walk():
                if parte.get_content_maintype() == "multipart":
                    continue
                disp = (parte.get("Content-Disposition") or "").lower()
                nombre = _decodificar(parte.get_filename())
                if not nombre:
                    continue
                ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
                if ext not in tipos_norm and "attachment" not in disp:
                    continue
                if ext not in tipos_norm:
                    continue
                try:
                    contenido = parte.get_payload(decode=True)
                except Exception:  # noqa: BLE001
                    contenido = None
                if not contenido:
                    continue
                adjuntos.append(
                    {
                        "filename": nombre,
                        "data": contenido,
                        "size": len(contenido),
                        "remitente": remite,
                        "asunto": asunto,
                        "fecha": fecha_str,
                    }
                )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            conn.logout()
        except Exception:  # noqa: BLE001
            pass

    return adjuntos


def a_gmail_files(adjuntos: list[dict]) -> list[GmailFile]:
    """Convierte los dicts de `buscar_adjuntos` en objetos GmailFile."""
    return [
        GmailFile(
            a["filename"],
            a["data"],
            remitente=a.get("remitente", ""),
            asunto=a.get("asunto", ""),
        )
        for a in adjuntos
    ]
