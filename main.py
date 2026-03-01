"""Entry point del Agente Calendario v2."""

from __future__ import annotations

import asyncio
import signal
import sys

import aiosqlite
from telegram.ext import Application, CommandHandler

from agents.telegram_listener.commands import (
    clientes_command,
    help_command,
    start_command,
    status_command,
)
from agents.telegram_listener.handler import build_conversation_handler
from agents.telegram_listener.keyboards import get_main_menu
from config.settings import Settings
from core.logger import configure_logging, get_logger


log = get_logger(__name__)


async def post_init(application: Application) -> None:
    """Callback post-inicio: abre conexión DB persistente, crea repositorio e inyecta al orchestrator."""
    settings: Settings = application.bot_data["settings"]

    # ── Abrir conexión DB persistente ─────────────────────────────────────────
    from agents.db_manager.migrations import run_migrations
    from agents.db_manager.repository import DBRepository

    conn = await aiosqlite.connect(settings.sqlite_db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.commit()
    await run_migrations(conn)
    log.info("db_inicializada")

    # Guardar conexión para cerrarla en post_shutdown
    application.bot_data["db_conn"] = conn

    # Crear repositorio y asignarlo
    repository = DBRepository(conn=conn)
    application.bot_data["repository"] = repository

    # Inyectar repositorio al orchestrator
    orchestrator = application.bot_data["orchestrator"]
    orchestrator._repo = repository
    log.info("repository_inyectado_en_orchestrator")

    # ── Enviar menú a cada usuario autorizado ─────────────────────────────────
    for admin_id in settings.admin_telegram_ids:
        try:
            menu = get_main_menu(admin_id, settings)
            await application.bot.send_message(
                chat_id=admin_id,
                text="🤖 Bot iniciado. Menú disponible.",
                reply_markup=menu,
            )
        except Exception as exc:
            log.warning("no_se_pudo_enviar_menu_admin", admin_id=admin_id, error=str(exc))

    for editor_id in settings.editor_telegram_ids:
        try:
            menu = get_main_menu(editor_id, settings)
            await application.bot.send_message(
                chat_id=editor_id,
                text="🤖 Bot iniciado. Menú disponible.",
                reply_markup=menu,
            )
        except Exception as exc:
            log.warning("no_se_pudo_enviar_menu_editor", editor_id=editor_id, error=str(exc))

    log.info(
        "bot_iniciado",
        admins=len(settings.admin_telegram_ids),
        editors=len(settings.editor_telegram_ids),
    )


async def post_shutdown(application: Application) -> None:
    """Callback post-shutdown: cierra conexión DB persistente."""
    conn = application.bot_data.get("db_conn")
    if conn is not None:
        await conn.close()
        log.info("db_conexion_cerrada")


def main() -> None:
    """Función principal: configura y ejecuta el bot."""
    # 1. Cargar Settings — fail-fast si faltan vars requeridas
    try:
        settings = Settings()
    except Exception as exc:
        print(f"ERROR: No se pudo cargar la configuración: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Configurar logging
    configure_logging(log_level=settings.log_level, log_file=settings.log_file)
    log.info("configuracion_cargada", calendar_id=settings.google_calendar_id)

    # 3. Construir Application de python-telegram-bot
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # 4. Inyectar dependencias en bot_data
    application.bot_data["settings"] = settings

    # Groq client
    from agents.groq_parser.client import GroqClient

    groq_client = GroqClient(
        api_key=settings.groq_api_key,
        model_primary=settings.groq_model_primary,
        model_fallback=settings.groq_model_fallback,
        max_tokens=settings.groq_max_tokens,
        temperature=settings.groq_temperature,
    )
    application.bot_data["groq_client"] = groq_client

    # Calendar client
    from agents.calendar_sync.auth import get_credentials
    from agents.calendar_sync.client import CalendarClient

    credentials = get_credentials(settings.google_service_account_path)
    calendar_client = CalendarClient(
        credentials=credentials,
        calendar_id=settings.google_calendar_id,
    )
    application.bot_data["calendar_client"] = calendar_client

    # Orchestrator (repository se inyecta en post_init cuando la conexión DB está activa)
    from core.orchestrator import Orchestrator

    orchestrator = Orchestrator(
        settings=settings,
        groq_client=groq_client,
        repository=None,  # Se configura en post_init con la conexión DB activa
        calendar_client=calendar_client,
    )
    application.bot_data["orchestrator"] = orchestrator

    # 5. Registrar handlers
    conv_handler = build_conversation_handler(settings)
    application.add_handler(conv_handler)

    # Comandos que funcionan fuera de la conversación
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("clientes", clientes_command))

    # 6. Arrancar polling con graceful shutdown
    log.info("iniciando_polling")
    application.run_polling(
        drop_pending_updates=True,
        stop_signals=[signal.SIGINT, signal.SIGTERM],
    )


if __name__ == "__main__":
    main()
