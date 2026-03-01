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
