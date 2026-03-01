"""Configuración central del proyecto via pydantic-settings."""
from __future__ import annotations

from datetime import time
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del Agente Calendario. Carga desde .env o argumentos directos."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Requeridos ────────────────────────────────────────────────────────────
    telegram_bot_token: str
    admin_telegram_ids: list[int]
    groq_api_key: str
    google_calendar_id: str
    google_service_account_path: str

    # ── Opcionales con defaults ───────────────────────────────────────────────
    editor_telegram_ids: list[int] = []
    sqlite_db_path: str = "data/agenda.db"
    log_level: str = "INFO"
    log_file: str = "logs/agente.log"
    groq_model_primary: str = "llama-3.3-70b-versatile"
    groq_model_fallback: str = "llama-3.1-8b-instant"
    groq_max_tokens: int = 512
    groq_temperature: float = 0.1
    conflict_buffer_minutes: int = 30
    max_events_list: int = 10
    fuzzy_match_threshold: int = 75
    timezone: str = "America/Argentina/Buenos_Aires"

    # Horario laboral
    work_days_weekday_start: time = time(15, 0)
    work_days_weekday_end: time = time(21, 0)
    work_days_saturday_start: time = time(8, 0)
    work_days_saturday_end: time = time(20, 0)

    # ── Validators de campo ───────────────────────────────────────────────────

    @field_validator("admin_telegram_ids", "editor_telegram_ids", mode="before")
    @classmethod
    def parse_telegram_ids(cls, v: Any) -> list[int]:
        """Parsea la lista desde string CSV ('123,456') o desde lista directa."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        return v

    @field_validator(
        "work_days_weekday_start",
        "work_days_weekday_end",
        "work_days_saturday_start",
        "work_days_saturday_end",
        mode="before",
    )
    @classmethod
    def parse_time_field(cls, v: Any) -> time:
        """Parsea el tiempo desde string 'HH:MM' o desde objeto time directamente."""
        if isinstance(v, str):
            parts = v.strip().split(":")
            return time(int(parts[0]), int(parts[1]))
        return v

    # ── Validators de modelo ──────────────────────────────────────────────────

    @model_validator(mode="after")
    def validate_telegram_ids(self) -> "Settings":
        """Valida que Admin tenga 1-2 IDs y que no haya duplicados entre roles."""
        if len(self.admin_telegram_ids) < 1:
            raise ValueError("ADMIN_TELEGRAM_IDS debe tener al menos 1 ID")
        if len(self.admin_telegram_ids) > 2:
            raise ValueError(
                f"ADMIN_TELEGRAM_IDS no puede tener más de 2 IDs "
                f"(recibidos: {len(self.admin_telegram_ids)})"
            )
        duplicados = set(self.admin_telegram_ids) & set(self.editor_telegram_ids)
        if duplicados:
            raise ValueError(
                f"IDs duplicados entre Admin y Editor: {sorted(duplicados)}"
            )
        return self

    # ── Métodos de conveniencia ───────────────────────────────────────────────

    def is_admin(self, user_id: int) -> bool:
        """Retorna True si el user_id es un Admin."""
        return user_id in self.admin_telegram_ids

    def is_editor(self, user_id: int) -> bool:
        """Retorna True si el user_id es un Editor."""
        return user_id in self.editor_telegram_ids

    def is_authorized(self, user_id: int) -> bool:
        """Retorna True si el user_id es Admin o Editor."""
        return self.is_admin(user_id) or self.is_editor(user_id)
