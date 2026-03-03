# src/bot/formatters.py
"""Funciones de formateo de respuestas del bot de Telegram."""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from src.bot.constants import (
    TELEGRAM_MAX_LENGTH,
    SERVICE_EMOJIS,
    get_service_emoji,
)
from src.db.models import Cliente, Evento, TipoServicio

logger = logging.getLogger(__name__)


def format_events_list(
    eventos: list[Evento], clientes: Optional[dict[int, Cliente]] = None
) -> str:
    """Formatea una lista de eventos agrupados por día.

    Args:
        eventos: Lista de eventos a formatear.
        clientes: Diccionario opcional id->Cliente para mostrar nombres.

    Returns:
        Texto formateado en Markdown con eventos agrupados.

    Ejemplo de salida:
        📅 *Lunes 03/03/2026*
        ─────────────────────
        🔵 10:00 — *Juan Pérez*
           Instalación · Balcarce 132
    """
    if not eventos:
        return "No hay eventos pendientes."

    # Agrupar por fecha
    by_day: dict[str, list[Evento]] = defaultdict(list)
    for ev in eventos:
        day_key = _format_day_header(ev.fecha_hora)
        by_day[day_key].append(ev)

    lines: list[str] = []
    for date_header, day_events in by_day.items():
        lines.append(f"📅 *{date_header}*")
        lines.append("─────────────────────")
        for ev in day_events:
            emoji = get_service_emoji(ev.tipo_servicio)
            cliente_name = _get_cliente_name(ev, clientes)
            lines.append(f"{emoji} {ev.hora_formateada} — *{cliente_name}*")
            tipo_display = ev.tipo_servicio.value.capitalize()
            # Agregar dirección si está disponible
            direccion = _get_cliente_direccion(ev, clientes)
            if direccion:
                lines.append(f"   {tipo_display} · {direccion}")
            else:
                lines.append(f"   {tipo_display}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _flatten_event_data(event_data: dict) -> dict:
    """Aplana un dict estructurado del orchestrator a un dict plano.

    Si event_data tiene las claves 'evento', 'cliente' y/o 'parsed',
    extrae los campos relevantes y los devuelve en un dict plano que
    format_event_confirmation puede consumir.  Si ya es un dict plano,
    lo devuelve sin cambios.

    Args:
        event_data: Dict plano o estructurado del orchestrator.

    Returns:
        Dict plano con claves: tipo_servicio, cliente_nombre, telefono,
        direccion, fecha, hora, fecha_formateada, hora_formateada, notas.
    """
    # Si no tiene la clave 'evento', asumir que ya es plano
    if "evento" not in event_data:
        return event_data

    flat: dict = {}
    evento = event_data.get("evento")
    cliente = event_data.get("cliente")
    parsed = event_data.get("parsed")

    # Datos del Evento model
    if evento is not None:
        flat["tipo_servicio"] = getattr(evento, "tipo_servicio", None)
        flat["notas"] = getattr(evento, "notas", None)
        fecha_hora = getattr(evento, "fecha_hora", None)
        if fecha_hora is not None:
            flat["fecha_formateada"] = fecha_hora.strftime("%d/%m/%Y")
            flat["hora_formateada"] = fecha_hora.strftime("%H:%M")
            flat["fecha"] = fecha_hora.date()
            flat["hora"] = fecha_hora.time()
        duracion = getattr(evento, "duracion_minutos", None)
        if duracion is not None:
            flat["duracion_minutos"] = duracion

    # Datos del Cliente model
    if cliente is not None:
        flat["cliente_nombre"] = getattr(cliente, "nombre", None)
        flat["telefono"] = getattr(cliente, "telefono", None)
        flat["direccion"] = getattr(cliente, "direccion", None)

    # Datos del ParsedEvent (complementar si el cliente no tiene dirección)
    if parsed is not None:
        if not flat.get("direccion"):
            flat["direccion"] = getattr(parsed, "direccion", None)
        if not flat.get("telefono"):
            flat["cliente_telefono"] = getattr(parsed, "cliente_telefono", None)
        # Guardar nombre parseado para detectar discrepancias con el resuelto
        parsed_nombre = getattr(parsed, "cliente_nombre", None)
        if parsed_nombre:
            flat["_parsed_cliente_nombre"] = parsed_nombre

    return flat


def format_event_confirmation(event_data: dict) -> str:
    """Formatea el resumen de confirmación previo a guardar.

    REGLA: El tipo de servicio SIEMPRE debe mostrarse. Nunca "Sin tipo".

    Soporta dos formatos de entrada:
    - Dict plano: {"tipo_servicio": "instalacion", "cliente_nombre": "Juan", ...}
    - Dict estructurado del orchestrator: {"evento": Evento, "cliente": Cliente, "parsed": ParsedEvent}

    Args:
        event_data: Diccionario con datos del evento (del orquestador).

    Returns:
        Texto formateado en Markdown con resumen del evento.
    """
    # Si viene del orchestrator con objetos anidados, aplanar primero
    flat = _flatten_event_data(event_data)

    # Extraer datos — soporta tanto dict plano como objetos
    tipo = _extract_field(flat, "tipo_servicio", "otro")
    # Garantizar que nunca sea "Sin tipo"
    if not tipo or tipo == "null":
        tipo = "otro"
    tipo_display = tipo.capitalize() if isinstance(tipo, str) else tipo

    cliente = _extract_field(flat, "cliente_nombre", "Sin nombre")
    # Detectar si el cliente resuelto difiere del nombre que dijo el usuario
    parsed_nombre = flat.get("_parsed_cliente_nombre")
    client_warning = ""
    if (
        parsed_nombre
        and cliente != "Sin nombre"
        and parsed_nombre.lower().strip() != cliente.lower().strip()
    ):
        client_warning = (
            f"\n\n"
            f"⚠️ El teléfono ya pertenece a *{cliente}*. "
            f'Se usará ese cliente en lugar de "{parsed_nombre}".'
        )
    telefono = _extract_field(flat, "telefono", "No especificado")
    if not telefono or telefono == "No especificado":
        telefono = _extract_field(flat, "cliente_telefono", "No especificado")
    direccion = _extract_field(flat, "direccion", "No especificada")
    fecha = _extract_field(flat, "fecha_formateada", "")
    if not fecha:
        fecha = _extract_field(flat, "fecha", "No especificada")
    hora = _extract_field(flat, "hora_formateada", "")
    if not hora:
        hora = _extract_field(flat, "hora", "No especificada")
    notas = _extract_field(flat, "notas", "Sin notas")
    if not notas:
        notas = "Sin notas"

    return (
        f"📋 *Resumen del evento*\n\n"
        f"🔧 Tipo de servicio: {tipo_display}\n"
        f"👤 Cliente: {cliente}\n"
        f"📞 Teléfono: {telefono}\n"
        f"📍 Dirección: {direccion}\n"
        f"📅 Fecha: {fecha}\n"
        f"🕐 Hora: {hora}\n"
        f"📝 Notas: {notas}"
        f"{client_warning}\n\n"
        f"¿Confirmás la creación del evento?"
    )


def format_event_detail(evento: Evento, cliente: Optional[Cliente] = None) -> str:
    """Formatea el detalle completo de un evento.

    Args:
        evento: Evento a formatear.
        cliente: Cliente asociado (opcional).

    Returns:
        Texto formateado con todos los detalles.
    """
    emoji = get_service_emoji(evento.tipo_servicio)
    tipo_display = evento.tipo_servicio.value.capitalize()
    cliente_name = cliente.nombre if cliente else f"Cliente #{evento.cliente_id}"
    fecha = evento.fecha_hora.strftime("%d/%m/%Y")
    hora = evento.hora_formateada

    lines = [
        f"{emoji} *Evento #{evento.id}*",
        "",
        f"🔧 Tipo: {tipo_display}",
        f"👤 Cliente: {cliente_name}",
    ]

    if cliente and cliente.telefono:
        lines.append(f"📞 Teléfono: {cliente.telefono}")
    if cliente and cliente.direccion:
        lines.append(f"📍 Dirección: {cliente.direccion}")

    lines.extend(
        [
            f"📅 Fecha: {fecha}",
            f"🕐 Hora: {hora}",
            f"⏱️ Duración: {evento.duracion_minutos} min",
            f"📊 Estado: {evento.estado.value.capitalize()}",
        ]
    )

    if evento.notas:
        lines.append(f"📝 Notas: {evento.notas}")

    return "\n".join(lines)


def format_contacts_list(contacts: list[Cliente]) -> str:
    """Formatea una lista de contactos.

    Args:
        contacts: Lista de clientes a formatear.

    Returns:
        Texto formateado en Markdown.

    Ejemplo de salida:
        👤 *Juan Pérez* — 351-1234567
        📍 Balcarce 132
    """
    if not contacts:
        return "No hay contactos registrados."

    lines: list[str] = []
    for c in contacts:
        telefono = c.telefono or "Sin teléfono"
        lines.append(f"👤 *{c.nombre}* — {telefono}")
        if c.direccion:
            lines.append(f"📍 {c.direccion}")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_closure_confirmation(
    evento: Evento, cliente: Optional[Cliente] = None
) -> str:
    """Formatea la confirmación de cierre de un servicio.

    Args:
        evento: Evento completado con datos de cierre.
        cliente: Cliente asociado (opcional).

    Returns:
        Texto formateado con datos de cierre.
    """
    emoji = get_service_emoji(evento.tipo_servicio)
    cliente_name = cliente.nombre if cliente else f"Cliente #{evento.cliente_id}"

    lines = [
        f"{emoji} *Cierre de servicio*",
        "",
        f"👤 Cliente: {cliente_name}",
        f"🔧 Tipo: {evento.tipo_servicio.value.capitalize()}",
    ]

    if evento.trabajo_realizado:
        lines.append(f"📋 Trabajo realizado: {evento.trabajo_realizado}")

    if evento.monto_cobrado is not None:
        lines.append(f"💰 Monto cobrado: ${evento.monto_cobrado:,.0f}")

    if evento.notas_cierre:
        lines.append(f"📝 Notas de cierre: {evento.notas_cierre}")

    if evento.fotos:
        lines.append(f"📸 Fotos: {len(evento.fotos)} adjuntada(s)")

    return "\n".join(lines)


def split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Divide un texto largo en partes que respeten el límite de Telegram.

    Corta en saltos de línea para no romper formato Markdown.

    Args:
        text: Texto a dividir.
        max_length: Longitud máxima por parte.

    Returns:
        Lista de strings, cada uno dentro del límite.
    """
    if len(text) <= max_length:
        return [text]

    parts: list[str] = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        # Buscar el último salto de línea dentro del límite
        cut = text.rfind("\n", 0, max_length)
        if cut == -1:
            # Sin salto de línea — cortar en el límite duro
            cut = max_length

        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")

    return parts


async def send_long_message(
    bot,
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown",
) -> None:
    """Envía un mensaje largo dividiéndolo en partes si es necesario.

    Args:
        bot: Instancia del Bot de Telegram.
        chat_id: ID del chat destino.
        text: Texto a enviar.
        parse_mode: Modo de parseo de Telegram (Markdown/HTML).
    """
    parts = split_message(text)
    for part in parts:
        await bot.send_message(
            chat_id=chat_id,
            text=part,
            parse_mode=parse_mode,
        )


# ── Helpers privados ──────────────────────────────────────────────────────────


_DAYS_ES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def _format_day_header(dt: datetime) -> str:
    """Formatea un datetime como encabezado de día.

    Args:
        dt: Datetime del evento.

    Returns:
        String con formato "Lunes 03/03/2026".
    """
    day_name = _DAYS_ES.get(dt.weekday(), "")
    return f"{day_name} {dt.strftime('%d/%m/%Y')}"


def _get_cliente_name(
    evento: Evento,
    clientes: Optional[dict[int, Cliente]] = None,
) -> str:
    """Obtiene el nombre del cliente de un evento.

    Args:
        evento: Evento con cliente_id.
        clientes: Diccionario id->Cliente.

    Returns:
        Nombre del cliente o "Cliente #ID" como fallback.
    """
    if clientes and evento.cliente_id in clientes:
        return clientes[evento.cliente_id].nombre
    return f"Cliente #{evento.cliente_id}"


def _get_cliente_direccion(
    evento: Evento,
    clientes: Optional[dict[int, Cliente]] = None,
) -> Optional[str]:
    """Obtiene la dirección del cliente de un evento.

    Args:
        evento: Evento con cliente_id.
        clientes: Diccionario id->Cliente.

    Returns:
        Dirección del cliente o None si no está disponible.
    """
    if clientes and evento.cliente_id in clientes:
        return clientes[evento.cliente_id].direccion
    return None


def _extract_field(data: dict, field: str, default: str = "") -> str:
    """Extrae un campo de un diccionario, soportando claves anidadas.

    Args:
        data: Diccionario de datos.
        field: Nombre del campo.
        default: Valor por defecto.

    Returns:
        Valor del campo como string.
    """
    if isinstance(data, dict):
        value = data.get(field, default)
        # Si el valor es un enum, obtener su value
        if hasattr(value, "value"):
            return value.value
        return str(value) if value is not None else default
    # Si es un objeto con atributos
    value = getattr(data, field, default)
    if hasattr(value, "value"):
        return value.value
    return str(value) if value is not None else default
