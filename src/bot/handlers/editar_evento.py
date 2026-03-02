# src/bot/handlers/editar_evento.py
"""ConversationHandler para la edición de eventos."""

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.bot.constants import CallbackData, Messages, States
from src.bot.formatters import format_event_detail
from src.bot.keyboards import build_confirmation_keyboard, build_event_list_keyboard
from src.bot.middleware import require_role

logger = logging.getLogger(__name__)

# Estados locales
WAITING_SELECT = States.EDITAR_SELECT
WAITING_CHANGES = States.EDITAR_CHANGES
WAITING_CONFIRMATION = States.EDITAR_CONFIRMATION


@require_role("admin", "editor")
async def start_editar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de edición mostrando la lista de eventos pendientes."""
    query = update.callback_query
    await query.answer()

    context.user_data["chat_id"] = update.effective_chat.id

    orchestrator = context.bot_data["orchestrator"]
    eventos = await orchestrator.repo.list_eventos_pendientes()

    if not eventos:
        await query.edit_message_text(Messages.NO_PENDING_EVENTS)
        return ConversationHandler.END

    keyboard = build_event_list_keyboard(eventos, action="editar")
    await query.edit_message_text(
        Messages.SELECT_EVENT_EDIT,
        reply_markup=keyboard,
    )
    return WAITING_SELECT


async def select_evento(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario seleccionó un evento para editar."""
    query = update.callback_query
    await query.answer()

    evento_id = int(query.data.replace("editar_", ""))
    orchestrator = context.bot_data["orchestrator"]

    evento = await orchestrator.repo.get_evento_by_id(evento_id)
    if not evento:
        await query.edit_message_text("❌ Evento no encontrado.")
        return ConversationHandler.END

    context.user_data["editing_evento_id"] = evento_id
    context.user_data["editing_evento"] = evento

    cliente = await orchestrator.repo.get_cliente_by_id(evento.cliente_id)
    detail = format_event_detail(evento, cliente)

    await query.edit_message_text(
        f"{detail}\n\n{Messages.DESCRIBE_CHANGES}",
        parse_mode="Markdown",
    )
    return WAITING_CHANGES


async def receive_changes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe la descripción de cambios en lenguaje natural."""
    orchestrator = context.bot_data["orchestrator"]
    evento = context.user_data.get("editing_evento")

    if not evento:
        await update.message.reply_text("❌ Error: no se encontró el evento.")
        return ConversationHandler.END

    result = await orchestrator.edit_event_from_text(
        text=update.message.text,
        evento=evento,
        user_id=update.effective_user.id,
    )

    if result.ok:
        context.user_data["pending_changes"] = result.data
        # Mostrar resumen de cambios y pedir confirmación
        changes_text = _format_changes(result.data)
        keyboard = build_confirmation_keyboard()
        await update.message.reply_text(
            f"✏️ *Cambios a aplicar:*\n\n{changes_text}\n\n¿Confirmás los cambios?",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return WAITING_CONFIRMATION

    if result.needs_input:
        await update.message.reply_text(result.question or Messages.DESCRIBE_CHANGES)
        return WAITING_CHANGES

    await update.message.reply_text(f"❌ {result.message}")
    return ConversationHandler.END


async def confirm_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Confirma y aplica los cambios al evento."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    evento_id = context.user_data.get("editing_evento_id")
    changes = context.user_data.get("pending_changes", {})

    result = await orchestrator.apply_event_changes(
        evento_id=evento_id,
        changes=changes,
    )

    if result.ok:
        await query.edit_message_text(f"✅ {Messages.EVENT_UPDATED}")
    else:
        await query.edit_message_text(f"❌ {result.message}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Cancela la edición."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(Messages.OPERATION_CANCELLED)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handler de /cancel para salir de la conversación."""
    await update.message.reply_text(Messages.OPERATION_CANCELLED)
    context.user_data.clear()
    return ConversationHandler.END


async def timeout_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handler de timeout para conversaciones abandonadas."""
    chat_id = context.user_data.get("chat_id")
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=Messages.CONVERSATION_TIMEOUT,
        )
    context.user_data.clear()
    return ConversationHandler.END


def _format_changes(changes: dict) -> str:
    """Formatea los cambios para mostrar al usuario."""
    if not changes:
        return "Sin cambios detectados."
    lines = []
    for field, value in changes.items():
        lines.append(f"• *{field}*: {value}")
    return "\n".join(lines)


def get_conversation_handler() -> ConversationHandler:
    """Retorna el ConversationHandler para editar eventos."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_editar,
                pattern=f"^{CallbackData.EDITAR_EVENTO}$",
            ),
        ],
        states={
            WAITING_SELECT: [
                CallbackQueryHandler(select_evento, pattern=r"^editar_\d+$"),
            ],
            WAITING_CHANGES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_changes,
                ),
            ],
            WAITING_CONFIRMATION: [
                CallbackQueryHandler(
                    confirm_edit,
                    pattern=f"^{CallbackData.CONFIRM_YES}$",
                ),
                CallbackQueryHandler(
                    cancel_edit,
                    pattern=f"^{CallbackData.CONFIRM_NO}$",
                ),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout_handler),
                CallbackQueryHandler(timeout_handler),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CallbackQueryHandler(cancel_edit, pattern=f"^{CallbackData.CANCEL}$"),
        ],
        conversation_timeout=300,
    )
