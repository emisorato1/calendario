# src/bot/handlers/start.py
"""Handlers para /start y /menu — menú principal del bot."""

import logging

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.bot.constants import CallbackData, Messages
from src.bot.keyboards import build_main_menu
from src.bot.middleware import get_user_role, require_authorized

logger = logging.getLogger(__name__)


@require_authorized
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /start. Muestra bienvenida y menú principal."""
    user = update.effective_user
    nombre = user.first_name or "usuario"
    role = get_user_role(user.id)

    welcome = Messages.WELCOME.format(nombre=nombre)
    keyboard = build_main_menu(role)

    await update.message.reply_text(
        f"{welcome}\n\n{Messages.MENU_HEADER}",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@require_authorized
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /menu. Muestra el menú principal."""
    user = update.effective_user
    role = get_user_role(user.id)
    keyboard = build_main_menu(role)

    await update.message.reply_text(
        Messages.MENU_HEADER,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@require_authorized
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el botón de volver al menú principal."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    role = get_user_role(user.id)
    keyboard = build_main_menu(role)

    await query.edit_message_text(
        Messages.MENU_HEADER,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


def get_start_handlers() -> list:
    """Retorna los handlers de /start y /menu.

    Returns:
        Lista de handlers para registrar en la Application.
    """
    return [
        CommandHandler("start", start_command),
        CommandHandler("menu", menu_command),
        CallbackQueryHandler(menu_callback, pattern="^menu$"),
    ]
