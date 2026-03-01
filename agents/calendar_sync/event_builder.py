"""Construcción de eventos para la Google Calendar API."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz

from agents.calendar_sync.colors import get_color_id
from agents.db_manager.models import Cliente
from agents.groq_parser.schemas import EditInstruction, ParsedMessage
from config.constants import DURACIONES_SERVICIO, TIMEZONE

tz = pytz.timezone(TIMEZONE)


def build_event(data: ParsedMessage, cliente: Cliente) -> dict:
    """Construye el dict de evento listo para la Google Calendar API.

    Prioridad de datos: DB > Mensaje > Default.

    Args:
        data: Mensaje parseado con datos del evento.
        cliente: Datos del cliente desde la base de datos.

    Returns:
        Dict compatible con la Google Calendar API.
    """
    # Prioridad DB > Mensaje para nombre y teléfono
    nombre = cliente.nombre_completo
    telefono = cliente.telefono or data.telefono or ""
    direccion = cliente.direccion or data.direccion or ""

    # Título: "nombre_completo - telefono"
    titulo = f"{nombre} - {telefono}" if telefono else nombre

    # Tipo de servicio
    tipo = data.tipo_servicio.value if data.tipo_servicio else "otro"

    # Duración
    duracion_horas = data.duracion_estimada_horas or DURACIONES_SERVICIO.get(tipo, 1.0)

    # Start / End con timezone
    fecha = data.fecha
    hora = data.hora
    if fecha is None or hora is None:
        msg = "fecha y hora son requeridos para construir un evento"
        raise ValueError(msg)

    start_dt = tz.localize(datetime.combine(fecha, hora))
    end_dt = start_dt + timedelta(hours=duracion_horas)

    # Descripción estándar
    tipo_display = tipo.capitalize()
    descripcion = (
        f"Tipo de Servicio: {tipo_display}\n"
        f"---\n"
        f"Notas: Creado vía IA\n"
        f"Descripción del trabajo:\n"
        f"Resultados:\n"
        f"Materiales/Equipos utilizados:\n"
        f"Códigos de cámaras/alarmas:"
    )

    return {
        "summary": titulo,
        "location": direccion,
        "description": descripcion,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "colorId": get_color_id(tipo),
    }


def build_patch(
    instruccion: EditInstruction,
    evento_actual: dict,
    cliente: Cliente,
) -> dict:
    """Construye el dict de PATCH a partir de un EditInstruction.

    Solo incluye en el dict los campos que tienen valor en la instrucción.

    Args:
        instruccion: Instrucción de edición con campos opcionales.
        evento_actual: Evento actual de Google Calendar.
        cliente: Datos del cliente desde la base de datos.

    Returns:
        Dict con solo los campos a modificar.
    """
    patch: dict = {}

    # Si cambia fecha u hora, recalcular start/end
    if instruccion.nueva_fecha is not None or instruccion.nueva_hora is not None:
        # Obtener start actual para extraer fecha/hora base
        start_actual = _parse_datetime(evento_actual["start"]["dateTime"])
        fecha = instruccion.nueva_fecha or start_actual.date()
        hora = instruccion.nueva_hora or start_actual.time()

        # Calcular duración actual para mantenerla
        end_actual = _parse_datetime(evento_actual["end"]["dateTime"])
        duracion = instruccion.nueva_duracion_horas
        if duracion is not None:
            duracion_td = timedelta(hours=duracion)
        else:
            duracion_td = end_actual - start_actual

        new_start = tz.localize(datetime.combine(fecha, hora))
        new_end = new_start + duracion_td

        patch["start"] = {
            "dateTime": new_start.isoformat(),
            "timeZone": TIMEZONE,
        }
        patch["end"] = {
            "dateTime": new_end.isoformat(),
            "timeZone": TIMEZONE,
        }
    elif instruccion.nueva_duracion_horas is not None:
        # Solo cambia duración, mantener start
        start_actual = _parse_datetime(evento_actual["start"]["dateTime"])
        new_end = start_actual + timedelta(hours=instruccion.nueva_duracion_horas)
        patch["start"] = {
            "dateTime": start_actual.isoformat(),
            "timeZone": TIMEZONE,
        }
        patch["end"] = {
            "dateTime": new_end.isoformat(),
            "timeZone": TIMEZONE,
        }

    # Si cambia dirección
    if instruccion.nueva_direccion is not None:
        patch["location"] = instruccion.nueva_direccion

    # Si cambia tipo de servicio → recalcular colorId
    if instruccion.nuevo_tipo_servicio is not None:
        patch["colorId"] = get_color_id(instruccion.nuevo_tipo_servicio.value)

    # Si cambia teléfono → recalcular título
    if instruccion.nuevo_telefono is not None:
        nombre = cliente.nombre_completo
        patch["summary"] = f"{nombre} - {instruccion.nuevo_telefono}"

    return patch


def _parse_datetime(dt_string: str) -> datetime:
    """Parsea un string ISO 8601 a datetime con timezone."""
    dt = datetime.fromisoformat(dt_string)
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt
