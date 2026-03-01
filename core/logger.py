"""Configuración de logging estructurado con structlog."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

import structlog


def configure_logging(
    log_level: str = "INFO",
    log_file: str = "logs/agente.log",
) -> None:
    """
    Configura structlog con salida JSON a archivo (con rotación) y a consola.

    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Ruta del archivo de log. La carpeta se crea si no existe.
    """
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Handler de archivo con rotación: max 10 MB, 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)

    logging.basicConfig(
        level=numeric_level,
        handlers=[file_handler, console_handler],
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Retorna un logger estructurado con el nombre del módulo."""
    return structlog.get_logger(name)
