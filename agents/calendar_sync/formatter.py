"""Formateo de eventos de Google Calendar para mensajes de Telegram."""

from __future__ import annotations

from datetime import datetime

from config.constants import COLOR_EMOJI

# Emojis numéricos para listas
_NUM_EMOJI: dict[int, str] = {
    1: "1\ufe0f\u20e3",
    2: "2\ufe0f\u20e3",
    3: "3\ufe0f\u20e3",
    4: "4\ufe0f\u20e3",
    5: "5\ufe0f\u20e3",
    6: "6\ufe0f\u20e3",
    7: "7\ufe0f\u20e3",
    8: "8\ufe0f\u20e3",
    9: "9\ufe0f\u20e3",
    10: "\U0001f51f",
}

# Días de la semana en español (abreviado)
_DIAS_SEMANA: dict[int, str] = {
    0: "Lun",
    1: "Mar",
    2: "Mié",
    3: "Jue",
    4: "Vie",
    5: "Sáb",
    6: "Dom",
}

_DIAS_SEMANA_FULL: dict[int, str] = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def format_event_summary(evento: dict) -> str:
    """Formatea un evento como resumen de confirmación para Telegram.

    Formato:
        🔧 Tipo: Instalación de cámaras
        👤 Cliente: Carlos García
        📅 Fecha: Martes 03/03/2026
        🕐 Hora: 10:00 - 13:00 (3h)
        📍 Dirección: Av. San Martín 456
        🎨 Color: 🔵 Azul

    Args:
        evento: Dict de evento de Google Calendar.

    Returns:
        Texto formateado para Telegram.
    """
    start_dt = _parse_dt(evento.get("start", {}).get("dateTime", ""))
    end_dt = _parse_dt(evento.get("end", {}).get("dateTime", ""))

    # Tipo de servicio desde descripción
    tipo = _extract_tipo_servicio(evento.get("description", ""))

    # Cliente desde summary (formato: "Nombre - Teléfono")
    summary = evento.get("summary", "")
    cliente = summary.split(" - ")[0] if " - " in summary else summary

    # Fecha formateada
    fecha_str = ""
    if start_dt:
        dia_semana = _DIAS_SEMANA_FULL.get(start_dt.weekday(), "")
        fecha_str = f"{dia_semana} {start_dt.strftime('%d/%m/%Y')}"

    # Hora y duración
    hora_str = ""
    if start_dt and end_dt:
        duracion = end_dt - start_dt
        horas = duracion.total_seconds() / 3600
        hora_str = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')} ({horas:.0f}h)"

    # Color
    color_id = evento.get("colorId", "8")
    color_emoji = COLOR_EMOJI.get(color_id, "⚫")
    color_nombre = _color_nombre(color_id)

    # Dirección
    direccion = evento.get("location", "No especificada")

    lines = [
        f"\U0001f527 Tipo: {tipo}",
        f"\U0001f464 Cliente: {cliente}",
        f"\U0001f4c5 Fecha: {fecha_str}",
        f"\U0001f550 Hora: {hora_str}",
        f"\U0001f4cd Dirección: {direccion}",
        f"\U0001f3a8 Color: {color_emoji} {color_nombre}",
    ]
    return "\n".join(lines)


def format_event_list_item(evento: dict, index: int) -> str:
    """Formatea un evento como ítem de lista numerada para Telegram.

    Formato:
        2️⃣ Mar 03/03 | 10:00 - 13:00 | 🔵 Instalación — López, Pedro

    Args:
        evento: Dict de evento de Google Calendar.
        index: Posición en la lista (1-based).

    Returns:
        Texto formateado de una línea.
    """
    start_dt = _parse_dt(evento.get("start", {}).get("dateTime", ""))
    end_dt = _parse_dt(evento.get("end", {}).get("dateTime", ""))

    # Emoji numérico
    num_emoji = _NUM_EMOJI.get(index, f"{index}.")

    # Fecha corta
    fecha_str = ""
    if start_dt:
        dia = _DIAS_SEMANA.get(start_dt.weekday(), "")
        fecha_str = f"{dia} {start_dt.strftime('%d/%m')}"

    # Hora
    hora_str = ""
    if start_dt and end_dt:
        hora_str = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"

    # Color + tipo
    color_id = evento.get("colorId", "8")
    color_emoji = COLOR_EMOJI.get(color_id, "⚫")
    tipo = _extract_tipo_servicio(evento.get("description", ""))

    # Cliente
    summary = evento.get("summary", "")
    cliente = summary.split(" - ")[0] if " - " in summary else summary

    return f"{num_emoji} {fecha_str} | {hora_str} | {color_emoji} {tipo} — {cliente}"


def format_events_list(eventos: list[dict], titulo: str) -> str:
    """Formatea una lista completa de eventos para Telegram.

    Formato:
        📅 *Eventos pendientes (5):*

        📌 Lun 02/03 | 09:00 - 10:00 | 🟡 Revisión — García, Juan
        ...

    Args:
        eventos: Lista de dicts de eventos de Google Calendar.
        titulo: Título para el encabezado.

    Returns:
        Texto formateado completo.
    """
    if not eventos:
        return f"\U0001f4c5 *{titulo}:*\n\nNo hay eventos programados."

    header = f"\U0001f4c5 *{titulo} ({len(eventos)}):*\n"
    items = []
    for i, evento in enumerate(eventos, 1):
        items.append(
            f"\U0001f4cc {format_event_list_item(evento, i)[len(_NUM_EMOJI.get(i, f'{i}.')) + 1 :]}"
        )

    return header + "\n" + "\n".join(items)


def _parse_dt(dt_string: str) -> datetime | None:
    """Parsea string ISO 8601 a datetime. Retorna None si está vacío."""
    if not dt_string:
        return None
    return datetime.fromisoformat(dt_string)


def _extract_tipo_servicio(description: str) -> str:
    """Extrae el tipo de servicio desde la descripción del evento.

    Busca el patrón "Tipo de Servicio: <valor>" en la descripción.

    Args:
        description: Descripción del evento.

    Returns:
        Tipo de servicio capitalizado, o "Sin tipo" si no se encuentra.
    """
    for line in description.split("\n"):
        if line.strip().startswith("Tipo de Servicio:"):
            return line.split(":", 1)[1].strip()
    return "Sin tipo"


def _color_nombre(color_id: str) -> str:
    """Retorna el nombre legible de un color de Google Calendar."""
    nombres: dict[str, str] = {
        "5": "Amarillo",
        "6": "Naranja",
        "8": "Grafito",
        "9": "Azul",
    }
    return nombres.get(color_id, "Desconocido")
