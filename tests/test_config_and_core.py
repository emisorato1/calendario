"""Tests de configuración, logger y excepciones."""
from __future__ import annotations

from datetime import time

import pytest
from pydantic import ValidationError

from config.settings import Settings
from core.exceptions import (
    AccesoNoAutorizadoError,
    AgenteCalendarioError,
    CalendarAuthError,
    CalendarError,
    ClienteNoEncontradoError,
    ConflictoHorarioError,
    DBError,
    DBMigrationError,
    EventoNoEncontradoError,
    GroqError,
    GroqParsingError,
    GroqTimeoutError,
    TelegramError,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_settings(**kwargs) -> Settings:
    """Crea un Settings mínimo válido, con posibilidad de override."""
    defaults: dict = dict(
        telegram_bot_token="tok",
        admin_telegram_ids=[123],
        groq_api_key="key",
        google_calendar_id="cal@id",
        google_service_account_path="/path",
        _env_file=None,
    )
    defaults.update(kwargs)
    return Settings(**defaults)


# ── Settings: campos y defaults ────────────────────────────────────────────────

class TestSettingsCarga:
    def test_token_y_ids_cargados(self, mock_settings):
        assert mock_settings.telegram_bot_token == "test_token_123"
        assert mock_settings.admin_telegram_ids == [123456789, 987654321]
        assert mock_settings.editor_telegram_ids == [111222333]

    def test_defaults_groq(self, mock_settings):
        assert mock_settings.groq_model_primary == "llama-3.3-70b-versatile"
        assert mock_settings.groq_model_fallback == "llama-3.1-8b-instant"
        assert mock_settings.groq_max_tokens == 512

    def test_defaults_calendario(self, mock_settings):
        assert mock_settings.conflict_buffer_minutes == 30
        assert mock_settings.max_events_list == 10

    def test_defaults_horario_semana(self, mock_settings):
        assert mock_settings.work_days_weekday_start == time(15, 0)
        assert mock_settings.work_days_weekday_end == time(21, 0)

    def test_defaults_horario_sabado(self, mock_settings):
        assert mock_settings.work_days_saturday_start == time(8, 0)
        assert mock_settings.work_days_saturday_end == time(20, 0)

    def test_ids_desde_csv_string(self):
        """Simula cómo llegan los IDs desde .env: string CSV."""
        s = _make_settings(
            admin_telegram_ids="100,200",
            editor_telegram_ids="300",
        )
        assert s.admin_telegram_ids == [100, 200]
        assert s.editor_telegram_ids == [300]

    def test_horario_desde_string_hhmm(self):
        """Simula cómo llegan los times desde .env: string HH:MM."""
        s = _make_settings(
            work_days_weekday_start="16:30",
            work_days_saturday_end="19:00",
        )
        assert s.work_days_weekday_start == time(16, 30)
        assert s.work_days_saturday_end == time(19, 0)


# ── Settings: validaciones de negocio ─────────────────────────────────────────

class TestSettingsValidaciones:
    def test_falta_token_lanza_error(self):
        with pytest.raises(ValidationError):
            Settings(
                admin_telegram_ids=[1],
                groq_api_key="k",
                google_calendar_id="cal",
                google_service_account_path="/p",
                _env_file=None,
            )

    def test_falta_groq_key_lanza_error(self):
        with pytest.raises(ValidationError):
            Settings(
                telegram_bot_token="tok",
                admin_telegram_ids=[1],
                google_calendar_id="cal",
                google_service_account_path="/p",
                _env_file=None,
            )

    def test_admin_ids_mas_de_2_lanza_error(self):
        with pytest.raises(ValidationError, match="más de 2"):
            _make_settings(admin_telegram_ids=[1, 2, 3])

    def test_admin_ids_vacio_lanza_error(self):
        with pytest.raises(ValidationError):
            _make_settings(admin_telegram_ids=[])

    def test_ids_duplicados_admin_editor_lanza_error(self):
        with pytest.raises(ValidationError, match="duplicados"):
            _make_settings(admin_telegram_ids=[100], editor_telegram_ids=[100])

    def test_editor_ids_puede_ser_lista_vacia(self):
        s = _make_settings(editor_telegram_ids=[])
        assert s.editor_telegram_ids == []

    def test_editor_ids_puede_tener_multiples_ids(self):
        s = _make_settings(editor_telegram_ids=[10, 20, 30])
        assert len(s.editor_telegram_ids) == 3


# ── Settings: métodos de rol ──────────────────────────────────────────────────

class TestSettingsRoles:
    def test_is_admin_true_para_admin(self, mock_settings):
        assert mock_settings.is_admin(123456789) is True

    def test_is_admin_false_para_editor(self, mock_settings):
        assert mock_settings.is_admin(111222333) is False

    def test_is_admin_false_para_desconocido(self, mock_settings):
        assert mock_settings.is_admin(9999) is False

    def test_is_editor_true_para_editor(self, mock_settings):
        assert mock_settings.is_editor(111222333) is True

    def test_is_editor_false_para_admin(self, mock_settings):
        assert mock_settings.is_editor(123456789) is False

    def test_is_authorized_true_para_admin(self, mock_settings):
        assert mock_settings.is_authorized(123456789) is True

    def test_is_authorized_true_para_editor(self, mock_settings):
        assert mock_settings.is_authorized(111222333) is True

    def test_is_authorized_false_para_desconocido(self, mock_settings):
        assert mock_settings.is_authorized(9999) is False


# ── Excepciones ───────────────────────────────────────────────────────────────

class TestExcepciones:
    def test_jerarquia_db(self):
        assert issubclass(DBError, AgenteCalendarioError)
        assert issubclass(ClienteNoEncontradoError, DBError)
        assert issubclass(DBMigrationError, DBError)

    def test_jerarquia_groq(self):
        assert issubclass(GroqError, AgenteCalendarioError)
        assert issubclass(GroqParsingError, GroqError)
        assert issubclass(GroqTimeoutError, GroqError)

    def test_jerarquia_calendar(self):
        assert issubclass(CalendarError, AgenteCalendarioError)
        assert issubclass(EventoNoEncontradoError, CalendarError)
        assert issubclass(ConflictoHorarioError, CalendarError)
        assert issubclass(CalendarAuthError, CalendarError)

    def test_jerarquia_telegram(self):
        assert issubclass(TelegramError, AgenteCalendarioError)
        assert issubclass(AccesoNoAutorizadoError, TelegramError)

    def test_se_puede_lanzar_y_capturar_base(self):
        with pytest.raises(AgenteCalendarioError):
            raise ClienteNoEncontradoError("no encontrado")

    def test_excepcion_tiene_mensaje(self):
        err = ClienteNoEncontradoError("García no existe")
        assert "García no existe" in str(err)


# ── Logger ────────────────────────────────────────────────────────────────────

class TestLogger:
    def test_get_logger_retorna_objeto(self):
        from core.logger import get_logger
        logger = get_logger("test_module")
        assert logger is not None

    def test_configure_logging_no_lanza_error(self, tmp_path):
        from core.logger import configure_logging
        log_file = str(tmp_path / "test.log")
        configure_logging(log_level="DEBUG", log_file=log_file)

    def test_configure_logging_crea_carpeta(self, tmp_path):
        from core.logger import configure_logging
        log_file = str(tmp_path / "subdir" / "nested" / "app.log")
        configure_logging(log_level="INFO", log_file=log_file)
        # Si no lanzó error, la carpeta fue creada exitosamente
