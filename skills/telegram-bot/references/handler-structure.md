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
from src.bot.keyboards import build_confirmation_keyboard, build_time_slots_keyboard
from src.orchestrator import Orchestrator

# Estados de la conversación
WAITING_DESCRIPTION = 0
WAITING_DATE = 1
WAITING_TIME_SLOT = 2
WAITING_CONFIRMATION = 3


@require_role("admin")
async def start_crear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de creación de evento."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(Messages.DESCRIBE_EVENT)
    return WAITING_DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la descripción en lenguaje natural y la parsea."""
    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    context.user_data["original_text"] = update.message.text
    
    result = await orchestrator.create_event_from_text(
        text=update.message.text,
        user_id=update.effective_user.id,
    )
    
    if result.ok:
        # Todo completo → resumen y confirmación
        context.user_data["pending_event"] = result.data
        confirmation = format_event_confirmation(result.data)
        keyboard = build_confirmation_keyboard()
        await update.message.reply_text(confirmation, reply_markup=keyboard)
        return WAITING_CONFIRMATION
    
    if result.needs_input:
        slots = result.data.get("available_slots") if result.data else None
        if slots:
            # Tiene fecha, falta hora → mostrar botones de horarios disponibles
            context.user_data["partial_result"] = result
            keyboard = build_time_slots_keyboard(slots)
            await update.message.reply_text(
                result.question or "Elegí el horario para el evento:",
                reply_markup=keyboard,
            )
            return WAITING_TIME_SLOT
        else:
            # Falta fecha u otros datos → preguntar
            context.user_data["partial_result"] = result
            await update.message.reply_text(result.question)
            return WAITING_DATE if "fecha" in (result.question or "") else WAITING_DESCRIPTION
    
    if result.status == ResultStatus.CONFLICT:
        slots = result.data.get("available_slots") if result.data else None
        if slots:
            keyboard = build_time_slots_keyboard(slots)
            await update.message.reply_text(
                f"⚠️ {result.message}",
                reply_markup=keyboard,
            )
            return WAITING_TIME_SLOT
        else:
            context.user_data["partial_result"] = result
            await update.message.reply_text(f"⚠️ {result.message}")
            return WAITING_DATE
    
    # Error
    await update.message.reply_text(f"❌ Error: {result.message}")
    return ConversationHandler.END


async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la fecha y re-procesa para obtener horarios disponibles."""
    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    original = context.user_data.get("original_text", "")
    combined = f"{original} {update.message.text}"
    
    result = await orchestrator.create_event_from_text(
        text=combined, user_id=update.effective_user.id,
    )
    
    if result.ok:
        context.user_data["pending_event"] = result.data
        confirmation = format_event_confirmation(result.data)
        keyboard = build_confirmation_keyboard()
        await update.message.reply_text(confirmation, reply_markup=keyboard)
        return WAITING_CONFIRMATION
    
    if result.needs_input:
        slots = result.data.get("available_slots") if result.data else None
        if slots:
            context.user_data["partial_result"] = result
            keyboard = build_time_slots_keyboard(slots)
            await update.message.reply_text(
                result.question or "Elegí el horario para el evento:",
                reply_markup=keyboard,
            )
            return WAITING_TIME_SLOT
        else:
            await update.message.reply_text(
                "No pude entender la fecha. Indicá un día concreto "
                "(ej: mañana, el viernes, 15/03)."
            )
            return WAITING_DATE
    
    return WAITING_DESCRIPTION


