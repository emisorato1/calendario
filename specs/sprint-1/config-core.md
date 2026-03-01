# Sprint 1 — Configuración Core

## Descripción

Establecer la base del proyecto: estructura de carpetas, configuración
centralizada con Pydantic, sistema de logging con rotación, excepciones
de dominio tipadas y validación de arranque.

## Objetivos

- [x] Crear la estructura de carpetas del proyecto (`src/`, `tests/`, `data/`, `logs/`).
- [x] Implementar `config.py` con Pydantic Settings y validación de `.env`.
- [x] Incluir configuración de horario laboral (lunes-viernes, sábados, domingos bloqueados).
- [x] Configurar logging estructurado con rotación de archivos.
- [x] Definir jerarquía de excepciones de dominio.
- [x] Crear `pyproject.toml` con dependencias y metadata.
- [x] Verificar que el sistema arranca correctamente con `.env.example`.

## Requisitos Técnicos

| Requisito                         | Detalle                                  |
| --------------------------------- | ---------------------------------------- |
| Python                            | 3.11+                                    |
| Config                            | `pydantic-settings` v2                   |
| Logging                           | `logging` stdlib + RotatingFileHandler   |
| Variables de entorno              | `.env` + `.env.example`                  |
| Validación al inicio              | Fail-fast si falta config crítica        |

## Pasos de Implementación

### 1. Estructura de Carpetas

```bash
mkdir -p src/{bot/handlers,llm,calendar_api,db,orchestrator,core}
mkdir -p tests/{unit,integration}
mkdir -p data logs
touch src/__init__.py src/bot/__init__.py src/bot/handlers/__init__.py
touch src/llm/__init__.py src/calendar_api/__init__.py
touch src/db/__init__.py src/orchestrator/__init__.py src/core/__init__.py
```

### 2. Configuración (`src/config.py`)

- Implementar `Settings` con Pydantic Settings.
- Parsear `ADMIN_TELEGRAM_IDS` y `EDITOR_TELEGRAM_IDS` desde JSON strings.
- Incluir campos de horario laboral (`WORK_DAYS_WEEKDAY_START/END`, `WORK_DAYS_SATURDAY_START/END`).
- Valores por defecto sensatos para desarrollo.
- Función `get_settings()` con patrón singleton.
- Función `validate_settings()` para verificación al inicio.

### 3. Logging (`src/core/logging_config.py`)

- Formato: `[timestamp] LEVEL module │ message`.
- RotatingFileHandler: 5 MB, 3 backups.
- Handler de consola.
- Silenciar loggers ruidosos (httpx, googleapiclient).

### 4. Excepciones (`src/core/exceptions.py`)

- `AgenteCalendarioError` (base).
- `DatabaseError`, `ClienteNotFoundError`, `EventoNotFoundError`.
- `CalendarError`, `CalendarSyncError`.
- `LLMError`, `LLMParsingError`, `LLMUnavailableError`.
- `ScheduleConflictError`, `PermissionDeniedError`, `InvalidDateError`.

### 5. Dependencias (`pyproject.toml`)

```toml
[project]
name = "agente-calendario"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "python-telegram-bot>=20.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "aiosqlite>=0.19.0",
    "groq>=0.4.0",
    "google-api-python-client>=2.0",
    "google-auth>=2.0",
    "thefuzz[speedup]>=0.20.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
]
```

### 6. Tests

- `tests/unit/test_config.py`: Verificar parsing de settings.
- `tests/unit/test_exceptions.py`: Verificar jerarquía de excepciones.

## Criterios de Aceptación

- [x] `python -c "from src.config import get_settings"` no falla.
- [x] Los logs se escriben en `logs/agente.log` con rotación.
- [x] Si falta `TELEGRAM_BOT_TOKEN`, el sistema falla al arrancar con mensaje claro.
- [x] Todos los tests pasan (`pytest tests/unit/`).

## Skills Referenciadas

- [Config & Observability](../../skills/config-observability/SKILL.md)
  - [Pydantic Settings](../../skills/config-observability/references/pydantic-settings.md)
  - [Logging Setup](../../skills/config-observability/references/logging-setup.md)
  - [Excepciones de Dominio](../../skills/config-observability/references/domain-exceptions.md)
