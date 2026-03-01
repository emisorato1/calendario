"""Tests para agents/calendar_sync/client.py."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytz
import pytest
from googleapiclient.errors import HttpError

from agents.calendar_sync.client import CalendarClient, _is_retryable_http_error
from config.constants import TIMEZONE
from core.exceptions import CalendarError, EventoNoEncontradoError

tz = pytz.timezone(TIMEZONE)


def _make_http_error(status: int) -> HttpError:
    """Crea un HttpError simulado con el status dado."""
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b"error")


@pytest.fixture
def mock_service():
    """Mock del servicio de Google Calendar."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_credentials():
    """Mock de credenciales de Google."""
    return MagicMock()


@pytest.fixture
def calendar_client(mock_credentials, mock_service):
    """CalendarClient con servicio mockeado."""
    with patch(
        "agents.calendar_sync.client.build",
        return_value=mock_service,
    ):
        client = CalendarClient(
            credentials=mock_credentials,
            calendar_id="test_calendar_id",
            timeout=5,
        )
    return client


class TestIsRetryableHttpError:
    """Tests para _is_retryable_http_error."""

    def test_429_es_retryable(self):
        assert _is_retryable_http_error(_make_http_error(429)) is True

    def test_500_es_retryable(self):
        assert _is_retryable_http_error(_make_http_error(500)) is True

    def test_503_es_retryable(self):
        assert _is_retryable_http_error(_make_http_error(503)) is True

    def test_404_no_es_retryable(self):
        assert _is_retryable_http_error(_make_http_error(404)) is False

    def test_400_no_es_retryable(self):
        assert _is_retryable_http_error(_make_http_error(400)) is False

    def test_excepcion_generica_no_es_retryable(self):
        assert _is_retryable_http_error(ValueError("test")) is False


class TestCalendarClientCrearEvento:
    """Tests para crear_evento."""

    async def test_crear_evento_exitoso(self, calendar_client, mock_service):
        """Crear evento retorna el evento con ID."""
        mock_request = MagicMock()
        mock_request.execute.return_value = {
            "id": "new_event_id",
            "htmlLink": "https://calendar.google.com/...",
            "summary": "Test evento",
        }
        mock_service.events.return_value.insert.return_value = mock_request

        result = await calendar_client.crear_evento({"summary": "Test evento"})

        assert result["id"] == "new_event_id"
        mock_service.events.return_value.insert.assert_called_once()


class TestCalendarClientActualizarEvento:
    """Tests para actualizar_evento."""

    async def test_actualizar_evento_exitoso(self, calendar_client, mock_service):
        """Actualizar evento retorna el evento modificado."""
        mock_request = MagicMock()
        mock_request.execute.return_value = {
            "id": "evt_1",
            "summary": "Modificado",
        }
        mock_service.events.return_value.patch.return_value = mock_request

        result = await calendar_client.actualizar_evento("evt_1", {"summary": "Modificado"})

        assert result["summary"] == "Modificado"

    async def test_actualizar_evento_404_lanza_error(self, calendar_client, mock_service):
        """Actualizar evento inexistente lanza EventoNoEncontradoError."""
        mock_request = MagicMock()
        mock_request.execute.side_effect = _make_http_error(404)
        mock_service.events.return_value.patch.return_value = mock_request

        with pytest.raises(EventoNoEncontradoError):
            await calendar_client.actualizar_evento("evt_inexistente", {})


class TestCalendarClientEliminarEvento:
    """Tests para eliminar_evento."""

    async def test_eliminar_evento_exitoso(self, calendar_client, mock_service):
        """Eliminar evento exitoso retorna None."""
        mock_request = MagicMock()
        mock_request.execute.return_value = None
        mock_service.events.return_value.delete.return_value = mock_request

        await calendar_client.eliminar_evento("evt_1")

        mock_service.events.return_value.delete.assert_called_once()

    async def test_eliminar_evento_404_lanza_error(self, calendar_client, mock_service):
        """Eliminar evento inexistente lanza EventoNoEncontradoError."""
        mock_request = MagicMock()
        mock_request.execute.side_effect = _make_http_error(404)
        mock_service.events.return_value.delete.return_value = mock_request

        with pytest.raises(EventoNoEncontradoError, match="no encontrado"):
            await calendar_client.eliminar_evento("evt_inexistente")


