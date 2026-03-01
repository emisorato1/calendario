"""Tests para core/work_schedule.py — Motor de horario laboral."""

from __future__ import annotations

from datetime import date, time

from core.work_schedule import (
    calculate_free_hours,
    get_available_slots,
    get_day_schedule,
    is_day_fully_booked,
)


# ── get_day_schedule ─────────────────────────────────────────────────────────


class TestGetDaySchedule:
    """Tests para get_day_schedule()."""

    def test_lunes_retorna_horario_semana(self):
        """Lunes → weekday schedule {start: 15:00, end: 21:00, total_hours: 6.0}."""
        # Lunes 2 de marzo 2026
        fecha = date(2026, 3, 2)
        assert fecha.weekday() == 0  # Lunes
        result = get_day_schedule(fecha)
        assert result is not None
        assert result["start"] == "15:00"
        assert result["end"] == "21:00"
        assert result["total_hours"] == 6.0

    def test_martes_retorna_horario_semana(self):
        """Martes → mismo horario weekday."""
        fecha = date(2026, 3, 3)
        assert fecha.weekday() == 1
        result = get_day_schedule(fecha)
        assert result is not None
        assert result["start"] == "15:00"

    def test_viernes_retorna_horario_semana(self):
        """Viernes → mismo horario weekday."""
        fecha = date(2026, 3, 6)
        assert fecha.weekday() == 4
        result = get_day_schedule(fecha)
        assert result is not None
        assert result["total_hours"] == 6.0

    def test_sabado_retorna_horario_sabado(self):
        """Sábado → {start: 08:00, end: 20:00, total_hours: 12.0}."""
        fecha = date(2026, 3, 7)
        assert fecha.weekday() == 5
        result = get_day_schedule(fecha)
        assert result is not None
        assert result["start"] == "08:00"
        assert result["end"] == "20:00"
        assert result["total_hours"] == 12.0

    def test_domingo_retorna_none(self):
        """Domingo → None (sin servicio)."""
        fecha = date(2026, 3, 8)
        assert fecha.weekday() == 6
        result = get_day_schedule(fecha)
        assert result is None


# ── get_available_slots ──────────────────────────────────────────────────────


class TestGetAvailableSlots:
    """Tests para get_available_slots()."""

    def test_sin_eventos_retorna_todos_los_slots(self):
        """Lunes sin eventos, duración 2h → retorna todas las franjas posibles."""
        fecha = date(2026, 3, 2)  # Lunes
        slots = get_available_slots(fecha, 2.0, [], buffer_minutes=0)
        assert len(slots) > 0
        # Primer slot debe empezar a las 15:00
        assert slots[0][0] == time(15, 0)
        # Cada tupla es (inicio, fin)
        for start, end in slots:
            assert start < end

    def test_retorna_tuplas_inicio_fin(self):
        """Cada elemento es una tupla (time, time) de inicio y fin."""
        fecha = date(2026, 3, 2)
        slots = get_available_slots(fecha, 1.0, [], buffer_minutes=0)
        for slot in slots:
            assert isinstance(slot, tuple)
            assert len(slot) == 2
            assert isinstance(slot[0], time)
            assert isinstance(slot[1], time)

    def test_excluye_franja_ocupada(self):
        """Evento 16:00-18:00 → rangos que se solapan no aparecen."""
        fecha = date(2026, 3, 2)  # Lunes 15:00-21:00
        eventos = [
            {
                "start": {"dateTime": "2026-03-02T16:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T18:00:00-03:00"},
            }
        ]
        slots = get_available_slots(fecha, 1.0, eventos, buffer_minutes=0)
        # Ningún slot debe empezar entre 16 y 17 (inclusive)
        for start, end in slots:
            assert not (time(16, 0) <= start < time(18, 0))

    def test_excluye_franja_con_buffer(self):
        """Con buffer_minutes=30, se extiende la exclusión."""
        fecha = date(2026, 3, 2)
        eventos = [
            {
                "start": {"dateTime": "2026-03-02T17:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T18:00:00-03:00"},
            }
        ]
        slots_sin_buffer = get_available_slots(fecha, 1.0, eventos, buffer_minutes=0)
        slots_con_buffer = get_available_slots(fecha, 1.0, eventos, buffer_minutes=30)
        # Con buffer hay menos slots disponibles
        assert len(slots_con_buffer) <= len(slots_sin_buffer)

    def test_excluye_franja_que_no_cabe(self):
        """Duración 3h en lunes: rango 19:00+ no aparece (excede cierre de 21:00)."""
        fecha = date(2026, 3, 2)
        slots = get_available_slots(fecha, 3.0, [], buffer_minutes=0)
        for start, end in slots:
            # Fin no puede exceder las 21:00
            assert end <= time(21, 0)

    def test_domingo_retorna_lista_vacia(self):
        """Domingo → sin slots."""
        fecha = date(2026, 3, 8)
        slots = get_available_slots(fecha, 1.0, [])
        assert slots == []

    def test_sabado_tiene_mas_slots_que_dia_semana(self):
        """Sábado (12h) tiene más slots que día de semana (6h)."""
        lunes = date(2026, 3, 2)
        sabado = date(2026, 3, 7)
        slots_lunes = get_available_slots(lunes, 1.0, [], buffer_minutes=0)
        slots_sabado = get_available_slots(sabado, 1.0, [], buffer_minutes=0)
        assert len(slots_sabado) > len(slots_lunes)

    def test_dia_completamente_ocupado_retorna_vacio(self):
        """Si el día está totalmente ocupado, no hay slots."""
        fecha = date(2026, 3, 2)  # Lunes 15:00-21:00
        eventos = [
            {
                "start": {"dateTime": "2026-03-02T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T21:00:00-03:00"},
            }
        ]
        slots = get_available_slots(fecha, 1.0, eventos, buffer_minutes=0)
        assert slots == []


