# Formato de Respuestas

## Principio

Las respuestas del bot deben ser **claras, compactas y visualmente agradables**.
Usar emojis de forma consistente y formateo Markdown (soportado por Telegram).

## Formato de Lista de Eventos

```python
def format_events_list(events_by_day: dict) -> str:
    """
    Formatea una lista de eventos agrupados por día.
    
    Ejemplo de salida:
    📅 *Lunes 03/03/2026*
    ─────────────────────
    🔵 10:00 — *Juan Pérez*
       Instalación · Balcarce 132
    
    🟡 14:00 — *María García*
       Revisión · San Martín 456
    """
    lines = []
    for date, events in events_by_day.items():
        lines.append(f"📅 *{date}*")
        lines.append("─────────────────────")
        for ev in events:
            lines.append(f"{ev.emoji} {ev.hora} — *{ev.cliente}*")
            lines.append(f"   {ev.tipo_servicio} · {ev.direccion}")
        lines.append("")
    return "\n".join(lines)
```

## Formato de Confirmación de Evento

```python
def format_event_confirmation(event) -> str:
    """
    Formatea el resumen de confirmación previo a guardar.
    
    REGLA: El tipo de servicio SIEMPRE debe mostrarse. Nunca "Sin tipo".
    El campo tipo_servicio tiene default "otro" y un validador que impide null,
    pero este formatter agrega un guardrail adicional por seguridad.
    """
    tipo = event.tipo_servicio or "Otro"
    # Capitalizar para presentación
    tipo_display = tipo.capitalize() if isinstance(tipo, str) else tipo.value.capitalize()
    
    return (
        f"📋 *Resumen del evento*\n\n"
        f"🔧 Tipo de servicio: {tipo_display}\n"
        f"👤 Cliente: {event.cliente_nombre}\n"
        f"📞 Teléfono: {event.telefono}\n"
        f"📍 Dirección: {event.direccion}\n"
        f"📅 Fecha: {event.fecha_formateada}\n"
        f"🕐 Hora: {event.hora_formateada}\n"
        f"📝 Notas: {event.notas or 'Sin notas'}\n\n"
        f"¿Confirmás la creación del evento?"
    )
```

## Formato de Lista de Contactos

```python
def format_contacts_list(contacts: list) -> str:
    """
    Ejemplo de salida:
    👤 *Juan Pérez* — 351-1234567
    📍 Balcarce 132
    
    👤 *María García* — 351-9876543
    📍 San Martín 456
    """
    lines = []
    for c in contacts:
        lines.append(f"👤 *{c.nombre}* — {c.telefono}")
        if c.direccion:
            lines.append(f"📍 {c.direccion}")
        lines.append("")
    return "\n".join(lines)
```

## Mapa de Emojis por Tipo de Servicio

```python
SERVICE_EMOJIS = {
    "instalacion": "🔵",
    "revision": "🟡",
    "mantenimiento": "🟠",
    "reparacion": "🟠",
    "presupuesto": "🟡",
    "otro": "⚪",
}
```

## Notas

- Usar `parse_mode="Markdown"` en los `send_message`.
- Los emojis de color reflejan los colores de Google Calendar.
- Limitar respuestas a 4096 caracteres (límite de Telegram).
- Para listas largas, implementar paginación con botones "Anterior/Siguiente".

## Manejo del Límite de 4096 Caracteres

Telegram rechaza mensajes que excedan 4096 caracteres. Hay dos estrategias
complementarias: **split** (dividir un texto largo en partes) y **paginación**
(mostrar N ítems por página con botones de navegación).

### Split de Mensajes Largos

Para respuestas que pueden exceder el límite (listados, reportes):

```python
TELEGRAM_MAX_LENGTH = 4096

def split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """
    Divide un texto largo en partes que respeten el límite de Telegram.
    Corta en saltos de línea para no romper formato Markdown.
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
    """Envía un mensaje largo dividiéndolo en partes si es necesario."""
    parts = split_message(text)
    for part in parts:
        await bot.send_message(
            chat_id=chat_id,
            text=part,
            parse_mode=parse_mode,
        )
```

### Paginación con Botones

Para listas de eventos o contactos donde el usuario navega entre páginas:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

ITEMS_PER_PAGE = 5

def paginate_items(
    items: list,
    page: int,
    per_page: int = ITEMS_PER_PAGE,
) -> tuple[list, int]:
    """
    Retorna (items_de_la_pagina, total_paginas).
    page es 0-indexed.
    """
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    return items[start : start + per_page], total_pages


def build_pagination_keyboard(
    page: int,
    total_pages: int,
    callback_prefix: str,
) -> InlineKeyboardMarkup | None:
    """
    Construye teclado con botones ◀ Anterior / Siguiente ▶.
    callback_prefix identifica la lista (ej: "ev_page", "cli_page").
    Retorna None si hay una sola página.
    """
    if total_pages <= 1:
        return None

    buttons = []
    if page > 0:
        buttons.append(
            InlineKeyboardButton("◀ Anterior", callback_data=f"{callback_prefix}:{page - 1}")
        )
    buttons.append(
        InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton("Siguiente ▶", callback_data=f"{callback_prefix}:{page + 1}")
        )
    return InlineKeyboardMarkup([buttons])
```

#### Ejemplo de uso en handler:

```python
async def listar_eventos(update, context):
    """Lista eventos pendientes con paginación."""
    eventos = repo.list_eventos(estado="pendiente")
    if not eventos:
        await update.message.reply_text("No hay eventos pendientes.")
        return

    page = int(context.args[0]) if context.args else 0
    page_items, total_pages = paginate_items(eventos, page)

    text = format_events_list(agrupar_por_dia(page_items))
    keyboard = build_pagination_keyboard(page, total_pages, "ev_page")

    # Usar send_long_message por si una sola página excede 4096
    parts = split_message(text)
    for i, part in enumerate(parts):
        if i == len(parts) - 1 and keyboard:
            await update.message.reply_text(part, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text(part, parse_mode="Markdown")


async def handle_pagination_callback(update, context):
    """Maneja clicks en botones de paginación."""
    query = update.callback_query
    await query.answer()

    prefix, page_str = query.data.rsplit(":", 1)
    if prefix == "noop":
        return
    page = int(page_str)

    if prefix == "ev_page":
        eventos = repo.list_eventos(estado="pendiente")
        page_items, total_pages = paginate_items(eventos, page)
        text = format_events_list(agrupar_por_dia(page_items))
    elif prefix == "cli_page":
        clientes = repo.list_clientes()
        page_items, total_pages = paginate_items(clientes, page)
        text = format_contacts_list(page_items)
    else:
        return

    keyboard = build_pagination_keyboard(page, total_pages, prefix)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
```

### Cuándo usar cada estrategia

| Escenario | Estrategia |
|-----------|------------|
| Confirmación de evento, detalle individual | `send_long_message` (split si excede) |
| Lista de eventos pendientes | Paginación (5 por página) |
| Lista de contactos | Paginación (5 por página) |
| Mensaje de error / ayuda | Directo (siempre <4096) |
