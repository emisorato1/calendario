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
    return (
        f"✅ *Evento creado correctamente*\n\n"
        f"📋 Tipo: {event.tipo_servicio}\n"
        f"👤 Cliente: {event.cliente_nombre}\n"
        f"📞 Teléfono: {event.telefono}\n"
        f"📍 Dirección: {event.direccion}\n"
        f"📅 Fecha: {event.fecha_formateada}\n"
        f"🕐 Hora: {event.hora_formateada}\n"
        f"📝 Notas: {event.notas or 'Sin notas'}"
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
    "completado": "🟢",
}
```

## Notas

- Usar `parse_mode="Markdown"` en los `send_message`.
- Los emojis de color reflejan los colores de Google Calendar.
- Limitar respuestas a 4096 caracteres (límite de Telegram).
- Para listas largas, implementar paginación con botones "Anterior/Siguiente".
