# src/bot/app.py
"""Configuración de la Application de python-telegram-bot, registro de handlers
y punto de entrada para polling."""

import logging

from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler

from src.bot.handlers import (
    contactos,
    crear_evento,
    editar_evento,
    eliminar_evento,
    natural,
    start,
    terminar_evento,
    ver_eventos,
)
from src.bot.handlers.start import MENU_BUTTON_FILTER, menu_text_handler
from src.config import get_settings

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler global de errores.

    Loguea el error y, si hay un chat disponible, notifica al usuario.

    Args:
        update: Update que causó el error (puede ser None).
        context: Contexto con la excepción en context.error.
    """
    logger.error("Excepción no manejada:", exc_info=context.error)

    # Intentar notificar al usuario
    try:
        if update and hasattr(update, "effective_chat") and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ocurrió un error inesperado. Por favor, intentá de nuevo.",
            )
    except Exception:
        logger.error("No se pudo notificar al usuario del error", exc_info=True)


def create_application(orchestrator=None) -> Application:
    """Crea y configura la Application con todos los handlers registrados.

    Args:
        orchestrator: Instancia del Orchestrator para inyectar en bot_data.
            Si es None, se espera que sea inyectado antes de iniciar polling.

    Returns:
        Application configurada y lista para ejecutar.
    """
    settings = get_settings()

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Inyectar orchestrator en bot_data para que los handlers lo usen
    if orchestrator is not None:
        app.bot_data["orchestrator"] = orchestrator

    _register_handlers(app)

    # Error handler global
    app.add_error_handler(error_handler)

    logger.info("Application creada y handlers registrados")
    return app


def _register_handlers(app: Application) -> None:
    """Registra todos los handlers en el orden correcto.

    ORDEN IMPORTANTE:
    1. Comandos /start y /menu
    2. ConversationHandlers (tienen prioridad sobre handlers simples)
    3. Handlers inmediatos (ver eventos, ver contactos, menú callback)
    4. Handler natural (ÚLTIMO — solo captura texto que no matcheó antes)

    Args:
        app: Application donde registrar los handlers.
    """
    # 1. Comandos /start y /menu
    for handler in start.get_start_handlers():
        app.add_handler(handler)

    # 2. ConversationHandlers
    app.add_handler(crear_evento.get_conversation_handler())
    app.add_handler(editar_evento.get_conversation_handler())
    app.add_handler(eliminar_evento.get_conversation_handler())
    app.add_handler(terminar_evento.get_conversation_handler())
    app.add_handler(contactos.get_editar_contacto_handler())

    # 3. Handlers inmediatos (CallbackQueryHandler sin conversación)
    for handler in ver_eventos.get_ver_eventos_handlers():
        app.add_handler(handler)
    for handler in contactos.get_ver_contactos_handlers():
        app.add_handler(handler)

    # 4. Botón persistente "📋 Menú" — DESPUÉS de ConversationHandlers
    #    para que los fallbacks de las conversaciones tengan prioridad
    #    y cierren la conversación activa antes de mostrar el menú.
    app.add_handler(MessageHandler(MENU_BUTTON_FILTER, menu_text_handler))

    # 5. Handler de texto natural — SIEMPRE ÚLTIMO
    app.add_handler(natural.get_natural_handler())

    logger.info("Handlers registrados: %d en total", len(app.handlers.get(0, [])))


def run_polling(orchestrator=None) -> None:
    """Punto de entrada principal: crea la app e inicia polling.

    Args:
        orchestrator: Instancia del Orchestrator. Si es None, se espera
            que sea configurado antes de llamar a esta función.
    """
    app = create_application(orchestrator)
    logger.info("Iniciando bot en modo polling...")
    app.run_polling(drop_pending_updates=True)
