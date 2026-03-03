# src/bot/middleware.py
"""Middleware de autenticación y permisos por rol para el bot de Telegram."""

import functools
import logging
from typing import Callable

from telegram import Update
from telegram.ext import ConversationHandler, ContextTypes

from src.bot.constants import Messages
from src.config import get_settings
from src.db.models import Rol

logger = logging.getLogger(__name__)


def get_user_role(telegram_id: int) -> str | None:
    """Determina el rol de un usuario por su Telegram ID.

    Verifica contra las listas de IDs configuradas en .env.

    Args:
        telegram_id: ID de Telegram del usuario.

    Returns:
        'admin', 'editor', o None si no está autorizado.
    """
    settings = get_settings()
    if telegram_id in settings.admin_telegram_ids:
        return Rol.ADMIN.value
    if telegram_id in settings.editor_telegram_ids:
        return Rol.EDITOR.value
    return None


def require_role(*roles: str) -> Callable:
    """Decorador que verifica que el usuario tenga uno de los roles especificados.

    Cuando se usa sobre entry points de ConversationHandler, retorna
    ConversationHandler.END en vez de None para no dejar la conversación
    en estado roto.

    Uso:
        @require_role("admin")
        async def handler(update, context): ...

        @require_role("admin", "editor")
        async def handler(update, context): ...

    Args:
        roles: Uno o más roles permitidos.

    Returns:
        Decorador que envuelve el handler.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args,
            **kwargs,
        ):
            user_id = update.effective_user.id if update.effective_user else None
            if user_id is None:
                logger.warning("Update sin effective_user, denegando acceso")
                return ConversationHandler.END

            user_role = get_user_role(user_id)

            if user_role is None:
                logger.warning(
                    "Acceso denegado: usuario %d no autorizado",
                    user_id,
                )
                await _send_denied_message(update, Messages.NOT_AUTHORIZED)
                return ConversationHandler.END

            if user_role not in roles:
                logger.warning(
                    "Acceso denegado: usuario %d (rol=%s) intentó acción que requiere %s",
                    user_id,
                    user_role,
                    roles,
                )
                await _send_denied_message(update, Messages.PERMISSION_DENIED)
                return ConversationHandler.END

            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator


def require_authorized(func: Callable) -> Callable:
    """Decorador que verifica que el usuario esté autorizado (cualquier rol).

    Equivale a @require_role("admin", "editor") pero con sintaxis más limpia
    para handlers que no necesitan rol específico.

    Retorna ConversationHandler.END al denegar acceso para compatibilidad
    con ConversationHandlers (aunque normalmente se usa en handlers simples).

    Uso:
        @require_authorized
        async def handler(update, context): ...

    Args:
        func: Handler async a proteger.

    Returns:
        Wrapper que verifica autorización.
    """

    @functools.wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args,
        **kwargs,
    ):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id is None:
            logger.warning("Update sin effective_user, denegando acceso")
            return ConversationHandler.END

        user_role = get_user_role(user_id)

        if user_role is None:
            logger.warning(
                "Acceso denegado: usuario %d no autorizado",
                user_id,
            )
            await _send_denied_message(update, Messages.NOT_AUTHORIZED)
            return ConversationHandler.END

        return await func(update, context, *args, **kwargs)

    return wrapper


async def _send_denied_message(update: Update, text: str) -> None:
    """Envía un mensaje de acceso denegado al usuario.

    Soporta tanto mensajes directos como callback queries.

    Args:
        update: Update de Telegram.
        text: Texto del mensaje de denegación.
    """
    if update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
    elif update.message:
        await update.message.reply_text(text)
