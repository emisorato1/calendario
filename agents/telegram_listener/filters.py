"""Filtros de autorización para mensajes de Telegram."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import Message
from telegram.ext.filters import MessageFilter

from config.settings import Settings
from core.logger import get_logger

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


class AuthorizedUserFilter(MessageFilter):
    """Deja pasar mensajes solo de usuarios en ADMIN_TELEGRAM_IDS o EDITOR_TELEGRAM_IDS.

    Los demás se ignoran silenciosamente con un log WARNING del user_id.
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    def filter(self, message: Message) -> bool:
        """Filtra mensajes no autorizados."""
        user_id = message.from_user.id if message.from_user else None
        if user_id is None:
            log.warning("mensaje_sin_usuario", message_id=message.message_id)
            return False

        if self._settings.is_authorized(user_id):
            return True

        log.warning(
            "acceso_no_autorizado",
            user_id=user_id,
            username=message.from_user.username if message.from_user else None,
        )
        return False


class AdminOnlyFilter(MessageFilter):
    """Deja pasar mensajes únicamente de IDs en ADMIN_TELEGRAM_IDS."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    def filter(self, message: Message) -> bool:
        """Filtra mensajes que no son de un Admin."""
        user_id = message.from_user.id if message.from_user else None
        if user_id is None:
            return False

        if self._settings.is_admin(user_id):
            return True

        log.warning(
            "accion_admin_denegada",
            user_id=user_id,
            username=message.from_user.username if message.from_user else None,
        )
        return False


class EditorOrAdminFilter(MessageFilter):
    """Deja pasar mensajes de IDs en ADMIN_TELEGRAM_IDS o EDITOR_TELEGRAM_IDS."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    def filter(self, message: Message) -> bool:
        """Filtra mensajes que no son de un Admin ni Editor."""
        user_id = message.from_user.id if message.from_user else None
        if user_id is None:
            return False

        return self._settings.is_authorized(user_id)