# ── is_day_fully_booked ──────────────────────────────────────────────────────


class TestIsDayFullyBooked:
    """Tests para is_day_fully_booked()."""

    def test_true_cuando_sin_franjas(self):
        """Si no hay ninguna franja disponible → True."""
        fecha = date(2026, 3, 2)
        eventos = [
            {
                "start": {"dateTime": "2026-03-02T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T21:00:00-03:00"},
            }
        ]
        assert is_day_fully_booked(fecha, 1.0, eventos, buffer_minutes=0) is True

    def test_false_con_espacios_libres(self):
        """Si quedan tuplas disponibles → False."""
        fecha = date(2026, 3, 2)
        assert is_day_fully_booked(fecha, 1.0, [], buffer_minutes=0) is False

    def test_true_para_domingo(self):
        """Domingo → siempre completamente lleno."""
        fecha = date(2026, 3, 8)
        assert is_day_fully_booked(fecha, 1.0, []) is True


# ── calculate_free_hours ─────────────────────────────────────────────────────


class TestCalculateFreeHours:
    """Tests para calculate_free_hours()."""

    def test_dia_vacio_retorna_total(self):
        """Lunes sin eventos → 6.0 horas libres."""
        fecha = date(2026, 3, 2)
        result = calculate_free_hours(fecha, [])
        assert result == 6.0

    def test_descuenta_eventos(self):
        """Lunes con 2h de eventos → 4.0 horas libres."""
        fecha = date(2026, 3, 2)
        eventos = [
            {
                "start": {"dateTime": "2026-03-02T16:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T18:00:00-03:00"},
            }
        ]
        result = calculate_free_hours(fecha, eventos)
        assert result == 4.0

    def test_sabado_vacio_retorna_12(self):
        """Sábado sin eventos → 12.0 horas libres."""
        fecha = date(2026, 3, 7)
        result = calculate_free_hours(fecha, [])
        assert result == 12.0

    def test_domingo_retorna_cero(self):
        """Domingo → 0.0 horas libres."""
        fecha = date(2026, 3, 8)
        result = calculate_free_hours(fecha, [])
        assert result == 0.0

    def test_dia_completamente_lleno_retorna_cero(self):
        """Lunes con 6h de eventos → 0.0 horas libres."""
        fecha = date(2026, 3, 2)
        eventos = [
            {
                "start": {"dateTime": "2026-03-02T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T21:00:00-03:00"},
            }
        ]
        result = calculate_free_hours(fecha, eventos)
        assert result == 0.0

    def test_no_baja_de_cero(self):
        """Si los eventos exceden el total, no retorna negativo."""
        fecha = date(2026, 3, 2)
        eventos = [
            {
                "start": {"dateTime": "2026-03-02T14:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T22:00:00-03:00"},
            }
        ]
        result = calculate_free_hours(fecha, eventos)
        assert result == 0.0

    def test_ignora_eventos_sin_datetime(self):
        """Eventos sin dateTime se ignoran (sin error)."""
        fecha = date(2026, 3, 2)
        eventos = [
            {"start": {}, "end": {}},
            {"start": {"date": "2026-03-02"}, "end": {"date": "2026-03-02"}},
        ]
        result = calculate_free_hours(fecha, eventos)
        assert result == 6.0
