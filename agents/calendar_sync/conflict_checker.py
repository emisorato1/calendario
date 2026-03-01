"""Detección de conflictos horarios y sugerencia de alternativas."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytz

from config.constants import TIMEZONE, WORK_DAYS, WORK_SCHEDULE
from core.logger import get_logger

if TYPE_CHECKING:
    from agents.calendar_sync.client import CalendarClient

log = get_logger(__name__)

tz = pytz.timezone(TIMEZONE)


async def check_conflicts(
    client: CalendarClient,
    calendar_id: str,
    start: datetime,
    end: datetime,
    buffer_minutes: int = 30,
) -> list[dict]:
    """Consulta eventos en [start - buffer, end + buffer] y retorna los solapados.

    Args:
        client: Instancia de CalendarClient.
        calendar_id: ID del calendario de Google.
        start: Inicio del evento propuesto.
        end: Fin del evento propuesto.
        buffer_minutes: Margen en minutos antes y después del evento.

    Returns:
        Lista de eventos solapados (vacía si no hay conflictos).
    """
    buffer = timedelta(minutes=buffer_minutes)
    search_start = start - buffer
    search_end = end + buffer

    eventos = await client.listar_eventos(
        time_min=search_start,
        time_max=search_end,
    )

    conflictos = []
    for evento in eventos:
        evt_start_str = evento.get("start", {}).get("dateTime")
        evt_end_str = evento.get("end", {}).get("dateTime")
        if not evt_start_str or not evt_end_str:
            continue

        evt_start = datetime.fromisoformat(evt_start_str)
        evt_end = datetime.fromisoformat(evt_end_str)

        # Hay solapamiento si los rangos se intersectan
        if evt_start < end and evt_end > start:
            conflictos.append(evento)

    log.info(
        "check_conflicts_resultado",
        start=start.isoformat(),
        end=end.isoformat(),
        buffer_minutes=buffer_minutes,
        conflictos_encontrados=len(conflictos),
    )
    return conflictos


def suggest_alternatives(
    start: datetime,
    duration_hours: float,
    n: int = 3,
) -> list[dict]:
    """Genera N horarios alternativos a partir de un horario con conflicto.

    Estrategia:
        1. Mismo día +2h
        2. Siguiente día hábil, mismo horario
        3. Siguiente día hábil, +2h

    Args:
        start: Horario original propuesto.
        duration_hours: Duración del servicio en horas.
        n: Cantidad de alternativas a generar.

    Returns:
        Lista de dicts con start/end como datetime.
    """
    duration = timedelta(hours=duration_hours)
    alternativas: list[dict] = []

    # Alternativa 1: mismo día +2h
    alt1_start = start + timedelta(hours=2)
    alternativas.append(
        {
            "start": alt1_start,
            "end": alt1_start + duration,
        }
    )

    # Alternativa 2: siguiente día hábil, mismo horario
    next_work_day = _next_work_day(start)
    alt2_start = next_work_day.replace(
        hour=start.hour,
        minute=start.minute,
        second=0,
        microsecond=0,
    )
    alternativas.append(
        {
            "start": alt2_start,
            "end": alt2_start + duration,
        }
    )

    # Alternativa 3: siguiente día hábil +2h
    alt3_start = alt2_start + timedelta(hours=2)
    alternativas.append(
        {
            "start": alt3_start,
            "end": alt3_start + duration,
        }
    )

    return alternativas[:n]


def _next_work_day(dt: datetime) -> datetime:
    """Retorna el siguiente día hábil a partir de una fecha.

    Args:
        dt: Datetime de referencia.

    Returns:
        Datetime del siguiente día hábil (misma hora).
    """
    candidate = dt + timedelta(days=1)
    while candidate.weekday() not in WORK_DAYS:
        candidate += timedelta(days=1)
    return candidate


def _get_day_schedule(dt: datetime) -> dict | None:
    """Retorna el horario laboral de un día.

    Args:
        dt: Datetime de referencia.

    Returns:
        Dict con start/end/total_hours o None si no es día laboral.
    """
    weekday = dt.weekday()
    if weekday == 5:  # Sábado
        return WORK_SCHEDULE["saturday"]
    if weekday == 6:  # Domingo
        return WORK_SCHEDULE["sunday"]
    return WORK_SCHEDULE["weekday"]
