# Logging Setup

## Configuración

```python
# src/core/logging_config.py
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: str = "DEBUG", log_file: str = "logs/agente.log"):
    """Configura el logging del sistema."""
    
    # Crear directorio de logs si no existe
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Formato consistente
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-25s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de archivo con rotación
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper()))
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Silenciar loggers ruidosos
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
```

## Uso en Módulos

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Evento creado: %s", evento_id)
logger.warning("LLM fallback activado: %s → %s", provider_1, provider_2)
logger.error("Error creando evento en Calendar: %s", error, exc_info=True)
```

## Formato del Log

```
[2026-03-01 12:30:00] INFO     src.orchestrator          │ Evento creado: 42 para Juan Pérez
[2026-03-01 12:30:01] WARNING  src.llm.parser            │ LLM fallback: groq → gemini
[2026-03-01 12:30:02] ERROR    src.calendar_api.client    │ Google Calendar API error: 429 Rate Limit
```

## Notas

- Rotación automática a 5 MB, 3 backups (máximo ~20 MB en disco).
- Nunca loguear datos sensibles (tokens, API keys).
- Usar `%s` para interpolación lazy (evita formatear si el nivel no aplica).
- `exc_info=True` para incluir traceback en errores.
