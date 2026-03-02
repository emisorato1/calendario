# src/bot/handlers/natural.py
"""Handler de texto libre — delega al LLM para detección de intención."""

import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from src.bot.constants import Messages
from src.bot.formatters import format_contacts_list, format_events_list
from src.bot.keyboards import (
    build_contact_list_keyboard,
    build_event_list_keyboard,
)
from src.bot.middleware import require_authorized

logger = logging.getLogger(__name__)


@require_authorized
async def handle_natural(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Maneja mensajes de texto libre que no están dentro de una conversación.

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
                await update.message.reply_text(Messages.NO_PENDING_EVENTS)
                return
            await update.message.reply_text(
                format_events_list(eventos),
                parse_mode="Markdown",
            )
            return

        if action == "ver_contactos":
            clientes = data.get("clientes", [])
            if not clientes:
                await update.message.reply_text(Messages.NO_CONTACTS)
                return
            await update.message.reply_text(
                format_contacts_list(clientes),
                parse_mode="Markdown",
            )
            return

        if action in ("editar", "eliminar", "terminar"):
            # Mostrar lista de eventos seleccionables
            eventos = data.get("eventos", [])
            keyboard = build_event_list_keyboard(eventos, action=action)
            await update.message.reply_text(
                result.message or f"Seleccioná un evento:",
                reply_markup=keyboard,
            )
            return

        if action == "editar_contacto":
            clientes = data.get("clientes", [])
            keyboard = build_contact_list_keyboard(clientes)
            await update.message.reply_text(
                result.message or Messages.SELECT_CONTACT,
                reply_markup=keyboard,
            )
            return

        # Intención simple (saludo, ayuda) → solo mensaje
        if result.message:
            await update.message.reply_text(result.message)
            return

    if result.needs_input:
        # Intención ambigua → mostrar pregunta o menú
        await update.message.reply_text(
            result.question or result.message or Messages.UNKNOWN_INTENT,
        )
        return

    # Error
    await update.message.reply_text(
        f"❌ {result.message or 'Error inesperado'}",
    )


def get_natural_handler() -> MessageHandler:
    """Retorna el handler de texto libre.

    IMPORTANTE: Se registra DESPUÉS de todos los ConversationHandler
    para que solo capture mensajes que no son parte de una conversación.

    Returns:
        MessageHandler para texto libre.
    """
    return MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_natural,
    )
