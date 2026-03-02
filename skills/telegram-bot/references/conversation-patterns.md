# ConversationHandler Patterns

## Concepto

Los `ConversationHandler` de `python-telegram-bot` permiten crear flujos de
conversación de múltiples pasos. Son ideales para este proyecto porque cada
acción (crear, editar, terminar evento) requiere recopilar datos del usuario
en varios turnos.

## Ciclo de Vida

```
entry_points → estado_1 → estado_2 → ... → fin
                  ↑            |
                  └────────────┘  (si falta info)
```

## Patrón Estándar

```python
ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_flow, pattern="^action_name$"),
    ],
    states={
        STEP_1: [MessageHandler(filters.TEXT, handle_step_1)],
        STEP_2: [CallbackQueryHandler(handle_step_2, pattern="^option_")],
        CONFIRM: [CallbackQueryHandler(handle_confirm, pattern="^confirm_")],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_conversation),
        CallbackQueryHandler(cancel_conversation, pattern="^cancel$"),
        MessageHandler(filters.COMMAND, cancel_conversation),
    ],
    conversation_timeout=300,  # 5 minutos de timeout
)
```

## Manejo de Timeouts

```python
async def timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se ejecuta cuando la conversación expira.
    
    NOTA: En python-telegram-bot v20+, cuando se dispara conversation_timeout,
    update puede ser None. Se debe usar context.bot.send_message() directamente
    con el chat_id almacenado en context.user_data.
    """
    chat_id = context.user_data.get("chat_id")
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text="La conversación expiró por inactividad. Usá /menu para reiniciar.",
        )
    return ConversationHandler.END
```

**Importante:** En cada entry_point, guardar `context.user_data["chat_id"] = update.effective_chat.id` para que el timeout handler pueda enviar el mensaje.

## Flujo con Re-preguntas (Fallback del LLM)

Cuando el orquestador necesita más información del usuario:

```python
async def handle_description(update, context):
    result = await orchestrator.create_event_from_text(
        update.message.text, update.effective_user.id,
    )
    
    if result.needs_input:
        # Re-preguntar lo que falta
        await update.message.reply_text(
            f"Necesito un poco más de información:\n{result.question}"
        )
        context.user_data["partial_result"] = result
        return WAITING_DESCRIPTION  # Volver al mismo estado
    
    if result.ok:
        # Continuar al siguiente paso (confirmación)
        context.user_data["pending_event"] = result.data
        return WAITING_CONFIRMATION
```

## Flujo de Creación de Evento (con estados de fecha/hora)

El flujo de creación tiene estados adicionales para manejar la recolección
secuencial de fecha y hora:

```python
# Estados de la conversación de crear evento
WAITING_DESCRIPTION = 0   # Esperando texto libre del usuario
WAITING_DATE = 1           # Falta la fecha, esperando respuesta
WAITING_TIME_SLOT = 2      # Falta la hora, mostrando botones de horarios
WAITING_CONFIRMATION = 3   # Mostrando resumen, esperando confirmar/cancelar

ConversationHandler(
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

### Flujo detallado de estados:

```python
async def receive_description(update, context):
    """Recibe texto libre, parsea con LLM y decide siguiente estado."""
    orchestrator = context.bot_data["orchestrator"]
    context.user_data["original_text"] = update.message.text
    
    result = await orchestrator.create_event_from_text(
        text=update.message.text,
        user_id=update.effective_user.id,
    )
    
    # Caso 1: Todo completo → resumen y confirmación
    if result.ok:
        context.user_data["pending_event"] = result.data
        confirmation = format_event_confirmation(result.data)
        keyboard = build_confirmation_keyboard()
        await update.message.reply_text(confirmation, reply_markup=keyboard)
        return WAITING_CONFIRMATION
    
    # Caso 2: Falta información (fecha, hora, u otros datos)
    if result.needs_input:
        slots = result.data.get("available_slots") if result.data else None
        if slots:
            # Tiene fecha, falta hora → mostrar botones de horarios
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
    
    # Caso 3: Conflicto de horario
    if result.status == ResultStatus.CONFLICT:
        slots = result.data.get("available_slots") if result.data else None
        if slots:
            # Hay horarios alternativos → mostrar botones
            keyboard = build_time_slots_keyboard(slots)
            await update.message.reply_text(
                f"⚠️ {result.message}",
                reply_markup=keyboard,
            )
            return WAITING_TIME_SLOT
        else:
            # No quedan horarios → pedir otro día
            context.user_data["partial_result"] = result
            await update.message.reply_text(f"⚠️ {result.message}")
            return WAITING_DATE
    
    # Caso 4: Error (fecha pasada, fuera de horario, etc.)
    await update.message.reply_text(f"❌ {result.message}")
    return ConversationHandler.END


async def receive_date(update, context):
    """Recibe la fecha del usuario y re-procesa el evento."""
    orchestrator = context.bot_data["orchestrator"]
    original_text = context.user_data.get("original_text", "")
    combined = f"{original_text} {update.message.text}"
    
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
            # Ahora tiene fecha pero falta hora → mostrar botones
            context.user_data["partial_result"] = result
            keyboard = build_time_slots_keyboard(slots)
            await update.message.reply_text(
                result.question or "Elegí el horario para el evento:",
                reply_markup=keyboard,
            )
            return WAITING_TIME_SLOT
        else:
            # Todavía falta la fecha (no se entendió)
            await update.message.reply_text(
                "No pude entender la fecha. Por favor indicá un día concreto "
                "(ej: mañana, el viernes, el 15/03)."
            )
            return WAITING_DATE
    
    # Error o conflicto → volver al inicio
    if result.message:
        await update.message.reply_text(f"❌ {result.message}")
    return WAITING_DESCRIPTION


async def receive_time_slot(update, context):
    """Recibe la selección de horario por botón inline."""
    query = update.callback_query
    await query.answer()
    
    # Extraer horario del callback_data (formato: "slot_15:00-16:00")
    slot_data = query.data.replace("slot_", "")
    
    # Si el usuario seleccionó múltiples slots consecutivos,
    # se acumulan en context.user_data["selected_slots"]
    selected = context.user_data.get("selected_slots", [])
    selected.append(slot_data)
    context.user_data["selected_slots"] = selected
    
    # Recalcular el evento con el horario seleccionado
    # La hora de inicio es el primer slot, la duración = cantidad de slots * 60
    start_time = selected[0].split("-")[0]  # "15:00"
    duration = len(selected) * 60
    
    # Actualizar el evento parcial con hora y duración
    partial = context.user_data.get("partial_result")
    # ... completar y crear evento
    
    context.user_data["pending_event"] = evento
    confirmation = format_event_confirmation(evento)
    keyboard = build_confirmation_keyboard()
    await query.edit_message_text(confirmation, reply_markup=keyboard)
    return WAITING_CONFIRMATION
```

## Notas

- Siempre incluir un fallback con `/cancel` para permitir al usuario salir.
- Configurar `conversation_timeout` para evitar conversaciones colgadas.
- Un usuario solo puede tener una conversación activa a la vez (por defecto).
- Usar `context.user_data` para pasar datos entre pasos de la conversación.
- **WAITING_DATE** y **WAITING_TIME_SLOT** son estados nuevos para el flujo
  secuencial de fecha y hora.
- Cuando falta la hora, NUNCA se pregunta por texto. Se muestran botones
  inline con los horarios disponibles calculados por el Orquestador.
- El usuario puede presionar 1, 2 o 3 botones consecutivos para seleccionar
  bloques de 1, 2 o 3 horas respectivamente.
