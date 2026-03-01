"""Motor de horario laboral: franjas disponibles, capacidad del día."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from config.constants import TIME_SLOT_INTERVAL_MINUTES, TIMEZONE, WORK_DAYS, WORK_SCHEDULE
from core.logger import get_logger

log = get_logger(__name__)


def get_day_schedule(fecha: date) -> dict | None:
    """Retorna el horario laboral de un día.

    Args:
        fecha: Fecha a consultar.

    Returns:
        Dict con start, end, total_hours o None si no es día laboral (domingo).
    """
    weekday = fecha.weekday()
    if weekday == 6:  # Domingo
        return WORK_SCHEDULE["sunday"]
    if weekday == 5:  # Sábado
        return WORK_SCHEDULE["saturday"]
    return WORK_SCHEDULE["weekday"]


def get_available_slots(
    fecha: date,
    duracion_horas: float,
    eventos_del_dia: list[dict],
    buffer_minutes: int = 30,
    interval_minutes: int = TIME_SLOT_INTERVAL_MINUTES,
) -> list[tuple[time, time]]:
    """Calcula franjas horarias disponibles para un día dado.

    Genera rangos completos (inicio, fin) que no se solapan con eventos existentes
    y que caben dentro del horario laboral del día.

    Args:
        fecha: Fecha del día a consultar.
        duracion_horas: Duración del servicio en horas.
        eventos_del_dia: Lista de eventos de Google Calendar del día.
        buffer_minutes: Margen en minutos entre eventos.
        interval_minutes: Intervalo entre inicio de franjas sucesivas.

    Returns:
        Lista de tuplas (hora_inicio, hora_fin) disponibles.
    """
    schedule = get_day_schedule(fecha)
    if schedule is None:
        return []

    # Parsear horario laboral
    start_str = schedule["start"]
    end_str = schedule["end"]
    work_start = _parse_time(start_str)
    work_end = _parse_time(end_str)

    # Calcular bloques ocupados (con buffer)
    bloques_ocupados = _extraer_bloques_ocupados(eventos_del_dia, buffer_minutes)

    # Generar candidatos cada interval_minutes desde work_start
    duracion = timedelta(hours=duracion_horas)
    interval = timedelta(minutes=interval_minutes)

    slots: list[tuple[time, time]] = []
    current_dt = datetime.combine(fecha, work_start)
    end_dt = datetime.combine(fecha, work_end)

    while current_dt + duracion <= end_dt:
        slot_start = current_dt.time()
        slot_end = (current_dt + duracion).time()

        # Verificar que no se solapa con ningún bloque ocupado
        if not _solapa_con_bloques(current_dt, current_dt + duracion, bloques_ocupados):
            slots.append((slot_start, slot_end))

        current_dt += interval

    log.debug(
        "available_slots_calculated",
        fecha=str(fecha),
        duracion_horas=duracion_horas,
        total_slots=len(slots),
    )
    return slots


def is_day_fully_booked(
    fecha: date,
    duracion_horas: float,
    eventos_del_dia: list[dict],
    buffer_minutes: int = 30,
) -> bool:
    """Verifica si el día está completamente lleno para un servicio de la duración dada.

    Args:
        fecha: Fecha a verificar.
        duracion_horas: Duración del servicio en horas.
        eventos_del_dia: Lista de eventos del día.
        buffer_minutes: Margen entre eventos.

    Returns:
        True si no hay ninguna franja disponible.
    """
    slots = get_available_slots(fecha, duracion_horas, eventos_del_dia, buffer_minutes)
    return len(slots) == 0


def calculate_free_hours(
    fecha: date,
    eventos_del_dia: list[dict],
) -> float:
    """Calcula las horas libres restantes en un día.

    Args:
        fecha: Fecha a consultar.
        eventos_del_dia: Lista de eventos del día.

    Returns:
        Horas libres disponibles (0.0 si es domingo o día no laboral).
    """
    schedule = get_day_schedule(fecha)
    if schedule is None:
        return 0.0

    total_hours = schedule["total_hours"]
    horas_ocupadas = _sumar_duraciones_eventos(eventos_del_dia)
    free = max(total_hours - horas_ocupadas, 0.0)

    log.debug(
        "free_hours_calculated",
        fecha=str(fecha),
        total_hours=total_hours,
        horas_ocupadas=horas_ocupadas,
        free=free,
    )
    return free


# ── Helpers privados ──────────────────────────────────────────────────────────


def _parse_time(time_str: str) -> time:
    """Parsea 'HH:MM' a time."""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def _extraer_bloques_ocupados(
    eventos: list[dict],
    buffer_minutes: int,
) -> list[tuple[datetime, datetime]]:
    """Extrae bloques de tiempo ocupados (con buffer) de una lista de eventos."""
    buffer = timedelta(minutes=buffer_minutes)
    bloques: list[tuple[datetime, datetime]] = []

    for evento in eventos:
        start_str = evento.get("start", {}).get("dateTime")
        end_str = evento.get("end", {}).get("dateTime")
        if not start_str or not end_str:
            continue

        evt_start = datetime.fromisoformat(start_str)
        evt_end = datetime.fromisoformat(end_str)

        # Quitar timezone para comparación con naive datetimes
        if evt_start.tzinfo is not None:
            evt_start = evt_start.replace(tzinfo=None)
        if evt_end.tzinfo is not None:
            evt_end = evt_end.replace(tzinfo=None)

        bloques.append((evt_start - buffer, evt_end + buffer))

    return bloques


def _solapa_con_bloques(
    start: datetime,
    end: datetime,
    bloques: list[tuple[datetime, datetime]],
) -> bool:
    """Verifica si un rango se solapa con algún bloque ocupado."""
    for bloque_start, bloque_end in bloques:
        if start < bloque_end and end > bloque_start:
            return True
    return False


def _sumar_duraciones_eventos(eventos: list[dict]) -> float:
    """Suma las duraciones de una lista de eventos en horas."""
    total = 0.0
    for evento in eventos:
        start_str = evento.get("start", {}).get("dateTime")
        end_str = evento.get("end", {}).get("dateTime")
        if not start_str or not end_str:
            continue

        evt_start = datetime.fromisoformat(start_str)
        evt_end = datetime.fromisoformat(end_str)
        delta = (evt_end - evt_start).total_seconds() / 3600
        total += delta

    return total