class TestCalendarClientListarEventos:
    """Tests para listar_eventos y listar_proximos_eventos."""

    async def test_listar_eventos_retorna_items(self, calendar_client, mock_service):
        """Listar eventos retorna la lista de items."""
        mock_request = MagicMock()
        mock_request.execute.return_value = {
            "items": [
                {"id": "evt_1", "summary": "Evento 1"},
                {"id": "evt_2", "summary": "Evento 2"},
            ]
        }
        mock_service.events.return_value.list.return_value = mock_request

        now = datetime.now(tz)
        result = await calendar_client.listar_eventos(
            time_min=now,
            time_max=now + timedelta(days=1),
        )

        assert len(result) == 2
        assert result[0]["id"] == "evt_1"

    async def test_listar_eventos_sin_items_retorna_lista_vacia(
        self, calendar_client, mock_service
    ):
        """Si no hay eventos, retorna lista vacía."""
        mock_request = MagicMock()
        mock_request.execute.return_value = {"items": []}
        mock_service.events.return_value.list.return_value = mock_request

        now = datetime.now(tz)
        result = await calendar_client.listar_eventos(
            time_min=now,
            time_max=now + timedelta(days=1),
        )

        assert result == []

    async def test_listar_proximos_eventos_retorna_ordenados(self, calendar_client, mock_service):
        """listar_proximos_eventos retorna eventos ordenados por fecha."""
        mock_request = MagicMock()
        mock_request.execute.return_value = {
            "items": [
                {
                    "id": "evt_1",
                    "summary": "Primero",
                    "start": {"dateTime": "2026-03-02T09:00:00-03:00"},
                },
                {
                    "id": "evt_2",
                    "summary": "Segundo",
                    "start": {"dateTime": "2026-03-03T10:00:00-03:00"},
                },
            ]
        }
        mock_service.events.return_value.list.return_value = mock_request

        result = await calendar_client.listar_proximos_eventos(n=5)

        assert len(result) == 2
        assert result[0]["id"] == "evt_1"

    async def test_listar_eventos_por_fecha(self, calendar_client, mock_service):
        """listar_eventos_por_fecha retorna eventos del día."""
        mock_request = MagicMock()
        mock_request.execute.return_value = {
            "items": [{"id": "evt_dia", "summary": "Evento del día"}]
        }
        mock_service.events.return_value.list.return_value = mock_request

        result = await calendar_client.listar_eventos_por_fecha(date(2026, 3, 3))

        assert len(result) == 1


class TestCalendarClientBuscarPorCliente:
    """Tests para buscar_eventos_por_cliente."""

    async def test_buscar_encuentra_eventos_del_cliente(self, calendar_client, mock_service):
        """Buscar por nombre de cliente retorna eventos coincidentes."""
        mock_request = MagicMock()
        mock_request.execute.return_value = {
            "items": [
                {"id": "evt_1", "summary": "García, Juan - 260-111"},
            ]
        }
        mock_service.events.return_value.list.return_value = mock_request

        result = await calendar_client.buscar_eventos_por_cliente("García")

        assert len(result) == 1
        # Verificar que se pasó el query
        call_args = mock_service.events.return_value.list.call_args
        assert call_args.kwargs["q"] == "García"

    async def test_buscar_sin_resultados(self, calendar_client, mock_service):
        """Buscar cliente inexistente retorna lista vacía."""
        mock_request = MagicMock()
        mock_request.execute.return_value = {"items": []}
        mock_service.events.return_value.list.return_value = mock_request

        result = await calendar_client.buscar_eventos_por_cliente("NoExiste")

        assert result == []


class TestCalendarClientReintentos:
    """Tests para el mecanismo de reintentos."""

    async def test_reintento_en_429(self, calendar_client, mock_service):
        """Error 429 trigger reintento y eventualmente tiene éxito."""
        mock_request = MagicMock()
        # Primer intento falla con 429, segundo éxito
        mock_request.execute.side_effect = [
            _make_http_error(429),
            {"id": "evt_retry", "summary": "Retry success"},
        ]
        mock_service.events.return_value.insert.return_value = mock_request

        result = await calendar_client.crear_evento({"summary": "Test"})

        assert result["id"] == "evt_retry"
        assert mock_request.execute.call_count == 2

    async def test_reintento_en_500(self, calendar_client, mock_service):
        """Error 500 trigger reintento."""
        mock_request = MagicMock()
        mock_request.execute.side_effect = [
            _make_http_error(500),
            {"items": []},
        ]
        mock_service.events.return_value.list.return_value = mock_request

        now = datetime.now(tz)
        result = await calendar_client.listar_eventos(
            time_min=now,
            time_max=now + timedelta(days=1),
        )

        assert result == []
        assert mock_request.execute.call_count == 2

    async def test_no_reintento_en_400(self, calendar_client, mock_service):
        """Error 400 no genera reintento."""
        mock_request = MagicMock()
        mock_request.execute.side_effect = _make_http_error(400)
        mock_service.events.return_value.insert.return_value = mock_request

        with pytest.raises(HttpError):
            await calendar_client.crear_evento({"summary": "Test"})

        assert mock_request.execute.call_count == 1

    async def test_agota_reintentos_lanza_excepcion(self, calendar_client, mock_service):
        """Si se agotan los reintentos, lanza la excepción original."""
        mock_request = MagicMock()
        mock_request.execute.side_effect = _make_http_error(429)
        mock_service.events.return_value.insert.return_value = mock_request

        with pytest.raises(HttpError):
            await calendar_client.crear_evento({"summary": "Test"})

        assert mock_request.execute.call_count == 3  # 3 intentos


class TestCalendarClientTimeout:
    """Tests para el manejo de timeout."""

    async def test_timeout_lanza_calendar_error(self, calendar_client, mock_service):
        """Timeout en la operación lanza CalendarError."""
        mock_request = MagicMock()

        async def slow_execute():
            await asyncio.sleep(10)
            return {}

        # Simular una operación lenta
        mock_request.execute.side_effect = lambda: asyncio.sleep(10)
        mock_service.events.return_value.insert.return_value = mock_request

        # El client tiene timeout=5, pero necesitamos simular el timeout
        # de asyncio.wait_for
        with patch("agents.calendar_sync.client.asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            with pytest.raises(CalendarError, match="Timeout"):
                await calendar_client.crear_evento({"summary": "Test"})
