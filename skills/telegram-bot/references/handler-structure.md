# Estructura de Handlers

## Principio

Cada handler debe ser **delgado** (thin): su única responsabilidad es traducir
la interacción de Telegram a llamadas al Orquestador y formatear las respuestas.

## Estructura de Carpetas

```
src/bot/
├── __init__.py
├── app.py                  # Configuración de Application y registro de handlers
├── middleware.py            # Verificación de permisos
├── constants.py             # Textos, emojis, estados de conversación
├── formatters.py            # Funciones para formatear respuestas (eventos, contactos)
├── keyboards.py             # Generadores de InlineKeyboard y ReplyKeyboard
└── handlers/
    ├── __init__.py
    ├── start.py             # /start y /menu
    ├── crear_evento.py      # Flujo de creación de evento
    ├── editar_evento.py     # Flujo de edición de evento
    ├── ver_eventos.py       # Ver lista de eventos pendientes
    ├── eliminar_evento.py   # Flujo de eliminación de evento
    ├── terminar_evento.py   # Flujo de cierre/completar evento
    ├── contactos.py         # Ver y editar contactos
    └── natural.py           # Handler de texto libre (delega al LLM)
```

## Ejemplo de Handler

```python
# src/bot/handlers/crear_evento.py
from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from src.bot.middleware import require_role
from src.bot.constants import States, Messages
from src.bot.formatters import format_event_confirmation
from src.orchestrator import Orchestrator

# Estados de la conversación
WAITING_DESCRIPTION = 0
WAITING_CONFIRMATION = 1


@require_role("admin")
async def start_crear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de creación de evento."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(Messages.DESCRIBE_EVENT)
    return WAITING_DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la descripción en lenguaje natural y la parsea."""
    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    result = await orchestrator.create_event_from_text(
        text=update.message.text,
        user_id=update.effective_user.id,
    )
    if result.needs_clarification:
        await update.message.reply_text(result.question)
        return WAITING_DESCRIPTION

    context.user_data["pending_event"] = result.event
    confirmation = format_event_confirmation(result.event)
    await update.message.reply_text(confirmation)
    return WAITING_CONFIRMATION


def get_conversation_handler() -> ConversationHandler:
    """Retorna el ConversationHandler para crear eventos."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_crear, pattern="^crear_evento$"),
        ],
        states={
            WAITING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description),
            ],
            WAITING_CONFIRMATION: [
                CallbackQueryHandler(confirm_event, pattern="^confirm_yes$"),
                CallbackQueryHandler(cancel_event, pattern="^confirm_no$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
```

## Notas Clave

- Los handlers **nunca** acceden directamente a la BD ni a Google Calendar.
- Todo pasa por el `Orchestrator` que está en `context.bot_data`.
- Los textos están centralizados en `constants.py` para facilitar cambios.
- Cada handler expone una función `get_conversation_handler()` que se registra
  en `app.py`.
