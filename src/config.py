# src/config.py
"""Configuración centralizada del Agente Calendario con Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional
import json
import re


class Settings(BaseSettings):
    """Configuración centralizada del Agente Calendario."""

    # -- Telegram --
    telegram_bot_token: str
    admin_telegram_ids: list[int] = Field(default_factory=list)
    editor_telegram_ids: list[int] = Field(default_factory=list)

    # -- Horario Laboral --
    work_days_weekday_start: str = "15:00"
    work_days_weekday_end: str = "21:00"
    work_days_saturday_start: str = "08:00"
    work_days_saturday_end: str = "20:00"

    # -- Groq API --
    groq_api_key: str
    groq_model_primary: str = "llama-3.3-70b-versatile"
    groq_model_fallback: str = "llama-3.1-8b-instant"
    groq_max_tokens: int = 512
    groq_temperature: float = 0.1

    # -- Google Calendar --
    google_calendar_id: str
    google_service_account_path: str = "credentials/service_account.json"

    # -- Base de Datos --
    sqlite_db_path: str = "data/crm.db"
    fuzzy_match_threshold: int = 75

    # -- Sistema --
    timezone: str = "America/Argentina/Buenos_Aires"
    log_level: str = "DEBUG"
    log_file: str = "logs/agente.log"

    @field_validator("admin_telegram_ids", "editor_telegram_ids", mode="before")
    @classmethod
    def parse_id_list(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator(
        "work_days_weekday_start",
        "work_days_weekday_end",
        "work_days_saturday_start",
        "work_days_saturday_end",
        mode="after",
    )
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Valida que los horarios laborales tengan formato HH:MM válido."""
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError(
                f"Formato de hora inválido: '{v}'. Usar HH:MM (ej: '09:00')."
            )
        hours, minutes = int(v[:2]), int(v[3:])
        if hours > 23 or minutes > 59:
            raise ValueError(f"Hora fuera de rango: '{v}'. Debe ser 00:00-23:59.")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Obtiene la instancia singleton de Settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Resetea el singleton (útil para tests)."""
    global _settings
    _settings = None


def validate_settings() -> None:
    """Verifica que la configuración es válida al arrancar."""
    settings = get_settings()

    errors = []
    if not settings.telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN es requerido")
    if not settings.groq_api_key:
        errors.append("GROQ_API_KEY es requerido")
    if not settings.google_calendar_id:
        errors.append("GOOGLE_CALENDAR_ID es requerido")
    if not settings.admin_telegram_ids:
        errors.append("Al menos un ADMIN_TELEGRAM_IDS es requerido")

    if errors:
        raise SystemExit(
            "Errores de configuración:\n" + "\n".join(f"  - {e}" for e in errors)
        )
