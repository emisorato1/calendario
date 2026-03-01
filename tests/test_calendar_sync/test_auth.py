"""Tests para agents/calendar_sync/auth.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.calendar_sync.auth import SCOPES, get_credentials
from core.exceptions import CalendarAuthError


class TestGetCredentials:
    """Tests para la función get_credentials."""

    def test_archivo_no_existe_lanza_calendar_auth_error(self):
        """Si el archivo no existe, lanza CalendarAuthError."""
        with pytest.raises(CalendarAuthError, match="no encontrado"):
            get_credentials("/ruta/inexistente/service_account.json")

    def test_archivo_formato_invalido_lanza_calendar_auth_error(self, tmp_path):
        """Si el JSON tiene formato inválido, lanza CalendarAuthError."""
        archivo = tmp_path / "service_account.json"
        archivo.write_text("{}")  # JSON vacío, sin los campos requeridos

        with pytest.raises(CalendarAuthError, match="Formato inválido"):
            get_credentials(str(archivo))

    def test_archivo_valido_retorna_credentials(self, tmp_path):
        """Con un archivo SA válido, retorna Credentials con scope correcto."""
        archivo = tmp_path / "service_account.json"
        archivo.write_text('{"type": "service_account"}')

        mock_creds = MagicMock()
        mock_creds.service_account_email = "test@test-project.iam.gserviceaccount.com"
        mock_creds.scopes = SCOPES

        with patch(
            "agents.calendar_sync.auth.Credentials.from_service_account_file",
            return_value=mock_creds,
        ) as mock_from_file:
            creds = get_credentials(str(archivo))

        assert creds is not None
        assert creds.service_account_email == "test@test-project.iam.gserviceaccount.com"
        mock_from_file.assert_called_once_with(str(archivo), scopes=SCOPES)

    def test_logging_exitoso(self, tmp_path):
        """Verifica que get_credentials no lanza error en happy path."""
        archivo = tmp_path / "service_account.json"
        archivo.write_text('{"type": "service_account"}')

        mock_creds = MagicMock()
        mock_creds.service_account_email = "test@test-project.iam.gserviceaccount.com"

        with patch(
            "agents.calendar_sync.auth.Credentials.from_service_account_file",
            return_value=mock_creds,
        ):
            creds = get_credentials(str(archivo))

        assert creds is not None

    def test_scopes_correctos(self):
        """El scope debe ser el de Google Calendar."""
        assert SCOPES == ["https://www.googleapis.com/auth/calendar"]

    def test_value_error_en_from_file_lanza_calendar_auth_error(self, tmp_path):
        """Si from_service_account_file lanza ValueError, se transforma a CalendarAuthError."""
        archivo = tmp_path / "service_account.json"
        archivo.write_text('{"type": "service_account"}')

        with patch(
            "agents.calendar_sync.auth.Credentials.from_service_account_file",
            side_effect=ValueError("Bad key data"),
        ):
            with pytest.raises(CalendarAuthError, match="Formato inválido"):
                get_credentials(str(archivo))

    def test_key_error_en_from_file_lanza_calendar_auth_error(self, tmp_path):
        """Si from_service_account_file lanza KeyError, se transforma a CalendarAuthError."""
        archivo = tmp_path / "service_account.json"
        archivo.write_text('{"type": "service_account"}')

        with patch(
            "agents.calendar_sync.auth.Credentials.from_service_account_file",
            side_effect=KeyError("missing_field"),
        ):
            with pytest.raises(CalendarAuthError, match="Formato inválido"):
                get_credentials(str(archivo))
