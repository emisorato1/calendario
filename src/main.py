# src/main.py
"""Entry point del sistema — arranca BD, Calendar, LLM, Orchestrator y Bot."""

import asyncio
import logging
import sys

from src.bot.app import create_application
from src.calendar_api.async_wrapper import AsyncGoogleCalendarClient
from src.calendar_api.client import GoogleCalendarClient
from src.config import get_settings, validate_settings
from src.core.logging_config import setup_logging
from src.db.database import DatabaseManager
from src.db.repository import Repository
from src.llm.client import build_llm_chain
from src.llm.parser import LLMParser
from src.orchestrator.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


async def main() -> None:
    """Inicializa todos los componentes y arranca el bot en modo polling."""

    # 1. Cargar y validar configuración (fail-fast si falta algo)
    settings = get_settings()
    validate_settings()

    # 2. Configurar logging
    setup_logging(settings.log_level, settings.log_file)
    logger.info("Configuración cargada correctamente")

    # 3. Inicializar base de datos
    db_manager = DatabaseManager(settings.sqlite_db_path)
    await db_manager.connect()
    await db_manager.initialize()
    logger.info("Base de datos inicializada: %s", settings.sqlite_db_path)

    repository = Repository(db_manager.db)

    # 4. Inicializar Google Calendar (sync client envuelto en async)
    sync_calendar = GoogleCalendarClient(
        settings.google_service_account_path,
        settings.google_calendar_id,
    )
    calendar_client = AsyncGoogleCalendarClient(sync_calendar)
    logger.info("Google Calendar inicializado")

    # 5. Inicializar LLM Parser (cadena con fallback)
    llm_chain = build_llm_chain()
    llm_parser = LLMParser(llm_chain)
    logger.info("LLM Parser inicializado")

    # 6. Crear Orquestador
    orchestrator = Orchestrator(
        repository=repository,
        calendar_client=calendar_client,
        llm_parser=llm_parser,
        settings=settings,
    )
    logger.info("Orquestador creado")

    # 7. Crear y ejecutar Bot
    app = create_application(orchestrator)
    logger.info("Bot iniciando en modo polling...")

    try:
        app.run_polling(drop_pending_updates=True)
    finally:
        await db_manager.close()
        logger.info("Sistema finalizado")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot detenido por el usuario.")
        sys.exit(0)
    except SystemExit as e:
        # validate_settings() lanza SystemExit con mensaje descriptivo
        print(str(e))
        sys.exit(1)
