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
        MessageHandler(filters.COMMAND, cancel_conversation),
    ],
    conversation_timeout=300,  # 5 minutos de timeout
)
```

## Manejo de Timeouts

```python
async def timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se ejecuta cuando la conversación expira."""
    await update.effective_message.reply_text(
        "⏰ La conversación expiró por inactividad. Usá /menu para reiniciar."
    )
    return ConversationHandler.END
```

## Flujo con Re-preguntas (Fallback del LLM)

Cuando el LLM no puede interpretar completamente la entrada del usuario:

```python
async def handle_description(update, context):
    result = await orchestrator.parse_event(update.message.text)
    
    if result.needs_clarification:
        # Re-preguntar lo que falta
        await update.message.reply_text(
            f"Necesito un poco más de información:\n{result.question}"
        )
        return WAITING_DESCRIPTION  # Volver al mismo estado
    
    # Continuar al siguiente paso
    context.user_data["parsed_event"] = result
    return CONFIRMATION
```

## Notas

- Siempre incluir un fallback con `/cancel` para permitir al usuario salir.
- Configurar `conversation_timeout` para evitar conversaciones colgadas.
- Un usuario solo puede tener una conversación activa a la vez (por defecto).
- Usar `context.user_data` para pasar datos entre pasos de la conversación.
