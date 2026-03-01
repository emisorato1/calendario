"""Autenticación con Google Calendar via Service Account."""

from __future__ import annotations

from pathlib import Path

from google.oauth2.service_account import Credentials

from core.exceptions import CalendarAuthError
from core.logger import get_logger

log = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_credentials(service_account_path: str) -> Credentials:
    """Carga credenciales de Service Account desde un archivo JSON.

    Args:
        service_account_path: Ruta al archivo service_account.json.

    Returns:
        Credenciales de Google autenticadas con scope de Calendar.

    Raises:
        CalendarAuthError: Si el archivo no existe o tiene formato inválido.
    """
    path = Path(service_account_path)

    if not path.exists():
        log.error(
            "service_account_no_encontrado",
            path=str(path),
        )
        raise CalendarAuthError(f"Archivo de Service Account no encontrado: {path}")

    try:
        credentials = Credentials.from_service_account_file(
            str(path),
            scopes=SCOPES,
        )
    except (ValueError, KeyError) as exc:
        log.error(
            "service_account_formato_invalido",
            path=str(path),
            error=str(exc),
        )
        raise CalendarAuthError(f"Formato inválido en Service Account ({path}): {exc}") from exc

    log.info(
        "autenticacion_exitosa",
        service_account=credentials.service_account_email,
    )
    return credentials
