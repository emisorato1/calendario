# Menú y Botones Inline

## Diseño del Menú Principal

El menú principal se muestra al ejecutar `/start` o `/menu`. Se implementa con
`InlineKeyboardMarkup` para una experiencia limpia y profesional.

## Ejemplo de Implementación

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_main_menu(role: str) -> InlineKeyboardMarkup:
    """
    Construye el menú principal según el rol del usuario.
    
    Args:
        role: 'admin' o 'editor'
    
    Returns:
        InlineKeyboardMarkup con los botones disponibles.
    """
    buttons = []

    if role == "admin":
        buttons.append(
            [InlineKeyboardButton("📝 Crear Evento", callback_data="crear_evento")]
        )

    buttons.extend([
        [InlineKeyboardButton("✏️ Editar Evento", callback_data="editar_evento")],
        [InlineKeyboardButton("📋 Ver Eventos", callback_data="ver_eventos")],
    ])

    if role == "admin":
        buttons.append(
            [InlineKeyboardButton("🗑️ Eliminar Evento", callback_data="eliminar_evento")]
        )

    buttons.extend([
        [InlineKeyboardButton("✅ Terminar Evento", callback_data="terminar_evento")],
        [InlineKeyboardButton("👥 Ver Contactos", callback_data="ver_contactos")],
    ])

    if role == "admin":
        buttons.append(
            [InlineKeyboardButton("✏️ Editar Contacto", callback_data="editar_contacto")]
        )

    return InlineKeyboardMarkup(buttons)
```

## Botones de Confirmación

Para acciones destructivas (eliminar) o irreversibles (crear):

```python
def build_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Cancelar", callback_data="confirm_no"),
        ]
    ])
```

## Botones de Selección de Eventos

Para mostrar una lista de eventos seleccionables:

```python
def build_event_list_keyboard(events: list) -> InlineKeyboardMarkup:
    buttons = []
    for event in events:
        label = f"{event.emoji} {event.hora} — {event.cliente_nombre}"
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f"event_{event.id}")]
        )
    buttons.append(
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    )
    return InlineKeyboardMarkup(buttons)
```

## Notas

- Los `callback_data` siguen el patrón `{accion}_{id}` para parsearse fácilmente.
- Las listas de eventos se paginan si hay más de 8 (limitación de Telegram).
- Los botones se adaptan dinámicamente al rol del usuario.

## Botones de Horarios Disponibles

Para mostrar los slots horarios libres cuando falta la hora de un evento.
El usuario puede seleccionar 1, 2 o 3 bloques consecutivos.

```python
def build_time_slots_keyboard(
    available_slots: list,
    selected: list[str] = None,
) -> InlineKeyboardMarkup:
    """
    Construye un teclado con los horarios disponibles del día.
    
    Args:
        available_slots: Lista de AvailableSlot del Orquestador.
        selected: Lista de slots ya seleccionados (para multi-selección).
    
    Returns:
        InlineKeyboardMarkup con botones de horarios.
    
    Ejemplo visual:
        [15:00 - 16:00]
        [16:00 - 17:00]
        [17:00 - 18:00]
        [19:00 - 20:00]
        ──────────────
        [✅ Confirmar selección]
        [❌ Cancelar]
    """
    selected = selected or []
    buttons = []
    
    for slot in available_slots:
        slot_label = f"{slot.start.strftime('%H:%M')} - {slot.end.strftime('%H:%M')}"
        slot_id = f"{slot.start.strftime('%H:%M')}-{slot.end.strftime('%H:%M')}"
        
        # Marcar slots ya seleccionados
        if slot_id in selected:
            slot_label = f"✅ {slot_label}"
        
        buttons.append(
            [InlineKeyboardButton(slot_label, callback_data=f"slot_{slot_id}")]
        )
    
    # Botón de confirmar si hay al menos un slot seleccionado
    if selected:
        buttons.append(
            [InlineKeyboardButton(
                "✅ Confirmar selección",
                callback_data="slot_confirm",
            )]
        )
    
    buttons.append(
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    )
    
    return InlineKeyboardMarkup(buttons)
```

### Reglas de selección múltiple de horarios

- El usuario puede presionar **1, 2 o 3** botones de horarios.
- Los horarios seleccionados deben ser **consecutivos** (uno seguido del otro).
- Si el usuario selecciona un horario no consecutivo, se deselecciona la
  selección anterior y se empieza de nuevo con el nuevo horario.
- La duración total del evento se calcula como: `cantidad_slots * 60 minutos`.
- Ejemplo: si selecciona 15:00-16:00 y 16:00-17:00, el evento va de 15:00 a 17:00
  con duración de 120 minutos.

```python
def validate_consecutive_slots(selected_slots: list[str]) -> bool:
    """Verifica que los slots seleccionados sean consecutivos."""
    if len(selected_slots) <= 1:
        return True
    
    for i in range(len(selected_slots) - 1):
        current_end = selected_slots[i].split("-")[1]   # "16:00"
        next_start = selected_slots[i + 1].split("-")[0]  # "16:00"
        if current_end != next_start:
            return False
    return True
```
