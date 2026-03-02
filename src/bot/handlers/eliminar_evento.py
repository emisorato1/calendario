# src/bot/handlers/eliminar_evento.py
"""ConversationHandler para la eliminación de eventos."""

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
WAITING_SELECT = States.ELIMINAR_SELECT
WAITING_CONFIRMATION = States.ELIMINAR_CONFIRMATION


@require_role("admin")
async def start_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de eliminación mostrando la lista de eventos pendientes."""
    query = update.callback_query
    await query.answer()

    context.user_data["chat_id"] = update.effective_chat.id

    orchestrator = context.bot_data["orchestrator"]
    eventos = await orchestrator.repo.list_eventos_pendientes()

    if not eventos:
        await query.edit_message_text(Messages.NO_PENDING_EVENTS)
        return ConversationHandler.END

    keyboard = build_event_list_keyboard(eventos, action="eliminar")
    await query.edit_message_text(
        Messages.SELECT_EVENT_DELETE,
        reply_markup=keyboard,
    )
    return WAITING_SELECT


async def select_evento(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """El usuario seleccionó un evento para eliminar."""
    query = update.callback_query
    await query.answer()

    evento_id = int(query.data.replace("eliminar_", ""))
    orchestrator = context.bot_data["orchestrator"]

    evento = await orchestrator.repo.get_evento_by_id(evento_id)
    if not evento:
        await query.edit_message_text("❌ Evento no encontrado.")
        return ConversationHandler.END

    context.user_data["deleting_evento_id"] = evento_id

    cliente = await orchestrator.repo.get_cliente_by_id(evento.cliente_id)
    detail = format_event_detail(evento, cliente)

    keyboard = build_confirmation_keyboard()
    await query.edit_message_text(
        f"{detail}\n\n{Messages.CONFIRM_DELETE}",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return WAITING_CONFIRMATION


async def confirm_delete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Confirma y ejecuta la eliminación del evento."""
    query = update.callback_query
    await query.answer()

    orchestrator = context.bot_data["orchestrator"]
    evento_id = context.user_data.get("deleting_evento_id")

    result = await orchestrator.delete_event(evento_id)

    if result.ok:
        await query.edit_message_text(f"✅ {Messages.EVENT_DELETED}")
    else:
        await query.edit_message_text(f"❌ {result.message}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_delete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Cancela la eliminación."""
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


def get_conversation_handler() -> ConversationHandler:
    """Retorna el ConversationHandler para eliminar eventos."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_eliminar,
                pattern=f"^{CallbackData.ELIMINAR_EVENTO}$",
            ),
        ],
        states={
            WAITING_SELECT: [
                CallbackQueryHandler(select_evento, pattern=r"^eliminar_\d+$"),
            ],
            WAITING_CONFIRMATION: [
                CallbackQueryHandler(
                    confirm_delete,
                    pattern=f"^{CallbackData.CONFIRM_YES}$",
                ),
                CallbackQueryHandler(
                    cancel_delete,
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
            CallbackQueryHandler(cancel_delete, pattern=f"^{CallbackData.CANCEL}$"),
        ],
        conversation_timeout=300,
    )
