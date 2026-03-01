"""Tests para agents/calendar_sync/conflict_checker.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytz
import pytest

from agents.calendar_sync.conflict_checker import (
    check_conflicts,
    suggest_alternatives,
    _next_work_day,
    _get_day_schedule,
)
from config.constants import TIMEZONE, WORK_DAYS

tz = pytz.timezone(TIMEZONE)


@pytest.fixture
def mock_calendar_client():
    """Mock de CalendarClient con listar_eventos."""
    client = AsyncMock()
    client.listar_eventos.return_value = []
    return client


@pytest.fixture
def evento_solapado():
    """Evento que se solapa con el rango 10:00-13:00 del 3/3/2026."""
    return {
        "id": "evt_overlap",
        "summary": "Otro evento",
        "start": {"dateTime": "2026-03-03T11:00:00-03:00"},
        "end": {"dateTime": "2026-03-03T12:00:00-03:00"},
    }


@pytest.fixture
def evento_no_solapado():
    """Evento fuera del rango 10:00-13:00 del 3/3/2026."""
    return {
        "id": "evt_no_overlap",
        "summary": "Evento diferente",
        "start": {"dateTime": "2026-03-03T08:00:00-03:00"},
        "end": {"dateTime": "2026-03-03T09:00:00-03:00"},
    }


class TestCheckConflicts:
    """Tests para check_conflicts."""

    async def test_sin_eventos_retorna_lista_vacia(self, mock_calendar_client):
        """Sin eventos en el rango, retorna lista vacía."""
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        end = tz.localize(datetime(2026, 3, 3, 13, 0))

        result = await check_conflicts(
            mock_calendar_client,
            "test_calendar_id",
            start,
            end,
        )

        assert result == []
        mock_calendar_client.listar_eventos.assert_called_once()

    async def test_evento_solapado_retorna_ese_evento(self, mock_calendar_client, evento_solapado):
        """Un evento solapado debe ser retornado."""
        mock_calendar_client.listar_eventos.return_value = [evento_solapado]
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        end = tz.localize(datetime(2026, 3, 3, 13, 0))

        result = await check_conflicts(
            mock_calendar_client,
            "test_calendar_id",
            start,
            end,
        )

        assert len(result) == 1
        assert result[0]["id"] == "evt_overlap"

    async def test_evento_no_solapado_no_retorna(self, mock_calendar_client, evento_no_solapado):
        """Un evento fuera del rango no debe ser retornado."""
        mock_calendar_client.listar_eventos.return_value = [evento_no_solapado]
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        end = tz.localize(datetime(2026, 3, 3, 13, 0))

        result = await check_conflicts(
            mock_calendar_client,
            "test_calendar_id",
            start,
            end,
        )

        assert result == []

    async def test_buffer_extiende_rango_de_busqueda(self, mock_calendar_client):
        """El buffer debe extender el rango de búsqueda."""
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        end = tz.localize(datetime(2026, 3, 3, 13, 0))

        await check_conflicts(
            mock_calendar_client,
            "test_calendar_id",
            start,
            end,
            buffer_minutes=30,
        )

        call_args = mock_calendar_client.listar_eventos.call_args
        time_min = call_args.kwargs["time_min"]
        time_max = call_args.kwargs["time_max"]
        # time_min debe ser start - 30min
        assert time_min == start - timedelta(minutes=30)
        # time_max debe ser end + 30min
        assert time_max == end + timedelta(minutes=30)

    async def test_multiples_eventos_solapados(self, mock_calendar_client, evento_solapado):
        """Múltiples eventos solapados deben ser retornados."""
        evento2 = {
            "id": "evt_overlap_2",
            "summary": "Otro solapado",
            "start": {"dateTime": "2026-03-03T12:00:00-03:00"},
            "end": {"dateTime": "2026-03-03T14:00:00-03:00"},
        }
        mock_calendar_client.listar_eventos.return_value = [evento_solapado, evento2]
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        end = tz.localize(datetime(2026, 3, 3, 13, 0))

        result = await check_conflicts(
            mock_calendar_client,
            "test_calendar_id",
            start,
            end,
        )

        assert len(result) == 2

    async def test_evento_sin_datetime_ignorado(self, mock_calendar_client):
        """Eventos sin dateTime (ej: all-day) son ignorados."""
        evento_all_day = {
            "id": "evt_all_day",
            "summary": "Evento todo el día",
            "start": {"date": "2026-03-03"},
            "end": {"date": "2026-03-04"},
        }
        mock_calendar_client.listar_eventos.return_value = [evento_all_day]
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        end = tz.localize(datetime(2026, 3, 3, 13, 0))

        result = await check_conflicts(
            mock_calendar_client,
            "test_calendar_id",
            start,
            end,
        )

        assert result == []


class TestSuggestAlternatives:
    """Tests para suggest_alternatives."""

    def test_retorna_exactamente_3_opciones(self):
        """Debe retornar exactamente 3 alternativas."""
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        result = suggest_alternatives(start, duration_hours=2.0, n=3)

        assert len(result) == 3

    def test_primera_alternativa_mismo_dia_mas_2h(self):
        """La primera alternativa es el mismo día +2h."""
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        result = suggest_alternatives(start, duration_hours=2.0)

        alt1 = result[0]
        expected_start = start + timedelta(hours=2)
        assert alt1["start"] == expected_start
        assert alt1["end"] == expected_start + timedelta(hours=2)

    def test_segunda_alternativa_siguiente_dia_habil(self):
        """La segunda alternativa es el siguiente día hábil, mismo horario."""
        # Martes 3/3/2026
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        result = suggest_alternatives(start, duration_hours=2.0)

        alt2 = result[1]
        # Siguiente día hábil = Miércoles 4/3/2026
        assert alt2["start"].date() == datetime(2026, 3, 4).date()
        assert alt2["start"].hour == 10

    def test_tercera_alternativa_siguiente_dia_habil_mas_2h(self):
        """La tercera alternativa es el siguiente día hábil +2h."""
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        result = suggest_alternatives(start, duration_hours=2.0)

        alt3 = result[2]
        assert alt3["start"].date() == datetime(2026, 3, 4).date()
        assert alt3["start"].hour == 12

    def test_sabado_siguiente_dia_habil_es_lunes(self):
        """Si el día es sábado, el siguiente día hábil es lunes."""
        # Sábado 7/3/2026
        start = tz.localize(datetime(2026, 3, 7, 10, 0))
        result = suggest_alternatives(start, duration_hours=1.0)

        alt2 = result[1]
        # Siguiente día hábil = Lunes 9/3/2026
        assert alt2["start"].weekday() == 0  # Lunes

    def test_duracion_aplicada_correctamente(self):
        """La duración se aplica a cada alternativa."""
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        result = suggest_alternatives(start, duration_hours=3.0)

        for alt in result:
            diff = alt["end"] - alt["start"]
            assert diff == timedelta(hours=3)

    def test_n_menor_a_3(self):
        """Si n < 3, retorna solo n alternativas."""
        start = tz.localize(datetime(2026, 3, 3, 10, 0))
        result = suggest_alternatives(start, duration_hours=1.0, n=1)

        assert len(result) == 1


class TestNextWorkDay:
    """Tests para _next_work_day."""

    def test_viernes_retorna_sabado(self):
        """El siguiente día hábil del viernes es sábado."""
        # Viernes 6/3/2026
        dt = tz.localize(datetime(2026, 3, 6, 10, 0))
        result = _next_work_day(dt)
        assert result.weekday() == 5  # Sábado

    def test_sabado_retorna_lunes(self):
        """El siguiente día hábil del sábado es lunes."""
        # Sábado 7/3/2026
        dt = tz.localize(datetime(2026, 3, 7, 10, 0))
        result = _next_work_day(dt)
        assert result.weekday() == 0  # Lunes

    def test_lunes_retorna_martes(self):
        """El siguiente día hábil del lunes es martes."""
        # Lunes 2/3/2026
        dt = tz.localize(datetime(2026, 3, 2, 10, 0))
        result = _next_work_day(dt)
        assert result.weekday() == 1  # Martes


class TestGetDaySchedule:
    """Tests para _get_day_schedule."""

    def test_lunes_retorna_horario_semana(self):
        """Lunes debe retornar el horario de día de semana."""
        dt = tz.localize(datetime(2026, 3, 2, 10, 0))  # Lunes
        schedule = _get_day_schedule(dt)
        assert schedule is not None
        assert schedule["start"] == "15:00"

    def test_sabado_retorna_horario_sabado(self):
        """Sábado debe retornar el horario de sábado."""
        dt = tz.localize(datetime(2026, 3, 7, 10, 0))  # Sábado
        schedule = _get_day_schedule(dt)
        assert schedule is not None
        assert schedule["start"] == "08:00"

    def test_domingo_retorna_none(self):
        """Domingo debe retornar None."""
        dt = tz.localize(datetime(2026, 3, 8, 10, 0))  # Domingo
        schedule = _get_day_schedule(dt)
        assert schedule is None
