"""Fixtures globales compartidas por todos los tests."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from agents.db_manager.connection import get_db_connection
from agents.db_manager.migrations import run_migrations
from agents.db_manager.models import Cliente, Servicio
from config.settings import Settings


@pytest_asyncio.fixture
async def db_connection():
    """SQLite :memory: con migraciones aplicadas. Aislado por test."""
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        yield conn


@pytest.fixture
def mock_settings() -> Settings:
    """Settings válido con dos admins y un editor. Sin leer .env."""
    return Settings(
        telegram_bot_token="test_token_123",
        admin_telegram_ids=[123456789, 987654321],
        editor_telegram_ids=[111222333],
        groq_api_key="test_groq_key",
        google_calendar_id="test@group.calendar.google.com",
        google_service_account_path="/fake/path/service_account.json",
        sqlite_db_path=":memory:",
        _env_file=None,
    )


@pytest.fixture
def mock_settings_admin_only() -> Settings:
    """Settings con solo un admin y sin editors."""
    return Settings(
        telegram_bot_token="test_token_123",
        admin_telegram_ids=[123456789],
        editor_telegram_ids=[],
        groq_api_key="test_groq_key",
        google_calendar_id="test@group.calendar.google.com",
        google_service_account_path="/fake/path/service_account.json",
        sqlite_db_path=":memory:",
        _env_file=None,
    )


# ── Fixtures de datos ─────────────────────────────────────────────────────────


@pytest.fixture
def cliente_garcia() -> Cliente:
    """Cliente de ejemplo para tests."""
    return Cliente(
        id_cliente=1,
        nombre_completo="García, Juan",
        alias="Juan",
        telefono="2604567890",
        direccion="Av. San Martín 456",
        ciudad="San Rafael",
        notas_equipamiento=None,
        fecha_alta=datetime(2025, 1, 15),
    )


@pytest.fixture
def evento_proximo() -> dict:
    """Evento de Google Calendar de ejemplo."""
    return {
        "id": "evt_test_1",
        "summary": "García, Juan - 2604567890",
        "start": {"dateTime": "2026-03-02T09:00:00-03:00"},
        "end": {"dateTime": "2026-03-02T10:00:00-03:00"},
        "location": "Av. San Martín 456",
        "colorId": "5",
        "description": "Tipo de Servicio: revision\n---\nNotas: Creado vía IA",
    }


@pytest.fixture
def evento_proximo_2() -> dict:
    """Segundo evento de ejemplo."""
    return {
        "id": "evt_test_2",
        "summary": "López, Pedro - 2601234567",
        "start": {"dateTime": "2026-03-02T15:00:00-03:00"},
        "end": {"dateTime": "2026-03-02T18:00:00-03:00"},
        "location": "Calle Belgrano 789",
        "colorId": "9",
        "description": "Tipo de Servicio: instalacion\n---\nNotas: Creado vía IA",
    }


# ── Mock de Calendar Client ──────────────────────────────────────────────────


@pytest.fixture
def mock_calendar_client() -> AsyncMock:
    """Mock del CalendarClient con todos los métodos async."""
    client = AsyncMock()
    client.crear_evento.return_value = {
        "id": "fake_event_id_123",
        "htmlLink": "https://calendar.google.com/fake",
        "summary": "García - 2604567890",
    }
    client.listar_proximos_eventos.return_value = [
        {
            "id": "evt_1",
            "summary": "García, Juan - 2604567890",
            "start": {"dateTime": "2026-03-02T09:00:00-03:00"},
            "end": {"dateTime": "2026-03-02T10:00:00-03:00"},
            "colorId": "5",
            "description": "Tipo de Servicio: revision",
        },
    ]
    client.listar_eventos.return_value = [
        {
            "id": "evt_1",
            "summary": "García, Juan - 2604567890",
            "start": {"dateTime": "2026-03-02T09:00:00-03:00"},
            "end": {"dateTime": "2026-03-02T10:00:00-03:00"},
            "colorId": "5",
            "description": "Tipo de Servicio: revision",
        },
    ]
    client.listar_eventos_por_fecha.return_value = []
    client.buscar_eventos_por_cliente.return_value = []
    client.eliminar_evento.return_value = None
    client.actualizar_evento.return_value = {
        "id": "evt_1",
        "htmlLink": "https://calendar.google.com/fake_updated",
    }
    return client


# ── Mock de Groq Client ──────────────────────────────────────────────────────


@pytest.fixture
def mock_groq_client() -> AsyncMock:
    """Mock del GroqClient."""
    client = AsyncMock()
    client.call.return_value = json.dumps(
        {
            "intencion": "agendar",
            "nombre_cliente": "García",
            "tipo_servicio": "instalacion",
            "fecha": "2026-03-03",
            "hora": "10:00",
            "duracion_estimada_horas": 3.0,
            "direccion": None,
            "telefono": None,
            "urgente": False,
        }
    )
    return client


# ── Mock de DB Repository ────────────────────────────────────────────────────


@pytest.fixture
def mock_repository(cliente_garcia) -> AsyncMock:
    """Mock del DBRepository."""
    repo = AsyncMock()
    repo.buscar_cliente_fuzzy.return_value = cliente_garcia
    repo.crear_cliente.return_value = cliente_garcia
    repo.registrar_servicio.return_value = 1
    repo.listar_clientes.return_value = [cliente_garcia]
    repo.buscar_servicio_por_event_id.return_value = Servicio(
        id_servicio=1,
        id_cliente=1,
        calendar_event_id="evt_1",
        tipo_trabajo="revision",
        estado="pendiente",
    )
    repo.actualizar_estado_servicio.return_value = None
    repo._conn = AsyncMock()
    repo._conn.execute.return_value = MagicMock()
    return repo


# ── Mock de Telegram Update/Context ──────────────────────────────────────────


@pytest.fixture
def mock_telegram_update():
    """Factory para crear Update mocks de Telegram."""

    def _make(
        user_id: int = 123456789,
        first_name: str = "TestUser",
        text: str = "Hello",
        chat_id: int = 123456789,
        username: str = "testuser",
    ):
        update = MagicMock()
        update.effective_user.id = user_id
        update.effective_user.first_name = first_name
        update.effective_user.username = username
        update.effective_chat.id = chat_id
        update.effective_chat.send_message = AsyncMock()
        update.message.text = text
        update.message.message_id = 1
        update.message.reply_text = AsyncMock()
        update.message.from_user.id = user_id
        update.message.from_user.username = username
        update.callback_query = None
        return update

    return _make


@pytest.fixture
def mock_telegram_callback_update():
    """Factory para crear Update mocks con callback_query."""

    def _make(
        user_id: int = 123456789,
        callback_data: str = "confirm",
        chat_id: int = 123456789,
    ):
        update = MagicMock()
        update.effective_user.id = user_id
        update.effective_chat.id = chat_id
        update.effective_chat.send_message = AsyncMock()
        update.callback_query.data = callback_data
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.message = None
        return update

    return _make


@pytest.fixture
def mock_context(mock_settings, mock_calendar_client, mock_groq_client, mock_repository):
    """Mock del ContextTypes.DEFAULT_TYPE con bot_data y user_data."""
    from core.orchestrator import Orchestrator

    orchestrator = Orchestrator(
        settings=mock_settings,
        groq_client=mock_groq_client,
        repository=mock_repository,
        calendar_client=mock_calendar_client,
    )

    context = MagicMock()
    context.bot_data = {
        "settings": mock_settings,
        "orchestrator": orchestrator,
        "calendar_client": mock_calendar_client,
        "groq_client": mock_groq_client,
        "repository": mock_repository,
    }
    context.user_data = {}
    context.bot.send_message = AsyncMock()
    return context