async def confirm_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """El usuario confirmó la creación del evento → guardar en BD + Calendar."""
    query = update.callback_query
    await query.answer()
    
    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    pending = context.user_data.get("pending_event", {})
    
    save_result = await orchestrator.save_confirmed_event(
        evento=pending["evento"],
        cliente=pending["cliente"],
        parsed=pending.get("parsed"),
    )
    
    if save_result.ok:
        await query.edit_message_text(
            f"✅ {format_event_confirmation(save_result.data)}"
        )
    else:
        await query.edit_message_text(f"❌ {save_result.message}")
    
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """El usuario canceló la creación del evento."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Creación de evento cancelada.")
    context.user_data.clear()
    return ConversationHandler.END


async def receive_time_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe selección de horario por botón inline."""
    query = update.callback_query
    await query.answer()
    
    slot_data = query.data.replace("slot_", "")
    
    if slot_data == "confirm":
        # El usuario confirmó su selección de slots
        # Completar evento con horarios seleccionados y mostrar resumen
        # ...
        return WAITING_CONFIRMATION
    
    # Acumular slots seleccionados (máximo 3 consecutivos)
    selected = context.user_data.get("selected_slots", [])
    selected.append(slot_data)
    context.user_data["selected_slots"] = selected
    
    # Re-mostrar keyboard con slots marcados
    partial = context.user_data.get("partial_result")
    keyboard = build_time_slots_keyboard(partial.available_slots, selected)
    await query.edit_message_text(
        "Elegí el horario (podés seleccionar hasta 3 bloques consecutivos):",
        reply_markup=keyboard,
    )
    return WAITING_TIME_SLOT


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
            WAITING_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date),
            ],
            WAITING_TIME_SLOT: [
                CallbackQueryHandler(receive_time_slot, pattern="^slot_"),
            ],
            WAITING_CONFIRMATION: [
                CallbackQueryHandler(confirm_event, pattern="^confirm_yes$"),
                CallbackQueryHandler(cancel_event, pattern="^confirm_no$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        conversation_timeout=300,
    )
```

## Handler Natural (`natural.py`)

El handler natural captura **todo texto libre** que no sea comando ni parte de
una conversación activa. Delega al orquestador, que detecta la intención con el
LLM y ejecuta la acción correspondiente.

### Orquestador: `handle_natural_message`

```python
# En la clase Orchestrator (create-event-flow.md)
async def handle_natural_message(self, text: str, user_id: int) -> Result:
    """
    Punto de entrada para mensajes en lenguaje natural.
    Detecta intención → verifica permisos → delega al caso de uso.
    """
    # 1. Detectar intención
    intent_result = await self.parser.detect_intent(text)
    
    # 2. Verificar permisos para la intención
    if not self._check_permission(user_id, intent_result.intent):
        return Result.error("No tenés permiso para esta acción.")
    
    # 3. Delegar según intención
    match intent_result.intent:
        case Intent.CREAR_EVENTO:
            return await self.create_event_from_text(text, user_id)
        
        case Intent.EDITAR_EVENTO:
            # Necesita saber QUÉ evento editar → mostrar lista de pendientes
            eventos = await self.repo.list_eventos_pendientes()
            if not eventos:
                return Result.error("No hay eventos pendientes para editar.")
            return Result.success(
                data={"action": "editar", "eventos": eventos},
                message="¿Cuál evento querés editar?",
            )
        
        case Intent.ELIMINAR_EVENTO:
            # Necesita saber QUÉ evento eliminar → mostrar lista
            eventos = await self.repo.list_eventos_pendientes()
            if not eventos:
                return Result.error("No hay eventos pendientes para eliminar.")
            return Result.success(
                data={"action": "eliminar", "eventos": eventos},
                message="¿Cuál evento querés eliminar?",
            )
        
        case Intent.TERMINAR_EVENTO:
            # Necesita saber QUÉ evento terminar → mostrar lista
            eventos = await self.repo.list_eventos_pendientes()
            if not eventos:
                return Result.error("No hay eventos pendientes para terminar.")
            return Result.success(
                data={"action": "terminar", "eventos": eventos},
                message="¿Cuál evento querés marcar como terminado?",
            )
        
        case Intent.VER_EVENTOS:
            eventos = await self.repo.list_eventos_pendientes()
            return Result.success(data={"action": "ver_eventos", "eventos": eventos})
        
        case Intent.VER_CONTACTOS:
            clientes = await self.repo.list_clientes()
            return Result.success(data={"action": "ver_contactos", "clientes": clientes})
        
        case Intent.EDITAR_CONTACTO:
            clientes = await self.repo.list_clientes()
            if not clientes:
                return Result.error("No hay contactos para editar.")
            return Result.success(
                data={"action": "editar_contacto", "clientes": clientes},
                message="¿Cuál contacto querés editar?",
            )
        
        case Intent.SALUDO:
            return Result.success(
                message="¡Hola! ¿En qué puedo ayudarte? Usá /menu para ver las opciones.",
            )
        
        case Intent.AYUDA:
            return Result.success(
                message=(
                    "Puedo ayudarte con:\n"
                    "• Crear, editar o eliminar eventos\n"
                    "• Ver tu agenda de eventos pendientes\n"
                    "• Gestionar contactos\n"
                    "• Marcar eventos como terminados\n\n"
                    "Podés escribir en lenguaje natural o usar /menu."
                ),
            )
        
        case Intent.DESCONOCIDO | _:
            return Result.needs_clarification(
                "No entendí tu mensaje. Usá /menu para ver las acciones disponibles."
            )
```

### Handler Telegram: `natural.py`

```python
# src/bot/handlers/natural.py
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes
from src.bot.middleware import require_authorized
from src.bot.formatters import (
    format_events_list,
    format_contacts_list,
)
from src.bot.keyboards import (
    build_event_list_keyboard,
    build_contact_list_keyboard,
)


@require_authorized
async def handle_natural(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja mensajes de texto libre que no están dentro de una conversación.
    Detecta la intención via LLM y redirige al flujo correspondiente.
    """
    orchestrator = context.bot_data["orchestrator"]
    result = await orchestrator.handle_natural_message(
        text=update.message.text,
        user_id=update.effective_user.id,
    )
    
    if result.ok:
        data = result.data or {}
        action = data.get("action")
        
        if action == "ver_eventos":
            eventos = data.get("eventos", [])
            if not eventos:
                await update.message.reply_text("No hay eventos pendientes.")
                return
            await update.message.reply_text(format_events_list(eventos))
            return
        
        if action == "ver_contactos":
            clientes = data.get("clientes", [])
            if not clientes:
                await update.message.reply_text("No hay contactos registrados.")
                return
            await update.message.reply_text(format_contacts_list(clientes))
            return
        
        if action in ("editar", "eliminar", "terminar"):
            # Mostrar lista de eventos seleccionables para que el usuario elija
            eventos = data.get("eventos", [])
            keyboard = build_event_list_keyboard(eventos, action=action)
            await update.message.reply_text(
                result.message,
                reply_markup=keyboard,
            )
            return
        
        if action == "editar_contacto":
            clientes = data.get("clientes", [])
            keyboard = build_contact_list_keyboard(clientes)
            await update.message.reply_text(
                result.message,
                reply_markup=keyboard,
            )
            return
        
        # Intención simple (saludo, ayuda) → solo mensaje
        if result.message:
            await update.message.reply_text(result.message)
            return
    
    if result.needs_input:
        # Intención ambigua → mostrar pregunta o menú
        await update.message.reply_text(result.question or result.message)
        return
    
    # Error
    await update.message.reply_text(f"❌ {result.message}")


def get_natural_handler() -> MessageHandler:
    """
    Retorna el handler de texto libre.
    
    IMPORTANTE: Se registra DESPUÉS de todos los ConversationHandler
    para que solo capture mensajes que no son parte de una conversación.
    """
    return MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_natural,
    )
```

## Notas Clave

- Los handlers **nunca** acceden directamente a la BD ni a Google Calendar.
- Todo pasa por el `Orchestrator` que está en `context.bot_data`.
- Los textos están centralizados en `constants.py` para facilitar cambios.
- Cada handler expone una función `get_conversation_handler()` que se registra
  en `app.py`.
- El handler natural (`get_natural_handler()`) se registra **último** en `app.py`,
  después de todos los `ConversationHandler`. Esto es porque python-telegram-bot
  usa el orden de registro como prioridad: si un `ConversationHandler` ya está
  activo para un usuario, captura los mensajes antes que el handler natural.
- Las intenciones `EDITAR_EVENTO`, `ELIMINAR_EVENTO` y `TERMINAR_EVENTO` desde
  texto natural primero muestran la lista de eventos pendientes para que el
  usuario seleccione uno. Esa selección es manejada por los respectivos
  `ConversationHandler` de cada módulo (via `CallbackQueryHandler`).
- La intención `CREAR_EVENTO` desde texto natural delega directamente a
  `create_event_from_text`, que puede devolver el evento completo si el texto
  tiene toda la información (sin necesidad de pasar por el `ConversationHandler`).
